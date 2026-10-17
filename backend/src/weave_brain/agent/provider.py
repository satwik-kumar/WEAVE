import os
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        pass


class AnthropicProvider(LLMProvider):
    def __init__(self):
        import anthropic

        key = os.environ.get("LLM_API_KEY")
        if not key:
            raise OSError("LLM_API_KEY not set. Add it to env")
        self.client = anthropic.Anthropic(api_key=key)
        self.model = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")

    def complete(self, messages: list[dict]) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        convo = [m for m in messages if m["role"] != "system"]
        r = self.client.messages.create(
            model=self.model, max_tokens=512, system=system, messages=convo
        )
        return r.content[0].text


class OpenAIProvider(LLMProvider):
    def __init__(self):
        import openai

        key = os.environ.get("LLM_API_KEY")
        if not key:
            raise OSError("LLM_API_KEY not set.")
        self.client = openai.OpenAI(api_key=key)
        self.model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    def complete(self, messages: list[dict]) -> str:
        r = self.client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=512
        )
        return r.choices[0].message.content


def get_provider() -> LLMProvider:
    name = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Use 'anthropic' or 'openai'.")
