# Independent verification audit — 2026-10-17

**Verdict: the local application works, but the complete Dev C delivery is not ready to call finished.** Four issues remain below; latest upstream integration, paid-provider validation and hosted acceptance are unresolved. This audit inspected and exercised current source rather than treating earlier completion notes as evidence of success. No implementation source was changed.

## Confirmed findings

| Priority | Finding | Evidence / reproduction | Owner |
| --- | --- | --- | --- |
| P1 delivery | Latest D integration is not reconciled | Fetched `origin/main` is `fc317af`; local HEAD is `5a96928`, 0 ahead / 9 behind. Local `chat_service.py:6` imports `aggregate` and `followups`, which do not exist in the upstream orchestrator. It calls `process_question(request, service)`, while upstream D accepts one request argument. Upstream reports use `/api/v1/reports` and `HealthScore` (`overall`, `dimensions`, flat gaps); the local contract/API/UI use `/api/reports`, `HealthReport` (`health_score`, metrics, categorized gaps). Current local versions work together, but replacing them with current D files would not be compatible. No merge or replacement was attempted. | C + D, with shared model/contract coordination |
| P1 accessibility | Dimmed graph text fails normal-text contrast | `frontend/src/components/graph/GraphCanvas.tsx:186` applies opacity 0.7 to the whole node. Browser measurements accounting for compositing over the canvas found User Profile/Notification service type text at **3.32:1** and freshness text at **3.08:1** in Light; service type text measured **4.45:1** in Dark. Target is 4.5:1. The existing theme test checks computed colors on a highlighted node, so it misses ancestor opacity. Preserve text contrast when de-emphasizing unrelated nodes. | C |
| P2 | Focusing evidence resets the intent-specific layout | `frontend/src/components/chat/EvidenceList.tsx:15` calls `replace(graph)` without intent. Live browser probe: `decision_rationale` before Focus evidence path, empty intent afterward. Highlighting works, but decision layout becomes generic left-to-right. Preserve the associated answer's intent when restoring its graph. | C |
| P2 | HOST/PORT in `.env` do not control documented module startup | `backend/src/weave_brain/api/__main__.py:10` reads `os.getenv` before the application/config imports load dotenv. An isolated copy of the exact entry point, with server binding stubbed and `.env` specifying host 127.0.0.1 / port 8123, selected defaults 0.0.0.0 / 8000. The existing local API also listens on 0.0.0.0. **Process** HOST/PORT works: a fresh documented module launch on 8022 and Docker launch on 8127 passed. Load startup configuration before choosing the binding or document process-only settings. | C |

Freshness is **not** a confirmed defect. The initial helper probe returned unknown without timestamps and aging with a recent timestamp plus `is_stale=true`. Inspection of B's mapper shows that its boolean covers both aging and stale records; the guide deliberately requires unknown age when no timestamp exists. Those probe observations do not justify the earlier claim that both must display stale.

## Repository and references

- Expected branch confirmed: `feat/c/api-frontend`. Nothing staged; many modified/untracked implementation files remain, including API, services, agent, ingestion, frontend components/tests, CI and deployment files. Most C delivery is not represented by a commit yet. This is a workspace audit, not a claim that the remote branch contains this work.
- `git fetch origin` succeeded. Inspected all nine incoming commits and changed paths; no pull, merge, branch switch, reset or overwrite. `origin/main` now includes A's ingestion/demo and D/integration commits.
- Read the applicable root AGENTS.md, graph schema, the 16-page execution guide, local interface contract including superseding §§10–11, Python domain models and TypeScript API types. Also inspected relevant remote interfaces. No original 119-page blueprint is present.
- Opened `sss.png`; it is the only matching root reference. Its white rounded content panel, narrow rail, quiet grey/green ground, compact information cards and restrained accents are visibly reflected in the app. The latest reference/theme request supersedes the guide's older dark-only colors.
- Existing previews on 8000/5173 were preserved. Audit browser servers used 8011/5174; documented startup/production preview used 8022/5175. Temporary audit processes/containers were stopped after their checks.

