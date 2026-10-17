"""Adapt B's public retrieval interfaces at the application boundary."""

from collections import deque
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from weave_brain.core.config import Settings
from weave_brain.domain.models import EvidenceItem, GraphNode, GraphView
from weave_brain.graph import fixtures, mapper, queries
from weave_brain.graph.client import get_graph

AUTH = "service:authentication-api"


class ServiceOverview(BaseModel):
    service: GraphNode
    team: GraphNode | None = None
    repositories: list[GraphNode] = []
    decisions: list[GraphNode] = []
    dependents: list[GraphNode] = []
    evidence: list[EvidenceItem] = []
    graph: GraphView


class BlastRadius(BaseModel):
    affected_services: list[GraphNode]
    evidence: list[EvidenceItem] = []
    graph: GraphView


class ShortestPath(BaseModel):
    path_found: bool
    graph: GraphView


class Retrieval(BaseModel):
    nodes: list[GraphNode]
    evidence: list[EvidenceItem]
    graph: GraphView


def evidence_path(view: GraphView, start: str, target: str) -> list[str]:
    projects = {
        edge.target_id
        for edge in view.edges
        if edge.source_id == start and edge.relationship_type == "WORKED_ON"
    }
    for edge in view.edges:
        if (
            edge.source_id in projects
            and edge.target_id == target
            and edge.relationship_type == "USES"
        ):
            return [start, edge.source_id, target]
    return []


def bounded_view(raw: dict[str, Any]) -> GraphView:
    view = mapper.to_graph_view(raw)
    if len(view.nodes) > 100:
        roots = set(view.root_node_ids)
        view.nodes = sorted(view.nodes, key=lambda n: n.id not in roots)[:100]
        view.truncated = True
        view.warning = " ".join(
            filter(None, [view.warning, "Graph limited to 100 nodes."])
        )
    ids = {node.id for node in view.nodes}
    valid_edges = [
        edge for edge in view.edges if edge.source_id in ids and edge.target_id in ids
    ]
    if len(valid_edges) != len(view.edges):
        view.warning = " ".join(
            filter(None, [view.warning, "Edges with missing endpoints omitted."])
        )
    view.edges = valid_edges
    edge_ids = {edge.id for edge in valid_edges}
    view.highlighted_path_ids = [
        edge for edge in view.highlighted_path_ids if edge in edge_ids
    ]
    view.root_node_ids = [node for node in view.root_node_ids if node in ids]
    return view


