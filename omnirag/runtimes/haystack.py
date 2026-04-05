"""Haystack runtime — wraps Haystack components."""

from __future__ import annotations

import logging
from typing import Any

from omnirag.core.exceptions import RuntimeNotAvailableError
from omnirag.core.models import GenerationResult
from omnirag.runtimes.base import BaseRuntime

logger = logging.getLogger(__name__)


class HaystackRuntime(BaseRuntime):
    """Runtime adapter for Haystack."""

    def __init__(self) -> None:
        self._components: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "haystack"

    def is_available(self) -> bool:
        try:
            import haystack  # noqa: F401
            return True
        except ImportError:
            return False

    def _require(self) -> None:
        if not self.is_available():
            raise RuntimeNotAvailableError(
                "Haystack is not installed. Install with: pip install omnirag[haystack]"
            )

    def load_component(self, component_type: str, config: dict[str, Any]) -> Any:
        """Load a Haystack component by type.

        Supported component_type values:
            - "retriever": InMemoryBM25Retriever (or InMemoryEmbeddingRetriever).
            - "generator": HuggingFaceLocalGenerator (or OpenAIGenerator).
            - "pipeline": A Haystack Pipeline assembled from stored components.

        Config keys vary by type — see inline docs for each branch.
        """
        self._require()

        component_type = component_type.lower()

        if component_type == "retriever":
            return self._load_retriever(config)
        elif component_type == "generator":
            return self._load_generator(config)
        elif component_type == "pipeline":
            return self._load_pipeline(config)
        else:
            raise ValueError(
                f"Unsupported Haystack component type: {component_type!r}. "
                f"Supported types: retriever, generator, pipeline"
            )

    def _load_retriever(self, config: dict[str, Any]) -> Any:
        """Load a retriever component.

        Config:
            retriever_type: "bm25" | "embedding" (default "bm25")
            document_store: an existing DocumentStore instance (optional)
            top_k: int (default 5)
        """
        retriever_type = config.get("retriever_type", "bm25").lower()
        document_store = config.get("document_store")
        top_k = config.get("top_k", 5)

        if document_store is None:
            # Create an in-memory document store as default
            document_store = self._get_or_create_document_store(config)

        if retriever_type == "bm25":
            try:
                from haystack.components.retrievers.in_memory import (
                    InMemoryBM25Retriever,
                )
            except ImportError:
                raise RuntimeNotAvailableError(
                    "Haystack InMemoryBM25Retriever not available. "
                    "Install with: pip install haystack-ai"
                )
            retriever = InMemoryBM25Retriever(
                document_store=document_store,
                top_k=top_k,
            )

        elif retriever_type == "embedding":
            try:
                from haystack.components.retrievers.in_memory import (
                    InMemoryEmbeddingRetriever,
                )
            except ImportError:
                raise RuntimeNotAvailableError(
                    "Haystack InMemoryEmbeddingRetriever not available. "
                    "Install with: pip install haystack-ai"
                )
            retriever = InMemoryEmbeddingRetriever(
                document_store=document_store,
                top_k=top_k,
            )

        else:
            raise ValueError(
                f"Unsupported retriever type: {retriever_type!r}. "
                f"Supported: bm25, embedding"
            )

        self._components["retriever"] = retriever
        self._components["document_store"] = document_store
        logger.debug("Loaded Haystack retriever (type=%s, top_k=%d)", retriever_type, top_k)
        return retriever

    def _get_or_create_document_store(self, config: dict[str, Any]) -> Any:
        """Get existing or create new InMemoryDocumentStore."""
        if "document_store" in self._components:
            return self._components["document_store"]

        try:
            from haystack.document_stores.in_memory import InMemoryDocumentStore
        except ImportError:
            raise RuntimeNotAvailableError(
                "Haystack InMemoryDocumentStore not available. "
                "Install with: pip install haystack-ai"
            )

        store = InMemoryDocumentStore()

        # Write initial documents if provided
        documents = config.get("documents")
        if documents:
            store.write_documents(documents)

        self._components["document_store"] = store
        return store

    def _load_generator(self, config: dict[str, Any]) -> Any:
        """Load a generator component.

        Config:
            generator_type: "huggingface_local" | "openai" (default "huggingface_local")
            model: model name/path
            **kwargs: forwarded to the generator constructor.
        """
        generator_type = config.get("generator_type", "huggingface_local").lower()

        if generator_type == "huggingface_local":
            try:
                from haystack.components.generators import HuggingFaceLocalGenerator
            except ImportError:
                raise RuntimeNotAvailableError(
                    "Haystack HuggingFaceLocalGenerator not available. "
                    "Install with: pip install haystack-ai"
                )
            model = config.get("model", "google/flan-t5-small")
            extra = {k: v for k, v in config.items()
                     if k not in ("generator_type", "model")}
            generator = HuggingFaceLocalGenerator(model=model, **extra)

        elif generator_type == "openai":
            try:
                from haystack.components.generators import OpenAIGenerator
            except ImportError:
                raise RuntimeNotAvailableError(
                    "Haystack OpenAIGenerator not available. "
                    "Install with: pip install haystack-ai"
                )
            model = config.get("model", "gpt-3.5-turbo")
            extra = {k: v for k, v in config.items()
                     if k not in ("generator_type", "model")}
            generator = OpenAIGenerator(model=model, **extra)

        else:
            raise ValueError(
                f"Unsupported generator type: {generator_type!r}. "
                f"Supported: huggingface_local, openai"
            )

        self._components["generator"] = generator
        logger.debug("Loaded Haystack generator (type=%s)", generator_type)
        return generator

    def _load_pipeline(self, config: dict[str, Any]) -> Any:
        """Assemble a Haystack Pipeline from stored components.

        Config:
            components: list of dicts, each with:
                name: str — component name in the pipeline
                component_key: str — key in self._components to reference
                component: object — direct component instance (alternative to key)
            connections: list of dicts, each with:
                sender: str — "component_name.output_name"
                receiver: str — "component_name.input_name"
        """
        try:
            from haystack import Pipeline
        except ImportError:
            raise RuntimeNotAvailableError(
                "Haystack Pipeline not available. "
                "Install with: pip install haystack-ai"
            )

        pipeline = Pipeline()

        # Add components
        component_defs = config.get("components", [])
        for comp_def in component_defs:
            comp_name = comp_def["name"]
            component = comp_def.get("component") or self._components.get(
                comp_def.get("component_key", comp_name)
            )
            if component is None:
                raise ValueError(
                    f"Component {comp_name!r} not found. Load it first or "
                    f"pass it directly via 'component' key."
                )
            pipeline.add_component(comp_name, component)

        # Connect components
        connections = config.get("connections", [])
        for conn in connections:
            pipeline.connect(conn["sender"], conn["receiver"])

        self._components["pipeline"] = pipeline
        logger.debug(
            "Assembled Haystack pipeline (%d components, %d connections)",
            len(component_defs), len(connections),
        )
        return pipeline

    def run_pipeline(
        self, pipeline_steps: list[dict[str, Any]], input_data: Any
    ) -> GenerationResult:
        """Execute pipeline steps and run the assembled pipeline.

        Each step dict must have:
            type: str — component type ("retriever", "generator", "pipeline")
            config: dict — config passed to load_component

        input_data can be a str (query) or a dict with pipeline input mappings.

        If a "pipeline" step is present, the assembled Pipeline.run() is called
        with input_data. Otherwise, individual components are invoked directly.
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

        # Execute
        pipeline = self._components.get("pipeline")
        retriever = self._components.get("retriever")
        generator = self._components.get("generator")

        citations: list[str] = []
        confidence = 0.5

        if pipeline is not None:
            # Build input data for the pipeline
            if isinstance(input_data, dict):
                pipeline_input = input_data
            else:
                # Auto-map query to retriever input if retriever exists
                pipeline_input = {}
                if retriever is not None:
                    pipeline_input["retriever"] = {"query": query}
                if generator is not None and retriever is None:
                    pipeline_input["generator"] = {"prompt": query}

            result = pipeline.run(pipeline_input)
            return self._parse_pipeline_result(result, query, pipeline_steps)

        elif retriever is not None and generator is not None:
            # Manual two-step: retrieve then generate
            retriever_output = retriever.run(query=query)
            documents = retriever_output.get("documents", [])

            for doc in documents:
                doc_id = getattr(doc, "id", "") or ""
                if doc_id:
                    citations.append(doc_id)
                score = getattr(doc, "score", None)
                if score is not None and score > confidence:
                    confidence = min(float(score), 1.0)

            # Build prompt from retrieved documents
            context_parts: list[str] = []
            for doc in documents:
                content = getattr(doc, "content", str(doc))
                context_parts.append(content)
            context = "\n\n".join(context_parts)

            prompt = (
                f"Based on the following context, answer the question.\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {query}\n\n"
                f"Answer:"
            )

            generator_output = generator.run(prompt=prompt)
            replies = generator_output.get("replies", [])
            answer = replies[0] if replies else ""

            return GenerationResult(
                answer=str(answer),
                confidence=confidence,
                citations=citations,
                metadata={
                    "runtime": self.name,
                    "query": query,
                    "documents_retrieved": len(documents),
                    "steps_count": len(pipeline_steps),
                },
            )

        elif retriever is not None:
            # Retrieval only
            retriever_output = retriever.run(query=query)
            documents = retriever_output.get("documents", [])

            contents: list[str] = []
            for doc in documents:
                content = getattr(doc, "content", str(doc))
                contents.append(content)
                doc_id = getattr(doc, "id", "") or ""
                if doc_id:
                    citations.append(doc_id)
                score = getattr(doc, "score", None)
                if score is not None and score > confidence:
                    confidence = min(float(score), 1.0)

            answer = "\n\n".join(contents) if contents else "No relevant documents found."

            return GenerationResult(
                answer=answer,
                confidence=confidence,
                citations=citations,
                metadata={
                    "runtime": self.name,
                    "query": query,
                    "retrieval_only": True,
                    "documents_count": len(documents),
                    "steps_count": len(pipeline_steps),
                },
            )

        elif generator is not None:
            # Generation only
            generator_output = generator.run(prompt=query)
            replies = generator_output.get("replies", [])
            answer = replies[0] if replies else ""

            return GenerationResult(
                answer=str(answer),
                confidence=confidence,
                citations=[],
                metadata={
                    "runtime": self.name,
                    "query": query,
                    "generation_only": True,
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
                    "error": "No pipeline, retriever, or generator was built from steps.",
                    "steps_count": len(pipeline_steps),
                },
            )

    def _parse_pipeline_result(
        self, result: dict[str, Any], query: str, steps: list[dict[str, Any]]
    ) -> GenerationResult:
        """Parse the output dict from Haystack Pipeline.run()."""
        citations: list[str] = []
        confidence = 0.5
        answer = ""

        # Haystack Pipeline.run() returns {component_name: {output_name: value}}
        # Look for generator output first, then retriever output
        for component_name, outputs in result.items():
            if not isinstance(outputs, dict):
                continue

            # Generator outputs
            replies = outputs.get("replies")
            if replies:
                answer = str(replies[0]) if replies else ""
                confidence = 0.7

            # Retriever outputs
            documents = outputs.get("documents")
            if documents:
                for doc in documents:
                    doc_id = getattr(doc, "id", "") or ""
                    if doc_id:
                        citations.append(doc_id)
                    score = getattr(doc, "score", None)
                    if score is not None and score > confidence:
                        confidence = min(float(score), 1.0)
                # If no generator answer, concatenate document contents
                if not answer:
                    contents = [
                        getattr(doc, "content", str(doc)) for doc in documents
                    ]
                    answer = "\n\n".join(contents)

        if not answer:
            # Fallback: stringify the entire result
            answer = str(result)

        return GenerationResult(
            answer=answer,
            confidence=confidence,
            citations=citations,
            metadata={
                "runtime": self.name,
                "query": query,
                "pipeline_components": list(result.keys()),
                "steps_count": len(steps),
            },
        )

    def normalize_output(self, raw_output: Any) -> GenerationResult:
        """Haystack-specific output normalization."""
        if isinstance(raw_output, GenerationResult):
            return raw_output

        if isinstance(raw_output, dict):
            return self._parse_pipeline_result(raw_output, query="", steps=[])

        return super().normalize_output(raw_output)