## Actual check results

Exact command output and exit codes: [verification-audit-checks.txt](verification-audit-checks.txt). Additional scripts, probe JSON, runtime output and screenshots are in ignored `backend/dist/audit/`.

| Check | Result | Scope |
| --- | --- | --- |
| `uv sync --frozen` | PASS | Actual current backend environment |
| `uv run ruff check . ../scripts` | PASS | Backend and seed/validation scripts |
| `uv run ruff format --check . ../scripts` | PASS | Formatting checked, no files formatted |
| `uv run pytest tests/unit/ -v` | PASS: **101** | Includes mocked API/provider/error paths |
| `uv run pytest tests/ -q` with live DB enabled | PASS: **119 total**, no skips | Includes the 101 unit tests and 18 integration tests; integration fixtures use UUID graphs and delete only their temporary graphs |
| Actual `scripts/validate_demo.py` | PASS | All 19 frozen demo entities |
| `npm ci --dry-run --ignore-scripts` | PASS | Manifest/lock check; **not** a clean reinstall |
| `npm run lint`, `npm test`, `npm run build` | PASS; **8** state tests | Current frontend source |
| `npm audit` | PASS: **0 vulnerabilities** | Installed frontend dependency audit at run time |
| Existing fixture/browser suite with isolated audit configuration | PASS: **9** | Chat/retry, expansion/dedup/filter, followups/timeline/connections, reports/deep reloads, visual layouts, themes and reduced motion |
| Existing live FalkorDB browser test | PASS: **1** | Actual seeded graph, not fixtures |
| Fresh live HTTP acceptance | PASS | All eight README demo questions, typed endpoints, input errors, source IDs, directions and dependency recovery |
| Production API URL build and preview | PASS | Compiled API URL on 8022; real chat and `/health`/`/onboarding` direct reloads; page errors `[]`, failed requests `[]` |
| `uv build --wheel` | PASS | Current package configuration |
| Fresh backend Docker build/runtime | PASS | Non-root image, PORT=8127, real readiness/chat; temporary verification container removed |
| Impeccable detector | PASS: `[]` | Static detector, not proof of full visual/accessibility correctness |
| Credential pattern scan | No findings | 199 working-tree text files, 23 reachable commits, 109 unique Git blobs; no committed `.env`/PEM/key paths found. Pattern-based, not a guarantee against arbitrary secrets. Values were not printed. |

One existing upstream Starlette/httpx deprecation warning remains. Initial audit-only browser runs failed before tests started because Playwright does not transform a TypeScript config inside node_modules; the temporary harness was corrected to MJS and both suites passed. Those failures are retained in the log and are not application failures. No existing lint/format/test regression failure was found; green suites do not cover all four findings above.

## Backend/API verification

- Documented `python -m weave_brain.api` starts in a fresh process; package import/build and Docker runtime succeed. Environment parsing/precedence and CSV/JSON CORS are covered by tests; allowed and denied real preflights were also exercised. HOST/PORT dotenv caveat is listed above.
- Every current C route exists: liveness/readiness, chat, overview, blast radius, neighborhood, entity detail, shortest path and search. Reports/health score/onboarding/decisions are registered once and work against the local contract. Success responses were validated against Pydantic DTOs.
- Actual HTTP checks covered blank/malformed chat, blank conversation ID, invalid/unknown entity, encoded and unencoded repository slash ID, empty search, missing matches and invalid traversal bounds. Dependency failures are safe 503s; no raw details or credentials were returned.
- AST scan found **no raw query execution calls in API/services**. C uses B's named queries and mapper; sync route functions keep blocking network work out of async handlers.
- Current local agent-mode adapter is connected and its three provider transports/tool/grounding/failure cases pass mock tests. Actual external model success is NOT RUN. It is not yet reconciled with the freshly fetched D implementation.
- A real closed-port connection attempt returned 503, liveness stayed 200 and restored live readiness was 200. Explicit fixtures are labeled and readiness stays 503. Missing model credentials in agent mode returned 503 without switching to retrieval or fixtures.

