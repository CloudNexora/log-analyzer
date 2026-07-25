"""
FastAPI application factory for the Log Analyzer HTTP API.

Start the server:
    log-analyzer-serve
    # or
    uvicorn log_analyzer.api.app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from log_analyzer.api.routes import router

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Log Analyzer API",
    description="""
## 🔍 Log Analyzer — REST API

Analyze log files from **Jenkins**, **Docker**, **Kubernetes**, and generic
sources over HTTP. Detect errors, warnings, and performance issues, then
retrieve structured reports with remediation steps.

### Quick Start

1. **Upload a log file** → `POST /analyze`
2. **View the full report** → `GET /reports/{id}`
3. **Download as HTML** → `GET /reports/{id}/download?format=html`

### Interactive Docs
- **Swagger UI** → `/docs`
- **ReDoc** → `/redoc`
""",
    version="1.0.0",
    contact={
        "name": "Log Analyzer",
        "url": "https://github.com/log-analyzer",
    },
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "System",
            "description": "Health checks and service status.",
        },
        {
            "name": "Discovery",
            "description": "List available log sources and report formats.",
        },
        {
            "name": "Analysis",
            "description": "Upload and analyze log files.",
        },
        {
            "name": "Reports",
            "description": "Retrieve, download, and manage analysis reports.",
        },
    ],
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root to Swagger UI."""
    return RedirectResponse(url="/docs")


# ---------------------------------------------------------------------------
# CLI entry point  (used by `log-analyzer-serve` script)
# ---------------------------------------------------------------------------

def serve():
    """Start the Uvicorn server — called by the `log-analyzer-serve` CLI script."""
    import uvicorn
    uvicorn.run(
        "log_analyzer.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    serve()
