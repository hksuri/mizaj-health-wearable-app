# Mizaj — Implementation Plan

Status: draft for review  
Upstream: [hld.md](hld.md), [lld.md](lld.md)  
Index: [PLAN.md](../PLAN.md)

**Product name:** Mizaj (HLD D20). Python package `mizaj`; UI and README use Mizaj.

Coding agents execute tasks in order within each phase. Every task cites the HLD decision and LLD section it implements. Do not invent contracts; update HLD/LLD (and an ADR if needed) first.

Task shape: **Depends on** · **Creates** · **Acceptance** · **Docs to update**

---

## Phase 1 — First weekend (working chatbot)

Synthetic cut line: if Google OAuth stalls (tasks 1.3–1.4), continue with synthetic data through 1.8 and finish OAuth later. Chatbot acceptance may use synthetic gold until real backfill succeeds.

### 1.1 Monorepo scaffold

- **HLD / LLD:** D1, D2, D13, D17 · LLD B4 bind/CORS, Part D logging stub
- **Depends on:** nothing
- **Creates:** `apps/api` (`uv`), `apps/web` (`pnpm`), `packages/ingest`, `docker-compose.yml`, `Makefile`, `.env.example`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `AGENTS.md`, `data/.gitkeep` + gitignore rules, empty `tests/`
- **Acceptance:** `make test` and `make lint` pass on the skeleton
- **Docs:** README stub with run placeholders

### 1.2 Synthetic data + gold build

- **HLD / LLD:** D8, D12, D15 · LLD A3–A5, A4 publish
- **Depends on:** 1.1
- **Creates:** `scripts/make_synthetic_data.py`, silver under `data/` (gitignored) via `make synth`, gold SQL, `tests/fixtures/synthetic/silver/`, pytest row-count/null checks
- **Acceptance:** `make synth` produces published `data/health.duckdb`; coverage and null checks pass
- **Docs:** note synthetic persona in README

### 1.3 Google Cloud + `ingest auth`

- **HLD / LLD:** D3, D4, D5 · LLD A1
- **Depends on:** 1.1 (can parallel 1.2)
- **Creates:** `packages/ingest` auth module, keyring integration, CLI `ingest auth`
- **Acceptance:** Authenticated `users.getIdentity` succeeds; refresh token in keychain; `ACCOUNT_NOT_LINKED` path documented
- **Docs:** ADR stub if setup differs; README auth section

### 1.4 Backfill bronze → silver → gold (real data)

- **HLD / LLD:** D3, D8, D12, D16 · LLD A2–A4
- **Depends on:** 1.3; ideally 1.2 schemas exist
- **Creates:** client, backfill/sync/build, checkpointing, real silver writers, **redacted** `tests/fixtures/api_shapes/` after first success, `docs/adr/0001-data-access.md` (history depth)
- **Acceptance:** Resumable backfill; idempotent re-run; coverage filled; freeze-after-sample fields updated in LLD
- **Docs:** LLD freeze items; ADR 0001

### 1.4b Fixtures before tools (explicit)

- **HLD / LLD:** D8 · LLD A3 fixtures
- **Depends on:** 1.2 (synthetic required); 1.4 for real shape (optional until OAuth works)
- **Creates:** Committed synthetic silver fixture (from 1.2); redacted API shape fixture when available
- **Acceptance:** Tools and tests bind to fixtures; CI never reads `data/` personal files
- **Docs:** none beyond fixture README one-liner

### 1.5 Metrics registry + six data tools

- **HLD / LLD:** D7, D8 · LLD B1, B2 (all tools except chart wiring in 1.6)
- **Depends on:** 1.2, 1.4b synthetic fixture
- **Creates:** `metrics_registry.py`, tool functions + Pydantic models, unit tests on synthetic gold
- **Acceptance:** Each tool tested including `OUT_OF_COVERAGE` / `UNKNOWN_METRIC`
- **Docs:** none if LLD unchanged

### 1.6 Agent loop + SSE chat + tracing

- **HLD / LLD:** D6, D7, D9, D10, D11 · LLD B3–B5
- **Depends on:** 1.5
- **Creates:** agent loop, prompts, `POST /api/chat` SSE, chart builder, SQLite models/Alembic, pricing table, grounding detector (record only)
- **Acceptance:** `curl` a question sees `tool_call`, `text_delta`, `chart` (when requested), `done`; trace row written with tokens/cost
- **Docs:** prompt version note in README if useful

### 1.7 Web chat UI

- **HLD / LLD:** D1, D10, D13, D19 · LLD B4 ChartSpec / SSE / theme
- **Depends on:** 1.6
- **Creates:** Next.js chat page, SSE client, tool chips, Recharts from `ChartSpec`, light/dark theme toggle (OS default + `localStorage` override), OpenAPI-generated types if pipeline ready
- **UI reference:** [`docs/mockups/mizaj-ui/`](mockups/mizaj-ui/) (`Main`, `ChatEmpty`, `Sidebar`, light/dark)
- **Acceptance:** "plot my steps by week" shows a correct chart against synthetic or real gold; theme toggle switches light/dark and survives reload; chart readable in both modes; layout matches mockups in spirit (not pixel-perfect required)
- **Docs:** README screenshots from synthetic only (D15) — include one light and one dark if practical

### 1.8 README v1

- **Depends on:** 1.7
- **Creates:** architecture diagram, run instructions, privacy pointer
- **Acceptance:** Fresh clone instructions work with `make synth` + `make dev` without credentials
- **Docs:** `docs/privacy.md` short draft

### Phase 1 exit criteria

