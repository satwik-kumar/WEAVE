"""Chat service adapter delegating to the canonical agent orchestrator."""

from __future__ import annotations

from weave_brain.agent.orchestrator import process_question
from weave_brain.domain.models import ChatRequest, ChatResponse
from weave_brain.services.graph_service import GraphService


def submit_question(
    question: str,
    service: GraphService | None = None,
) -> ChatResponse:
    """Submit a question to the WEAVE brain knowledge assistant.

    Constructs a canonical ChatRequest and delegates execution directly to
    the canonical orchestrator `process_question(request)`.
    """
    request = ChatRequest(question=question)
    response = process_question(request)

    if service is not None and getattr(service.settings, "development_fixtures", False):
        fixture_warning = "Development fixture data; no live database retrieval."
        if fixture_warning not in response.warnings:
            response.warnings.append(fixture_warning)

    return response