## Live facts and graph agreement

| Story | Observed actual graph result |
| --- | --- |
| Authentication overview/ownership | Platform Engineering, actual repository, Team → OWNS → authentication; 9 nodes / 6 evidence items |
| Rationale | ADR-001 → MOTIVATED_BY → INC-007; external `adr-001` source ID; 5 nodes / 3 evidence items |
| Blast radius | Authentication plus User Profile/Notification, incoming DEPENDS_ON arrows; 3 nodes / 2 evidence items |
| Experts | Priya Sharma and James Chen with WORKED_ON → Project → USES → Service support; 16 nodes / 2 evidence items |
| Change impact | Retrieved dependents/decisions/incident/ticket; no fabricated files/tests; 16 nodes / 7 evidence items |
| Knowledge health | Actual 66.7 score/gaps; 4-node gap graph; no source-document evidence claimed for that aggregate |
| Onboarding | Two accepted non-superseded decisions and two experts; resolved incident not described as open; 16 nodes / 2 evidence items |
| Connection | Actual Priya-to-service path; 3 nodes / 2 evidence items |

Each returned view was checked for unique IDs, valid endpoints, <=100 nodes and stored edge direction. The demo currently has no file/test records; live file-import/test-coverage answers therefore remain unexercised. This is a data coverage limit, not permission to invent those facts. No shared graph was reseeded or reset for this audit.

## Frontend, visual and theme verification

- Chat, complete responses, warnings, evidence, suggested followups, error retry, retained prior state, selection/background deselection, properties/source IDs, service timeline, repeated expansion, filters, fit/zoom and connections were exercised. State tests cover request serialization, stale expansion rejection, report-page context, limits/dedup and consecutive evidence edges. Evidence intent reset is the exception above.
- An additional isolated browser probe reused an actual retrieved response with null graph/intent/excerpts/URLs and empty suggestions: two answers remained usable, the graph empty state appeared, and no console error occurred. A real unsupported question also returned a usable no-result response. This null-field test is **mocked**, separate from live grounding.
- Both themes were freshly captured and manually inspected at 1440px desktop and 390px mobile for initial, populated, selected-node and error states. Loading/expansion and intermediate 760/1024 widths were also captured by the theme suite. Screenshots are retained under `backend/dist/audit/screenshots/` as `reference-{light|dark}-{state}-{width}.png`.
- The reference-inspired layout, approximately 39/61 desktop split, typography/surface hierarchy, bottom detail panel, composer and compact cards are implemented. Mobile panels stack and scroll; the graph deliberately provides a readable panning viewport with Fit view for the full overview. A settled desktop expansion probe found no off-canvas nodes before or after manual Fit. Tiny overview labels are still a practical mobile limitation when fitting many nodes; the zoom controls restore detail.
- Light, Dark and default System choices, open-app OS changes, saved preference reload, early bootstrap before the application module/CSS, blocked storage, keyboard selection and visible focus were checked. Surface/entity/edge/control/tooltip/detail tokens change consistently. The contrast finding means blanket AA readability is **not** verified.
- Theme test console captures had no page errors. Expected warnings about reduced motion/NO_COLOR and the upstream Python deprecation are not counted as application errors. Physical phones and Safari/Firefox were not tested.

## Design skills and motion audit

Installed skills are present at `.agents/skills/impeccable` and the user's `emil-design-eng`, `review-animations` and `transitions-dev` skill folders. This audit applied Impeccable's technical audit/detector and manually compared the reference; it applied Emil's motion review against actual source and reduced-motion tests. It did **not** run the separate full Impeccable critique workflow or claim its multi-review process occurred.

Historical local notes (`reference-polish.md`) and the conversation record document earlier skill reads/use, and the source contains matching timing/token choices. That supports documented historical use, not a claim of an independently recorded CLI command for every workflow. Transitions.dev's guidance is adapted; its full panel/tooltip recipe was not installed verbatim. DialKit is an installed application dependency, not an agent skill: current `npm ls` confirms DialKit 2.0.2 / Motion 14.3.0, source contains no DialKit imports, and production pages expose no tuning panel.

