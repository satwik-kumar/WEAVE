"""Integration tests for FalkorDB schema initialization and idempotency."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Generator
from typing import Any

import pytest
from redis.exceptions import ResponseError

from weave_brain.graph.client import get_graph
from weave_brain.graph.schema import (
    IDENTITY_PROPERTY,
    WHITELISTED_LABELS,
    get_existing_indexes,
    init_schema,
)


@pytest.fixture
def isolated_schema_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Any, None, None]:
    """Provide an isolated temporary FalkorDB graph for schema initialization testing."""
    if not os.getenv("FALKORDB_AVAILABLE"):
        pytest.skip("FalkorDB integration test requires FALKORDB_AVAILABLE=1")

    if not os.getenv("FALKORDB_HOST"):
        monkeypatch.setenv("FALKORDB_HOST", "localhost")
    if not os.getenv("FALKORDB_PORT"):
        monkeypatch.setenv("FALKORDB_PORT", "6379")

    test_graph_name = "test_schema_init_graph"
    monkeypatch.setenv("FALKORDB_GRAPH_NAME", test_graph_name)

    graph = get_graph()
    # Ensure fresh starting state
    with contextlib.suppress(ResponseError):
        graph.delete()

    # Re-select after delete
    graph = get_graph()
    yield graph

    # Cleanup after test
    with contextlib.suppress(ResponseError):
        graph.delete()


def test_init_schema_live_idempotency(isolated_schema_graph: Any) -> None:
    """Verify live schema initialization creates indexes for all 11 labels and runs idempotently."""
    # First initialization on empty graph
    first_run = init_schema(isolated_schema_graph)
    assert len(first_run) == 11
    assert set(first_run) == WHITELISTED_LABELS

    # Verify indexes in FalkorDB via db.indexes()
    indexes = get_existing_indexes(isolated_schema_graph)
    for label in WHITELISTED_LABELS:
        assert (label, IDENTITY_PROPERTY) in indexes

    # Second initialization (must be strictly idempotent)
    second_run = init_schema(isolated_schema_graph)
    assert len(second_run) == 11
    assert set(second_run) == WHITELISTED_LABELS

    # Re-verify indexes remain intact
    indexes_after = get_existing_indexes(isolated_schema_graph)
    assert indexes == indexes_after
