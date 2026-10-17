"""Validator for synthetic demo data in data/demo/.

Validates all demo records against weave_brain.domain.models.SourceArtifact,
checks presence of the 19 frozen canonical demo entity IDs, enforces referential
integrity and graph edge direction constraints, and verifies intentional knowledge gaps.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure backend/src is in sys.path so weave_brain can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from pydantic import ValidationError

from weave_brain.domain.models import SourceArtifact
from weave_brain.graph.writer import WHITELISTED_RELATIONSHIPS

DEMO_DIR = REPO_ROOT / "data" / "demo"

DEMO_FILES = [
    "organization.json",
    "services.json",
    "decisions.json",
    "incidents.json",
    "projects.json",
    "documents.json",
]

OFFICIAL_FROZEN_IDS = frozenset({
    "service:authentication-api",
    "service:user-profile-api",
    "service:notification-service",
    "service:data-pipeline",
    "team:platform-engineering",
    "team:backend-core",
    "team:data-infra",
    "person:priya-sharma",
    "person:james-chen",
    "person:aisha-kowalski",
    "person:dev-four",
    "project:auth-modernization",
    "decision:adr-001",
    "decision:adr-002",
    "decision:adr-003",
    "incident:inc-007",
    "ticket:eng-042",
    "repository:acme/auth-api",
    "document:auth-runbook",
})


def load_demo_artifacts() -> tuple[list[SourceArtifact], list[str]]:
    """Load and validate all JSON files from data/demo/ as SourceArtifacts."""
    errors: list[str] = []
    artifacts: list[SourceArtifact] = []

    if not DEMO_DIR.is_dir():
        errors.append(f"Demo directory does not exist: {DEMO_DIR}")
        return artifacts, errors

    for filename in DEMO_FILES:
        filepath = DEMO_DIR / filename
        if not filepath.is_file():
            errors.append(f"Missing required demo file: {filepath}")
            continue

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"Failed to parse JSON in {filename}: {e}")
            continue

        if not isinstance(data, list):
            errors.append(f"Expected JSON list in {filename}, got {type(data).__name__}")
            continue

        for idx, item in enumerate(data):
            try:
                artifact = SourceArtifact.model_validate(item)
                artifacts.append(artifact)
            except (ValidationError, ValueError, TypeError) as e:
                errors.append(f"Validation failed in {filename} item #{idx}: {e}")

    return artifacts, errors


def run_checks() -> bool:
    """Run full checklist verification and print results."""
    print("=" * 65)
    print(" WEAVE Brain - Demo Data Validation Checklist (Developer A)")
    print("=" * 65)

    artifacts, load_errors = load_demo_artifacts()
    all_passed = True

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal all_passed
        status = "[PASS]" if passed else "[FAIL]"
        print(f" {status} {name}")
        if detail and not passed:
            print(f"        -> {detail}")
        if not passed:
            all_passed = False

    # 1. File loading & Model Validation
    check(
        "All 6 demo JSON files exist and are valid JSON",
        len(load_errors) == 0,
        detail="; ".join(load_errors[:3]) if load_errors else "",
    )

    check(
        f"All records parse into SourceArtifact ({len(artifacts)} artifacts)",
        len(artifacts) > 0 and len(load_errors) == 0,
    )

    artifact_map: dict[str, SourceArtifact] = {a.canonical_id: a for a in artifacts}
    all_canonical_ids = set(artifact_map.keys())

    # 2. Frozen ID completeness
    missing_frozen = OFFICIAL_FROZEN_IDS - all_canonical_ids
    check(
        f"All 19 official frozen demo entity IDs present ({len(all_canonical_ids & OFFICIAL_FROZEN_IDS)}/19)",
        len(missing_frozen) == 0,
        detail=f"Missing: {sorted(missing_frozen)}" if missing_frozen else "",
    )

    # 3. Canonical ID format (type:slug)
    malformed_ids = [
        cid for cid in all_canonical_ids
        if ":" not in cid or cid.lower() != cid or " " in cid
    ]
    check(
        "All entity IDs follow canonical type:slug format",
        len(malformed_ids) == 0,
        detail=f"Malformed IDs: {malformed_ids}" if malformed_ids else "",
    )

    # 4. Referential Integrity (all relationship targets exist)
    missing_targets: list[str] = []
    invalid_rel_types: list[str] = []
    incoming_owns: dict[str, list[str]] = {}

    for a in artifacts:
        for edge in a.relationships:
            rel_type = edge[0]
            target_id = edge[1]

            if rel_type not in WHITELISTED_RELATIONSHIPS:
                invalid_rel_types.append(f"{a.canonical_id} -[:{rel_type}]-> {target_id}")

            if target_id not in all_canonical_ids:
                missing_targets.append(
                    f"{a.canonical_id} -[:{rel_type}]-> '{target_id}' (not found)"
                )

            if rel_type == "OWNS":
                incoming_owns.setdefault(target_id, []).append(a.canonical_id)

    check(
        "Referential integrity (all relationship targets resolve to existing entities)",
        len(missing_targets) == 0,
        detail="; ".join(missing_targets[:3]) if missing_targets else "",
    )

    check(
        "Whitelisted relationship types (all edges use approved Cypher rels)",
        len(invalid_rel_types) == 0,
        detail="; ".join(invalid_rel_types[:3]) if invalid_rel_types else "",
    )

    # 5. Graph Edge Directions
    # Service dependencies: caller points to dependency (user-profile-api -> auth-api)
    profile_svc = artifact_map.get("service:user-profile-api")
    profile_deps = [e[1] for e in profile_svc.relationships if e[0] == "DEPENDS_ON"] if profile_svc else []
    check(
        "Service dependency direction (:Service)-[:DEPENDS_ON]->(:Service)",
        "service:authentication-api" in profile_deps,
        detail=f"Expected user-profile-api to depend on auth-api, got {profile_deps}",
    )

    # Decisions: DECIDES_FOR points to service, MOTIVATED_BY points to incident
    adr1 = artifact_map.get("decision:adr-001")
    adr1_targets = {e[0]: e[1] for e in adr1.relationships} if adr1 else {}
    check(
        "Decision lineage (:Decision)-[:DECIDES_FOR]->(:Service) and [:MOTIVATED_BY]->(:Incident)",
        adr1_targets.get("DECIDES_FOR") == "service:authentication-api"
        and adr1_targets.get("MOTIVATED_BY") == "incident:inc-007",
        detail=f"ADR-001 targets: {adr1_targets}",
    )

    # Supersedes: newer points to older (adr-003 -> adr-002)
    adr3 = artifact_map.get("decision:adr-003")
    adr3_supersedes = [e[1] for e in adr3.relationships if e[0] == "SUPERSEDES"] if adr3 else []
    check(
        "Decision supersedes direction (:Decision)-[:SUPERSEDES]->(:Decision)",
        "decision:adr-002" in adr3_supersedes,
        detail=f"Expected adr-003 to supersede adr-002, got {adr3_supersedes}",
    )

    # 6. Intentional Knowledge Gaps
    # Gap 1: service:data-pipeline has NO owner
    pipeline_owners = incoming_owns.get("service:data-pipeline", [])
    check(
        "Intentional Gap 1: service:data-pipeline has NO owner (unowned service)",
        len(pipeline_owners) == 0,
        detail=f"Expected 0 owners for data-pipeline, found: {pipeline_owners}",
    )

    # Gap 2: decision:adr-002 has empty rationale
    adr2 = artifact_map.get("decision:adr-002")
    adr2_rationale = adr2.properties.get("rationale", None) if adr2 else None
    check(
        "Intentional Gap 2: decision:adr-002 has empty rationale",
        adr2_rationale == "",
        detail=f"Expected empty string rationale, got: {adr2_rationale!r}",
    )

    # 7. Edge properties support (3-tuple validation)
    priya = artifact_map.get("person:priya-sharma")
    worked_on_edges = [e for e in priya.relationships if e[0] == "WORKED_ON"] if priya else []
    has_edge_props = any(len(e) == 3 and isinstance(e[2], dict) and e[2].get("role") == "Lead" for e in worked_on_edges)
    check(
        "Edge properties support (3-tuple on WORKED_ON edge)",
        has_edge_props,
        detail=f"Expected 3-tuple with role='Lead', got: {worked_on_edges}",
    )

    print("=" * 65)
    if all_passed:
        print(" RESULT: ALL CHECKS PASSED (19/19 frozen entities verified)")
    else:
        print(" RESULT: VALIDATION FAILED - Please fix the issues above")
    print("=" * 65)

    return all_passed


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
