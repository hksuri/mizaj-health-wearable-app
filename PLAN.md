# Health Trends Chatbot — Plan Index

Audience: coding agents. Read this file first, then the design docs it points to. Where this plan and the official Google Health API or Claude API docs disagree, the docs win; record the difference in `docs/adr/`.

## Goal

A personal chatbot for one user's Fitbit / Google Health wearable data: plain-language questions about trends, typed tools over local gold tables, streamed text answers, and charts when useful. Second deliverable: an evaluation harness (v1: **100** scenarios, human annotation UI, LLM judge, Cohen's kappa; stretch to 500 later).

Success criteria, non-goals, architecture, contracts, and task sequencing live in the docs below — not in this index.

## Design documents (read in order)

| Doc | Role |
| --- | --- |
| [docs/hld.md](docs/hld.md) | High-level design: context, containers, decision log (D1–D19), v1 scope, risks |
| [docs/lld.md](docs/lld.md) | Low-level design: ingest/auth, silver/gold schemas, tools, SSE, SQLite, evals |
| [docs/implementation-plan.md](docs/implementation-plan.md) | Phased build tasks with acceptance criteria citing HLD/LLD |

Do not invent schemas, errors, or stack choices missing from those docs. If a contract is wrong, update HLD/LLD (and an ADR) before coding.

## Locked stack

| Area | Decision |
| --- | --- |
| UI | FastAPI backend + Next.js/React frontend; SSE chat |
| Storage | Parquet + DuckDB (bronze / silver / gold); SQLite for sessions, traces, labels |
| Runtime | Local `docker-compose` (`api` + `web`); ingest is a CLI |
| Data access | Google Health API (`https://health.googleapis.com/v4`), Google OAuth 2.0 |
| LLM | App: `claude-haiku-5-5`. Judge / scenarios: `claude-sonnet-5-5` |
| Packages | Python 3.12 + `uv`; TypeScript + `pnpm` |

## Do not add

LangChain or other agent frameworks, a vector database, Kafka, Kubernetes, or any hosted observability product. If you think one is needed, write an ADR and ask.

## Conventions

- Small PRs per implementation-plan task; tests + lint must pass.
- Type everything (`ruff`, `pyright`, `eslint`, `tsc`).
- Never read, print, or commit personal files under `data/`. CI and committed evals use the synthetic persona only.
- Prefer boring code.
