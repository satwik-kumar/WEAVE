# Graph Schema & Canonical ID Contract (FROZEN)

## 1. Node Labels & Properties

| Label | What it represents | Required Properties | Optional Properties | Example ID |
| :--- | :--- | :--- | :--- | :--- |
| `Service` | A software service | `id`, `title` | `description`, `tech_stack`, `language`, `status` | `service:authentication-api` |
| `Team` | An engineering team | `id`, `title` | `description`, `slack_channel` | `team:platform-engineering` |
| `Person` | An engineer | `id`, `title`, `source_type` | `email`, `role`, `slug` | `person:priya-sharma` |
| `Project` | An engineering initiative | `id`, `title` | `description`, `status` | `project:auth-modernization` |
| `Decision` | An architecture decision (ADR) | `id`, `title`, `status` | `rationale`, `decision_date` | `decision:adr-001` |
| `Incident` | A production incident | `id`, `title`, `severity` | `status`, `summary`, `resolved_at` | `incident:inc-007` |
| `Ticket` | An engineering work item | `id`, `title`, `status` | `priority`, `summary` | `ticket:eng-042` |
| `Document` | A runbook or doc | `id`, `title` | `source_url`, `content_excerpt` | `document:auth-runbook` |
| `Repository` | A code repository | `id`, `title`, `url` | `language`, `default_branch` | `repository:acme/auth-api` |
| `File` | A source code file | `id`, `title`, `content_hash` | `is_test`, `parse_error` | `file:acme/auth-api:src/auth/tokens.py` |

*All nodes additionally carry:* `source_id`, `source_type`, `ingested_at` (ISO-8601 string), `aliases`.

---

## 2. Canonical Edge Types & Direction Rules

| Relationship | Direction | Meaning | Edge Properties |
| :--- | :--- | :--- | :--- |
| `OWNS` | `(:Team)-[:OWNS]->(:Service)` | Team points toward the Service it owns | `source_id` |
| `MEMBER_OF` | `(:Person)-[:MEMBER_OF]->(:Team)` | Person points toward their Team | `source_id` |
| `MAINTAINS` | `(:Person)-[:MAINTAINS]->(:Service)` | Person points toward Service they maintain | `source_id` |
| `DEPENDS_ON` | `(:Service)-[:DEPENDS_ON]->(:Service)` | **Dependent service points toward what it needs** | — |
| `IMPLEMENTED_IN` | `(:Service)-[:IMPLEMENTED_IN]->(:Repository)` | Service points toward its code Repo | — |
| `CONTAINS` | `(:Repository)-[:CONTAINS]->(:File)` | Repo points toward File | — |
| `IMPORTS` | `(:File)-[:IMPORTS]->(:File)` | **File A points toward File B that it imports** | — |
| `DECIDES_FOR` | `(:Decision)-[:DECIDES_FOR]->(:Service)` | Decision points toward Service it governs | — |
| `MOTIVATED_BY` | `(:Decision)-[:MOTIVATED_BY]->(:Incident)` | Decision points toward Incident that caused it | — |
| `SUPERSEDES` | `(:Decision)-[:SUPERSEDES]->(:Decision)` | Newer Decision points toward older Decision | — |
| `DOCUMENTS` | `(:Document)-[:DOCUMENTS]->(:Service)` | Document points toward Service it documents | — |
| `AFFECTS` | `(:Incident\|:Ticket)-[:AFFECTS]->(:Service)` | Incident or Ticket points toward affected Service | — |
| `WORKED_ON` | `(:Person)-[:WORKED_ON]->(:Project)` | Person points toward Project they worked on | `role`, `period` |
| `USES` | `(:Project)-[:USES]->(:Service)` | Project points toward Service it touches | `since` |

### CRITICAL DIRECTION RULE (DO NOT REVERSE):
1. **`(:Service A)-[:DEPENDS_ON]->(:Service B)`** means **A depends on B** (A points toward what it needs).
   - **Blast Radius Query ("What breaks if B goes down?"):** Look for arrows pointing **into** B:
     `MATCH path = (s:Service {id: $service_id})<-[:DEPENDS_ON*1..3]-(dependent:Service)`
