"""Generation (LLM) adapters."""

from omnirag.adapters.generation.ollama_gen import OllamaGenerationAdapter
from omnirag.adapters.generation.openai_gen import OpenAIGenerationAdapter

__all__ = ["OpenAIGenerationAdapter", "OllamaGenerationAdapter"]
