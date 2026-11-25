# Mizaj

Personal health-trends chatbot over your Fitbit / Google Health data (local-first).

## Status

Phase 1 scaffold. Design docs in [`docs/`](docs/). UI mockups in [`docs/mockups/mizaj-ui/`](docs/mockups/mizaj-ui/).

## Quick start (skeleton)

```bash
# Python (uv) + JS (pnpm)
make install
make test
make lint

# API
make api
# http://127.0.0.1:8000/health

# Web (after Next app is present)
make web
```

Full architecture and task plan: [PLAN.md](PLAN.md).

## Privacy

Real data stays under gitignored `data/`. Committed evals and demos use a synthetic persona only. See `docs/privacy.md` (added in task 1.8).
