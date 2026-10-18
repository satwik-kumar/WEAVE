"""Focused unit tests for configurable LLM providers and zero-cost guardrails."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from weave_brain.agent.provider import (
    AnthropicProvider,
    ConfigurationError,
    DeterministicModeActive,
    DeterministicProvider,
    GeminiProvider,
    LLMProviderError,
    OpenAICompatibleProvider,
    ProviderTimeoutError,
    QuotaExceededError,
    get_provider,
)
from weave_brain.core.config import Settings


def test_deterministic_provider_selection_and_behavior():
    """Verify deterministic provider raises DeterministicModeActive cleanly."""
    settings = Settings(llm_provider="deterministic")
    provider = get_provider(settings)
    assert isinstance(provider, DeterministicProvider)
    with pytest.raises(DeterministicModeActive, match="Deterministic mode active"):
        provider.complete([{"role": "user", "content": "hello"}])


def test_unsupported_provider_raises_configuration_error():
    """Verify unsupported provider name raises ConfigurationError."""
    # We bypass pydantic validation here to test factory validation
    settings = Settings.model_construct(llm_provider="unsupported_ai")
    with pytest.raises(ConfigurationError, match="Unsupported LLM provider"):
        get_provider(settings)


def test_missing_credentials_for_hosted_providers():
    """Verify missing credentials raise clear ConfigurationError without crashes."""
    # Groq missing key
    s_groq = Settings(llm_provider="groq", groq_api_key=None, llm_api_key=None)
    with pytest.raises(ConfigurationError, match="Missing API key for groq"):
        get_provider(s_groq)

    # Gemini missing key
    s_gemini = Settings(llm_provider="gemini", gemini_api_key=None, llm_api_key=None)
    with pytest.raises(ConfigurationError, match="Missing Gemini API key"):
        get_provider(s_gemini)

    # Anthropic missing key
    s_anthropic = Settings(
        llm_provider="anthropic", anthropic_api_key=None, llm_api_key=None
    )
    with pytest.raises(ConfigurationError, match="Missing Anthropic API key"):
        get_provider(s_anthropic)

    # OpenRouter missing key
    s_openrouter = Settings(
        llm_provider="openrouter", openrouter_api_key=None, llm_api_key=None
    )
    with pytest.raises(ConfigurationError, match="Missing API key for openrouter"):
        get_provider(s_openrouter)


def test_ollama_provider_does_not_require_api_key():
    """Verify local Ollama provider works without an API key."""
    settings = Settings(
        llm_provider="ollama",
        llm_base_url="http://localhost:11434/v1",
        llm_model="llama3.2",
    )
    provider = get_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.api_key is None
    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.model == "llama3.2"


def test_generic_api_key_fallback():
    """Verify generic LLM_API_KEY is used when provider-specific key is not set."""
    settings = Settings(
        llm_provider="groq",
        groq_api_key=None,
        llm_api_key=SecretStr("generic-secret-key-123"),
    )
    provider = get_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.api_key == "generic-secret-key-123"


def test_provider_specific_api_key_takes_precedence():
    """Verify provider-specific key takes precedence over generic key."""
    settings = Settings(
        llm_provider="groq",
        groq_api_key=SecretStr("groq-specific-key-456"),
        llm_api_key=SecretStr("generic-secret-key-123"),
    )
    provider = get_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.api_key == "groq-specific-key-456"


@patch("httpx.Client.post")
def test_openai_compatible_success(mock_post):
    """Verify OpenAI-compatible completion parsing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"tool": "get_service_overview", "service_id": "service:authentication-api"}',
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    provider = OpenAICompatibleProvider(
        provider_name="groq",
        model="llama-3.1-8b-instant",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk-mock-key-12345",
    )
    result = provider.complete([{"role": "user", "content": "who owns auth?"}])
    assert "get_service_overview" in result
    mock_post.assert_called_once()
    _args, kwargs = mock_post.call_args
    assert "Bearer gsk-mock-key-12345" in kwargs["headers"]["Authorization"]


