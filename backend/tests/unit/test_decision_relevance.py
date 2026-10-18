"""Unit tests for hybrid architectural decision relevance ranking and candidate validation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from weave_brain.agent.answer_generator import (
    generate_answer,
    synthesize_grounded_answer,
)
from weave_brain.agent.orchestrator import process_question
from weave_brain.agent.ranking import (
    extract_topic_terms,
    get_linked_incident,
    get_supersedes_info,
    rank_decision_candidates,
    score_decision_relevance,
    validate_candidate_ids,
)
from weave_brain.domain.models import ChatRequest, GraphEdge, GraphNode, GraphView


def _build_test_decision_evidence() -> dict[str, Any]:
    """Build mock evidence mimicking get_decisions_for_service graph output."""
    adr_001 = {
        "id": "decision:adr-001",
        "type": "decision",
        "title": "Token expiry 24h policy",
        "properties": {
            "status": "accepted",
            "decision_date": "2025-11-15",
            "rationale": "Mitigate risk of stolen long-lived tokens following incident INC-007",
        },
    }
    adr_002 = {
        "id": "decision:adr-002",
        "type": "decision",
        "title": "Service mesh adoption",
        "properties": {
            "status": "superseded",
            "decision_date": "2025-06-01",
            "rationale": "",
        },
    }
    adr_003 = {
        "id": "decision:adr-003",
        "type": "decision",
        "title": "Envoy proxy standard",
        "properties": {
            "status": "accepted",
            "decision_date": "2026-01-20",
            "rationale": "Standardize Envoy sidecars for service-to-service mTLS and observability",
        },
    }
    inc_007 = {
        "id": "incident:inc-007",
        "type": "incident",
        "title": "Stolen long-lived token exploited",
        "properties": {
            "severity": "P1",
            "status": "resolved",
            "summary": "Credential leak via public test script compromised production auth token",
        },
    }
    svc_auth = {
        "id": "service:authentication-api",
        "type": "service",
        "title": "Authentication API",
    }

    edges = [
        {
            "id": "e1",
            "source_id": "decision:adr-001",
            "target_id": "service:authentication-api",
            "relationship_type": "DECIDES_FOR",
        },
        {
            "id": "e2",
            "source_id": "decision:adr-001",
            "target_id": "incident:inc-007",
            "relationship_type": "MOTIVATED_BY",
        },
        {
            "id": "e3",
            "source_id": "decision:adr-002",
            "target_id": "service:authentication-api",
            "relationship_type": "DECIDES_FOR",
        },
        {
            "id": "e4",
            "source_id": "decision:adr-003",
            "target_id": "service:authentication-api",
            "relationship_type": "DECIDES_FOR",
        },
        {
            "id": "e5",
            "source_id": "decision:adr-003",
            "target_id": "decision:adr-002",
            "relationship_type": "SUPERSEDES",
        },
    ]

    return {
        "service_id": "service:authentication-api",
        "decisions": [adr_001, adr_002, adr_003],
        "graph": {
            "nodes": [svc_auth, adr_001, adr_002, adr_003, inc_007],
            "edges": edges,
        },
    }


def test_scenario_1_direct_keyword_match():
    """Scenario 1: Direct keyword match prioritizes ADR-001 and links INC-007."""
    evidence = _build_test_decision_evidence()
    q = "why was the token policy chosen"

    ranked, is_specific, terms = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is True
    assert "token" in terms
    assert len(ranked) == 1
    assert ranked[0]["id"] == "decision:adr-001"

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert "Token expiry 24h policy" in answer
    assert "INC-007" in answer or "inc-007" in answer
    assert "Service mesh" not in answer
    assert "Envoy proxy" not in answer


def test_scenario_2_semantic_paraphrase():
    """Scenario 2: Semantic paraphrase/synonyms match ADR-001."""
    evidence = _build_test_decision_evidence()
    q = "why was 24h credential expiration implemented"

    terms = extract_topic_terms(q)
    assert any(t in terms for t in ("24h", "credential", "expiration", "token"))

    ranked, is_specific, _ = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is True
    assert len(ranked) >= 1
    assert ranked[0]["id"] == "decision:adr-001"

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert "Token expiry 24h policy" in answer
    assert "Mitigate risk of stolen long-lived tokens" in answer


def test_scenario_3_technology_comparison_and_superseding():
    """Scenario 3: Technology comparison prioritizes ADR-003 and explains superseding ADR-002."""
    evidence = _build_test_decision_evidence()
    q = "why was envoy chosen over service mesh"

    ranked, is_specific, _ = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is True
    assert len(ranked) >= 1
    assert ranked[0]["id"] == "decision:adr-003"

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert "Envoy proxy standard" in answer
    assert "Supersedes `decision:adr-002`" in answer


def test_scenario_4_broad_query():
    """Scenario 4: Broad query returns all decisions without dropping any."""
    evidence = _build_test_decision_evidence()
    q = "what architectural decisions exist for authentication"

    ranked, is_specific, _ = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is False
    assert len(ranked) == 3

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert "Token expiry 24h policy" in answer
    assert "Service mesh adoption" in answer
    assert "Envoy proxy standard" in answer


def test_scenario_5_no_matching_decision_uncertainty():
    """Scenario 5: Specific topic with no matching decision reports grounded limitation."""
    evidence = _build_test_decision_evidence()
    q = "why was the oauth policy chosen"

    ranked, is_specific, terms = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is True
    assert len(ranked) == 0
    assert "oauth" in terms

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert (
        "The knowledge graph does not have enough information for this question"
        in answer
    )
    assert "oauth" in answer
    assert "No architectural decisions matching" in answer


def test_scenario_6_superseded_decision():
    """Scenario 6: Querying for an older superseded technology identifies ADR-002 and its replacement."""
    evidence = _build_test_decision_evidence()
    q = "why was service mesh adopted"

    ranked, is_specific, _ = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is True
    assert len(ranked) >= 1
    assert ranked[0]["id"] == "decision:adr-002"

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert "Service mesh adoption" in answer
    assert "status: `superseded`" in answer
    assert "Superseded by" in answer
    assert "decision:adr-003" in answer


def test_scenario_7_multiple_relevant_decisions():
    """Scenario 7: Query touching multiple decisions returns both relevant candidates."""
    evidence = _build_test_decision_evidence()
    q = "what proxy and token decisions were made"

    ranked, is_specific, _ = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is True
    matched_ids = {d["id"] for d in ranked}
    assert "decision:adr-001" in matched_ids
    assert "decision:adr-003" in matched_ids
    assert "decision:adr-002" not in matched_ids

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert "Token expiry 24h policy" in answer
    assert "Envoy proxy standard" in answer
    assert "Service mesh adoption" not in answer


def test_candidate_id_validation_prevents_hallucination():
    """Validation rejects LLM answers citing unsupported canonical decision IDs and falls back."""
    evidence = _build_test_decision_evidence()
    valid_ids = {"decision:adr-001", "decision:adr-002", "decision:adr-003"}

    # Supported citation
    assert (
        validate_candidate_ids(
            "According to decision:adr-001, tokens expire in 24 hours.", valid_ids
        )
        is True
    )

    # Hallucinated decision ID
    assert (
        validate_candidate_ids(
            "Refer to decision:adr-999 and decision:adr-004 for OAuth rules.", valid_ids
        )
        is False
    )

    mock_provider = MagicMock()
    mock_provider.complete.return_value = "We chose OAuth per decision:adr-999."
    res = generate_answer(
        "why was oauth chosen",
        evidence,
        provider=mock_provider,
        tool_name="get_decisions_for_service",
    )
    # Hallucinated candidate ID must trigger fallback to grounded synthesis
    assert "decision:adr-999" not in res
    assert "No architectural decisions matching" in res


def test_elimination_of_substring_false_positives():
    """Correction 1: Word-boundary token matching eliminates substring collisions."""
    evidence = _build_test_decision_evidence()

    # 1. 'gate' must NOT match 'Mitigate' in ADR-001 rationale
    q_gate = "Why was the gate policy chosen?"
    ranked_gate, is_specific_gate, _ = rank_decision_candidates(
        q_gate, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific_gate is True
    assert len(ranked_gate) == 0  # No decision matches gate

    answer_gate = synthesize_grounded_answer(
        q_gate, evidence, tool_name="get_decisions_for_service"
    )
    assert "No architectural decisions matching 'gate' were found" in answer_gate
    assert "Token expiry 24h policy" not in answer_gate

    # 2. 'port' must NOT match 'support'
    decision_with_support = {
        "id": "decision:adr-test",
        "title": "Support protocol",
        "properties": {"status": "accepted", "rationale": "Add support for protocol."},
    }
    score_port = score_decision_relevance(decision_with_support, {"port"})
    assert score_port == 0.0

    # 3. Existing genuine token match continues to work
    score_token = score_decision_relevance(
        evidence["decisions"][0], {"token", "expiry"}
    )
    assert score_token > 0.0


def test_question_framing_and_stop_words():
    """Correction 2: Temporal framing, question particles, and team prepositions separate cleanly."""
    evidence = _build_test_decision_evidence()

    # 1. 'When was the architecture decision made?' must not fail as a no-match
    q_when = "When was the architecture decision made?"
    ranked_when, is_specific_when, _ = rank_decision_candidates(
        q_when, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific_when is False  # Treated as broad query
    assert len(ranked_when) == 3

    answer_when = synthesize_grounded_answer(
        q_when, evidence, tool_name="get_decisions_for_service"
    )
    assert "Architectural decisions for Authentication API" in answer_when
    assert "Token expiry 24h policy" in answer_when

    # 2. 'Why was the policy chosen by the team?' separates framing particles from decision topic
    q_by_team = "Why was the policy chosen by the team?"
    ranked_team, is_specific_team, _ = rank_decision_candidates(
        q_by_team, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific_team is False
    assert len(ranked_team) == 3

    answer_team = synthesize_grounded_answer(
        q_by_team, evidence, tool_name="get_decisions_for_service"
    )
    assert "Architectural decisions for Authentication API" in answer_team
    assert "Token expiry 24h policy" in answer_team


def test_symmetric_synonym_expansion_keys():
    """Correction 2: Bidirectional synonym expansion allows key questions to match token evidence."""
    evidence = _build_test_decision_evidence()

    # 1. 'What key policies exist?'
    q_key_exist = "What key policies exist?"
    ranked_key_exist, is_specific_key, terms = rank_decision_candidates(
        q_key_exist, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific_key is True
    assert "key" in terms
    assert len(ranked_key_exist) >= 1
    assert ranked_key_exist[0]["id"] == "decision:adr-001"

    answer_key_exist = synthesize_grounded_answer(
        q_key_exist, evidence, tool_name="get_decisions_for_service"
    )
    assert "Token expiry 24h policy" in answer_key_exist

    # 2. 'Why was the key policy chosen?'
    q_key_why = "Why was the key policy chosen?"
    ranked_key_why, is_specific_why, _ = rank_decision_candidates(
        q_key_why, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific_why is True
    assert len(ranked_key_why) >= 1
    assert ranked_key_why[0]["id"] == "decision:adr-001"

    answer_key_why = synthesize_grounded_answer(
        q_key_why, evidence, tool_name="get_decisions_for_service"
    )
    assert "Token expiry 24h policy" in answer_key_why


def test_decision_ownership_question():
    """Correction 2: Asking which team chose the token policy prioritizes the specific decision."""
    evidence = _build_test_decision_evidence()
    q = "Which team chose the token policy?"

    ranked, is_specific, terms = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is True
    assert "token" in terms
    assert len(ranked) == 1
    assert ranked[0]["id"] == "decision:adr-001"

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert "Token expiry 24h policy" in answer
    assert "Authentication API (`service:authentication-api`)" in answer


def test_negative_decision_question_superseding_explanation():
    """Correction 4: Querying why a superseded option was not chosen explains superseding decision and rationale."""
    evidence = _build_test_decision_evidence()
    q = "Why did we not choose service mesh?"

    ranked, is_specific, terms = rank_decision_candidates(
        q, evidence["decisions"], graph=evidence["graph"]
    )
    assert is_specific is True
    assert "mesh" in terms
    assert any(d["id"] == "decision:adr-002" for d in ranked)

    answer = synthesize_grounded_answer(
        q, evidence, tool_name="get_decisions_for_service"
    )
    assert "Service mesh adoption" in answer
    assert "status: `superseded`" in answer
    # Must explain that it was superseded by Envoy proxy standard and include its rationale
    assert "Superseded by **Envoy proxy standard** (`decision:adr-003`)" in answer
    assert "Standardize Envoy sidecars" in answer


def test_discrete_highlighted_paths_in_chat_response():
    """Correction 3: Discrete graph paths survive into ChatResponse and are not flattened into one sequence."""
    mock_result = _build_test_decision_evidence()
    with patch("weave_brain.agent.orchestrator.call_tool", return_value=mock_result):
        resp = process_question(ChatRequest(question="why was the token policy chosen"))

        assert resp.intent == "get_decisions_for_service"
        assert len(resp.highlighted_paths) == 1
        # Discrete path representing the MOTIVATED_BY relationship: [decision, incident]
        assert resp.highlighted_paths[0] == ["decision:adr-001", "incident:inc-007"]

        # Ensure node flags are set
        hl_nodes = {n.id for n in resp.graph.nodes if n.on_highlighted_path}
        assert "decision:adr-001" in hl_nodes
        assert "incident:inc-007" in hl_nodes

        # Serialization test: ChatResponse survives dict/model dump
        data = resp.model_dump()
        assert data["highlighted_paths"] == [["decision:adr-001", "incident:inc-007"]]


def test_candidate_validation_boundary_informal_citations():
    """Correction 5: Candidate validator enforces canonical decision:<id> format but does not catch informal prose citations."""
    valid_ids = {"decision:adr-001", "decision:adr-002", "decision:adr-003"}

    # Canonical fake ID is caught
    assert (
        validate_candidate_ids("See decision:adr-999 for details.", valid_ids) is False
    )

    # Canonical valid ID passes
    assert (
        validate_candidate_ids("See decision:adr-001 for details.", valid_ids) is True
    )

    # Boundary limitation: informal citations without the 'decision:' prefix are not caught by this pattern
    assert validate_candidate_ids("We follow ADR-999 guidelines.", valid_ids) is True
    assert validate_candidate_ids("Refer to Decision 42.", valid_ids) is True


def test_typed_graph_view_compatibility():
    """Correction 6: get_linked_incident and get_supersedes_info support typed GraphView, GraphNode, and GraphEdge."""
    node_d1 = GraphNode(
        id="decision:adr-001",
        type="decision",
        title="Token policy",
        properties={},
    )
    node_inc = GraphNode(
        id="incident:inc-007",
        type="incident",
        title="Auth leak",
        properties={"summary": "Token compromised."},
    )
    node_d2 = GraphNode(
        id="decision:adr-002",
        type="decision",
        title="Mesh",
        properties={},
    )
    node_d3 = GraphNode(
        id="decision:adr-003",
        type="decision",
        title="Envoy",
        properties={},
    )

    edges = [
        GraphEdge(
            id="e1",
            source_id="decision:adr-001",
            target_id="incident:inc-007",
            relationship_type="MOTIVATED_BY",
            label="MOTIVATED_BY",
        ),
        GraphEdge(
            id="e2",
            source_id="decision:adr-003",
            target_id="decision:adr-002",
            relationship_type="SUPERSEDES",
            label="SUPERSEDES",
        ),
    ]

    typed_graph = GraphView(
        nodes=[node_d1, node_inc, node_d2, node_d3],
        edges=edges,
    )

    # Test incident retrieval with typed GraphView
    inc = get_linked_incident(node_d1, graph=typed_graph)
    assert inc is not None
    assert (inc.id if hasattr(inc, "id") else inc.get("id")) == "incident:inc-007"

    # Test supersedes info with typed GraphView
    older_id, newer_id = get_supersedes_info(node_d3, graph=typed_graph)
    assert older_id == "decision:adr-002"
    assert newer_id is None

    older_id_2, newer_id_2 = get_supersedes_info(node_d2, graph=typed_graph)
    assert older_id_2 is None
    assert newer_id_2 == "decision:adr-003"