2. **`(:File A)-[:IMPORTS]->(:File B)`** means **File A imports File B**.
   - **Impact Query ("Who imports File B?"):** Look for arrows pointing **into** B:
     `MATCH (caller:File)-[:IMPORTS]->(target:File {id: $file_id})`

---

## 3. Official Frozen Demo Entity IDs
Every JSON file, Cypher query, fixture, and test MUST use these exact strings:

### Services
- `service:authentication-api` (owned by `team:platform-engineering`)
- `service:user-profile-api` (owned by `team:backend-core`, `DEPENDS_ON` `service:authentication-api`)
- `service:notification-service` (owned by `team:platform-engineering`, `DEPENDS_ON` `service:authentication-api`)
- `service:data-pipeline` (NO owner — intentional gap for Knowledge Health check)

### Teams
- `team:platform-engineering`
- `team:backend-core`
- `team:data-infra`

### People
- `person:priya-sharma` (Lead, `team:platform-engineering`, `WORKED_ON` `project:auth-modernization`)
- `person:james-chen` (`team:platform-engineering`, `WORKED_ON` `project:auth-modernization`)
- `person:aisha-kowalski` (`team:backend-core`, `WORKED_ON` `project:profile-modernization`)
- `person:dev-four` (`team:data-infra`)

### Projects
- `project:auth-modernization` (`USES` `service:authentication-api`)

### Decisions
- `decision:adr-001` ("Token expiry 24h policy", `DECIDES_FOR` `service:authentication-api`, `MOTIVATED_BY` `incident:inc-007`)
- `decision:adr-002` ("Service mesh adoption", empty rationale — intentional gap, superseded by `decision:adr-003`)
- `decision:adr-003` ("Envoy proxy standard", `SUPERSEDES` `decision:adr-002`)

### Incidents & Tickets
- `incident:inc-007` ("Stolen long-lived token exploited", P1, `AFFECTS` `service:authentication-api`, resolved)
- `ticket:eng-042` ("Rotate legacy signing keys", `AFFECTS` `service:authentication-api`, in_progress)

### Repositories & Documents
- `repository:acme/auth-api` (`IMPLEMENTED_IN` target for `service:authentication-api`)
- `document:auth-runbook` (`DOCUMENTS` `service:authentication-api`)

---

## 4. Index & Schema Initialization (`schema.py`)

### Range Indexes on Identity Property
To guarantee $O(1)$ lookups and fast traversals across millions of nodes without table scans, FalkorDB creates schema range indexes on the `id` property for all 11 canonical node labels:

```cypher
CREATE INDEX FOR (n:Person) ON (n.id)
CREATE INDEX FOR (n:Team) ON (n.id)
CREATE INDEX FOR (n:Service) ON (n.id)
CREATE INDEX FOR (n:Repository) ON (n.id)
CREATE INDEX FOR (n:File) ON (n.id)
CREATE INDEX FOR (n:Document) ON (n.id)
CREATE INDEX FOR (n:Decision) ON (n.id)
CREATE INDEX FOR (n:Ticket) ON (n.id)
CREATE INDEX FOR (n:Incident) ON (n.id)
CREATE INDEX FOR (n:Test) ON (n.id)
CREATE INDEX FOR (n:Project) ON (n.id)
```

### Idempotent Discovery via `CALL db.indexes()`
`init_schema(graph)` first queries existing indexes using `CALL db.indexes()` to detect existing `(label, property)` index definitions. If an index already exists, `init_schema` skips execution. Furthermore, if FalkorDB returns an `already indexed` response, the initialization gracefully recovers and continues, making schema initialization strictly idempotent and safe across service restarts and worker threads.

---

## 5. Idempotent Two-Phase Write Strategy (`writer.py`)

### Phase 1: Node Upsert via Parameterized MERGE
Nodes are ingested from `SourceArtifact` models. To prevent duplicate nodes and race conditions, each node is merged on its canonical `id`:

