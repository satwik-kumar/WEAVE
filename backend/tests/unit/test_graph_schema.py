"""Unit tests for graph schema mapping and index initialization."""

from __future__ import annotations

from typing import Any, get_args

import pytest
from redis.exceptions import ResponseError

from weave_brain.domain.models import EntityType
from weave_brain.graph.schema import (
    ENTITY_TYPE_TO_LABEL,
    IDENTITY_PROPERTY,
    WHITELISTED_LABELS,
    get_label_for_entity_type,
    init_schema,
)


class MockQueryResult:
    def __init__(self, header: list[list[Any]], result_set: list[list[Any]]) -> None:
        self.header = header
        self.result_set = result_set


class MockGraph:
    def __init__(
        self,
        existing_indexes: list[list[Any]] | None = None,
        query_error: Exception | None = None,
    ) -> None:
        self.existing_indexes = existing_indexes or []
        self.executed_queries: list[str] = []
        self.query_error = query_error

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> MockQueryResult:
        self.executed_queries.append(cypher)
        if cypher == "CALL db.indexes()":
            header = [[1, "label"], [1, "properties"]]
            return MockQueryResult(header=header, result_set=self.existing_indexes)

        if self.query_error:
            raise self.query_error

        return MockQueryResult(header=[], result_set=[])


def test_entity_type_mapping_completeness() -> None:
    """Verify all 11 EntityType literals are mapped to canonical graph labels."""
    expected_mapping = {
        "person": "Person",
        "team": "Team",
        "service": "Service",
        "repository": "Repository",
        "file": "File",
        "document": "Document",
        "decision": "Decision",
        "ticket": "Ticket",
        "incident": "Incident",
        "test": "Test",
        "project": "Project",
    }
    allowed_types = get_args(EntityType)
    assert len(allowed_types) == 11
    assert set(allowed_types) == set(expected_mapping.keys())

    for entity_type in allowed_types:
        assert entity_type in ENTITY_TYPE_TO_LABEL
        assert ENTITY_TYPE_TO_LABEL[entity_type] == expected_mapping[entity_type]
        assert get_label_for_entity_type(entity_type) == expected_mapping[entity_type]


def test_get_label_for_unknown_type() -> None:
    """Verify get_label_for_entity_type raises KeyError for unsupported entity types."""
    with pytest.raises(KeyError, match="Unknown entity type"):
        get_label_for_entity_type("unknown_type")


def test_whitelisted_labels() -> None:
    """Verify WHITELISTED_LABELS contains all expected labels."""
    assert len(WHITELISTED_LABELS) == 11
    assert WHITELISTED_LABELS == frozenset(ENTITY_TYPE_TO_LABEL.values())


def test_init_schema_creates_indexes_on_empty_graph() -> None:
    """Verify init_schema creates indexes on identity property for all 11 labels."""
    mock_graph = MockGraph(existing_indexes=[])
    initialized = init_schema(mock_graph)

    assert len(initialized) == 11
    assert set(initialized) == WHITELISTED_LABELS
    # 1 query for db.indexes + 11 CREATE INDEX queries
    assert len(mock_graph.executed_queries) == 12
    assert mock_graph.executed_queries[0] == "CALL db.indexes()"

    for label in WHITELISTED_LABELS:
        expected_query = f"CREATE INDEX FOR (n:{label}) ON (n.{IDENTITY_PROPERTY})"
        assert expected_query in mock_graph.executed_queries


def test_init_schema_idempotency_with_existing_indexes() -> None:
    """Verify init_schema skips labels that already have an index on id."""
    existing = [
        ["Service", ["id"]],
        ["Team", ["id"]],
    ]
    mock_graph = MockGraph(existing_indexes=existing)
    initialized = init_schema(mock_graph)

    assert len(initialized) == 11
    # 1 for CALL db.indexes() + 9 CREATE INDEX queries for the remaining labels
    assert len(mock_graph.executed_queries) == 10
    assert "CREATE INDEX FOR (n:Service) ON (n.id)" not in mock_graph.executed_queries
    assert "CREATE INDEX FOR (n:Team) ON (n.id)" not in mock_graph.executed_queries
    assert "CREATE INDEX FOR (n:Person) ON (n.id)" in mock_graph.executed_queries


def test_init_schema_handles_already_indexed_response_error() -> None:
    """Verify init_schema tolerates ResponseError when index already exists."""
    error = ResponseError("Attribute 'id' is already indexed")
    mock_graph = MockGraph(existing_indexes=[], query_error=error)

    # Should not raise
    initialized = init_schema(mock_graph)
    assert len(initialized) == 11


def test_init_schema_propagates_unrelated_database_error() -> None:
    """Verify init_schema re-raises unexpected database errors."""
    error = ResponseError("Database disk full or syntax error")
    mock_graph = MockGraph(existing_indexes=[], query_error=error)

    with pytest.raises(ResponseError, match="Database disk full"):
        init_schema(mock_graph)
