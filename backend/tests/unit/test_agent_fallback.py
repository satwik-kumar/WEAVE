"""Targeted unit tests for agent fallback visibility, safety, and decision grounding."""

import copy
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from weave_brain.agent.answer_generator import (
    generate_answer,
    synthesize_grounded_answer,
)
from weave_brain.agent.orchestrator import (
    process_question,
)
from weave_brain.agent.prompts import ANSWER_SYSTEM
from weave_brain.agent.provider import GeminiProvider
from weave_brain.core.config import Settings
from weave_brain.domain.models import ChatRequest, ChatResponse


def _sample_decision_evidence() -> dict:
    """Build isolated decision evidence matching seeded demo graph entities."""
    return {
        "service_id": "service:authentication-api",
        "decisions": [
            {
                "id": "decision:adr-001",
                "title": "Token expiry 24h policy",
                "properties": {
                    "status": "accepted",
                    "decision_date": "2025-11-15",
                    "rationale": "Mitigate risk of stolen long-lived tokens following incident INC-007",
                },
            },
            {
                "id": "decision:adr-002",
                "title": "Service mesh adoption",
                "properties": {
                    "status": "superseded",
                    "decision_date": "2025-06-01",
                    "rationale": "",
                },
            },
            {
                "id": "decision:adr-003",
                "title": "Envoy proxy standard",
                "properties": {
                    "status": "accepted",
                    "decision_date": "2026-01-20",
                    "rationale": "Standardize Envoy sidecars for service-to-service mTLS and observability",
                },
            },
        ],
        "evidence": [],
        "graph": {
            "nodes": [
                {
                    "id": "decision:adr-001",
                    "title": "Token expiry 24h policy",
                    "entity_type": "decision",
                    "properties": {"status": "accepted"},
                },
                {
                    "id": "decision:adr-002",
                    "title": "Service mesh adoption",
                    "entity_type": "decision",
                    "properties": {"status": "superseded"},
                },
                {
                    "id": "decision:adr-003",
                    "title": "Envoy proxy standard",
                    "entity_type": "decision",
                    "properties": {"status": "accepted"},
                },
                {
                    "id": "incident:inc-007",
                    "title": "Token leak incident",
                    "entity_type": "incident",
                    "properties": {},
                },
            ],
            "edges": [
                {
                    "id": "decision:adr-001::MOTIVATED_BY::incident:inc-007",
                    "source_id": "decision:adr-001",
                    "target_id": "incident:inc-007",
                    "relationship_type": "MOTIVATED_BY",
                },
                {
                    "id": "decision:adr-003::SUPERSEDES::decision:adr-002",
                    "source_id": "decision:adr-003",
                    "target_id": "decision:adr-002",
                    "relationship_type": "SUPERSEDES",
                },
            ],
            "root_node_ids": ["decision:adr-001", "decision:adr-002", "decision:adr-003"],
        },
    }


def test_gemini_successful_classification_and_answer():
    """Requirement 1: Successful Gemini classification and answer generation produces no warnings."""
    mock_provider = MagicMock(spec=GeminiProvider)
    mock_provider.complete.side_effect = [
        '{"tool": "get_service_overview", "service_id": "service:authentication-api"}',
        "The Authentication API is owned by Platform Engineering according to team:platform-engineering.",
    ]

    with patch("weave_brain.agent.orchestrator.get_provider", return_value=mock_provider), patch(
        "weave_brain.agent.orchestrator.get_settings"
    ) as mock_settings:
        mock_settings.return_value = Settings(
            llm_provider="gemini",
            gemini_api_key=SecretStr("mock-key-secret"),
        )
        resp = process_question(ChatRequest(question="Who owns the authentication service?"))

        assert resp.warnings == []
        assert resp.intent == "get_service_overview"
        assert "Platform Engineering" in resp.answer