class GraphService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _graph(self):
        if not self.settings.falkordb_host or not self.settings.falkordb_graph_name:
            raise HTTPException(503, "Database is not configured.")
        return get_graph(
            self.settings.falkordb_graph_name,
            self.settings.falkordb_host,
            self.settings.falkordb_port,
            username=self.settings.falkordb_username,
            password=self.settings.falkordb_password.get_secret_value()
            if self.settings.falkordb_password
            else None,
            ssl=self.settings.falkordb_ssl,
            timeout=self.settings.falkordb_timeout,
        )

    def overview(self, service_id: str) -> ServiceOverview:
        if self.settings.development_fixtures:
            raw = fixtures.get_catalog_overview_stub(service_id)
        else:
            raw = queries.get_service_overview(service_id, graph=self._graph())
        if not raw:
            raise HTTPException(404, "Service not found.")
        view = bounded_view(raw)
        if self.settings.development_fixtures:
            view.warning = "Development fixture data."
        nodes = {node.id: node for node in view.nodes}

        def mapped(key: str) -> list[GraphNode]:
            ids = [
                item if isinstance(item, str) else item["id"]
                for item in raw.get(key, [])
            ]
            return [nodes[node_id] for node_id in ids if node_id in nodes]

        team = raw.get("team")
        evidence = mapper.to_evidence_items(raw)
        for edge in view.edges:
            if edge.relationship_type not in ("OWNS", "IMPLEMENTED_IN"):
                continue
            source, target = nodes.get(edge.source_id), nodes.get(edge.target_id)
            if source and target:
                evidence.append(
                    EvidenceItem(
                        source_id=str(source.properties.get("source_id") or source.id),
                        title=source.title,
                        source_type=str(
                            source.properties.get("source_type") or source.type
                        ),
                        excerpt=f"{source.title} — {edge.relationship_type} → {target.title}",
                        source_url=source.properties.get("source_url"),
                        relationship_path=[source.id, target.id],
                    )
                )
        return ServiceOverview(
            service=nodes[service_id],
            team=nodes.get(team["id"]) if team else None,
            repositories=mapped("repositories"),
            decisions=mapped("decisions"),
            dependents=mapped("dependents"),
            evidence=evidence,
            graph=view,
        )

    def neighborhood(self, node_id: str, depth: int) -> GraphView:
        if self.settings.development_fixtures:
            raw = fixtures.get_catalog_neighborhood_stub(node_id, depth)
        else:
            raw = queries.get_neighborhood(node_id, depth, graph=self._graph())
        view = bounded_view(raw)
        if node_id not in {node.id for node in view.nodes}:
            raise HTTPException(404, "Entity not found.")
        return view

    def blast(self, service_id: str, depth: int) -> BlastRadius:
        raw = (
            fixtures.get_catalog_blast_stub(service_id, depth)
            if self.settings.development_fixtures
            else queries.get_blast_radius(service_id, depth, graph=self._graph())
        )
        view = bounded_view(raw)
        if service_id not in {node.id for node in view.nodes}:
            raise HTTPException(404, "Service not found.")
        affected = {node["id"] for node in raw.get("affected_services", [])}
        if self.settings.development_fixtures:
            view.warning = "Development fixture data."
        return BlastRadius(
            affected_services=[n for n in view.nodes if n.id in affected],
            evidence=mapper.to_evidence_items(raw),
            graph=view,
        )

    def entity(self, node_id: str) -> GraphNode:
        return next(n for n in self.neighborhood(node_id, 1).nodes if n.id == node_id)

    def decisions(self, service_id: str) -> Retrieval:
        overview = self.overview(service_id)
        raw = (
            fixtures.get_catalog_decisions_stub(service_id)
            if self.settings.development_fixtures
            else queries.get_decisions_for_service(service_id, graph=self._graph())
        )
        # Include the retrieved service before mapping DECIDES_FOR endpoints.
        raw["service"] = overview.service.model_dump()
        evidence = mapper.to_evidence_items(raw)
        view = mapper.to_graph_view(
            raw, highlighted_paths=[e.relationship_path for e in evidence]
        )
        view = bounded_view({"graph": view.model_dump()})
        view.root_node_ids = [service_id]
        if self.settings.development_fixtures:
            view.warning = "Development fixture data."
        ids = {item["id"] for item in raw.get("decisions", [])}
        return Retrieval(
            nodes=[n for n in view.nodes if n.id in ids], evidence=evidence, graph=view
        )

    def experts(self, service_id: str) -> Retrieval:
        self.overview(service_id)
        raw = (
            fixtures.find_catalog_experts_stub(service_id)
            if self.settings.development_fixtures
            else queries.find_experts(service_id, graph=self._graph())
        )
        nodes = bounded_view({"nodes": raw}).nodes
        view = self.neighborhood(service_id, 3)
        view = bounded_view(
            {
                "nodes": [n.model_dump() for n in [*view.nodes, *nodes]],
                "edges": [e.model_dump() for e in view.edges],
                "root_node_ids": [service_id],
                "warning": view.warning,
                "truncated": view.truncated,
            }
        )
        evidence = [
            EvidenceItem(
                source_id=str(node.properties.get("source_id") or node.id),
                title=node.title,
                source_type=str(node.properties.get("source_type") or "person"),
                excerpt="Expertise supported by retrieved WORKED_ON → Project → USES → Service relationships.",
                source_url=node.properties.get("source_url"),
                relationship_path=evidence_path(view, node.id, service_id),
            )
            for node in nodes
        ]
        paths = [item.relationship_path for item in evidence if item.relationship_path]
        view = mapper.to_graph_view(
            {"graph": view.model_dump()}, highlighted_paths=paths
        )
        if len(paths) != len(nodes):
            view.warning = " ".join(
                filter(
                    None,
                    [
                        view.warning,
                        "Some expert support paths were not included in the bounded neighborhood.",
                    ],
                )
            )
        return Retrieval(nodes=nodes, evidence=evidence, graph=view)

    def shortest(self, from_id: str, to_id: str) -> ShortestPath:
        # Search only the public three-hop neighborhood; preserve its bounded-result
        # warning and original relationship directions in the returned path.
        view = self.neighborhood(from_id, 3)
        view.warning = " ".join(
            filter(
                None,
                [
                    view.warning,
                    "Path search uses only the returned neighborhood (maximum three hops).",
                ],
            )
        )
        queue = deque([(from_id, [from_id], [])])
        seen = {from_id}
        while queue:
            current, path, path_edges = queue.popleft()
            if current == to_id:
                ids = set(path)
                result = GraphView(
                    nodes=[n for n in view.nodes if n.id in ids],
                    edges=path_edges,
                    root_node_ids=[from_id],
                    highlighted_path_ids=[e.id for e in path_edges],
                    truncated=view.truncated,
                    warning=view.warning,
                )
                for node in result.nodes:
                    node.on_highlighted_path = True
                return ShortestPath(path_found=True, graph=result)
            if len(path_edges) >= 3:
                continue
            for edge in view.edges:
                neighbor = (
                    edge.target_id
                    if edge.source_id == current
                    else (edge.source_id if edge.target_id == current else None)
                )
                if neighbor and neighbor not in seen:
                    seen.add(neighbor)
                    queue.append((neighbor, [*path, neighbor], [*path_edges, edge]))
        return ShortestPath(
            path_found=False,
            graph=GraphView(
                nodes=[],
                edges=[],
                truncated=view.truncated,
                warning="No path found within the returned neighborhood (maximum three hops).",
            ),
        )

    def search(self, query: str) -> list[GraphNode]:
        if self.settings.development_fixtures:
            nodes = bounded_view(fixtures.get_catalog_stub()).nodes
            return [n for n in nodes if query.lower() in (n.id + " " + n.title).lower()]
        raw = queries.search_entities(query, graph=self._graph())
        return bounded_view({"nodes": raw}).nodes
