"""Ollama local LLM generation adapter.

Calls the Ollama REST API directly — no extra dependencies needed.
"""

from __future__ import annotations

import json
import urllib.request
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
class OllamaGenerationAdapter(BaseAdapter):
    """Generate answers using a local Ollama instance."""

    @property
    def name(self) -> str:
        return "ollama_gen"

    @property
    def category(self) -> str:
        return "generation"

    def generate(
        self, query: str, context: list[OmniChunk], **kwargs: Any
    ) -> GenerationResult:
        """Generate an answer via Ollama.

        Params:
            model: Ollama model name (default: 'phi3').
            base_url: Ollama API URL (default: http://localhost:11434).
            prompt_template: Custom prompt with {query} and {context}.
            temperature: Sampling temperature (default: 0.3).
        """
        model: str = kwargs.get("model", "phi3")
        base_url: str = kwargs.get(
            "base_url", "http://localhost:11434"
        )
        prompt_template: str = kwargs.get(
            "prompt_template", _DEFAULT_PROMPT
        )
        temperature: float = kwargs.get("temperature", 0.3)

        context_text = "\n\n".join(
            f"[{i+1}] {c.content}" for i, c in enumerate(context)
        )
        prompt = prompt_template.format(
            query=query, context=context_text
        )

        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }).encode()

        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310
                data = json.loads(resp.read())
        except Exception as e:
            return GenerationResult(
                answer=f"Ollama error: {e}",
                confidence=0.0,
                metadata={"model": model, "error": str(e)},
            )

        answer = data.get("response", "")

        return GenerationResult(
            answer=answer,
            citations=[c.id for c in context],
            confidence=0.75,
            metadata={
                "model": model,
                "eval_count": data.get("eval_count", 0),
                "eval_duration_ns": data.get("eval_duration", 0),
                "total_duration_ns": data.get("total_duration", 0),
            },
        )
