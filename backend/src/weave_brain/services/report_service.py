from __future__ import annotations

from typing import Any

from weave_brain.agent.answer_generator import generate_answer
from weave_brain.agent.mapper import (
    tool_result_to_evidence,
    tool_result_to_graph_view,
)
from weave_brain.agent.tools import call_tool
from weave_brain.domain.models import (
    HealthDimension,
    HealthReport,
    HealthScore,
    KnowledgeGap,
    KnowledgeGaps,
    OnboardingBrief,
)
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


def build_health_score() -> HealthScore:
    raw = queries.get_health_score()

    metrics = raw.get("metrics", {}) if isinstance(raw.get("metrics"), dict) else {}
    counts = raw.get("counts", {}) if isinstance(raw.get("counts"), dict) else {}

    dims_spec = [
        (
            "services_owned",
            "Services with owner",
            raw.get("services_owned", metrics.get("services_owned", 0.0)),
            raw.get(
                "services_owned_count",
                (counts.get("owned_services", 0), counts.get("total_services", 0)),
            ),
        ),
        (
            "decisions_with_rationale",
            "Decisions documented",
            raw.get(
                "decisions_with_rationale", metrics.get("decisions_rationale", 0.0)
            ),
            raw.get(
                "decisions_with_rationale_count",
                (
                    counts.get("decisions_with_rationale", 0),
                    counts.get("total_decisions", 0),
                ),
            ),
        ),
        (
            "incidents_resolved",
            "Incidents resolved",
            raw.get("incidents_resolved", metrics.get("incidents_resolved", 0.0)),
            raw.get(
                "incidents_resolved_count",
                (counts.get("resolved_incidents", 0), counts.get("total_incidents", 0)),
            ),
        ),
        (
            "services_documented",
            "Services with docs",
            raw.get("services_documented", metrics.get("services_documented", 0.0)),
            raw.get(
                "services_documented_count",
                (counts.get("documented_services", 0), counts.get("total_services", 0)),
            ),
        ),
    ]

    dims: list[HealthDimension] = []
    for _key, label, score_val, count_val in dims_spec:
        score = float(score_val)
        cur, tot = count_val if isinstance(count_val, (tuple, list)) else (0, 0)
        status = "good" if score >= 0.8 else "warning" if score >= 0.5 else "critical"
        dims.append(
            HealthDimension(
                label=label,
                score=score,
                current=int(cur),
                total=int(tot),
                status=status,
            )
        )

    gaps_raw = queries.get_knowledge_gaps()
    if isinstance(gaps_raw, list):
        gaps = [KnowledgeGap(**g) for g in gaps_raw]
    elif isinstance(gaps_raw, dict):
        gaps = []
        for s in gaps_raw.get("unowned_services", []):
            gaps.append(
                KnowledgeGap(
                    entity_id=s.get("id", ""),
                    entity_title=s.get("title") or s.get("id", ""),
                    gap_type="no_owner",
                )
            )
        for d in gaps_raw.get("decisions_missing_rationale", []):
            gaps.append(
                KnowledgeGap(
                    entity_id=d.get("id", ""),
                    entity_title=d.get("title") or d.get("id", ""),
                    gap_type="missing_rationale",
                )
            )
        for s in gaps_raw.get("undocumented_services", []):
            gaps.append(
                KnowledgeGap(
                    entity_id=s.get("id", ""),
                    entity_title=s.get("title") or s.get("id", ""),
                    gap_type="undocumented",
                )
            )
    else:
        gaps = []

    overall = sum(d.score for d in dims) / len(dims) if dims else 0.0
    return HealthScore(dimensions=dims, overall=round(overall, 2), gaps=gaps)


def build_onboarding_brief(service_id: str, provider: Any) -> dict[str, Any]:
    data = call_tool("get_onboarding_brief", {"service_id": service_id})
    svc = data.get("overview", {}).get("service", {})
    q = f"Give me a complete onboarding overview of {svc.get('title', service_id)}."
    answer = generate_answer(q, data, provider)

    if isinstance(data.get("experts"), dict):
        experts_raw = data.get("experts", {}).get("experts", [])
    elif isinstance(data.get("experts"), list):
        experts_raw = data.get("experts", [])
    else:
        experts_raw = []

    blast_raw = data.get("blast_radius", {})
    if isinstance(blast_raw, dict):
        blast = blast_raw.get("blast_radius", []) or blast_raw.get(
            "affected_services", []
        )
    elif isinstance(blast_raw, list):
        blast = blast_raw
    else:
        blast = []

    decisions_dict = data.get("decisions", {})
    if isinstance(decisions_dict, dict):
        decisions_raw = decisions_dict.get("decisions", [])
    elif isinstance(decisions_dict, list):
        decisions_raw = decisions_dict
    else:
        decisions_raw = []

    return {
        "service_id": service_id,
        "service_title": svc.get("title", service_id),
        "answer": answer,
        "key_decisions": tool_result_to_evidence(
            "get_decisions_for_service", {"decisions": decisions_raw}
        ),
        "top_experts": experts_raw[:3],
        "blast_radius_summary": (
            f"{len(blast)} service(s) depend on this"
            if blast
            else "No known dependents"
        ),
        "open_incidents": [],
        "graph": tool_result_to_graph_view(data),
        "warnings": [],
    }
