"""Select explicit retrieval mode or the bounded model-backed orchestrator."""

import json
import re

from weave_brain.agent.orchestrator import aggregate, followups, process_question
from weave_brain.agent.tools import execute_tool
from weave_brain.domain.models import ChatRequest, ChatResponse
from weave_brain.services.graph_service import GraphService
from weave_brain.services.report_service import ReportService


def submit_question(question: str, service: GraphService) -> ChatResponse:
    if service.settings.chat_mode == "agent":
        return process_question(ChatRequest(question=question), service)
    lower = question.lower()
    warnings = [
        "Deterministic graph retrieval; no LLM synthesis. No conversation memory."
    ]
    if service.settings.development_fixtures:
        warnings.append("Development fixture data; no live database retrieval.")
    if any(
        word in lower for word in ("knowledge health", "health score", "knowledge gaps")
    ):
        report = ReportService(service).health()
        return ChatResponse(
            answer=f"Knowledge health: {report.health_score}/100. {report.gaps.total_gaps} recorded knowledge gaps.",
            graph=report.graph,
            warnings=warnings,
            intent="knowledge_health",
            suggested_followups=[
                "Who owns the authentication service?",
                "Onboard me to the authentication service",
            ],
        )
    ids = re.findall(
        r"(?:service|team|person|decision|incident|ticket|repository|file|project|document|test):[a-z0-9][a-z0-9/._:-]*",
        lower,
    )
    ids = [value.rstrip(".") for value in ids]
    if len(ids) >= 2 and any(
        word in lower for word in ("connect", "path", "between", "related")
    ):
        tool, args = "find_connection", {"from_id": ids[0], "to_id": ids[1]}
        service_id = None
    else:
        service_id = next(
            (value for value in ids if value.startswith("service:")), None
        )
        if not service_id:
            candidates = service.search("service:")
            scored = []
            for candidate in candidates:
                tokens = set(
                    re.findall(r"[a-z0-9]+", candidate.id.split(":", 1)[1])
                ) - {"api", "service"}
                score = sum(
                    bool(re.search(r"\b" + re.escape(t) + r"\b", lower)) for t in tokens
                )
                if "auth" in re.findall(r"\w+", lower) and "authentication" in tokens:
                    score += 1
                if score:
                    scored.append((score, candidate.id))
            scored.sort(reverse=True)
            if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                service_id = scored[0][1]
        file_id = next((value for value in ids if value.startswith("file:")), None)
        if not service_id and not file_id:
            return ChatResponse(
                answer="Please name a service or canonical entity. Try ownership, decisions, experts, blast radius, onboarding or knowledge health.",
                warnings=warnings,
                intent="unsupported",
            )
        if "onboard" in lower and service_id:
            brief = ReportService(service).onboarding(service_id)
            return ChatResponse(
                answer=brief.overview + "\n\n" + "\n".join(brief.change_risks),
                evidence=brief.key_decisions,
                graph=brief.graph,
                related_entities=brief.top_experts,
                suggested_followups=followups(service_id),
                warnings=warnings,
                intent="onboarding",
            )
        if any(word in lower for word in ("change", "impact", "test coverage")):
            tool = "change_impact"
        elif any(word in lower for word in ("expert", "worked on", "who knows")):
            tool = "find_experts"
        elif any(
            word in lower for word in ("why", "rationale", "decision", "token", "adr")
        ):
            tool = "service_decisions"
        elif any(word in lower for word in ("blast", "break", "down", "depend")):
            tool = "blast_radius"
        else:
            tool = "service_overview"
        args = {"entity_id": file_id or service_id}
    result = execute_tool(tool, json.dumps(args), service)
    response = aggregate([result])
    response.answer = (
        result.summary
        + "\n\n"
        + "\n\n".join(
            f"[S{i + 1}] **{e.title}**: {e.excerpt or 'Retrieved source record.'}"
            for i, e in enumerate(response.evidence)
        )
    )
    response.intent = {
        "find_experts": "expert_finder",
        "service_decisions": "decision_rationale",
    }.get(tool, tool)
    response.warnings = [*warnings, *response.warnings]
    return response
