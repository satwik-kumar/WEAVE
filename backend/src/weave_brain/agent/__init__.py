"""Agent package for WEAVE engineering knowledge assistant."""

from weave_brain.agent.answer_generator import EMPTY, generate_answer
from weave_brain.agent.mapper import (
    tool_result_to_evidence,
    tool_result_to_graph_view,
)
from weave_brain.agent.orchestrator import (
    classify_question,
    process_question,
)
from weave_brain.agent.prompts import (
    ANSWER_SYSTEM,
    CLASSIFIER_SYSTEM,
    build_answer_messages,
    build_classifier_messages,
)
from weave_brain.agent.provider import (
    AnthropicProvider,
    LLMProvider,
    OpenAIProvider,
    get_provider,
)
from weave_brain.agent.suggestions import suggest_followups
from weave_brain.agent.tools import (
    TOOL_REGISTRY,
    ToolExecutionError,
    ToolNotFoundError,
    call_tool,
    get_tool_descriptions,
)

__all__ = [
    "ANSWER_SYSTEM",
    "CLASSIFIER_SYSTEM",
    "EMPTY",
    "TOOL_REGISTRY",
    "AnthropicProvider",
    "LLMProvider",
    "OpenAIProvider",
    "ToolExecutionError",
    "ToolNotFoundError",
    "build_answer_messages",
    "build_classifier_messages",
    "call_tool",
    "classify_question",
    "generate_answer",
    "get_provider",
    "get_tool_descriptions",
    "process_question",
    "suggest_followups",
    "tool_result_to_evidence",
    "tool_result_to_graph_view",
]
