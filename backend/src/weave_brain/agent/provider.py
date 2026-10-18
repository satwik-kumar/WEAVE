"""Configurable LLM provider architecture with zero-cost support and safe fallbacks."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from weave_brain.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Official endpoints for OpenAI-compatible and REST providers
DEFAULT_BASE_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}

# Default models per provider
# Note on zero-cost policy:
# - groq: llama-3.1-8b-instant verified under Groq free tier
# - gemini: gemini-1.5-flash verified under Google AI Studio free tier
# - openrouter: openrouter/free meta-router verified for zero-cost routing
# - ollama: llama3.2 (requires local Ollama server running)
# - openai / anthropic: commercial/paid only; not default
DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.1-8b-instant",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openrouter/free",
    "ollama": "llama3.2",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
}


class LLMProviderError(Exception):
    """Base exception for provider errors. Never includes secret credentials."""


class ConfigurationError(LLMProviderError):
    """Raised when provider configuration or credentials are missing/invalid."""


class QuotaExceededError(LLMProviderError):
    """Raised when provider rate limits or quotas are exceeded (HTTP 429)."""


class ProviderTimeoutError(LLMProviderError):
    """Raised when provider request times out."""


class DeterministicModeActive(LLMProviderError):
    """Raised when deterministic mode is intentionally selected (no LLM configured)."""


class LLMProvider(ABC):
    """Abstract base contract for model completions."""

    @abstractmethod
    def complete(self, messages: list[dict[str, Any]]) -> str:
        """Complete a conversation given standard message dicts."""


class DeterministicProvider(LLMProvider):
    """Explicitly bypasses LLM calls in favor of deterministic rule-based processing."""

    def complete(self, messages: list[dict[str, Any]]) -> str:
        raise DeterministicModeActive("Deterministic mode active; LLM calls bypassed.")


class BaseHTTPProvider(LLMProvider):
    """Shared HTTP client with timeout, bounded retries, and secret-safe error masking."""

    def __init__(
        self,
        provider_name: str,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def _mask_secrets(self, text: str) -> str:
        """Strip raw API key if present in error message string."""
        if self.api_key and len(self.api_key) > 4:
            text = text.replace(self.api_key, "[REDACTED_API_KEY]")
        return text

    def _post_with_retry(
        self, url: str, headers: dict[str, str], json_body: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute HTTP POST with bounded retries on 5xx or timeouts, failing immediately on 4xx."""
        attempts = 0
        last_err: Exception | None = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=json_body)

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception as e:
                        raise LLMProviderError(
                            f"{self.provider_name} returned non-JSON response."
                        ) from e

                if resp.status_code == 429:
                    raise QuotaExceededError(
                        f"{self.provider_name} rate limit or quota exceeded (HTTP 429). Preserving deterministic fallback without paid escalation."
                    )

                if resp.status_code in (401, 403):
                    raise ConfigurationError(
                        f"{self.provider_name} authentication failed (HTTP {resp.status_code}). Check your API key."
                    )

                if resp.status_code >= 500 and attempts <= self.max_retries:
                    logger.warning(
                        "%s returned HTTP %s; retrying attempt %s/%s",
                        self.provider_name,
                        resp.status_code,
                        attempts,
                        self.max_retries,
                    )
                    continue

                detail = resp.text[:300] if resp.text else f"status {resp.status_code}"
                detail = self._mask_secrets(detail)
                raise LLMProviderError(
                    f"{self.provider_name} request failed (HTTP {resp.status_code}): {detail}"
                )

            except httpx.TimeoutException as e:
                last_err = e
                if attempts <= self.max_retries:
                    logger.warning(
                        "%s request timed out; retrying attempt %s/%s",
                        self.provider_name,
                        attempts,
                        self.max_retries,
                    )
                    continue
                raise ProviderTimeoutError(
                    f"{self.provider_name} request timed out after {self.timeout}s."
                ) from e
            except (QuotaExceededError, ConfigurationError, LLMProviderError):
                raise
            except Exception as e:
                last_err = e
                if attempts <= self.max_retries:
                    continue
                safe_msg = self._mask_secrets(str(e))
                raise LLMProviderError(
                    f"{self.provider_name} communication failure: {safe_msg}"
                ) from e

        safe_last = self._mask_secrets(str(last_err)) if last_err else "unknown error"
        raise LLMProviderError(
            f"{self.provider_name} failed after {self.max_retries} retries: {safe_last}"
        )


