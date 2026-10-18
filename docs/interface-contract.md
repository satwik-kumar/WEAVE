# WEAVE — Cross-Developer Interface Contract

**Document Version:** 1.0.0  
**Status:** Canonical Interface Specification & Integration Baseline  
**Target Systems:** FalkorDB 4.4.0, FastAPI (Python 3.12), React (Vite / TypeScript 5)  
**Authoritative Package Root:** `backend/src/weave_brain/`  

---

## 1. System Architecture & Component Ownership

WEAVE is a graph-powered company knowledge brain designed to give engineering organizations deep contextual answers, dependency analysis, incident lineage, and knowledge-health metrics backed by FalkorDB.

```
       +-------------------------------------------------------------+
       |                       Frontend (UI)                         |
       | React / TypeScript / Vite / Cytoscape or React Flow         |
       | Types: `frontend/src/types/api.ts` (Shared Contract)        |
       +------------------------------+------------------------------+
                                      | HTTP REST / Streaming SSE
                                      v
       +-------------------------------------------------------------+
       |                  Developer C: API Layer                     |
       | FastAPI Routes (`api/routes/`), Orchestration Services      |
       +--------------+-------------------------------+--------------+
                      |                               |
                      | Calls Agent                   | Calls Queries
                      v                               v
+-------------------------------+   +--------------------------------+
|  Developer D: Agent & Health  |   | Developer B: FalkorDB Engine   |
| Tool Calling (`agent/tools.py`)|   | Client (`graph/client.py`)      |
| Evidence (`models.py`)        |-->| Schema (`graph/schema.py`)     |
| Reports (`routes/reports.py`) |   | Writer (`graph/writer.py`)     |
+-------------------------------+   | Queries (`graph/queries.py`)   |
                                    | Mapper (`graph/mapper.py`)     |
                                    | Stubs (`graph/fixtures.py`)    |
                                    +----------------+---------------+
                                                     ^
                                                     | upsert_many(artifacts)
                                    +----------------+---------------+
                                    | Developer A: Ingestion Pipeline|
                                    | JSON / MD Parsers (`ingestion/`)|
                                    | Demo Data (`data/demo/`)       |
                                    +--------------------------------+
```

### 1.1 Team Ownership Matrix