def test_classification_failure_deterministic_fallback():
    """Requirement 2: Classification failure cleanly falls back to deterministic routing with safe warning."""
    mock_provider = MagicMock(spec=GeminiProvider)
    # Classifier fails with rate limit, answer succeeds
    mock_provider.complete.side_effect = [
        Exception("HTTP 429 Quota exceeded: https://api.google.com/key=MOCK_SECRET"),
        "Synthesized answer text according to decision:adr-001.",
    ]

    with patch("weave_brain.agent.orchestrator.get_provider", return_value=mock_provider), patch(
        "weave_brain.agent.orchestrator.get_settings"
    ) as mock_settings:
        mock_settings.return_value = Settings(
            llm_provider="gemini",
            gemini_api_key=SecretStr("mock-key-secret"),
        )
        resp = process_question(ChatRequest(question="Who owns the authentication service?"))

        assert "AI classifier unavailable; used deterministic routing." in resp.warnings
        assert resp.intent == "get_service_overview"


def test_answer_generation_failure_deterministic_fallback():
    """Requirement 3: Answer-generation failure cleanly falls back to grounded synthesis with safe warning."""
    mock_provider = MagicMock(spec=GeminiProvider)
    # Classifier succeeds, answer generation explodes
    mock_provider.complete.side_effect = [
        '{"tool": "get_decisions_for_service", "service_id": "service:authentication-api"}',
        Exception("Connection timeout to https://generativelanguage.googleapis.com?key=SECRET_TOKEN_LEAK"),
    ]

    mock_evidence = _sample_decision_evidence()
    with patch("weave_brain.agent.orchestrator.get_provider", return_value=mock_provider), patch(
        "weave_brain.agent.orchestrator.get_settings"
    ) as mock_settings, patch("weave_brain.agent.orchestrator.call_tool", return_value=mock_evidence):
        mock_settings.return_value = Settings(
            llm_provider="gemini",
            gemini_api_key=SecretStr("mock-key-secret"),
        )
        resp = process_question(ChatRequest(question="Why was the token policy chosen?"))

        assert "AI answer generation unavailable; used grounded fallback." in resp.warnings
        assert resp.intent == "get_decisions_for_service"
        assert "Token expiry 24h policy" in resp.answer
        assert "Mitigate risk of stolen long-lived tokens" in resp.answer


def test_safe_and_visible_warnings_never_leak_secrets():
    """Requirements 4 & 5: Visible fallback warnings never expose API keys, headers, or raw provider exceptions."""
    secret_key = "AIzaSyD-CONFIDENTIAL-GEMINI-KEY-999"
    mock_provider = MagicMock(spec=GeminiProvider)
    mock_provider.complete.side_effect = [
        Exception(f"Classifier error with Bearer {secret_key}"),
        Exception(f"Synthesis error with key={secret_key}"),
    ]

    mock_evidence = _sample_decision_evidence()
    with patch("weave_brain.agent.orchestrator.get_provider", return_value=mock_provider), patch(
        "weave_brain.agent.orchestrator.get_settings"
    ) as mock_settings, patch("weave_brain.agent.orchestrator.call_tool", return_value=mock_evidence):
        mock_settings.return_value = Settings(
            llm_provider="gemini",
            gemini_api_key=SecretStr(secret_key),
        )
        resp = process_question(ChatRequest(question="Why was the token policy chosen?"))

        assert len(resp.warnings) == 2
        assert "AI classifier unavailable; used deterministic routing." in resp.warnings
        assert "AI answer generation unavailable; used grounded fallback." in resp.warnings

        # Strict credential leak assertions
        for w in resp.warnings:
            assert secret_key not in w
            assert "Bearer" not in w
            assert "AIzaSy" not in w
            assert "key=" not in w


def test_unsupported_decision_citations_trigger_grounded_fallback():
    """Verification that hallucinated decision IDs trigger safe fallback and visible warning."""
    warnings: list[str] = []
    mock_provider = MagicMock(spec=GeminiProvider)
    mock_provider.complete.return_value = "We selected decision:adr-999 because it looked modern."

    mock_evidence = _sample_decision_evidence()
    ans = generate_answer(
        "Why was the token policy chosen?",
        mock_evidence,
        provider=mock_provider,
        tool_name="get_decisions_for_service",
        warnings=warnings,
    )

    assert "AI answer cited unsupported entities; used grounded fallback." in warnings
    assert "Token expiry 24h policy" in ans
    assert "decision:adr-999" not in ans


