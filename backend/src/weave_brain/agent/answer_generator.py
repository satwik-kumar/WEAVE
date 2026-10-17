import logging

from weave_brain.agent.prompts import build_answer_messages
from weave_brain.agent.provider import LLMProvider

logger = logging.getLogger(__name__)

EMPTY = (
    "The knowledge graph does not have enough information for this question. "
    "Try asking about the authentication service."
)


def generate_answer(question: str, evidence: dict, provider: LLMProvider) -> str:
    if not evidence:
        logger.warning("Empty evidence for: %s", question)
        return EMPTY
    try:
        return provider.complete(build_answer_messages(question, evidence)).strip()
    except Exception as e:  # noqa: BLE001
        logger.error("Answer generation failed: %s", e)
        return (
            "I had trouble generating an answer. "
            "The graph data was retrieved successfully try again."
        )