@patch("httpx.Client.post")
def test_gemini_provider_success(mock_post):
    """Verify Gemini generateContent request format and response parsing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Authentication is owned by Platform Engineering."}
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    provider = GeminiProvider(
        model="gemini-1.5-flash",
        api_key="gemini-mock-key",
    )
    result = provider.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "who owns auth?"},
        ]
    )
    assert "Platform Engineering" in result
    mock_post.assert_called_once()
    url, kwargs = mock_post.call_args
    assert "key=gemini-mock-key" in url[0]
    assert "system_instruction" in kwargs["json"]
    assert kwargs["json"]["contents"][0]["parts"][0]["text"] == "who owns auth?"


@patch("httpx.Client.post")
def test_anthropic_provider_success(mock_post):
    """Verify Anthropic messages request format and response parsing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": "Platform Engineering owns this service."}]
    }
    mock_post.return_value = mock_resp

    provider = AnthropicProvider(
        model="claude-3-5-haiku-20241022",
        api_key="sk-ant-mock-key",
    )
    result = provider.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "who owns auth?"},
        ]
    )
    assert "Platform Engineering" in result
    mock_post.assert_called_once()
    _url, kwargs = mock_post.call_args
    assert kwargs["headers"]["x-api-key"] == "sk-ant-mock-key"
    assert kwargs["json"]["system"] == "You are helpful."


@patch("httpx.Client.post")
def test_quota_exceeded_error_no_paid_fallback(mock_post):
    """Verify HTTP 429 raises QuotaExceededError and never switches to paid fallback."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Rate limit reached for model llama-3.1-8b-instant"
    mock_post.return_value = mock_resp

    provider = OpenAICompatibleProvider(
        provider_name="groq",
        model="llama-3.1-8b-instant",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk-mock-key-12345",
        max_retries=1,
    )
    with pytest.raises(QuotaExceededError, match="rate limit or quota exceeded"):
        provider.complete([{"role": "user", "content": "test"}])


@patch("httpx.Client.post")
def test_timeout_and_bounded_retry(mock_post):
    """Verify timeout bounded retry behavior."""
    mock_post.side_effect = httpx.TimeoutException("Read timed out")

    provider = OpenAICompatibleProvider(
        provider_name="groq",
        model="llama-3.1-8b-instant",
        base_url="https://api.groq.com/openai/v1",
        api_key="test-key",
        timeout=1.0,
        max_retries=1,
    )
    with pytest.raises(ProviderTimeoutError, match="request timed out after 1.0s"):
        provider._post_with_retry(
            "https://api.groq.com/openai/v1/test", {}, {"test": True}
        )
    # Initial attempt + 1 retry = 2 calls
    assert mock_post.call_count == 2


@patch("httpx.Client.post")
def test_secret_masking_in_error_messages(mock_post):
    """Verify sensitive API keys are never exposed in exception strings."""
    secret_key = "very-sensitive-private-api-key-999"
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = f"Server error occurred with authorization Bearer {secret_key}"
    mock_post.return_value = mock_resp

    provider = OpenAICompatibleProvider(
        provider_name="groq",
        model="llama-3.1-8b-instant",
        base_url="https://api.groq.com/openai/v1",
        api_key=secret_key,
        max_retries=0,
    )
    with pytest.raises(LLMProviderError) as exc_info:
        provider._post_with_retry(
            "https://api.groq.com/openai/v1/test", {}, {"test": True}
        )
    err_str = str(exc_info.value)
    assert secret_key not in err_str
    assert "[REDACTED_API_KEY]" in err_str


@patch("httpx.Client.post")
def test_malformed_response_handling(mock_post):
    """Verify malformed non-JSON or missing structure raises safe error."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"unexpected_key": []}
    mock_post.return_value = mock_resp

    provider = OpenAICompatibleProvider(
        provider_name="groq",
        model="llama-3.1-8b-instant",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk-mock-key",
    )
    with pytest.raises(LLMProviderError, match="Malformed completion response"):
        provider.complete([{"role": "user", "content": "hi"}])


# =========================================================================
# Orchestrator Integration & Regression Tests for Core Demo Questions
# =========================================================================

from weave_brain.agent.orchestrator import process_question
from weave_brain.domain.models import ChatRequest
from weave_brain.graph.fixtures import (
    find_experts_stub,
    get_blast_radius_stub,
    get_decisions_for_service_stub,
    get_service_overview_stub,
)


@pytest.fixture(autouse=True)
def mock_graph_tools_for_orchestrator(monkeypatch):
    """Ensure orchestrator tests run hermetically with offline fixtures and no live DB needed."""

    def _fake_call_tool(tool_name: str, args: dict):
        sid = args.get("service_id", "service:authentication-api")
        if tool_name == "get_service_overview":
            return get_service_overview_stub(sid)
        if tool_name == "get_decisions_for_service":
            return get_decisions_for_service_stub(sid)
        if tool_name == "get_blast_radius":
            return get_blast_radius_stub(sid)
        if tool_name == "find_experts":
            return {"experts": find_experts_stub(sid)}
        if tool_name == "get_onboarding_brief":
            return {
                "overview": get_service_overview_stub(sid),
                "decisions": get_decisions_for_service_stub(sid),
                "experts": find_experts_stub(sid),
                "blast_radius": get_blast_radius_stub(sid),
            }
        raise ValueError(f"Unknown tool {tool_name}")

    monkeypatch.setattr("weave_brain.agent.orchestrator.call_tool", _fake_call_tool)


