"""Experiment CRUD endpoints."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timezone

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

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


# ---------------------------------------------------------------------------
# Request / response helpers
# ---------------------------------------------------------------------------

class CreateExperimentRequest(BaseModel):
    name: str
    compute_backend: str = "local"
    steps: list[Step] = Field(default_factory=list)


class UpdateExperimentRequest(BaseModel):
    name: str | None = None
    compute_backend: str | None = None


def _slug(name: str) -> str:
    """Create a URL-safe slug from a name."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{s}-{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[Experiment])
async def list_experiments(request: Request) -> list[Experiment]:
    store = request.app.state.store
    return store.list_all()


@router.post("", response_model=Experiment, status_code=201)
async def create_experiment(body: CreateExperimentRequest, request: Request) -> Experiment:
    store = request.app.state.store
    mgr: ConnectionManager = request.app.state.ws_manager
    now = datetime.now(timezone.utc)
    exp = Experiment(
        id=_slug(body.name),
        name=body.name,
        created_at=now,
        updated_at=now,
        compute_backend=body.compute_backend,
        steps=body.steps,
    )
    result = store.create(exp)
    await mgr.broadcast({"type": "experiment_created", "experiment": result.model_dump(mode="json")})
    return result


@router.get("/{experiment_id}", response_model=Experiment)
async def get_experiment(experiment_id: str, request: Request) -> Experiment:
    store = request.app.state.store
    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")
    return exp


@router.put("/{experiment_id}", response_model=Experiment)
async def update_experiment(
    experiment_id: str, body: UpdateExperimentRequest, request: Request
) -> Experiment:
    store = request.app.state.store
    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")
    if body.name is not None:
        exp.name = body.name
    if body.compute_backend is not None:
        exp.compute_backend = body.compute_backend
    return store.update(exp)


@router.delete("/{experiment_id}")
async def delete_experiment(experiment_id: str, request: Request) -> dict[str, bool]:
    store = request.app.state.store
    mgr: ConnectionManager = request.app.state.ws_manager
    deleted = store.delete(experiment_id)
    if not deleted:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")
    await mgr.broadcast({
        "type": "experiment_deleted",
        "experiment_id": experiment_id,
    })
    return {"deleted": True}


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


async def _run_pipeline_background(
    experiment_id: str,
    request: Request,
) -> None:
    """Run the full pipeline in the background, broadcasting lifecycle events via WebSocket."""
    store = request.app.state.store
    sessions = request.app.state.sessions
    mgr: ConnectionManager = request.app.state.ws_manager

    exp = store.get(experiment_id)
    if exp is None:
        return

    try:
        kernel = await sessions.get_or_create(experiment_id)
        on_chunk = _make_on_chunk(mgr)
        on_canvas = _make_on_canvas(mgr)
        on_progress = _make_on_progress(mgr)
        runner = PipelineRunner(
            kernel, store, on_chunk=on_chunk, on_canvas=on_canvas, on_progress=on_progress
        )

        # Run each step with lifecycle broadcasts
        from research_lab.pipeline.runner import topological_sort

        ordered = topological_sort(exp.steps)
        for step in ordered:
            await mgr.broadcast({
                "type": "step_started",
                "experiment_id": experiment_id,
                "step_name": step.name,
            })
            t0 = time.monotonic()
            result = await runner.run_step(experiment_id, step.name)
            elapsed = round(time.monotonic() - t0, 1)
            await mgr.broadcast({
                "type": "step_completed",
                "experiment_id": experiment_id,
                "step_name": step.name,
                "status": result.status,
                "duration_s": elapsed,
            })
            if result.status == "failed":
                logger.warning(
                    "Step %s failed in experiment %s, halting pipeline",
                    step.name,
                    experiment_id,
                )
                break

        # Broadcast pipeline-level completion
        await mgr.broadcast({
            "type": "pipeline_completed",
            "experiment_id": experiment_id,
        })
    except Exception:
        logger.exception("Background pipeline %s failed", experiment_id)
        await mgr.broadcast({
            "type": "pipeline_completed",
            "experiment_id": experiment_id,
            "status": "failed",
        })


@router.post("/{experiment_id}/run")
async def run_pipeline(experiment_id: str, request: Request) -> dict:
    store = request.app.state.store

    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")

    # Launch pipeline execution in the background; results stream via WebSocket
    asyncio.create_task(
        _run_pipeline_background(experiment_id, request)
    )
    return {"status": "started", "experiment_id": experiment_id}


@router.get("/{experiment_id}/kernel/namespace")
async def inspect_namespace(experiment_id: str, request: Request) -> dict:
    """Inspect the kernel namespace for an experiment.

    Returns a mapping of variable names to info dicts containing type, repr,
    and optionally shape/len.
    """
    import json as _json

    sessions = request.app.state.sessions
    kernel = await sessions.get(experiment_id)
    if kernel is None:
        raise HTTPException(404, "No active kernel for this experiment")

    _inspect_code = '''
import json as _rlinspect_json
_rl_vars = {}
for _rl_name, _rl_val in globals().items():
    if not _rl_name.startswith('_') and _rl_name not in ('In', 'Out', 'get_ipython', 'exit', 'quit', 'ctx'):
        _rl_type = type(_rl_val).__name__
        _rl_repr = repr(_rl_val)[:200]
        _rl_info = {"type": _rl_type, "repr": _rl_repr}
        if hasattr(_rl_val, 'shape'):
            _rl_info["shape"] = str(_rl_val.shape)
        if hasattr(_rl_val, '__len__'):
            try: _rl_info["len"] = len(_rl_val)
            except: pass
        _rl_vars[_rl_name] = _rl_info
print(_rlinspect_json.dumps(_rl_vars))
'''

    text = ""
    try:
        async for chunk in kernel.execute(_inspect_code):
            if chunk.kind == "stdout":
                text += chunk.text
            elif chunk.kind == "error":
                raise HTTPException(500, f"Kernel error: {chunk.text}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to inspect namespace: {exc}")

    if not text.strip():
        return {}

    try:
        return _json.loads(text.strip())
    except _json.JSONDecodeError:
        raise HTTPException(500, "Failed to parse namespace data")


@router.get("/{experiment_id}/results")
async def get_all_results(experiment_id: str, request: Request) -> dict:
    """Return a mapping of step_name -> StepResult (with canvases) for the experiment.

    The response is a JSON object keyed by step name, e.g.::

        {"train": {..., "canvases": [...]}, "evaluate": {..., "canvases": [...]}}
    """
    store = request.app.state.store
    exp = store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id!r} not found")
    results = store.get_all_results(experiment_id)
    # Enrich each result with its persisted canvas data
    enriched: dict[str, dict] = {}
    for step_name, result in results.items():
        result_dict = result.model_dump()
        # Merge in canvases from separate file if the result itself has none
        if not result_dict.get("canvases"):
            result_dict["canvases"] = store.get_canvases(experiment_id, step_name)
        enriched[step_name] = result_dict
    return enriched
