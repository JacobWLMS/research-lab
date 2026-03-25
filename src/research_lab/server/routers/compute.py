"""Compute backend management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from research_lab.compute.local import LocalBackend

router = APIRouter(prefix="/api/compute", tags=["compute"])


class ConnectRequest(BaseModel):
    backend: str = "local"
    config: dict = {}


@router.post("/connect")
async def connect(body: ConnectRequest, request: Request) -> dict:
    """Connect a compute backend and provision a kernel."""
    sessions = request.app.state.sessions

    if body.backend == "local":
        backend = LocalBackend()
        conn = await backend.provision(body.config)
        # Also ensure we have a session kernel ready
        await sessions.get_or_create()
        return {
            "status": "connected",
            "backend": body.backend,
            "connection": {
                "transport": conn.transport,
                "ip": conn.ip,
            },
        }
    else:
        raise HTTPException(400, f"Unknown backend: {body.backend!r}")


@router.get("/status")
async def compute_status(request: Request) -> dict:
    """Check the status of the compute backend."""
    sessions = request.app.state.sessions
    alive = await sessions.is_alive()
    return {
        "connected": alive,
        "kernel_count": sessions.kernel_count,
        "active_experiments": sessions.active_experiments(),
    }


@router.post("/disconnect")
async def disconnect(request: Request) -> dict:
    """Disconnect and shut down all kernels."""
    sessions = request.app.state.sessions
    await sessions.shutdown_all()
    return {"status": "disconnected"}
