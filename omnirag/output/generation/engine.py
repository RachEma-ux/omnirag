"""Generation engine — citation-aware prompt, LLM adapters, citation extraction."""

from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

from omnirag.output.retrieval.hybrid import RetrievalResult

logger = structlog.get_logger(__name__)

PROMPT_TEMPLATE = """Answer the question using ONLY the following chunks. Cite each chunk as [doc_id:chunk_id].

Question: {query}

Chunks:
{chunks_with_citations}

Answer:"""


@dataclass
class Citation:
    doc_id: str
    chunk_id: str
    snippet: str
    relevance_score: float = 0.0


@dataclass
class GenerationResult:
    answer: str
    citations: list[Citation]
    latency_ms: float = 0
    model: str = ""
    tokens: int = 0


def build_prompt(query: str, chunks: list[RetrievalResult]) -> str:
    """Build the citation-aware prompt from query + retrieved chunks."""
    formatted = []
    for chunk in chunks:
        formatted.append(f"[{chunk.doc_id}:{chunk.chunk_id}] {chunk.content}")
    chunks_text = "\n\n".join(formatted)
    return PROMPT_TEMPLATE.format(query=query, chunks_with_citations=chunks_text)


def extract_citations(answer: str, chunks: list[RetrievalResult]) -> list[Citation]:
    """Extract [doc_id:chunk_id] citations from generated answer and validate."""
    pattern = r'\[([a-f0-9\-]+):([a-f0-9\-]+)\]'
    matches = re.findall(pattern, answer)

    valid_ids = {(c.doc_id, c.chunk_id) for c in chunks}
    chunk_map = {c.chunk_id: c for c in chunks}

    citations = []
    seen = set()
    for doc_id, chunk_id in matches:
        key = (doc_id, chunk_id)
        if key in seen:
            continue
        seen.add(key)
        chunk = chunk_map.get(chunk_id)
        citations.append(Citation(
            doc_id=doc_id,
            chunk_id=chunk_id,
            snippet=chunk.content[:100] if chunk else "",
            relevance_score=chunk.score if chunk else 0.0,
        ))
    return citations


# ─── LLM Adapters ───

class LLMAdapter(ABC):
    """Base LLM adapter — generate answer from query + chunks."""

    name: str = "base"

    @abstractmethod
    async def generate(self, prompt: str) -> tuple[str, int]:
        """Generate answer text. Returns (text, token_count)."""
        ...


class OllamaAdapter(LLMAdapter):
    """Local Ollama LLM."""
    name = "ollama"

    def __init__(self, model: str = "tinyllama", base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.base_url = base_url

    async def generate(self, prompt: str) -> tuple[str, int]:
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", ""), data.get("eval_count", 0)


class OpenAIAdapter(LLMAdapter):
    """OpenAI API."""
    name = "openai"

    def __init__(self, model: str = "gpt-4", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    async def generate(self, prompt: str) -> tuple[str, int]:
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return text, tokens


class FallbackAdapter(LLMAdapter):
    """Fallback: returns chunks as-is when no LLM is available."""
    name = "fallback"

    async def generate(self, prompt: str) -> tuple[str, int]:
        return "No LLM configured. Raw chunks returned in the evidence bundle.", 0


# ─── Engine ───

class GenerationEngine:
    """Orchestrates: build prompt → call LLM → extract citations."""

    def __init__(self) -> None:
        self._adapter: LLMAdapter = FallbackAdapter()

    def set_adapter(self, adapter: LLMAdapter) -> None:
        self._adapter = adapter

    def get_adapter_name(self) -> str:
        return self._adapter.name

    async def generate(self, query: str, chunks: list[RetrievalResult]) -> GenerationResult:
        start = time.monotonic()

        prompt = build_prompt(query, chunks)
        try:
            answer, tokens = await self._adapter.generate(prompt)
        except Exception as e:
            logger.error("generation.failed", error=str(e))
            answer = f"Generation failed: {e}"
            tokens = 0

        citations = extract_citations(answer, chunks)

        return GenerationResult(
            answer=answer,
            citations=citations,
            latency_ms=(time.monotonic() - start) * 1000,
            model=self._adapter.name,
            tokens=tokens,
        )


_engine = GenerationEngine()


def get_generation_engine() -> GenerationEngine:
    return _engine
