"""Core graph query operations for FalkorDB with safe object unpacking."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from weave_brain.graph.client import get_graph

logger = logging.getLogger(__name__)

QUERY_LIMIT: int = 50
MAX_TRAVERSAL_DEPTH: int = 3


@dataclass
class _QueryRows:
    result_set: list[Any]
    truncated: bool = False


def _unpack_node(node: Any) -> dict[str, Any]:
    """Unpack a FalkorDB Node object or dictionary into a clean dictionary."""
    if isinstance(node, dict):
        nid = str(node.get("id", ""))
        ntype = str(
            node.get("type") or (nid.split(":")[0] if ":" in nid else "service")
        )
        title = str(node.get("title") or nid)
        props = dict(node.get("properties", {}))
        return {
            "id": nid,
            "type": ntype,
            "title": title,
            "properties": props,
            "on_highlighted_path": bool(node.get("on_highlighted_path", False)),
            "is_stale": bool(node.get("is_stale", False)),
        }

    # FalkorDB driver Node object
    props = dict(getattr(node, "properties", {}))
    nid = str(props.get("id", ""))
    labels = list(getattr(node, "labels", []))
    ntype = (
        labels[0].lower()
        if labels
        else (nid.split(":")[0] if ":" in nid else "service")
    )
    title = str(props.get("title", nid))

    clean_props = {k: v for k, v in props.items() if k not in ("id", "title")}

    return {
        "id": nid,
        "type": ntype,
        "title": title,
        "properties": clean_props,
        "on_highlighted_path": False,
        "is_stale": False,
    }


def _unpack_edge(edge: Any, source_id: str, target_id: str) -> dict[str, Any]:
    """Unpack a FalkorDB Edge object or dictionary into a clean dictionary."""
    if isinstance(edge, dict):
        rel = str(
            edge.get("relationship_type")
            or edge.get("label")
            or edge.get("relation")
            or "RELATED_TO"
        )
        eid = str(edge.get("id") or f"{source_id}::{rel}::{target_id}")
        return {
            "id": eid,
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": rel,
            "label": rel,
            "properties": dict(edge.get("properties", {})),
        }

    rel = str(getattr(edge, "relation", "RELATED_TO"))
    props = dict(getattr(edge, "properties", {}))
    eid = f"{source_id}::{rel}::{target_id}"

    return {
        "id": eid,
        "source_id": source_id,
        "target_id": target_id,
        "relationship_type": rel,
        "label": rel,
        "properties": props,
    }


def _unpack_path(path: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Safely unpack a FalkorDB Path object into nodes and edges using canonical IDs."""
    if not path:
        return ([], [])

    nodes = (
        path.nodes()
        if callable(getattr(path, "nodes", None))
        else getattr(path, "nodes", [])
    )
    edges = (
        path.edges()
        if callable(getattr(path, "edges", None))
        else getattr(path, "edges", [])
    )

    # Build internal database id -> canonical string id mapping
    id_map: dict[Any, str] = {}
    unpacked_nodes: list[dict[str, Any]] = []

    for n in nodes:
        props = getattr(n, "properties", {}) if hasattr(n, "properties") else n
        canonical_id = str(props.get("id", str(getattr(n, "id", ""))))
        id_map[getattr(n, "id", None)] = canonical_id
        unpacked_nodes.append(_unpack_node(n))

    unpacked_edges: list[dict[str, Any]] = []
    for e in edges:
        src_id = id_map.get(getattr(e, "src_node", None), "")
        dst_id = id_map.get(getattr(e, "dest_node", None), "")
        if src_id and dst_id:
            unpacked_edges.append(_unpack_edge(e, src_id, dst_id))

    return (unpacked_nodes, unpacked_edges)


