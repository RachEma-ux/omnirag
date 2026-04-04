"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from omnirag import __version__
from omnirag.api.routes.health import router as health_router
from omnirag.api.routes.invoke import router as invoke_router
from omnirag.api.routes.pipelines import router as pipelines_router
from omnirag.api.routes.tasks import router as tasks_router
from omnirag.api.routes.websocket import router as ws_router
from omnirag.observability.metrics import metrics

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OmniRAG",
        description="Open-source control plane for RAG systems",
        version=__version__,
        docs_url=None,    # disabled — custom dark Swagger below
        redoc_url=None,   # disabled — custom dark ReDoc below
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health_router, tags=["health"])
    app.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
    app.include_router(invoke_router, tags=["invoke"])
    app.include_router(tasks_router, tags=["tasks"])
    app.include_router(ws_router, tags=["websocket"])

    # Prometheus metrics endpoint
    @app.get("/metrics", response_class=PlainTextResponse, tags=["observability"])
    async def prometheus_metrics() -> str:
        return metrics.export_prometheus()

    # Custom dark Swagger UI
    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    async def custom_swagger_ui():
        return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OmniRAG — API Docs</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
<style>
  html {{ background: #0d0d0d; }}
  body {{ margin: 0; background: #0d0d0d; }}
  /* Dark theme overrides matching OmniRAG shell */
  .swagger-ui {{ background: #0d0d0d; color: #e8e8e8; }}
  .swagger-ui .topbar {{ display: none; }}
  .swagger-ui .info {{ margin: 20px 0; }}
  .swagger-ui .info .title {{ color: #e8e8e8; }}
  .swagger-ui .info .description {{ color: #888; }}
  .swagger-ui .info a {{ color: #6366f1; }}
  .swagger-ui .scheme-container {{ background: #151515; box-shadow: none; border-bottom: 1px solid #2a2a2a; padding: 12px 20px; }}
  .swagger-ui .opblock-tag {{ color: #e8e8e8; border-bottom: 1px solid #2a2a2a; }}
  .swagger-ui .opblock-tag:hover {{ background: #1c1c1c; }}
  .swagger-ui .opblock {{ background: #151515; border-color: #2a2a2a; box-shadow: none; }}
  .swagger-ui .opblock .opblock-summary {{ border-color: #2a2a2a; }}
  .swagger-ui .opblock .opblock-summary-method {{ border-radius: 4px; }}
  .swagger-ui .opblock.opblock-get {{ background: rgba(99,102,241,0.04); border-color: #6366f140; }}
  .swagger-ui .opblock.opblock-get .opblock-summary-method {{ background: #6366f1; }}
  .swagger-ui .opblock.opblock-get .opblock-summary {{ border-color: #6366f130; }}
  .swagger-ui .opblock.opblock-post {{ background: rgba(76,175,80,0.04); border-color: #4caf5040; }}
  .swagger-ui .opblock.opblock-post .opblock-summary-method {{ background: #4caf50; }}
  .swagger-ui .opblock.opblock-post .opblock-summary {{ border-color: #4caf5030; }}
  .swagger-ui .opblock.opblock-put {{ background: rgba(245,158,11,0.04); border-color: #f59e0b40; }}
  .swagger-ui .opblock.opblock-put .opblock-summary-method {{ background: #f59e0b; }}
  .swagger-ui .opblock.opblock-delete {{ background: rgba(239,68,68,0.04); border-color: #ef444440; }}
  .swagger-ui .opblock.opblock-delete .opblock-summary-method {{ background: #ef4444; }}
  .swagger-ui .opblock-body {{ background: #0d0d0d; }}
  .swagger-ui .opblock-description-wrapper, .swagger-ui .opblock-external-docs-wrapper {{ color: #888; }}
  .swagger-ui .opblock-summary-path {{ color: #e8e8e8; }}
  .swagger-ui .opblock-summary-description {{ color: #888; }}
  .swagger-ui table thead tr th, .swagger-ui table thead tr td {{ color: #888; border-bottom: 1px solid #2a2a2a; }}
  .swagger-ui table tbody tr td {{ color: #e8e8e8; border-bottom: 1px solid #1c1c1c; }}
  .swagger-ui .parameters-col_description input, .swagger-ui .parameters-col_description textarea {{
    background: #1e1e1e; border: 1px solid #2a2a2a; color: #e8e8e8; border-radius: 4px;
  }}
  .swagger-ui .parameter__name {{ color: #e8e8e8; }}
  .swagger-ui .parameter__type {{ color: #6366f1; }}
  .swagger-ui .parameter__in {{ color: #555; }}
  .swagger-ui .response-col_status {{ color: #e8e8e8; }}
  .swagger-ui .response-col_description {{ color: #888; }}
  .swagger-ui .model-box {{ background: #151515; }}
  .swagger-ui .model {{ color: #e8e8e8; }}
  .swagger-ui .model-title {{ color: #e8e8e8; }}
  .swagger-ui section.models {{ border: 1px solid #2a2a2a; }}
  .swagger-ui section.models h4 {{ color: #e8e8e8; border-bottom: 1px solid #2a2a2a; }}
  .swagger-ui .model-toggle::after {{ background: none; }}
  .swagger-ui .prop-type {{ color: #6366f1; }}
  .swagger-ui .prop-format {{ color: #555; }}
  .swagger-ui textarea {{ background: #1e1e1e; color: #e8e8e8; border: 1px solid #2a2a2a; }}
  .swagger-ui select {{ background: #1e1e1e; color: #e8e8e8; border: 1px solid #2a2a2a; }}
  .swagger-ui input[type=text], .swagger-ui input[type=password], .swagger-ui input[type=search], .swagger-ui input[type=email] {{
    background: #1e1e1e; color: #e8e8e8; border: 1px solid #2a2a2a;
  }}
  .swagger-ui .btn {{ background: #1c1c1c; color: #e8e8e8; border: 1px solid #2a2a2a; box-shadow: none; }}
  .swagger-ui .btn:hover {{ background: #252525; }}
  .swagger-ui .btn.execute {{ background: #6366f1; color: #fff; border-color: #6366f1; }}
  .swagger-ui .btn.execute:hover {{ background: #818cf8; }}
  .swagger-ui .btn.cancel {{ background: #ef4444; border-color: #ef4444; }}
  .swagger-ui .responses-inner {{ background: #0d0d0d; }}
  .swagger-ui .response {{ border-color: #2a2a2a; }}
  .swagger-ui .highlight-code {{ background: #0a0c0f; }}
  .swagger-ui .highlight-code pre {{ background: #0a0c0f; color: #a1a7b4; }}
  .swagger-ui .microlight {{ background: #0a0c0f !important; color: #a1a7b4 !important; }}
  .swagger-ui .copy-to-clipboard {{ background: #1c1c1c; }}
  .swagger-ui .loading-container {{ background: #0d0d0d; }}
  .swagger-ui .loading-container .loading::after {{ color: #888; }}
  .swagger-ui .wrapper {{ padding: 0 20px; }}
  .swagger-ui .markdown p, .swagger-ui .markdown li {{ color: #888; }}
  .swagger-ui .markdown code {{ background: #1e1e1e; color: #6366f1; padding: 1px 4px; border-radius: 3px; }}
  .swagger-ui .model-container {{ background: #151515; }}
  .swagger-ui .servers-title, .swagger-ui .servers>label {{ color: #888; }}
  .swagger-ui .servers>label>select {{ background: #1e1e1e; color: #e8e8e8; border: 1px solid #2a2a2a; }}
  .swagger-ui .auth-container {{ background: #151515; border-color: #2a2a2a; }}
  .swagger-ui .dialog-ux .modal-ux {{ background: #151515; border: 1px solid #2a2a2a; }}
  .swagger-ui .dialog-ux .modal-ux-header {{ border-bottom: 1px solid #2a2a2a; }}
  .swagger-ui .dialog-ux .modal-ux-header h3 {{ color: #e8e8e8; }}
  .swagger-ui .renderedMarkdown p {{ color: #888; }}
  ::-webkit-scrollbar {{ width: 6px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.06); border-radius: 3px; }}
</style>
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({{
  url: "/openapi.json",
  dom_id: "#swagger-ui",
  presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
  layout: "BaseLayout",
  deepLinking: true,
  defaultModelsExpandDepth: 0,
  syntaxHighlight: {{ theme: "monokai" }},
}})
</script>
</body></html>"""

    # Custom dark ReDoc
    @app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
    async def custom_redoc():
        return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OmniRAG — ReDoc</title>
<style>
  body {{ margin: 0; padding: 0; }}
  ::-webkit-scrollbar {{ width: 6px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.06); border-radius: 3px; }}
</style>
</head><body>
<redoc spec-url="/openapi.json"
  theme='{{"colors":{{"primary":{{"main":"#6366f1"}},"success":{{"main":"#4caf50"}},"warning":{{"main":"#f59e0b"}},"error":{{"main":"#ef4444"}},"text":{{"primary":"#e8e8e8","secondary":"#888"}},"http":{{"get":"#6366f1","post":"#4caf50","put":"#f59e0b","delete":"#ef4444","patch":"#818cf8"}},"responses":{{"success":{{"backgroundColor":"#151515","color":"#e8e8e8"}},"error":{{"backgroundColor":"#1c1c1c","color":"#ef4444"}}}}}},"typography":{{"fontSize":"14px","fontFamily":"-apple-system, Inter, sans-serif","code":{{"fontSize":"12px","fontFamily":"JetBrains Mono, Fira Code, monospace","backgroundColor":"#0a0c0f","color":"#a1a7b4"}},"headings":{{"fontFamily":"-apple-system, Inter, sans-serif"}}}},"sidebar":{{"backgroundColor":"#0d0d0d","textColor":"#888","activeTextColor":"#e8e8e8","groupItems":{{"textTransform":"uppercase"}},"arrow":{{"color":"#555"}}}},"rightPanel":{{"backgroundColor":"#0a0c0f"}},"schema":{{"nestedBackground":"#151515","typeNameColor":"#6366f1","typeTitleColor":"#e8e8e8"}}}}'
></redoc>
<script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body></html>"""

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Shell UI at root
    @app.get("/", response_class=FileResponse, include_in_schema=False)
    async def shell_ui():
        return FileResponse(str(STATIC_DIR / "index.html"))

    # Register default adapters on startup
    @app.on_event("startup")
    async def startup() -> None:
        from omnirag.adapters.defaults import register_defaults
        register_defaults()

    return app