```cypher
MERGE (n:<Label> {id: $id})
SET n += $props
RETURN n.id
```

- **Property Collision Defense**: Any incoming keys in `artifact.properties` that collide with reserved system keys (`id`, `canonical_id`, `title`, `source_id`, `source_type`, `ingested_at`, `source_url`, `content_hash`, `source_updated_at`) are automatically stripped.
- **Freshness Preservation**: `ingested_at` is preserved as an ISO-8601 UTC timestamp on every node for staleness and freshness calculations.
- **Type Serialization**: Datetimes are converted to ISO-8601 strings and nested dictionaries are serialized to JSON strings.

### Phase 2: Index-Optimized Relationship Upsert
Edges are created only after endpoint nodes exist. To maximize performance and leverage FalkorDB label indexes, `upsert_relationship` extracts the entity type prefix (e.g., `service:` -> `Service`, `team:` -> `Team`) to target indexed label patterns:

```cypher
MATCH (a:<SourceLabel> {id: $src_id}), (b:<TargetLabel> {id: $tgt_id})
MERGE (a)-[r:<RELATIONSHIP_TYPE>]->(b)
SET r += $props
RETURN type(r)
```

- **Phantom Node Prevention**: Because `MATCH` requires both endpoints to exist, no orphaned or untyped phantom nodes are ever created if a target artifact is missing.
- **Whitelist Enforcement**: The relationship type MUST be an exact match from `WHITELISTED_RELATIONSHIPS` (14 canonical types).

---

## 6. Complete Verified Cypher Query Reference (`queries.py`)

All queries use parameterized inputs (`$param`) with bounded result limits (`LIMIT 100`) and bounded traversal depths (max 3 hops).

### 1. Service Overview (`get_service_overview`)
Retrieves complete contextual topology for a service:
```cypher
-- 1. Service Node
MATCH (s:Service {id: $sid}) RETURN s

-- 2. Owning Team & Membership
MATCH (t:Team)-[r:OWNS]->(s:Service {id: $sid}) RETURN t, r

-- 3. Implementing Repositories
MATCH (s:Service {id: $sid})-[r:IMPLEMENTED_IN]->(repo:Repository) RETURN repo, r

-- 4. Architectural Decisions
MATCH (d:Decision)-[r:DECIDES_FOR]->(s:Service {id: $sid}) RETURN d, r

-- 5. Documentation
MATCH (doc:Document)-[r:DOCUMENTS]->(s:Service {id: $sid}) RETURN doc, r

-- 6. Upstream Dependencies (Services that this service needs)
MATCH (s:Service {id: $sid})-[r:DEPENDS_ON]->(target:Service) RETURN target, r

-- 7. Downstream Dependents (Services that depend on this service)
MATCH (dep:Service)-[r:DEPENDS_ON]->(s:Service {id: $sid}) RETURN dep, r
```

### 2. Decision Rationale & Lineage (`get_decisions_for_service`)
Inspects ADRs, motivating incidents, and supersession chains:
```cypher
MATCH (d:Decision)-[r:DECIDES_FOR]->(s:Service {id: $sid})
OPTIONAL MATCH (d)-[m:MOTIVATED_BY]->(inc:Incident)
OPTIONAL MATCH (newer:Decision)-[sup:SUPERSEDES]->(d)
OPTIONAL MATCH (d)-[sup_out:SUPERSEDES]->(older:Decision)
RETURN d, r, inc, m, newer, sup, older, sup_out
LIMIT 100
```

### 3. Blast Radius / Reverse Dependency Traversal (`get_blast_radius`)
Calculates cascading impact if a service goes down (reversing traversal arrow to find dependents pointing INTO the target service):
```cypher
-- Bounded depth between 1 and 3 hops
MATCH path = (s:Service {id: $sid})<-[:DEPENDS_ON*1..3]-(dep:Service)
RETURN path
LIMIT 100
```

### 4. Expert Finder (`find_experts`)
Discovers engineers who worked on initiatives/projects utilizing a service:
```cypher
MATCH (p:Person)-[w:WORKED_ON]->(proj:Project)-[:USES]->(s:Service {id: $sid})
OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)
RETURN p, w, proj, t
LIMIT 100
```