def _execute_query(
    graph: Any,
    cypher: str,
    params: dict[str, Any] | None = None,
    query_name: str = "cypher_query",
) -> Any:
    """Execute a parameterized query against FalkorDB with debug timing."""
    active_graph = graph if graph is not None else get_graph()
    params = params or {}
    start_time = time.perf_counter()

    try:
        # Request one extra row to detect omitted results, including legacy
        # overview/gap queries that previously had no LIMIT at all.
        bounded = "count(" not in cypher.lower() and not cypher.endswith("LIMIT 1")
        if bounded:
            cypher = (
                re.sub(r"LIMIT \d+\s*$", f"LIMIT {QUERY_LIMIT + 1}", cypher)
                if re.search(r"LIMIT \d+\s*$", cypher)
                else cypher + f" LIMIT {QUERY_LIMIT + 1}"
            )
        result = active_graph.query(cypher, params)
        rows = result.result_set
        res = _QueryRows(
            rows[:QUERY_LIMIT] if bounded else rows, bounded and len(rows) > QUERY_LIMIT
        )
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "Query [%s] executed in %.2fms (returned %d rows)",
            query_name,
            duration_ms,
            len(getattr(res, "result_set", [])),
        )
        return res
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            "Query [%s] failed after %.2fms: %s",
            query_name,
            duration_ms,
            e,
        )
        raise


def get_service_overview(service_id: str, graph: Any = None) -> dict[str, Any] | None:
    """Return overview of a service including team, repos, decisions, documents, and dependents.

    Returns None if service_id does not exist.
    """
    svc_res = _execute_query(
        graph,
        "MATCH (s:Service {id: $sid}) RETURN s",
        {"sid": service_id},
        "get_service_overview_service",
    )
    if not svc_res.result_set:
        return None

    service_node = _unpack_node(svc_res.result_set[0][0])

    # Owning team
    team_res = _execute_query(
        graph,
        "MATCH (t:Team)-[r:OWNS]->(s:Service {id: $sid}) RETURN t, r",
        {"sid": service_id},
        "get_service_overview_team",
    )
    team_node = None
    edges: list[dict[str, Any]] = []
    if team_res.result_set:
        team_node = _unpack_node(team_res.result_set[0][0])
        edges.append(
            _unpack_edge(team_res.result_set[0][1], team_node["id"], service_id)
        )

    # Repositories
    repo_res = _execute_query(
        graph,
        "MATCH (s:Service {id: $sid})-[r:IMPLEMENTED_IN]->(repo:Repository) RETURN repo, r",
        {"sid": service_id},
        "get_service_overview_repos",
    )
    repositories: list[dict[str, Any]] = []
    for row in repo_res.result_set:
        repo = _unpack_node(row[0])
        repositories.append(repo)
        edges.append(_unpack_edge(row[1], service_id, repo["id"]))

    # Decisions
    dec_res = _execute_query(
        graph,
        "MATCH (d:Decision)-[r:DECIDES_FOR]->(s:Service {id: $sid}) RETURN d, r",
        {"sid": service_id},
        "get_service_overview_decisions",
    )
    decisions: list[dict[str, Any]] = []
    for row in dec_res.result_set:
        dec = _unpack_node(row[0])
        decisions.append(dec)
        edges.append(_unpack_edge(row[1], dec["id"], service_id))

    # Documents
    doc_res = _execute_query(
        graph,
        "MATCH (doc:Document)-[r:DOCUMENTS]->(s:Service {id: $sid}) RETURN doc, r",
        {"sid": service_id},
        "get_service_overview_docs",
    )
    documents: list[dict[str, Any]] = []
    for row in doc_res.result_set:
        doc = _unpack_node(row[0])
        documents.append(doc)
        edges.append(_unpack_edge(row[1], doc["id"], service_id))

    # Dependents (services depending on this service)
    dep_res = _execute_query(
        graph,
        "MATCH (dep:Service)-[r:DEPENDS_ON]->(s:Service {id: $sid}) RETURN dep, r",
        {"sid": service_id},
        "get_service_overview_dependents",
    )
    dependents: list[str] = []
    dependent_nodes: list[dict[str, Any]] = []
    for row in dep_res.result_set:
        dep_node = _unpack_node(row[0])
        dependents.append(dep_node["id"])
        dependent_nodes.append(dep_node)
        edges.append(_unpack_edge(row[1], dep_node["id"], service_id))

    # Build evidence items
    evidence: list[dict[str, Any]] = []
    for dec in decisions:
        excerpt = dec.get("properties", {}).get("rationale") or dec.get("title")
        evidence.append(
            {
                "source_id": dec.get("properties", {}).get("source_id") or dec["id"],
                "title": dec["title"],
                "source_type": dec.get("properties", {}).get("source_type")
                or "decision",
                "excerpt": excerpt,
                "source_url": None,
                "relationship_path": [dec["id"], service_id],
            }
        )
    for doc in documents:
        props = doc.get("properties", {})
        evidence.append(
            {
                "source_id": props.get("source_id") or doc["id"],
                "title": doc["title"],
                "source_type": props.get("source_type") or "document",
                "excerpt": props.get("content_excerpt") or doc["title"],
                "source_url": props.get("source_url"),
                "relationship_path": [doc["id"], service_id],
            }
        )

    all_nodes = [service_node]
    if team_node:
        all_nodes.append(team_node)
    all_nodes.extend(repositories)
    all_nodes.extend(decisions)
    all_nodes.extend(documents)
    all_nodes.extend(dependent_nodes)

    graph_view_dict = {
        "nodes": all_nodes,
        "edges": edges,
        "root_node_ids": [service_id],
        "highlighted_path_ids": [],
        "truncated": any(
            result.truncated
            for result in (team_res, repo_res, dec_res, doc_res, dep_res)
        ),
        "warning": "Query results limited to 50 rows per retrieval."
        if any(
            result.truncated
            for result in (team_res, repo_res, dec_res, doc_res, dep_res)
        )
        else None,
    }

    return {
        "service": service_node,
        "team": team_node,
        "repositories": repositories,
        "decisions": decisions,
        "documents": documents,
        "dependents": dependents,
        "evidence": evidence,
        "graph": graph_view_dict,
    }