def test_orchestrator_deterministic_mode_has_no_offline_warning():
    """Verify explicit deterministic mode produces no 'AI provider offline' warning."""
    with patch("weave_brain.agent.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value = Settings(llm_provider="deterministic")
        res = process_question(
            ChatRequest(question="who owns the authentication service")
        )
        assert res.warnings == []
        assert res.intent == "get_service_overview"
        assert "Platform Engineering" in res.answer
        assert len(res.evidence) > 0


def test_orchestrator_regression_core_question_1_ownership():
    """Regression test 1: who owns the authentication service."""
    res = process_question(ChatRequest(question="who owns the authentication service"))
    assert res.intent == "get_service_overview"
    assert "Platform Engineering" in res.answer
    assert any(e.source_id == "service:authentication-api" for e in res.evidence)


def test_orchestrator_regression_core_question_2_decisions():
    """Regression test 2: why was the token policy chosen."""
    res = process_question(ChatRequest(question="why was the token policy chosen"))
    assert res.intent == "get_decisions_for_service"
    assert "adr-001" in res.answer.lower() or "token" in res.answer.lower()
    assert any(e.source_id == "decision:adr-001" for e in res.evidence)


def test_orchestrator_regression_core_question_3_blast_radius():
    """Regression test 3: what breaks if authentication goes down."""
    res = process_question(
        ChatRequest(question="what breaks if authentication goes down")
    )
    assert res.intent == "get_blast_radius"
    assert "notification" in res.answer.lower() or "user-profile" in res.answer.lower()
    assert any("notification" in e.source_id for e in res.evidence)


def test_orchestrator_regression_core_question_4_experts():
    """Regression test 4: who knows about authentication."""
    res = process_question(ChatRequest(question="who knows about authentication"))
    assert res.intent == "find_experts"
    assert "priya" in res.answer.lower() or "chen" in res.answer.lower()
    assert any("priya" in e.source_id or "chen" in e.source_id for e in res.evidence)


@patch("weave_brain.agent.provider.OpenAICompatibleProvider.complete")
def test_orchestrator_mocked_llm_success(mock_complete):
    """Verify orchestrator uses mocked LLM classification and answer when configured."""
    mock_complete.side_effect = [
        '{"tool": "get_blast_radius", "service_id": "service:authentication-api"}',  # classifier
        "Mocked LLM Answer: If auth goes down, notification service and user profile will be impacted.",  # answer
    ]

    with patch("weave_brain.agent.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            llm_provider="groq",
            groq_api_key=SecretStr("gsk-mock-key"),
        )
        res = process_question(
            ChatRequest(question="what breaks if authentication fails?")
        )
        assert res.warnings == []
        assert res.intent == "get_blast_radius"
        assert "Mocked LLM Answer" in res.answer
        assert len(res.evidence) > 0


@patch("weave_brain.agent.provider.OpenAICompatibleProvider.complete")
def test_orchestrator_malformed_llm_response_falls_back_safely(mock_complete):
    """Verify malformed LLM response falls back cleanly to deterministic classification and answer."""
    mock_complete.side_effect = [
        "This is not valid json!",  # malformed classifier
        Exception("LLM generation exploded!"),  # failed answer
    ]

    with patch("weave_brain.agent.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            llm_provider="groq",
            groq_api_key=SecretStr("gsk-mock-key"),
        )
        res = process_question(
            ChatRequest(question="who owns the authentication service")
        )
        # Must fall back to deterministic classification and synthesis without crashing
        assert res.intent == "get_service_overview"
        assert "Platform Engineering" in res.answer
        assert len(res.evidence) > 0


def test_orchestrator_provider_failure_warning_and_deterministic_fallback():
    """Verify real provider initialization failure produces clean warning and deterministic answer."""
    with patch("weave_brain.agent.orchestrator.get_settings") as mock_settings:
        # Groq configured without any API key
        mock_settings.return_value = Settings(
            llm_provider="groq",
            groq_api_key=None,
            llm_api_key=None,
        )
        res = process_question(
            ChatRequest(question="who owns the authentication service")
        )
        assert len(res.warnings) == 1
        assert "AI provider offline: Missing API key for groq" in res.warnings[0]
        # Grounded deterministic response preserved
        assert res.intent == "get_service_overview"
        assert "Platform Engineering" in res.answer
        assert len(res.evidence) > 0
