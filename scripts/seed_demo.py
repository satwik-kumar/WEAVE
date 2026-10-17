"""Seed synthetic demo data into FalkorDB knowledge graph.

Exposes run_seed() which initializes schema indexes, loads artifacts
from data/demo/ using structured_json, and batch-upserts them using writer.upsert_many().
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure backend/src is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from weave_brain.domain.models import SyncReport
from weave_brain.graph.client import get_graph
from weave_brain.graph.schema import init_schema
from weave_brain.graph.writer import upsert_many
from weave_brain.ingestion.connectors.structured_json import load_json_directory

DEFAULT_DEMO_DIR = REPO_ROOT / "data" / "demo"


def run_seed(
    data_dir: Path | str = DEFAULT_DEMO_DIR,
    graph: Any = None,
) -> SyncReport:
    """Initialize schema, load demo JSON files, and batch-upsert into FalkorDB.

    Returns the resulting SyncReport from the batch upsert.
    """
    demo_path = Path(data_dir).resolve()
    active_graph = graph if graph is not None else get_graph()

    print("=" * 60)
    print(" WEAVE Brain - Seeding Demo Data into Knowledge Graph")
    print("=" * 60)
    print(f" Source Directory: {demo_path}")

    # 1. Initialize schema indexes
    print(" -> Initializing schema indexes...")
    indexed_labels = init_schema(active_graph)
    print(
        f"    Indexed {len(indexed_labels)} entity labels: {', '.join(sorted(indexed_labels))}"
    )

    # 2. Load demo artifacts
    print(" -> Loading structured demo JSON records...")
    artifacts = load_json_directory(demo_path)
    print(f"    Loaded {len(artifacts)} SourceArtifact records.")

    # 3. Two-phase batch upsert
    print(" -> Executing two-phase batch upsert...")
    report = upsert_many(artifacts, graph=active_graph, source_name="demo-seed")

    # 4. Print summary
    print("-" * 60)
    print(" SYNC REPORT SUMMARY:")
    print(f"  Source:            {report.source}")
    print(f"  Records Processed: {report.records_processed}")
    print(f"  Nodes Created:     {report.nodes_created}")
    print(f"  Nodes Updated:     {report.nodes_updated}")
    print(f"  Edges Created:     {report.edges_created}")
    print(f"  Warnings:          {len(report.warnings)}")
    print(f"  Errors:            {len(report.errors)}")

    if report.warnings:
        print("  Warnings Detail (first 3):")
        for w in report.warnings[:3]:
            print(f"   [WARN] {w}")

    if report.errors:
        print("  Errors Detail:")
        for err in report.errors[:3]:
            print(f"   [ERR]  {err}")

    print("=" * 60)
    if not report.errors:
        print(" RESULT: SEED COMPLETED SUCCESSFULLY")
    else:
        print(" RESULT: SEED COMPLETED WITH ERRORS")
    print("=" * 60)

    return report


if __name__ == "__main__":
    report = run_seed()
    sys.exit(0 if len(report.errors) == 0 else 1)