def get_decisions_for_service(service_id: str, graph: Any = None) -> dict[str, Any]:
    """Return decisions governing service_id including MOTIVATED_BY incidents and SUPERSEDES links."""
    cypher = (
        "MATCH (d:Decision)-[r:DECIDES_FOR]->(s:Service {id: $sid}) "
        "OPTIONAL MATCH (d)-[m:MOTIVATED_BY]->(inc:Incident) "
        "OPTIONAL MATCH (newer:Decision)-[sup:SUPERSEDES]->(d) "
        "OPTIONAL MATCH (d)-[sup_out:SUPERSEDES]->(older:Decision) "
        "RETURN d, r, inc, m, newer, sup, older, sup_out "
        f"LIMIT {QUERY_LIMIT}"
    )
    res = _execute_query(
        graph, cypher, {"sid": service_id}, "get_decisions_for_service"
    )

    nodes_map: dict[str, dict[str, Any]] = {}
    edges_map: dict[str, dict[str, Any]] = {}
    decisions_list: list[dict[str, Any]] = []
    evidence_items: list[dict[str, Any]] = []

    for row in res.result_set:
        d_raw, r_raw, inc_raw, m_raw, newer_raw, sup_raw, older_raw, sup_out_raw = row

        if d_raw:
            d_node = _unpack_node(d_raw)
            nodes_map[d_node["id"]] = d_node
            if d_node["id"] not in [x["id"] for x in decisions_list]:
                decisions_list.append(d_node)
            if r_raw:
                e = _unpack_edge(r_raw, d_node["id"], service_id)
                edges_map[e["id"]] = e

        if inc_raw and m_raw and d_raw:
            inc_node = _unpack_node(inc_raw)
            nodes_map[inc_node["id"]] = inc_node
            e = _unpack_edge(m_raw, d_node["id"], inc_node["id"])
            edges_map[e["id"]] = e
            evidence_items.append(
                {
                    "source_id": d_node.get("properties", {}).get("source_id")
                    or d_node["id"],
                    "title": d_node["title"],
                    "source_type": d_node.get("properties", {}).get("source_type")
                    or "decision",
                    "excerpt": d_node.get("properties", {}).get("rationale")
                    or f"Motivated by {inc_node['id']}",
                    "source_url": None,
                    "relationship_path": [d_node["id"], inc_node["id"]],
                }
            )

        if newer_raw and sup_raw and d_raw:
            newer_node = _unpack_node(newer_raw)
            nodes_map[newer_node["id"]] = newer_node
            e = _unpack_edge(sup_raw, newer_node["id"], d_node["id"])
            edges_map[e["id"]] = e

        if older_raw and sup_out_raw and d_raw:
            older_node = _unpack_node(older_raw)
            nodes_map[older_node["id"]] = older_node
            e = _unpack_edge(sup_out_raw, d_node["id"], older_node["id"])
            edges_map[e["id"]] = e

    service_result = _execute_query(
        graph,
        "MATCH (s:Service {id: $sid}) RETURN s",
        {"sid": service_id},
        "get_decisions_service",
    )
    if service_result.result_set:
        service_node = _unpack_node(service_result.result_set[0][0])
        nodes_map[service_id] = service_node

    # Fallback evidence for decisions without incidents
    for dec in decisions_list:
        if not any(
            ev["relationship_path"] and ev["relationship_path"][0] == dec["id"]
            for ev in evidence_items
        ):
            evidence_items.append(
                {
                    "source_id": dec.get("properties", {}).get("source_id")
                    or dec["id"],
                    "title": dec["title"],
                    "source_type": dec.get("properties", {}).get("source_type")
                    or "decision",
                    "excerpt": dec.get("properties", {}).get("rationale")
                    or dec["title"],
                    "source_url": None,
                    "relationship_path": [dec["id"], service_id],
                }
            )

    graph_dict = {
        "nodes": list(nodes_map.values()),
        "edges": list(edges_map.values()),
        "root_node_ids": [d["id"] for d in decisions_list],
        "highlighted_path_ids": [],
        "truncated": res.truncated,
        "warning": "Query results limited to 50 rows." if res.truncated else None,
    }

    return {
        "service_id": service_id,
        "decisions": decisions_list,
        "evidence": evidence_items,
        "graph": graph_dict,
    }


