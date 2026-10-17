"""Unit tests for graph writer functions, normalization, and properties preparation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from weave_brain.domain.models import SourceArtifact
from weave_brain.graph.writer import (
    WHITELISTED_RELATIONSHIPS,
    normalize_relationship,
    prepare_node_properties,
    upsert_edge,
    upsert_many,
    upsert_node,
    upsert_relationship,
    write_artifacts,
)


class MockQueryResult:
    def __init__(
        self,
        result_set: list[list[Any]] | None = None,
        nodes_created: int = 0,
        relationships_created: int = 0,
    ) -> None:
        self.result_set = result_set if result_set is not None else [["ok"]]
        self.nodes_created = float(nodes_created)
        self.relationships_created = float(relationships_created)


class MockGraph:
    def __init__(
        self,
        node_created: bool = True,
        edge_matched: bool = True,
        edge_created: bool = True,
    ) -> None:
        self.executed_queries: list[tuple[str, dict[str, Any] | None]] = []
        self.node_created = node_created
        self.edge_matched = edge_matched
        self.edge_created = edge_created

    def query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> MockQueryResult:
        self.executed_queries.append((cypher, params))
        if cypher.startswith("MERGE (n:"):
            return MockQueryResult(nodes_created=1 if self.node_created else 0)
        if cypher.startswith("MATCH ("):
            if not self.edge_matched:
                return MockQueryResult(
                    result_set=[], relationships_created=0
                )
            return MockQueryResult(
                result_set=[["type"]],
                relationships_created=1 if self.edge_created else 0,
            )
        return MockQueryResult()


def test_whitelisted_relationships_completeness() -> None:
    """Verify all 14 canonical relationship types from docs/graph-schema.md are present."""
    expected = {
        "OWNS",
        "MEMBER_OF",
        "MAINTAINS",
        "DEPENDS_ON",
        "IMPLEMENTED_IN",
        "CONTAINS",
        "IMPORTS",
        "DECIDES_FOR",
        "MOTIVATED_BY",
        "SUPERSEDES",
        "DOCUMENTS",
        "AFFECTS",
        "WORKED_ON",
        "USES",
    }
    assert WHITELISTED_RELATIONSHIPS == expected
    assert len(WHITELISTED_RELATIONSHIPS) == 14


def test_normalize_relationship_two_tuple() -> None:
    """Verify normalization of a 2-tuple RelationshipEdge."""
    edge = ("DEPENDS_ON", "service:authentication-api")
    rel_type, target_id, props = normalize_relationship(edge)
    assert rel_type == "DEPENDS_ON"
    assert target_id == "service:authentication-api"
    assert props == {}


def test_normalize_relationship_three_tuple() -> None:
    """Verify normalization of a 3-tuple with datetime and None sanitization."""
    ts = datetime(2025, 5, 1, 12, 0, 0, tzinfo=UTC)
    edge = (
        "WORKED_ON",
        "project:auth-modernization",
        {"role": "Lead", "since": ts, "extra": None},
    )
    rel_type, target_id, props = normalize_relationship(edge)
    assert rel_type == "WORKED_ON"
    assert target_id == "project:auth-modernization"
    assert props["role"] == "Lead"
    assert props["since"] == ts.isoformat()
    assert "extra" not in props


def test_normalize_relationship_invalid_type() -> None:
    """Verify normalize_relationship rejects unwhitelisted relationship types."""
    with pytest.raises(ValueError, match="Invalid relationship type"):
        normalize_relationship(("UNSUPPORTED_REL", "service:target"))


def test_normalize_relationship_invalid_target() -> None:
    """Verify normalize_relationship rejects empty target_id."""
    with pytest.raises(ValueError, match="target_id must be a non-empty string"):
        normalize_relationship(("DEPENDS_ON", "   "))


def test_prepare_node_properties_collision_defense() -> None:
    """Verify arbitrary properties cannot overwrite reserved canonical identity fields."""
    fixed_time = datetime(2025, 1, 10, 8, 30, 0, tzinfo=UTC)
    artifact = SourceArtifact(
        canonical_id="service:auth-api",
        entity_type="service",
        title="Auth API",
        source_id="git:auth",
        source_type="git",
        ingested_at=fixed_time,
        properties={
            "id": "hacked:id",
            "canonical_id": "hacked:canonical",
            "title": "Malicious Title",
            "tech_stack": "FastAPI",
            "language": "Python",
            "nullable": None,
        },
    )

    props = prepare_node_properties(artifact)
    assert props["id"] == "service:auth-api"
    assert props["title"] == "Auth API"
    assert props["source_id"] == "git:auth"
    assert props["source_type"] == "git"
    assert props["ingested_at"] == fixed_time.isoformat()
    assert props["tech_stack"] == "FastAPI"
    assert props["language"] == "Python"
    assert "nullable" not in props


def test_prepare_node_properties_nested_dict_json() -> None:
    """Verify nested dictionary properties are serialized to valid JSON strings."""
    artifact = SourceArtifact(
        canonical_id="ticket:eng-042",
        entity_type="ticket",
        title="Ticket 42",
        source_id="jira:42",
        source_type="jira",
        properties={
            "metadata": {"sprint": 12, "points": 5},
        },
    )
    props = prepare_node_properties(artifact)
    assert isinstance(props["metadata"], str)
    decoded = json.loads(props["metadata"])
    assert decoded["sprint"] == 12
    assert decoded["points"] == 5


def test_upsert_node_created_vs_updated() -> None:
    """Verify upsert_node returns True on creation and False on match/update."""
    artifact = SourceArtifact(
        canonical_id="service:auth-api",
        entity_type="service",
        title="Auth API",
        source_id="git:auth",
        source_type="git",
        properties={},
    )

    graph_created = MockGraph(node_created=True)
    assert upsert_node(artifact, graph=graph_created) is True
    assert len(graph_created.executed_queries) == 1
    cypher, params = graph_created.executed_queries[0]
    assert "MERGE (n:Service {id: $id})" in cypher
    assert params["id"] == "service:auth-api"

    graph_updated = MockGraph(node_created=False)
    assert upsert_node(artifact, graph=graph_updated) is False


def test_upsert_relationship_indexed_matching() -> None:
    """Verify upsert_relationship uses labels from known ID prefixes for index optimization."""
    graph = MockGraph(edge_matched=True, edge_created=True)
    matched, created = upsert_relationship(
        source_id="service:user-profile-api",
        rel_type="DEPENDS_ON",
        target_id="service:authentication-api",
        properties={"since": "v1.0"},
        graph=graph,
    )
    assert matched is True
    assert created is True
    assert len(graph.executed_queries) == 1
    cypher, params = graph.executed_queries[0]
    assert "(a:Service {id: $src_id})" in cypher
    assert "(b:Service {id: $tgt_id})" in cypher
    assert "MERGE (a)-[r:DEPENDS_ON]->(b)" in cypher
    assert params["src_id"] == "service:user-profile-api"
    assert params["tgt_id"] == "service:authentication-api"
    assert params["props"] == {"since": "v1.0"}


def test_upsert_edge_alias() -> None:
    """Verify upsert_edge is an alias for upsert_relationship."""
    assert upsert_edge == upsert_relationship


def test_write_artifacts_alias() -> None:
    """Verify write_artifacts is an alias for upsert_many."""
    assert write_artifacts == upsert_many


def test_upsert_many_two_phase_and_reporting() -> None:
    """Verify two-phase batch processing, reporting statistics, and forward references."""
    artifacts = [
        SourceArtifact(
            canonical_id="team:platform-engineering",
            entity_type="team",
            title="Platform Engineering",
            source_id="team:plat",
            source_type="jira",
            properties={},
            # Forward reference to service:auth-api which is the 2nd artifact
            relationships=[("OWNS", "service:auth-api")],
        ),
        SourceArtifact(
            canonical_id="service:auth-api",
            entity_type="service",
            title="Auth API",
            source_id="git:auth",
            source_type="git",
            properties={},
            relationships=[("DEPENDS_ON", "service:nonexistent")],
        ),
    ]

    # Graph simulates:
    # 2 nodes created
    # 1st edge (OWNS) matches endpoints and creates edge
    # 2nd edge (DEPENDS_ON) fails to match nonexistent target
    class TwoPhaseMockGraph:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def query(
            self, cypher: str, params: dict[str, Any] | None = None
        ) -> MockQueryResult:
            self.queries.append(cypher)
            if cypher.startswith("MERGE (n:"):
                return MockQueryResult(nodes_created=1)
            if "DEPENDS_ON" in cypher:
                # Target nonexistent
                return MockQueryResult(
                    result_set=[], relationships_created=0
                )
            return MockQueryResult(
                result_set=[["OWNS"]], relationships_created=1
            )

    graph = TwoPhaseMockGraph()
    report = upsert_many(artifacts, graph=graph, source_name="unit_test")

    assert report.source == "unit_test"
    assert report.records_processed == 2
    assert report.nodes_created == 2
    assert report.nodes_updated == 0
    assert report.edges_created == 1
    assert len(report.warnings) == 1
    assert "service:nonexistent" in report.warnings[0]
    assert len(report.errors) == 0

    # Assert Phase 1 queries preceded Phase 2 queries
    assert graph.queries[0].startswith("MERGE (n:Team")
    assert graph.queries[1].startswith("MERGE (n:Service")
    assert graph.queries[2].startswith("MATCH (a:Team")
    assert graph.queries[3].startswith("MATCH (a:Service")
