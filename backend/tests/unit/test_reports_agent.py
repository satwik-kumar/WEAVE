"""Reports, bounded model tools, provider failures and grounding checks."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from weave_brain.agent.orchestrator import process_question
from weave_brain.agent.providers import ModelProvider, ProviderError, ProviderState
from weave_brain.agent.tools import execute_tool
from weave_brain.api.main import create_app
from weave_brain.core.config import Settings
from weave_brain.domain.models import ChatRequest, HealthReport, OnboardingBrief
from weave_brain.services.graph_service import AUTH, GraphService


def service():
    return GraphService(Settings(_env_file=None, development_fixtures=True))


def test_health_gaps_and_onboarding_contracts():
    client = TestClient(create_app(service().settings))
    report = HealthReport.model_validate(client.get("/api/reports/health-score").json())
    assert report.metrics.services_owned == 0.75
    assert report.metrics.decisions_rationale == 0.67
    assert report.gaps.unowned_services[0].id == "service:data-pipeline"
    assert report.gaps.decisions_missing_rationale[0].id == "decision:adr-002"
    assert report.health_score == 66.7
    assert report.warnings
    brief = OnboardingBrief.model_validate(
        client.get(f"/api/reports/onboarding/{AUTH}").json()
    )
    assert {n.id for n in brief.top_experts} == {
        "person:priya-sharma",
        "person:james-chen",
    }
    assert len(brief.key_decisions) == 2
    assert all(
        "decision:adr-002" != e.relationship_path[0] for e in brief.key_decisions
    )
    assert not brief.open_incidents
    assert brief.related_tickets[0].id == "ticket:eng-042"
    empty = client.get("/api/reports/onboarding/service:data-pipeline")
    assert empty.status_code == 200 and "No owning team" in empty.json()["overview"]
    assert client.get("/api/reports/onboarding/service:unknown").status_code == 404


def test_timeline_order_and_unique_router_registration():
    app = create_app(service().settings)
    client = TestClient(app)
    timeline = client.get(f"/api/services/{AUTH}/decisions").json()
    assert timeline["nodes"][0]["id"] == "decision:adr-003"
    assert timeline["nodes"][-1]["properties"]["status"] == "superseded"
    paths = [route.path for route in app.routes if hasattr(route, "path")]
    assert len(paths) == len(set(paths))


def test_experts_have_real_project_evidence_and_impact_never_fabricates_tests():
    graph_service = service()
    experts = execute_tool(
        "find_experts", json.dumps({"entity_id": AUTH}), graph_service
    )
    for evidence in experts.evidence:
        assert "project:auth-modernization" in evidence.relationship_path
        assert evidence.relationship_path[-1] == AUTH
        assert evidence.source_id not in ("person:priya-sharma", "person:james-chen")
    impact = execute_tool(
        "change_impact", json.dumps({"entity_id": AUTH}), graph_service
    )
    assert not any(n.type in ("file", "test") for n in impact.graph.nodes)
    assert any(n.id == "ticket:eng-042" for n in impact.related_entities)
    with pytest.raises(ValueError):
        execute_tool("execute_cypher", "{}", graph_service)
    with pytest.raises(ValueError):
        execute_tool(
            "service_overview",
            json.dumps({"entity_id": AUTH, "cypher": "MATCH"}),
            graph_service,
        )


def provider_settings(**kwargs):
    return Settings(
        _env_file=None,
        development_fixtures=True,
        chat_mode="agent",
        llm_api_key="test-only-key",
        llm_model="test-model",
        **kwargs,
    )


def test_openai_actual_http_adapter_and_agent_citation_roundtrip():
    requests = []

    def mock(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["store"] is False
        assert all(
            tool["strict"] and tool["parameters"]["additionalProperties"] is False
            for tool in payload["tools"]
        )
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "c1",
                            "name": "service_overview",
                            "arguments": json.dumps({"entity_id": AUTH}),
                        }
                    ]
                },
            )
        assert payload["input"][-1]["type"] == "function_call_output"
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Platform Engineering owns service:authentication-api. [S5]",
                            }
                        ],
                    }
                ]
            },
        )

    settings = provider_settings()
    response = process_question(
        ChatRequest(question="Who owns authentication?"),
        GraphService(settings),
        ModelProvider(settings, httpx.MockTransport(mock)),
    )
    assert response.graph and response.evidence and response.suggested_followups
    assert response.answer.endswith("[S5]")
    assert len(requests) == 2


@pytest.mark.parametrize(
    "answer", ["Uncited invented claim.", "Claim [S999]", "service:invented [S1]"]
)
def test_agent_rejects_missing_invalid_citations_and_unknown_entities(answer):
    calls = 0

    def mock(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "c1",
                            "name": "service_overview",
                            "arguments": json.dumps({"entity_id": AUTH}),
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": answer}],
                    }
                ]
            },
        )

    settings = provider_settings()
    with pytest.raises(ProviderError):
        process_question(
            ChatRequest(question="auth"),
            GraphService(settings),
            ModelProvider(settings, httpx.MockTransport(mock)),
        )


def test_provider_failure_is_503_without_retrieval_fallback(monkeypatch):
    def failed(*_args, **_kwargs):
        raise ProviderError("Provider temporarily unavailable.")

    monkeypatch.setattr(ModelProvider, "turn", failed)
    client = TestClient(create_app(provider_settings()))
    response = client.post("/api/chat", json={"question": "Who owns authentication?"})
    assert response.status_code == 503 and "answer" not in response.json()
    missing = TestClient(
        create_app(
            Settings(_env_file=None, chat_mode="agent", development_fixtures=True)
        )
    )
    assert missing.post("/api/chat", json={"question": "auth"}).status_code == 503


def test_gemini_stateless_wire_protocol():
    def mock(request):
        payload = json.loads(request.content)
        assert payload["input"][0]["type"] == "user_input"
        assert payload["store"] is False
        return httpx.Response(
            200,
            json={
                "steps": [
                    {
                        "type": "function_call",
                        "id": "g1",
                        "name": "find_experts",
                        "arguments": {"entity_id": AUTH},
                    }
                ]
            },
        )

    settings = provider_settings(llm_provider="gemini")
    provider = ModelProvider(settings, httpx.MockTransport(mock))
    reply = provider.turn(
        ProviderState(
            items=[
                {
                    "type": "user_input",
                    "content": [{"type": "text", "text": "Who knows auth?"}],
                }
            ]
        ),
        first=True,
    )
    state = provider.add_result(reply.state, reply.calls[0], "verified result")
    assert state.items[-1]["type"] == "function_result"
    assert state.items[-1]["call_id"] == "g1"


def test_runaway_model_tool_calls_are_bounded():
    def mock(_request):
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "repeat",
                        "name": "service_overview",
                        "arguments": json.dumps({"entity_id": AUTH}),
                    }
                ]
            },
        )

    settings = provider_settings()
    with pytest.raises(ProviderError, match="budget"):
        process_question(
            ChatRequest(question="auth"),
            GraphService(settings),
            ModelProvider(settings, httpx.MockTransport(mock)),
        )


@pytest.mark.parametrize("provider_name", ["gemini", "anthropic"])
def test_other_provider_full_tool_roundtrip(provider_name):
    calls = 0

    def mock(request):
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        if provider_name == "gemini":
            if calls == 1:
                assert payload["generation_config"]["tool_choice"] == "any"
                return httpx.Response(
                    200,
                    json={
                        "steps": [
                            {
                                "type": "function_call",
                                "id": "c1",
                                "name": "service_overview",
                                "arguments": {"entity_id": AUTH},
                            }
                        ]
                    },
                )
            assert payload["input"][-1]["type"] == "function_result"
            return httpx.Response(
                200,
                json={
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Platform Engineering owns authentication. [S5]",
                                }
                            ],
                        }
                    ]
                },
            )
        if calls == 1:
            assert payload["messages"][0]["role"] == "user"
            return httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "c1",
                            "name": "service_overview",
                            "input": {"entity_id": AUTH},
                        }
                    ]
                },
            )
        assert payload["messages"][-1]["content"][0]["type"] == "tool_result"
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": "Platform Engineering owns authentication. [S5]",
                    }
                ]
            },
        )

    settings = provider_settings(llm_provider=provider_name)
    response = process_question(
        ChatRequest(question="Who owns authentication?"),
        GraphService(settings),
        ModelProvider(settings, httpx.MockTransport(mock)),
    )
    assert response.evidence and response.graph and calls == 2
