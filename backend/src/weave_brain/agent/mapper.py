from weave_brain.domain.models import (
    EvidenceItem,
    GraphEdge,
    GraphNode,
    GraphView,
)


def _make_node(raw: dict) -> GraphNode | None:
    nid = raw.get("id") or raw.get("source_id")
    if not nid:
        return None
    return GraphNode(
        id=nid,
        type=raw.get("type", "service"),
        title=raw.get("title") or raw.get("name") or nid,
        properties={
            k: v
            for k, v in raw.items()
            if k
            not in (
                "id",
                "type",
                "title",
                "name",
                "source_id",
                "on_highlighted_path",
            )
        },
        on_highlighted_path=raw.get("on_highlighted_path", False),
    )


def tool_result_to_graph_view(
    result: dict,
    highlighted: list[str] | None = None,
) -> GraphView:
    if highlighted is None:
        highlighted = []
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    seen: set[str] = set()

    def add(raw: dict | None) -> GraphNode | None:
        if not raw:
            return None
        node = _make_node(raw)
        if node and node.id not in seen:
            if node.id in highlighted:
                node.on_highlighted_path = True
            nodes.append(node)
            seen.add(node.id)
        return node

    def edge(src: str, rel: str, tgt: str) -> None:
        if src and tgt:
            edges.append(
                GraphEdge(
                    id=f"{src}::{rel}::{tgt}",
                    source_id=src,
                    target_id=tgt,
                    relationship_type=rel,
                    label=rel.replace("_", " ").title(),
                )
            )

    if not isinstance(result, dict):
        return GraphView(nodes=[], edges=[])

    # Pre-formed graph dict or GraphView in result
    if "graph" in result:
        graph_obj = result["graph"]
        if isinstance(graph_obj, GraphView):
            for n in graph_obj.nodes:
                add({"id": n.id, "type": n.type, "title": n.title, **n.properties})
            edges.extend(e for e in graph_obj.edges if e.id not in {ex.id for ex in edges})
        elif isinstance(graph_obj, dict):
            for n in graph_obj.get("nodes", []):
                add(n)
            for e in graph_obj.get("edges", []):
                if isinstance(e, dict):
                    edge(e.get("source_id", ""), e.get("relationship_type", ""), e.get("target_id", ""))

    # service overview shape
    svc = result.get("service")
    if svc:
        add(svc)
        team = result.get("team")
        if team:
            add(team)
            edge(team.get("id", ""), "OWNS", svc.get("id", ""))
        for r in result.get("repositories", []):
            add(r)
            edge(svc["id"], "IMPLEMENTED_IN", r.get("id", ""))
        for d in result.get("decisions", []):
            add(d)
            edge(d.get("id", ""), "DECIDES_FOR", svc["id"])
        for dep in result.get("dependents", []):
            if isinstance(dep, str):
                add({"id": dep, "type": "service", "title": dep})
                edge(dep, "DEPENDS_ON", svc["id"])
            elif isinstance(dep, dict):
                add(dep)
                edge(dep.get("id", ""), "DEPENDS_ON", svc["id"])

    # blast radius shape
    target_sid = result.get("service_id")
    if target_sid:
        add({"id": target_sid, "type": "service", "title": target_sid})

    blast_raw = result.get("blast_radius", []) or result.get("affected_services", [])
    if isinstance(blast_raw, dict):
        blast_items = blast_raw.get("blast_radius", []) or blast_raw.get(
            "affected_services", []
        )
    elif isinstance(blast_raw, list):
        blast_items = blast_raw
    else:
        blast_items = []

    for item in blast_items:
        if isinstance(item, dict):
            sid = item.get("service_id", "") or item.get("id", "")
            if sid:
                add(
                    {
                        "id": sid,
                        "type": item.get("type", "service"),
                        "title": item.get("service_name") or item.get("title", sid),
                    }
                )

    # decisions shape (standalone list)
    decisions_raw = [] if svc else result.get("decisions", [])
    if isinstance(decisions_raw, dict):
        decisions_list = decisions_raw.get("decisions", [])
    elif isinstance(decisions_raw, list):
        decisions_list = decisions_raw
    else:
        decisions_list = []

    for d in decisions_list:
        if isinstance(d, dict):
            dn = add(d)
            if dn:
                for inc in d.get("incidents", []):
                    if isinstance(inc, dict):
                        inode = add(inc)
                        if inode:
                            edge(dn.id, "MOTIVATED_BY", inode.id)
                mot_by = d.get("motivated_by") or d.get("properties", {}).get("motivated_by")
                if mot_by:
                    inode = add({"id": mot_by, "type": "incident", "title": mot_by})
                    if inode:
                        edge(dn.id, "MOTIVATED_BY", inode.id)

    # experts shape
    experts_raw = result.get("experts", [])
    if isinstance(experts_raw, dict):
        experts_list = experts_raw.get("experts", [])
    elif isinstance(experts_raw, list):
        experts_list = experts_raw
    else:
        experts_list = []

    for ex in experts_list:
        if isinstance(ex, dict):
            add(
                {
                    "id": ex.get("id", ""),
                    "type": "person",
                    "title": ex.get("name") or ex.get("title", ex.get("id", "")),
                }
            )

    # onboarding brief (composite - only recurse if this is a composite brief)
    is_composite = "overview" in result and any(k in result for k in ("decisions", "experts", "blast_radius"))
    if is_composite:
        for key in ("overview", "decisions", "experts", "blast_radius"):
            val = result.get(key)
            if isinstance(val, dict):
                sub = tool_result_to_graph_view(val)
                for n in sub.nodes:
                    add({"id": n.id, "type": n.type, "title": n.title, **n.properties})
                edges.extend(e for e in sub.edges if e.id not in {ex.id for ex in edges})
            elif isinstance(val, list) and key == "experts":
                for ex in val:
                    if isinstance(ex, dict):
                        add({"id": ex.get("id", ""), "type": "person", "title": ex.get("name") or ex.get("title", ex.get("id", ""))})

    return GraphView(
        nodes=nodes,
        edges=edges,
        highlighted_path_ids=highlighted,
        truncated=len(nodes) >= 50,
    )


