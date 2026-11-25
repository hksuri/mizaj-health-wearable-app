from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from mizaj.agent.loop import run_chat_turn
from mizaj.config import settings
from mizaj.data.duckdb import connect_gold
from mizaj.db.models import SessionRow
from mizaj.db.session import init_db

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1)


def _db() -> Session:
    init_db()
    from mizaj.db.session import _SessionLocal

    assert _SessionLocal is not None
    return _SessionLocal()


@router.post("/chat")
async def chat(body: ChatRequest) -> EventSourceResponse:
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="message required")

    db = _db()
    session_id = body.session_id or str(uuid.uuid4())
    if body.session_id is None:
        db.add(SessionRow(id=session_id))
        db.commit()
    else:
        existing = db.get(SessionRow, session_id)
        if existing is None:
            db.add(SessionRow(id=session_id))
            db.commit()

    try:
        gold = connect_gold()
    except FileNotFoundError as exc:
        db.close()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def event_gen() -> Any:
        try:
            yield {"event": "session", "data": json.dumps({"session_id": session_id})}
            async for item in run_chat_turn(
                db=db, gold=gold, session_id=session_id, question=body.message.strip()
            ):
                yield {
                    "event": item["event"],
                    "data": json.dumps(item["data"], default=str),
                }
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}
        finally:
            gold.close()
            db.close()

    # sse-starlette typing expects ContentStream; async generator is correct at runtime
    return EventSourceResponse(event_gen())  # type: ignore[arg-type]
