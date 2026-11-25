from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import date
from pathlib import Path
from typing import Any, Literal, cast

import duckdb
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolParam
from sqlalchemy.orm import Session

from mizaj.agent import tools as tool_fns
from mizaj.agent.chart_spec import build_chart_spec
from mizaj.agent.grounding import find_ungrounded
from mizaj.agent.metrics_registry import registry_prompt_lines
from mizaj.agent.pricing import estimate_cost_usd
from mizaj.agent.tools import ToolError
from mizaj.config import settings
from mizaj.db.models import MessageRow, TraceRow

PROMPT_VERSION = "sys_v1"
MAX_TOOL_CALLS = 4
HISTORY_MESSAGES = 12

TOOL_SCHEMAS: list[ToolParam] = [
    {
        "name": "list_available_metrics",
        "description": "List metrics with units and coverage dates.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_metric_series",
        "description": "Get a metric time series by day or week.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "granularity": {"type": "string", "enum": ["day", "week"]},
            },
            "required": ["metric", "start", "end"],
        },
    },
    {
        "name": "compare_periods",
        "description": "Compare metric means across two date ranges.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string"},
                "a_start": {"type": "string"},
                "a_end": {"type": "string"},
                "b_start": {"type": "string"},
                "b_end": {"type": "string"},
            },
            "required": ["metric", "a_start", "a_end", "b_start", "b_end"],
        },
    },
    {
        "name": "get_baseline_and_anomalies",
        "description": "Return baseline mean/std and high-z days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string"},
                "window_days": {"type": "integer"},
            },
            "required": ["metric"],
        },
    },
    {
        "name": "get_sleep_summary",
        "description": "Per-night sleep stages and averages.",
        "input_schema": {
            "type": "object",
            "properties": {"start": {"type": "string"}, "end": {"type": "string"}},
            "required": ["start", "end"],
        },
    },
    {
        "name": "correlate_metrics",
        "description": "Spearman correlation between two metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_x": {"type": "string"},
                "metric_y": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
            "required": ["metric_x", "metric_y", "start", "end"],
        },
    },
    {
        "name": "render_chart",
        "description": "Request a chart from a prior tool result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_call_id": {"type": "string"},
                "kind": {"type": "string", "enum": ["line", "bar", "scatter"]},
                "title": {"type": "string"},
            },
            "required": ["source_call_id", "kind", "title"],
        },
    },
]


def load_system_prompt() -> str:
    path = Path(__file__).parent / "prompts" / "system.md"
    text = path.read_text(encoding="utf-8")
    return text.replace("{{metrics}}", "\n".join(registry_prompt_lines()))


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _execute_tool(
    con: duckdb.DuckDBPyConnection,
    name: str,
    args: dict[str, Any],
    stored: dict[str, dict[str, Any]],
) -> tuple[Any, str | None]:
    """Return (result, source_shape for chart)."""
    if name == "list_available_metrics":
        return tool_fns.list_available_metrics(con), None
    if name == "get_metric_series":
        result = tool_fns.get_metric_series(
            con,
            args["metric"],
            _parse_date(args["start"]),
            _parse_date(args["end"]),
            args.get("granularity", "day"),
        )
        return result, "series"
    if name == "compare_periods":
        result = tool_fns.compare_periods(
            con,
            args["metric"],
            _parse_date(args["a_start"]),
            _parse_date(args["a_end"]),
            _parse_date(args["b_start"]),
            _parse_date(args["b_end"]),
        )
        return result, "series"
    if name == "get_baseline_and_anomalies":
        result = tool_fns.get_baseline_and_anomalies(
            con, args["metric"], int(args.get("window_days", 30))
        )
        return result, "series"
    if name == "get_sleep_summary":
        result = tool_fns.get_sleep_summary(
            con, _parse_date(args["start"]), _parse_date(args["end"])
        )
        return result, "sleep"
    if name == "correlate_metrics":
        result = tool_fns.correlate_metrics(
            con,
            args["metric_x"],
            args["metric_y"],
            _parse_date(args["start"]),
            _parse_date(args["end"]),
        )
        return result, "pairs"
    if name == "render_chart":
        source = stored.get(args["source_call_id"])
        if source is None:
            return (
                ToolError(error_code="SOURCE_NOT_FOUND", message="Unknown source_call_id"),
                None,
            )
        shape = source.get("shape", "unknown")
        ack = tool_fns.render_chart_ack(shape, args["kind"])
        return ack, shape
    return ToolError(error_code="INTERNAL", message=f"Unknown tool {name}"), None


def _summarize(result: Any) -> str:
    if isinstance(result, ToolError):
        return f"error {result.error_code}: {result.message}"
    if isinstance(result, dict) and "n" in result:
        return f"ok n={result.get('n')}"
    if isinstance(result, dict) and "metrics" in result:
        return f"ok metrics={len(result['metrics'])}"
    if isinstance(result, dict) and result.get("chart_queued"):
        return "chart queued"
    return "ok"


