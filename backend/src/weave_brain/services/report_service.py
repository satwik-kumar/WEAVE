"""Grounded health and onboarding reports from named graph retrievals."""

from weave_brain.domain.models import HealthReport, KnowledgeGaps, OnboardingBrief
from weave_brain.graph import fixtures, queries
from weave_brain.services.graph_service import GraphService, Retrieval, bounded_view


class ReportService:
    def __init__(self, graph_service: GraphService):
        self.graph = graph_service

    def health(self) -> HealthReport:
        raw = (
            fixtures.get_catalog_health_stub()
            if self.graph.settings.development_fixtures
            else queries.get_health_score(graph=self.graph._graph())
        )
        gaps = raw["gaps"]
        converted = {}
        for key in (
            "unowned_services",
            "decisions_missing_rationale",
            "undocumented_services",
        ):
            converted[key] = bounded_view({"nodes": gaps[key]}).nodes
        admitted = set()
        clipped = False
        for key, nodes in converted.items():
            kept = []
            for node in nodes:
                if node.id in admitted or len(admitted) < 100:
                    admitted.add(node.id)
                    kept.append(node)
                else:
                    clipped = True
            converted[key] = kept
        warning = gaps.get("warning")
        if clipped:
            warning = " ".join(
                filter(None, [warning, "Gap details limited to 100 unique entities."])
            )
        graph = bounded_view(
            raw.get("graph", {"nodes": [n for key in converted for n in gaps[key]]})
        )
        return HealthReport(
            health_score=raw["health_score"],
            metrics=raw["metrics"],
            counts=raw["counts"],
            gaps=KnowledgeGaps(
                **converted,
                total_gaps=gaps["total_gaps"],
                truncated=gaps.get("truncated", False) or clipped,
                warning=warning,
            ),
            graph=graph,
            warnings=[
                *raw.get("warnings", []),
                *(
                    [
                        "No service records were found; empty metric categories use the score convention of 100%."
                    ]
                    if not raw["counts"]["total_services"]
                    else []
                ),
            ],
        )

    def gaps(self) -> KnowledgeGaps:
        return self.health().gaps

    def decisions(self, service_id: str) -> Retrieval:
        result = self.graph.decisions(service_id)
        result.nodes.sort(
            key=lambda n: str(n.properties.get("decision_date", "")), reverse=True
        )
        return result

    def onboarding(self, service_id: str) -> OnboardingBrief:
        overview = self.graph.overview(service_id)
        decisions = self.graph.decisions(service_id)
        experts = self.graph.experts(service_id)
        blast = self.graph.blast(service_id, 3)
        neighborhood = self.graph.neighborhood(service_id, 2)
        combined = bounded_view(
            {
                "nodes": [
                    n.model_dump()
                    for view in (
                        overview.graph,
                        decisions.graph,
                        experts.graph,
                        blast.graph,
                        neighborhood,
                    )
                    for n in view.nodes
                ],
                "edges": [
                    e.model_dump()
                    for view in (
                        overview.graph,
                        decisions.graph,
                        experts.graph,
                        blast.graph,
                        neighborhood,
                    )
                    for e in view.edges
                ],
                "root_node_ids": [service_id],
                "truncated": any(
                    view.truncated
                    for view in (
                        overview.graph,
                        decisions.graph,
                        experts.graph,
                        blast.graph,
                        neighborhood,
                    )
                ),
            }
        )
        current = {
            n.id for n in decisions.nodes if n.properties.get("status") == "accepted"
        }
        evidence = [
            item
            for item in decisions.evidence
            if any(node_id in current for node_id in item.relationship_path)
        ]
        incidents = [
            n
            for n in neighborhood.nodes
            if n.type == "incident"
            and n.properties.get("status") != "resolved"
            and any(
                e.source_id == n.id
                and e.target_id == service_id
                and e.relationship_type == "AFFECTS"
                for e in neighborhood.edges
            )
        ]
        tickets = [
            n
            for n in neighborhood.nodes
            if n.type == "ticket"
            and any(
                e.source_id == n.id
                and e.target_id == service_id
                and e.relationship_type == "AFFECTS"
                for e in neighborhood.edges
            )
        ]
        return OnboardingBrief(
            service_id=service_id,
            service_title=overview.service.title,
            overview=str(
                overview.service.properties.get("description") or overview.service.title
            )
            + (
                f" Owned by {overview.team.title}."
                if overview.team
                else " No owning team recorded."
            ),
            key_decisions=evidence,
            top_experts=experts.nodes,
            change_risks=[
                f"{n.title} depends on this service." for n in blast.affected_services
            ],
            open_incidents=incidents,
            related_tickets=tickets,
            graph=combined,
            warnings=["Development fixture data; no live database retrieval."]
            if self.graph.settings.development_fixtures
            else [],
        )