| Developer | Primary Component Scope | Owned Directories & Files | Contractual Boundaries |
| :--- | :--- | :--- | :--- |
| **Dev A** | Ingestion & Demo Data | `backend/src/weave_brain/ingestion/`<br>`data/demo/`<br>`scripts/`<br>`backend/tests/unit/test_ingestion*.py` | Produces `SourceArtifact` objects. Calls `writer.upsert_many()`. **Never** calls raw Cypher. |
| **Dev B** | FalkorDB Engine & Retrieval | `backend/src/weave_brain/graph/`<br>`docs/graph-schema.md`<br>`backend/tests/integration/`<br>`docker-compose.yml` | Owns database connection, indexes, upsert logic, Cypher queries, mapper, and stubs. |
| **Dev C** | Web API & Services & Frontend | `backend/src/weave_brain/api/` (except `reports.py`)<br>`backend/src/weave_brain/services/`<br>`backend/src/weave_brain/core/`<br>`frontend/src/` (except D's files) | Calls B's query & mapper functions. Implements REST endpoints. Renders `GraphView`. |
| **Dev D** | Agent, Tools & Health Dashboard | `backend/src/weave_brain/agent/`<br>`backend/src/weave_brain/api/routes/reports.py`<br>`frontend/src/pages/HealthPage.tsx`<br>`frontend/src/components/chat/SuggestedFollowups.tsx`<br>`frontend/src/components/entities/DecisionTimeline.tsx` | Implements LLM graph-query tools, grounding, and knowledge-health metrics using B's query layer. |

### 1.2 Shared Files (Require Group Consensus)
Any modification to the following files requires explicit approval across all active developers:
- `backend/src/weave_brain/domain/models.py` (Pydantic shared models)
- `frontend/src/types/api.ts` (TypeScript shared types)
- `docs/graph-schema.md` (Node labels, relationship directions, entity ID formulas)
- `docs/interface-contract.md` (This document)
- `docker-compose.yml` (FalkorDB database container definition)
- `backend/pyproject.toml` & `uv.lock` (Dependencies)
- `AGENTS.md` (Engineering rules)

---

## 2. Canonical Data Models & Identifiers

### 2.1 Canonical Entity ID Formula
All node identifiers in FalkorDB, API responses, and frontend state **must** follow the lowercase slug format:
$$\text{id} = \text{type}:\text{slug}$$

- Hyphen-separated lowercase alphanumeric characters (no spaces, no capitals, no underscores in slug).
- Path separators in files or repositories must use forward slashes (`/`).
- Whitelisted Entity Types (11 total):
  `person`, `team`, `service`, `repository`, `file`, `document`, `decision`, `ticket`, `incident`, `test`, `project`.

### 2.2 Frozen Demo Entity Identifiers
The following 19 IDs are officially frozen for demo validation and seed fixtures:
- **Services:** `service:authentication-api`, `service:user-profile-api`, `service:notification-service`, `service:data-pipeline` (unowned gap).
- **Teams:** `team:platform-engineering`, `team:backend-core`, `team:data-infra`.
- **People:** `person:priya-sharma`, `person:james-chen`, `person:aisha-kowalski`, `person:dev-four`.
- **Projects:** `project:auth-modernization`.
- **Decisions:** `decision:adr-001`, `decision:adr-002` (empty rationale gap), `decision:adr-003` (supersedes `adr-002`).
- **Incidents & Tickets:** `incident:inc-007` (P1, resolved), `ticket:eng-042` (in-progress).
- **Repositories & Documents:** `repository:acme/auth-api`, `document:auth-runbook`.

### 2.3 Canonical Graph Relationship Types & Direction Conventions
Every Cypher query, ingestion edge, and writer upsert **must** adhere strictly to the 14 whitelisted relationships and directions defined in `docs/graph-schema.md`:

| Relationship Type | Directed Cypher Pattern | Traversal Semantics |
| :--- | :--- | :--- |
| `OWNS` | `(:Team)-[:OWNS]->(:Service)` | Team owns the Service. |
| `MEMBER_OF` | `(:Person)-[:MEMBER_OF]->(:Team)` | Person belongs to Team. |
| `MAINTAINS` | `(:Person)-[:MAINTAINS]->(:Service)` | Person maintains Service. |
| `DEPENDS_ON` | `(:Service)-[:DEPENDS_ON]->(:Service)` | **Caller points to dependency.** (To find what breaks when $S$ fails: `MATCH (s:Service {id: $S})<-[:DEPENDS_ON*1..3]-(dependent:Service)`). |
| `IMPLEMENTED_IN` | `(:Service)-[:IMPLEMENTED_IN]->(:Repository)` | Service points to Git repository. |
| `CONTAINS` | `(:Repository)-[:CONTAINS]->(:File)` | Repository contains File. |
| `IMPORTS` | `(:File)-[:IMPORTS]->(:File)` | **File A points to File B that it imports.** (Impact query: `(caller)-[:IMPORTS]->(target)`). |
| `DECIDES_FOR` | `(:Decision)-[:DECIDES_FOR]->(:Service)` | Decision governs Service. |
| `MOTIVATED_BY` | `(:Decision)-[:MOTIVATED_BY]->(:Incident)` | Decision triggered by Incident. |
| `SUPERSEDES` | `(:Decision)-[:SUPERSEDES]->(:Decision)` | Newer Decision points to older Decision. |
| `DOCUMENTS` | `(:Document)-[:DOCUMENTS]->(:Service)` | Document documents Service. |
| `AFFECTS` | `(:Incident\|:Ticket)-[:AFFECTS]->(:Service)` | Incident or Ticket affects Service. |
| `WORKED_ON` | `(:Person)-[:WORKED_ON]->(:Project)` | Person worked on Project (`role`, `period`). |
| `USES` | `(:Project)-[:USES]->(:Service)` | Project touches Service (`since`). |

---

## 3. Developer A: Ingestion Pipeline Contract

Developer A parses raw files (JSON, Markdown, YAML) and seeds them into FalkorDB via Developer B's writer.

### 3.1 Contract: Ingestion Output Structure
Developer A's parsers must emit instances of `weave_brain.domain.models.SourceArtifact`.

```python
from datetime import datetime
from weave_brain.domain.models import SourceArtifact

artifact = SourceArtifact(
    source_id="repo-acme-auth-api",                  # ID in external source system
    source_type="git",                               # 'git', 'catalog', 'adr', 'jira', 'confluence'
    entity_type="service",                           # One of the 11 EntityType literals
    canonical_id="service:authentication-api",       # Stable canonical ID (type:slug)
    title="Authentication API",                      # Human-readable title
    properties={                                     # Arbitrary key-value metadata
        "status": "production",
        "language": "Python",
        "tech_stack": "FastAPI, FalkorDB"
    },
    relationships=[                                  # 2-tuples or 3-tuples (rel_type, target_canonical_id, [props])
        ("IMPLEMENTED_IN", "repository:acme/auth-api"),
        ("DEPENDS_ON", "service:user-profile-api", {"criticality": "high"})
    ],
    source_url="https://github.com/acme/auth-api",   # Optional
    content_hash="sha256:abc123...",                 # Optional (used for change detection)
    source_updated_at=datetime(2025, 2, 1, 12, 0, 0),# Optional
    ingested_at=datetime.now()                       # Auto-populated
)
```

### 3.2 Seeding Execution Contract
Developer A invokes B's batch writer:

```python
from weave_brain.graph.writer import upsert_many
from weave_brain.graph.client import get_graph

graph = get_graph()
report = upsert_many(artifacts, graph=graph, source_name="demo_seed")
# Returns: SyncReport(source="demo_seed", records_processed=N, nodes_created=X, nodes_updated=Y, edges_created=Z, errors=[], warnings=[])
```

- **Two-Phase Guarantee:** Phase 1 writes all nodes; Phase 2 writes all edges. Forward references in the batch are safely resolved.
- **Missing Edge Handling:** If an edge points to a node not in FalkorDB, B's writer skips the edge and logs a warning in `report.warnings`. **No phantom nodes are created.**
- **Reserved Keys:** Properties matching `id`, `canonical_id`, `title`, `source_id`, `source_type`, `ingested_at` cannot be overwritten via the `properties` dictionary.

---

## 4. Developer B: FalkorDB Engine & Retrieval Interface

### 4.1 FalkorDB Connection Client
**Module:** `weave_brain.graph.client`

```python
def get_client(
    host: str | None = None,
    port: int | None = None,
    password: str | None = None,
    username: str | None = None,
    ssl: bool | None = None,
) -> FalkorDB:
    """Create a FalkorDB driver client using FALKORDB_HOST and FALKORDB_PORT.
    Optionally accepts password, username, and ssl parameters (or reads FALKORDB_PASSWORD,
    FALKORDB_USERNAME, and FALKORDB_SSL).
    Raises: ConfigurationError if required environment variables are missing or port is non-integer.
    """

def get_graph(
    graph_name: str | None = None,
    host: str | None = None,
    port: int | None = None,
    password: str | None = None,
    username: str | None = None,
    ssl: bool | None = None,
) -> Any:
    """Select and return a FalkorDB Graph object using FALKORDB_GRAPH_NAME.
    Raises: ConfigurationError if FALKORDB_GRAPH_NAME is not set.
    """
```

### 4.2 Schema & Index Management
**Module:** `weave_brain.graph.schema`

```python
IDENTITY_PROPERTY: str = "id"
ENTITY_TYPE_TO_LABEL: dict[EntityType, str]  # 'service' -> 'Service', 'person' -> 'Person', etc.
WHITELISTED_LABELS: frozenset[str]

def get_label_for_entity_type(entity_type: EntityType | str) -> str:
    """Return PascalCase label or raise KeyError."""

def init_schema(graph: Any) -> list[str]:
    """Idempotently create range indexes on (n.id) for all 11 entity labels.
    Returns list of verified/created labels.
    """
```

### 4.3 Graph Writer
**Module:** `weave_brain.graph.writer`

```python
WHITELISTED_RELATIONSHIPS: frozenset[str]  # 14 frozen relationship strings

def upsert_node(artifact: SourceArtifact, graph: Any = None) -> bool:
    """Upsert node by canonical id. Returns True if created, False if updated."""

def upsert_relationship(
    source_id: str,
    rel_type: str,
    target_id: str,
    properties: dict[str, Any] | None = None,
    graph: Any = None
) -> tuple[bool, bool]:
    """Upsert directed edge. Returns (matched_endpoints: bool, created_edge: bool).
    Raises: ValueError if rel_type is not in WHITELISTED_RELATIONSHIPS.
    """

def upsert_many(artifacts: list[SourceArtifact], graph: Any = None, source_name: str = "seed") -> SyncReport:
    """Two-phase batch upsert. Resolves forward references, returns SyncReport."""

# Aliases
upsert_edge = upsert_relationship
write_artifacts = upsert_many
```

### 4.4 Graph Retrieval Queries
**Module:** `weave_brain.graph.queries`

All queries use parameterized Cypher (`$sid`, `$nid`, etc.), bounded traversals (max depth 3, limits 50), and return clean dictionaries.

```python
def get_service_overview(service_id: str, graph: Any = None) -> dict[str, Any] | None:
    """Returns overview: service node, owning team, repos, decisions, docs, dependents,
    synthesized evidence, and a graph dictionary. Returns None if service does not exist.
    """

def get_decisions_for_service(service_id: str, graph: Any = None) -> dict[str, Any]:
    """Returns decisions governing service_id including MOTIVATED_BY incidents and SUPERSEDES links."""

def get_blast_radius(service_id: str, max_depth: int = 3, graph: Any = None) -> dict[str, Any]:
    """Traverses incoming <-[:DEPENDS_ON*1..3]- to find services that fail if service_id fails."""

def find_experts(service_id: str, graph: Any = None) -> list[dict[str, Any]]:
    """Finds engineers connected via Person -> WORKED_ON -> Project -> USES -> Service."""

def get_neighborhood(node_id: str, depth: int = 2, graph: Any = None) -> dict[str, Any]:
    """Returns bounded graph neighborhood centered on node_id with highlighted center."""

def find_shortest_path(from_id: str, to_id: str, graph: Any = None) -> dict[str, Any]:
    """Finds shortest path up to 5 hops. Returns {path_found: bool, nodes: [], edges: [], highlighted_path_ids: []}."""

def get_service_dependents(service_id: str, graph: Any = None) -> list[dict[str, Any]]:
    """Returns direct dependents: (dep:Service)-[:DEPENDS_ON]->(s:Service)."""

def search_entities(query: str, graph: Any = None) -> list[dict[str, Any]]:
    """Case-insensitive substring search matching n.id or n.title."""

def get_knowledge_gaps(graph: Any = None) -> dict[str, Any]:
    """Returns unowned_services, decisions_missing_rationale, undocumented_services, total_gaps."""

def get_health_score(graph: Any = None) -> dict[str, Any]:
    """Computes overall health score (0-100) and 4 metrics: services_owned, decisions_rationale,
    incidents_resolved, services_documented, plus gap details.
    """
```

### 4.5 Result Mapper
**Module:** `weave_brain.graph.mapper`

```python
def to_graph_view(
    query_result: dict[str, Any],
    highlighted_paths: list[list[str]] | None = None,
    now: datetime | None = None
) -> GraphView:
    """Converts query dictionary to GraphView.
    - Computes node freshness (fresh <30d, aging 30-90d, stale >90d).
    - Detects SUPERSEDES edges and sets decision status to 'superseded'.
    - Formats canonical edge IDs: 'src::REL::tgt'.
    - Flags on_highlighted_path.
    """

def to_evidence_items(query_result: dict[str, Any]) -> list[EvidenceItem]:
    """Extracts or synthesizes EvidenceItem records from query dictionaries."""
```

### 4.6 Offline Fixtures (Zero-Database Stubs)
**Module:** `weave_brain.graph.fixtures`

For frontend and agent development without a live FalkorDB instance:
- `get_service_overview_stub(service_id="service:authentication-api") -> dict`
- `get_decisions_for_service_stub(service_id="service:authentication-api") -> dict`
- `get_blast_radius_stub(service_id="service:authentication-api") -> dict`
- `find_experts_stub(service_id="service:authentication-api") -> list[dict]`
- `get_neighborhood_stub(node_id="service:authentication-api", depth=2) -> dict`

---

## 5. Developer C: Web API & Application Services Contract

Developer C exposes REST endpoints consuming Developer B's query layer and returning Pydantic domain models.

### 5.1 Route Specifications

| Method | Endpoint | Handler Call | Response Model | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System readiness check | `{"status": "ok", "database": "connected"}` | 200, 503 |
| `POST` | `/api/chat` | Agent query or direct graph lookup | `ChatResponse` | 200, 400, 500 |
| `GET` | `/api/services/{service_id}` | `get_service_overview(service_id)` + `to_graph_view` | `{"service": ..., "graph": GraphView, "evidence": []}` | 200, 404 |
| `GET` | `/api/services/{service_id}/blast-radius` | `get_blast_radius(service_id)` + `to_graph_view` | `{"affected_services": ..., "graph": GraphView}` | 200, 404 |
| `GET` | `/api/graph/neighborhood/{node_id}` | `get_neighborhood(node_id)` + `to_graph_view` | `GraphView` | 200, 404 |
| `GET` | `/api/graph/shortest-path` | `find_shortest_path(from_id, to_id)` | `{"path_found": bool, "graph": GraphView}` | 200, 400 |
| `GET` | `/api/search` | `search_entities(q)` | `list[GraphNode]` | 200 |
| `GET` | `/api/health-score` | `get_health_score()` | `{"health_score": float, "metrics": ..., "gaps": ...}` | 200 |

### 5.2 Implementation Pattern for API Handlers
```python
from fastapi import APIRouter, HTTPException
from weave_brain.graph.queries import get_service_overview
from weave_brain.graph.mapper import to_graph_view, to_evidence_items

router = APIRouter(prefix="/api/services", tags=["services"])

@router.get("/{service_id}")
def get_service(service_id: str):
    data = get_service_overview(service_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    
    return {
        "service": data["service"],
        "team": data["team"],
        "repositories": data["repositories"],
        "decisions": data["decisions"],
        "dependents": data["dependents"],
        "evidence": to_evidence_items(data),
        "graph": to_graph_view(data)
    }
```

---

## 6. Developer D: Agent & Health Reports Contract

Developer D implements controlled graph tools, evidence-grounded synthesis, and reports.

### 6.1 Agent Graph Tools Integration
Developer D's agent tools **must not** emit custom Cypher queries. Instead, each tool wraps an existing query function from `weave_brain.graph.queries`:

1. **`tool_service_overview(service_id: str)`** -> Calls `get_service_overview(service_id)`.
2. **`tool_blast_radius(service_id: str)`** -> Calls `get_blast_radius(service_id, max_depth=3)`.
3. **`tool_find_experts(service_id: str)`** -> Calls `find_experts(service_id)`.
4. **`tool_service_decisions(service_id: str)`** -> Calls `get_decisions_for_service(service_id)`.
5. **`tool_find_connection(from_id: str, to_id: str)`** -> Calls `find_shortest_path(from_id, to_id)`.
6. **`tool_search_knowledge(query: str)`** -> Calls `search_entities(query)`.

### 6.2 Chat Response Construction Contract
Every query answered by the agent must populate `ChatResponse`:
- `answer`: Grounded markdown text citing evidence.
- `evidence`: List of `EvidenceItem` objects returned by `to_evidence_items(raw_data)`.
- `graph`: `GraphView` returned by `to_graph_view(raw_data, highlighted_paths=[...])`.
- `highlighted_paths`: List of node ID lists representing the causal or reasoning path.
- `suggested_followups`: List of context-aware follow-up question strings.

### 6.3 Onboarding Brief Contract
For `OnboardingBrief` (`GET /api/reports/onboarding/{service_id}`), Developer D aggregates:
- `service_id`, `service_title`: From `get_service_overview`.
- `key_decisions`: From `get_decisions_for_service` (filtered to accepted, non-superseded ADRs).
- `top_experts`: From `find_experts`.
- `change_risks`: Formulated from `get_blast_radius` (dependents at risk).
- `graph`: `GraphView` encompassing service, team, repos, and direct dependencies.

---

## 7. Frontend Integration Contract (`api.ts`)

The frontend imports interfaces from `frontend/src/types/api.ts`. These match backend Pydantic models 1:1:

| Backend Model (`domain/models.py`) | Frontend Type (`src/types/api.ts`) | Key Fields |
| :--- | :--- | :--- |
| `GraphNode` | `GraphNode` | `id`, `type`, `title`, `properties`, `on_highlighted_path`, `is_stale` |
| `GraphEdge` | `GraphEdge` | `id`, `source_id`, `target_id`, `relationship_type`, `label`, `properties` |
| `GraphView` | `GraphView` | `nodes`, `edges`, `root_node_ids`, `highlighted_path_ids`, `truncated`, `warning` |
| `EvidenceItem` | `EvidenceItem` | `source_id`, `title`, `source_type`, `excerpt`, `source_url`, `relationship_path` |
| `ChatRequest` | `ChatRequest` | `question`, `conversation_id` |
| `ChatResponse` | `ChatResponse` | `message_id`, `answer`, `evidence`, `graph`, `highlighted_paths`, `related_entities`, `suggested_followups`, `warnings`, `intent` |
| `OnboardingBrief` | `OnboardingBrief` | `service_id`, `service_title`, `overview`, `key_decisions`, `top_experts`, `change_risks`, `open_incidents`, `related_tickets`, `graph`, `warnings` |

---

## 8. Environment & Deployment Configuration

### 8.1 Required Environment Variables

```bash
# FalkorDB Database Configuration
FALKORDB_HOST=localhost          # Hostname of FalkorDB container or cluster
FALKORDB_PORT=6379               # Port number (must be integer)
FALKORDB_GRAPH_NAME=weave_brain  # Active graph namespace

# Web & CORS
ALLOWED_ORIGINS=http://localhost:5173

# LLM Agent Configuration (Developer D)
LLM_PROVIDER=gemini              # 'gemini', 'openai', or 'anthropic'
LLM_MODEL=gemini-1.5-pro
LLM_API_KEY=your_key_here
```

### 8.2 Database Container Specification (`docker-compose.yml`)
```yaml
services:
  falkordb:
    image: falkordb/falkordb:v4.4.0
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - falkordb_data:/data
    restart: unless-stopped

volumes:
  falkordb_data:
```

---

## 9. Verification & Safe Execution Workflows

1. **Run Unit Tests (Zero Network / Offline):**
   ```powershell
   cd backend
   uv run pytest tests/unit/ -v
   ```
2. **Run Full Suite including Live FalkorDB Integration Tests:**
   ```powershell
   $env:FALKORDB_AVAILABLE="1"
   $env:FALKORDB_HOST="localhost"
   $env:FALKORDB_PORT="6379"
   $env:FALKORDB_GRAPH_NAME="test_live_graph"
   uv run pytest tests/ -v
   ```
3. **Run Code Linter:**
   ```powershell
   uv run ruff check .
   ```
EOF
