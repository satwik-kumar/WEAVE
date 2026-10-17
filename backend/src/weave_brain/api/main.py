"""Run with uvicorn weave_brain.api.main:app --app-dir src."""

import logging

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.exceptions import RedisError

from weave_brain.agent.providers import ProviderError
from weave_brain.core.config import Settings, get_settings
from weave_brain.core.logging import configure_logging
from weave_brain.core.validation import canonical
from weave_brain.domain.models import ChatRequest, ChatResponse, GraphNode, GraphView
from weave_brain.graph.client import ConfigurationError
from weave_brain.services.chat_service import submit_question
from weave_brain.services.graph_service import (
    BlastRadius,
    GraphService,
    ServiceOverview,
    ShortestPath,
)


class Readiness(BaseModel):
    status: str
    database: str


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    configure_logging()
    service = GraphService(config)
    app = FastAPI(title="WEAVE", version="1.0.0")
    router = APIRouter()
    app.state.graph_service = service

    @app.exception_handler(ProviderError)
    @app.exception_handler(RedisError)
    @app.exception_handler(ConfigurationError)
    async def unavailable(_request: Request, _error: Exception):
        return JSONResponse(
            status_code=503,
            content={"detail": "A required dependency is unavailable. Please retry."},
        )

    @app.middleware("http")
    async def safe_boundary(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as error:  # noqa: BLE001 -- final HTTP boundary; redact internal failures
            # Log only the exception class, never dependency strings or user input.
            logging.getLogger(__name__).error(
                "Internal request failure (%s).", type(error).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "An internal error occurred. Please retry."},
            )

    @app.exception_handler(RequestValidationError)
    async def invalid(_request: Request, _error: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid request fields or query parameters."},
        )

    @router.get("/api/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/health", response_model=Readiness)
    def health():
        if config.development_fixtures:
            return JSONResponse(
                status_code=503,
                content={"status": "development", "database": "fixtures"},
            )
        service.search("service:")
        return Readiness(status="ok", database="connected")

    @router.post("/api/chat", response_model=ChatResponse)
    def chat(body: ChatRequest):
        question = body.question.strip()
        if not question or len(question) > 4000:
            raise HTTPException(400, "Question must contain 1 to 4000 characters.")
        if body.conversation_id is not None and (
            not body.conversation_id.strip() or len(body.conversation_id) > 200
        ):
            raise HTTPException(400, "Invalid conversation ID.")
        return submit_question(question, service)

    # Register suffix routes before path converters; canonical file IDs contain slashes.
    @router.get("/api/services/{service_id}/blast-radius", response_model=BlastRadius)
    def blast(service_id: str, max_depth: int = Query(3, ge=1, le=3)):
        return service.blast(canonical(service_id, True), max_depth)

    @router.get("/api/services/{service_id}", response_model=ServiceOverview)
    def overview(service_id: str):
        return service.overview(canonical(service_id, True))

    @router.get("/api/graph/neighborhood/{node_id:path}", response_model=GraphView)
    def neighborhood(node_id: str, depth: int = Query(2, ge=1, le=3)):
        return service.neighborhood(canonical(node_id), depth)

    @router.get("/api/search", response_model=list[GraphNode])
    def search(q: str = Query(min_length=1, max_length=200)):
        if not q.strip():
            raise HTTPException(400, "Search query cannot be blank.")
        return service.search(q.strip())

    @router.get("/api/entities/{node_id:path}", response_model=GraphNode)
    def entity(node_id: str):
        return service.entity(canonical(node_id))

    @router.get("/api/graph/shortest-path", response_model=ShortestPath)
    def shortest(from_id: str, to_id: str):
        source, target = canonical(from_id), canonical(to_id)
        try:
            return service.shortest(source, target)
        except HTTPException as error:
            if error.status_code == 404:
                raise HTTPException(400, "Starting entity not found.") from None
            raise

    app.include_router(router)
    from weave_brain.api.routes.reports import router as reports_router

    app.include_router(reports_router)
    # CORS must wrap the failure boundary so error responses remain browser-readable.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    return app


app = create_app()
