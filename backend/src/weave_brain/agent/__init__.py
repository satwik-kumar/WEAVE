"""Agent package for WEAVE engineering knowledge assistant."""

from weave_brain.agent.answer_generator import (
    EMPTY,
    build_deterministic_answer,
    generate_answer,
    generate_answer_with_fallback,
)
from weave_brain.agent.citations import (
    extract_citations,
    get_valid_ids,
    verify_and_sanitize_response,
    verify_citations,
)
from weave_brain.agent.mapper import (
    tool_result_to_evidence,
    tool_result_to_graph_view,
)
from weave_brain.agent.orchestrator import (
    classify_question,
    extract_service_id,
    process_question,
    rule_based_classify,
)
from weave_brain.agent.prompts import (
    ANSWER_SYSTEM,
    CLASSIFIER_SYSTEM,
    UNTRUSTED_DATA_END,
    UNTRUSTED_DATA_START,
    build_answer_messages,
    build_classifier_messages,
    sanitize_untrusted_evidence,
    wrap_untrusted_data,
)
from weave_brain.agent.provider import (
    AnthropicProvider,
    LLMProvider,
    OfflineProvider,
    OpenAIProvider,
    get_provider,
)
from weave_brain.agent.suggestions import suggest_followups
from weave_brain.agent.tools import (
    TOOL_ALLOWLIST,
    TOOL_REGISTRY,
    InvalidEntityIdError,
    ToolExecutionError,
    ToolNotFoundError,
    call_tool,
    get_tool_descriptions,
    is_valid_canonical_id,
    validate_canonical_id,
)

__all__ = [
    "ANSWER_SYSTEM",
    "CLASSIFIER_SYSTEM",
    "EMPTY",
    "TOOL_ALLOWLIST",
    "TOOL_REGISTRY",
    "UNTRUSTED_DATA_END",
    "UNTRUSTED_DATA_START",
    "AnthropicProvider",
    "InvalidEntityIdError",
    "LLMProvider",
    "OfflineProvider",
    "OpenAIProvider",
    "ToolExecutionError",
    "ToolNotFoundError",
    "build_answer_messages",
    "build_classifier_messages",
    "build_deterministic_answer",
    "call_tool",
    "classify_question",
    "extract_citations",
    "extract_service_id",
    "generate_answer",
    "generate_answer_with_fallback",
    "get_provider",
    "get_tool_descriptions",
    "get_valid_ids",
    "is_valid_canonical_id",
    "process_question",
    "rule_based_classify",
    "sanitize_untrusted_evidence",
    "suggest_followups",
    "tool_result_to_evidence",
    "tool_result_to_graph_view",
    "validate_canonical_id",
    "verify_and_sanitize_response",
    "verify_citations",
    "wrap_untrusted_data",
]

