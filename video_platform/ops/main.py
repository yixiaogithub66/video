from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    app = FastAPI(title="Video Platform Ops Web", version="0.1.0")

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/config.js")
    def config_js():
        api_base = os.getenv("OPS_API_BASE_URL", "http://localhost:8000")
        token = os.getenv("LOCAL_API_TOKEN", "dev-token")
        js = f"window.__OPS_CONFIG__ = {{ apiBase: '{api_base}', apiToken: '{token}' }};"
        return HTMLResponse(content=js, media_type="application/javascript")

    return app


app = create_app()
