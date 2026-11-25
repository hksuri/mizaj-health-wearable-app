# Agent notes — Mizaj

1. Read [PLAN.md](PLAN.md), then [docs/hld.md](docs/hld.md), [docs/lld.md](docs/lld.md), [docs/implementation-plan.md](docs/implementation-plan.md).
2. Product name is **Mizaj** (HLD D20). UI mockups: [docs/mockups/mizaj-ui/](docs/mockups/mizaj-ui/).
3. Official Google Health / Claude docs win over this repo when they disagree — write an ADR.
4. Do not commit anything under `data/` (personal health data). Use synthetic fixtures in tests.
5. No LangChain, vector DB, Kafka, Kubernetes, or hosted observability without an ADR and human approval.
6. Prefer small PRs per implementation-plan task; keep tests and lint green.
