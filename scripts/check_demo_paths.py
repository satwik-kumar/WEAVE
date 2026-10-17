"""Verification script for WEAVE demo graph paths, freshness, gaps, and integrity.

Validates:
1. Absence of duplicate canonical IDs across all JSON files.
2. Freshness spread (fresh <30d, aging 30-90d, stale >90d) relative to Oct 18, 2026.
3. Deliberate knowledge gaps (unowned service, missing rationale, undocumented service).
4. Supersession linkage (adr-003 SUPERSEDES adr-002).
5. Five core demo graph traversal paths for service:authentication-api.
"""

from __future__ import annotations

import json
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO_ROOT / "data" / "demo"
AUTH_SERVICE_ID = "service:authentication-api"
BENCHMARK_DATE = datetime(2026, 10, 18, 0, 0, 0, tzinfo=UTC)


def load_demo_entities(
    demo_dir: Path = DEMO_DIR,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    """Load all JSON files from demo_dir into a canonical_id -> entity dict.

    Also tracks duplicate IDs across files.
    Returns (entities_dict, duplicate_id_map).
    """
    entities: dict[str, dict[str, Any]] = {}
    seen_ids: dict[str, list[str]] = {}

    if not demo_dir.is_dir():
        print(f"[ERROR] Demo directory does not exist: {demo_dir}")
        return entities, {}

    for json_file in sorted(demo_dir.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as f:
                records = json.load(f)
            if not isinstance(records, list):
                continue
            for r in records:
                cid = r.get("canonical_id")
                if cid:
                    seen_ids.setdefault(cid, []).append(json_file.name)
                    entities[cid] = r
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Failed to read {json_file.name}: {e}")

    duplicate_ids = {cid: files for cid, files in seen_ids.items() if len(files) > 1}
    return entities, duplicate_ids


def parse_timestamp(entity: dict[str, Any]) -> datetime | None:
    """Parse ingested_at or last_updated from entity."""
    val = entity.get("ingested_at") or entity.get("properties", {}).get("last_updated")
    if not val:
        return None
    if isinstance(val, str):
        try:
            clean = val.replace("Z", "+00:00")
            if len(clean) == 10:  # YYYY-MM-DD
                dt = datetime.fromisoformat(f"{clean}T00:00:00+00:00")
            else:
                dt = datetime.fromisoformat(clean)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except (ValueError, TypeError):
            return None
    return None


def verify_demo_paths(demo_dir: Path = DEMO_DIR) -> tuple[bool, dict[str, bool]]:
    """Run full verification on demo data integrity, freshness, gaps, and paths."""
    entities, duplicate_ids = load_demo_entities(demo_dir)
    results: dict[str, bool] = {}

    print("=" * 65)
    print(" WEAVE Brain - Demo Data Integrity & Path Verification (A-R2)")
    print(f" Target Service:   {AUTH_SERVICE_ID}")
    print(f" Loaded Entities:  {len(entities)}")
    print(f" Benchmark Date:   {BENCHMARK_DATE.strftime('%Y-%m-%d')}")
    print("=" * 65)

    # --------------------------------------------------------------------------
    # Integrity Check: Duplicate IDs across all JSON files
    # --------------------------------------------------------------------------
    has_no_duplicates = len(duplicate_ids) == 0
    results["Duplicate ID Check"] = has_no_duplicates
    status_dup = "[PASS]" if has_no_duplicates else "[FAIL]"
    print(f" {status_dup} Duplicate ID Check (across all demo JSON files)")
    if not has_no_duplicates:
        for cid, files in duplicate_ids.items():
            print(f"        -> Duplicate '{cid}' found in: {files}")
    else:
        print("        0 duplicates found across all JSON files.")

    # --------------------------------------------------------------------------
    # Freshness Spread Analysis (<30d, 30-90d, >90d)
    # --------------------------------------------------------------------------
    fresh_nodes: list[str] = []
    aging_nodes: list[str] = []
    stale_nodes: list[str] = []
    untracked_nodes: list[str] = []

    for cid, entity in entities.items():
        dt = parse_timestamp(entity)
        if dt is None:
            untracked_nodes.append(cid)
            continue
        age_days = (BENCHMARK_DATE - dt).days
        if age_days < 30:
            fresh_nodes.append(cid)
        elif age_days <= 90:
            aging_nodes.append(cid)
        else:
            stale_nodes.append(cid)

    freshness_ok = len(fresh_nodes) > 0 and len(aging_nodes) > 0 and len(stale_nodes) > 0
    results["Freshness Spread"] = freshness_ok
    status_fresh = "[PASS]" if freshness_ok else "[FAIL]"
    print(f" {status_fresh} Freshness Spread (relative to {BENCHMARK_DATE.strftime('%Y-%m-%d')})")
    print(f"        Fresh (<30d):  {len(fresh_nodes)} nodes (e.g., {fresh_nodes[:3]})")
    print(f"        Aging (30-90d): {len(aging_nodes)} nodes (e.g., {aging_nodes[:3]})")
    print(f"        Stale (>90d):  {len(stale_nodes)} nodes (e.g., {stale_nodes[:3]})")

    # --------------------------------------------------------------------------
    # Build Relationship Graph Index
    # --------------------------------------------------------------------------
    outgoing: dict[str, list[tuple[str, str]]] = {cid: [] for cid in entities}
    incoming: dict[str, list[tuple[str, str]]] = {cid: [] for cid in entities}

    for cid, entity in entities.items():
        rels = entity.get("relationships", [])
        for edge in rels:
            if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                rel_type = edge[0]
                target_id = edge[1]
                outgoing[cid].append((rel_type, target_id))
                if target_id not in incoming:
                    incoming[target_id] = []
                incoming[target_id].append((rel_type, cid))

    # --------------------------------------------------------------------------
    # Deliberate Knowledge Gaps Verification
    # --------------------------------------------------------------------------
    # Gap 1: service:data-pipeline has NO owner
    pipeline_owners = [
        src for rel, src in incoming.get("service:data-pipeline", [])
        if rel == "OWNS" and entities.get(src, {}).get("entity_type") == "team"
    ]
    gap1_ok = len(pipeline_owners) == 0

    # Gap 2: decision:adr-002 has empty rationale
    adr2_entity = entities.get("decision:adr-002", {})
    adr2_rationale = adr2_entity.get("properties", {}).get("rationale")
    gap2_ok = adr2_rationale == ""

    # Gap 3: At least one service has NO linked document
    all_services = [cid for cid, e in entities.items() if e.get("entity_type") == "service"]
    undocumented_services = [
        sid for sid in all_services
        if not any(rel == "DOCUMENTS" for rel, _ in incoming.get(sid, []))
    ]
    gap3_ok = len(undocumented_services) >= 1

    gaps_ok = gap1_ok and gap2_ok and gap3_ok
    results["Deliberate Knowledge Gaps"] = gaps_ok
    status_gaps = "[PASS]" if gaps_ok else "[FAIL]"
    print(f" {status_gaps} Deliberate Knowledge Gaps")
    print(f"        Gap 1 (Unowned Service):    service:data-pipeline (owners={pipeline_owners})")
    print(f"        Gap 2 (Missing Rationale):  decision:adr-002 (rationale={adr2_rationale!r})")
    print(f"        Gap 3 (Undocumented):       {undocumented_services}")

    # --------------------------------------------------------------------------
    # Supersession Linkage Verification (adr-003 SUPERSEDES adr-002)
    # --------------------------------------------------------------------------
    supersedes_targets = [
        tgt for rel, tgt in outgoing.get("decision:adr-003", [])
        if rel == "SUPERSEDES"
    ]
    supersession_ok = "decision:adr-002" in supersedes_targets
    results["Decision Supersession"] = supersession_ok
    status_sup = "[PASS]" if supersession_ok else "[FAIL]"
    print(f" {status_sup} Decision Supersession (decision:adr-003 -> decision:adr-002)")
    print(f"        Supersedes Target(s): {supersedes_targets}")

    # --------------------------------------------------------------------------
    # Path 1 (Service Overview)
    # --------------------------------------------------------------------------
    owning_teams = [
        src for rel, src in incoming.get(AUTH_SERVICE_ID, [])
        if rel == "OWNS" and entities.get(src, {}).get("entity_type") == "team"
    ]
    repos = [
        tgt for rel, tgt in outgoing.get(AUTH_SERVICE_ID, [])
        if rel == "IMPLEMENTED_IN" and entities.get(tgt, {}).get("entity_type") == "repository"
    ]
    path1_ok = len(owning_teams) >= 1 and len(repos) >= 1
    results["Path 1 (Service Overview)"] = path1_ok
    print(f" {'[PASS]' if path1_ok else '[FAIL]'} Path 1: Service Overview")
    print(f"        Owning Team(s): {owning_teams} | Repository: {repos}")

    # --------------------------------------------------------------------------
    # Path 2 (Decision Rationale)
    # --------------------------------------------------------------------------
    qualifying_decisions = []
    for rel, src in incoming.get(AUTH_SERVICE_ID, []):
        if rel == "DECIDES_FOR" and entities.get(src, {}).get("entity_type") == "decision":
            motivated_incidents = [
                tgt for r_rel, tgt in outgoing.get(src, [])
                if r_rel == "MOTIVATED_BY" and entities.get(tgt, {}).get("entity_type") == "incident"
            ]
            if motivated_incidents:
                qualifying_decisions.append((src, motivated_incidents))

    path2_ok = len(qualifying_decisions) >= 1
    results["Path 2 (Decision Rationale)"] = path2_ok
    print(f" {'[PASS]' if path2_ok else '[FAIL]'} Path 2: Decision Rationale")
    print(f"        Decisions & Incidents: {qualifying_decisions}")

    # --------------------------------------------------------------------------
    # Path 3 (Blast Radius)
    # --------------------------------------------------------------------------
    dependent_services: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque([(AUTH_SERVICE_ID, 0)])
    visited = {AUTH_SERVICE_ID}

    while queue:
        curr_id, hops = queue.popleft()
        if hops >= 3:
            continue
        for rel, src in incoming.get(curr_id, []):
            if (
                rel == "DEPENDS_ON"
                and entities.get(src, {}).get("entity_type") == "service"
                and src not in visited
            ):
                visited.add(src)
                dependent_services[src] = hops + 1
                queue.append((src, hops + 1))

    blast_owning_teams: dict[str, list[str]] = {}
    for dep_svc in dependent_services:
        for rel, src in incoming.get(dep_svc, []):
            if rel == "OWNS" and entities.get(src, {}).get("entity_type") == "team":
                blast_owning_teams.setdefault(src, []).append(dep_svc)

    distinct_blast_teams = list(blast_owning_teams.keys())
    path3_ok = len(dependent_services) >= 1 and len(distinct_blast_teams) >= 2
    results["Path 3 (Blast Radius)"] = path3_ok
    print(f" {'[PASS]' if path3_ok else '[FAIL]'} Path 3: Blast Radius (Diverse Owners)")
    print(f"        Dependents: {dependent_services} | Owning Teams ({len(distinct_blast_teams)}): {distinct_blast_teams}")

    # --------------------------------------------------------------------------
    # Path 4 (Expert Finder)
    # --------------------------------------------------------------------------
    using_projects = [
        src for rel, src in incoming.get(AUTH_SERVICE_ID, [])
        if rel == "USES" and entities.get(src, {}).get("entity_type") == "project"
    ]
    experts: set[str] = set()
    for proj in using_projects:
        for rel, src in incoming.get(proj, []):
            if rel == "WORKED_ON" and entities.get(src, {}).get("entity_type") == "person":
                experts.add(src)

    path4_ok = len(experts) >= 2
    results["Path 4 (Expert Finder)"] = path4_ok
    print(f" {'[PASS]' if path4_ok else '[FAIL]'} Path 4: Expert Discovery")
    print(f"        Using Projects: {using_projects} | Experts ({len(experts)}): {sorted(experts)}")

    # --------------------------------------------------------------------------
    # Path 5 (Onboarding / Active Risk)
    # --------------------------------------------------------------------------
    affects_incidents = [
        src for rel, src in incoming.get(AUTH_SERVICE_ID, [])
        if rel == "AFFECTS" and entities.get(src, {}).get("entity_type") == "incident"
    ]
    open_incidents = [
        inc for inc in affects_incidents
        if entities.get(inc, {}).get("properties", {}).get("status", "").lower() != "resolved"
    ]
    affects_tickets = [
        src for rel, src in incoming.get(AUTH_SERVICE_ID, [])
        if rel == "AFFECTS" and entities.get(src, {}).get("entity_type") == "ticket"
    ]

    path5_ok = len(open_incidents) >= 1 and len(affects_tickets) >= 1
    results["Path 5 (Onboarding / Active Risk)"] = path5_ok
    print(f" {'[PASS]' if path5_ok else '[FAIL]'} Path 5: Onboarding & Active Risk")
    print(f"        Open Incident(s): {open_incidents} | Affecting Ticket(s): {affects_tickets}")

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    all_passed = all(results.values())
    print("=" * 65)
    if all_passed:
        print(" RESULT: ALL INTEGRITY, FRESHNESS, GAP & PATH CHECKS PASSED")
    else:
        failed_checks = [k for k, ok in results.items() if not ok]
        print(f" RESULT: {len(failed_checks)} CHECKS FAILED: {', '.join(failed_checks)}")
    print("=" * 65)

    return all_passed, results


if __name__ == "__main__":
    success, _ = verify_demo_paths()
    sys.exit(0 if success else 1)
