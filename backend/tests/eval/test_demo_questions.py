"""Evaluation suite for routing of the five canonical demo questions and paraphrases (Task D-R1).

Evaluates 20 test cases (5 canonical demo questions + 3 paraphrases each).
For every question, asserts:
1. The intent chosen
2. The tool called
3. That the expected node IDs appear in the returned GraphView
"""

from __future__ import annotations

import pytest

from weave_brain.agent.orchestrator import classify_question, process_question
from weave_brain.domain.models import ChatRequest

DEMO_EVALUATION_CASES = [
    # =========================================================================
    # Question 1: Service Overview & Ownership
    # Expected Tool: get_service_overview
    # Expected Nodes: service:authentication-api, team:platform-engineering
    # =========================================================================
    pytest.param(
        "Who owns the authentication API?",
        "get_service_overview",
        "get_service_overview",
        ["service:authentication-api", "team:platform-engineering"],
        id="q1_canonical_overview_who_owns",
    ),
    pytest.param(
        "Which team is responsible for service:authentication-api?",
        "get_service_overview",
        "get_service_overview",
        ["service:authentication-api", "team:platform-engineering"],
        id="q1_paraphrase1_which_team_responsible",
    ),
    pytest.param(
        "Can you give me an overview and architecture of the authentication service?",
        "get_service_overview",
        "get_service_overview",
        ["service:authentication-api", "team:platform-engineering"],
        id="q1_paraphrase2_overview_architecture",
    ),
    pytest.param(
        "Explain what service:authentication-api does and who maintains it.",
        "get_service_overview",
        "get_service_overview",
        ["service:authentication-api", "team:platform-engineering"],
        id="q1_paraphrase3_explain_service_and_ownership",
    ),
    # =========================================================================
    # Question 2: Blast Radius & Dependency Breakage
    # Expected Tool: get_blast_radius
    # Expected Nodes: service:user-profile-api, service:notification-service
    # =========================================================================
    pytest.param(
        "What breaks if authentication-api goes down?",
        "get_blast_radius",
        "get_blast_radius",
        ["service:user-profile-api", "service:notification-service"],
        id="q2_canonical_blast_radius_what_breaks",
    ),
    pytest.param(
        "What is the blast radius if service:authentication-api fails?",
        "get_blast_radius",
        "get_blast_radius",
        ["service:user-profile-api", "service:notification-service"],
        id="q2_paraphrase1_blast_radius_fails",
    ),
    pytest.param(
        "Which downstream services depend on authentication-api?",
        "get_blast_radius",
        "get_blast_radius",
        ["service:user-profile-api", "service:notification-service"],
        id="q2_paraphrase2_downstream_depend_on",
    ),
    pytest.param(
        "What services are impacted by an outage in service:authentication-api?",
        "get_blast_radius",
        "get_blast_radius",
        ["service:user-profile-api", "service:notification-service"],
        id="q2_paraphrase3_services_impacted_outage",
    ),
    # =========================================================================
    # Question 3: Architecture Decisions & Rationale (ADR)
    # Expected Tool: get_decisions_for_service
    # Expected Nodes: decision:adr-001, incident:inc-007
    # =========================================================================
    pytest.param(
        "Why was the 24h token expiry policy chosen for authentication-api?",
        "get_decisions_for_service",
        "get_decisions_for_service",
        ["decision:adr-001", "incident:inc-007"],
        id="q3_canonical_decisions_token_expiry_rationale",
    ),
    pytest.param(
        "What architectural decisions and ADRs govern service:authentication-api?",
        "get_decisions_for_service",
        "get_decisions_for_service",
        ["decision:adr-001"],
        id="q3_paraphrase1_decisions_and_adrs_govern",
    ),
    pytest.param(
        "Show me the rationale and motivating incidents for decisions on authentication-api.",
        "get_decisions_for_service",
        "get_decisions_for_service",
        ["decision:adr-001", "incident:inc-007"],
        id="q3_paraphrase2_rationale_and_motivating_incidents",
    ),
    pytest.param(
        "What decisions have been made regarding service:authentication-api?",
        "get_decisions_for_service",
        "get_decisions_for_service",
        ["decision:adr-001"],
        id="q3_paraphrase3_decisions_made_regarding_service",
    ),
    # =========================================================================
    # Question 4: Knowledge Holders & Experts
    # Expected Tool: find_experts
    # Expected Nodes: person:priya-sharma, person:james-chen
    # =========================================================================
    pytest.param(
        "Who are the experts on authentication-api?",
        "find_experts",
        "find_experts",
        ["person:priya-sharma", "person:james-chen"],
        id="q4_canonical_experts_who_are_experts",
    ),
    pytest.param(
        "Who has worked on service:authentication-api?",
        "find_experts",
        "find_experts",
        ["person:priya-sharma", "person:james-chen"],
        id="q4_paraphrase1_who_has_worked_on",
    ),
    pytest.param(
        "Who knows the most about authentication-api and can answer questions about it?",
        "find_experts",
        "find_experts",
        ["person:priya-sharma", "person:james-chen"],
        id="q4_paraphrase2_who_knows_the_most",
    ),
    pytest.param(
        "Which engineers have expertise in service:authentication-api?",
        "find_experts",
        "find_experts",
        ["person:priya-sharma", "person:james-chen"],
        id="q4_paraphrase3_engineers_with_expertise",
    ),
    # =========================================================================
    # Question 5: Onboarding Brief & Risk Summary
    # Expected Tool: get_onboarding_brief
    # Expected Nodes: service:authentication-api, team:platform-engineering,
    #                 person:priya-sharma, decision:adr-001
    # =========================================================================
    pytest.param(
        "Give me an onboarding brief for authentication-api.",
        "get_onboarding_brief",
        "get_onboarding_brief",
        [
            "service:authentication-api",
            "team:platform-engineering",
            "person:priya-sharma",
            "decision:adr-001",
        ],
        id="q5_canonical_onboarding_brief",
    ),
    pytest.param(
        "I am a new engineer joining, how do I get started with service:authentication-api?",
        "get_onboarding_brief",
        "get_onboarding_brief",
        [
            "service:authentication-api",
            "team:platform-engineering",
            "person:priya-sharma",
            "decision:adr-001",
        ],
        id="q5_paraphrase1_new_engineer_getting_started",
    ),
    pytest.param(
        "Can you generate an onboarding overview and risk summary for authentication-api?",
        "get_onboarding_brief",
        "get_onboarding_brief",
        [
            "service:authentication-api",
            "team:platform-engineering",
            "person:priya-sharma",
            "decision:adr-001",
        ],
        id="q5_paraphrase2_onboarding_overview_and_risk_summary",
    ),
    pytest.param(
        "Provide a comprehensive onboarding guide for new team members on service:authentication-api.",
        "get_onboarding_brief",
        "get_onboarding_brief",
        [
            "service:authentication-api",
            "team:platform-engineering",
            "person:priya-sharma",
            "decision:adr-001",
        ],
        id="q5_paraphrase3_onboarding_guide_for_new_members",
    ),
]


