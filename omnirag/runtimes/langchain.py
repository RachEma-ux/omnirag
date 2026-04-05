"""LangChain runtime — wraps LangChain components."""

from __future__ import annotations

import logging
from typing import Any

from omnirag.core.exceptions import RuntimeNotAvailableError
from omnirag.core.models import GenerationResult
from omnirag.runtimes.base import BaseRuntime

logger = logging.getLogger(__name__)


class LangChainRuntime(BaseRuntime):
    """Runtime adapter for LangChain."""

    def __init__(self) -> None:
        self._components: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "langchain"

    def is_available(self) -> bool:
        try:
            import langchain  # noqa: F401
            return True
        except ImportError:
            return False

    def _require(self) -> None:
        if not self.is_available():
            raise RuntimeNotAvailableError(
                "LangChain is not installed. Install with: pip install omnirag[langchain]"
            )

    def load_component(self, component_type: str, config: dict[str, Any]) -> Any:
        """Load a LangChain component by type.

        Supported component_type values:
            - "llm": ChatOpenAI or ChatOllama depending on config["provider"].
            - "retriever": Wraps a vectorstore into a retriever.
            - "chain": Creates a retrieval QA chain from an llm and retriever.

        Config keys vary by type — see inline docs for each branch.
        """
        self._require()

        component_type = component_type.lower()

        if component_type == "llm":
            return self._load_llm(config)
        elif component_type == "retriever":
            return self._load_retriever(config)
        elif component_type == "chain":
            return self._load_chain(config)
        else:
            raise ValueError(
                f"Unsupported LangChain component type: {component_type!r}. "
                f"Supported types: llm, retriever, chain"
            )

    def _load_llm(self, config: dict[str, Any]) -> Any:
        """Load a chat LLM.

        Config:
            provider: "openai" | "ollama" (default "openai")
            model: model name (default "gpt-3.5-turbo" / "llama2")
            temperature: float (default 0.0)
            **kwargs: forwarded to the LLM constructor.
        """
        provider = config.get("provider", "openai").lower()
        temperature = config.get("temperature", 0.0)

        if provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                raise RuntimeNotAvailableError(
                    "langchain-openai is not installed. "
                    "Install with: pip install langchain-openai"
                )
            model = config.get("model", "gpt-3.5-turbo")
            extra = {k: v for k, v in config.items()
                     if k not in ("provider", "model", "temperature")}
            llm = ChatOpenAI(model=model, temperature=temperature, **extra)

        elif provider == "ollama":
            try:
                from langchain_community.chat_models import ChatOllama
            except ImportError:
                raise RuntimeNotAvailableError(
                    "langchain-community is not installed. "
                    "Install with: pip install langchain-community"
                )
            model = config.get("model", "llama2")
            extra = {k: v for k, v in config.items()
                     if k not in ("provider", "model", "temperature")}
            llm = ChatOllama(model=model, temperature=temperature, **extra)

        else:
            raise ValueError(
                f"Unsupported LLM provider: {provider!r}. "
                f"Supported: openai, ollama"
            )

        self._components["llm"] = llm
        logger.debug("Loaded LangChain LLM: %s/%s", provider, config.get("model"))
        return llm

    def _load_retriever(self, config: dict[str, Any]) -> Any:
        """Load a retriever from an existing vectorstore component.

        Config:
            vectorstore: a LangChain-compatible VectorStore instance, OR
            vectorstore_key: str key in self._components referencing one.
            search_type: "similarity" | "mmr" (default "similarity")
            search_kwargs: dict passed to as_retriever() (default {"k": 4})
        """
        vectorstore = config.get("vectorstore")
        if vectorstore is None:
            vs_key = config.get("vectorstore_key", "vectorstore")
            vectorstore = self._components.get(vs_key)
        if vectorstore is None:
            raise ValueError(
                "No vectorstore provided. Pass a 'vectorstore' object or "
                "load one first and reference it via 'vectorstore_key'."
            )

        search_type = config.get("search_type", "similarity")
        search_kwargs = config.get("search_kwargs", {"k": 4})

        retriever = vectorstore.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs,
        )
        self._components["retriever"] = retriever
        logger.debug("Loaded LangChain retriever (search_type=%s)", search_type)
        return retriever

    def _load_chain(self, config: dict[str, Any]) -> Any:
        """Create a retrieval chain.

        Config:
            llm_key: key in self._components for the LLM (default "llm")
            retriever_key: key in self._components for the retriever (default "retriever")
            chain_type: str (default "stuff")
        """
        try:
            from langchain.chains import create_retrieval_chain
            from langchain.chains.combine_documents import create_stuff_documents_chain
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError:
            raise RuntimeNotAvailableError(
                "Required LangChain chain modules not available. "
                "Install with: pip install langchain langchain-core"
            )

        llm_key = config.get("llm_key", "llm")
        retriever_key = config.get("retriever_key", "retriever")

        llm = self._components.get(llm_key)
        retriever = self._components.get(retriever_key)

        if llm is None:
            raise ValueError(
                f"LLM not found at key {llm_key!r}. "
                f"Load an LLM component first."
            )
        if retriever is None:
            raise ValueError(
                f"Retriever not found at key {retriever_key!r}. "
                f"Load a retriever component first."
            )

        system_prompt = config.get(
            "system_prompt",
            "Answer the question based on the context below.\n\n{context}",
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])

        combine_chain = create_stuff_documents_chain(llm, prompt)
        chain = create_retrieval_chain(retriever, combine_chain)

        self._components["chain"] = chain
        logger.debug("Loaded LangChain retrieval chain")
        return chain

    def run_pipeline(
        self, pipeline_steps: list[dict[str, Any]], input_data: Any
    ) -> GenerationResult:
        """Execute pipeline steps sequentially, returning a GenerationResult.

        Each step dict must have:
            type: str — component type to load ("llm", "retriever", "chain")
            config: dict — config passed to load_component

        The final step's output is used as the answer. If a "chain" step is
        present, it is invoked with the input_data as the query.

        input_data can be a str (query) or a dict with an "input" key.
        """
        self._require()

        if isinstance(input_data, str):
            query = input_data
            invoke_input = {"input": input_data}
        elif isinstance(input_data, dict):
            query = input_data.get("input", input_data.get("query", str(input_data)))
            invoke_input = input_data
        else:
            query = str(input_data)
            invoke_input = {"input": query}

        # Load all components from steps
        last_component = None
        for step in pipeline_steps:
            step_type = step.get("type", "")
            step_config = step.get("config", {})
            last_component = self.load_component(step_type, step_config)

        # Execute: prefer chain, then fall back to direct LLM invoke
        chain = self._components.get("chain")
        llm = self._components.get("llm")

        raw_output: Any
        citations: list[str] = []
        confidence = 0.5

        if chain is not None:
            result = chain.invoke(invoke_input)
            if isinstance(result, dict):
                raw_output = result.get("answer", result.get("result", str(result)))
                # Extract source document IDs for citations
                source_docs = result.get("context", result.get("source_documents", []))
                for doc in source_docs:
                    doc_id = getattr(doc, "metadata", {}).get("id", "")
                    if doc_id:
                        citations.append(doc_id)
                confidence = 0.7
            else:
                raw_output = result
        elif llm is not None:
            response = llm.invoke(query)
            raw_output = getattr(response, "content", str(response))
            confidence = 0.5
        elif last_component is not None:
            # Try invoking whatever the last loaded component was
            if callable(getattr(last_component, "invoke", None)):
                raw_output = last_component.invoke(invoke_input)
            else:
                raw_output = str(last_component)
        else:
            raw_output = ""

        if isinstance(raw_output, GenerationResult):
            return raw_output

        return GenerationResult(
            answer=str(raw_output),
            confidence=confidence,
            citations=citations,
            metadata={
                "runtime": self.name,
                "query": query,
                "steps_count": len(pipeline_steps),
            },
        )

    def normalize_output(self, raw_output: Any) -> GenerationResult:
        """LangChain-specific output normalization."""
        if isinstance(raw_output, GenerationResult):
            return raw_output

        if isinstance(raw_output, dict):
            answer = raw_output.get("answer", raw_output.get("result", str(raw_output)))
            citations: list[str] = []
            for doc in raw_output.get("source_documents", []):
                doc_id = getattr(doc, "metadata", {}).get("id", "")
                if doc_id:
                    citations.append(doc_id)
            return GenerationResult(
                answer=str(answer),
                confidence=0.7,
                citations=citations,
                metadata={"runtime": self.name, "raw_type": "dict"},
            )

        # AIMessage or similar
        content = getattr(raw_output, "content", None)
        if content is not None:
            return GenerationResult(
                answer=str(content),
                confidence=0.5,
                metadata={"runtime": self.name, "raw_type": type(raw_output).__name__},
            )

        return super().normalize_output(raw_output)
