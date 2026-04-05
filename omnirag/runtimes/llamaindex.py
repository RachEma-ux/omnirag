"""LlamaIndex runtime — wraps LlamaIndex components."""

from __future__ import annotations

import logging
from typing import Any

from omnirag.core.exceptions import RuntimeNotAvailableError
from omnirag.core.models import GenerationResult
from omnirag.runtimes.base import BaseRuntime

logger = logging.getLogger(__name__)


class LlamaIndexRuntime(BaseRuntime):
    """Runtime adapter for LlamaIndex."""

    def __init__(self) -> None:
        self._components: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "llamaindex"

    def is_available(self) -> bool:
        try:
            import llama_index  # noqa: F401
            return True
        except ImportError:
            return False

    def _require(self) -> None:
        if not self.is_available():
            raise RuntimeNotAvailableError(
                "LlamaIndex is not installed. Install with: pip install omnirag[llamaindex]"
            )

    def load_component(self, component_type: str, config: dict[str, Any]) -> Any:
        """Load a LlamaIndex component by type.

        Supported component_type values:
            - "index": VectorStoreIndex from documents or an existing vector store.
            - "query_engine": Query engine built from an index.
            - "retriever": Retriever built from an index.

        Config keys vary by type — see inline docs for each branch.
        """
        self._require()

        component_type = component_type.lower()

        if component_type == "index":
            return self._load_index(config)
        elif component_type == "query_engine":
            return self._load_query_engine(config)
        elif component_type == "retriever":
            return self._load_retriever(config)
        else:
            raise ValueError(
                f"Unsupported LlamaIndex component type: {component_type!r}. "
                f"Supported types: index, query_engine, retriever"
            )

    def _load_index(self, config: dict[str, Any]) -> Any:
        """Load or create a VectorStoreIndex.

        Config:
            documents: list of LlamaIndex Document objects (optional)
            nodes: list of pre-parsed nodes (optional)
            vector_store: an existing vector store instance (optional)
            service_context: a ServiceContext / Settings override (optional)
        """
        try:
            from llama_index.core import VectorStoreIndex
        except ImportError:
            try:
                from llama_index import VectorStoreIndex
            except ImportError:
                raise RuntimeNotAvailableError(
                    "llama-index-core is not installed. "
                    "Install with: pip install llama-index-core"
                )

        vector_store = config.get("vector_store")
        documents = config.get("documents")
        nodes = config.get("nodes")

        extra = {k: v for k, v in config.items()
                 if k not in ("documents", "nodes", "vector_store", "service_context")}

        if vector_store is not None:
            try:
                from llama_index.core import StorageContext
            except ImportError:
                from llama_index import StorageContext
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                storage_context=storage_context,
                **extra,
            )
        elif nodes is not None:
            index = VectorStoreIndex(nodes=nodes, **extra)
        elif documents is not None:
            index = VectorStoreIndex.from_documents(documents, **extra)
        else:
            # Empty index — user will add documents later
            index = VectorStoreIndex(nodes=[], **extra)

        self._components["index"] = index
        logger.debug("Loaded LlamaIndex VectorStoreIndex")
        return index

    def _load_query_engine(self, config: dict[str, Any]) -> Any:
        """Build a query engine from an index.

        Config:
            index_key: key in self._components (default "index")
            similarity_top_k: int (default 4)
            response_mode: str (default "compact")
            **kwargs: forwarded to as_query_engine()
        """
        index_key = config.get("index_key", "index")
        index = config.get("index") or self._components.get(index_key)

        if index is None:
            raise ValueError(
                f"Index not found at key {index_key!r}. "
                f"Load an index component first."
            )

        similarity_top_k = config.get("similarity_top_k", 4)
        response_mode = config.get("response_mode", "compact")
        extra = {k: v for k, v in config.items()
                 if k not in ("index_key", "index", "similarity_top_k", "response_mode")}

        query_engine = index.as_query_engine(
            similarity_top_k=similarity_top_k,
            response_mode=response_mode,
            **extra,
        )

        self._components["query_engine"] = query_engine
        logger.debug(
            "Loaded LlamaIndex query engine (top_k=%d, mode=%s)",
            similarity_top_k, response_mode,
        )
        return query_engine

    def _load_retriever(self, config: dict[str, Any]) -> Any:
        """Build a retriever from an index.

        Config:
            index_key: key in self._components (default "index")
            similarity_top_k: int (default 4)
            **kwargs: forwarded to as_retriever()
        """
        index_key = config.get("index_key", "index")
        index = config.get("index") or self._components.get(index_key)

        if index is None:
            raise ValueError(
                f"Index not found at key {index_key!r}. "
                f"Load an index component first."
            )

        similarity_top_k = config.get("similarity_top_k", 4)
        extra = {k: v for k, v in config.items()
                 if k not in ("index_key", "index", "similarity_top_k")}

        retriever = index.as_retriever(
            similarity_top_k=similarity_top_k,
            **extra,
        )

        self._components["retriever"] = retriever
        logger.debug("Loaded LlamaIndex retriever (top_k=%d)", similarity_top_k)
        return retriever

    def run_pipeline(
        self, pipeline_steps: list[dict[str, Any]], input_data: Any
    ) -> GenerationResult:
        """Execute pipeline steps and query, returning a GenerationResult.

        Each step dict must have:
            type: str — component type ("index", "query_engine", "retriever")
            config: dict — config passed to load_component

        input_data can be a str (query) or a dict with a "query" key.
        The pipeline builds a query engine from steps and executes the query.
        """
        self._require()

        if isinstance(input_data, str):
            query = input_data
        elif isinstance(input_data, dict):
            query = input_data.get("query", input_data.get("input", str(input_data)))
        else:
            query = str(input_data)

        # Load all components from steps
        for step in pipeline_steps:
            step_type = step.get("type", "")
            step_config = step.get("config", {})
            self.load_component(step_type, step_config)

        # Execute: prefer query_engine, then retriever
        query_engine = self._components.get("query_engine")
        retriever = self._components.get("retriever")

        citations: list[str] = []
        confidence = 0.5

        if query_engine is not None:
            response = query_engine.query(query)
            answer = str(response)

            # Extract source nodes for citations
            source_nodes = getattr(response, "source_nodes", [])
            for node in source_nodes:
                node_id = getattr(node, "node_id", "") or getattr(
                    getattr(node, "node", None), "id_", ""
                )
                if node_id:
                    citations.append(node_id)
                # Use the best score as confidence
                score = getattr(node, "score", None)
                if score is not None and score > confidence:
                    confidence = min(float(score), 1.0)

            return GenerationResult(
                answer=answer,
                confidence=confidence,
                citations=citations,
                metadata={
                    "runtime": self.name,
                    "query": query,
                    "source_nodes_count": len(source_nodes),
                    "steps_count": len(pipeline_steps),
                },
            )

        elif retriever is not None:
            nodes = retriever.retrieve(query)
            # Retriever returns nodes but no generation — concatenate content
            contents: list[str] = []
            for node in nodes:
                text = getattr(node, "text", "") or str(
                    getattr(getattr(node, "node", None), "text", "")
                )
                if text:
                    contents.append(text)
                node_id = getattr(node, "node_id", "") or getattr(
                    getattr(node, "node", None), "id_", ""
                )
                if node_id:
                    citations.append(node_id)
                score = getattr(node, "score", None)
                if score is not None and score > confidence:
                    confidence = min(float(score), 1.0)

            answer = "\n\n".join(contents) if contents else "No relevant content found."

            return GenerationResult(
                answer=answer,
                confidence=confidence,
                citations=citations,
                metadata={
                    "runtime": self.name,
                    "query": query,
                    "retrieval_only": True,
                    "nodes_count": len(nodes),
                    "steps_count": len(pipeline_steps),
                },
            )

        else:
            return GenerationResult(
                answer="",
                confidence=0.0,
                citations=[],
                metadata={
                    "runtime": self.name,
                    "query": query,
                    "error": "No query_engine or retriever was built from pipeline steps.",
                    "steps_count": len(pipeline_steps),
                },
            )

    def normalize_output(self, raw_output: Any) -> GenerationResult:
        """LlamaIndex-specific output normalization."""
        if isinstance(raw_output, GenerationResult):
            return raw_output

        # LlamaIndex Response objects
        answer = str(raw_output)
        citations: list[str] = []
        confidence = 0.5

        source_nodes = getattr(raw_output, "source_nodes", [])
        for node in source_nodes:
            node_id = getattr(node, "node_id", "") or getattr(
                getattr(node, "node", None), "id_", ""
            )
            if node_id:
                citations.append(node_id)
            score = getattr(node, "score", None)
            if score is not None and score > confidence:
                confidence = min(float(score), 1.0)

        return GenerationResult(
            answer=answer,
            confidence=confidence,
            citations=citations,
            metadata={
                "runtime": self.name,
                "raw_type": type(raw_output).__name__,
                "source_nodes_count": len(source_nodes),
            },
        )
