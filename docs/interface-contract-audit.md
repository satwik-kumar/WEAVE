# WEAVE — Interface Contract Verification & Audit

**Audit Date:** 2026-10-17  
**Scope:** Verification of `docs/interface-contract.md` against codebase, Pydantic models, FalkorDB queries, TypeScript interfaces, and tests.  
**Branch:** `main` (commit `f57b37a`)  

---

## 1. Executive Summary

This document audits the contracts defined in [`docs/interface-contract.md`](file:///d:/projects/hackathon/WEAVE/WEAVE/docs/interface-contract.md) against the actual implementation in `backend/` and `frontend/`.

- **Developer B (FalkorDB & Graph Engine):** **VERIFIED**. 100% of defined functions, signatures, models, and idempotency guarantees match implementation and pass all unit and integration tests (45 of 45 passing).
- **Shared Data Models (`models.py` & `api.ts`):** **VERIFIED WITH LINT ADVISORY**. Model schemas match TypeScript interfaces 1:1. A Python 3.12 `DeprecationWarning` exists for `datetime.utcnow()` in `models.py:101`.
- **Developer A (Ingestion):** **NOT YET VERIFIABLE (PENDING IMPLEMENTATION)**. Ingestion directory and demo datasets are not yet implemented.
- **Developer C (API & UI):** **NOT YET VERIFIABLE (PENDING IMPLEMENTATION)**. API routes are not yet implemented; frontend template is ready.
- **Developer D (Agent & Reports):** **NOT YET VERIFIABLE (PENDING IMPLEMENTATION)**. Agent tools and reports are not yet implemented.

---

## 2. Interface Verification Matrix

| Interface / Requirement | Expected Contract | Actual Implementation | Code Evidence | Test Evidence | Status | Responsible Developer | Recommended Next Action |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FalkorDB Client** | `get_client(host, port)`, `get_graph(name, host, port)` | Reads env vars, raises `ConfigurationError` on missing/invalid config | [`backend/src/weave_brain/graph/client.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/client.py#L22-L71) | `tests/integration/test_smoke.py::test_configuration_error_when_env_vars_missing` | **VERIFIED** | Dev B | None. |
| **Schema Indexing** | `init_schema(graph)` creates indexes for 11 entity types on `id` | Idempotent index creation with existing index inspection | [`backend/src/weave_brain/graph/schema.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/schema.py#L68-L98) | `tests/unit/test_graph_schema.py` (7 tests) + `tests/integration/test_schema.py` | **VERIFIED** | Dev B | None. |
| **Batch Upsert** | `upsert_many(artifacts, graph, source_name) -> SyncReport` | Two-phase batch upsert (nodes then relationships), no phantom nodes | [`backend/src/weave_brain/graph/writer.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/writer.py#L232-L302) | `tests/unit/test_graph_writer.py` (12 tests) + `tests/integration/test_writer.py` (5 tests) | **VERIFIED** | Dev B | Ingestion pipeline can consume immediately. |
| **Service Overview** | `get_service_overview(service_id, graph) -> dict \| None` | Returns service, team, repos, decisions, docs, dependents, evidence, graph | [`backend/src/weave_brain/graph/queries.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/queries.py#L140-L268) | `tests/integration/test_queries.py::test_get_service_overview_live` | **VERIFIED** | Dev B | Ready for Dev C API `/api/services/{id}`. |
| **Decisions Retrieval** | `get_decisions_for_service(service_id, graph) -> dict` | Returns decisions, incidents, supersedes chains | [`backend/src/weave_brain/graph/queries.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/queries.py#L271-L353) | `tests/integration/test_queries.py::test_get_decisions_for_service_live` | **VERIFIED** | Dev B | Ready for Dev D Decision Timeline. |
| **Blast Radius** | `get_blast_radius(service_id, max_depth, graph) -> dict` | Traverses incoming `<-[:DEPENDS_ON*1..3]-` | [`backend/src/weave_brain/graph/queries.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/queries.py#L355-L443) | `tests/integration/test_queries.py::test_get_blast_radius_live` | **VERIFIED** | Dev B | Ready for Dev C `/api/services/{id}/blast-radius`. |
| **Expertise Discovery** | `find_experts(service_id, graph) -> list[dict]` | Returns engineers connected via `WORKED_ON -> Project -> USES` | [`backend/src/weave_brain/graph/queries.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/queries.py#L446-L476) | `tests/integration/test_queries.py::test_find_experts_live` | **VERIFIED** | Dev B | Ready for Dev D Agent tool. |
| **Neighborhood Query** | `get_neighborhood(node_id, depth, graph) -> dict` | Bounded neighborhood centered on node_id with highlighted center | [`backend/src/weave_brain/graph/queries.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/queries.py#L478-L525) | `tests/integration/test_queries.py::test_get_neighborhood_live` | **VERIFIED** | Dev B | Ready for Dev C Explorer graph. |
| **Shortest Path** | `find_shortest_path(from_id, to_id, graph) -> dict` | 5-hop shortest path returning `{path_found, nodes, edges, highlighted_path_ids}` | [`backend/src/weave_brain/graph/queries.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/queries.py#L527-L570) | `tests/integration/test_queries.py::test_find_shortest_path_live` | **VERIFIED** | Dev B | Ready for Dev D "Find Connection". |
| **Knowledge Gaps & Health Score** | `get_knowledge_gaps()`, `get_health_score()` | Returns 4 metrics (`services_owned`, `decisions_rationale`, `incidents_resolved`, `services_documented`) | [`backend/src/weave_brain/graph/queries.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/queries.py#L572-L688) | `tests/integration/test_queries.py::test_get_knowledge_gaps_and_health_score_live` | **VERIFIED** | Dev B | Ready for Dev D Health Dashboard. |
| **Graph & Evidence Mappers** | `to_graph_view()`, `to_evidence_items()` | Maps raw Cypher results into `GraphView` and `list[EvidenceItem]`, flags staleness and supersession | [`backend/src/weave_brain/graph/mapper.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/mapper.py#L91-L390) | `tests/unit/test_queries_mapper.py` (5 tests) | **VERIFIED** | Dev B | None. |
| **Offline Stubs** | 5 fixture functions in `graph/fixtures.py` | Returns mock data validating as `GraphView` and `EvidenceItem` without database | [`backend/src/weave_brain/graph/fixtures.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/graph/fixtures.py#L1-L502) | `tests/integration/test_smoke.py::test_offline_fixtures_validation` | **VERIFIED** | Dev B | None. |
| **Shared Pydantic Models** | `domain/models.py` | 8 models matching TypeScript contract 1:1 | [`backend/src/weave_brain/domain/models.py`](file:///d:/projects/hackathon/WEAVE/WEAVE/backend/src/weave_brain/domain/models.py#L1-L126) | Used across all tests | **VERIFIED WITH LINT ADVISORY** | All Devs | Fix `datetime.utcnow()` deprecation at line 101. |
| **Shared TypeScript Types** | `frontend/src/types/api.ts` | Matches `domain/models.py` 1:1 | [`frontend/src/types/api.ts`](file:///d:/projects/hackathon/WEAVE/WEAVE/frontend/src/types/api.ts#L1-L71) | Compile-time validation | **VERIFIED** | All Devs | None. |
| **Ingestion Pipeline** | `backend/src/weave_brain/ingestion/` | Directory exists, but parsers are not yet implemented | Directory empty | None | **NOT YET VERIFIABLE** | Dev A | Implement JSON & Markdown parsers emitting `SourceArtifact`. |
| **Demo Data Seed Files** | `data/demo/` | Seed data directory exists, but JSON/MD files are missing | Directory empty | None | **NOT YET VERIFIABLE** | Dev A | Add 19 frozen demo entity seed files to `data/demo/`. |
| **API Endpoints** | `backend/src/weave_brain/api/routes/` | Routes directory exists, but endpoint files (`chat.py`, `services.py`) are missing | Directory empty | None | **NOT YET VERIFIABLE** | Dev C | Implement routes calling B's queries and returning models. |
| **Agent Tools & Orchestration** | `backend/src/weave_brain/agent/` | Agent directory exists, but LLM tools and graph orchestration are missing | Directory empty | None | **NOT YET VERIFIABLE** | Dev D | Implement agent tools wrapping B's queries. |
| **Health Dashboard Page** | `frontend/src/pages/HealthPage.tsx` | Page not yet created | Missing | None | **NOT YET VERIFIABLE** | Dev D | Implement `HealthPage.tsx` calling `/api/health-score`. |

---

## 3. Discrepancy & Mismatch Analysis

### 3.1 Historical Blueprint vs. Actual Implementation
1. **Package Name Discrepancy:**  
   - Earlier architectural notes suggested `backend/src/repocompass_brain/` or `backend/src/weave/`.  
   - **Actual Implementation:** The single authoritative package is `backend/src/weave_brain/`. `pyproject.toml`, Git history, and all imports strictly reference `weave_brain`. There is no package naming defect in code.
2. **Environment Variable Naming in `.env.example`:**  
   - Line 3 of `.env.example` lists `FALKORDB_GRAPH_NAME=repocompass_brain`.  
   - **Contract Recommendation:** Change `.env.example` to `FALKORDB_GRAPH_NAME=weave_brain` for consistency across teams.
3. **Deprecation in Shared Domain Model:**  
   - `src/weave_brain/domain/models.py:101` uses `datetime.utcnow()`, which triggers a Python 3.12 `DeprecationWarning`.  
   - **Contract Recommendation:** Group consensus to update to `datetime.now(UTC)` or `Field(default_factory=...)`.

---

## 4. Cross-Developer Readiness Assessment

### Can Developers A, B, C, and D integrate independently right now?
**YES.**
- **Developer A** has a crystal-clear writer contract: instantiate `SourceArtifact` and pass lists to `upsert_many()`.
- **Developer B**'s work is 100% complete and tested.
- **Developer C** has exact function signatures in `weave_brain.graph.queries` and `weave_brain.graph.mapper` to implement all API routes without guessing return shapes, and has `fixtures.py` to test offline.
- **Developer D** has dedicated query functions for all 6 required agent tools and the exact data structure for the Onboarding Brief and Health Score.

---

## 5. Single Highest-Priority Integration Blocker

**Developer A's missing demo data (`data/demo/`) and ingestion seed script.**

Until Developer A implements the JSON/Markdown parser and seeds the 19 demo entities into FalkorDB, the API routes (Dev C) and Agent (Dev D) will only return empty results or fall back to offline fixtures. Seeding the live database is the critical path for full-system demonstration.
EOF
