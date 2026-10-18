"""Smoke and idempotency integration tests for FalkorDB."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest

from weave_brain.domain.models import EvidenceItem, GraphView
from weave_brain.graph.client import ConfigurationError, get_graph
from weave_brain.graph.fixtures import (
    find_experts_stub,
    get_blast_radius_stub,
    get_decisions_for_service_stub,
    get_neighborhood_stub,
    get_service_overview_stub,
)


def test_configuration_error_when_env_vars_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify get_graph raises ConfigurationError when any required env var is missing or invalid."""
    monkeypatch.delenv("FALKORDB_HOST", raising=False)
    monkeypatch.delenv("FALKORDB_PORT", raising=False)
    monkeypatch.delenv("FALKORDB_GRAPH_NAME", raising=False)

    # Missing FALKORDB_GRAPH_NAME
    with pytest.raises(ConfigurationError, match="FALKORDB_GRAPH_NAME"):
        get_graph()

    monkeypatch.setenv("FALKORDB_GRAPH_NAME", "test_graph")

    # Missing FALKORDB_HOST
    with pytest.raises(ConfigurationError, match="FALKORDB_HOST"):
        get_graph()

    monkeypatch.setenv("FALKORDB_HOST", "localhost")

    # Missing FALKORDB_PORT
    with pytest.raises(ConfigurationError, match="FALKORDB_PORT"):
        get_graph()

    # Invalid FALKORDB_PORT
    monkeypatch.setenv("FALKORDB_PORT", "invalid-port")
    with pytest.raises(ConfigurationError, match="Invalid FALKORDB_PORT"):
        get_graph()


def test_offline_fixtures_validation() -> None:
    """Verify that all offline stubs validate cleanly against shared domain models."""
    overview = get_service_overview_stub("service:authentication-api")
    assert "service" in overview
    assert "evidence" in overview
    GraphView(**overview["graph"])
    for ev in overview["evidence"]:
        EvidenceItem(**ev)

    decisions = get_decisions_for_service_stub("service:authentication-api")
    assert "decisions" in decisions
    GraphView(**decisions["graph"])
    for ev in decisions["evidence"]:
        EvidenceItem(**ev)

    blast = get_blast_radius_stub("service:authentication-api")
    assert "affected_services" in blast
    GraphView(**blast["graph"])
    for ev in blast["evidence"]:
        EvidenceItem(**ev)

    experts = find_experts_stub("service:authentication-api")
    assert len(experts) >= 2
    for exp in experts:
        assert exp["id"].startswith("person:")

    neighborhood = get_neighborhood_stub("service:authentication-api", depth=2)
    assert "nodes" in neighborhood
    assert "edges" in neighborhood
    GraphView(**neighborhood)


@pytest.fixture
def falkordb_graph(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    """Provide a configured FalkorDB graph instance when FALKORDB_AVAILABLE is set."""
    if not os.getenv("FALKORDB_AVAILABLE"):
        pytest.skip("FalkorDB integration test requires FALKORDB_AVAILABLE=1")

    if not os.getenv("FALKORDB_HOST"):
        monkeypatch.setenv("FALKORDB_HOST", "localhost")
    if not os.getenv("FALKORDB_PORT"):
        monkeypatch.setenv("FALKORDB_PORT", "6379")
    if not os.getenv("FALKORDB_GRAPH_NAME"):
        monkeypatch.setenv("FALKORDB_GRAPH_NAME", "test_smoke_graph")

    graph = get_graph()
    yield graph


def test_falkordb_connectivity(falkordb_graph: Any) -> None:
    """Verify basic FalkorDB Cypher execution with RETURN 1 AS ok."""
    result = falkordb_graph.query("RETURN 1 AS ok")
    assert result.result_set == [[1]]


def test_merge_idempotency_and_cleanup(falkordb_graph: Any) -> None:
    """Verify parameterized MERGE idempotency and isolated test node cleanup."""
    test_node_id = "test:smoke-node"
    test_title = "Smoke Test"
    params = {"id": test_node_id, "title": test_title}

    # Clean up before running test
    falkordb_graph.query("MATCH (n:TestNode {id: $id}) DELETE n", {"id": test_node_id})

    try:
        # Run MERGE twice
        merge_query = (
            "MERGE (n:TestNode {id: $id}) ON CREATE SET n.title = $title RETURN n"
        )
        res1 = falkordb_graph.query(merge_query, params)
        assert len(res1.result_set) == 1

        res2 = falkordb_graph.query(merge_query, params)
        assert len(res2.result_set) == 1

        # Assert exactly one node exists
        count_res = falkordb_graph.query(
            "MATCH (n:TestNode {id: $id}) RETURN count(n)",
            {"id": test_node_id},
        )
        # count(n) returns [[1]]
        assert count_res.result_set[0][0] == 1
    finally:
        # Clean up after test
        falkordb_graph.query(
            "MATCH (n:TestNode {id: $id}) DELETE n",
            {"id": test_node_id},
        )