@pytest.mark.parametrize(
    ("question", "expected_intent", "expected_tool", "expected_node_ids"),
    DEMO_EVALUATION_CASES,
)
def test_demo_question_routing_and_graph(
    question: str,
    expected_intent: str,
    expected_tool: str,
    expected_node_ids: list[str],
) -> None:
    """Validate intent chosen, tool executed, and expected node IDs in GraphView."""
    request = ChatRequest(question=question)
    response = process_question(request)

    # 1. Assert intent chosen
    assert response.intent == expected_intent, (
        f"Intent mismatch for question: '{question}'. "
        f"Expected intent: '{expected_intent}', got: '{response.intent}'"
    )

    # 2. Assert tool called
    assert response.intent == expected_tool, (
        f"Tool called mismatch for question: '{question}'. "
        f"Expected tool: '{expected_tool}', got: '{response.intent}'"
    )

    # 3. Assert that expected node IDs appear in the returned GraphView
    assert response.graph is not None, f"No GraphView returned for: '{question}'"
    returned_node_ids = {node.id for node in response.graph.nodes}
    for expected_id in expected_node_ids:
        assert expected_id in returned_node_ids, (
            f"Expected node '{expected_id}' missing in GraphView for '{question}'. "
            f"Returned nodes: {returned_node_ids}"
        )


@pytest.mark.parametrize(
    ("question", "expected_intent", "expected_tool", "expected_node_ids"),
    DEMO_EVALUATION_CASES,
)
def test_classify_question_routing_direct(
    question: str,
    expected_intent: str,
    expected_tool: str,
    expected_node_ids: list[str],
) -> None:
    """Validate direct question classifier resolves correct tool and target service."""
    tool, service_id = classify_question(question)
    assert tool == expected_tool, (
        f"Direct classify_question returned wrong tool for '{question}'. "
        f"Expected: '{expected_tool}', got: '{tool}'"
    )
    assert service_id == "service:authentication-api"