def get_blast_radius(
    service_id: str, max_depth: int = 3, graph: Any = None
) -> dict[str, Any]:
    """Return blast radius data: what breaks if service_id goes down.

    Traverses incoming DEPENDS_ON edges (<-[:DEPENDS_ON*1..max_depth]-).
    """
    bounded_depth = min(max(1, max_depth), MAX_TRAVERSAL_DEPTH)

    # Fetch root service first
    root_res = _execute_query(
        graph,
        "MATCH (s:Service {id: $sid}) RETURN s",
        {"sid": service_id},
        "get_blast_radius_root",
    )
    if not root_res.result_set:
        return {
            "service_id": service_id,
            "affected_services": [],
            "evidence": [],
            "graph": {
                "nodes": [],
                "edges": [],
                "root_node_ids": [service_id],
                "highlighted_path_ids": [],
                "truncated": False,
                "warning": f"Service '{service_id}' not found",
            },
        }

    root_node = _unpack_node(root_res.result_set[0][0])
    root_node["on_highlighted_path"] = True

    # Critical direction rule: look for arrows pointing INTO service_id
    cypher = (
        f"MATCH path = (s:Service {{id: $sid}})<-[:DEPENDS_ON*1..{bounded_depth}]-(dep:Service) "
        "RETURN path "
        f"LIMIT {QUERY_LIMIT}"
    )
    res = _execute_query(graph, cypher, {"sid": service_id}, "get_blast_radius_paths")

    nodes_map: dict[str, dict[str, Any]] = {root_node["id"]: root_node}
    edges_map: dict[str, dict[str, Any]] = {}
    affected_services: list[dict[str, Any]] = []
    highlighted_path_ids: list[str] = []
    evidence_items: list[dict[str, Any]] = []

    for row in res.result_set:
        path_obj = row[0]
        unpacked_nodes, unpacked_edges = _unpack_path(path_obj)

        for n in unpacked_nodes:
            n["on_highlighted_path"] = True
            if n["id"] not in nodes_map:
                nodes_map[n["id"]] = n
                if n["id"] != service_id and n["id"] not in [
                    x["id"] for x in affected_services
                ]:
                    affected_services.append(n)

        for e in unpacked_edges:
            edges_map[e["id"]] = e
            if e["id"] not in highlighted_path_ids:
                highlighted_path_ids.append(e["id"])

    for dep in affected_services:
        evidence_items.append(
            {
                "source_id": dep["id"],
                "title": dep["title"],
                "source_type": dep.get("properties", {}).get("source_type")
                or "service",
                "excerpt": f"{dep['id']} depends on {service_id} and will fail if it goes down",
                "source_url": None,
                "relationship_path": [dep["id"], service_id],
            }
        )

    graph_dict = {
        "nodes": list(nodes_map.values()),
        "edges": list(edges_map.values()),
        "root_node_ids": [service_id],
        "highlighted_path_ids": highlighted_path_ids,
        "truncated": res.truncated,
        "warning": "Query results limited to 50 rows." if res.truncated else None,
    }

    return {
        "service_id": service_id,
        "affected_services": affected_services,
        "evidence": evidence_items,
        "graph": graph_dict,
    }


