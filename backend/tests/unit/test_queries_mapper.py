"""Unit tests for graph mapper and query unpacking logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from weave_brain.domain.models import EvidenceItem, GraphView
from weave_brain.graph.fixtures import (
    get_blast_radius_stub,
    get_decisions_for_service_stub,
    get_neighborhood_stub,
    get_service_overview_stub,
)
from weave_brain.graph.mapper import (
    _calculate_freshness,
    to_evidence_items,
    to_graph_view,
)
from weave_brain.graph.queries import (
    _unpack_edge,
    _unpack_node,
    _unpack_path,
    get_service_overview,
    search_entities,
)


def test_mapper_fixtures_to_graph_view():
    """Verify to_graph_view cleanly validates all 4 offline fixtures into GraphView."""
    for stub_fn in (
        get_service_overview_stub,
        get_decisions_for_service_stub,
        get_blast_radius_stub,
        get_neighborhood_stub,
    ):
        data = stub_fn()
        gv = to_graph_view(data)
        assert isinstance(gv, GraphView)
        assert len(gv.nodes) > 0
        assert len(gv.edges) > 0
        for edge in gv.edges:
            assert "::" in edge.id


def test_mapper_staleness_and_freshness():
    """Verify freshness status calculation: fresh (<30d), aging (30-90d), stale (>90d)."""
    now = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)

    # Fresh (<30d)
    dt_fresh = (now - timedelta(days=10)).isoformat()
    stale, status = _calculate_freshness({"ingested_at": dt_fresh}, now=now)
    assert not stale
    assert status == "fresh"

    # Aging (30-90d)
    dt_aging = (now - timedelta(days=45)).isoformat()
    stale, status = _calculate_freshness({"ingested_at": dt_aging}, now=now)
    assert stale
    assert status == "aging"

    # Stale (>90d)
    dt_stale = (now - timedelta(days=120)).isoformat()
    stale, status = _calculate_freshness({"ingested_at": dt_stale}, now=now)
    assert stale
    assert status == "stale"

    # Missing
    stale, status = _calculate_freshness({}, now=now)
    assert not stale
    assert status == "fresh"


def test_mapper_superseded_decision():
    """Verify a Decision node targeted by SUPERSEDES is marked status='superseded'."""
    raw = {
        "nodes": [
            {
                "id": "decision:adr-002",
                "type": "decision",
                "title": "Old Decision",
                "properties": {"status": "accepted"},
            },
            {
                "id": "decision:adr-003",
                "type": "decision",
                "title": "New Decision",
                "properties": {"status": "accepted"},
            },
        ],
        "edges": [
            {
                "id": "decision:adr-003::SUPERSEDES::decision:adr-002",
                "source_id": "decision:adr-003",
                "target_id": "decision:adr-002",
                "relationship_type": "SUPERSEDES",
            }
        ],
    }
    gv = to_graph_view(raw)
    node_map = {n.id: n for n in gv.nodes}
    assert node_map["decision:adr-002"].properties["status"] == "superseded"
    assert node_map["decision:adr-003"].properties["status"] == "accepted"


def test_mapper_highlighted_paths():
    """Verify nodes and edges along highlighted_paths receive highlighted flags."""
    raw = {
        "nodes": [
            {"id": "service:a", "type": "service", "title": "A"},
            {"id": "service:b", "type": "service", "title": "B"},
            {"id": "service:c", "type": "service", "title": "C"},
        ],
        "edges": [
            {
                "id": "service:a::DEPENDS_ON::service:b",
                "source_id": "service:a",
                "target_id": "service:b",
                "relationship_type": "DEPENDS_ON",
            },
            {
                "id": "service:b::DEPENDS_ON::service:c",
                "source_id": "service:b",
                "target_id": "service:c",
                "relationship_type": "DEPENDS_ON",
            },
        ],
    }
    highlighted_paths = [["service:a", "service:b"]]
    gv = to_graph_view(raw, highlighted_paths=highlighted_paths)

    node_map = {n.id: n for n in gv.nodes}
    assert node_map["service:a"].on_highlighted_path is True
    assert node_map["service:b"].on_highlighted_path is True
    assert node_map["service:c"].on_highlighted_path is False
    assert "service:a::DEPENDS_ON::service:b" in gv.highlighted_path_ids


def test_to_evidence_items_explicit_and_synthesis():
    """Verify evidence extraction and fallback synthesis."""
    # Explicit evidence
    explicit_data = {
        "evidence": [
            {
                "source_id": "decision:adr-001",
                "title": "ADR 001",
                "source_type": "decision",
                "excerpt": "Token expiry rule",
                "relationship_path": ["decision:adr-001", "service:auth"],
            }
        ]
    }
    items = to_evidence_items(explicit_data)
    assert len(items) == 1
    assert isinstance(items[0], EvidenceItem)
    assert items[0].source_id == "decision:adr-001"

    # Synthesis from decisions
    synth_data = {
        "service_id": "service:auth",
        "decisions": [
            {
                "id": "decision:adr-001",
                "title": "ADR 001",
                "properties": {"rationale": "Security mandate"},
            }
        ],
    }
    synth_items = to_evidence_items(synth_data)
    assert len(synth_items) == 1
    assert synth_items[0].source_id == "decision:adr-001"
    assert synth_items[0].excerpt == "Security mandate"


def test_query_unpacking_helpers():
    """Test safe unpacking of mock FalkorDB driver objects."""
    # Mock Node
    mock_node = MagicMock()
    mock_node.id = 42
    mock_node.labels = ["Service"]
    mock_node.properties = {
        "id": "service:test-api",
        "title": "Test API",
        "language": "Python",
    }

    unpacked_n = _unpack_node(mock_node)
    assert unpacked_n["id"] == "service:test-api"
    assert unpacked_n["type"] == "service"
    assert unpacked_n["title"] == "Test API"
    assert unpacked_n["properties"] == {"language": "Python"}

    # Mock Edge
    mock_edge = MagicMock()
    mock_edge.id = 99
    mock_edge.relation = "DEPENDS_ON"
    mock_edge.properties = {"weight": 2}

    unpacked_e = _unpack_edge(mock_edge, "service:a", "service:b")
    assert unpacked_e["id"] == "service:a::DEPENDS_ON::service:b"
    assert unpacked_e["source_id"] == "service:a"
    assert unpacked_e["target_id"] == "service:b"
    assert unpacked_e["relationship_type"] == "DEPENDS_ON"
    assert unpacked_e["properties"] == {"weight": 2}


def test_query_path_unpacking_canonical_ids():
    """Test Path unpacking maps internal node IDs to canonical string IDs for edges."""
    node1 = MagicMock()
    node1.id = 101
    node1.labels = ["Service"]
    node1.properties = {"id": "service:auth-api", "title": "Auth API"}

    node2 = MagicMock()
    node2.id = 102
    node2.labels = ["Repository"]
    node2.properties = {"id": "repository:auth-repo", "title": "Auth Repo"}

    edge = MagicMock()
    edge.id = 201
    edge.relation = "IMPLEMENTED_IN"
    edge.src_node = 101
    edge.dest_node = 102
    edge.properties = {}

    mock_path = MagicMock()
    mock_path.nodes = MagicMock(return_value=[node1, node2])
    mock_path.edges = MagicMock(return_value=[edge])

    unpacked_nodes, unpacked_edges = _unpack_path(mock_path)
    assert len(unpacked_nodes) == 2
    assert len(unpacked_edges) == 1
    assert unpacked_edges[0]["source_id"] == "service:auth-api"
    assert unpacked_edges[0]["target_id"] == "repository:auth-repo"
    assert unpacked_edges[0]["relationship_type"] == "IMPLEMENTED_IN"


def test_queries_empty_returns_safely():
    """Verify queries return None or empty collections on missing records."""
    mock_graph = MagicMock()
    mock_res = MagicMock()
    mock_res.result_set = []
    mock_graph.query.return_value = mock_res

    # Service overview returns None on missing service
    res = get_service_overview("service:missing", graph=mock_graph)
    assert res is None

    # Empty search query returns empty list
    empty_res = search_entities("", graph=mock_graph)
    assert empty_res == []