- Ten hand-written questions answered correctly (synthetic acceptable if OAuth slipped; real data when 1.4 done)
- Cost per request logged
- Nothing under personal `data/` tracked by git

---

## Phase 2 — Evals foundation

### 2.1 Scenario set + dedupe (v1 = 100)

- **HLD / LLD:** D14, D15, D18 · LLD C1
- **Depends on:** Phase 1 exit (agent runnable on synthetic)
- **Creates:** `evals/scenarios/scenarios.jsonl` (100), dedupe/validate script; optional `evals/generate.py` (API) — Claude web drafts are OK if JSONL validates
- **Acceptance:** 100 lines; v1 category counts match LLD; ~15-spot human review checklist done; no hard-coded 500 in tooling
- **Docs:** none

### 2.2 Eval runner + deterministic checks

- **HLD / LLD:** D11, D15, D18 · LLD C2
- **Depends on:** 2.1, 1.6
- **Creates:** `evals/run.py`, `eval_responses` storage, number/tool checks
- **Acceptance:** `make eval-run` stores **100** responses; checks populate booleans
- **Docs:** none

### 2.3 Annotation UI

- **HLD / LLD:** D15, D18, D19 · LLD C3, B4 theme
- **Depends on:** 2.2
- **Creates:** `/annotate` hotkey UI, annotations API, autosave, rounds; reuse shared theme shell from 1.7
- **Acceptance:** Keyboard flow labels one response end-to-end; closed tab loses nothing; light/dark matches chat
- **Docs:** short annotator README section

### 2.4 Human labeling sittings

- **Depends on:** 2.3
- **Creates:** round-1 annotations in SQLite (export JSONL under `evals/annotations/` if desired for backup — synthetic responses only in git)
- **Acceptance:** All **100** labeled on accuracy, scope_safety, chart, helpfulness (~45–70 minutes)
- **Docs:** none

---

## Phase 3 — Judge and metrics

### 3.1 Judge + splits + cache

- **HLD / LLD:** D6, D15, D18 · LLD C4
- **Depends on:** 2.2
- **Creates:** `evals/judge.py`, split module (30/70 for n=100; configurable), output cache, Pydantic judge schema
- **Acceptance:** Dev split (30) runs; invalid JSON retries once
- **Docs:** none

### 3.2 Metrics + report generator

- **HLD / LLD:** eval principles, D18 · LLD C5
- **Depends on:** 3.1, 2.4
- **Creates:** `evals/metrics.py`, unit tests on known kappa arrays, `make eval-report`
- **Acceptance:** Report MD+JSON written; prevalence and CIs present; report states n=100 and exploratory per-category caveat
- **Docs:** commit report; link in README

### 3.3 `/review` + judge iteration

- **LLD:** C6
- **Depends on:** 3.2
- **Creates:** disagreement review UI
- **Acceptance:** Filter by category/dimension; iterate judge prompt on **dev only**
- **Docs:** note final judge prompt version

### 3.4 Round-2 relabel + final test report

- **LLD:** C3 round 2, C5 · HLD D18
- **Depends on:** 3.3
- **Creates:** **~20**-item round-2 labels; final test-split (70) report
- **Acceptance:** Human self-kappa and test kappas in README results table with n and CI notes
- **Docs:** README results

### 3.5 CI smoke eval

- **Depends on:** 2.2, 3.1
- **Creates:** CI job: deterministic checks + ~20-item judged smoke (subset of the 100)
- **Acceptance:** PR CI green on synthetic fixtures
- **Docs:** none

---

## Phase 4 — Production hardening

Preserve original stretch hardening; still cite contracts.

| Task | Notes | Acceptance |
| --- | --- | --- |
| 4.1 Load test | k6 or Locust; publish p50/p95, TTFT, cost per 1k | Numbers in `docs/` or README |
| 4.2 Number-verifier guardrail | Promote D11 from record-only to block/flag | Mismatched numbers blocked or flagged in API |
| 4.3 Prompt caching | System prompt + tool defs; measure cost delta | Before/after cost note |
| 4.4 Daily `ingest sync` | cron or launchd; token-expiry alerting | Documented schedule; failure notifies operator |
| 4.5 Optional upgrades | `dbt-duckdb`, self-hosted Langfuse, webhook sync | ADR before adopting |

---

## Phase 5 — Stretch

Out of first three build phases (HLD D15, D18).

- Scale eval set from 100 → **500** (same schema; relabel; 150/350 split; round-2 ~50); treat kappas as more definitive
- Text-to-SQL variant vs typed tools on the same eval set
- SwiftUI client against the same API
- Public demo on free tier using **synthetic data only**
- Bronze/silver on S3-compatible storage; DuckDB `httpfs`

---

## Cost checklist (recompute from logs)

| Item | Model | Plan estimate |
| --- | --- | --- |
| Build/debug | Haiku 5.5 | &lt; $1 |
| 100 scenarios | Sonnet API or Claude web | ~$0.20 API, or $0 if web |
| Run 100 | Haiku 5.5 | ~$0.05–$0.15 |
| Judge 100 | Haiku 5.5 | ~$0.04 |
| Judge 100 | Sonnet 5.5 | ~$0.80 |
| Dev judge 30 | Sonnet 5.5 | ~$0.25 |
| Stretch: run+judge 500 | Haiku / Sonnet | see prior ~$0.25–$0.75 run; ~$4 Sonnet judge |
| Load test 1k | Haiku 5.5 | $0.50–$1.50 |

Use a Console API key with a spend limit. Cap retries at 2 and tool calls at 4.

---

## Definition of done (every task)

Tests pass, lint passes, acceptance met, README/docs updated when behavior changes, ADR written for any deviation from HLD/LLD.