def find_experts(service_id: str, graph: Any = None) -> list[dict[str, Any]]:
    """Return engineers connected to service_id via initiatives and ownership."""
    cypher = (
        "MATCH (p:Person)-[w:WORKED_ON]->(proj:Project)-[:USES]->(s:Service {id: $sid}) "
        "OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team) "
        "RETURN p, w, proj, t "
        f"LIMIT {QUERY_LIMIT}"
    )
    res = _execute_query(graph, cypher, {"sid": service_id}, "find_experts")

    experts_map: dict[str, dict[str, Any]] = {}
    for row in res.result_set:
        p_raw, _w_raw, proj_raw, t_raw = row
        p_node = _unpack_node(p_raw)
        pid = p_node["id"]

        if pid not in experts_map:
            p_node["properties"].setdefault("worked_on", [])
            experts_map[pid] = p_node

        if proj_raw:
            proj_node = _unpack_node(proj_raw)
            if proj_node["id"] not in experts_map[pid]["properties"]["worked_on"]:
                experts_map[pid]["properties"]["worked_on"].append(proj_node["id"])

        if t_raw:
            t_node = _unpack_node(t_raw)
            experts_map[pid]["properties"]["team"] = t_node["id"]

    return list(experts_map.values())


def get_neighborhood(node_id: str, depth: int = 2, graph: Any = None) -> dict[str, Any]:
    """Return graph neighborhood centered on node_id with bounded depth."""
    bounded_depth = min(max(1, depth), MAX_TRAVERSAL_DEPTH)

    cypher = (
        f"MATCH path = (center {{id: $nid}})-[*1..{bounded_depth}]-(neighbor) "
        "RETURN path "
        f"LIMIT {QUERY_LIMIT}"
    )
    res = _execute_query(graph, cypher, {"nid": node_id}, "get_neighborhood")

    nodes_map: dict[str, dict[str, Any]] = {}
    edges_map: dict[str, dict[str, Any]] = {}

    # Center node fallback lookup
    center_res = _execute_query(
        graph,
        "MATCH (c {id: $nid}) RETURN c",
        {"nid": node_id},
        "get_neighborhood_center",
    )
    if center_res.result_set:
        c_node = _unpack_node(center_res.result_set[0][0])
        c_node["on_highlighted_path"] = True
        nodes_map[c_node["id"]] = c_node

    for row in res.result_set:
        path_obj = row[0]
        unpacked_nodes, unpacked_edges = _unpack_path(path_obj)
        for n in unpacked_nodes:
            if n["id"] == node_id:
                n["on_highlighted_path"] = True
            if n["id"] not in nodes_map:
                nodes_map[n["id"]] = n
        for e in unpacked_edges:
            edges_map[e["id"]] = e

    return {
        "nodes": list(nodes_map.values()),
        "edges": list(edges_map.values()),
        "root_node_ids": [node_id],
        "highlighted_path_ids": [],
        "truncated": res.truncated,
        "warning": "Query results limited to 50 rows." if res.truncated else None,
    }


