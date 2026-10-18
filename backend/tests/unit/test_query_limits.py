"""Tests for query traversal bounds, over-fetching, and truncation signaling."""

from __future__ import annotations

import re
from typing import Any

from weave_brain.graph.queries import (
    QUERY_LIMIT,
    _execute_query,
    find_shortest_path,
    get_blast_radius,
    get_decisions_for_service,
    get_knowledge_gaps,
    get_neighborhood,
)


class MockResult:
    def __init__(self, rows: list[Any]):
        self.result_set = rows


class MockGraph:
    def __init__(self, handler=None):
        self.handler = handler
        self.queries_run: list[tuple[str, dict[str, Any]]] = []

    def query(self, cypher: str, params: dict[str, Any]) -> MockResult:
        self.queries_run.append((cypher, params))
        if self.handler:
            return self.handler(cypher, params)
        return MockResult([])


def test_query_limit_surfaces_omitted_rows_without_unbounded_output():
    """Verify get_blast_radius requests LIMIT 51 and marks truncation when 51 rows return."""

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        if "RETURN path" in cypher:
            assert re.search(r"LIMIT 51\s*$", cypher, re.IGNORECASE)
            return MockResult([[None]] * 51)
        return MockResult(
            [
                [
                    {
                        "id": "service:authentication-api",
                        "type": "service",
                        "title": "Auth",
                    }
                ]
            ]
        )

    graph = MockGraph(handler)
    result = get_blast_radius("service:authentication-api", graph=graph)
    assert result["graph"]["truncated"] is True
    assert result["graph"]["warning"] == "Query results limited to 50 rows."
    assert len(result["graph"]["nodes"]) <= 100


def test_query_results_below_limit():
    """Verify queries returning fewer rows than limit are not marked truncated."""

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        if "RETURN path" in cypher:
            return MockResult([[None]] * 10)
        return MockResult(
            [
                [
                    {
                        "id": "service:authentication-api",
                        "type": "service",
                        "title": "Auth",
                    }
                ]
            ]
        )

    graph = MockGraph(handler)
    result = get_blast_radius("service:authentication-api", graph=graph)
    assert result["graph"]["truncated"] is False
    assert result["graph"]["warning"] is None


def test_query_results_exactly_at_limit():
    """Verify queries returning exactly QUERY_LIMIT (50) rows are not marked truncated."""

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        if "RETURN path" in cypher:
            return MockResult([[None]] * QUERY_LIMIT)
        return MockResult(
            [
                [
                    {
                        "id": "service:authentication-api",
                        "type": "service",
                        "title": "Auth",
                    }
                ]
            ]
        )

    graph = MockGraph(handler)
    result = get_blast_radius("service:authentication-api", graph=graph)
    assert result["graph"]["truncated"] is False
    assert result["graph"]["warning"] is None


def test_explicit_query_specific_limit_preservation():
    """Verify queries with explicit custom limits (e.g. LIMIT 20) fetch limit+1 and slice."""
    executed = []

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        executed.append(cypher)
        # Emulate 21 rows returned from DB
        return MockResult([["row"]] * 21)

    graph = MockGraph(handler)
    res = _execute_query(
        graph,
        "MATCH (n:Service) RETURN n LIMIT 20",
        {},
        "test_custom_limit",
    )

    assert "LIMIT 21" in executed[0]
    assert res.truncated is True
    assert len(res.result_set) == 20


def test_aggregate_and_count_queries_not_bounded():
    """Verify aggregate/count queries are never altered with LIMIT."""
    executed = []

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        executed.append(cypher)
        return MockResult([[42]])

    graph = MockGraph(handler)
    res = _execute_query(
        graph,
        "MATCH (s:Service) RETURN count(s)",
        {},
        "test_count",
    )

    assert "LIMIT" not in executed[0]
    assert res.truncated is False
    assert res.result_set[0][0] == 42


def test_single_result_limit_1_queries_not_overfetched():
    """Verify queries ending in LIMIT 1 are not rewritten to LIMIT 2."""
    executed = []

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        executed.append(cypher)
        return MockResult([[None]])

    graph = MockGraph(handler)
    res = _execute_query(
        graph,
        "MATCH (s:Service) RETURN s LIMIT 1",
        {},
        "test_limit_1",
    )

    assert "LIMIT 1" in executed[0]
    assert "LIMIT 2" not in executed[0]
    assert res.truncated is False


def test_shortest_path_cypher_max_three_hops():
    """Verify find_shortest_path specifies *1..3 hops in Cypher."""
    executed = []

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        executed.append(cypher)
        return MockResult([])

    graph = MockGraph(handler)
    find_shortest_path(
        "service:authentication-api",
        "service:data-pipeline",
        graph=graph,
    )

    assert len(executed) == 1
    assert "*1..3" in executed[0]
    assert "*1..5" not in executed[0]


def test_neighborhood_truncation_propagation():
    """Verify get_neighborhood sets truncated=True and warning when results exceed limit."""

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        if "neighbor" in cypher:
            assert "LIMIT 51" in cypher
            return MockResult([[None]] * 51)
        return MockResult(
            [
                [
                    {
                        "id": "service:authentication-api",
                        "type": "service",
                        "title": "Auth",
                    }
                ]
            ]
        )

    graph = MockGraph(handler)
    res = get_neighborhood("service:authentication-api", graph=graph)
    assert res["truncated"] is True
    assert res["warning"] == "Query results limited to 50 rows."


def test_decisions_truncation_propagation():
    """Verify get_decisions_for_service sets truncated=True and warning when results exceed limit."""

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        assert "LIMIT 51" in cypher
        # 8 values per row
        row = (None, None, None, None, None, None, None, None)
        return MockResult([row] * 51)

    graph = MockGraph(handler)
    res = get_decisions_for_service("service:authentication-api", graph=graph)
    assert res["graph"]["truncated"] is True
    assert res["graph"]["warning"] == "Query results limited to 50 rows."


def test_knowledge_gaps_truncation_propagation():
    """Verify get_knowledge_gaps sets truncated=True when any category exceeds 50."""

    def handler(cypher: str, _params: dict[str, Any]) -> MockResult:
        if "NOT ()-[:OWNS]" in cypher:
            return MockResult([[{"id": f"s:{i}", "title": f"S{i}"}] for i in range(51)])
        return MockResult([])

    graph = MockGraph(handler)
    res = get_knowledge_gaps(graph=graph)
    assert res["truncated"] is True
    assert "Gap lists are bounded to 50 records per category" in res["warning"]
