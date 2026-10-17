# Dev C execution audit — 2026-10-17

Historical checkpoint: superseded by the later [full-scope implementation audit](../full-scope-audit.md). The user subsequently authorized all guide features; several blockers listed below are now resolved. Retained as evidence of the original Dev C baseline.

Status: C-owned implementation and offline verification delivered; the complete live/agent product remains blocked by the dependencies below. The 16-page local execution guide was read completely. No original blueprint was attached or found. The local PDF is explicitly ignored and was not staged or committed.

## Baseline and authorization

- Existing checkout and branch: `D:\WEAVE`, `feat/c/api-frontend`; initial tree was clean except for the subsequently supplied PDF. Fetched origin at baseline and again during integration. Main/branch divergence: `0 0`, base `5a96928`. No merge/rebase, new branch or clone was needed.
- `weave_brain` is the actual package. B's writer/query/mapper are on main. A's demo records and validator are only on `origin/feat/a/demo-data`; the newly fetched ingestion branch currently points to the baseline. D's modules are absent.
- Canonical routes are `/api/chat` and `/api/health`; guide `/api/v1` examples are historical. Shared TS nullability mismatches were confirmed and repaired with user-provided team approval.
- `uv` was initially missing and PowerShell blocked `npm.ps1`. Installed uv for Python 3.12 and used `npm.cmd`. Frozen installation then exposed the real packaging failure: `Expected a Python module at: src\backend\__init__.py`. The approved shared fix explicitly selects `weave_brain`; frozen installation, wheel build and isolated installed-wheel import now work.
- Baseline unit tests: 27 passed. Baseline frontend lint/build passed with an empty Tailwind content warning. Existing repository findings: 13 domain-model Ruff errors; 11 files need formatting; `datetime.utcnow()` deprecation; seven npm audit advisories. Teammate-owned code was not rewritten to hide those findings.

## Guide requirement mapping

Rows group parallel bullets from every guide page; linked code and the check record provide implementation/check evidence.

