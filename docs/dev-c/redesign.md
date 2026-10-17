# Frontend redesign verification — 2026-10-17

The redesign changes C-owned frontend presentation and adds a browser visual workflow. API contracts, stores, provider behavior and D-owned component source files were preserved. No reference image was attached to this request. No new dependencies were installed.

Implemented a 64px sidebar (48px mobile), 54px header, 40/60 workspace, neutral surface hierarchy, unified native SVG icons, blue interaction/evidence focus, compact entity cards, readable answer typography, numbered source cards and an integrated composer. Responsive graph layout/refitting prevents retaining desktop zoom on mobile. Existing report components inherit the shared shell/styles.

Actual screenshots inspected: empty, populated rationale, source cards, selected service, and widths 390/760/1024/1440. Visual examples explicitly label development fixtures. Screenshots are retained locally under ignored `backend/dist/redesign/`; no production results are fabricated.

Executed from `frontend/`:

```text
npm.cmd run lint
> oxlint
(no findings; exit 0)

npm.cmd run build
> tsc -b && vite build
410 modules transformed.
✓ built in 425ms
(exit 0)

npm.cmd test
Test Files  1 passed (1)
Tests  8 passed (8)
(exit 0)

npm.cmd run test:browser
6 passed (12.6s)
(exit 0; fixtures explicitly enabled by test configuration)

$env:WEAVE_BROWSER_LIVE='1'
npm.cmd run test:browser -- live.spec.ts
1 passed (7.3s)
(exit 0; actual seeded local FalkorDB)
```

Browser coverage retains chat/retry, expansion/dedup, type filters, selected node/timeline, followups, connections, navigation and direct reloads. Visual checks assert desktop panel separation, no page overflow and useful graph height at responsive widths.

Backend instructions also checked from `backend/`:

```text
.\.venv\Scripts\ruff.exe check
All checks passed!

.\.venv\Scripts\python.exe -m pytest tests/unit/ -q
101 passed, 1 warning in 1.61s
```

The remaining warning is the existing upstream Starlette/httpx deprecation. `git diff --check` exited 0 with Git's existing LF/CRLF notices. No known blocking issue, commit, push or deployment.
