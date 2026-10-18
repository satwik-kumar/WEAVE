"""Live integration tests for core FalkorDB queries, mapper, and health score."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

from weave_brain.domain.models import GraphView, SourceArtifact
from weave_brain.graph.client import get_graph
from weave_brain.graph.mapper import to_evidence_items, to_graph_view
from weave_brain.graph.queries import (
    find_experts,
    find_shortest_path,
    get_blast_radius,
    get_decisions_for_service,
    get_health_score,
    get_knowledge_gaps,
    get_neighborhood,
    get_service_dependents,
    get_service_overview,
    search_entities,
)
from weave_brain.graph.schema import init_schema
from weave_brain.graph.writer import upsert_many

pytestmark = pytest.mark.skipif(
    os.getenv("FALKORDB_AVAILABLE") != "1",
    reason="Live FalkorDB container required (FALKORDB_AVAILABLE != 1)",
)


@pytest.fixture(scope="module")
def seeded_graph():
    """Create isolated test graph, initialize schema, and seed frozen demo artifacts."""
    graph = get_graph()
    try:
        graph.query("RETURN 1")
    except (RedisConnectionError, ConnectionError, OSError) as e:
        pytest.skip(f"FalkorDB unavailable at configured endpoint: {e}")

    try:
        graph.delete()
    except (ResponseError, RedisConnectionError):
        pass

    init_schema(graph)

    now = datetime.now(UTC)
    artifacts: list[SourceArtifact] = [
        # Repositories & Documents
        SourceArtifact(
            source_id="repo-1",
            source_type="git",
            entity_type="repository",
            canonical_id="repository:acme/auth-api",
            title="acme/auth-api",
            properties={
                "url": "https://github.com/acme/auth-api",
                "language": "Python",
            },
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="doc-1",
            source_type="confluence",
            entity_type="document",
            canonical_id="document:auth-runbook",
            title="Auth Service Operations Runbook",
            properties={
                "source_url": "https://wiki.acme.internal/docs/auth-runbook",
                "content_excerpt": "Emergency token rotation procedures",
            },
            relationships=[("DOCUMENTS", "service:authentication-api")],
            ingested_at=now,
        ),
        # Incidents & Tickets
        SourceArtifact(
            source_id="inc-1",
            source_type="pagerduty",
            entity_type="incident",
            canonical_id="incident:inc-007",
            title="Stolen long-lived token exploited",
            properties={
                "severity": "P1",
                "status": "resolved",
                "summary": "Credential leak",
            },
            relationships=[("AFFECTS", "service:authentication-api")],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="tick-1",
            source_type="jira",
            entity_type="ticket",
            canonical_id="ticket:eng-042",
            title="Rotate legacy signing keys",
            properties={"priority": "high", "status": "in_progress"},
            relationships=[("AFFECTS", "service:authentication-api")],
            ingested_at=now,
        ),
        # Services
        SourceArtifact(
            source_id="svc-1",
            source_type="catalog",
            entity_type="service",
            canonical_id="service:authentication-api",
            title="Authentication API",
            properties={
                "status": "production",
                "language": "Python",
                "tech_stack": "FastAPI, Redis",
            },
            relationships=[("IMPLEMENTED_IN", "repository:acme/auth-api")],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="svc-2",
            source_type="catalog",
            entity_type="service",
            canonical_id="service:user-profile-api",
            title="User Profile API",
            properties={"status": "production"},
            relationships=[("DEPENDS_ON", "service:authentication-api")],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="svc-3",
            source_type="catalog",
            entity_type="service",
            canonical_id="service:notification-service",
            title="Notification Service",
            properties={"status": "production"},
            relationships=[("DEPENDS_ON", "service:authentication-api")],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="svc-4",
            source_type="catalog",
            entity_type="service",
            canonical_id="service:data-pipeline",
            title="Data Pipeline",
            properties={"status": "active"},
            # Intentionally no OWNS relationship (gap)
            ingested_at=now,
        ),
        # Teams
        SourceArtifact(
            source_id="team-1",
            source_type="hr",
            entity_type="team",
            canonical_id="team:platform-engineering",
            title="Platform Engineering",
            properties={"slack_channel": "#platform-eng"},
            relationships=[
                ("OWNS", "service:authentication-api"),
                ("OWNS", "service:notification-service"),
            ],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="team-2",
            source_type="hr",
            entity_type="team",
            canonical_id="team:backend-core",
            title="Backend Core",
            properties={"slack_channel": "#backend"},
            relationships=[("OWNS", "service:user-profile-api")],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="team-3",
            source_type="hr",
            entity_type="team",
            canonical_id="team:data-infra",
            title="Data Infra",
            properties={"slack_channel": "#data-infra"},
            ingested_at=now,
        ),
        # Projects
        SourceArtifact(
            source_id="proj-1",
            source_type="jira",
            entity_type="project",
            canonical_id="project:auth-modernization",
            title="Auth Modernization",
            properties={"status": "active"},
            relationships=[("USES", "service:authentication-api")],
            ingested_at=now,
        ),
        # People
        SourceArtifact(
            source_id="usr-1",
            source_type="hr",
            entity_type="person",
            canonical_id="person:priya-sharma",
            title="Priya Sharma",
            properties={"role": "Lead", "email": "priya@acme.internal"},
            relationships=[
                ("MEMBER_OF", "team:platform-engineering"),
                ("WORKED_ON", "project:auth-modernization"),
            ],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="usr-2",
            source_type="hr",
            entity_type="person",
            canonical_id="person:james-chen",
            title="James Chen",
            properties={"role": "Senior Engineer", "email": "james@acme.internal"},
            relationships=[
                ("MEMBER_OF", "team:platform-engineering"),
                ("WORKED_ON", "project:auth-modernization"),
            ],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="usr-3",
            source_type="hr",
            entity_type="person",
            canonical_id="person:aisha-kowalski",
            title="Aisha Kowalski",
            properties={"role": "Engineer"},
            relationships=[("MEMBER_OF", "team:backend-core")],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="usr-4",
            source_type="hr",
            entity_type="person",
            canonical_id="person:dev-four",
            title="Dev Four",
            properties={"role": "Engineer"},
            relationships=[("MEMBER_OF", "team:data-infra")],
            ingested_at=now,
        ),
        # Decisions
        SourceArtifact(
            source_id="dec-1",
            source_type="adr",
            entity_type="decision",
            canonical_id="decision:adr-001",
            title="Token expiry 24h policy",
            properties={
                "status": "accepted",
                "rationale": "Mitigate token theft risks",
            },
            relationships=[
                ("DECIDES_FOR", "service:authentication-api"),
                ("MOTIVATED_BY", "incident:inc-007"),
            ],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="dec-2",
            source_type="adr",
            entity_type="decision",
            canonical_id="decision:adr-002",
            title="Service mesh adoption",
            properties={
                "status": "accepted",
                "rationale": "",
            },  # Intentionally empty rationale
            relationships=[("DECIDES_FOR", "service:authentication-api")],
            ingested_at=now,
        ),
        SourceArtifact(
            source_id="dec-3",
            source_type="adr",
            entity_type="decision",
            canonical_id="decision:adr-003",
            title="Envoy proxy standard",
            properties={
                "status": "accepted",
                "rationale": "Standardize Envoy sidecars",
            },
            relationships=[
                ("DECIDES_FOR", "service:authentication-api"),
                ("SUPERSEDES", "decision:adr-002"),
            ],
            ingested_at=now,
        ),
    ]

    report = upsert_many(artifacts, graph=graph, source_name="demo_seed")
    assert report.records_processed == len(artifacts)
    assert len(report.errors) == 0

    yield graph

    try:
        graph.delete()
    except (ResponseError, RedisConnectionError):
        pass


def test_get_service_overview_live(seeded_graph):
    """Test get_service_overview returns expected connections and maps to GraphView."""
    overview = get_service_overview("service:authentication-api", graph=seeded_graph)
    assert overview is not None
    assert overview["service"]["id"] == "service:authentication-api"
    assert overview["team"]["id"] == "team:platform-engineering"
    assert len(overview["repositories"]) == 1
    assert overview["repositories"][0]["id"] == "repository:acme/auth-api"
    assert len(overview["decisions"]) >= 2
    assert "service:user-profile-api" in overview["dependents"]
    assert "service:notification-service" in overview["dependents"]

    # Verify mapper conversion
    gv = to_graph_view(overview)
    assert isinstance(gv, GraphView)
    assert len(gv.nodes) >= 5
    assert len(gv.edges) >= 4

    evidence = to_evidence_items(overview)
    assert len(evidence) >= 2


def test_get_decisions_for_service_live(seeded_graph):
    """Test decisions retrieval and automatic marking of superseded status."""
    res = get_decisions_for_service("service:authentication-api", graph=seeded_graph)
    decision_ids = [d["id"] for d in res["decisions"]]
    assert "decision:adr-001" in decision_ids
    assert "decision:adr-002" in decision_ids
    assert "decision:adr-003" in decision_ids

    # Piping to to_graph_view must detect incoming SUPERSEDES and mark adr-002 as superseded
    gv = to_graph_view(res)
    node_map = {n.id: n for n in gv.nodes}
    assert node_map["decision:adr-002"].properties["status"] == "superseded"
    assert node_map["decision:adr-003"].properties["status"] == "accepted"


def test_get_blast_radius_live(seeded_graph):
    """Test reverse DEPENDS_ON traversal for blast radius calculation."""
    res = get_blast_radius(
        "service:authentication-api", max_depth=3, graph=seeded_graph
    )
    affected_ids = [s["id"] for s in res["affected_services"]]
    assert "service:user-profile-api" in affected_ids
    assert "service:notification-service" in affected_ids
    assert len(res["graph"]["highlighted_path_ids"]) >= 2

    gv = to_graph_view(res)
    assert isinstance(gv, GraphView)
    for n in gv.nodes:
        assert n.on_highlighted_path is True


def test_find_experts_live(seeded_graph):
    """Test finding experts connected via projects and team ownership."""
    experts = find_experts("service:authentication-api", graph=seeded_graph)
    expert_ids = [e["id"] for e in experts]
    assert "person:priya-sharma" in expert_ids
    assert "person:james-chen" in expert_ids
    priya = next(e for e in experts if e["id"] == "person:priya-sharma")
    assert "project:auth-modernization" in priya["properties"]["worked_on"]


def test_get_neighborhood_live(seeded_graph):
    """Test 2-hop graph neighborhood retrieval centered on service."""
    res = get_neighborhood("service:authentication-api", depth=2, graph=seeded_graph)
    gv = to_graph_view(res)
    assert len(gv.nodes) >= 6
    assert len(gv.edges) >= 5
    assert gv.root_node_ids == ["service:authentication-api"]


def test_find_shortest_path_live(seeded_graph):
    """Test path discovery from engineer to code repository."""
    res = find_shortest_path(
        "person:priya-sharma", "repository:acme/auth-api", graph=seeded_graph
    )
    assert res["path_found"] is True
    node_ids = [n["id"] for n in res["nodes"]]
    assert "person:priya-sharma" in node_ids
    assert "service:authentication-api" in node_ids
    assert "repository:acme/auth-api" in node_ids
    assert len(res["edges"]) >= 2


def test_get_knowledge_gaps_and_health_score_live(seeded_graph):
    """Test detection of gaps and computation of 4 health metrics."""
    gaps = get_knowledge_gaps(graph=seeded_graph)
    unowned_ids = [s["id"] for s in gaps["unowned_services"]]
    assert "service:data-pipeline" in unowned_ids

    missing_rat_ids = [d["id"] for d in gaps["decisions_missing_rationale"]]
    assert "decision:adr-002" in missing_rat_ids

    health = get_health_score(graph=seeded_graph)
    assert 0.0 <= health["health_score"] <= 100.0
    assert health["metrics"]["services_owned"] == 0.75  # 3 of 4 services owned
    assert (
        health["metrics"]["decisions_rationale"] == 0.67
    )  # 2 of 3 decisions have rationale
    assert health["metrics"]["incidents_resolved"] == 1.0  # 1 of 1 resolved


def test_get_service_dependents_and_search_live(seeded_graph):
    """Test API helper queries for service dependents and case-insensitive search."""
    deps = get_service_dependents("service:authentication-api", graph=seeded_graph)
    dep_ids = [d["id"] for d in deps]
    assert "service:user-profile-api" in dep_ids
    assert "service:notification-service" in dep_ids

    search_res = search_entities("auth", graph=seeded_graph)
    search_ids = [r["id"] for r in search_res]
    assert "service:authentication-api" in search_ids
    assert "project:auth-modernization" in search_ids
    assert "document:auth-runbook" in search_ids
