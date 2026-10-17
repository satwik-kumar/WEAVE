"""Unit tests for seed_demo and reset_demo scripts using MockGraph."""

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