def find_shortest_path(from_id: str, to_id: str, graph: Any = None) -> dict[str, Any]:
    """Find the shortest path connecting from_id and to_id up to 3 hops."""
    cypher = (
        "MATCH (a {id: $from_id}), (b {id: $to_id}) "
        "MATCH path = (a)-[*1..3]-(b) "
        "RETURN path "
        "ORDER BY length(path) ASC "
        "LIMIT 1"
    )
    res = _execute_query(
        graph,
        cypher,
        {"from_id": from_id, "to_id": to_id},
        "find_shortest_path",
    )

    if not res.result_set:
        return {
            "from_id": from_id,
            "to_id": to_id,
            "path_found": False,
            "nodes": [],
            "edges": [],
            "highlighted_path_ids": [],
        }

    path_obj = res.result_set[0][0]
    unpacked_nodes, unpacked_edges = _unpack_path(path_obj)
    for n in unpacked_nodes:
        n["on_highlighted_path"] = True

    highlighted_path_ids = [e["id"] for e in unpacked_edges]

    return {
        "from_id": from_id,
        "to_id": to_id,
        "path_found": True,
        "nodes": unpacked_nodes,
        "edges": unpacked_edges,
        "highlighted_path_ids": highlighted_path_ids,
    }


def get_knowledge_gaps(graph: Any = None) -> dict[str, Any]:
    """Identify knowledge gaps in the company brain."""
    # 1. Services without an owning Team
    unowned_res = _execute_query(
        graph,
        "MATCH (s:Service) WHERE NOT ()-[:OWNS]->(s) RETURN s",
        {},
        "get_knowledge_gaps_unowned",
    )
    unowned_services = [_unpack_node(row[0]) for row in unowned_res.result_set]

    # 2. Decisions with missing or empty rationale
    dec_res = _execute_query(
        graph,
        "MATCH (d:Decision) WHERE d.rationale IS NULL OR d.rationale = '' RETURN d",
        {},
        "get_knowledge_gaps_missing_rationale",
    )
    decisions_missing_rationale = [_unpack_node(row[0]) for row in dec_res.result_set]

    # 3. Services without documentation
    undoc_res = _execute_query(
        graph,
        "MATCH (s:Service) WHERE NOT ()-[:DOCUMENTS]->(s) RETURN s",
        {},
        "get_knowledge_gaps_undocumented",
    )
    undocumented_services = [_unpack_node(row[0]) for row in undoc_res.result_set]

    return {
        "unowned_services": unowned_services,
        "decisions_missing_rationale": decisions_missing_rationale,
        "undocumented_services": undocumented_services,
        "total_gaps": len(unowned_services)
        + len(decisions_missing_rationale)
        + len(undocumented_services),
        "truncated": any(
            result.truncated for result in (unowned_res, dec_res, undoc_res)
        ),
        "warning": "Gap lists are bounded to 50 records per category; the displayed count may be incomplete."
        if any(result.truncated for result in (unowned_res, dec_res, undoc_res))
        else None,
    }