def _chart_rows_from_source(source: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str]:
    payload = source["result"]
    shape = source.get("shape")
    if isinstance(payload, ToolError):
        return [], "value", "Series"
    if shape == "series" and "rows" in payload:
        return payload["rows"], payload.get("unit", "value"), payload.get("metric", "Series")
    if shape == "sleep" and "nights" in payload:
        rows = [{"date": n["date"], "value": n["duration_min"]} for n in payload["nights"]]
        return rows, "min", "Sleep"
    if shape == "pairs" and payload.get("spearman_r") is not None:
        # scatter needs pairs; correlate tool doesn't return pairs — empty chart
        return [], "y", "Correlation"
    return [], "value", "Series"


async def run_chat_turn(
    *,
    db: Session,
    gold: duckdb.DuckDBPyConnection,
    session_id: str,
    question: str,
    client: AsyncAnthropic | None = None,
    model: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    started = time.perf_counter()
    model = model or settings.app_model
    client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)
    trace_id = str(uuid.uuid4())

    history = (
        db.query(MessageRow)
        .filter(MessageRow.session_id == session_id)
        .order_by(MessageRow.created_at.asc())
        .all()
    )
    recent = history[-HISTORY_MESSAGES:]
    messages: list[dict[str, Any]] = [
        {"role": m.role, "content": m.content} for m in recent if m.role in {"user", "assistant"}
    ]
    messages.append({"role": "user", "content": question})

    db.add(MessageRow(id=str(uuid.uuid4()), session_id=session_id, role="user", content=question))
    db.commit()

    stored_results: dict[str, dict[str, Any]] = {}
    tool_trace: list[dict[str, Any]] = []
    answer_parts: list[str] = []
    chart_spec: dict[str, Any] | None = None
    input_tokens = 0
    output_tokens = 0
    tool_calls = 0

    system = load_system_prompt()

    while True:
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            tools=TOOL_SCHEMAS,
            messages=cast(list[MessageParam], messages),
        )
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        for block in text_blocks:
            answer_parts.append(block.text)
            yield {"event": "text_delta", "data": {"text": block.text}}

        if response.stop_reason != "tool_use" or not tool_uses:
            break

        tool_results_content: list[dict[str, Any]] = []
        for block in tool_uses:
            if tool_calls >= MAX_TOOL_CALLS:
                tool_results_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(
                            {"ok": False, "error_code": "INTERNAL", "message": "tool call cap"}
                        ),
                        "is_error": True,
                    }
                )
                continue
            tool_calls += 1
            args = block.input if isinstance(block.input, dict) else {}
            yield {"event": "tool_call", "data": {"id": block.id, "name": block.name, "args": args}}
            result, shape = _execute_tool(gold, block.name, args, stored_results)
            payload = result.model_dump() if isinstance(result, ToolError) else result
            stored_results[block.id] = {
                "result": result,
                "shape": shape,
                "name": block.name,
                "args": args,
            }
            tool_trace.append({"id": block.id, "name": block.name, "args": args, "result": payload})
            yield {
                "event": "tool_result",
                "data": {
                    "id": block.id,
                    "ok": not isinstance(result, ToolError),
                    "summary": _summarize(result),
                },
            }

            if (
                block.name == "render_chart"
                and isinstance(result, dict)
                and result.get("chart_queued")
            ):
                source_id = str(args["source_call_id"])
                kind = cast(Literal["line", "bar", "scatter"], args["kind"])
                title = str(args["title"])
                source = stored_results.get(source_id)
                if source:
                    rows, y_label, series_name = _chart_rows_from_source(source)
                    chart_spec = build_chart_spec(
                        kind, title, rows, y_label=y_label, series_name=series_name
                    )
                    yield {"event": "chart", "data": chart_spec}

            tool_results_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(payload, default=str),
                    "is_error": isinstance(result, ToolError),
                }
            )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results_content})

    answer = "".join(answer_parts).strip()
    ungrounded = find_ungrounded(answer, [t["result"] for t in tool_trace])
    cost = estimate_cost_usd(model, input_tokens, output_tokens)
    latency_ms = int((time.perf_counter() - started) * 1000)

    db.add(
        MessageRow(id=str(uuid.uuid4()), session_id=session_id, role="assistant", content=answer)
    )
    db.add(
        TraceRow(
            trace_id=trace_id,
            session_id=session_id,
            question=question,
            model=model,
            prompt_version=PROMPT_VERSION,
            tool_calls_json=json.dumps(tool_trace, default=str),
            answer=answer,
            chart_json=json.dumps(chart_spec) if chart_spec else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            ungrounded_numbers_json=json.dumps(ungrounded) if ungrounded else None,
        )
    )
    db.commit()

    yield {
        "event": "done",
        "data": {
            "trace_id": trace_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "latency_ms": latency_ms,
        },
    }


# Convenience for tests injecting a fake client factory
ClientFactory = Callable[[], AsyncAnthropic]
