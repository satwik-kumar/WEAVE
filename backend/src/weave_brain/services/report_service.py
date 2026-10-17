from typing import Any

from weave_brain.agent.answer_generator import generate_answer
from weave_brain.agent.mapper import (
    tool_result_to_evidence,
    tool_result_to_graph_view,
)
from weave_brain.agent.tools import call_tool
from weave_brain.domain.models import (
    HealthDimension,
    HealthScore,
    KnowledgeGap,
)
from weave_brain.graph import queries


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
