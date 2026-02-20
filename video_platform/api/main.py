from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from video_platform.api.middleware import RequestContextMiddleware
from video_platform.api.routes import cases, health, jobs, models, reviews
from video_platform.core.schemas import ErrorResponse
from video_platform.db import db_session, init_db
from video_platform.services.knowledge import ensure_collection
from video_platform.services.model_manager import BUNDLES
from video_platform.services.repository import seed_model_bundles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("video_platform")


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    init_db()
    ensure_collection()
    with db_session() as session:
        seed_model_bundles(session, BUNDLES)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Video Editing Platform", version="0.2.0", lifespan=app_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(reviews.router)
    app.include_router(models.router)
    app.include_router(cases.router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", None)
        payload = ErrorResponse(error=str(exc.detail), request_id=request_id)
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("unhandled_error request_id=%s", request_id)
        payload = ErrorResponse(error="internal_server_error", request_id=request_id)
        return JSONResponse(status_code=500, content=payload.model_dump())

    return app


app = create_app()
