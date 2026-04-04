"""OpenAI-compatible generation adapter.

Works with OpenAI, Ollama, vLLM, or any OpenAI-compatible API.
Uses the openai Python SDK.
"""

from __future__ import annotations

import os
from typing import Any

from omnirag.adapters.base import BaseAdapter
from omnirag.core.maturity import maturity_level
from omnirag.core.models import GenerationResult, OmniChunk


_DEFAULT_PROMPT = (
    "Answer the question based on the provided context.\n\n"
    "Context:\n{context}\n\n"
    "Question: {query}\n\n"
    "Answer:"
)


@maturity_level("core")
class OpenAIGenerationAdapter(BaseAdapter):
    """Generate answers using any OpenAI-compatible API."""

    @property
    def name(self) -> str:
        return "openai_gen"

    @property
    def category(self) -> str:
        return "generation"

    def generate(
        self, query: str, context: list[OmniChunk], **kwargs: Any
    ) -> GenerationResult:
        """Generate an answer using an LLM.

        Params:
            model: Model name (default: 'gpt-4o-mini').
            base_url: API base URL (default: OpenAI).
            api_key: API key (default: OPENAI_API_KEY env var).
            prompt_template: Custom prompt template with {query} and {context}.
            temperature: Sampling temperature (default: 0.3).
            max_tokens: Max response tokens (default: 1024).
        """
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "openai is required. Install with: pip install openai"
            ) from e

        model: str = kwargs.get("model", "gpt-4o-mini")
        base_url: str | None = kwargs.get("base_url")
        api_key: str = kwargs.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
        prompt_template: str = kwargs.get("prompt_template", _DEFAULT_PROMPT)
        temperature: float = kwargs.get("temperature", 0.3)
        max_tokens: int = kwargs.get("max_tokens", 1024)

        # Build context string from chunks
        context_text = "\n\n".join(
            f"[{i+1}] {c.content}" for i, c in enumerate(context)
        )

        prompt = prompt_template.format(query=query, context=context_text)

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        answer = response.choices[0].message.content or ""
        usage = response.usage

        return GenerationResult(
            answer=answer,
            citations=[c.id for c in context],
            confidence=0.8,  # Placeholder — could use logprobs
            metadata={
                "model": model,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
        )
