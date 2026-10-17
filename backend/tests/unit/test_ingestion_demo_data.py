"""Unit tests for demo data artifacts and validation (Developer A scope).

Verifies that all synthetic demo datasets in data/demo/ strictly conform to
SourceArtifact, contain all 19 official frozen demo entity IDs, maintain referential
integrity and canonical edge directions, and model intentional knowledge gaps.
"""

from __future__ import annotations

import json
from pathlib import Path

from weave_brain.domain.models import SourceArtifact
from weave_brain.graph.writer import (
    WHITELISTED_RELATIONSHIPS,
    normalize_relationship,
    prepare_node_properties,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEMO_DIR = REPO_ROOT / "data" / "demo"

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

DEMO_FILES = [
    "organization.json",
    "services.json",
    "decisions.json",
    "incidents.json",
    "projects.json",
    "documents.json",
]


def load_all_artifacts() -> list[SourceArtifact]:
    """Helper to load all demo artifacts across the 6 JSON files."""
    artifacts: list[SourceArtifact] = []
    for filename in DEMO_FILES:
        filepath = DEMO_DIR / filename
        assert filepath.is_file(), f"Missing required demo file: {filepath}"
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list), f"Expected list in {filename}"
        for item in data:
            artifacts.append(SourceArtifact.model_validate(item))
    return artifacts


def test_demo_files_exist_and_parse():
    """Verify all 6 demo dataset files exist and parse into SourceArtifact instances."""
    artifacts = load_all_artifacts()
    assert len(artifacts) == 19
    for artifact in artifacts:
        assert isinstance(artifact, SourceArtifact)
        assert artifact.canonical_id.startswith(f"{artifact.entity_type}:")


def test_official_frozen_demo_ids_present():
    """Verify all 19 official frozen demo entity IDs from AGENTS.md are present."""
    artifacts = load_all_artifacts()
    found_ids = {a.canonical_id for a in artifacts}
    assert found_ids == OFFICIAL_FROZEN_IDS


def test_referential_integrity():
    """Verify every target_canonical_id in relationships exists in the demo dataset."""
    artifacts = load_all_artifacts()
    all_ids = {a.canonical_id for a in artifacts}

    for a in artifacts:
        for edge in a.relationships:
            rel_type, target_id, *_ = edge
            assert rel_type in WHITELISTED_RELATIONSHIPS
            assert target_id in all_ids, (
                f"Dangling edge: {a.canonical_id} -[:{rel_type}]-> {target_id} "
                f"(target does not exist in demo data)"
            )


def test_graph_edge_directions():
    """Verify directional edge rules from AGENTS.md."""
    artifacts = load_all_artifacts()
    by_id = {a.canonical_id: a for a in artifacts}

    # 1. Team OWNS Service
    platform_team = by_id["team:platform-engineering"]
    owns_targets = [e[1] for e in platform_team.relationships if e[0] == "OWNS"]
    assert "service:authentication-api" in owns_targets
    assert "service:notification-service" in owns_targets

    backend_team = by_id["team:backend-core"]
    backend_owns = [e[1] for e in backend_team.relationships if e[0] == "OWNS"]
    assert "service:user-profile-api" in backend_owns

    # 2. Person MEMBER_OF Team
    priya = by_id["person:priya-sharma"]
    priya_teams = [e[1] for e in priya.relationships if e[0] == "MEMBER_OF"]
    assert "team:platform-engineering" in priya_teams

    # 3. Service DEPENDS_ON Service (user-profile-api -> auth-api)
    user_svc = by_id["service:user-profile-api"]
    user_deps = [e[1] for e in user_svc.relationships if e[0] == "DEPENDS_ON"]
    assert "service:authentication-api" in user_deps

    # 4. Service IMPLEMENTED_IN Repository
    auth_svc = by_id["service:authentication-api"]
    auth_repos = [e[1] for e in auth_svc.relationships if e[0] == "IMPLEMENTED_IN"]
    assert "repository:acme/auth-api" in auth_repos

    # 5. Decision DECIDES_FOR Service & MOTIVATED_BY Incident
    adr1 = by_id["decision:adr-001"]
    adr1_decides = [e[1] for e in adr1.relationships if e[0] == "DECIDES_FOR"]
    adr1_motivated = [e[1] for e in adr1.relationships if e[0] == "MOTIVATED_BY"]
    assert "service:authentication-api" in adr1_decides
    assert "incident:inc-007" in adr1_motivated

    # 6. Decision SUPERSEDES Decision (newer -> older)
    adr3 = by_id["decision:adr-003"]
    adr3_supersedes = [e[1] for e in adr3.relationships if e[0] == "SUPERSEDES"]
    assert "decision:adr-002" in adr3_supersedes

    # 7. Document DOCUMENTS Service
    runbook = by_id["document:auth-runbook"]
    doc_targets = [e[1] for e in runbook.relationships if e[0] == "DOCUMENTS"]
    assert "service:authentication-api" in doc_targets

    # 8. Incident & Ticket AFFECTS Service
    inc7 = by_id["incident:inc-007"]
    inc_affects = [e[1] for e in inc7.relationships if e[0] == "AFFECTS"]
    assert "service:authentication-api" in inc_affects

    tick42 = by_id["ticket:eng-042"]
    tick_affects = [e[1] for e in tick42.relationships if e[0] == "AFFECTS"]
    assert "service:authentication-api" in tick_affects

    # 9. Person WORKED_ON Project & Project USES Service
    priya_projects = [e[1] for e in priya.relationships if e[0] == "WORKED_ON"]
    assert "project:auth-modernization" in priya_projects

    proj = by_id["project:auth-modernization"]
    proj_uses = [e[1] for e in proj.relationships if e[0] == "USES"]
    assert "service:authentication-api" in proj_uses


def test_intentional_knowledge_gaps():
    """Verify intentional gaps for Knowledge Health checks."""
    artifacts = load_all_artifacts()
    by_id = {a.canonical_id: a for a in artifacts}

    # Gap 1: service:data-pipeline has NO owner
    all_owns_targets = [
        edge[1]
        for a in artifacts
        for edge in a.relationships
        if edge[0] == "OWNS"
    ]
    assert "service:data-pipeline" not in all_owns_targets

    # Gap 2: decision:adr-002 has empty rationale
    adr2 = by_id["decision:adr-002"]
    assert adr2.properties.get("rationale") == ""


def test_edge_properties_and_writer_compatibility():
    """Verify 3-tuple relationship edges and compatibility with Dev B writer functions."""
    artifacts = load_all_artifacts()

    for artifact in artifacts:
        # Verify prepare_node_properties handles every demo artifact cleanly
        props = prepare_node_properties(artifact)
        assert props["id"] == artifact.canonical_id
        assert props["title"] == artifact.title

        # Verify normalize_relationship handles all relationships cleanly
        for edge in artifact.relationships:
            rel_type, target_id, edge_props = normalize_relationship(edge)
            assert rel_type in WHITELISTED_RELATIONSHIPS
            assert isinstance(target_id, str)
            assert isinstance(edge_props, dict)
