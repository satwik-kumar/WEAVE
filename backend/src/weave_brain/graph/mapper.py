"""Graph mapper converting Cypher query results into Pydantic domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from weave_brain.domain.models import (
    EntityType,
    EvidenceItem,
    GraphEdge,
    GraphNode,
    GraphView,
)

VALID_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "person",
        "team",
        "service",
        "repository",
        "file",
        "document",
        "decision",
        "ticket",
        "incident",
        "test",
        "project",
    }
)


def _parse_datetime(val: Any) -> datetime | None:
    """Safely parse a datetime or ISO-8601 string to a timezone-aware UTC datetime."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=UTC)
        return val.astimezone(UTC)
    if isinstance(val, str) and val.strip():
        try:
            # Handle ISO string with or without Z
            clean_str = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except (ValueError, TypeError):
            return None
    return None


def _calculate_freshness(
    props: dict[str, Any], now: datetime | None = None
) -> tuple[bool, str]:
    """Compute is_stale and freshness_status ('fresh', 'aging', 'stale').

    Rules:
      < 30 days: 'fresh' (is_stale=False)
      30 - 90 days: 'aging' (is_stale=True)
      > 90 days: 'stale' (is_stale=True)
    """
    ref_dt = _parse_datetime(props.get("ingested_at") or props.get("source_updated_at"))
    if ref_dt is None:
        return (False, "fresh")

    current_time = now or datetime.now(UTC)
    age_days = (current_time - ref_dt).days

    if age_days < 30:
        return (False, "fresh")
    if age_days <= 90:
        return (True, "aging")
    return (True, "stale")


def _infer_entity_type(node_id: str, raw_type: Any = None) -> EntityType:
    """Infer EntityType from raw_type or node_id prefix."""
    if isinstance(raw_type, str):
        candidate = raw_type.lower().strip()
        if candidate in VALID_ENTITY_TYPES:
            return candidate  # type: ignore[return-value]

    if ":" in node_id:
        prefix = node_id.split(":")[0].lower().strip()
        if prefix in VALID_ENTITY_TYPES:
            return prefix  # type: ignore[return-value]

    return "service"


def to_graph_view(
    query_result: dict[str, Any],
    highlighted_paths: list[list[str]] | None = None,
    now: datetime | None = None,
) -> GraphView:
    """Map a query result dictionary into a validated GraphView.

    Computes is_stale and freshness_status for nodes.
    Marks Decision nodes as 'superseded' when an incoming SUPERSEDES edge is present.
    Ensures canonical edge IDs ('source_id::rel_type::target_id') and flags on_highlighted_path.
    """
    highlighted_paths = highlighted_paths or []
    # Set of node IDs appearing anywhere in highlighted_paths
    highlighted_node_ids: set[str] = {
        nid for path in highlighted_paths for nid in path if isinstance(nid, str)
    }

    # Extract raw nodes and edges from query_result
    raw_nodes: list[Any] = []
    raw_edges: list[Any] = []

    if "graph" in query_result and isinstance(query_result["graph"], dict):
        g = query_result["graph"]
        raw_nodes.extend(g.get("nodes", []))
        raw_edges.extend(g.get("edges", []))
    else:
        raw_nodes.extend(query_result.get("nodes", []))
        raw_edges.extend(query_result.get("edges", []))

    # Also harvest standalone node keys from query_result (e.g. service, team, repositories, decisions)
    for key, val in query_result.items():
        if key in ("graph", "nodes", "edges", "evidence"):
            continue
        if isinstance(val, dict) and "id" in val:
            raw_nodes.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "id" in item:
                    raw_nodes.append(item)

    # First pass: collect edges and find superseded decisions
    superseded_decision_ids: set[str] = set()
    cleaned_edges: list[GraphEdge] = []
    seen_edge_ids: set[str] = set()

    for e in raw_edges:
        if isinstance(e, GraphEdge):
            edge_obj = e
        elif isinstance(e, dict):
            src_id = str(e.get("source_id", "")).strip()
            tgt_id = str(e.get("target_id", "")).strip()
            rel_type = str(
                e.get("relationship_type") or e.get("label") or e.get("relation") or ""
            ).strip()
            if not (src_id and tgt_id and rel_type):
                continue

            edge_id = (
                str(e.get("id")) if e.get("id") else f"{src_id}::{rel_type}::{tgt_id}"
            )
            props = dict(e.get("properties", {}))

            edge_obj = GraphEdge(
                id=edge_id,
                source_id=src_id,
                target_id=tgt_id,
                relationship_type=rel_type,
                label=rel_type,
                properties=props,
            )
        else:
            continue

        if edge_obj.relationship_type == "SUPERSEDES":
            superseded_decision_ids.add(edge_obj.target_id)

        if edge_obj.id not in seen_edge_ids:
            seen_edge_ids.add(edge_obj.id)
            cleaned_edges.append(edge_obj)

    # Second pass: map and deduplicate nodes
    cleaned_nodes: list[GraphNode] = []
    seen_node_ids: set[str] = set()

    for n in raw_nodes:
        if isinstance(n, GraphNode):
            node_id = n.id
            entity_type = n.type
            title = n.title
            props = dict(n.properties)
            on_path = n.on_highlighted_path
        elif isinstance(n, dict):
            node_id = str(n.get("id", "")).strip()
            if not node_id:
                continue
            entity_type = _infer_entity_type(node_id, n.get("type"))
            title = str(n.get("title") or node_id)
            props = dict(n.get("properties", {}))
            # Also inherit top-level keys if not in properties
            for prop_key in (
                "description",
                "status",
                "rationale",
                "severity",
                "language",
                "tech_stack",
                "slack_channel",
                "ingested_at",
                "source_updated_at",
            ):
                if prop_key in n and prop_key not in props:
                    props[prop_key] = n[prop_key]
            on_path = bool(n.get("on_highlighted_path", False))
        else:
            continue

        if node_id in seen_node_ids:
            continue
        seen_node_ids.add(node_id)

        # Freshness / staleness
        is_stale, freshness_status = _calculate_freshness(props, now=now)
        props["freshness_status"] = freshness_status

        # Superseded decision status
        if entity_type == "decision" and (
            node_id in superseded_decision_ids or props.get("status") == "superseded"
        ):
            props["status"] = "superseded"

        # On highlighted path check
        if node_id in highlighted_node_ids:
            on_path = True

        cleaned_nodes.append(
            GraphNode(
                id=node_id,
                type=entity_type,
                title=title,
                properties=props,
                on_highlighted_path=on_path,
                is_stale=is_stale,
            )
        )

    # Determine root node IDs
    root_node_ids: list[str] = []
    if "graph" in query_result and isinstance(query_result["graph"], dict):
        root_node_ids = list(query_result["graph"].get("root_node_ids", []))
    if not root_node_ids and "root_node_ids" in query_result:
        root_node_ids = list(query_result["root_node_ids"])
    if not root_node_ids:
        for fallback_key in ("service_id", "node_id"):
            if query_result.get(fallback_key):
                root_node_ids = [str(query_result[fallback_key])]
                break
        if not root_node_ids and isinstance(
            query_result.get("service"), (dict, GraphNode)
        ):
            svc = query_result["service"]
            sid = svc.id if isinstance(svc, GraphNode) else svc.get("id")
            if sid:
                root_node_ids = [str(sid)]

    # Collect highlighted edge IDs from highlighted paths
    highlighted_path_ids: list[str] = []
    if "graph" in query_result and isinstance(query_result["graph"], dict):
        highlighted_path_ids.extend(
            query_result["graph"].get("highlighted_path_ids", [])
        )
    if "highlighted_path_ids" in query_result:
        highlighted_path_ids.extend(query_result["highlighted_path_ids"])

    for path in highlighted_paths:
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            for edge in cleaned_edges:
                if (edge.source_id == u and edge.target_id == v) or (
                    edge.source_id == v and edge.target_id == u
                ):
                    highlighted_path_ids.append(edge.id)

    # Deduplicate highlighted path IDs
    seen_hids: set[str] = set()
    deduped_highlighted_path_ids = [
        hid
        for hid in highlighted_path_ids
        if not (hid in seen_hids or seen_hids.add(hid))
    ]

    truncated = bool(
        query_result.get("truncated", False)
        or (
            isinstance(query_result.get("graph"), dict)
            and query_result["graph"].get("truncated", False)
        )
    )
    warning = query_result.get("warning") or (
        query_result["graph"].get("warning")
        if isinstance(query_result.get("graph"), dict)
        else None
    )

    return GraphView(
        nodes=cleaned_nodes,
        edges=cleaned_edges,
        root_node_ids=root_node_ids,
        highlighted_path_ids=deduped_highlighted_path_ids,
        truncated=truncated,
        warning=warning,
    )


