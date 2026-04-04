# OmniRAG v4

**Open-source control plane for RAG systems.**

OmniRAG unifies LangChain, LlamaIndex, and Haystack under a single API, adds a Selective Execution Planner that compiles deterministic RAG sub-graphs into pure Python functions (2-5x speedup), and provides explicit execution strategies (single, fallback, ensemble, vote) for combining multiple pipelines.

> OmniRAG is to RAG what Kubernetes is to containers — a control plane, not a replacement.

## Status

**Alpha** — Phase 0 (Foundation) and Phase 1 (Control Plane) implemented.

## Quick Start

```bash
pip install -e ".[dev]"

# Validate a pipeline
omnirag validate examples/simple_rag.yaml

# Start API server
omnirag serve --port 8100
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│              OmniRAG Control Plane               │
│  Unified API · YAML Pipelines · Strategies       │
│  Selective Execution Planner · Governance        │
└─────────────────────────────────────────────────┘
        │               │               │
   LangChain       LlamaIndex       Haystack
    Runtime          Runtime          Runtime
        │               │               │
        └───────────────┼───────────────┘
                        │
              Shared Adapter Registry
         (ingestion, embedding, retrieval,
          reranking, generation)
                        │
              Execution Strategy Layer
         single | fallback | ensemble | vote
```

## Key Features

- **Canonical Data Model** — Pydantic models (OmniChunk, OmniDocument, RetrievalResult, GenerationResult) for cross-framework interop
- **YAML Pipelines** — Declarative DAG pipelines with validation, cycle detection, and topological execution
- **Execution Strategies** — Single, Fallback (confidence/timeout), Ensemble (parallel + merge), Vote (majority weighted)
- **Adapter Registry** — Pluggable adapters with maturity levels (Core, Extended, Experimental)
- **Runtime Isolation** — Each framework runs in its own context; data passes as canonical models
- **FastAPI REST API** — Upload pipelines, invoke sync/async, health checks
- **CLI** — `omnirag validate`, `omnirag run`, `omnirag serve`

## Project Structure

```
omnirag/
├── core/           # Canonical data model, maturity levels, exceptions
├── adapters/       # Base adapter, registry, built-in adapters
├── runtimes/       # LangChain, LlamaIndex, Haystack wrappers
├── pipelines/      # YAML schema, loader, DAG, interpreted executor
├── strategies/     # Execution strategies (single, fallback, ensemble, vote)
├── compiler/       # Selective Execution Planner (Phase 2)
├── api/            # FastAPI REST endpoints
└── cli/            # Click CLI
```

## License

Apache 2.0
