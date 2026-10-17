"""Reset FalkorDB graph and re-seed clean synthetic demo data.

Exposes run_reset() which deletes the current graph and re-runs run_seed().
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

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from scripts.seed_demo import DEFAULT_DEMO_DIR, run_seed

from weave_brain.domain.models import SyncReport
from weave_brain.graph.client import get_graph


def run_reset(
    data_dir: Path | str = DEFAULT_DEMO_DIR,
    graph: Any = None,
) -> SyncReport:
    """Delete all nodes and edges from the graph, then re-seed demo data."""
    active_graph = graph if graph is not None else get_graph()

    print("=" * 60)
    print(" WEAVE Brain - Resetting Knowledge Graph")
    print("=" * 60)

    try:
        print(" -> Deleting existing graph...")
        active_graph.delete()
        print("    Graph cleared successfully.")
    except (ResponseError, RedisConnectionError, ConnectionError, OSError) as e:
        print(f"    Notice during graph delete (tolerated if non-existent): {e}")

    return run_seed(data_dir=data_dir, graph=active_graph)


if __name__ == "__main__":
    report = run_reset()
    sys.exit(0 if len(report.errors) == 0 else 1)
