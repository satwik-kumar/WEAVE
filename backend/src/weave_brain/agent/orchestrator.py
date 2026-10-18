import json
import logging
import uuid

from weave_brain.agent.answer_generator import (
    EMPTY,
    generate_answer_with_fallback,
)
from weave_brain.agent.citations import verify_and_sanitize_response
from weave_brain.agent.mapper import (
    tool_result_to_evidence,
    tool_result_to_graph_view,
)
from weave_brain.agent.prompts import build_classifier_messages
from weave_brain.agent.provider import LLMProvider, OfflineProvider, get_provider
from weave_brain.agent.suggestions import suggest_followups
from weave_brain.agent.tools import (
    TOOL_ALLOWLIST,
    ToolExecutionError,
    ToolNotFoundError,
    call_tool,
    is_valid_canonical_id,
)
from weave_brain.domain.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

DEFAULT_SERVICE = "service:authentication-api"


def extract_service_id(question: str) -> str:
    """Extract canonical service ID from question text or fallback to DEFAULT_SERVICE."""
    q = question.lower()
    if "user-profile-api" in q or "user-profile" in q or "user profile" in q:
        return "service:user-profile-api"
    if "notification-service" in q or "notification" in q:
        return "service:notification-service"
    if "data-pipeline" in q or "data pipeline" in q:
        return "service:data-pipeline"
    if "auth-api" in q or "authentication-api" in q or "authentication" in q or "auth" in q:
        return "service:authentication-api"
    return DEFAULT_SERVICE


def rule_based_classify(question: str) -> tuple[str, str]:
    """Deterministic routing classifier matching canonical intent patterns and service IDs."""
    q = question.lower()
    sid = extract_service_id(question)

    # 1. Onboarding Brief (high specificity)
    onboarding_patterns = [
        "onboard",
        "onboarding",
        "getting started",
        "get started",
        "new to",
        "new engineer",
        "new team member",
    ]
    if any(pat in q for pat in onboarding_patterns):
        return "get_onboarding_brief", sid

    # 2. Blast Radius / Downstream Impact
    blast_radius_patterns = [
        "blast radius",
        "what breaks",
        "breaks if",
        "break if",
        "downstream",
        "impact",
        "impacted",
        "outage",
        "goes down",
        "go down",
        "fails",
        "failover",
        "depend on",
        "dependents",
    ]
    if any(pat in q for pat in blast_radius_patterns):
        return "get_blast_radius", sid

    # 3. Architectural Decisions / ADRs / Rationale
    decisions_patterns = [
        "decision",
        "decisions",
        "adr",
        "adrs",
        "why was",
        "policy",
        "rationale",
        "motivat",
        "supersed",
        "architectural decision",
    ]
    if any(pat in q for pat in decisions_patterns):
        return "get_decisions_for_service", sid

    # 4. Service Overview / Ownership / Description (e.g. explain, who owns, what does)
    overview_patterns = [
        "who owns",
        "which team",
        "what team",
        "overview",
        "explain",
        "what does",
        "architecture",
        "describe",
    ]
    if any(pat in q for pat in overview_patterns):
        return "get_service_overview", sid

    # 5. Expertise / Knowledge Holders
    experts_patterns = [
        "expert",
        "experts",
        "expertise",
        "who knows",
        "who worked",
        "who has worked",
        "who to ask",
        "who should i talk to",
        "who to contact",
    ]
    if any(pat in q for pat in experts_patterns):
        return "find_experts", sid

    return "get_service_overview", sid


def classify_question(
    question: str,
    provider: LLMProvider | None = None,
) -> tuple[str, str]:
    """Classify a question to a tool and service ID with LLM or rule-based fallback."""
    if provider is not None and not isinstance(provider, OfflineProvider):
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
            sid = parsed.get("service_id") or extract_service_id(question)
            if tool in TOOL_ALLOWLIST:
                if is_valid_canonical_id(sid):
                    return tool, sid
                logger.warning("Classifier returned malformed service_id '%s'; falling back", sid)
            else:
                logger.warning("Model selected unknown tool '%s' not in allowlist; rejecting.", tool)
        except Exception as e:  # noqa: BLE001
            logger.debug("Classifier LLM parsing fallback (%s)", e)


    return rule_based_classify(question)


def process_question(
    request: ChatRequest,
    provider: LLMProvider | None = None,
) -> ChatResponse:
    mid = str(uuid.uuid4())
    question = request.question
    warnings: list[str] = []

    if provider is None:
        try:
            provider = get_provider()
        except Exception as e:  # noqa: BLE001
            logger.debug("Provider init fallback to OfflineProvider: %s", e)
            provider = OfflineProvider()

    tool_name, service_id = classify_question(question, provider)
    logger.info("Intent: tool=%s service=%s", tool_name, service_id)

    try:
        result = call_tool(tool_name, {"service_id": service_id})
    except (ToolNotFoundError, ToolExecutionError) as e:
        logger.error("Tool failed: %s", e)
        return ChatResponse(message_id=mid, answer=EMPTY, warnings=[str(e)])

    answer, gen_warnings = generate_answer_with_fallback(question, result, provider)
    warnings.extend(gen_warnings)

    graph = tool_result_to_graph_view(result)
    evidence = tool_result_to_evidence(tool_name, result)
    followups = suggest_followups(graph, tool_name)

    response = ChatResponse(
        message_id=mid,
        answer=answer,
        evidence=evidence,
        graph=graph,
        suggested_followups=followups,
        intent=tool_name,
        warnings=warnings,
    )

    return verify_and_sanitize_response(response)