def to_evidence_items(query_result: dict[str, Any]) -> list[EvidenceItem]:
    """Extract or synthesize a list of EvidenceItem from a query result dictionary."""
    evidence_items: list[EvidenceItem] = []
    raw_evidence = query_result.get("evidence", [])

    if raw_evidence:
        for item in raw_evidence:
            if isinstance(item, EvidenceItem):
                evidence_items.append(item)
            elif isinstance(item, dict):
                evidence_items.append(
                    EvidenceItem(
                        source_id=str(item.get("source_id") or item.get("id") or ""),
                        title=str(item.get("title") or item.get("source_id") or ""),
                        source_type=str(
                            item.get("source_type") or item.get("type") or "entity"
                        ),
                        excerpt=item.get("excerpt"),
                        source_url=item.get("source_url"),
                        relationship_path=list(item.get("relationship_path", [])),
                    )
                )
        return evidence_items

    # Synthesize evidence from decisions, documents, and affected entities if evidence list is missing
    target_id = query_result.get("service_id") or query_result.get("node_id", "")

    for dec in query_result.get("decisions", []):
        if isinstance(dec, dict):
            props = dec.get("properties", {})
            excerpt = props.get("rationale") or props.get("status")
            evidence_items.append(
                EvidenceItem(
                    source_id=dec.get("id", ""),
                    title=dec.get("title", dec.get("id", "")),
                    source_type="decision",
                    excerpt=excerpt,
                    source_url=props.get("source_url"),
                    relationship_path=[p for p in [dec.get("id"), target_id] if p],
                )
            )

    for doc in query_result.get("documents", []):
        if isinstance(doc, dict):
            props = doc.get("properties", {})
            excerpt = props.get("content_excerpt") or props.get("summary")
            evidence_items.append(
                EvidenceItem(
                    source_id=doc.get("id", ""),
                    title=doc.get("title", doc.get("id", "")),
                    source_type="document",
                    excerpt=excerpt,
                    source_url=props.get("source_url"),
                    relationship_path=[p for p in [doc.get("id"), target_id] if p],
                )
            )

    for dep in query_result.get("affected_services", []):
        if isinstance(dep, dict):
            dep_id = dep.get("id", "")
            evidence_items.append(
                EvidenceItem(
                    source_id=dep_id,
                    title=dep.get("title", dep_id),
                    source_type="service",
                    excerpt=f"{dep_id} depends on {target_id} and will fail if it goes down",
                    source_url=None,
                    relationship_path=[p for p in [dep_id, target_id] if p],
                )
            )

    return evidence_items