class OpenAICompatibleProvider(BaseHTTPProvider):
    """Adapter for OpenAI-compatible REST endpoints (Groq, OpenRouter, Ollama, OpenAI)."""

    def __init__(
        self,
        provider_name: str,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            provider_name=provider_name,
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        # Ollama does not require an API key; hosted providers do
        if provider_name != "ollama" and not api_key:
            raise ConfigurationError(
                f"Missing API key for {provider_name}. Please configure {provider_name.upper()}_API_KEY or LLM_API_KEY."
            )

    def complete(self, messages: list[dict[str, Any]]) -> str:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "WEAVE-Brain-Knowledge-Assistant",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # OpenRouter-specific attribution headers if using OpenRouter
        if self.provider_name == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/satwik-kumar/WEAVE"
            headers["X-Title"] = "WEAVE Knowledge Assistant"

        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 512,
        }

        data = self._post_with_retry(f"{self.base_url}/chat/completions", headers, body)
        try:
            choices = data.get("choices")
            if not choices or not isinstance(choices, list):
                raise ValueError("Response missing 'choices' array")
            content = choices[0].get("message", {}).get("content", "")
            return content.strip()
        except Exception as e:
            raise LLMProviderError(
                f"Malformed completion response from {self.provider_name}: {e}"
            ) from e


class OpenAIProvider(OpenAICompatibleProvider):
    """Convenience alias for OpenAI endpoint compatibility."""

    def __init__(
        self,
        model: str = DEFAULT_MODELS["openai"],
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URLS["openai"],
        timeout: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            provider_name="openai",
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )


class GeminiProvider(BaseHTTPProvider):
    """Adapter for Google Gemini REST generateContent endpoint."""

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str = DEFAULT_BASE_URLS["gemini"],
        timeout: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        if not api_key:
            raise ConfigurationError(
                "Missing Gemini API key. Please configure GEMINI_API_KEY or LLM_API_KEY."
            )
        super().__init__(
            provider_name="gemini",
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    def complete(self, messages: list[dict[str, Any]]) -> str:
        # Convert standard OpenAI-style messages to Gemini contents & system_instruction
        system_text = ""
        contents = []

        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                system_text += f"{content}\n"
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": 512,
            },
        }
        if system_text.strip():
            body["system_instruction"] = {"parts": [{"text": system_text.strip()}]}

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        data = self._post_with_retry(url, headers, body)
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("Response missing 'candidates'")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise ValueError("Response candidate missing 'parts'")
            return parts[0].get("text", "").strip()
        except Exception as e:
            raise LLMProviderError(
                f"Malformed response from Gemini generateContent: {e}"
            ) from e


class AnthropicProvider(BaseHTTPProvider):
    """Adapter for Anthropic REST messages endpoint."""

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str = DEFAULT_BASE_URLS["anthropic"],
        timeout: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        if not api_key:
            raise ConfigurationError(
                "Missing Anthropic API key. Please configure ANTHROPIC_API_KEY or LLM_API_KEY."
            )
        super().__init__(
            provider_name="anthropic",
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    def complete(self, messages: list[dict[str, Any]]) -> str:
        system_text = ""
        anthropic_messages = []

        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                system_text += f"{content}\n"
            else:
                anthropic_messages.append({"role": role, "content": content})

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
        }
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 512,
            "messages": anthropic_messages,
        }
        if system_text.strip():
            body["system"] = system_text.strip()

        data = self._post_with_retry(f"{self.base_url}/messages", headers, body)
        try:
            content_blocks = data.get("content", [])
            if not content_blocks:
                raise ValueError("Response missing 'content' array")
            return content_blocks[0].get("text", "").strip()
        except Exception as e:
            raise LLMProviderError(f"Malformed response from Anthropic API: {e}") from e


def _resolve_api_key(settings: Settings, provider_name: str) -> str | None:
    """Resolve provider-specific or generic API key from settings."""
    key_field = f"{provider_name}_api_key"
    if hasattr(settings, key_field):
        secret = getattr(settings, key_field)
        if secret and secret.get_secret_value().strip():
            return secret.get_secret_value().strip()

    if settings.llm_api_key and settings.llm_api_key.get_secret_value().strip():
        return settings.llm_api_key.get_secret_value().strip()

    return None


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Instantiate and return the configured LLMProvider based on authoritative Settings."""
    if settings is None:
        settings = get_settings()

    provider_name = (settings.llm_provider or "deterministic").lower().strip()

    if provider_name == "deterministic":
        return DeterministicProvider()

    # Determine model and base URL
    model = (
        settings.llm_model.strip()
        if settings.llm_model and settings.llm_model.strip()
        else DEFAULT_MODELS.get(provider_name, "")
    )
    base_url = (
        settings.llm_base_url.strip()
        if settings.llm_base_url and settings.llm_base_url.strip()
        else DEFAULT_BASE_URLS.get(provider_name, "")
    )
    api_key = _resolve_api_key(settings, provider_name)
    timeout = settings.llm_timeout
    retries = settings.llm_max_retries

    if provider_name in ("groq", "openrouter", "ollama", "openai"):
        return OpenAICompatibleProvider(
            provider_name=provider_name,
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=retries,
        )

    if provider_name == "gemini":
        return GeminiProvider(
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=retries,
        )

    if provider_name == "anthropic":
        return AnthropicProvider(
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=retries,
        )

    raise ConfigurationError(
        f"Unsupported LLM provider '{provider_name}'. Supported: deterministic, groq, gemini, openrouter, ollama, anthropic, openai."
    )
