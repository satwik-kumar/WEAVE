"""Verification script for WEAVE demo graph paths (Developer A).

Validates that the demo data in data/demo/ covers all five core demo paths for
service:authentication-api without requiring a running FalkorDB database.
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO_ROOT / "data" / "demo"
AUTH_SERVICE_ID = "service:authentication-api"


def load_demo_entities(demo_dir: Path = DEMO_DIR) -> dict[str, dict[str, Any]]:
    """Load all JSON files from demo_dir into a canonical_id -> entity dict."""
    entities: dict[str, dict[str, Any]] = {}
    if not demo_dir.is_dir():
        print(f"[ERROR] Demo directory does not exist: {demo_dir}")
        return entities

    for json_file in sorted(demo_dir.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as f:
                records = json.load(f)
            if not isinstance(records, list):
                continue
            for r in records:
                cid = r.get("canonical_id")
                if cid:
                    entities[cid] = r
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Failed to read {json_file.name}: {e}")

    return entities


def verify_demo_paths(demo_dir: Path = DEMO_DIR) -> tuple[bool, dict[str, bool]]:
    """Verify all 5 demo question graph paths for service:authentication-api."""
    entities = load_demo_entities(demo_dir)
    results: dict[str, bool] = {}

    print("=" * 65)
    print(" WEAVE Brain - Demo Data Graph Path Coverage Verification")
    print(f" Target Service: {AUTH_SERVICE_ID}")
    print(f" Loaded Entities: {len(entities)}")
    print("=" * 65)

    # Index relationships
    # outgoing: src -> list of (rel_type, target_id)
    # incoming: tgt -> list of (rel_type, source_id)
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
    # Path 1 (Service Overview):
    # At least one team OWNS service:authentication-api,
    # AND service:authentication-api is IMPLEMENTED_IN a repository.
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

    status1 = "[PASS]" if path1_ok else "[FAIL]"
    print(f" {status1} Path 1: Service Overview")
    print(f"        Owning Team(s): {owning_teams or 'NONE'}")
    print(f"        Repository:     {repos or 'NONE'}")

    # --------------------------------------------------------------------------
    # Path 2 (Decision Rationale):
    # At least one decision DECIDES_FOR service:authentication-api
    # AND is MOTIVATED_BY an incident.
    # --------------------------------------------------------------------------
    qualifying_decisions = []
    for rel, src in incoming.get(AUTH_SERVICE_ID, []) if AUTH_SERVICE_ID in incoming else []:
        if rel == "DECIDES_FOR" and entities.get(src, {}).get("entity_type") == "decision":
            motivated_incidents = [
                tgt for r_rel, tgt in outgoing.get(src, [])
                if r_rel == "MOTIVATED_BY" and entities.get(tgt, {}).get("entity_type") == "incident"
            ]
            if motivated_incidents:
                qualifying_decisions.append((src, motivated_incidents))

    path2_ok = len(qualifying_decisions) >= 1
    results["Path 2 (Decision Rationale)"] = path2_ok

    status2 = "[PASS]" if path2_ok else "[FAIL]"
    print(f" {status2} Path 2: Decision Rationale & Motivation")
    if qualifying_decisions:
        for dec, incs in qualifying_decisions:
            print(f"        Decision: {dec} -> MOTIVATED_BY: {incs}")
    else:
        print("        No decision DECIDES_FOR auth-api that is MOTIVATED_BY an incident.")

    # --------------------------------------------------------------------------
    # Path 3 (Blast Radius):
    # Services DEPENDS_ON service:authentication-api (transitively up to 3 hops),
    # and those dependent services are owned (OWNS) across >= 2 distinct teams.
    # --------------------------------------------------------------------------
    dependent_services: dict[str, int] = {}  # service_id -> hop count
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

    status3 = "[PASS]" if path3_ok else "[FAIL]"
    print(f" {status3} Path 3: Blast Radius (Transitive Dependents & Diverse Owners)")
    print(f"        Transitive Dependents: {dependent_services or 'NONE'}")
    print(f"        Owning Teams ({len(distinct_blast_teams)}): {distinct_blast_teams or 'NONE'}")

    # --------------------------------------------------------------------------
    # Path 4 (Expert Finder):
    # At least 2 distinct person entities have WORKED_ON a project that USES auth-api.
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

    status4 = "[PASS]" if path4_ok else "[FAIL]"
    print(f" {status4} Path 4: Expert Discovery (Person -> Project -> Service)")
    print(f"        Using Project(s): {using_projects or 'NONE'}")
    print(f"        Found Experts ({len(experts)}): {sorted(experts) if experts else 'NONE'}")

    # --------------------------------------------------------------------------
    # Path 5 (Onboarding / Active Risk):
    # At least one open incident (status == 'open' or non-resolved)
    # AND at least one ticket AFFECTS service:authentication-api.
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

    status5 = "[PASS]" if path5_ok else "[FAIL]"
    print(f" {status5} Path 5: Onboarding & Active Risk (Open Incidents & Tickets)")
    print(f"        All Affecting Incidents:  {affects_incidents or 'NONE'}")
    print(f"        Open Incident(s):         {open_incidents or 'NONE (FAILED: incident:inc-007 is resolved)'}")
    print(f"        Affecting Ticket(s):      {affects_tickets or 'NONE'}")

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    all_passed = all(results.values())
    print("=" * 65)
    if all_passed:
        print(" RESULT: ALL 5 DEMO PATH CHECKS PASSED")
    else:
        failed_paths = [p for p, ok in results.items() if not ok]
        print(f" RESULT: {len(failed_paths)}/5 PATH CHECKS FAILED: {', '.join(failed_paths)}")
    print("=" * 65)

    return all_passed, results


if __name__ == "__main__":
    success, _ = verify_demo_paths()
    sys.exit(0 if success else 1)
