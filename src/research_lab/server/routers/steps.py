"""Step CRUD, execution, and stop endpoints."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from research_lab.pipeline.runner import PipelineRunner
from research_lab.schemas import Experiment, OutputChunk, Step, StepResult
from research_lab.server.ws import ConnectionManager, broadcast_canvas_update, broadcast_chunk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experiments/{experiment_id}/steps", tags=["steps"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateStepRequest(BaseModel):
    name: str
    code: str = ""
    depends_on: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)


class UpdateStepRequest(BaseModel):
    code: str | None = None
    depends_on: list[str] | None = None
    config: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=Experiment, status_code=201)
async def add_step(
    experiment_id: str, body: CreateStepRequest, request: Request
) -> Experiment:
    store = request.app.state.store
    step = Step(name=body.name, code=body.code, depends_on=body.depends_on, config=body.config)
    exp = store.add_step(experiment_id, step)
    if exp is None:
        raise HTTPException(404, "Experiment not found or duplicate step name")
    return exp


@router.get("/{step_name}")
async def get_step(experiment_id: str, step_name: str, request: Request) -> dict:
    store = request.app.state.store
    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")
    step = next((s for s in exp.steps if s.name == step_name), None)
    if step is None:
        raise HTTPException(404, f"Step {step_name!r} not found")
    result = store.get_result(experiment_id, step_name)
    canvases = store.get_canvases(experiment_id, step_name)
    resp: dict = {
        "step": step.model_dump(),
        "result": result.model_dump() if result else None,
        "canvases": canvases,
    }
    return resp


@router.put("/{step_name}", response_model=Experiment)
async def update_step(
    experiment_id: str, step_name: str, body: UpdateStepRequest, request: Request
) -> Experiment:
    store = request.app.state.store
    updates = body.model_dump(exclude_none=True)
    exp = store.update_step(experiment_id, step_name, updates)
    if exp is None:
        raise HTTPException(404, "Experiment or step not found")
    return exp


@router.delete("/{step_name}", response_model=Experiment)
async def delete_step(
    experiment_id: str, step_name: str, request: Request
) -> Experiment:
    store = request.app.state.store
    exp = store.delete_step(experiment_id, step_name)
    if exp is None:
        raise HTTPException(404, "Experiment or step not found")
    return exp


def _make_on_chunk(mgr: ConnectionManager):
    """Create an on_chunk async callback that broadcasts via WebSocket."""

    async def on_chunk(
        experiment_id: str, step_name: str, chunk: OutputChunk
    ) -> None:
        await broadcast_chunk(mgr, experiment_id, step_name, chunk)

    return on_chunk


def _make_on_canvas(mgr: ConnectionManager):
    """Create an on_canvas async callback that broadcasts canvas updates via WebSocket."""

    async def on_canvas(
        experiment_id: str, step_name: str, canvas_name: str, widgets: list[dict]
    ) -> None:
        await broadcast_canvas_update(mgr, experiment_id, step_name, canvas_name, widgets)

    return on_canvas


async def _run_step_background(
    experiment_id: str,
    step_name: str,
    request: Request,
) -> None:
    """Run a single step in the background, broadcasting lifecycle events via WebSocket."""
    store = request.app.state.store
    sessions = request.app.state.sessions
    mgr: ConnectionManager = request.app.state.ws_manager

    # Broadcast step_started
    await mgr.broadcast({
        "type": "step_started",
        "experiment_id": experiment_id,
        "step_name": step_name,
    })

    t0 = time.monotonic()
    try:
        kernel = await sessions.get_or_create(experiment_id)
        runner = PipelineRunner(
            kernel, store, on_chunk=_make_on_chunk(mgr), on_canvas=_make_on_canvas(mgr)
        )
        result = await runner.run_step(experiment_id, step_name)
        elapsed = round(time.monotonic() - t0, 1)

        # Broadcast step_completed
        await mgr.broadcast({
            "type": "step_completed",
            "experiment_id": experiment_id,
            "step_name": step_name,
            "status": result.status,
            "duration_s": elapsed,
        })
    except Exception:
        elapsed = round(time.monotonic() - t0, 1)
        logger.exception("Background step %s/%s failed", experiment_id, step_name)
        await mgr.broadcast({
            "type": "step_completed",
            "experiment_id": experiment_id,
            "step_name": step_name,
            "status": "failed",
            "duration_s": elapsed,
        })


@router.post("/{step_name}/run")
async def run_step(
    experiment_id: str, step_name: str, request: Request
) -> dict:
    store = request.app.state.store

    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")
    step = next((s for s in exp.steps if s.name == step_name), None)
    if step is None:
        raise HTTPException(404, f"Step {step_name!r} not found")

    # Launch execution in the background; results stream via WebSocket
    asyncio.create_task(
        _run_step_background(experiment_id, step_name, request)
    )
    return {"status": "started", "experiment_id": experiment_id, "step_name": step_name}


@router.post("/{step_name}/stop")
async def stop_step(
    experiment_id: str, step_name: str, request: Request
) -> dict[str, str]:
    sessions = request.app.state.sessions
    kernel = await sessions.get(experiment_id)
    if kernel is None:
        raise HTTPException(404, "No active kernel for this experiment")
    await kernel.interrupt()
    return {"status": "interrupted"}
