# WEAVE reference-led UI and themes

Primary visual authority: `D:/WEAVE/sss.png`, opened and inspected. Its narrow white rail, rounded floating content panel, quiet map ground, compact cards and restrained lime status treatment were translated to WEAVE's actual chat/evidence/graph workflow. No map, graph data, metrics or product claims were fabricated.

Skills actually read and used: installed Impeccable (context, critique/audit references, craft floor and polish), `emil-design-eng`, `review-animations` with its standards, and `transitions-dev` with panel/tooltip references. The user supplied a precise reference and prior authorization to proceed; those settled the direction. No skill reinstallation or additional approval was needed. Impeccable's context reported no PRODUCT.md/DESIGN.md; this scoped implementation used the supplied product brief and reference. No project rules or teammate-owned feature source was rewritten.

DialKit 2.0.2 and Motion 14.3.0 were verified installed. DialKit's installed React API was inspected; no tuning panel was added because three small motion parameters did not justify development controls. Motion is used in the lazy-loaded graph/detail components. No production DialKit import exists.

## Critique and technical audit

The initial system had clear functional structure but an incumbent dark identity that conflicted with the supplied reference. Main deficiencies: hard-coded theme colors, small metadata, flat rectangular panels, dense graph overview scaling on phones, continuous highlighted-edge animation, and missing persistence/system theme support. Existing API/state behavior and safe markdown/source handling were sound and preserved.

| Dimension | Result | Evidence and limit |
| --- | --- | --- |
| Accessibility | 3/4 | Labeled native theme select, keyboard operation/focus, system/reduced-motion checks and representative node text contrast >=4.5:1. This is not a full WCAG certification. |
| Performance | 3/4 | Detail/menu motion uses transform/opacity; no continuous decorative edges; graph and Motion remain lazy-loaded. No device frame-rate benchmark. |
| Theming | 4/4 | Shared surface/text/entity/edge/control tokens; Light/Dark/System; early head bootstrap before app/CSS, persistence and blocked-storage tests. |
| Responsive | 3/4 | Desktop/mobile screenshots, 390/760/1024/1440 layouts and overflow checks. Phones use a readable panning viewport; Fit view provides the complete overview. Physical-device testing not run. |
| Integrity | 3/4 | Real product functions retained; fixture captures labeled; Impeccable detector returned `[]`. Detector output is not proof of visual quality. |

Audit: 16/20 (Good), with testing limits above. No known task-blocking defect remains.

## Motion review

| Before | After | Why |
| --- | --- | --- |
| Continuous animated evidence edges in GraphCanvas | Static themed path color/weight | Repeated motion interferes with reading an engineering graph. |
| Detail panel appears/disappears abruptly | Interruptible 200ms entrance / 150ms exit using full transform strings and opacity | Explains the reference-style bottom detail panel without delaying work. |
| Context menu appears abruptly | Trigger-origin scale .97 to 1; 150ms entrance / 100ms exit | Small, anchored and restrained feedback. |
| Keyboard/reduced-motion exits could retain a previous pointer transition | Presence custom variants resolve immediate exits from the current input/reduced-motion state | Escape and keyboard navigation must remain immediate. |
| Potential replay on already-known graph entities | 150ms starting-style reveal only for newly returned expansion IDs; expires after 250ms | Identifies added information without replaying graph entrances on filters/theme changes. |
| Loading feedback can scroll out of a resized conversation | Resize observer keeps active loading/error feedback visible; answers begin at their question | Preserves context and recovery without animated scrolling. |
| Press feedback has no shared rhythm | 150ms deliberate press, 100ms release, scale .98; keyboard/reduced-motion movement disabled | Consistent physical feedback with no bounce or decorative loop. |

Review verdict: **Approve** after corrections. No `transition: all`, animated layout properties, scale-from-zero, perpetual highlighted-edge motion or movement under reduced motion. Panel and menu exits are explicitly shorter than entrances. Keyboard actions are immediate; pointer hover motion is gated. Native selects retain native popup behavior. Transitions.dev informed shared timing/curve vocabulary and panel/tooltip behavior; the heavier blur/400ms panel recipe was not installed.

## Verification

Exact commands, exit codes and output: [reference-polish-checks.txt](reference-polish-checks.txt). Coverage includes chat, retry, followups, decision timelines, reports/routes, expansion/dedup, type filtering, evidence focus, connections, empty/loading/error/selected states and responsive layouts.

Screenshots for both themes and all requested states were captured in Chromium and manually inspected against `sss.png`. Retained locally under ignored `backend/dist/reference-polish/`. Visual inspection found and corrected conversation scrolling, mobile graph scale and textarea shrink behavior. The theme test delays the application entry module to verify the saved dark surface is applied before hydration. Browser/system changes, a saved explicit preference, blocked localStorage and reduced motion are exercised.

No backend logic, shared API types, D-owned features, uncommitted work or database seed was replaced for this UI task. No commit, push or deployment. Tests use explicitly labeled fixtures except the separately identified live FalkorDB browser smoke test. Physical phones and Safari/Firefox are not verified.