def get_health_score(graph: Any = None) -> dict[str, Any]:
    """Compute overall knowledge health score and the 4 tracked metrics."""
    # Counts
    svc_count_res = _execute_query(
        graph, "MATCH (s:Service) RETURN count(s)", {}, "health_total_services"
    )
    total_services = (
        int(svc_count_res.result_set[0][0]) if svc_count_res.result_set else 0
    )

    owned_count_res = _execute_query(
        graph,
        "MATCH (:Team)-[:OWNS]->(s:Service) RETURN count(DISTINCT s)",
        {},
        "health_owned_services",
    )
    owned_services = (
        int(owned_count_res.result_set[0][0]) if owned_count_res.result_set else 0
    )

    dec_count_res = _execute_query(
        graph, "MATCH (d:Decision) RETURN count(d)", {}, "health_total_decisions"
    )
    total_decisions = (
        int(dec_count_res.result_set[0][0]) if dec_count_res.result_set else 0
    )

    dec_rat_count_res = _execute_query(
        graph,
        "MATCH (d:Decision) WHERE d.rationale IS NOT NULL AND d.rationale <> '' RETURN count(d)",
        {},
        "health_decisions_with_rationale",
    )
    decisions_with_rationale = (
        int(dec_rat_count_res.result_set[0][0]) if dec_rat_count_res.result_set else 0
    )

    inc_count_res = _execute_query(
        graph, "MATCH (inc:Incident) RETURN count(inc)", {}, "health_total_incidents"
    )
    total_incidents = (
        int(inc_count_res.result_set[0][0]) if inc_count_res.result_set else 0
    )

    inc_res_count_res = _execute_query(
        graph,
        "MATCH (inc:Incident {status: 'resolved'}) RETURN count(inc)",
        {},
        "health_resolved_incidents",
    )
    resolved_incidents = (
        int(inc_res_count_res.result_set[0][0]) if inc_res_count_res.result_set else 0
    )

    doc_svc_count_res = _execute_query(
        graph,
        "MATCH (:Document)-[:DOCUMENTS]->(s:Service) RETURN count(DISTINCT s)",
        {},
        "health_documented_services",
    )
    documented_services = (
        int(doc_svc_count_res.result_set[0][0]) if doc_svc_count_res.result_set else 0
    )

    # Ratios
    r_owned = (owned_services / total_services) if total_services > 0 else 1.0
    r_dec = (decisions_with_rationale / total_decisions) if total_decisions > 0 else 1.0
    r_inc = (resolved_incidents / total_incidents) if total_incidents > 0 else 1.0
    r_doc = (documented_services / total_services) if total_services > 0 else 1.0

    score = round(((r_owned + r_dec + r_inc + r_doc) / 4.0) * 100.0, 1)

    # Detailed gaps
    gaps_data = get_knowledge_gaps(graph=graph)

    return {
        "health_score": score,
        "metrics": {
            "services_owned": round(r_owned, 2),
            "decisions_rationale": round(r_dec, 2),
            "incidents_resolved": round(r_inc, 2),
            "services_documented": round(r_doc, 2),
        },
        "counts": {
            "total_services": total_services,
            "owned_services": owned_services,
            "total_decisions": total_decisions,
            "decisions_with_rationale": decisions_with_rationale,
            "total_incidents": total_incidents,
            "resolved_incidents": resolved_incidents,
            "documented_services": documented_services,
        },
        "gaps": gaps_data,
    }


def get_service_dependents(service_id: str, graph: Any = None) -> list[dict[str, Any]]:
    """Return all services that directly depend on service_id."""
    cypher = (
        "MATCH (dep:Service)-[:DEPENDS_ON]->(s:Service {id: $sid}) "
        "RETURN dep "
        f"LIMIT {QUERY_LIMIT}"
    )
    res = _execute_query(graph, cypher, {"sid": service_id}, "get_service_dependents")
    return [_unpack_node(row[0]) for row in res.result_set]


def search_entities(query: str, graph: Any = None) -> list[dict[str, Any]]:
    """Case-insensitive substring search across entity id and title."""
    if not query or not query.strip():
        return []

    cypher = (
        "MATCH (n) "
        "WHERE toLower(n.id) CONTAINS toLower($q) OR toLower(n.title) CONTAINS toLower($q) "
        "RETURN n "
        f"LIMIT {QUERY_LIMIT}"
    )
    res = _execute_query(graph, cypher, {"q": query.strip()}, "search_entities")
    return [_unpack_node(row[0]) for row in res.result_set]
