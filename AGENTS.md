# WEAVE Brain Engineering Rules

## 1. Product
Graph-powered engineering company knowledge assistant.
Track 03: Company Brain — Graph Hacks 2026.
Demo: ask a question, traverse FalkorDB, get an evidence-backed answer + dynamic graph.

## 2. File Ownership Table (4 Developers)

| Developer | Owns these folders (may freely edit) | Never edits these (without group approval) |
| :--- | :--- | :--- |
| **Dev A** | `backend/src/*/ingestion/`, `data/demo/`, `scripts/`, `backend/tests/unit/test_ingestion*.py` | `graph/`, `api/`, `agent/`, `frontend/`, `domain/models.py` |
| **Dev B** | `backend/src/*/graph/`, `docs/graph-schema.md`, `backend/tests/integration/`, `docker-compose.yml` | `ingestion/`, `api/`, `agent/`, `frontend/`, `domain/models.py` |
| **Dev C** | `backend/src/*/api/` (except `reports.py`), `backend/src/*/services/`, `backend/src/*/core/`, `frontend/` (except D's files), `.github/workflows/` | `graph/`, `ingestion/`, `agent/`, `domain/models.py` |
| **Dev D** | `backend/src/*/agent/`, `backend/src/*/api/routes/reports.py`, `frontend/src/pages/HealthPage.tsx`, `frontend/src/components/chat/SuggestedFollowups.tsx`, `frontend/src/components/entities/DecisionTimeline.tsx`, `docs/evaluation.md` | `graph/`, `ingestion/`, `api/routes/chat.py`, `domain/models.py` |

### Shared Files (Require Group Agreement Before Any Change)
- `backend/src/*/domain/models.py` — Shared Pydantic data models
- `frontend/src/types/api.ts` — Shared TypeScript interfaces
- `docs/graph-schema.md` & `docs/api-contracts.md` — Graph & API contracts
- `docker-compose.yml` — Database setup (Dev B is canonical owner)
- `backend/pyproject.toml` / `uv.lock` — Python dependency list
- `AGENTS.md` — Project rules

## 3. Canonical ID Format & Frozen Demo Entity IDs
Formula: `type:slug` (lowercase with hyphens, no spaces, no capitals; forward slashes for file paths).

### Official Demo Entity IDs (Use these exact strings everywhere)
- `service:authentication-api`
- `service:user-profile-api`
- `service:notification-service`
- `service:data-pipeline`
- `team:platform-engineering`
- `team:backend-core`
- `team:data-infra`
- `person:priya-sharma`
- `person:james-chen`
- `person:aisha-kowalski`
- `person:dev-four`
- `project:auth-modernization`
- `decision:adr-001`
- `decision:adr-002`
- `decision:adr-003`
- `incident:inc-007`
- `ticket:eng-042`
- `repository:acme/auth-api`
- `document:auth-runbook`

## 4. Graph Edge Directions (Critical for Correctness)
- `(:Team)-[:OWNS]->(:Service)` — Team points to what it owns
- `(:Person)-[:MEMBER_OF]->(:Team)` — Person points to their team
- `(:Service)-[:DEPENDS_ON]->(:Service)` — Service A points to Service B that it needs (To find what breaks if B goes down: match arrows pointing INTO B: `<-[:DEPENDS_ON*1..3]-`)
- `(:Service)-[:IMPLEMENTED_IN]->(:Repository)` — Service points to its repository
- `(:Repository)-[:CONTAINS]->(:File)` — Repository points to file
- `(:File)-[:IMPORTS]->(:File)` — File A points to File B that it imports (To find what depends on File B: match arrows pointing INTO B: `<-[:IMPORTS]-`)
- `(:Decision)-[:DECIDES_FOR]->(:Service)` — Decision points to the service it governs
- `(:Decision)-[:MOTIVATED_BY]->(:Incident)` — Decision points to the incident that caused it
- `(:Decision)-[:SUPERSEDES]->(:Decision)` — Newer decision points to older decision
- `(:Document)-[:DOCUMENTS]->(:Service)` — Document points to service
- `(:Incident)-[:AFFECTS]->(:Service)` & `(:Ticket)-[:AFFECTS]->(:Service)`
- `(:Person)-[:WORKED_ON {role, period}]->(:Project)` & `(:Project)-[:USES {since}]->(:Service)`

## 5. Architecture & Security Rules
- `domain/models.py` is the contract. Never pass raw dicts across module boundaries.
- All Cypher lives in `graph/queries.py`, `graph/writer.py`, and `graph/schema.py`. Parameterized queries (`$param`) only. No LLM-generated Cypher.
- Ingestion produces `SourceArtifact`. It never calls Cypher directly.
- API and agent call named service/query functions. Never raw queries.
- Frontend renders `GraphView` returned by the backend. Never hard-codes graph structure or connects to FalkorDB directly.
- Bound graph traversal depth: max 3. Bound result size: max 100 nodes.
- `ast.parse()` always in `try/except SyntaxError`.
- No secrets in committed code.

## 6. Antigravity Work Style
1. Read `AGENTS.md` and `docs/graph-schema.md` first.
2. State files that will change (must be in your assigned scope).
3. Propose plan + acceptance criterion. Wait for approval on nontrivial changes.
4. Run checks: `cd backend && uv run ruff check && uv run pytest tests/unit/ -v`
5. Report exact commands and exact output. Never claim a test passed without running it.
