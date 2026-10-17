# Deployment preparation — no external deployment performed

Vercel frontend and Render/Railway backend configuration is ready. The backend image built successfully and served readiness and chat against actual FalkorDB on a local Docker network. No hosting project was created, no credentials were collected, no shared graph was reset, and no public URL is claimed.

## Backend: Render or Railway

1. Provision the intended FalkorDB connection and graph name with the account owner. Host/port/graph, optional username/password, TLS and finite socket timeouts are implemented. Use `FALKORDB_SSL=true` for TLS; certificate and hostname checks remain enabled.
2. From the repository root, build with `docker build -t weave-api:local ./backend`. The image uses Python 3.12, uv 0.13.1, frozen dependencies and an unprivileged runtime user. Its entry point is `python -m weave_brain.api`; `HOST` and the hosting platform's `PORT` are read directly by Python.
3. Render: use root `render.yaml`, or a Docker web service with root directory `backend` and Dockerfile `Dockerfile`. Auto-deployment is disabled. Railway alternative: root directory `backend`, config `/backend/railway.json`, supplied Dockerfile; set `RAILWAY_DOCKERFILE_PATH` explicitly if using another build context.
4. Configure `ALLOWED_ORIGINS`, `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_GRAPH_NAME`, optional DB username/password, TLS and `DEVELOPMENT_FIXTURES=false`. Set `CHAT_MODE=retrieval` for deterministic live graph answers. For AI synthesis, set `CHAT_MODE=agent`, `LLM_PROVIDER`, an available tool-capable `LLM_MODEL` and its `LLM_API_KEY` on the backend account only.
5. Readiness `/api/health` requires successful real retrieval; `/api/live` checks process liveness. Fixture mode intentionally fails readiness. Configure a working graph before expecting deployment health checks to pass.
6. After confirming the intended graph name, run A's actual commands from an environment with the backend dependencies and target DB settings: `backend/.venv/Scripts/python.exe scripts/validate_demo.py`, then `backend/.venv/Scripts/python.exe scripts/seed_demo.py` from the root on Windows. On Linux use the corresponding `.venv/bin/python`. Seeding is idempotent. Do not use the reset script on a shared graph.

Official references: [Render FastAPI startup](https://render.com/docs/deploy-fastapi), [Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles), [Railway health checks](https://docs.railway.com/deployments/healthchecks).

## Frontend: Vercel

1. Select/create the hosting project when external deployment is requested. Root: `frontend`; Node: 24; install: `npm ci`; build: `npm run build`; output: `dist`.
2. Set `VITE_API_BASE_URL=https://your-backend.example` without `/api`; rebuild when it changes. Vite embeds public configuration in JS, so DB/provider secrets must never use `VITE_*` variables.
3. Set backend `ALLOWED_ORIGINS` to the exact frontend origin. Add preview origins only when intended. C's settings reject wildcard origins and URLs with credentials or paths.
4. `frontend/vercel.json` handles SPA rewrites; `/health` and `/onboarding` are implemented routes. Test direct navigation/reload on the real hosting platform after deployment. Local reload checks already pass.
5. From the public frontend verify live readiness, ownership/evidence/graph agreement, rationale lineage, blast radius, expertise, change impact, sources, expansion/filter/focus/connection, followups, health gaps, onboarding, mobile layout, error/retry and cold start.

Official references: [Vercel configuration](https://vercel.com/docs/project-configuration/vercel-json), [rewrites](https://vercel.com/docs/routing/rewrites).

## Provider configuration and remaining account checks

All three adapters implement actual tool/result wire protocols: [OpenAI Responses function calling](https://developers.openai.com/api/docs/guides/function-calling), [Gemini stateless function calling](https://ai.google.dev/gemini-api/docs/function-calling), [Anthropic tool definitions](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools). Mock HTTP tests exercise each full tool roundtrip, failures, invalid tools/citations, unknown entities and loop budgets.

No model/API key is configured locally, so successful paid-provider calls were not run. Cloud TLS/authentication and public-browser checks require the actual account connection and deployment. These are verification/account prerequisites, not missing agent/report/UI implementations.
