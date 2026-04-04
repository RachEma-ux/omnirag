# OmniRAG v4

**Open-source control plane for RAG systems.**

OmniRAG unifies LangChain, LlamaIndex, and Haystack under a single API, adds a Selective Execution Planner that compiles deterministic RAG sub-graphs into optimized Python functions, and provides explicit execution strategies for combining multiple pipelines.

> OmniRAG is to RAG what Kubernetes is to containers — a control plane, not a replacement.

## Features

- **Canonical Data Model** — Pydantic v2 models for cross-framework interop
- **YAML Pipelines** — Declarative DAG pipelines with validation and cycle detection
- **4 Execution Strategies** — Single, Fallback, Ensemble, Vote
- **Selective Execution Planner** — Compiles deterministic sub-graphs for faster execution
- **8 Built-in Adapters** — Ingestion, chunking, embedding, vector DB, reranking, generation
- **FastAPI + WebSocket** — REST, async tasks, real-time streaming
- **Observability** — Prometheus metrics, OpenTelemetry tracing, structured logging
- **Security** — API key auth, rate limiting
- **Kubernetes** — Helm chart, Pipeline CRD

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Validate a pipeline
omnirag validate examples/simple_rag.yaml

# Start API server
omnirag serve --port 8100

# Run a pipeline directly
omnirag run examples/local_ollama_pipeline.yaml --query "What is RAG?"
```

## Architecture

```
                    ┌─────────────────────────────────┐
                    │      OmniRAG Control Plane       │
                    │  REST + WebSocket + CLI           │
                    │  YAML Pipelines + Strategies      │
                    │  Selective Execution Planner       │
                    └────────────────┬────────────────┘
           ┌─────────────────────────┼────────────────────────┐
     LangChain Runtime       LlamaIndex Runtime       Haystack Runtime
           └─────────────────────────┼────────────────────────┘
                    ┌────────────────┴────────────────┐
                    │       Adapter Registry           │
                    │  ingestion · chunking · embedding│
                    │  vector DB · reranking · generation│
                    └────────────────┬────────────────┘
                    ┌────────────────┴────────────────┐
                    │     Execution Strategies          │
                    │  single│fallback│ensemble│vote    │
                    └─────────────────────────────────┘
```

## Built-in Adapters

| Adapter | Category | Maturity | Dependencies |
|---------|----------|----------|-------------|
| `file_loader` | Ingestion | Core | None |
| `recursive_splitter` | Chunking | Core | None |
| `memory` | Retrieval | Core | None |
| `huggingface` | Embedding | Core | `sentence-transformers` |
| `qdrant` | Retrieval | Core | `qdrant-client` |
| `cross_encoder` | Reranking | Core | `sentence-transformers` |
| `openai_gen` | Generation | Core | `openai` |
| `ollama_gen` | Generation | Core | None (uses REST) |

Install optional deps:
```bash
pip install omnirag[huggingface]  # HF embedding + reranker
pip install omnirag[qdrant]       # Qdrant vector DB
pip install omnirag[all]          # Everything
```

## Execution Strategies

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| **Single** | Run first pipeline | Default, lowest latency |
| **Fallback** | Try A, if low confidence try B, C... | High availability |
| **Ensemble** | Run all in parallel, merge results | Maximum quality |
| **Vote** | Majority vote weighted by confidence | Disagreement resolution |

## Pipeline YAML

```yaml
version: "4.0"
name: my_pipeline
execution:
  strategy: ensemble
  ensemble_merge: rerank
stages:
  - id: load
    adapter: file_loader
    params: { path: ./data }
  - id: chunk
    adapter: recursive_splitter
    input: load
  - id: embed
    adapter: huggingface
    input: chunk
  - id: retrieve
    adapter: qdrant
    input: query
  - id: generate
    adapter: ollama_gen
    input: retrieve
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| POST | `/pipelines/` | Upload pipeline YAML |
| GET | `/pipelines/{name}` | Get pipeline info |
| GET | `/pipelines/{name}/plan` | View compiled execution plan |
| POST | `/pipelines/{name}/invoke` | Execute synchronously |
| POST | `/pipelines/{name}/invoke_async` | Execute async (returns task ID) |
| GET | `/tasks/{id}` | Poll task result |
| WS | `/ws/chat` | Real-time streaming |

## Selective Execution Planner

The compiler detects deterministic pipeline sub-graphs (no LLM calls, no randomness) and fuses them into optimized execution paths:

```
YAML Pipeline → DAG → Analyze → Compile deterministic sub-graphs → Execute

  [load] → [chunk] → [embed] → [store] → [retrieve] → [generate]
  ├── COMPILED (fused) ──────────────────┤   └── INTERPRETED
```

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OMNIRAG_HOST` | `127.0.0.1` | Server bind host |
| `OMNIRAG_PORT` | `8100` | Server bind port |
| `OMNIRAG_WORKERS` | `1` | Uvicorn workers |
| `OMNIRAG_API_KEYS` | *(empty)* | Comma-separated API keys |
| `OMNIRAG_RATE_LIMIT` | `100` | Requests per minute |
| `OMNIRAG_COMPILER` | `true` | Enable/disable compiler |
| `OMNIRAG_LOG_LEVEL` | `INFO` | Log level |

## Docker

```bash
# Development
docker-compose up

# Production
docker build -t omnirag .
docker run -p 8100:8100 omnirag
```

## Kubernetes

```bash
helm install omnirag ./charts/omnirag --set replicaCount=3
```

Includes a Pipeline CRD for declarative pipeline management:
```yaml
apiVersion: omnirag.io/v1
kind: Pipeline
metadata:
  name: prod-qa
spec:
  yaml: |
    version: "4.0"
    stages: ...
  replicas: 3
```

## Benchmarks

```bash
python -m benchmarks.runner
```

Compares interpreted vs compiled execution across queries. Reports geometric mean speedup.

## Project Structure

```
omnirag/
├── core/              # Data model, maturity levels, exceptions
├── adapters/          # 8 built-in adapters + registry
│   ├── ingestion/     #   FileLoader
│   ├── chunking/      #   RecursiveChunker
│   ├── embedding/     #   HuggingFace
│   ├── vectordb/      #   Qdrant
│   ├── reranking/     #   CrossEncoder
│   ├── generation/    #   OpenAI, Ollama
│   └── memory/        #   In-memory vector store
├── runtimes/          # LangChain, LlamaIndex, Haystack wrappers
├── pipelines/         # YAML schema, loader, DAG, executor
├── strategies/        # Single, Fallback, Ensemble, Vote
├── compiler/          # Selective Execution Planner
├── api/               # FastAPI + WebSocket + async tasks
├── observability/     # Metrics, tracing
├── cli/               # CLI commands
└── config.py          # Environment-based configuration
```

## License

Apache 2.0
