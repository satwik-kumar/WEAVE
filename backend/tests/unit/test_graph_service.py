"""Unit tests for GraphService and bounded graph views."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from weave_brain.core.config import Settings
from weave_brain.domain.models import GraphEdge, GraphNode, GraphView
from weave_brain.graph.client import ConfigurationError
from weave_brain.services.graph_service import (
    AUTH,
    BlastRadius,
    GraphService,
    Retrieval,
    ServiceOverview,
    ShortestPath,
    bounded_view,
    clean_graph,
)


def test_bounded_view_truncation_to_100_nodes() -> None:
    nodes = [
        {
            "id": f"service:svc-{i:03d}",
            "type": "service",
            "title": f"Service {i}",
            "properties": {},
        }
        for i in range(120)
    ]
    raw = {
        "nodes": nodes,
        "edges": [],
        "root_node_ids": ["service:svc-001"],
    }
    view = bounded_view(raw)
    assert len(view.nodes) == 100
    assert view.truncated is True
    assert view.warning is not None
    assert "Graph limited to 100 nodes." in view.warning
    assert "service:svc-001" in [n.id for n in view.nodes]


def test_bounded_view_dangling_edge_removal() -> None:
    raw = {
        "nodes": [
            {
                "id": "service:svc-a",
                "type": "service",
                "title": "Service A",
                "properties": {},
            },
            {
                "id": "service:svc-b",
                "type": "service",
                "title": "Service B",
                "properties": {},
            },
        ],
        "edges": [
            {
                "id": "service:svc-a::DEPENDS_ON::service:svc-b",
                "source_id": "service:svc-a",
                "target_id": "service:svc-b",
                "relationship_type": "DEPENDS_ON",
                "label": "DEPENDS_ON",
            },
            {
                "id": "service:svc-b::DEPENDS_ON::service:svc-missing",
                "source_id": "service:svc-b",
                "target_id": "service:svc-missing",
                "relationship_type": "DEPENDS_ON",
                "label": "DEPENDS_ON",
            },
        ],
    }
    view = bounded_view(raw)
    assert len(view.nodes) == 2
    assert len(view.edges) == 1
    assert view.edges[0].source_id == "service:svc-a"
    assert view.edges[0].target_id == "service:svc-b"
    assert view.warning is not None
    assert "Edges with missing endpoints omitted." in view.warning


def test_clean_graph_filters_dangling_edges() -> None:
    view = GraphView(
        nodes=[
            GraphNode(id="service:a", type="service", title="A"),
            GraphNode(id="service:b", type="service", title="B"),
        ],
        edges=[
            GraphEdge(
                id="service:a::DEPENDS_ON::service:b",
                source_id="service:a",
                target_id="service:b",
                relationship_type="DEPENDS_ON",
                label="DEPENDS_ON",
            ),
            GraphEdge(
                id="service:a::DEPENDS_ON::service:ghost",
                source_id="service:a",
                target_id="service:ghost",
                relationship_type="DEPENDS_ON",
                label="DEPENDS_ON",
            ),
        ],
        root_node_ids=["service:a", "service:ghost"],
        highlighted_path_ids=["service:a::DEPENDS_ON::service:ghost"],
    )
    cleaned = clean_graph(view)
    assert len(cleaned.edges) == 1
    assert cleaned.edges[0].target_id == "service:b"
    assert cleaned.root_node_ids == ["service:a"]
    assert cleaned.highlighted_path_ids == []
    assert cleaned.warning is not None
    assert "Edges with missing endpoints omitted." in cleaned.warning


@pytest.fixture
def fixture_service() -> GraphService:
    settings = Settings(
        development_fixtures=True,
        falkordb_graph_name="weave_brain",
        falkordb_host="localhost",
    )
    return GraphService(settings)


def test_service_overview_fixture(fixture_service: GraphService) -> None:
    overview = fixture_service.overview(AUTH)
    assert isinstance(overview, ServiceOverview)
    assert overview.service.id == AUTH
    assert overview.service.title == "Authentication API"
    assert overview.team is not None
    assert overview.team.id == "team:platform-engineering"
    assert len(overview.repositories) >= 1
    assert overview.repositories[0].id == "repository:acme/auth-api"
    assert len(overview.decisions) >= 1
    assert overview.decisions[0].id == "decision:adr-001"
    assert len(overview.evidence) >= 1
    assert isinstance(overview.graph, GraphView)
    assert AUTH in [n.id for n in overview.graph.nodes]


def test_service_overview_not_found(fixture_service: GraphService) -> None:
    with pytest.raises(HTTPException) as exc_info:
        fixture_service.overview("service:nonexistent")
    assert exc_info.value.status_code == 404
    assert "Service not found" in exc_info.value.detail


def test_neighborhood_fixture(fixture_service: GraphService) -> None:
    view = fixture_service.neighborhood(AUTH, depth=2)
    assert isinstance(view, GraphView)
    node_ids = {n.id for n in view.nodes}
    assert AUTH in node_ids
    assert "team:platform-engineering" in node_ids
    assert view.warning == "Development fixture data."


def test_neighborhood_not_found(fixture_service: GraphService) -> None:
    with pytest.raises(HTTPException) as exc_info:
        fixture_service.neighborhood("service:nonexistent", depth=1)
    assert exc_info.value.status_code == 404
    assert "Entity not found" in exc_info.value.detail


def test_entity_fixture(fixture_service: GraphService) -> None:
    entity = fixture_service.entity(AUTH)
    assert isinstance(entity, GraphNode)
    assert entity.id == AUTH
    assert entity.title == "Authentication API"


def test_entity_not_found(fixture_service: GraphService) -> None:
    with pytest.raises(HTTPException) as exc_info:
        fixture_service.entity("service:nonexistent")
    assert exc_info.value.status_code == 404


def test_blast_radius_fixture(fixture_service: GraphService) -> None:
    blast = fixture_service.blast(AUTH, depth=2)
    assert isinstance(blast, BlastRadius)
    affected_ids = {n.id for n in blast.affected_services}
    assert "service:user-profile-api" in affected_ids
    assert "service:notification-service" in affected_ids
    assert len(blast.evidence) >= 1
    assert AUTH in [n.id for n in blast.graph.nodes]


def test_blast_radius_not_found(fixture_service: GraphService) -> None:
    with pytest.raises(HTTPException) as exc_info:
        fixture_service.blast("service:nonexistent", depth=1)
    assert exc_info.value.status_code == 404
    assert "Service not found" in exc_info.value.detail


def test_decisions_fixture(fixture_service: GraphService) -> None:
    retrieval = fixture_service.decisions(AUTH)
    assert isinstance(retrieval, Retrieval)
    decision_ids = {n.id for n in retrieval.nodes}
    assert "decision:adr-001" in decision_ids
    # Ensure target service is preserved in graph view and DECIDES_FOR edges are not pruned
    graph_node_ids = {n.id for n in retrieval.graph.nodes}
    assert AUTH in graph_node_ids
    decides_for_edges = [
        e for e in retrieval.graph.edges if e.relationship_type == "DECIDES_FOR"
    ]
    assert len(decides_for_edges) >= 1
    assert all(e.target_id == AUTH for e in decides_for_edges)
    assert retrieval.graph.root_node_ids == [AUTH]


def test_experts_fixture(fixture_service: GraphService) -> None:
    retrieval = fixture_service.experts(AUTH)
    assert isinstance(retrieval, Retrieval)
    expert_ids = {n.id for n in retrieval.nodes}
    assert "person:priya-sharma" in expert_ids
    assert "person:james-chen" in expert_ids
    assert len(retrieval.evidence) == 2
    assert all(item.relationship_path is not None for item in retrieval.evidence)


def test_shortest_path_directional_and_highlights(
    fixture_service: GraphService,
) -> None:
    res = fixture_service.shortest("team:platform-engineering", AUTH)
    assert isinstance(res, ShortestPath)
    assert res.path_found is True
    assert len(res.graph.edges) == 1
    edge = res.graph.edges[0]
    # Edge direction must be preserved: Team -> OWNS -> Service
    assert edge.source_id == "team:platform-engineering"
    assert edge.target_id == AUTH
    assert edge.relationship_type == "OWNS"
    assert all(n.on_highlighted_path for n in res.graph.nodes)


def test_shortest_path_not_found(fixture_service: GraphService) -> None:
    # Use an isolated mock neighborhood to verify unreachable target returns path_found=False
    with patch.object(
        fixture_service,
        "neighborhood",
        return_value=GraphView(
            nodes=[GraphNode(id="service:a", type="service", title="A")],
            edges=[],
        ),
    ):
        res = fixture_service.shortest("service:a", "service:unreachable")
        assert res.path_found is False
        assert len(res.graph.nodes) == 0
        assert "No path found" in (res.graph.warning or "")


def test_search_fixture(fixture_service: GraphService) -> None:
    results = fixture_service.search("auth")
    assert len(results) >= 1
    assert any("auth" in n.id.lower() or "auth" in n.title.lower() for n in results)

    empty_results = fixture_service.search("completely_nonexistent_token_xyz")
    assert empty_results == []


def test_database_not_configured_raises_503() -> None:
    unconfigured_settings = Settings(
        development_fixtures=False,
        falkordb_graph_name=None,
        falkordb_host="localhost",
    )
    service = GraphService(unconfigured_settings)
    with pytest.raises(HTTPException) as exc_info:
        service._graph()
    assert exc_info.value.status_code == 503
    assert "Database is not configured." in exc_info.value.detail


def test_database_configuration_error_raises_503() -> None:
    settings = Settings(
        development_fixtures=False,
        falkordb_graph_name="weave_brain",
        falkordb_host="localhost",
    )
    service = GraphService(settings)
    with patch(
        "weave_brain.services.graph_service.get_graph",
        side_effect=ConfigurationError("Missing required variable"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            service._graph()
        assert exc_info.value.status_code == 503
        assert "Database configuration error" in exc_info.value.detail
