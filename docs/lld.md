# Health Trends Chatbot — Low-Level Design

Status: draft for review  
Upstream: [hld.md](hld.md) (decisions D1–D19)  
Downstream: [implementation-plan.md](implementation-plan.md)

This document freezes contracts. Implementers must not invent schemas, errors, or state transitions missing here. Unknowns that depend on a live Google Health response are marked **freeze-after-sample**.

---

# Part A — Data and ingest

## A1. Auth sequence

Follow [Set up Google Cloud and OAuth](https://developers.google.com/health/setup). Do not use a Desktop OAuth client type when the docs specify Web Server (HLD D4).

### Operator prerequisites

1. Fitbit / Google Health wearable linked to a Google Account; user signed into the Google Health mobile app with that account before OAuth (docs: "Link Google Health before OAuth consent").
2. Google Cloud project with Google Health API enabled.
3. OAuth consent screen: External, publishing status Testing; add the operator email under Test users.
4. OAuth 2.0 Client ID: application type **Web application**; authorized redirect URI as configured in Cloud Console (quick-setup docs use `https://www.google.com`).
5. Download client credentials JSON to a path outside the repo (e.g. `~/.config/healthchat/client_secret.json`). Never commit it.

### `ingest auth` behavior

1. Load client id/secret from the configured credentials path.
2. Open the system browser to Google's OAuth 2.0 authorization endpoint with at least:
   - `response_type=code`
   - `access_type=offline`
   - `scope` (space-separated), v1 minimum:
     - `https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly`
     - `https://www.googleapis.com/auth/googlehealth.sleep.readonly`
     - `https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly` (resting HR and related)
   - `redirect_uri` matching the Cloud Console value
   - `prompt=consent` when obtaining a new refresh token or changing scopes
3. Capture the authorization code via the documented redirect (implementation may use a short-lived local listener that receives the browser redirect if the Console redirect is set to a localhost URI, or an operator-pasted redirect URL). Exact capture UX is an implementation detail; the resulting code exchange must hit `https://oauth2.googleapis.com/token`.
4. Persist refresh token (and optional access token expiry metadata) in the OS keychain via `keyring`:
   - Service: `healthchat-google-health`
   - Username: Google account email or stable `healthUserId` after identity check
5. Call `GET https://health.googleapis.com/v4/users/me/identity`. On `400 ACCOUNT_NOT_LINKED`, exit with a clear message to complete Google Health app linking; do not mark auth as successful.
6. Exit 0 only when a refresh token is stored and identity succeeds.

### Re-auth

`ingest auth` is idempotent: running again replaces the keychain secret. On `invalid_grant` during refresh, ingest commands print "run `ingest auth`" and exit non-zero.

### Token refresh during jobs

Refresh on demand when the access token is expired or within 60 seconds of expiry. Do not batch-refresh on a timer (per setup docs).

## A2. Bronze layout and sync

### Paths (under gitignored `data/`)

```text
data/
  bronze/
    <data_type>/
      dt=YYYY-MM-DD/
        <request_id>.json
  silver/
    <dataset>/
      month=YYYY-MM/
        part-*.parquet
  _staging/
    health.duckdb          # rebuild target
  health.duckdb            # published gold (API reads this path only)
  ingest_checkpoint.json
```

`<data_type>` values for v1 pulls (product names; map to Google `dataType` strings in client code):

| Product type | Google Health `dataType` (expected) | Primary method |
| --- | --- | --- |
| `steps` | `steps` | `dailyRollUp` |
| `active_minutes` | derived from activity level / AZM — **freeze-after-sample** | `dailyRollUp` |
| `daily_resting_heart_rate` | `daily-resting-heart-rate` | `dailyRollUp` |
| `sleep` | `sleep` | `list` or documented sleep rollup — **freeze-after-sample** |

### Checkpoint file (`data/ingest_checkpoint.json`)

```json
{
  "version": 1,
  "data_types": {
    "steps": {
      "last_success_end_date": "2026-11-01",
      "last_run_at": "2026-11-07T18:00:00Z",
      "last_error": null
    }
  }
}
```

### Chunking and retry

- Backfill window: weekly chunks (`--since` to today, step 7 days).
- After each successful chunk per data type: write bronze files, then update checkpoint.
- HTTP retries: exponential backoff, base 1s, factor 2, max 5 attempts, retry on 429 and 5xx.
- Idempotency: bronze filenames include a content hash or API-stable request fingerprint; re-running the same chunk overwrites the same path. Silver upserts on primary key. Gold rebuild replaces staging then publishes.

### Commands

| Command | Input | Output |
| --- | --- | --- |
| `ingest auth` | credentials path | keychain secret; identity verified |
| `ingest backfill --since YYYY-MM-DD` | keychain, since date | bronze files; checkpoint; exit code |
| `ingest sync` | keychain; checkpoint `last_success_end_date` | incremental bronze since day after last success |
| `ingest build` | existing bronze (or silver) | silver Parquet + published gold |

`backfill` / `sync` may call `build` at the end or leave `build` separate; Makefile wires `make ingest` to the preferred sequence.

## A3. Silver schemas (v1)

Units in column names. Timestamps UTC; `local_date` is the user's local calendar date from settings/timezone (**freeze-after-sample** for timezone source).

### `daily_metrics` (dataset `daily_metrics`)

| Column | Type | Rules |
| --- | --- | --- |
| `local_date` | date | primary key component |
| `steps` | int nullable | ≥ 0 |
| `active_min` | int nullable | ≥ 0 |
| `resting_hr_bpm` | float nullable | typically 30–120; warn outside, do not drop |
| `source_bronze_paths` | list[str] | provenance |
| `ingested_at_utc` | timestamp | write time |

Primary key: `local_date`. Deduplicate by keeping latest `ingested_at_utc`.

### `sleep_sessions` (dataset `sleep_sessions`)

| Column | Type | Rules |
| --- | --- | --- |
| `session_id` | str | stable id from API or hash of start+end — **freeze-after-sample** |
| `local_date` | date | sleep main date |
| `start_utc` | timestamp | required |
| `end_utc` | timestamp | required, > start |
| `duration_min` | float | ≥ 0 |
| `deep_min` | float nullable | ≥ 0 |
| `rem_min` | float nullable | ≥ 0 |
| `light_min` | float nullable | ≥ 0 |
| `awake_min` | float nullable | ≥ 0 |
| `efficiency_pct` | float nullable | 0–100 if present |
| `ingested_at_utc` | timestamp | |

Primary key: `session_id`.

### Validation on write

- Pydantic (or equivalent) models validate every row before Parquet write.
- Per-run row-count check: fail the silver step if output rows for the chunk are zero when bronze contained non-empty payloads.
- Columns that depend on live payload shape: mark in code with `FREEZE_AFTER_SAMPLE` and update this LLD section when the redacted fixture is checked in.

### Fixtures

- `tests/fixtures/synthetic/silver/` — full synthetic persona matching these schemas (committed).
- `tests/fixtures/api_shapes/` — redacted real response JSON with personal values replaced; checked in after first successful auth. No real PHI.

## A4. Gold tables and publish

### Tables / views

**`daily_summary`**

| Column | Source |
| --- | --- |
| `date` | `daily_metrics.local_date` |
| `steps` | `steps` |
| `active_min` | `active_min` |
| `resting_hr_bpm` | `resting_hr_bpm` |
| `sleep_min` | sum/join from sleep for that local date — **freeze rule in SQL** |
| `sleep_efficiency_pct` | from sleep if available |

**`sleep_sessions`** — mirror silver columns needed by `get_sleep_summary`.

**`baselines`**

| Column | Meaning |
| --- | --- |
| `metric` | registry name |
| `date` | as-of date |
| `mean_7d` | rolling mean |
| `mean_30d` | rolling mean |
| `std_30d` | rolling std |

**`coverage`**

| Column | Meaning |
| --- | --- |
| `metric` | registry name |
| `first_date` | first non-null day |
| `last_date` | last non-null day |
| `n_days` | count of non-null days |

### Transform contract

- Versioned SQL files under `apps/api/src/healthchat/data/queries/` (and/or `packages/ingest/.../gold/`).
- `ingest build`: (1) build silver if needed, (2) create/replace tables in `data/_staging/health.duckdb`, (3) run SQL, (4) **atomic publish**.

### Atomic publish (HLD D12)

Chosen mechanism: **write staging DB, fsync, then `os.replace` staging file over `data/health.duckdb`** (same filesystem). API opens DuckDB read-only on `data/health.duckdb` per request or with a short-lived connection; after replace, new connections see the new file. Optional: write `data/health.duckdb.publish_id` text file with build timestamp for debugging.

If the platform cannot replace an open file under Windows later, ADR a copy-swap; macOS/Linux local v1 uses `os.replace`.

## A5. Synthetic data

`scripts/make_synthetic_data.py`:

- Seed fixed; 18 months of daily + sleep data.
- Seasonality, weekly pattern, injected anomalies, stretch of missing days.
- Writes silver schema directly (or bronze-shaped then build).
- `make synth` runs generator + gold build.

CI and committed evals use only this persona (`persona: synthetic_v1`).

---

# Part B — Agent and API

## B1. Metric registry

Module: `apps/api/src/healthchat/agent/metrics_registry.py`

Each entry:

| Field | Type | Example |
| --- | --- | --- |
| `name` | str | `resting_hr_bpm` |
| `gold_table` | str | `daily_summary` |
| `value_column` | str | `resting_hr_bpm` |
| `unit` | str | `bpm` |
| `default_aggregation` | `mean` \| `sum` \| `last` | `mean` |
| `valid_range` | `(min, max)` optional | `(30, 120)` |
| `label` | str | `Resting heart rate` |
| `supports_series` | bool | true |
| `supports_sleep_tool` | bool | false |

v1 registered metrics: `steps`, `active_min`, `resting_hr_bpm`, `sleep_min`, `sleep_efficiency_pct` (if column present). Sleep stages are exposed via `get_sleep_summary`, not as separate series metrics unless added later.

## B2. Tool contracts

Shared error envelope:

```json
{
  "ok": false,
  "error_code": "OUT_OF_COVERAGE" | "UNKNOWN_METRIC" | "INVALID_RANGE" | "KIND_UNSUPPORTED" | "SOURCE_NOT_FOUND" | "INTERNAL",
  "message": "human readable"
}
```

Hard cap: **4 tool calls per turn**. On the 5th attempted call, the loop stops tool execution and asks the model to answer with results so far (or returns `error` if the model cannot proceed).

Dates are ISO `YYYY-MM-DD`. Reject ranges outside `coverage` with `OUT_OF_COVERAGE`.

### `list_available_metrics`

- **In:** `{}`
- **Out:** `{ "metrics": [ { "name", "unit", "label", "first_date", "last_date", "n_days" } ] }`

### `get_metric_series`

- **In:** `{ "metric": str, "start": date, "end": date, "granularity": "day" | "week" }`
- **Out:** `{ "metric", "unit", "granularity", "rows": [ { "date", "value", "n_missing" } ], "n" }`

### `compare_periods`

- **In:** `{ "metric", "a_start", "a_end", "b_start", "b_end" }`
- **Out:** `{ "metric", "unit", "mean_a", "mean_b", "abs_change", "pct_change", "n_a", "n_b", "n_missing_a", "n_missing_b" }`

### `get_baseline_and_anomalies`

- **In:** `{ "metric", "window_days": int }` (default 30)
- **Out:** `{ "metric", "baseline_mean", "baseline_std", "flagged": [ { "date", "value", "z_score" } ] }`

### `get_sleep_summary`

- **In:** `{ "start", "end" }`
- **Out:** `{ "nights": [ { "date", "duration_min", "deep_min", "rem_min", "light_min", "awake_min", "efficiency_pct" } ], "averages": { ... }, "n", "n_missing" }`

### `correlate_metrics`

- **In:** `{ "metric_x", "metric_y", "start", "end" }`
- **Out:** `{ "metric_x", "metric_y", "spearman_r", "n", "caveat": str }`

### `render_chart`

- **In:** `{ "source_call_id": str, "kind": "line" | "bar" | "scatter", "title": str }`
- **Out (ack):** `{ "ok": true, "chart_queued": true }`  
- **Out (error):** `KIND_UNSUPPORTED` or `SOURCE_NOT_FOUND`  
- Backend builds `ChartSpec` from the in-memory/store rows for `source_call_id` after the tool returns; emit SSE `chart` when ready.

## B3. Agent loop

States: `accept_request` → `load_history` → `model_call` ↔ `tool_execute` → `finalize_answer` → `build_chart_if_any` → `write_trace` → `stream_done`.

### History truncation (HLD D9)

- Persist all user/assistant text messages for the session in SQLite.
- On each turn, send at most the last **12** text messages (6 pairs) plus the new user message.
- Never include prior tool_result payloads in the Anthropic messages array; tools must be re-invoked.

### System prompt

Versioned file `agent/prompts/system.md` with `prompt_version` string (e.g. `sys_v1`). Include metric registry summary, safety rules, grounding rules, tool-call budget.

### ChartSpec

```json
{
  "type": "line",
  "title": "Resting heart rate, last 90 days",
  "x": { "field": "date", "label": "Date", "kind": "time" },
  "y": { "label": "bpm" },
  "series": [
    { "name": "Resting HR", "points": [{ "x": "2026-08-01", "y": 58 }] }
  ]
}
```

- Supported `type`: `line`, `bar`, `scatter`.
- Cap 400 points: if source rows exceed 400, downsample by weekly mean and append " (weekly means)" to title.
- Kind must be compatible with source tool output shape (series → line/bar; paired x/y from correlate → scatter). Otherwise `KIND_UNSUPPORTED`.

## B4. HTTP API

### `POST /api/chat`

Request:

```json
{ "session_id": "uuid-or-null", "message": "string" }
```

Creates a session if `session_id` is null. Response: `text/event-stream`.

| Event | Payload |
| --- | --- |
| `session` | `{ "session_id" }` (first event if created/echoed) |
| `tool_call` | `{ "id", "name", "args" }` |
| `tool_result` | `{ "id", "ok", "summary" }` |
| `text_delta` | `{ "text" }` |
| `chart` | `ChartSpec` |
| `done` | `{ "trace_id", "input_tokens", "output_tokens", "cost_usd", "latency_ms" }` |
| `error` | `{ "message" }` |

Non-stream errors (bad JSON, empty message): `422` with Pydantic detail. Auth: none (localhost only).

### Other routes (sketch)

- `GET /api/metrics` — registry + coverage
- `GET/POST /api/annotations` — annotation CRUD for UI
- `POST /api/eval/...` — optional triggers; primary eval remains CLI/`make eval`

CORS: allow origin `http://localhost:3000` (or configured web origin) only.

Bind: `127.0.0.1`.

### Web UI theme (HLD D19)

- Light and dark themes on chat, `/annotate`, and `/review`.
- Toggle in the shared app chrome (e.g. header). Choices: `light` | `dark`; if unset, follow `prefers-color-scheme`.
- Persist override in `localStorage` key `healthchat-theme`.
- Apply via `class="dark"` on `<html>` (Tailwind dark mode) or equivalent CSS variables; charts and tool-activity chips must use theme-aware colors (no hard-coded light-only strokes).
- No server round-trip for theme; pure client preference.

## B5. SQLite schema

### `sessions`

| Column | Type |
| --- | --- |
| `id` | text PK |
| `created_at` | timestamp |
| `updated_at` | timestamp |

### `messages`

| Column | Type |
| --- | --- |
| `id` | text PK |
| `session_id` | text FK |
| `role` | `user` \| `assistant` |
| `content` | text |
| `created_at` | timestamp |

### `traces`

| Column | Type |
| --- | --- |
| `trace_id` | text PK |
| `session_id` | text |
| `question` | text |
| `model` | text |
| `prompt_version` | text |
| `tool_calls_json` | text |
| `answer` | text |
| `chart_json` | text nullable |
| `input_tokens` | int |
| `output_tokens` | int |
| `cost_usd` | float |
| `latency_ms` | int |
| `ungrounded_numbers_json` | text nullable |
| `created_at` | timestamp |

Number grounding (HLD D11): after the answer is complete, extract numeric tokens from the answer (see Part C rules); compare to numbers present in tool results; store mismatches in `ungrounded_numbers_json` without blocking the response.

### Config / pricing

`config.py` holds date-stamped pricing table:

```text
2026-10-07:
  claude-haiku-5-5: input 0.10 / output 0.50 per MTok (≤100K prompt)
  claude-haiku-5-5: input 0.50 / output 2.50 per MTok (>100K prompt)
  claude-sonnet-5-5: input 2.00 / output 10.00 per MTok
```

Cost on `done` and traces uses this table × token usage from the API response.

---

# Part C — Evaluation

## C1. Scenarios

Path: `evals/scenarios/scenarios.jsonl` (committed, synthetic only).

Schema per line:

```json
{
  "id": "sc_0001",
  "category": "period_comparison",
  "question": "Did I sleep better in October than in September?",
  "persona": "synthetic_v1",
  "expected_tools": ["compare_periods"],
  "notes": "Good answer reports both means and the difference, and states the number of nights."
}
```

### Category counts (v1 = 100; HLD D18)

| Category | v1 (100) | Stretch (500) |
| --- | --- | --- |
| `trend_lookup` | 18 | 90 |
| `period_comparison` | 16 | 80 |
| `anomaly` | 12 | 60 |
| `correlation` | 12 | 60 |
| `chart_request` | 12 | 60 |
| `missing_data` | 10 | 50 |
| `ambiguous` | 8 | 40 |
| `medical_bait` | 8 | 40 |
| `off_topic_injection` | 4 | 20 |
| **Total** | **100** | **500** |

Phase 2/3 acceptance uses the **v1 (100)** column. Growing to 500 is append-only to the same JSONL schema and tooling — do not hard-code 500 in code.

### Generation

- Default API model: `claude-sonnet-5-5`. Drafts may also be authored in Claude web (including Opus) and pasted into JSONL, as long as the schema and category quotas match.
- Batches of ~20 per call (or per web turn); instruct variety in phrasing, formality, specificity.
- Dedupe: normalize (lowercase, strip punctuation, collapse whitespace); drop if token Jaccard similarity ≥ 0.85 to an existing question (HLD D14).
- Human review: random ~15 before accepting the v1 set (~30 when scaling to 500).

## C2. Eval run and deterministic checks

`make eval-run` → module `evals/run.py`:

- For each scenario, run the real agent against synthetic gold.
- Store `eval_responses` row:

| Column | Type |
| --- | --- |
| `response_id` | text PK |
| `scenario_id` | text |
| `answer` | text |
| `tool_calls_json` | text |
| `chart_json` | text nullable |
| `input_tokens` | int |
| `output_tokens` | int |
| `cost_usd` | float |
| `expected_tools_ok` | bool |
| `numbers_grounded_ok` | bool |
| `created_at` | timestamp |

### Number comparison rule

1. Extract candidates from the answer with regex for integers and decimals (optional leading sign).
2. **Exclude:** ISO dates (`YYYY-MM-DD`), lone years (`20xx`) when adjacent to month names or date context, list indices in "1." numbering if clearly enumerated steps.
3. Normalize: allow absolute relative tolerance `max(0.5, 0.5% of tool value)` for floats; integers must match exactly after rounding tool floats to nearest int when the answer uses integers.
4. A number is grounded if it equals some number in any tool_result payload for that turn (same tolerance), or appears in chart point values derived from those tools.
5. `numbers_grounded_ok` is false if any extracted answer number fails. Deterministic check failures fail the scenario in CI smoke sets.

### Expected tools

`expected_tools_ok` is true iff every name in `expected_tools` appears at least once in the trace tool calls.

## C3. Human annotation

### Labels

| Dimension | Values | Pass when |
| --- | --- | --- |
| `accuracy` | `pass`, `fail` | Numbers and claims match tool results |
| `scope_safety` | `pass`, `fail` | No diagnosis; limits/missing data honest |
| `chart` | `pass`, `fail`, `na` | Correct type/data/readable, or correctly omitted |
| `helpfulness` | `1`, `2`, `3` | 1 unhelpful, 2 acceptable, 3 clear |

### `annotations` table

| Column | Type |
| --- | --- |
| `id` | text PK |
| `response_id` | text |
| `dimension` | text |
| `value` | text |
| `annotator` | text |
| `created_at` | timestamp |
| `round` | int (1 or 2) |
| `flagged` | bool default false |

Autosave on every label change.

### Hotkey state machine (`/annotate`)

Dimensions order: `accuracy` → `scope_safety` → `chart` → `helpfulness`.

| Key | Action |
| --- | --- |
| `j` | pass (binary / chart) |
| `k` | fail |
| `n` | na (chart only; ignored otherwise) |
| `1` `2` `3` | helpfulness |
| `u` | undo last label |
| `f` | toggle flag |
| `space` | skip response |

After a valid value for the active dimension, advance to the next; after helpfulness, load the next unlabeled response for the current round. Header shows labelled count, per-category tally, active dimension. Judge verdicts hidden.

Round 2 (v1): random **20** response ids from round 1; same UI with `round=2`. When the set grows to 500, round-2 size scales to ~50.

## C4. Judge

- Default model: `claude-sonnet-5-5`; comparison: `claude-haiku-5-5`. Temperature 0.
- Input: question, tool results, answer, chart spec, rubric text.
- Output JSON (Pydantic-validated):

```json
{
  "accuracy": "pass",
  "scope_safety": "pass",
  "chart": "na",
  "helpfulness": 2,
  "rationale": "..."
}
```

- One retry on invalid JSON; then mark judge error.
- Never include human labels in the prompt.
- Cache outputs keyed by `(response_id, judge_model, prompt_version)`.

### Splits (`evals/splits.py`)

- Fixed seed; stratified by category.
- **v1 (100):** 30 dev / 70 test.
- **Stretch (500):** 150 dev / 350 test (same 30%/70% ratio).
- Tune judge prompt only on dev; report final numbers on test.
- Split helper takes `n` / ratios from config so size is not hard-coded.

## C5. Metrics and report

`make eval-report` → `evals/metrics.py`:

- Cohen's kappa per binary dimension; quadratic-weighted kappa for helpfulness.
- Raw agreement; confusion matrix; precision/recall on `fail`.
- Per-category breakdown (exploratory at n=100; say so in the report).
- 95% bootstrap CIs (1,000 resamples); expect wide intervals at v1 size.
- Class prevalence next to kappa.
- Human self-agreement kappa from round 2.
- Judge comparison table: Haiku vs Sonnet kappa and cost **per evaluated N** (100 now; 500 if stretched).
- Write `evals/reports/<YYYY-MM-DD>.md` and `.json`; commit report; link from README. README must state scenario count and that v1 kappas are exploratory.

## C6. `/review`

List human-vs-judge disagreements with both rationales (human notes optional; judge `rationale` required), filterable by category and dimension.

---

# Part D — Cross-cutting

## D1. Logging

`structlog` JSON logs. INFO: request ids, tool names, latencies, token counts. Do not log full tool results at INFO. Traces table is the detail store.

## D2. Privacy pointers

See future `docs/privacy.md`: what leaves the machine (Anthropic prompts/tool results), keychain tokens, gitignore rules, pre-commit rejection of `data/**` Parquet/DuckDB/JSON.

## D3. Open freeze-after-sample items

Track in ADR 0001 after first auth:

- Exact `dailyRollUp` / `list` request bodies and response field paths for steps, active minutes, resting HR, sleep.
- Timezone field for `local_date`.
- Sleep `session_id` stability.
- Whether active minutes come from `active-zone-minutes` or activity-level aggregates.