| Guide / requirement | Status | Evidence or exact blocker |
| --- | --- | --- |
| pp.1–4: inspect ownership, canonical contracts, package, existing app/libraries, branch and tools | DONE | AGENTS.md/schema/contracts/models/types read; baseline above; preserved existing branch and teammate modules. |
| pp.2,4: package build/import fix | DONE | `backend/pyproject.toml` module selection; frozen sync, wheel build, isolated import and actual startup checks. |
| pp.2,6: nullability and agreed route consistency | DONE | Minimal shared `frontend/src/types/api.ts` edits; interface-contract §10; HTTP contract tests. |
| pp.4–5: settings, .env, CORS, placeholders, no client secrets | DONE | `core/config.py`, root/frontend examples; env precedence and CORS allow/deny tests. Origins accept CSV/JSON and reject credentials/paths/wildcards. |
| p.5: FastAPI app, router assembly, typed responses, readiness/liveness | DONE | `api/main.py`, `api/__main__.py`; real retrieval readiness, fixture readiness 503, separate process liveness. Sync handlers use worker threads. |
| pp.5–6: chat validation, safe dependency errors and no silent fixtures | DONE | Thin `chat_service.py`, deterministic mode warnings, fixture opt-in; API tests for validation, closed-port DB request 503, 500 redaction/CORS and recovery. |
| pp.5–6: call D's actual orchestrator | BLOCKED — D | No agent/orchestrator module or agreed callable exists. Adapter remains explicitly deterministic; no agent implementation is claimed. |
| p.6/current contract: overview, blast radius, neighborhood, search, entity detail | DONE | `GraphService`, API routes, B's named functions/mapper; slash IDs, absent entities, directions and bounds tested. Entity detail uses the agreed existing neighborhood interface. |
| p.6/current contract: shortest-path route with max three hops | DONE | Bounded public neighborhood plus BFS, preserving arrows; tests cover reverse traversal and exclusion of four-hop paths. B's five-hop query is not invoked. |
| pp.2,7: fixture dangling edges, graph limits and deduplication | DONE | Backend `bounded_view`, frontend `cleanGraph`/`mergeGraph`; root preservation, 100-node cap, visible warnings and no fabricated endpoints. B's source defects are recorded in handoffs. |
| p.7: tokens, graph store, canvas, toolbar, detail panel and custom nodes | DONE | `frontend/src/styles`, `store/graphStore.ts`, `components/graph/*`; all 11 entity colors/types use a generic entity node with labels and handles; React Flow styles and real canvas height. |
| p.7: intent-appropriate automatic layout and evidence highlights | DONE | Dagre left-to-right layout and top-down decision layout; backend edge IDs plus response/evidence paths; only consecutive path edges highlighted; unrelated nodes dimmed. |
| p.8: select/deselect, properties, IDs, relationships, safe source links and freshness | DONE | Entity detail panel, timestamp-based unknown/fresh/aging/stale display; click/background handlers; browser selection checks and safe-link unit test. |
| p.8: expand by HTTP, merge/dedup, preserve graph on error, stale-response protection | DONE | Double-click API depth=1, per-node pending state, graph version checks; state and real HTTP fixture browser tests. Browser-detected click/double-click conflict repaired. |
| p.8: filters hide incident edges, fit/zoom/legend and hover metadata | DONE | Toolbar and graph mapping; browser filter/fit checks; edge/node hover data. |
| p.8: optional context-menu/connection polish | NOT RUN | Explicit optional secondary polish; bounded shortest-path API is available. No separate Explore page or extra product scope added. |
| p.8: selected-service DecisionTimeline | BLOCKED — D | Component is absent; exact mount point documented in handoffs. |
| p.9: shell/navigation, AskBrainPage, API helpers, chat state and one submit action | DONE | `App.tsx`, page, `api/*`, `chatStore.ts`; input/cards/retry call the same serialized action. Complete response objects retained. |
| p.9: empty/loading/expansion/missing graph/no evidence/warnings/truncation/error retry | DONE | UI states, safe markdown, optional/null graph/intent/evidence fields; failed HTTP requests preserve prior conversation and graph; state/browser checks. |
| p.9: coherent answer/evidence/graph updates and request races | DONE | Single active question; versioned expansion; new responses replace graph; evidence buttons restore the corresponding response graph before focusing. State tests verify request count and stale expansion rejection. |
| p.9: desktop 40/60 and responsive mobile graph | DONE | Desktop/mobile screenshots inspected; browser checks confirm no horizontal overflow. Graph code is lazy-loaded; build has no oversized-chunk warning. |
| pp.9–10: SuggestedFollowups wired to shared action | BLOCKED — D | D-owned component absent. Mount point and action documented; no substitute D implementation or broken import. |
| p.10: report router exactly once, health/onboarding navigation and report helpers | BLOCKED — D | Reports/services/pages/helpers are absent on fetched main. Unknown routes display an unavailable page and return link; no misleading navigation. |
| p.11: live grounded auth overview/ownership/code/decision evidence | BLOCKED — A/B | Approved seed workflow/data not merged; Docker daemon unavailable; no reachable seeded database. Fixture HTTP checks pass but do not satisfy live acceptance. |
| p.11: live rationale ADR-001/INC-007, incoming blast radius, experts, change impact | BLOCKED — A/B/D | Decision/expert/blast deterministic fixture retrieval is tested. Expert fixture lacks support edges and warns. Change-impact synthesis is explicitly unavailable pending D and supporting records. |
| p.11: different questions produce different graphs; browser inspection/expansion | DONE (fixtures) | Real HTTP fixture browser checks: overview, expansion and blast graph replacement. No live graph pass claimed. |
| p.11: unavailable DB is honest and recoverable | DONE | Actual closed-port B retrieval returns safe 503; liveness remains 200. Mocked recovery and browser HTTP error/retry pass. |
| pp.12–13: reproducible backend/frontend CI | DONE, baseline failures visible | Frozen installation, C lint/format, all offline tests, Node 24, npm ci/lint/unit/build/browser; full repo lint/format remain failing baseline steps. No remote CI execution claimed. |
| p.12: Vercel frontend, Render/Railway backend, host/port, CORS and SPA configuration | DONE (preparation) | Vercel rewrite config, backend Dockerfile, Railway config, Render blueprint; Python host/port entry point and wheel startup. Exact remaining steps in deployment.md. |
| p.12: container build, real cloud DB/TLS, credentials, seeding and public URL validation | NOT RUN / BLOCKED — user/A/B/D | Docker daemon stopped; no hosting deployment authorized, cloud connection or approved seed workflow available. Nothing deployed. |
| pp.12,15: README prerequisites, install, env, seed status, startup/checks, architecture, graph docs, supported questions, limits, AI disclosure | DONE | Root README and deployment/handoff notes; no invented seed command, provider capability or public URL. |
| p.13: API validation/error/contract checks and graph/source integrity | DONE (offline) | C API tests plus existing regression suite; state tests; real browser fixture HTTP. Exact output in check-results.txt. |
| p.13: real DB integration tests | NOT RUN — A/B | Sixteen live tests skip without explicit availability opt-in; daemon/data unavailable. No shared database touched. |
| p.13: public browser and real D followups/reports/onboarding | NOT RUN — D/user | Components and deployment absent. Local direct-route reload and mobile behavior pass. |
| pp.14–16: troubleshoot current failures, keep owner boundaries, audit honestly | DONE | Source-path packaging defect fixed, nullability fixed, click conflict fixed, CORS harness corrected, remaining handoffs enumerated; no non-C owner module rewritten. |
| p.15: team demo recording/submission and external publication | NOT RUN | Not requested or authorized; user prohibited deployment/publication. |

## Check evidence and remaining limits

Final results: 67 unit tests passed; full offline regression run: 69 passed, 16 live tests skipped. Frontend: 7 state tests and 3 browser tests passed; lint/build passed. C-owned Ruff lint/format passed. Full repository lint remains at 13 existing model findings, formatting at 11 existing files, npm audit at 7 existing advisories (5 high, 2 moderate). Wheel build/isolated import and direct module startup passed. Actual unavailable-port database retrieval returned 503 while liveness stayed 200.

Exact commands, exit codes and captured output are in [check-results.txt](check-results.txt). Browser artifacts are local under ignored `frontend/test-results/`; screenshots were inspected. Fixture tests are not FalkorDB integration tests.

No commit, push, merge, external deployment or database reset was performed. PDF exclusion was verified with `git check-ignore`. See [handoffs](handoffs.md) and [deployment steps](deployment.md) for actionable remaining work and owners.
