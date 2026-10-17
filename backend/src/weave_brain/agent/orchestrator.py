import json
import logging
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
    ToolExecutionError,
    ToolNotFoundError,
    call_tool,
)
from weave_brain.domain.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

DEFAULT_SERVICE = "service:authentication-api"


def classify_question(question: str, provider: LLMProvider) -> tuple[str, str]:
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
        return (
            parsed.get("tool", "get_service_overview"),
            parsed.get("service_id", DEFAULT_SERVICE),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Classifier fallback (%s)", e)
        return "get_service_overview", DEFAULT_SERVICE


def process_question(request: ChatRequest) -> ChatResponse:
    mid = str(uuid.uuid4())
    question = request.question

    try:
        provider = get_provider()
    except OSError as e:
        logger.error("Provider not configured: %s", e)
        return ChatResponse(
            message_id=mid,
            answer=(
                "WEAVE's AI agent is not configured. "
                "Set LLM_PROVIDER and LLM_API_KEY in .env."
            ),
            warnings=[str(e)],
        )

    tool_name, service_id = classify_question(question, provider)
    logger.info("Intent: tool=%s service=%s", tool_name, service_id)

    try:
        result = call_tool(tool_name, {"service_id": service_id})
    except (ToolNotFoundError, ToolExecutionError) as e:
        logger.error("Tool failed: %s", e)
        return ChatResponse(message_id=mid, answer=EMPTY, warnings=[str(e)])

    answer = generate_answer(question, result, provider)
    graph = tool_result_to_graph_view(result)
    evidence = tool_result_to_evidence(tool_name, result)
    followups = suggest_followups(graph, tool_name)

    return ChatResponse(
        message_id=mid,
        answer=answer,
        evidence=evidence,
        graph=graph,
        suggested_followups=followups,
        intent=tool_name,
    )
