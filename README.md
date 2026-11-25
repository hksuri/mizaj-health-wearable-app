# Mizaj

Personal health-trends chatbot over Fitbit / Google Health data. Local-first: typed tools over DuckDB gold tables, streamed answers, charts, and an eval harness.

## Architecture

```text
Browser (Next.js) --SSE/REST--> FastAPI agent + tools
                                      |
                               DuckDB gold (local)
                                      ^
                         ingest CLI <- Google Health API
```

Design docs: [PLAN.md](PLAN.md) · [docs/hld.md](docs/hld.md) · [docs/lld.md](docs/lld.md) · [docs/implementation-plan.md](docs/implementation-plan.md)  
UI mockups: [docs/mockups/mizaj-ui/](docs/mockups/mizaj-ui/)  
Privacy: [docs/privacy.md](docs/privacy.md)

## Quick start (synthetic, no Google OAuth)

```bash
# Tooling: uv (Python 3.12) + pnpm
make install
make synth          # silver fixtures + data/health.duckdb
cp .env.example .env
# set ANTHROPIC_API_KEY in .env for chat

make api            # http://127.0.0.1:8000/health
make web            # http://localhost:3000
```

`make test` and `make lint` should pass on a fresh clone without credentials.

## Status

| Area | State |
| --- | --- |
| Scaffold, synth gold, tools, agent SSE, chat UI + theme | Done (phase 1 without Google) |
| Google Health OAuth + real backfill | Needs your Cloud project / `ingest auth` (tasks 1.3–1.4) |
| Eval harness (100 scenarios) | Phase 2+ |

## Theme

Light/dark toggle in the chat header. Default follows OS `prefers-color-scheme`; override stored as `mizaj-theme` in `localStorage`.
