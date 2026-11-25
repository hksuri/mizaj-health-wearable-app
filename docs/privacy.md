# Privacy — Mizaj

Mizaj is local-first and single-user.

## What stays on your machine

- Bronze / silver / gold health data under `data/` (gitignored)
- SQLite sessions, traces, and annotation labels
- OAuth refresh tokens in the OS keychain (`mizaj-google-health`)
- Application logs (structured metadata only; full tool payloads are not logged at INFO)

## What leaves your machine

- Chat turns send the system prompt, recent user/assistant text, tool schemas, and **tool results** to the Anthropic API (default: daily aggregates).
- Eval scenario generation / judging, when run, also sends synthetic-persona prompts and answers to Anthropic.
- Google Health API calls during ingest send OAuth access tokens to Google and download your consented health data into local bronze files.

## What we do not do

- Multi-user hosting of real health data
- Committing personal Parquet/DuckDB/JSON under `data/`
- Using real-data screenshots or eval sets in the public repo (synthetic persona only)

## Operator tips

- Prefer daily aggregates in tools; query intraday only when the question requires it.
- Keep `ANTHROPIC_API_KEY` in `.env` (never commit).
- Re-run `ingest auth` when Testing-mode refresh tokens expire (~7 days).
