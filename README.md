# WEAVE

Engineering knowledge with source-backed answers and an interactive FalkorDB graph. Includes Ask Brain, Knowledge Health, Service Onboarding, suggested followups, decision timelines, entity inspection/expansion, filters, evidence focus and connection finding.

## Prerequisites and startup

Use Python 3.12, uv 0.13.1, Node 24, npm and Docker Desktop. PowerShell examples use `npm.cmd` to avoid execution-policy problems with `npm.ps1`. Install uv with `python -m pip install uv` if necessary.

For a fresh checkout, from `D:\WEAVE`:

```powershell
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env
cd backend
python -m uv sync --frozen
cd ..\frontend
npm.cmd ci
cd ..
docker compose up -d falkordb
.\backend\.venv\Scripts\python.exe scripts/validate_demo.py
.\backend\.venv\Scripts\python.exe scripts/seed_demo.py
```

Set `FALKORDB_GRAPH_NAME` in `.env` to the local graph you intend to seed. A's seed uses the idempotent two-phase writer; all 19 frozen entities and 21 edges are supplied. Intentional gaps remain: unowned Data Pipeline and ADR-002 without rationale. Never run the destructive reset script against a shared graph; it was not used for verification.

Start the API and frontend in separate terminals:

```powershell
cd D:\WEAVE\backend
.\.venv\Scripts\python.exe -m weave_brain.api
```

```powershell
cd D:\WEAVE\frontend
npm.cmd run dev
```

Open `http://localhost:5173`. API docs: `http://localhost:8000/docs`. The module reads `HOST`/`PORT`. Reload alternative from `backend/`: `python -m uv run uvicorn weave_brain.api.main:app --host 127.0.0.1 --port 8000 --reload`.

This workspace already has an ignored `.env` selecting the newly created, seeded local verification graph. Existing settings were not overwritten. The import package is `weave_brain`; the historical distribution name remains `backend` with explicit build-module configuration. The wheel and Docker image were verified.

## Configuration and answer modes

The canonical HTTP prefix is `/api`. Root `.env` and optional `backend/.env` load with process variables taking precedence. `ALLOWED_ORIGINS` accepts comma-separated HTTP origins or a JSON array; use the exact browser origin. `VITE_API_BASE_URL` is the backend origin without `/api`, compiled into the public frontend. DB and LLM settings stay backend-only.

- `CHAT_MODE=retrieval` (default): deterministic named graph tools, grounded source excerpts and followups; no LLM key required. Answers disclose this mode.
- `CHAT_MODE=agent`: bounded tool-calling orchestrator. Set `LLM_PROVIDER` to `openai`, `gemini` or `anthropic`, an available tool-capable `LLM_MODEL`, and its `LLM_API_KEY`. Missing credentials or provider runtime failures safely fall back to grounded deterministic graph synthesis with visible response notices; ungrounded citations are caught and safe fallbacks applied without exposing secrets.
- `DEVELOPMENT_FIXTURES=true`: explicitly offline synthetic catalog. Answers/reports label it; `/api/health` stays 503 and `/api/live` stays 200. Normal live mode requires actual graph retrieval.

FalkorDB configuration includes host, port, graph name, optional username/password, TLS (`FALKORDB_SSL=true`, certificate/hostname verification enabled) and timeouts. Agent calls have time/tool/output limits. No generated Cypher or arbitrary execution is available. No conversation memory is claimed; browser conversation remains usable across navigation, and late responses cannot replace another page's graph.

No model credentials are configured here. All three provider protocols and failure/grounding behavior were verified with mock HTTP transports; successful paid-provider requests remain unverified.

## Try the product

- Who owns the authentication service?
- Why do authentication tokens expire?
- What breaks if the authentication service goes down?
- Who are the authentication experts?
- What is the change impact of authentication?
- What is the knowledge health score?
- Onboard me to the authentication service.
- Find a path between `person:priya-sharma` and `service:authentication-api`.

Click a node for properties, canonical/source IDs, relationships, safe source links, freshness and a service decision timeline. Double-click to fetch/merge a depth-one neighborhood. Filter types, fit/zoom, toggle the legend and focus evidence. Right-click to start a connection, then select the target; Ctrl/Cmd-click also starts a connection. New answers replace the graph; expansions merge by ID. Missing endpoints and truncated results produce visible warnings rather than invented entities.

Knowledge Health shows four metrics, actual gaps and graph context. Onboarding includes accepted non-superseded decisions, experts, dependent-service risks, open incidents, tickets and a timeline. Direct `/health` and `/onboarding?service_id=service:data-pipeline` reloads work. Missing code/test records are never invented for change-impact answers.

## API and architecture

A's JSON/Markdown/Python ingestion emits `SourceArtifact`; B's writer/query/mapper owns Cypher; typed services and a read-only agent expose FastAPI; React renders returned `GraphView`. Traversals are at most three hops, views at most 100 nodes, and bounded graph retrieval detects omitted rows. Arrows retain stored direction: Team → OWNS → Service; dependents point toward their dependency.

Routes include liveness/readiness, chat, service overview/blast radius/decisions, neighborhood, shortest path, search/details, `/api/health-score` and `/api/reports/{health-score,knowledge-gaps,onboarding}`. Onboarding accepts a service path parameter or query parameter. See [interface contract](docs/interface-contract.md) and [graph schema](docs/graph-schema.md).

## Verification

```powershell
cd D:\WEAVE\backend
python -m uv run ruff check
python -m uv run ruff format --check .
python -m uv run pytest tests/unit/ -v
$env:FALKORDB_AVAILABLE="1"
$env:FALKORDB_HOST="127.0.0.1"
$env:FALKORDB_PORT="6379"
$env:FALKORDB_GRAPH_NAME="weave_test_local"
python -m uv run pytest tests/ -v
cd ..\frontend
npm.cmd ci
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd audit
npx.cmd playwright install chromium
npm.cmd run test:browser
# Point at an already seeded development graph for the live browser test:
$env:WEAVE_BROWSER_LIVE="1"
# Load the seeded graph's connection from the root .env instead of test overrides:
Remove-Item Env:FALKORDB_HOST, Env:FALKORDB_PORT, Env:FALKORDB_GRAPH_NAME -ErrorAction SilentlyContinue
npm.cmd run test:browser
```

Browser checks need free ports 5173 and 8010. Default tests use labeled fixtures; live browser tests use actual FalkorDB. Backend integration tests create/delete isolated temporary graphs. CI runs frozen installs, full lint/format, live tests with FalkorDB, frontend tests/build and fixture browser checks. Nothing was pushed, so remote CI was not triggered.

See the [full-scope audit](docs/full-scope-audit.md) and its exact command/output record. The earlier Dev C audit is historical and superseded. Tests retain one upstream Starlette/httpx deprecation warning.

## Deployment and disclosure

Vercel SPA configuration, a non-root Python Docker image, Render blueprint and Railway configuration are prepared. Host/port handling and live container readiness/chat were tested locally. Follow [deployment steps](docs/dev-c/deployment.md) after supplying hosting accounts, approved public origins, cloud DB credentials and optional provider credentials. No public URL, external deployment, push or merge was performed.

Codex assisted implementation and verification. Demo records are synthetic. Retrieval mode is deterministic; agent mode uses a configured LLM with read-only tools and retrieved evidence. Citation checks cannot prove every natural-language claim. Paid-provider and cloud/public-browser verification still require credentials and deployment. The supplied PDF is ignored and must never be committed.
