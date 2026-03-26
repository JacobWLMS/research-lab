"""Step CRUD, execution, and stop endpoints."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from research_lab.pipeline.runner import PipelineRunner
from research_lab.schemas import Experiment, OutputChunk, Step, StepResult
from research_lab.server.ws import (
    ConnectionManager,
    broadcast_canvas_update,
    broadcast_chunk,
    broadcast_progress,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experiments/{experiment_id}/steps", tags=["steps"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateStepRequest(BaseModel):
    name: str
    title: str = ""
    description: str = ""
    code: str = ""
    depends_on: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)


class UpdateStepRequest(BaseModel):
    title: str | None = None
    description: str | None = None
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
    mgr: ConnectionManager = request.app.state.ws_manager
    step = Step(
        name=body.name, title=body.title, description=body.description,
        code=body.code, depends_on=body.depends_on, config=body.config,
    )
    exp = store.add_step(experiment_id, step)
    if exp is None:
        raise HTTPException(404, "Experiment not found or duplicate step name")
    await mgr.broadcast({
        "type": "step_added",
        "experiment_id": experiment_id,
        "step_name": body.name,
        "experiment": exp.model_dump(mode="json"),
    })
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


@router.get("/{step_name}/history")
async def get_step_history(
    experiment_id: str, step_name: str, request: Request
) -> dict:
    """Return summary metadata for every run of a step (lightweight, no stdout/images)."""
    store = request.app.state.store
    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")
    step = next((s for s in exp.steps if s.name == step_name), None)
    if step is None:
        raise HTTPException(404, f"Step {step_name!r} not found")
    runs = store.list_runs(experiment_id, step_name)
    return {"step_name": step_name, "runs": runs}


@router.get("/{step_name}/runs/{run_number}")
async def get_step_run(
    experiment_id: str, step_name: str, run_number: int, request: Request
) -> dict:
    """Return the full result + canvases for a specific historical run."""
    store = request.app.state.store
    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")
    step = next((s for s in exp.steps if s.name == step_name), None)
    if step is None:
        raise HTTPException(404, f"Step {step_name!r} not found")
    result = store.get_run_result(experiment_id, step_name, run_number)
    if result is None:
        raise HTTPException(404, f"Run #{run_number} not found for step {step_name!r}")
    canvases = store.get_run_canvases(experiment_id, step_name, run_number)
    return {
        "result": result.model_dump(mode="json"),
        "canvases": canvases,
    }


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


def _make_on_progress(mgr: ConnectionManager):
    """Create an on_progress async callback that broadcasts progress via WebSocket."""

    async def on_progress(
        experiment_id: str, step_name: str, current: int, total: int, message: str
    ) -> None:
        await broadcast_progress(mgr, experiment_id, step_name, current, total, message)

    return on_progress


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
            kernel,
            store,
            on_chunk=_make_on_chunk(mgr),
            on_canvas=_make_on_canvas(mgr),
            on_progress=_make_on_progress(mgr),
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


