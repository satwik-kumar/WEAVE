"""Unit tests for ReportService, report routes, and onboarding brief contracts."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from weave_brain.api.main import create_app
from weave_brain.core.config import Settings
from weave_brain.domain.models import (
    HealthReport,
    KnowledgeGaps,
    OnboardingBrief,
)
from weave_brain.services.graph_service import AUTH, GraphService, Retrieval
from weave_brain.services.report_service import ReportService


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
    assert client.get("/api/reports/onboarding/not-canonical").status_code == 400


def test_reports_knowledge_gaps_endpoint():
    client = TestClient(create_app(service().settings))
    response = client.get("/api/reports/knowledge-gaps")
    assert response.status_code == 200
    gaps = KnowledgeGaps.model_validate(response.json())
    assert gaps.total_gaps == 5
    assert len(gaps.unowned_services) == 1
    assert len(gaps.decisions_missing_rationale) == 1
    assert len(gaps.undocumented_services) == 3


def test_timeline_order_and_unique_router_registration():
    app = create_app(service().settings)
    client = TestClient(app)
    timeline = client.get(f"/api/services/{AUTH}/decisions").json()
    assert timeline["nodes"][0]["id"] == "decision:adr-003"
    assert timeline["nodes"][-1]["properties"]["status"] == "superseded"
    assert client.get("/api/services/service:unknown/decisions").status_code == 404
    assert client.get("/api/services/invalid-id/decisions").status_code == 400

    paths = [route.path for route in app.routes if hasattr(route, "path")]
    assert len(paths) == len(set(paths))


def test_report_service_direct_unit():
    graph_svc = service()
    report_svc = ReportService(graph_svc)

    health = report_svc.health()
    assert isinstance(health, HealthReport)
    assert health.health_score == 66.7

    gaps = report_svc.gaps()
    assert isinstance(gaps, KnowledgeGaps)
    assert gaps.total_gaps == 5

    decisions = report_svc.decisions(AUTH)
    assert isinstance(decisions, Retrieval)
    assert decisions.nodes[0].id == "decision:adr-003"

    onboarding = report_svc.onboarding(AUTH)
    assert isinstance(onboarding, OnboardingBrief)
    assert onboarding.service_id == AUTH

    with pytest.raises(HTTPException) as exc_info:
        report_svc.onboarding("service:unknown")
    assert exc_info.value.status_code == 404


def test_onboarding_query_parameter_alias():
    client = TestClient(create_app(service().settings))
    resp = client.get(f"/api/reports/onboarding?service_id={AUTH}")
    assert resp.status_code == 200
    brief = OnboardingBrief.model_validate(resp.json())
    assert brief.service_id == AUTH
