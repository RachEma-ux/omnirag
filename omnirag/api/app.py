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
from omnirag.api.routes.intake import router as intake_router
from omnirag.api.routes.search import router as search_router
from omnirag.api.routes.stream import router as stream_router
from omnirag.api.routes.webhooks import router as webhooks_router
from omnirag.api.routes.export import router as export_router
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

    # Security middleware (auth + rate limiting)
    from omnirag.api.middleware.security import SecurityMiddleware
    app.add_middleware(SecurityMiddleware)

    # Routes
    app.include_router(health_router, tags=["health"])
    app.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
    app.include_router(invoke_router, tags=["invoke"])
    app.include_router(tasks_router, tags=["tasks"])
    app.include_router(ws_router, tags=["websocket"])
    app.include_router(intake_router, tags=["intake"])
    app.include_router(search_router, tags=["search"])
    app.include_router(stream_router, tags=["stream"])
    app.include_router(webhooks_router, tags=["webhooks"])
    app.include_router(export_router, tags=["export"])

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
  .swagger-ui select {{
    background: #1e1e1e; color: #e8e8e8; border: 1px solid #2a2a2a;
    -webkit-appearance: none; appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888888' stroke-width='2.5'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 10px center; background-size: 12px;
    padding-right: 28px;
  }}
  .swagger-ui .opblock-summary-control svg {{ fill: #888; }}
  .swagger-ui .expand-methods svg, .swagger-ui .expand-operation svg {{ fill: #888; }}
  .swagger-ui .model-toggle svg {{ fill: #888; }}
  .swagger-ui .arrow {{ fill: #888 !important; }}
  .swagger-ui svg.arrow {{ fill: #888 !important; }}
  .swagger-ui .opblock-tag svg {{ fill: #888; }}
  .swagger-ui section.models .model-container svg {{ fill: #888; }}
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
        return """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OmniRAG — ReDoc</title>
<style>
  html, body { margin: 0; padding: 0; background: #0d0d0d; }
  /* Force dark on every ReDoc surface */
  .redoc-wrap { background: #0d0d0d !important; color: #e8e8e8 !important; }
  /* Left nav sidebar */
  .menu-content { background: #0d0d0d !important; }
  [role="navigation"] { background: #0d0d0d !important; }
  .menu-content label, .menu-content a, .menu-content span { color: #888 !important; }
  .menu-content label.-active, .menu-content a.-active { color: #e8e8e8 !important; }
  .menu-content ul { background: #0d0d0d !important; }
  .menu-content li { border-color: #2a2a2a !important; }
  /* Middle panel */
  .api-content { background: #0d0d0d !important; }
  .api-content h1, .api-content h2, .api-content h3, .api-content h4, .api-content h5 { color: #e8e8e8 !important; }
  .api-content p, .api-content li, .api-content td, .api-content span { color: #888 !important; }
  .api-content a { color: #6366f1 !important; }
  .api-content table { border-color: #2a2a2a !important; }
  .api-content th { color: #888 !important; background: #151515 !important; border-color: #2a2a2a !important; }
  .api-content td { border-color: #1c1c1c !important; }
  .api-content tr { background: #0d0d0d !important; }
  .api-content code { background: #1e1e1e !important; color: #6366f1 !important; }
  .api-content pre { background: #0a0c0f !important; color: #a1a7b4 !important; border-color: #2a2a2a !important; }
  /* Right panel (code samples) */
  [data-role="right-panel"], .react-tabs__tab-panel { background: #0a0c0f !important; }
  .react-tabs__tab { background: #151515 !important; color: #888 !important; border-color: #2a2a2a !important; }
  .react-tabs__tab--selected { color: #e8e8e8 !important; border-bottom-color: #6366f1 !important; }
  /* HTTP method badges */
  .http-verb { border-radius: 4px !important; font-weight: 600 !important; }
  .http-verb.get { background: #6366f1 !important; }
  .http-verb.post { background: #4caf50 !important; }
  .http-verb.put { background: #f59e0b !important; }
  .http-verb.delete { background: #ef4444 !important; }
  /* Schema */
  .model-title { color: #e8e8e8 !important; }
  .property .property-name { color: #e8e8e8 !important; }
  .property .property-type { color: #6366f1 !important; }
  .property .property-format { color: #555 !important; }
  .property .property-required { color: #ef4444 !important; }
  [kind="field"] { border-color: #2a2a2a !important; }
  /* Nested model containers */
  .model-title-container, .model { background: #151515 !important; }
  /* Response panels */
  .responses-list .response-title { color: #e8e8e8 !important; }
  /* Buttons */
  button { background: #1c1c1c !important; color: #e8e8e8 !important; border-color: #2a2a2a !important; }
  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.06); border-radius: 3px; }
  /* Search */
  .search-input { background: #1e1e1e !important; color: #e8e8e8 !important; border-color: #2a2a2a !important; }
  /* Bottom bar / footer */
  .powered-by { background: #0d0d0d !important; }
  .powered-by a { color: #555 !important; }
</style>
</head><body>
<div id="redoc-container"></div>
<script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
<script>
Redoc.init("/openapi.json", {
  theme: {
    colors: {
      primary: { main: "#6366f1" },
      success: { main: "#4caf50" },
      warning: { main: "#f59e0b" },
      error: { main: "#ef4444" },
      text: { primary: "#e8e8e8", secondary: "#888" },
      border: { dark: "#2a2a2a", light: "#1c1c1c" },
      http: {
        get: "#6366f1", post: "#4caf50", put: "#f59e0b",
        delete: "#ef4444", patch: "#818cf8", options: "#555"
      }
    },
    typography: {
      fontSize: "14px",
      fontFamily: "-apple-system, Inter, sans-serif",
      headings: { fontFamily: "-apple-system, Inter, sans-serif" },
      code: {
        fontSize: "12px",
        fontFamily: "JetBrains Mono, Fira Code, monospace",
        backgroundColor: "#0a0c0f",
        color: "#a1a7b4"
      },
      links: { color: "#6366f1" }
    },
    sidebar: {
      backgroundColor: "#0d0d0d",
      textColor: "#888",
      activeTextColor: "#e8e8e8",
      groupItems: { textTransform: "uppercase" },
      arrow: { color: "#555" }
    },
    rightPanel: { backgroundColor: "#0a0c0f" },
    schema: {
      nestedBackground: "#151515",
      typeNameColor: "#6366f1",
      typeTitleColor: "#e8e8e8"
    }
  },
  hideDownloadButton: true,
  nativeScrollbars: true
}, document.getElementById("redoc-container"));
</script>
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

        # Connect to PostgreSQL (falls back to in-memory)
        from omnirag.intake.storage.repository import get_repository
        await get_repository().connect()

        from omnirag.intake.defaults import register_defaults as register_intake
        register_intake()

        # Output layer: register index writers
        from omnirag.output.index_writers.base import get_writer_registry
        from omnirag.output.index_writers.vector import VectorIndexWriter
        from omnirag.output.index_writers.keyword import KeywordIndexWriter
        from omnirag.output.index_writers.metadata import MetadataIndexWriter
        registry = get_writer_registry()
        registry.register(VectorIndexWriter())
        registry.register(KeywordIndexWriter())
        registry.register(MetadataIndexWriter())

    return app
