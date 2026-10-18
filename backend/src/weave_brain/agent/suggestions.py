from weave_brain.domain.models import GraphView


def suggest_followups(graph: GraphView, intent: str) -> list[str]:
    node_types = {n.type for n in graph.nodes} if graph else set()
    candidates: list[str] = []

    if intent == "get_service_overview":
        candidates += [
            "What breaks if this service goes down?",
            "Who are the experts for this service?",
        ]
    elif intent == "get_blast_radius":
        candidates += [
            "Who owns the most critical dependent service?",
            "What decisions govern this service?",
        ]
    elif intent == "get_decisions_for_service":
        candidates += [
            "What incidents motivated these decisions?",
            "Who should I talk to about this service?",
        ]
    elif intent == "find_experts":
        candidates += [
            "Tell me more about this service.",
            "What decisions has this team made?",
        ]
    elif intent == "get_onboarding_brief":
        candidates.append(
            "What should I be careful about before changing this service?"
        )

    if "incident" in node_types and intent != "get_decisions_for_service":
        candidates.append("What incidents have affected this service?")
    if "decision" in node_types and intent not in (
        "get_decisions_for_service",
        "get_onboarding_brief",
    ):
        candidates.append("Why was the main architectural decision made?")

    seen: set[str] = set()
    result: list[str] = []
    for s in candidates:
        if s not in seen:
            seen.add(s)
            result.append(s)
        if len(result) == 3:
            break
    return result
