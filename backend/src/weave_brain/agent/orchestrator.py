import json
import logging
import re
import uuid

from weave_brain.agent.answer_generator import EMPTY, generate_answer
from weave_brain.agent.mapper import (
    tool_result_to_evidence,
    tool_result_to_graph_view,
)
from weave_brain.agent.prompts import build_classifier_messages
from weave_brain.agent.provider import (
    DeterministicModeActive,
    DeterministicProvider,
    LLMProvider,
    LLMProviderError,
    get_provider,
)
from weave_brain.agent.ranking import (
    get_linked_incident,
    get_supersedes_info,
    rank_decision_candidates,
)
from weave_brain.agent.suggestions import suggest_followups
from weave_brain.agent.tools import (
    TOOL_REGISTRY,
    ToolExecutionError,
    ToolNotFoundError,
    call_tool,
)
from weave_brain.core.config import get_settings
from weave_brain.domain.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

DEFAULT_SERVICE = "service:authentication-api"


def classify_question_deterministic(question: str) -> tuple[str, str]:
    """Deterministic keyword-based classification for offline / fallback mode."""
    q_lower = question.lower()

    # Target service extraction
    service_id = DEFAULT_SERVICE
    if "user-profile" in q_lower:
        service_id = "service:user-profile-api"
    elif "notification" in q_lower:
        service_id = "service:notification-service"
    elif "data-pipeline" in q_lower:
        service_id = "service:data-pipeline"
    elif "service:" in q_lower:
        match = re.search(r"service:[a-z0-9\-_]+", q_lower)
        if match:
            service_id = match.group(0)

    # Intent routing
    if any(k in q_lower for k in ("onboard", "brief", "guide")):
        return "get_onboarding_brief", service_id
    if any(
        k in q_lower
        for k in (
            "break",
            "depend",
            "blast",
            "down",
            "fail",
            "impact",
            "outage",
            "radius",
        )
    ):
        return "get_blast_radius", service_id
    if any(k in q_lower for k in ("own", "owner", "owns")):
        return "get_service_overview", service_id
    if any(
        k in q_lower
        for k in (
            "who",
            "expert",
            "team",
            "worked",
            "maintain",
            "author",
            "knows",
            "contact",
        )
    ):
        return "find_experts", service_id
    if any(
        k in q_lower
        for k in (
            "decision",
            "adr",
            "expiry",
            "token",
            "expire",
            "why",
            "rationale",
        )
    ):
        return "get_decisions_for_service", service_id

    return "get_service_overview", service_id


def classify_question(
    question: str,
    provider: LLMProvider | None = None,
    warnings: list[str] | None = None,
) -> tuple[str, str]:
    if provider is not None:
        try:
            raw = provider.complete(build_classifier_messages(question))
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean = "\n".join(lines).strip()
            parsed = json.loads(clean)
            tool = parsed.get("tool")
            if tool in TOOL_REGISTRY:
                return (
                    tool,
                    parsed.get("service_id", DEFAULT_SERVICE),
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM Classifier fallback (%s)", e)
            if warnings is not None:
                warnings.append("AI classifier unavailable; used deterministic routing.")

    return classify_question_deterministic(question)


def process_question(request: ChatRequest) -> ChatResponse:
    mid = str(uuid.uuid4())
    question = request.question
    warnings: list[str] = []

    settings = get_settings()
    provider: LLMProvider | None = None

    try:
        candidate_provider = get_provider(settings)
        if isinstance(candidate_provider, DeterministicProvider):
            # Intentional deterministic operation; no LLM requested and no offline warning
            logger.info("Deterministic mode active; using deterministic pipeline")
            provider = None
        else:
            provider = candidate_provider
    except DeterministicModeActive:
        logger.info("Deterministic mode active; using deterministic pipeline")
        provider = None
    except (
        LLMProviderError,
        OSError,
        ModuleNotFoundError,
        ImportError,
        ValueError,
    ) as e:
        logger.info("LLM provider unavailable (%s); using deterministic pipeline", e)
        provider = None
        warnings.append(f"AI provider offline: {e}")

    tool_name, service_id = classify_question(question, provider, warnings=warnings)
    logger.info("Intent: tool=%s service=%s", tool_name, service_id)

    try:
        result = call_tool(tool_name, {"service_id": service_id})
    except (ToolNotFoundError, ToolExecutionError) as e:
        logger.error("Tool failed: %s", e)
        return ChatResponse(message_id=mid, answer=EMPTY, warnings=[str(e)])

    highlighted_paths: list[list[str]] = []
    if tool_name == "get_decisions_for_service" and isinstance(result, dict):
        decs = result.get("decisions", [])
        if decs:
            ranked, is_specific, _ = rank_decision_candidates(
                question, decs, graph=result.get("graph")
            )
            if is_specific and ranked:
                for d in ranked:
                    did = d.get("id") if isinstance(d, dict) else getattr(d, "id", None)
                    if did:
                        inc = get_linked_incident(d, graph=result.get("graph"))
                        inc_id = (
                            inc.get("id")
                            if isinstance(inc, dict)
                            else getattr(inc, "id", None)
                        )
                        if inc_id:
                            # Discrete path representing the MOTIVATED_BY relationship
                            highlighted_paths.append([did, inc_id])
                        else:
                            older_id, newer_id = get_supersedes_info(
                                d, graph=result.get("graph")
                            )
                            if older_id:
                                # Discrete path representing the SUPERSEDES relationship
                                highlighted_paths.append([did, older_id])
                            elif newer_id:
                                # Discrete path representing the SUPERSEDES relationship
                                highlighted_paths.append([did, newer_id])
                            else:
                                highlighted_paths.append([did])

    answer = generate_answer(
        question, result, provider, tool_name=tool_name, warnings=warnings
    )
    graph = tool_result_to_graph_view(
        result,
        highlighted_paths=highlighted_paths if highlighted_paths else None,
    )
    evidence = tool_result_to_evidence(tool_name, result)
    if highlighted_paths:
        hl_node_ids = {nid for p in highlighted_paths for nid in p}
        evidence.sort(key=lambda item: 0 if item.source_id in hl_node_ids else 1)
    followups = suggest_followups(graph, tool_name)

    return ChatResponse(
        message_id=mid,
        answer=answer,
        evidence=evidence,
        graph=graph,
        highlighted_paths=highlighted_paths,
        suggested_followups=followups,
        warnings=warnings,
        intent=tool_name,
    )
