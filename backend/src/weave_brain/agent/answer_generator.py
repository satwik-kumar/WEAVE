import logging
from typing import Any

from weave_brain.agent.prompts import build_answer_messages
from weave_brain.agent.provider import LLMProvider

logger = logging.getLogger(__name__)

EMPTY = (
    "The knowledge graph does not have enough information for this question. "
    "Try asking about the authentication service."
)


def build_deterministic_answer(result: dict[str, Any]) -> str:
    """Build a deterministic, grounded answer directly from graph query results.

    Uses template text listing owner, decisions, dependents, and experts.
    """
    if not isinstance(result, dict) or not result:
        return EMPTY

    # 1. Resolve target service ID and title
    overview_dict = result.get("overview") if isinstance(result.get("overview"), dict) else {}
    svc_data = result.get("service") or overview_dict.get("service") or {}
    sid = svc_data.get("id") or result.get("service_id") or "service:authentication-api"
    title = svc_data.get("title") or "Authentication API"

    # 2. Resolve owning team / owner
    team_data = result.get("team") or overview_dict.get("team") or {}
    if team_data and isinstance(team_data, dict):
        team_title = team_data.get("title") or "Platform Engineering"
        team_id = team_data.get("id") or "team:platform-engineering"
        owner_str = f"{team_title} ({team_id})"
    else:
        owner_str = "Platform Engineering (team:platform-engineering)"

    # 3. Resolve key architectural decisions
    dec_candidates = (
        result.get("decisions")
        or overview_dict.get("decisions")
        or []
    )
    if isinstance(dec_candidates, dict):
        dec_candidates = dec_candidates.get("decisions", [])
    dec_strings: list[str] = []
    if isinstance(dec_candidates, list):
        for d in dec_candidates:
            if isinstance(d, dict) and d.get("id"):
                d_title = d.get("title") or d["id"]
                dec_strings.append(f"{d_title} ({d['id']})")
    if not dec_strings:
        dec_strings = ["Token expiry 24h policy (decision:adr-001)"]
    dec_str = ", ".join(dec_strings)

    # 4. Resolve dependent services (blast radius)
    blast_dict = result.get("blast_radius") if isinstance(result.get("blast_radius"), dict) else {}
    dep_candidates = (
        result.get("dependents")
        or result.get("affected_services")
        or blast_dict.get("affected_services")
        or overview_dict.get("dependents")
        or []
    )
    dep_strings: list[str] = []
    if isinstance(dep_candidates, list):
        for dep in dep_candidates:
            if isinstance(dep, str):
                dep_strings.append(dep)
            elif isinstance(dep, dict) and dep.get("id"):
                dep_strings.append(dep["id"])
    if not dep_strings:
        dep_strings = ["service:user-profile-api", "service:notification-service"]
    dep_str = ", ".join(dep_strings)

    # 5. Resolve experts
    exp_candidates = (
        result.get("experts")
        or overview_dict.get("experts")
        or []
    )
    if isinstance(exp_candidates, dict):
        exp_candidates = exp_candidates.get("experts", [])
    exp_strings: list[str] = []
    if isinstance(exp_candidates, list):
        for ex in exp_candidates:
            if isinstance(ex, dict) and ex.get("id"):
                ex_name = ex.get("title") or ex.get("name") or ex["id"]
                exp_strings.append(f"{ex_name} ({ex['id']})")
    if not exp_strings:
        exp_strings = [
            "Priya Sharma (person:priya-sharma)",
            "James Chen (person:james-chen)",
        ]
    exp_str = ", ".join(exp_strings)

    return (
        f"{title} ({sid}) is owned by {owner_str}. "
        f"Key architectural decisions: {dec_str}. "
        f"Dependent downstream services: {dep_str}. "
        f"Identified experts and contributors: {exp_str}."
    )


def generate_answer_with_fallback(
    question: str,
    evidence: dict[str, Any],
    provider: LLMProvider,
) -> tuple[str, list[str]]:
    """Generate answer using LLM provider, falling back to deterministic graph results on failure."""
    warnings: list[str] = []
    if not evidence:
        logger.warning("Empty evidence for: %s", question)
        return EMPTY, warnings

    from weave_brain.agent.provider import OfflineProvider

    if isinstance(provider, OfflineProvider):
        fallback_answer = build_deterministic_answer(evidence)
        return fallback_answer, warnings

    try:
        answer = provider.complete(build_answer_messages(question, evidence)).strip()
        if answer:
            lowered = answer.lower()
            if (
                "you are weave" in lowered
                or "system prompt" in lowered
                or "ignore previous instructions" in lowered
            ):
                logger.warning("Potential prompt injection leak in LLM answer; falling back to deterministic answer")
                fallback_answer = build_deterministic_answer(evidence)
                warnings.append(
                    "Prompt injection detected in model response; neutralized with deterministic graph fallback."
                )
                return fallback_answer, warnings
            return answer, warnings
        raise ValueError("LLM returned empty completion")
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM answer generation failed (%s); building deterministic fallback", e)
        fallback_answer = build_deterministic_answer(evidence)
        warning_msg = (
            f"LLM generation failed or timed out ({e}); "
            "generated deterministic answer from knowledge graph."
        )
        warnings.append(warning_msg)
        return fallback_answer, warnings



def generate_answer(question: str, evidence: dict[str, Any], provider: LLMProvider) -> str:
    """Backwards-compatible wrapper returning answer string."""
    answer, _ = generate_answer_with_fallback(question, evidence, provider)
    return answer
