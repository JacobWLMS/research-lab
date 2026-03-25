"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from research_lab.config import Settings, ensure_lab_dir, remove_lockfile, write_lockfile
from research_lab.engine.session import SessionManager
from research_lab.pipeline.store import ExperimentStore
from research_lab.server.ws import ConnectionManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage server startup / shutdown resources."""
    settings: Settings = app.state.settings
    ensure_lab_dir(settings.project_dir)
    write_lockfile(settings)

    # Initialize shared resources
    app.state.sessions = SessionManager()
    app.state.store = ExperimentStore(settings.experiments_dir)
    app.state.ws_manager = ConnectionManager()

    logger.info(
        "research-lab server started on %s:%s (project: %s)",
        settings.host,
        settings.port,
        settings.project_dir,
    )

    yield

    # Shutdown
    await app.state.sessions.shutdown_all()
    remove_lockfile(settings)
    logger.info("research-lab server stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return a configured FastAPI application."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="research-lab",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from research_lab.server.routers.system import router as system_router
    from research_lab.server.routers.experiments import router as experiments_router
    from research_lab.server.routers.steps import router as steps_router
    from research_lab.server.routers.compute import router as compute_router
    from research_lab.server.ws import router as ws_router

    app.include_router(system_router)
    app.include_router(experiments_router)
    app.include_router(steps_router)
    app.include_router(compute_router)
    app.include_router(ws_router)

    # Mount frontend static files — check multiple locations
    import os
    frontend_candidates = [
        os.environ.get("RESEARCHLAB_STATIC_DIR", ""),
        str(Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"),
        str(Path(settings.project_dir) / "research-lab-frontend"),
        "/root/research-lab-frontend",
    ]
    for candidate in frontend_candidates:
        if candidate and Path(candidate).is_dir() and (Path(candidate) / "index.html").exists():
            app.mount("/", StaticFiles(directory=candidate, html=True), name="frontend")
            logger.info("Serving frontend from %s", candidate)
            break

    return app
