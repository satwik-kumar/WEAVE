"""Integration tests for FalkorDB graph writer and two-phase batch upsert."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from redis.exceptions import ResponseError

from weave_brain.domain.models import SourceArtifact
from weave_brain.graph.client import get_graph
from weave_brain.graph.schema import init_schema
from weave_brain.graph.writer import (
    upsert_many,
    upsert_node,
    upsert_relationship,
    write_artifacts,
)


@pytest.fixture
def writer_graph(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    """Provide an isolated, schema-initialized FalkorDB graph for writer integration tests."""
    if not os.getenv("FALKORDB_AVAILABLE"):
        pytest.skip("FalkorDB integration test requires FALKORDB_AVAILABLE=1")

    if not os.getenv("FALKORDB_HOST"):
        monkeypatch.setenv("FALKORDB_HOST", "127.0.0.1")
    if not os.getenv("FALKORDB_PORT"):
        monkeypatch.setenv("FALKORDB_PORT", "6379")

    test_graph_name = os.getenv("FALKORDB_GRAPH_NAME") or "test_writer_graph"
    monkeypatch.setenv("FALKORDB_GRAPH_NAME", test_graph_name)

    graph = get_graph()
    with contextlib.suppress(ResponseError):
        graph.delete()

    graph = get_graph()
    # Initialize schema indexes before tests
    init_schema(graph)
    yield graph

    with contextlib.suppress(ResponseError):
        graph.delete()


def test_upsert_node_and_property_update_live(writer_graph: Any) -> None:
    """Verify live node creation, property updates, and idempotency."""
    time1 = datetime(2025, 2, 1, 10, 0, 0, tzinfo=UTC)
    artifact = SourceArtifact(
        canonical_id="service:test-auth",
        entity_type="service",
        title="Test Auth Service",
        source_id="git:auth-1",
        source_type="git",
        ingested_at=time1,
        properties={"status": "beta", "language": "Python"},
    )

    # Initial upsert: node created
    created = upsert_node(artifact, graph=writer_graph)
    assert created is True

    res = writer_graph.query(
        "MATCH (n:Service {id: $id}) RETURN n.title, n.status, n.language, n.ingested_at",
        {"id": "service:test-auth"},
    )
    assert len(res.result_set) == 1
    assert res.result_set[0][0] == "Test Auth Service"
    assert res.result_set[0][1] == "beta"
    assert res.result_set[0][2] == "Python"
    assert res.result_set[0][3] == time1.isoformat()

    # Second upsert with updated property: node updated, not recreated
    artifact.title = "Test Auth Service v2"
    artifact.properties["status"] = "production"
    created_second = upsert_node(artifact, graph=writer_graph)
    assert created_second is False

    res2 = writer_graph.query(
        "MATCH (n:Service {id: $id}) RETURN n.title, n.status",
        {"id": "service:test-auth"},
    )
    assert len(res2.result_set) == 1
    assert res2.result_set[0][0] == "Test Auth Service v2"
    assert res2.result_set[0][1] == "production"

    # Count nodes with this id: exactly 1
    count_res = writer_graph.query(
        "MATCH (n {id: $id}) RETURN count(n)",
        {"id": "service:test-auth"},
    )
    assert count_res.result_set[0][0] == 1


def test_upsert_relationship_live(writer_graph: Any) -> None:
    """Verify live directed edge creation between nodes and property setting."""
    svc_artifact = SourceArtifact(
        canonical_id="service:auth-api",
        entity_type="service",
        title="Auth API",
        source_id="git:auth",
        source_type="git",
        properties={},
    )
    team_artifact = SourceArtifact(
        canonical_id="team:platform-eng",
        entity_type="team",
        title="Platform Eng",
        source_id="jira:plat",
        source_type="jira",
        properties={},
    )
    upsert_node(svc_artifact, graph=writer_graph)
    upsert_node(team_artifact, graph=writer_graph)

    # First edge creation
    matched, created = upsert_relationship(
        source_id="team:platform-eng",
        rel_type="OWNS",
        target_id="service:auth-api",
        properties={"since": "2024-01-01"},
        graph=writer_graph,
    )
    assert matched is True
    assert created is True

    res = writer_graph.query(
        "MATCH (t:Team {id: $team_id})-[r:OWNS]->(s:Service {id: $svc_id}) RETURN r.since",
        {"team_id": "team:platform-eng", "svc_id": "service:auth-api"},
    )
    assert len(res.result_set) == 1
    assert res.result_set[0][0] == "2024-01-01"

    # Second edge execution (idempotent, updates property)
    matched2, created2 = upsert_relationship(
        source_id="team:platform-eng",
        rel_type="OWNS",
        target_id="service:auth-api",
        properties={"since": "2024-06-01"},
        graph=writer_graph,
    )
    assert matched2 is True
    assert created2 is False

    res2 = writer_graph.query(
        "MATCH (t:Team {id: $team_id})-[r:OWNS]->(s:Service {id: $svc_id}) RETURN r.since",
        {"team_id": "team:platform-eng", "svc_id": "service:auth-api"},
    )
    assert res2.result_set[0][0] == "2024-06-01"


def test_write_artifacts_two_phase_and_forward_reference(writer_graph: Any) -> None:
    """Verify batch write resolves forward references and generates accurate SyncReport."""
    batch = [
        SourceArtifact(
            canonical_id="team:backend-core",
            entity_type="team",
            title="Backend Core",
            source_id="team:core",
            source_type="jira",
            properties={},
            # Forward references to service:user-api which is 2nd in batch
            relationships=[("OWNS", "service:user-api")],
        ),
        SourceArtifact(
            canonical_id="service:user-api",
            entity_type="service",
            title="User API",
            source_id="git:user",
            source_type="git",
            properties={},
            # Forward reference to repository:user-repo which is 3rd in batch
            relationships=[("IMPLEMENTED_IN", "repository:user-repo")],
        ),
        SourceArtifact(
            canonical_id="repository:user-repo",
            entity_type="repository",
            title="acme/user-api",
            source_id="repo:user",
            source_type="git",
            properties={"url": "https://github.com/acme/user-api"},
        ),
    ]

    # First batch write
    report1 = write_artifacts(writer_graph, batch, source_name="live_seed")
    assert report1.source == "live_seed"
    assert report1.records_processed == 3
    assert report1.nodes_created == 3
    assert report1.nodes_updated == 0
    assert report1.edges_created == 2
    assert len(report1.errors) == 0
    assert len(report1.warnings) == 0

    # Verify both relationships exist in FalkorDB
    res_owns = writer_graph.query(
        "MATCH (t:Team {id: 'team:backend-core'})-[:OWNS]->(s:Service {id: 'service:user-api'}) RETURN s.id"
    )
    assert len(res_owns.result_set) == 1

    res_impl = writer_graph.query(
        "MATCH (s:Service {id: 'service:user-api'})-[:IMPLEMENTED_IN]->(r:Repository {id: 'repository:user-repo'}) RETURN r.id"
    )
    assert len(res_impl.result_set) == 1

    # Second batch write: 100% idempotent
    report2 = upsert_many(batch, graph=writer_graph, source_name="live_seed")
    assert report2.records_processed == 3
    assert report2.nodes_created == 0
    assert report2.nodes_updated == 3
    assert report2.edges_created == 0
    assert len(report2.errors) == 0
    assert len(report2.warnings) == 0


def test_missing_relationship_target_creates_no_phantom_node(writer_graph: Any) -> None:
    """Verify edges pointing to nonexistent nodes are safely skipped with warning."""
    artifact = SourceArtifact(
        canonical_id="service:standalone-api",
        entity_type="service",
        title="Standalone API",
        source_id="git:standalone",
        source_type="git",
        properties={},
        relationships=[
            ("DEPENDS_ON", "service:nonexistent-target"),
        ],
    )

    report = write_artifacts(writer_graph, [artifact], source_name="test")
    assert report.nodes_created == 1
    assert report.edges_created == 0
    assert len(report.warnings) == 1
    assert "service:nonexistent-target" in report.warnings[0]

    # Verify no phantom node with id 'service:nonexistent-target' was created
    phantom_check = writer_graph.query(
        "MATCH (n {id: 'service:nonexistent-target'}) RETURN count(n)"
    )
    assert phantom_check.result_set[0][0] == 0


def test_property_collision_defense_live(writer_graph: Any) -> None:
    """Verify live node cannot overwrite its canonical id via properties dict."""
    malicious = SourceArtifact(
        canonical_id="service:real-auth",
        entity_type="service",
        title="Real Auth",
        source_id="git:auth",
        source_type="git",
        properties={
            "id": "service:fake-spoofed",
            "canonical_id": "service:fake-spoofed",
            "tech": "FastAPI",
        },
    )
    upsert_node(malicious, graph=writer_graph)

    # Node must exist with real-auth, not fake-spoofed
    real = writer_graph.query(
        "MATCH (n {id: 'service:real-auth'}) RETURN n.tech"
    )
    assert len(real.result_set) == 1
    assert real.result_set[0][0] == "FastAPI"

    fake = writer_graph.query(
        "MATCH (n {id: 'service:fake-spoofed'}) RETURN count(n)"
    )
    assert fake.result_set[0][0] == 0
