# RepoCompass Brain — Engineering Rules & Operating System

## 1. Product Vision
Graph-powered engineering company knowledge assistant ("Company Brain").
Track 03: Company Brain — Graph Hacks 2026.
Core loop: Ask an engineering/organizational question -> traverse FalkorDB -> return an evidence-backed answer + dynamic interactive subgraph (@xyflow/react).

## 2. Four-Developer Module Ownership Matrix
Every developer/agent session MUST strictly stay within its assigned scope:

- **Developer A (Ingestion & Demo Data):**
  - Owns: `backend/src/repocompass_brain/ingestion/`, `data/demo/`, `scripts/` (`seed_demo.py`, `validate_demo.py`, `reset_demo.py`), `backend/tests/unit/test_ingestion*.py`
  - Others may: Read/run only, never edit without PR.

- **Developer B (FalkorDB & Graph Retrieval):**
  - Owns: `backend/src/repocompass_brain/graph/` (`client.py`, `schema.py`, `writer.py`, `queries.py`, `mapper.py`, `fixtures.py`), `backend/tests/integration/`, `docs/graph-schema.md`, `docker-compose.yml`
  - Others may: Read only; A and D may add integration test cases via PR.

- **Developer C (Core API, Services, Frontend & Deployment):**
  - Owns: `backend/src/repocompass_brain/main.py`, `backend/src/repocompass_brain/core/`, `backend/src/repocompass_brain/api/routes/health.py`, `backend/src/repocompass_brain/api/routes/chat.py`, `backend/src/repocompass_brain/services/`, `frontend/` (except D's explicit files), `.github/workflows/ci.yml`
  - Others may: D registers `reports.py` router in `main.py`, `/health` route in `App.tsx`/`Sidebar.tsx`, and renders `SuggestedFollowups` inside `BrainAnswer`.

- **Developer D (LLM Agent, Knowledge Health & Advanced Features):**
  - Owns: `backend/src/repocompass_brain/agent/`, `backend/src/repocompass_brain/api/routes/reports.py`, `frontend/src/pages/HealthPage.tsx`, `frontend/src/components/chat/SuggestedFollowups.tsx`, `frontend/src/components/entities/DecisionTimeline.tsx`, `docs/evaluation.md`
  - Others may: C calls `orchestrator.process_question()` from `chat_service.py`, never edits `agent/`.

### Shared Files (Require PR Review / Explicit Approval Before Editing)
- `backend/src/repocompass_brain/domain/models.py`
- `frontend/src/types/api.ts`
- `docs/api-contracts.md`
- `backend/pyproject.toml` and `uv.lock` (all run `uv sync` after merge)
- `docker-compose.yml` (B's branch is canonical)
- `AGENTS.md`
- `README.md` (C authors, all review)

## 3. Architecture & Contract Rules
1. `domain/models.py` (and `frontend/src/types/api.ts`) is the frozen contract. Never pass raw untyped dicts across module boundaries.
2. All Cypher lives exclusively in `graph/queries.py`, `graph/writer.py`, and `graph/schema.py`. Parameterized queries ONLY (`$param`). Never use f-strings for values or LLM-generated Cypher.
3. Ingestion produces `SourceArtifact` objects. It never calls Cypher directly; it passes artifacts to `graph/writer.py`.
4. API routes and the LLM agent call named service/query functions. Never expose or call raw Cypher from `api/` or `agent/`.
5. The graph does the retrieval; the LLM does the explanation. If `LLM_API_KEY` is unset or times out, fall back gracefully to deterministic routing and response synthesis so the app never crashes.
6. Frontend renders `GraphView` returned by the backend. Never hard-code graph structure or connect to FalkorDB directly from the frontend.
7. Bound graph traversal depth: max 3 hops. Bound result size: `LIMIT 50` (hard cap 100 nodes).

## 4. Graph Schema & Canonical ID Convention

### Stable ID Convention
Format: `<entity_type>:<slug>` (lowercase, hyphens, no spaces; forward slashes for file paths).
- `person:priya-sharma`
- `team:platform-engineering`
- `service:authentication-api`
- `project:auth-modernization`
- `repository:acme/auth-api`
- `file:acme/auth-api:src/auth/tokens.py`
- `document:auth-runbook`
- `decision:adr-001`
- `ticket:eng-042`
- `incident:inc-007`

### Node Labels & Properties
- Labels: `Person`, `Team`, `Service`, `Project`, `Repository`, `File`, `Document`, `Decision`, `Ticket`, `Incident`
- Every node MUST carry: `id` (canonical ID), `title`, `source_id`, `source_type`, `ingested_at` (ISO-8601 string).
- Preserve `artifact.ingested_at` when seeding so historical timestamps drive the Freshness/Staleness calculation (`<30d` fresh, `30-90d` aging, `>90d` stale).

### Canonical Relationships & Direction Rules
- `(:Person)-[:MEMBER_OF {source_id}]->(:Team)`
- `(:Team)-[:OWNS {source_id}]->(:Service)`               # Team points to Service it owns
- `(:Person)-[:MAINTAINS {source_id}]->(:Service)`
- `(:Person)-[:WORKED_ON {role, period}]->(:Project)`     # Person points to Project they worked on
- `(:Project)-[:USES {since}]->(:Service)`                # Project points to Service it uses
- `(:Service)-[:IMPLEMENTED_IN]->(:Repository)`
- `(:Service)-[:DEPENDS_ON]->(:Service)`                  # Dependent service points to upstream dependency
- `(:Repository)-[:CONTAINS]->(:File)`
- `(:File)-[:IMPORTS]->(:File)`                           # Source file points to the file it imports
- `(:Document)-[:DOCUMENTS]->(:Service)`
- `(:Decision)-[:DECIDES_FOR]->(:Service)`                # Decision points to Service it governs
- `(:Decision)-[:MOTIVATED_BY]->(:Incident)`              # Decision points to Incident that caused it
- `(:Decision)-[:SUPERSEDES]->(:Decision)`                # Newer decision points to older superseded decision
- `(:Ticket)-[:AFFECTS]->(:Service)`
- `(:Incident)-[:AFFECTS]->(:Service)`

## 5. Technical Implementation Guardrails
- **FalkorDB Python Client:** Use `from falkordb import FalkorDB`. Unpack `falkordb.Node` and `falkordb.Edge` objects into plain Python dicts/Pydantic models inside `graph/` before returning to callers. Serialize any `datetime` to `.isoformat()` before passing to Cypher `$props`.
- **React Flow v12:** Package is `@xyflow/react` (NOT legacy `reactflow`). Always include `import '@xyflow/react/dist/style.css';` and pass fallback node width/height (`200`x`72`) to `@dagrejs/dagre` layout calculations.
- **Python AST Parsing:** Always wrap `ast.parse()` in `try/except SyntaxError` and record `parse_error=str(e)` without crashing.

## 6. Antigravity Work Style
1. Read `AGENTS.md` and inspect existing files in your scope before proposing changes.
2. State exact files that will be created or modified (must be within your assigned scope).
3. Propose a brief plan and acceptance criteria. Wait for approval on nontrivial changes.
4. Run verification checks before finishing:
   - Backend: `cd backend && uv run ruff check && uv run pytest tests/unit/ -v`
   - Frontend: `cd frontend && npm run build`
5. Report exact commands run and exact terminal output. Never claim a test passed without running it.

## 7. Security Rules
- No Cypher string interpolation for values. Parameterized queries (`$param`) only.
- Never execute analyzed repository code.
- No secrets or API keys in committed code (only placeholders in `.env.example`).
- Never expose a raw arbitrary Cypher execution endpoint.
