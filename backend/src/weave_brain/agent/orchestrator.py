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
from weave_brain.agent.provider import LLMProvider, get_provider
from weave_brain.agent.suggestions import suggest_followups
from weave_brain.agent.tools import (
    TOOL_REGISTRY,
    ToolExecutionError,
    ToolNotFoundError,
    call_tool,
)
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
    question: str, provider: LLMProvider | None = None
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

    return classify_question_deterministic(question)


def process_question(request: ChatRequest) -> ChatResponse:
    mid = str(uuid.uuid4())
    question = request.question
    warnings: list[str] = []

    try:
        provider: LLMProvider | None = get_provider()
    except (OSError, ModuleNotFoundError, ImportError, ValueError) as e:
        logger.info(
            "LLM provider unavailable (%s); using deterministic pipeline", e
        )
        provider = None
        warnings.append(f"AI provider offline: {e}")

    tool_name, service_id = classify_question(question, provider)
    logger.info("Intent: tool=%s service=%s", tool_name, service_id)

    try:
        result = call_tool(tool_name, {"service_id": service_id})
    except (ToolNotFoundError, ToolExecutionError) as e:
        logger.error("Tool failed: %s", e)
        return ChatResponse(message_id=mid, answer=EMPTY, warnings=[str(e)])

    answer = generate_answer(question, result, provider, tool_name=tool_name)
    graph = tool_result_to_graph_view(result)
    evidence = tool_result_to_evidence(tool_name, result)
    followups = suggest_followups(graph, tool_name)

    return ChatResponse(
        message_id=mid,
        answer=answer,
        evidence=evidence,
        graph=graph,
        suggested_followups=followups,
        warnings=warnings,
        intent=tool_name,
    )
