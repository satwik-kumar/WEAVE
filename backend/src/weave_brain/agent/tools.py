"""Only explicitly registered graph operations are callable by a model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from weave_brain.core.validation import canonical
from weave_brain.domain.models import EvidenceItem, GraphNode, GraphView
from weave_brain.services.graph_service import GraphService, bounded_view


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str = Field(min_length=1, max_length=500)


class ConnectionArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_id: str = Field(min_length=1, max_length=500)
    to_id: str = Field(min_length=1, max_length=500)


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200)


class ToolResult(BaseModel):
    tool: str
    summary: str
    evidence: list[EvidenceItem] = []
    graph: GraphView | None = None
    related_entities: list[GraphNode] = []
    warnings: list[str] = []


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


TOOLS = [
    ToolSpec(name=name, description=description, parameters=model.model_json_schema())
    for name, description, model in [
        (
            "service_overview",
            "Retrieve a service's ownership, repositories, decisions and evidence. entity_id is a canonical service ID.",
            ToolArguments,
        ),
        (
            "blast_radius",
            "Find incoming service dependents, at most three hops. entity_id is a service ID.",
            ToolArguments,
        ),
        (
            "find_experts",
            "Find people who worked on projects using a service, with graph evidence. entity_id is a service ID.",
            ToolArguments,
        ),
        (
            "service_decisions",
            "Retrieve decision rationale, motivating incidents and supersession. entity_id is a service ID.",
            ToolArguments,
        ),
        (
            "find_connection",
            "Find a connection between two canonical entities, up to three hops.",
            ConnectionArguments,
        ),
        (
            "search_knowledge",
            "Find canonical entity IDs by title or ID before another lookup.",
            SearchArguments,
        ),
        (
            "change_impact",
            "Retrieve service blast radius, decisions, incidents, tickets and code/test records actually present. entity_id is a service or file ID.",
            ToolArguments,
        ),
    ]
]


def execute_tool(name: str, arguments: str, service: GraphService) -> ToolResult:
    if name not in {tool.name for tool in TOOLS}:
        raise ValueError("Unregistered tool")
    if name == "search_knowledge":
        args = SearchArguments.model_validate_json(arguments)
        if not args.query.strip():
            raise ValueError("Blank search query")
        nodes = service.search(args.query.strip())
        return ToolResult(
            tool=name,
            summary="Search results: " + ", ".join(n.id for n in nodes),
            related_entities=nodes,
            graph=GraphView(nodes=nodes, edges=[]),
            evidence=[
                EvidenceItem(
                    source_id=str(n.properties.get("source_id") or n.id),
                    title=n.title,
                    source_type=str(n.properties.get("source_type") or n.type),
                    excerpt=str(
                        n.properties.get("description")
                        or n.properties.get("summary")
                        or f"Retrieved entity {n.id}."
                    ),
                    source_url=n.properties.get("source_url"),
                    relationship_path=[n.id],
                )
                for n in nodes
            ],
        )
    if name == "find_connection":
        args = ConnectionArguments.model_validate_json(arguments)
        result = service.shortest(canonical(args.from_id), canonical(args.to_id))
        nodes = {node.id: node for node in result.graph.nodes}
        evidence = [
            EvidenceItem(
                source_id=str(
                    edge.properties.get("source_id")
                    or nodes[edge.source_id].properties.get("source_id")
                    or edge.source_id
                ),
                title=edge.relationship_type,
                source_type="relationship",
                excerpt=f"{nodes[edge.source_id].title} → {edge.relationship_type} → {nodes[edge.target_id].title}",
                relationship_path=[edge.source_id, edge.target_id],
            )
            for edge in result.graph.edges
        ]
        return ToolResult(
            tool=name,
            summary="Connection found."
            if result.path_found
            else "No connection found in the bounded neighborhood.",
            graph=result.graph,
            evidence=evidence,
        )
    args = ToolArguments.model_validate_json(arguments)
    entity_id = canonical(args.entity_id, service=name != "change_impact")
    if name == "change_impact" and not entity_id.startswith(("service:", "file:")):
        raise ValueError("Change impact requires a service or file ID")
    if name == "service_overview":
        overview = service.overview(entity_id)
        return ToolResult(
            tool=name,
            summary=overview.service.title
            + (
                f" is owned by {overview.team.title}."
                if overview.team
                else " has no recorded owner."
            ),
            graph=overview.graph,
            evidence=overview.evidence,
        )
    if name == "blast_radius":
        blast = service.blast(entity_id, 3)
        return ToolResult(
            tool=name,
            summary="Retrieved dependent services: "
            + (", ".join(n.title for n in blast.affected_services) or "none"),
            graph=blast.graph,
            evidence=blast.evidence,
        )
    if name in ("find_experts", "service_decisions"):
        result = (
            service.experts(entity_id)
            if name == "find_experts"
            else service.decisions(entity_id)
        )
        return ToolResult(
            tool=name,
            summary="Retrieved records: "
            + (", ".join(n.title for n in result.nodes) or "none"),
            graph=result.graph,
            evidence=result.evidence,
            related_entities=result.nodes,
        )
    neighborhood = service.neighborhood(entity_id, 3)
    if entity_id.startswith("service:"):
        blast = service.blast(entity_id, 3)
        decisions = service.decisions(entity_id)
        views = [neighborhood, blast.graph, decisions.graph]
        graph = bounded_view(
            {
                "nodes": [n.model_dump() for view in views for n in view.nodes],
                "edges": [e.model_dump() for view in views for e in view.edges],
                "root_node_ids": [entity_id],
                "truncated": any(view.truncated for view in views),
                "warning": " ".join(
                    dict.fromkeys(view.warning for view in views if view.warning)
                ),
            }
        )
        evidence = [*blast.evidence, *decisions.evidence]
    else:
        # Only direct IMPORTS callers are evidence of file impact; don't infer tests.
        graph = neighborhood
        callers = {
            e.source_id
            for e in graph.edges
            if e.relationship_type == "IMPORTS" and e.target_id == entity_id
        }
        evidence = [
            EvidenceItem(
                source_id=str(n.properties.get("source_id") or n.id),
                title=n.title,
                source_type=str(n.properties.get("source_type") or n.type),
                excerpt=f"{n.title} imports {entity_id}.",
                relationship_path=[n.id, entity_id],
            )
            for n in graph.nodes
            if n.id in callers
        ]
    records = [
        n for n in graph.nodes if n.type in ("incident", "ticket", "file", "test")
    ]
    for node in records:
        evidence.append(
            EvidenceItem(
                source_id=str(node.properties.get("source_id") or node.id),
                title=node.title,
                source_type=str(node.properties.get("source_type") or node.type),
                excerpt=str(
                    node.properties.get("summary")
                    or node.properties.get("description")
                    or "Retrieved related record."
                ),
            )
        )
    return ToolResult(
        tool=name,
        summary="Bounded change-impact records retrieved. No missing tests or downstream records are inferred.",
        graph=graph,
        evidence=evidence,
        related_entities=records,
    )