def tool_result_to_evidence(tool_name: str, result: dict) -> list[EvidenceItem]:
    if not isinstance(result, dict):
        return []

    items: list[EvidenceItem] = []

    svc = result.get("service")
    if svc and svc.get("id"):
        items.append(
            EvidenceItem(
                source_id=svc["id"],
                title=svc.get("title", svc["id"]),
                source_type="service",
                source_url=svc.get("source_url"),
            )
        )

    team = result.get("team")
    if team and team.get("id"):
        items.append(
            EvidenceItem(
                source_id=team["id"],
                title=team.get("title", team["id"]),
                source_type="team",
            )
        )

    # Pre-formed evidence list in result
    if "evidence" in result and isinstance(result["evidence"], list):
        for ev in result["evidence"]:
            if isinstance(ev, EvidenceItem):
                items.append(ev)
            elif isinstance(ev, dict) and ev.get("source_id"):
                items.append(
                    EvidenceItem(
                        source_id=ev["source_id"],
                        title=ev.get("title", ev["source_id"]),
                        source_type=ev.get("source_type", "document"),
                        excerpt=ev.get("excerpt"),
                        source_url=ev.get("source_url"),
                    )
                )

    dec_items = result.get("decisions", [])
    if isinstance(dec_items, dict):
        dec_items = dec_items.get("decisions", [])
    if isinstance(dec_items, list):
        for d in dec_items:
            if isinstance(d, dict) and d.get("id"):
                items.append(
                    EvidenceItem(
                        source_id=d["id"],
                        title=d.get("title", d["id"]),
                        source_type="decision",
                        excerpt=(d.get("rationale", "") or "")[:200] or None,
                    )
                )

    exp_items = result.get("experts", [])
    if isinstance(exp_items, dict):
        exp_items = exp_items.get("experts", [])
    if isinstance(exp_items, list):
        for ex in exp_items:
            if isinstance(ex, dict) and ex.get("id"):
                items.append(
                    EvidenceItem(
                        source_id=ex["id"],
                        title=ex.get("name") or ex.get("title", ex["id"]),
                        source_type="person",
                    )
                )

    # onboarding brief composite
    for key in ("overview", "decisions", "experts", "blast_radius"):
        if key in result and isinstance(result[key], dict):
            sub_evidence = tool_result_to_evidence(key, result[key])
            seen_ids = {item.source_id for item in items}
            for item in sub_evidence:
                if item.source_id not in seen_ids:
                    items.append(item)
                    seen_ids.add(item.source_id)

    # Final deduplication
    seen: set[str] = set()
    deduped: list[EvidenceItem] = []
    for it in items:
        if it.source_id not in seen:
            seen.add(it.source_id)
            deduped.append(it)
    return deduped
