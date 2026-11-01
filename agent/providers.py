import os
import json
from typing import Any, Dict, Optional
import openai
import anthropic


class BaseLLMProvider:
    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        raise NotImplementedError


class DemoLLMProvider(BaseLLMProvider):
    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if "evidence extraction" in prompt.lower() or "extract" in prompt.lower():
            return json.dumps({
                "has_ecommerce_channel": True,
                "price_tier": "premium",
                "summary": "Demo extracted evidence successfully."
            })
        elif "explanation" in prompt.lower() or "priority" in prompt.lower():
            return json.dumps({
                "priority_note": "High priority brand with active e-commerce and verified UK storefront.",
                "recommended_next_step": "Reach out to commercial partnership team for retail feature."
            })
        return json.dumps({"status": "ok"})


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider.")
        self.client = openai.OpenAI(api_key=self.api_key)

    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider.")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)
        return response.content[0].text if response.content else ""


def get_llm_provider(mode: str) -> BaseLLMProvider:
    if mode == "demo":
        return DemoLLMProvider()
    
    provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini" if provider_name == "openai" else "claude-3-5-sonnet-20241022")
    
    if provider_name == "anthropic":
        return AnthropicProvider(model=model)
    return OpenAIProvider(model=model)
