from __future__ import annotations

from typing import Any

from weave_brain.domain.models import (
    EvidenceItem,
    GraphView,
)
from weave_brain.graph import mapper as graph_mapper


def tool_result_to_graph_view(
    result: dict,
    highlighted: list[str] | None = None,
) -> GraphView:
    """Map a tool result dictionary to a GraphView by delegating to graph.mapper.

    Preserves staleness flags, freshness_status, superseded status, and root_node_ids.
    Handles composite structures (such as get_onboarding_brief) by merging subgraphs.
    """
    if not isinstance(result, dict):
        return GraphView(nodes=[], edges=[])

    # Composite structure check (e.g., get_onboarding_brief)
    if (
        any(k in result for k in ("overview", "blast_radius"))
        and "graph" not in result
        and "service" not in result
    ):
        combined_nodes: list[Any] = []
        combined_edges: list[Any] = []
        root_node_ids: list[str] = []

        for key in ("overview", "decisions", "blast_radius"):
            sub = result.get(key)
            if isinstance(sub, dict):
                sub_gv = tool_result_to_graph_view(sub, highlighted=highlighted)
                combined_nodes.extend(sub_gv.nodes)
                combined_edges.extend(sub_gv.edges)
                root_node_ids.extend(sub_gv.root_node_ids)

        experts_sub = result.get("experts")
        if isinstance(experts_sub, list):
            combined_nodes.extend(experts_sub)
        elif isinstance(experts_sub, dict):
            combined_nodes.extend(experts_sub.get("experts", []))

        merged_payload = {
            "graph": {
                "nodes": combined_nodes,
                "edges": combined_edges,
                "root_node_ids": root_node_ids,
            }
        }
        return graph_mapper.to_graph_view(
            merged_payload,
            highlighted_paths=[highlighted] if highlighted else None,
        )

    return graph_mapper.to_graph_view(
        result,
        highlighted_paths=[highlighted] if highlighted else None,
    )


def tool_result_to_evidence(tool_name: str, result: dict) -> list[EvidenceItem]:
    """Map a tool result dictionary to EvidenceItem list using graph.mapper."""
    if not isinstance(result, dict):
        return []

    # Composite structure check (e.g., get_onboarding_brief)
    if (
        any(k in result for k in ("overview", "blast_radius"))
        and "graph" not in result
        and "service" not in result
    ):
        combined_evidence: list[EvidenceItem] = []
        seen_ids: set[str] = set()
        for key in ("overview", "decisions", "experts", "blast_radius"):
            sub = result.get(key)
            if isinstance(sub, dict):
                items = tool_result_to_evidence(key, sub)
                for it in items:
                    if it.source_id not in seen_ids:
                        combined_evidence.append(it)
                        seen_ids.add(it.source_id)
            elif isinstance(sub, list):
                for item in sub:
                    if isinstance(item, dict) and "id" in item:
                        iid = item["id"]
                        if iid not in seen_ids:
                            combined_evidence.append(
                                EvidenceItem(
                                    source_id=iid,
                                    title=item.get("title")
                                    or item.get("name")
                                    or iid,
                                    source_type=item.get("type", "person"),
                                )
                            )
                            seen_ids.add(iid)
        return combined_evidence

    # If it's find_experts result
    if "experts" in result and isinstance(result["experts"], list):
        items: list[EvidenceItem] = []
        for ex in result["experts"]:
            if isinstance(ex, dict) and ex.get("id"):
                items.append(
                    EvidenceItem(
                        source_id=ex["id"],
                        title=ex.get("title") or ex.get("name") or ex["id"],
                        source_type="person",
                        relationship_path=(
                            list(ex.get("roles", [])) if "roles" in ex else []
                        ),
                    )
                )
        if items:
            return items

    # Standard tool result delegation
    items = graph_mapper.to_evidence_items(result)

    # Ensure service and team are included if present in top-level result
    seen_ids = {it.source_id for it in items}
    svc = result.get("service")
    if isinstance(svc, dict) and svc.get("id") and svc["id"] not in seen_ids:
        items.insert(
            0,
            EvidenceItem(
                source_id=svc["id"],
                title=svc.get("title", svc["id"]),
                source_type="service",
                source_url=svc.get("source_url")
                or svc.get("properties", {}).get("source_url"),
            ),
        )
        seen_ids.add(svc["id"])
    team = result.get("team")
    if isinstance(team, dict) and team.get("id") and team["id"] not in seen_ids:
        items.append(
            EvidenceItem(
                source_id=team["id"],
                title=team.get("title", team["id"]),
                source_type="team",
            )
        )
        seen_ids.add(team["id"])

    return items