def test_service_mesh_question_highlighted_paths_and_replacement_evidence_deterministic():
    """Requirement 6: Service-mesh question highlights superseded relationship and presents replacement rationale in deterministic mode."""
    mock_evidence = _sample_decision_evidence()

    with patch("weave_brain.agent.orchestrator.get_settings") as mock_settings, patch(
        "weave_brain.agent.orchestrator.call_tool", return_value=mock_evidence
    ):
        mock_settings.return_value = Settings(llm_provider="deterministic")
        resp = process_question(ChatRequest(question="Why did we not choose service mesh?"))

        # Both the superseded decision and its replacement are highlighted together
        assert len(resp.highlighted_paths) == 1
        assert resp.highlighted_paths[0] == ["decision:adr-002", "decision:adr-003"]

        # Deterministic grounded answer explains the replacement and its rationale
        assert "Service mesh adoption" in resp.answer
        assert "status: `superseded`" in resp.answer
        assert "Envoy proxy standard" in resp.answer
        assert "decision:adr-003" in resp.answer
        assert "Standardize Envoy sidecars" in resp.answer


def test_service_mesh_question_highlighted_paths_with_llm():
    """Requirement 6: Highlighted paths include superseded and replacement decision when LLM is active."""
    mock_provider = MagicMock(spec=GeminiProvider)
    mock_provider.complete.side_effect = [
        '{"tool": "get_decisions_for_service", "service_id": "service:authentication-api"}',
        'Service mesh adoption (decision:adr-002) was superseded by Envoy proxy standard (decision:adr-003): Standardize Envoy sidecars.',
    ]
    mock_evidence = _sample_decision_evidence()

    with patch("weave_brain.agent.orchestrator.get_provider", return_value=mock_provider), patch(
        "weave_brain.agent.orchestrator.get_settings"
    ) as mock_settings, patch("weave_brain.agent.orchestrator.call_tool", return_value=mock_evidence):
        mock_settings.return_value = Settings(
            llm_provider="gemini",
            gemini_api_key=SecretStr("mock-key-secret"),
        )
        resp = process_question(ChatRequest(question="Why did we not choose service mesh?"))

        assert len(resp.highlighted_paths) == 1
        assert resp.highlighted_paths[0] == ["decision:adr-002", "decision:adr-003"]
        assert resp.warnings == []
        assert "decision:adr-002" in resp.answer
        assert "decision:adr-003" in resp.answer


def test_service_mesh_question_prompt_rule_guidance():
    """Requirement 6: Prompt includes rule 8 guiding LLM to mention replacement decision and rationale."""
    assert "8. If a decision is superseded" in ANSWER_SYSTEM
    assert "mention the replacement decision (its title, source_id, and rationale if available)" in ANSWER_SYSTEM


def test_service_mesh_question_when_replacement_rationale_genuinely_absent():
    """Requirement 7: When replacement rationale is genuinely absent, honesty is preserved without inventing facts."""
    evidence_copy = copy.deepcopy(_sample_decision_evidence())
    # Remove rationale from adr-003
    evidence_copy["decisions"][2]["properties"]["rationale"] = ""

    ans = synthesize_grounded_answer(
        "Why did we not choose service mesh?",
        evidence_copy,
        tool_name="get_decisions_for_service",
    )

    assert "Service mesh adoption" in ans
    assert "status: `superseded`" in ans
    assert "Superseded by **Envoy proxy standard** (`decision:adr-003`)." in ans
    # Must NOT invent reasons when rationale is absent
    assert "Standardize Envoy sidecars" not in ans


def test_response_schema_compatibility_and_validation():
    """Requirements 8 & 9: ChatResponse schema remains 100% compliant and deserializable."""
    resp = ChatResponse(
        message_id="test-mid",
        answer="Sample answer",
        warnings=["AI answer generation unavailable; used grounded fallback."],
    )

    dumped = resp.model_dump()
    assert dumped["message_id"] == "test-mid"
    assert dumped["answer"] == "Sample answer"
    assert dumped["warnings"] == ["AI answer generation unavailable; used grounded fallback."]

    # Round-trip validation
    reloaded = ChatResponse.model_validate(dumped)
    assert reloaded.warnings == resp.warnings
