"""OmniRAG CLI — validate, run, and serve pipelines."""

from __future__ import annotations

from pathlib import Path

import click

from omnirag import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """OmniRAG v4 — Open-source control plane for RAG systems."""


@cli.command()
@click.argument("pipeline_path", type=click.Path(exists=True))
def validate(pipeline_path: str) -> None:
    """Validate a pipeline YAML file."""
    from omnirag.pipelines.loader import load_pipeline

    try:
        config = load_pipeline(Path(pipeline_path))
        click.echo(f"Pipeline '{config.name}' is valid.")
        click.echo(f"  Stages: {len(config.stages)}")
        click.echo(f"  Strategy: {config.execution.strategy}")
        for stage in config.stages:
            adapter_info = f" (adapter: {stage.adapter})" if stage.adapter else ""
            runtime_info = f" (runtime: {stage.runtime})" if stage.runtime != "shared" else ""
            click.echo(f"  - {stage.id}{adapter_info}{runtime_info}")
    except Exception as e:
        click.echo(f"Validation failed: {e}", err=True)
        raise SystemExit(1) from e


@cli.command()
@click.argument("pipeline_path", type=click.Path(exists=True))
@click.option("--query", "-q", required=True, help="Query to run against the pipeline")
def run(pipeline_path: str, query: str) -> None:
    """Execute a pipeline with a query."""
    from omnirag.pipelines.executor import InterpretedExecutor
    from omnirag.pipelines.loader import load_pipeline

    try:
        config = load_pipeline(Path(pipeline_path))
        executor = InterpretedExecutor()
        result = executor.execute(config, query)
        click.echo(f"Answer: {result.answer}")
        click.echo(f"Confidence: {result.confidence:.2f}")
        if result.citations:
            click.echo(f"Citations: {', '.join(result.citations)}")
    except Exception as e:
        click.echo(f"Execution failed: {e}", err=True)
        raise SystemExit(1) from e


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8100, type=int, help="Bind port")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the OmniRAG API server."""
    import uvicorn

    click.echo(f"Starting OmniRAG server on {host}:{port}...")
    uvicorn.run(
        "omnirag.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
