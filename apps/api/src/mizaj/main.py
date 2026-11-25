from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mizaj import __version__
from mizaj.config import settings

app = FastAPI(title="Mizaj API", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
