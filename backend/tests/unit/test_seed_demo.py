"""Unit tests for seed_demo and reset_demo scripts using MockGraph and idempotency verification."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from weave_brain.domain.models import SyncReport

# Ensure scripts is importable
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.reset_demo import run_reset
from scripts.seed_demo import DEFAULT_DEMO_DIR, run_seed


class MockQueryResult:
    def __init__(
        self,
        header: list[list[Any]] | None = None,
        result_set: list[list[Any]] | None = None,
        nodes_created: int = 1,
        relationships_created: int = 1,
    ) -> None:
        self.header = header or []
        self.result_set = result_set if result_set is not None else [["ok"]]
        self.nodes_created = float(nodes_created)
        self.relationships_created = float(relationships_created)


class MockGraph:
    """Mock FalkorDB Graph object to verify seeding without requiring Docker."""

    def __init__(self) -> None:
        self.executed_queries: list[tuple[str, dict[str, Any] | None]] = []
        self.deleted = False

    def query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> MockQueryResult:
        self.executed_queries.append((cypher, params))
        if cypher == "CALL db.indexes()":
            header = [[1, "label"], [1, "properties"]]
            return MockQueryResult(header=header, result_set=[])
        if cypher.startswith("CREATE INDEX"):
            return MockQueryResult()
        if cypher.startswith("MERGE (n:"):
            return MockQueryResult(nodes_created=1)
        if cypher.startswith("MATCH ("):
            return MockQueryResult(result_set=[["type"]], relationships_created=1)
        return MockQueryResult()

    def delete(self) -> None:
        self.deleted = True


class StatefulMockGraph:
    """Stateful mock graph tracking nodes and edges to verify 100% idempotency across seed runs."""

    def __init__(self) -> None:
        self.nodes: set[str] = set()
        self.edges: set[tuple[str, str, str]] = set()
        self.executed_queries: list[tuple[str, dict[str, Any] | None]] = []
        self.deleted = False

    def query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> MockQueryResult:
        self.executed_queries.append((cypher, params))
        if cypher == "CALL db.indexes()":
            return MockQueryResult(header=[[1, "label"], [1, "properties"]], result_set=[])
        if cypher.startswith("CREATE INDEX"):
            return MockQueryResult()
        if cypher.startswith("MERGE (n:"):
            nid = params.get("props", {}).get("id") if params else None
            if nid and nid not in self.nodes:
                self.nodes.add(nid)
                return MockQueryResult(nodes_created=1, relationships_created=0)
            return MockQueryResult(nodes_created=0, relationships_created=0)
        if cypher.startswith("MATCH ("):
            src_id = (params.get("src_id") or params.get("sid")) if params else None
            tgt_id = (params.get("tgt_id") or params.get("tid")) if params else None
            if src_id and tgt_id:
                edge_key = (str(src_id), cypher, str(tgt_id))
                if edge_key not in self.edges:
                    self.edges.add(edge_key)
                    return MockQueryResult(result_set=[["type"]], nodes_created=0, relationships_created=1)
                return MockQueryResult(result_set=[["type"]], nodes_created=0, relationships_created=0)
            return MockQueryResult(result_set=[["type"]], nodes_created=0, relationships_created=1)
        return MockQueryResult()

    def delete(self) -> None:
        self.nodes.clear()
        self.edges.clear()
        self.deleted = True


def test_run_seed_with_mock_graph():
    """Verify run_seed initializes schema, loads all 19 artifacts, and returns clean SyncReport."""
    mock_graph = MockGraph()
    report = run_seed(data_dir=DEFAULT_DEMO_DIR, graph=mock_graph)

    assert isinstance(report, SyncReport)
    assert report.source == "demo-seed"
    assert report.records_processed == 19
    assert report.nodes_created == 19
    assert report.edges_created > 0
    assert len(report.errors) == 0

    # Verify schema indexing queries were executed
    cyphers = [q[0] for q in mock_graph.executed_queries]
    assert "CALL db.indexes()" in cyphers
    assert any("CREATE INDEX FOR (n:Service)" in c for c in cyphers)
    assert any("CREATE INDEX FOR (n:Person)" in c for c in cyphers)


def test_run_reset_clears_and_reseeds():
    """Verify run_reset invokes graph.delete() then calls run_seed()."""
    mock_graph = MockGraph()
    report = run_reset(data_dir=DEFAULT_DEMO_DIR, graph=mock_graph)

    assert mock_graph.deleted is True
    assert isinstance(report, SyncReport)
    assert report.records_processed == 19
    assert len(report.errors) == 0


def test_run_seed_idempotency_two_runs_identical_counts():
    """Verify run_seed executed twice produces 100% identical node/edge counts (idempotency)."""
    graph = StatefulMockGraph()

    # First run: initial insertion
    report1 = run_seed(data_dir=DEFAULT_DEMO_DIR, graph=graph)
    nodes_run1 = len(graph.nodes)
    edges_run1 = len(graph.edges)

    assert report1.records_processed == 19
    assert report1.nodes_created == 19
    assert report1.nodes_updated == 0
    assert report1.edges_created == 21
    assert len(report1.errors) == 0
    assert nodes_run1 == 19
    assert edges_run1 == 21

    # Second run: identical re-run against existing graph state
    report2 = run_seed(data_dir=DEFAULT_DEMO_DIR, graph=graph)
    nodes_run2 = len(graph.nodes)
    edges_run2 = len(graph.edges)

    assert report2.records_processed == 19
    assert report2.nodes_created == 0
    assert report2.nodes_updated == 19
    assert report2.edges_created == 0
    assert len(report2.errors) == 0

    # Graph node and edge counts must remain 100% identical
    assert nodes_run1 == nodes_run2 == 19
    assert edges_run1 == edges_run2 == 21
