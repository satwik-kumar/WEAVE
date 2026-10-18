"""In-memory stub fixtures for graph queries and offline development.

Provides offline data using frozen canonical entity IDs from AGENTS.md.
Zero network or FalkorDB database connection required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from weave_brain.domain.models import SourceArtifact


def get_catalog_stub() -> dict[str, Any]:
    """Read the approved synthetic catalog; timestamps stay unknown if not supplied."""
    import json

    data = Path(__file__).resolve().parents[4] / "data" / "demo"
    artifacts = []
    for path in sorted(data.glob("*.json")):
        artifacts.extend(
            SourceArtifact.model_validate(row)
            for row in json.loads(path.read_text(encoding="utf-8"))
        )
    if not artifacts:
        raise ValueError("Development fixture catalog is missing")
    nodes = []
    edges = []
    known = {a.canonical_id for a in artifacts}
    for a in artifacts:
        props = {**a.properties, "source_id": a.source_id, "source_type": a.source_type}
        if a.source_url:
            props["source_url"] = a.source_url
        if "ingested_at" in a.model_fields_set:
            props["ingested_at"] = a.ingested_at.isoformat()
        nodes.append(
            {
                "id": a.canonical_id,
                "type": a.entity_type,
                "title": a.title,
                "properties": props,
            }
        )
        for relationship in a.relationships:
            rel, target = relationship[:2]
            if target in known:
                edges.append(
                    {
                        "id": f"{a.canonical_id}::{rel}::{target}",
                        "source_id": a.canonical_id,
                        "target_id": target,
                        "relationship_type": rel,
                        "label": rel,
                        "properties": relationship[2] if len(relationship) == 3 else {},
                    }
                )
    return {
        "nodes": nodes,
        "edges": edges,
        "warning": "Development fixture data.",
        "truncated": False,
    }


def get_catalog_neighborhood_stub(node_id: str, depth: int = 2) -> dict[str, Any]:
    catalog = get_catalog_stub()
    reached = {node_id}
    for _ in range(min(3, max(1, depth))):
        reached |= {
            endpoint
            for e in catalog["edges"]
            if e["source_id"] in reached or e["target_id"] in reached
            for endpoint in (e["source_id"], e["target_id"])
        }
    return {
        **catalog,
        "nodes": [n for n in catalog["nodes"] if n["id"] in reached],
        "edges": [
            e
            for e in catalog["edges"]
            if e["source_id"] in reached and e["target_id"] in reached
        ],
        "root_node_ids": [node_id],
    }


def get_catalog_overview_stub(service_id: str) -> dict[str, Any] | None:
    graph = get_catalog_neighborhood_stub(service_id, 1)
    nodes = {n["id"]: n for n in graph["nodes"]}
    if service_id not in nodes or nodes[service_id]["type"] != "service":
        return None

    def related(rel: str, incoming: bool):
        return [
            nodes[e["source_id"] if incoming else e["target_id"]]
            for e in graph["edges"]
            if e["relationship_type"] == rel
            and e["target_id" if incoming else "source_id"] == service_id
        ]

    owners = related("OWNS", True)
    return {
        "service": nodes[service_id],
        "team": owners[0] if owners else None,
        "repositories": related("IMPLEMENTED_IN", False),
        "decisions": related("DECIDES_FOR", True),
        "documents": related("DOCUMENTS", True),
        "dependents": related("DEPENDS_ON", True),
        "graph": graph,
    }


def get_catalog_decisions_stub(service_id: str) -> dict[str, Any]:
    catalog = get_catalog_stub()
    decision_ids = {
        e["source_id"]
        for e in catalog["edges"]
        if e["relationship_type"] == "DECIDES_FOR" and e["target_id"] == service_id
    }
    ids = {*decision_ids, service_id}
    for _ in range(2):
        ids |= {
            endpoint
            for e in catalog["edges"]
            if e["relationship_type"] in ("SUPERSEDES", "MOTIVATED_BY")
            and (e["source_id"] in ids or e["target_id"] in ids)
            for endpoint in (e["source_id"], e["target_id"])
        }
    graph = {
        **catalog,
        "nodes": [n for n in catalog["nodes"] if n["id"] in ids],
        "edges": [
            e
            for e in catalog["edges"]
            if e["source_id"] in ids and e["target_id"] in ids
        ],
        "root_node_ids": [service_id],
    }
    evidence = [
        {
            "source_id": n["properties"]["source_id"],
            "source_type": n["properties"]["source_type"],
            "title": n["title"],
            "excerpt": n["properties"].get("rationale") or "No rationale recorded.",
            "relationship_path": [
                n["id"],
                next(
                    (
                        e["target_id"]
                        for e in graph["edges"]
                        if e["source_id"] == n["id"]
                        and e["relationship_type"] == "MOTIVATED_BY"
                    ),
                    service_id,
                ),
            ],
        }
        for n in graph["nodes"]
        if n["id"] in decision_ids
    ]
    return {
        "service_id": service_id,
        "decisions": [n for n in graph["nodes"] if n["id"] in decision_ids],
        "evidence": evidence,
        "graph": graph,
    }


def get_catalog_blast_stub(service_id: str, depth: int = 3) -> dict[str, Any]:
    catalog = get_catalog_stub()
    reached = {service_id}
    for _ in range(min(3, depth)):
        reached |= {
            e["source_id"]
            for e in catalog["edges"]
            if e["relationship_type"] == "DEPENDS_ON" and e["target_id"] in reached
        }
    graph = {
        **catalog,
        "nodes": [n for n in catalog["nodes"] if n["id"] in reached],
        "edges": [
            e
            for e in catalog["edges"]
            if e["relationship_type"] == "DEPENDS_ON"
            and e["source_id"] in reached
            and e["target_id"] in reached
        ],
        "root_node_ids": [service_id],
    }
    return {
        "service_id": service_id,
        "affected_services": [n for n in graph["nodes"] if n["id"] != service_id],
        "graph": graph,
    }


def find_catalog_experts_stub(service_id: str) -> list[dict[str, Any]]:
    catalog = get_catalog_stub()
    projects = {
        e["source_id"]
        for e in catalog["edges"]
        if e["relationship_type"] == "USES" and e["target_id"] == service_id
    }
    people = {
        e["source_id"]
        for e in catalog["edges"]
        if e["relationship_type"] == "WORKED_ON" and e["target_id"] in projects
    }
    return [n for n in catalog["nodes"] if n["id"] in people]


def get_catalog_health_stub() -> dict[str, Any]:
    catalog = get_catalog_stub()
    services = [n for n in catalog["nodes"] if n["type"] == "service"]
    decisions = [n for n in catalog["nodes"] if n["type"] == "decision"]
    incidents = [n for n in catalog["nodes"] if n["type"] == "incident"]
    owned = {
        e["target_id"] for e in catalog["edges"] if e["relationship_type"] == "OWNS"
    }
    documented = {
        e["target_id"]
        for e in catalog["edges"]
        if e["relationship_type"] == "DOCUMENTS"
    }
    rationale = [
        n for n in decisions if str(n["properties"].get("rationale", "")).strip()
    ]
    resolved = [n for n in incidents if n["properties"].get("status") == "resolved"]
    metrics = {
        "services_owned": len(owned) / len(services) if services else 1,
        "decisions_rationale": len(rationale) / len(decisions) if decisions else 1,
        "incidents_resolved": len(resolved) / len(incidents) if incidents else 1,
        "services_documented": len(documented) / len(services) if services else 1,
    }
    gaps = {
        "unowned_services": [n for n in services if n["id"] not in owned],
        "decisions_missing_rationale": [n for n in decisions if n not in rationale],
        "undocumented_services": [n for n in services if n["id"] not in documented],
    }
    gaps["total_gaps"] = sum(len(items) for items in gaps.values())
    return {
        "health_score": round(sum(metrics.values()) / 4 * 100, 1),
        "metrics": {k: round(v, 2) for k, v in metrics.items()},
        "counts": {
            "total_services": len(services),
            "owned_services": len(owned),
            "total_decisions": len(decisions),
            "decisions_with_rationale": len(rationale),
            "total_incidents": len(incidents),
            "resolved_incidents": len(resolved),
            "documented_services": len(documented),
        },
        "gaps": gaps,
        "graph": catalog,
        "warnings": ["Development fixture data; no live database retrieval."],
    }


def get_service_overview_stub(
    service_id: str = "service:authentication-api",
) -> dict[str, Any]:
    """Return service overview data including team, repos, decisions, and graph view."""
    sid = service_id or "service:authentication-api"

    service_node = {
        "id": sid,
        "type": "service",
        "title": "Authentication API",
        "properties": {
            "description": "Core authentication and JWT token issuance service",
            "language": "Python",
            "tech_stack": "FastAPI, FalkorDB, Redis",
            "status": "production",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }
    team_node = {
        "id": "team:platform-engineering",
        "type": "team",
        "title": "Platform Engineering",
        "properties": {
            "slack_channel": "#platform-eng",
            "description": "Core infrastructure and identity platforms",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }
    repo_node = {
        "id": "repository:acme/auth-api",
        "type": "repository",
        "title": "acme/auth-api",
        "properties": {
            "url": "https://github.com/acme/auth-api",
            "language": "Python",
            "default_branch": "main",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }
    doc_node = {
        "id": "document:auth-runbook",
        "type": "document",
        "title": "Auth Service Operations Runbook",
        "properties": {
            "source_url": "https://wiki.acme.internal/docs/auth-runbook",
            "content_excerpt": "Emergency procedures and token rotation runbook for auth-api",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }
    adr1_node = {
        "id": "decision:adr-001",
        "type": "decision",
        "title": "Token expiry 24h policy",
        "properties": {
            "status": "accepted",
            "decision_date": "2025-11-15",
            "rationale": "Mitigate risk of stolen long-lived tokens following incident INC-007",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }

    edges = [
        {
            "id": f"team:platform-engineering::OWNS::{sid}",
            "source_id": "team:platform-engineering",
            "target_id": sid,
            "relationship_type": "OWNS",
            "label": "OWNS",
            "properties": {},
        },
        {
            "id": f"{sid}::IMPLEMENTED_IN::repository:acme/auth-api",
            "source_id": sid,
            "target_id": "repository:acme/auth-api",
            "relationship_type": "IMPLEMENTED_IN",
            "label": "IMPLEMENTED_IN",
            "properties": {},
        },
        {
            "id": f"document:auth-runbook::DOCUMENTS::{sid}",
            "source_id": "document:auth-runbook",
            "target_id": sid,
            "relationship_type": "DOCUMENTS",
            "label": "DOCUMENTS",
            "properties": {},
        },
        {
            "id": f"decision:adr-001::DECIDES_FOR::{sid}",
            "source_id": "decision:adr-001",
            "target_id": sid,
            "relationship_type": "DECIDES_FOR",
            "label": "DECIDES_FOR",
            "properties": {},
        },
    ]

    evidence = [
        {
            "source_id": "decision:adr-001",
            "title": "Token expiry 24h policy",
            "source_type": "decision",
            "excerpt": "All tokens must expire within 24 hours.",
            "source_url": None,
            "relationship_path": ["decision:adr-001", sid],
        },
        {
            "source_id": "document:auth-runbook",
            "title": "Auth Service Operations Runbook",
            "source_type": "document",
            "excerpt": "Runbook covering operational steps and key rotations for auth-api.",
            "source_url": "https://wiki.acme.internal/docs/auth-runbook",
            "relationship_path": ["document:auth-runbook", sid],
        },
    ]

    graph = {
        "nodes": [service_node, team_node, repo_node, doc_node, adr1_node],
        "edges": edges,
        "root_node_ids": [sid],
        "highlighted_path_ids": [],
        "truncated": False,
        "warning": None,
    }

    return {
        "service": service_node,
        "team": team_node,
        "repositories": [repo_node],
        "decisions": [adr1_node],
        "dependents": ["service:user-profile-api", "service:notification-service"],
        "evidence": evidence,
        "graph": graph,
    }


def get_decisions_for_service_stub(
    service_id: str = "service:authentication-api",
) -> dict[str, Any]:
    """Return architectural decisions governing the service, including supersedes and incidents."""
    sid = service_id or "service:authentication-api"

    adr1 = {
        "id": "decision:adr-001",
        "type": "decision",
        "title": "Token expiry 24h policy",
        "properties": {
            "status": "accepted",
            "rationale": "Mandate 24-hour token expiration following token leak",
            "decision_date": "2025-11-15",
            "motivated_by": "incident:inc-007",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }
    adr2 = {
        "id": "decision:adr-002",
        "type": "decision",
        "title": "Service mesh adoption",
        "properties": {
            "status": "superseded",
            "rationale": "",
            "decision_date": "2025-06-10",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }
    adr3 = {
        "id": "decision:adr-003",
        "type": "decision",
        "title": "Envoy proxy standard",
        "properties": {
            "status": "accepted",
            "rationale": "Standardize sidecar proxy on Envoy across Kubernetes clusters",
            "decision_date": "2025-12-01",
            "supersedes": "decision:adr-002",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }
    inc7 = {
        "id": "incident:inc-007",
        "type": "incident",
        "title": "Stolen long-lived token exploited",
        "properties": {
            "severity": "P1",
            "status": "resolved",
            "summary": "Compromised credential led to unauthorized API access.",
            "resolved_at": "2025-11-14T18:00:00Z",
        },
        "on_highlighted_path": False,
        "is_stale": False,
    }

    edges = [
        {
            "id": f"decision:adr-001::DECIDES_FOR::{sid}",
            "source_id": "decision:adr-001",
            "target_id": sid,
            "relationship_type": "DECIDES_FOR",
            "label": "DECIDES_FOR",
            "properties": {},
        },
        {
            "id": "decision:adr-001::MOTIVATED_BY::incident:inc-007",
            "source_id": "decision:adr-001",
            "target_id": "incident:inc-007",
            "relationship_type": "MOTIVATED_BY",
            "label": "MOTIVATED_BY",
            "properties": {},
        },
        {
            "id": f"decision:adr-002::DECIDES_FOR::{sid}",
            "source_id": "decision:adr-002",
            "target_id": sid,
            "relationship_type": "DECIDES_FOR",
            "label": "DECIDES_FOR",
            "properties": {},
        },
        {
            "id": "decision:adr-003::SUPERSEDES::decision:adr-002",
            "source_id": "decision:adr-003",
            "target_id": "decision:adr-002",
            "relationship_type": "SUPERSEDES",
            "label": "SUPERSEDES",
            "properties": {},
        },
        {
            "id": f"decision:adr-003::DECIDES_FOR::{sid}",
            "source_id": "decision:adr-003",
            "target_id": sid,
            "relationship_type": "DECIDES_FOR",
            "label": "DECIDES_FOR",
            "properties": {},
        },
    ]

    evidence = [
        {
            "source_id": "decision:adr-001",
            "title": "Token expiry 24h policy",
            "source_type": "decision",
            "excerpt": "Mandate 24-hour token expiration following incident INC-007",
            "source_url": None,
            "relationship_path": ["decision:adr-001", "incident:inc-007"],
        },
        {
            "source_id": "decision:adr-003",
            "title": "Envoy proxy standard",
            "source_type": "decision",
            "excerpt": "Standardize sidecar proxy on Envoy across Kubernetes clusters, superseding ADR-002",
            "source_url": None,
            "relationship_path": ["decision:adr-003", "decision:adr-002"],
        },
    ]

    graph = {
        "nodes": [get_service_overview_stub(sid)["service"], adr1, adr2, adr3, inc7],
        "edges": edges,
        "root_node_ids": ["decision:adr-001", "decision:adr-003"],
        "highlighted_path_ids": [],
        "truncated": False,
        "warning": None,
    }

    return {
        "service_id": sid,
        "decisions": [adr1, adr2, adr3],
        "evidence": evidence,
        "graph": graph,
    }


def get_blast_radius_stub(
    service_id: str = "service:authentication-api",
) -> dict[str, Any]:
    """Return blast radius data: what breaks if service_id goes down (incoming DEPENDS_ON)."""
    sid = service_id or "service:authentication-api"

    target_service = {
        "id": sid,
        "type": "service",
        "title": "Authentication API",
        "properties": {"status": "production"},
        "on_highlighted_path": True,
        "is_stale": False,
    }
    dep1 = {
        "id": "service:user-profile-api",
        "type": "service",
        "title": "User Profile API",
        "properties": {
            "owner": "team:backend-core",
            "status": "production",
            "description": "User profile management service depending on auth-api",
        },
        "on_highlighted_path": True,
        "is_stale": False,
    }
    dep2 = {
        "id": "service:notification-service",
        "type": "service",
        "title": "Notification Service",
        "properties": {
            "owner": "team:platform-engineering",
            "status": "production",
            "description": "Notification delivery service depending on auth-api",
        },
        "on_highlighted_path": True,
        "is_stale": False,
    }

    edges = [
        {
            "id": f"service:user-profile-api::DEPENDS_ON::{sid}",
            "source_id": "service:user-profile-api",
            "target_id": sid,
            "relationship_type": "DEPENDS_ON",
            "label": "DEPENDS_ON",
            "properties": {},
        },
        {
            "id": f"service:notification-service::DEPENDS_ON::{sid}",
            "source_id": "service:notification-service",
            "target_id": sid,
            "relationship_type": "DEPENDS_ON",
            "label": "DEPENDS_ON",
            "properties": {},
        },
    ]

    evidence = [
        {
            "source_id": "service:user-profile-api",
            "title": "User Profile API",
            "source_type": "service",
            "excerpt": "service:user-profile-api depends on service:authentication-api and will fail if auth goes down",
            "source_url": None,
            "relationship_path": ["service:user-profile-api", sid],
        },
        {
            "source_id": "service:notification-service",
            "title": "Notification Service",
            "source_type": "service",
            "excerpt": "service:notification-service depends on service:authentication-api and will fail if auth goes down",
            "source_url": None,
            "relationship_path": ["service:notification-service", sid],
        },
    ]

    graph = {
        "nodes": [target_service, dep1, dep2],
        "edges": edges,
        "root_node_ids": [sid],
        "highlighted_path_ids": [
            f"service:user-profile-api::DEPENDS_ON::{sid}",
            f"service:notification-service::DEPENDS_ON::{sid}",
        ],
        "truncated": False,
        "warning": None,
    }

    return {
        "service_id": sid,
        "affected_services": [dep1, dep2],
        "evidence": evidence,
        "graph": graph,
    }


def find_experts_stub(
    service_id: str = "service:authentication-api",
) -> list[dict[str, Any]]:
    """Return engineers connected to service_id via team ownership and project initiatives."""
    return [
        {
            "id": "person:priya-sharma",
            "type": "person",
            "title": "Priya Sharma",
            "properties": {
                "role": "Staff Engineer / Tech Lead",
                "team": "team:platform-engineering",
                "email": "priya.sharma@acme.internal",
                "worked_on": ["project:auth-modernization"],
                "focus": "Authentication, OAuth2, Architecture",
            },
            "on_highlighted_path": False,
            "is_stale": False,
        },
        {
            "id": "person:james-chen",
            "type": "person",
            "title": "James Chen",
            "properties": {
                "role": "Senior Engineer",
                "team": "team:platform-engineering",
                "email": "james.chen@acme.internal",
                "worked_on": ["project:auth-modernization"],
                "focus": "Backend infrastructure, Token storage",
            },
            "on_highlighted_path": False,
            "is_stale": False,
        },
    ]


def get_neighborhood_stub(
    node_id: str = "service:authentication-api", depth: int = 2
) -> dict[str, Any]:
    """Return graph neighborhood centered on node_id with bounded depth, validating as GraphView."""
    nid = node_id or "service:authentication-api"

    center = {
        "id": nid,
        "type": "service" if nid.startswith("service:") else "person",
        "title": "Authentication API" if nid == "service:authentication-api" else nid,
        "properties": {"status": "active"},
        "on_highlighted_path": True,
        "is_stale": False,
    }
    team = {
        "id": "team:platform-engineering",
        "type": "team",
        "title": "Platform Engineering",
        "properties": {"slack": "#platform-eng"},
        "on_highlighted_path": False,
        "is_stale": False,
    }
    repo = {
        "id": "repository:acme/auth-api",
        "type": "repository",
        "title": "acme/auth-api",
        "properties": {"default_branch": "main"},
        "on_highlighted_path": False,
        "is_stale": False,
    }
    dep = {
        "id": "service:user-profile-api",
        "type": "service",
        "title": "User Profile API",
        "properties": {"owner": "team:backend-core"},
        "on_highlighted_path": False,
        "is_stale": False,
    }
    doc = {
        "id": "document:auth-runbook",
        "type": "document",
        "title": "Auth Runbook",
        "properties": {},
        "on_highlighted_path": False,
        "is_stale": False,
    }

    edges = [
        {
            "id": f"team:platform-engineering::OWNS::{nid}",
            "source_id": "team:platform-engineering",
            "target_id": nid,
            "relationship_type": "OWNS",
            "label": "OWNS",
            "properties": {},
        },
        {
            "id": f"{nid}::IMPLEMENTED_IN::repository:acme/auth-api",
            "source_id": nid,
            "target_id": "repository:acme/auth-api",
            "relationship_type": "IMPLEMENTED_IN",
            "label": "IMPLEMENTED_IN",
            "properties": {},
        },
        {
            "id": f"service:user-profile-api::DEPENDS_ON::{nid}",
            "source_id": "service:user-profile-api",
            "target_id": nid,
            "relationship_type": "DEPENDS_ON",
            "label": "DEPENDS_ON",
            "properties": {},
        },
        {
            "id": f"document:auth-runbook::DOCUMENTS::{nid}",
            "source_id": "document:auth-runbook",
            "target_id": nid,
            "relationship_type": "DOCUMENTS",
            "label": "DOCUMENTS",
            "properties": {},
        },
    ]

    return {
        "nodes": [center, team, repo, dep, doc],
        "edges": edges,
        "root_node_ids": [nid],
        "highlighted_path_ids": [],
        "truncated": False,
        "warning": None,
    }
