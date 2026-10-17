"""Focused unit tests for ChatService adapter."""

from unittest.mock import patch

from weave_brain.core.config import Settings
from weave_brain.domain.models import ChatRequest, ChatResponse, EvidenceItem, GraphView
from weave_brain.services.chat_service import submit_question
from weave_brain.services.graph_service import GraphService


def test_submit_question_delegates_to_orchestrator():
    """Verify submit_question constructs ChatRequest and calls process_question with 1 arg."""
    mock_response = ChatResponse(
        answer="Authentication service handles JWT verification.",
        evidence=[
            EvidenceItem(
                source_id="decision:adr-001",
                title="ADR-001 JWT Auth",
                source_type="decision",
            )
        ],
        graph=GraphView(nodes=[], edges=[]),
        warnings=["AI provider offline: test warning"],
        intent="get_service_overview",
    )

    with patch(
        "weave_brain.services.chat_service.process_question",
        return_value=mock_response,
    ) as mock_process:
        result = submit_question("How does auth work?")

        mock_process.assert_called_once()
        args, kwargs = mock_process.call_args
        assert len(args) == 1
        assert len(kwargs) == 0
        req = args[0]
        assert isinstance(req, ChatRequest)
        assert req.question == "How does auth work?"

        assert result.answer == "Authentication service handles JWT verification."
        assert len(result.evidence) == 1
        assert result.evidence[0].source_id == "decision:adr-001"
        assert result.warnings == ["AI provider offline: test warning"]
        assert result.intent == "get_service_overview"


def test_submit_question_with_service_development_fixtures_adds_warning():
    """Verify development_fixtures warning is appended when enabled on service."""
    mock_response = ChatResponse(
        answer="Overview of service.",
        warnings=["Existing agent warning"],
    )

    settings = Settings(development_fixtures=True)
    service = GraphService(settings)

    with patch(
        "weave_brain.services.chat_service.process_question",
        return_value=mock_response,
    ):
        result = submit_question("Tell me about service", service=service)

        assert "Existing agent warning" in result.warnings
        assert (
            "Development fixture data; no live database retrieval." in result.warnings
        )


def test_submit_question_does_not_duplicate_fixture_warning():
    """Verify warning is not duplicated if already present in response."""
    fixture_warning = "Development fixture data; no live database retrieval."
    mock_response = ChatResponse(
        answer="Overview of service.",
        warnings=[fixture_warning],
    )

    settings = Settings(development_fixtures=True)
    service = GraphService(settings)

    with patch(
        "weave_brain.services.chat_service.process_question",
        return_value=mock_response,
    ):
        result = submit_question("Tell me about service", service=service)

        assert result.warnings.count(fixture_warning) == 1


def test_submit_question_without_service_does_not_add_fixture_warning():
    """Verify no fixture warning is added if service is None."""
    mock_response = ChatResponse(
        answer="Overview of service.",
        warnings=[],
    )

    with patch(
        "weave_brain.services.chat_service.process_question",
        return_value=mock_response,
    ):
        result = submit_question("Tell me about service", service=None)

        assert (
            "Development fixture data; no live database retrieval."
            not in result.warnings
        )


def test_submit_question_service_without_development_fixtures():
    """Verify no fixture warning is added if development_fixtures is False."""
    mock_response = ChatResponse(
        answer="Overview of service.",
        warnings=[],
    )

    settings = Settings(development_fixtures=False)
    service = GraphService(settings)

    with patch(
        "weave_brain.services.chat_service.process_question",
        return_value=mock_response,
    ):
        result = submit_question("Tell me about service", service=service)

        assert (
            "Development fixture data; no live database retrieval."
            not in result.warnings
        )
