# WEAVE frontend

The workspace uses React, TypeScript, Vite and React Flow. API configuration is
unchanged: set `VITE_API_BASE_URL` for your local service (default
`http://localhost:8000`). Light, Dark and System preferences persist under
`weave-theme`; the HTML bootstrap applies the theme before React loads.

Frontend checks:

```sh
npm run lint
npm run build
npm test
npx playwright test --config playwright.ui.config.ts
```

The UI Playwright configuration starts only Vite. Its tests intercept API requests
with explicitly labeled synthetic fixtures, independent of backend services.
Screenshots for chat, graph, errors, health and onboarding are written to
`test-results/` (ignored by Git). These checks do **not** verify live integration.
The existing `playwright.config.ts` retains its service-based integration checks.

With the frontend and backend already running, check the actual integration with:

```sh
npx playwright test --config playwright.live-ui.config.ts
```

This configuration uses `http://localhost:5173` and the frontend's configured API
without intercepting responses or starting backend services. Its screenshots and
traces are local artifacts under `.ui-review.local/`.

Desktop navigation has labels; tablet navigation uses a compact rail; mobile uses
a bottom bar with safe-area spacing. Graph nodes support both double-click
expansion and an **Expand neighborhood** button in entity details.

Use the graph finder to search returned entities by name or canonical ID, including
entities hidden by filters. Arrow keys navigate results and Enter opens the record
at readable zoom. **Show all entities** restores the overview. The maximize control
opens a graph workspace with keyboard focus contained inside it; Escape closes
entity details first, then restores the workspace.

In chat, Enter sends and Shift+Enter adds a line. Ctrl/Cmd + / focuses the composer.
Unsent drafts survive route changes in memory, and clear on reload. Answers and
entity IDs can be copied; source records can be collapsed without losing them.

Design references: [Apple materials](https://developer.apple.com/design/human-interface-guidelines/materials)
for separation of controls and reading surfaces, and [Linear search](https://linear.app/docs/search)
for keyboard-driven entity discovery. Existing WEAVE colors and tokens remain the
visual foundation. Browser checks cover emulated mobile sizes; real-device Safari,
software keyboard behavior and safe-area rendering still need device verification.

---

## Vite template notes

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