| Before / checked source | After / recommendation or observation | Why |
| --- | --- | --- |
| Detail panel full-transform/opacity entry, 200ms; exit 150ms | Retain | Bounded, spatially appropriate, shorter exit; current keyboard/reduced-motion presence variants are immediate |
| Context menu scale .97 from top-left, 150ms entry / 100ms exit | Retain | Trigger-origin restrained feedback; no scale-from-zero |
| Continuous highlighted-edge motion | Already absent in current source | Static path color/weight preserves reading focus |
| Newly added expansion IDs and CSS starting-style reveal | Retain | Short, expires; not replayed for all known nodes on each filter/theme change |
| Whole-node opacity 0.7 | Keep text opaque; de-emphasize surface/border instead | Confirmed contrast regression; this is a visual/accessibility finding, not a reason to add more animation |

Motion verdict: **Approve within the exercised Chromium scope**. No feel-breaking timing, layout-property animation, unconditional decorative edge loop, ungated moving hover or missing reduced-motion branch was found. This is not an on-device frame-rate benchmark.

Impeccable technical audit: accessibility 2/4 (contrast defect); performance 3/4 (no profile); theming 3/4 (working preferences, contrast incomplete); responsive 3/4 (emulation, dense graph caveat); integrity 3/4 (real product data, layout state issue). **14/20**; this score does not override the P1 release issues. Recommended follow-up work: harden evidence restoration/startup, correct graph contrast, then polish. No fixes were applied in this audit.

## Guide requirement disposition

| Guide scope | Disposition |
| --- | --- |
| pp.1–4 inspection, ownership, package/setup/current contracts | DONE inspection; latest shared/upstream reconciliation remains BLOCKED on C+D coordination |
| pp.5–6 C-1 routes, typed validation, safe errors/configuration | DONE local runtime/tests, except dotenv startup binding; upstream D adapter remains PARTIAL |
| pp.7–8 C-2 rendering/interactions | DONE core interactions; PARTIAL contrast and intent-preserving evidence focus |
| p.9 C-3 Ask Brain/states/concurrency | DONE functional loading/error/no-result/retry and state safety. The guide's specific answer-skeleton treatment is absent; status text/dot is used instead. |
| p.10 D reports/followups/onboarding/timeline | DONE with current local versions; NOT VERIFIED against new upstream D interfaces |
| p.11 real vertical slice | DONE deterministic live retrieval for all eight listed stories; paid-model synthesis NOT RUN |
| pp.12–13 CI/deployment/checks | DONE local configs/build/checks/container/production preview; hosted CI/cloud TLS/public deployment acceptance NOT RUN |
| pp.14–16 troubleshooting/README/demo audit | DONE audit and documented commands; hosted URL and external demo submission remain NOT RUN |

## Remaining external dependencies and delivery limits

- **C + D / shared contracts:** reconcile incoming orchestrator/report/health-model interfaces while preserving local work. Prior user/team authorization is already in the conversation; this audit did not identify a new permission requirement.
- **User + D:** supply an actual provider key/model to verify real model calls, grounding quality and provider failure behavior. No configured key/model was available; only safe booleans were reported.
- **User + B:** approved cloud DB/hosting credentials, origins and deployment authorization are needed for hosted TLS/auth and public-browser acceptance. Local DB connectivity is available and passed; there is no current A/B blocker to the local demo.
- **C delivery:** CI/deployment files are uncommitted; no remote CI execution was triggered. A clean frontend reinstall was not run to avoid replacing an active preview's dependencies; only lock dry-run/installed build was checked. Linux CI and external hosting behavior remain unverified.

No source fixes, commits, staging, pushes, merges, branch switches, external deployments or shared database resets were performed. The PDF and environment remain ignored. Existing local preview processes were left running.