### 5. Bounded Graph Neighborhood (`get_neighborhood`)
Fetches local subgraph centered on any entity node with bounded traversal:
```cypher
MATCH path = (center {id: $nid})-[*1..2]-(neighbor)
RETURN path
LIMIT 100
```

### 6. Shortest Path (`find_shortest_path`)
Discovers the shortest connecting path between any two entities up to 5 hops:
```cypher
MATCH (a {id: $from_id}), (b {id: $to_id})
MATCH path = (a)-[*1..5]-(b)
RETURN path
ORDER BY length(path) ASC
LIMIT 1
```

### 7. Knowledge Gaps (`get_knowledge_gaps`)
Identifies structural gaps in organizational knowledge:
```cypher
-- Services without an owning Team
MATCH (s:Service) WHERE NOT ()-[:OWNS]->(s) RETURN s

-- Decisions missing rationale
MATCH (d:Decision) WHERE d.rationale IS NULL OR d.rationale = '' RETURN d

-- Services without documentation
MATCH (s:Service) WHERE NOT ()-[:DOCUMENTS]->(s) RETURN s
```

### 8. Knowledge Health Score Metrics (`get_health_score`)
Calculates the 4 tracked governance dimensions:
```cypher
-- Metric 1: Services with owner
MATCH (s:Service) RETURN count(s)
MATCH (:Team)-[:OWNS]->(s:Service) RETURN count(DISTINCT s)

-- Metric 2: Decisions with rationale
MATCH (d:Decision) RETURN count(d)
MATCH (d:Decision) WHERE d.rationale IS NOT NULL AND d.rationale <> '' RETURN count(d)

-- Metric 3: Incidents resolved
MATCH (inc:Incident) RETURN count(inc)
MATCH (inc:Incident {status: 'resolved'}) RETURN count(inc)

-- Metric 4: Services documented
MATCH (:Document)-[:DOCUMENTS]->(s:Service) RETURN count(DISTINCT s)
```

### 9. Direct Dependents & Entity Search (`get_service_dependents`, `search_entities`)
```cypher
-- Direct 1-hop dependents
MATCH (dep:Service)-[:DEPENDS_ON]->(s:Service {id: $sid})
RETURN dep
LIMIT 100

-- Case-insensitive substring search
MATCH (n)
WHERE toLower(n.id) CONTAINS toLower($q) OR toLower(n.title) CONTAINS toLower($q)
RETURN n
LIMIT 100
```

---

## 7. Graph Mapper Rules (`mapper.py`)

The graph mapper translates raw FalkorDB `Node`, `Edge`, and `Path` query results into validated Pydantic models (`GraphView`, `GraphNode`, `GraphEdge`, `EvidenceItem`).

### Freshness & Staleness Calculation
Freshness is calculated from `ingested_at` or `source_updated_at`:
- **Fresh**: `< 30 days` old (`is_stale = False`, `freshness_status = "fresh"`)
- **Aging**: `30 - 90 days` old (`is_stale = True`, `freshness_status = "aging"`)
- **Stale**: `> 90 days` old (`is_stale = True`, `freshness_status = "stale"`)

### Automatic Decision Supersession
When a `SUPERSEDES` edge is present:
- `(:Decision A)-[:SUPERSEDES]->(:Decision B)`
- Decision B (the target of `SUPERSEDES`) is automatically tagged with `status = "superseded"` in its properties.
- Inactive / superseded decisions are properly reflected in visual graph nodes and timeline evidence.

### Path Unpacking & Direction Integrity
FalkorDB driver edge objects contain internal driver IDs (`src_node`, `dest_node`). The mapper maintains an internal ID to canonical `id` lookup table from the path nodes, ensuring:
1. Every edge preserves true source-to-destination direction (`source_id::rel_type::target_id`).
2. Multi-hop and reverse path traversals (such as blast radius) never invert edge direction.
3. Path node IDs on highlighted paths have `on_highlighted_path = True`.
