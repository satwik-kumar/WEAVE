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
