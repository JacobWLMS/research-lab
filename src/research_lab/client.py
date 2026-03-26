"""ResearchLabClient: async HTTP client for the research-lab server.

Discovers the server via the lockfile and provides typed methods
for all API operations.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from research_lab.config import read_lockfile
from research_lab.schemas import (
    ExecResult,
    Experiment,
    ImageOutput,
    OutputChunk,
    StatusResponse,
    StepResult,
)


class ResearchLabClient:
    """Async client that talks to the research-lab FastAPI server."""

    def __init__(
        self,
        base_url: str | None = None,
        project_dir: Path | None = None,
        timeout: float = 300.0,
    ) -> None:
        if base_url is None:
            # Check env var first — allows pointing at remote servers (RunPod tunnel etc.)
            import os
            base_url = os.environ.get("RESEARCH_LAB_URL")
        if base_url is None:
            lock = read_lockfile(project_dir)
            if lock is None:
                raise RuntimeError(
                    "Could not discover research-lab server. "
                    "Is it running? (research-lab server start)\n"
                    "Or set RESEARCH_LAB_URL=https://your-tunnel.trycloudflare.com"
                )
            base_url = lock["url"]
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base, timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> ResearchLabClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str) -> Any:
        r = await self._client.get(path)
        r.raise_for_status()
        return r.json()

    async def _post(self, path: str, json: Any = None) -> Any:
        r = await self._client.post(path, json=json)
        r.raise_for_status()
        return r.json()

    async def _put(self, path: str, json: Any = None) -> Any:
        r = await self._client.put(path, json=json)
        r.raise_for_status()
        return r.json()

    async def _delete(self, path: str) -> Any:
        r = await self._client.delete(path)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    async def health(self) -> dict:
        return await self._get("/api/health")

    async def get_status(self) -> StatusResponse:
        data = await self._get("/api/status")
        return StatusResponse.model_validate(data)

    # ------------------------------------------------------------------
    # Experiments
    # ------------------------------------------------------------------

    async def list_experiments(self) -> list[Experiment]:
        data = await self._get("/api/experiments")
        return [Experiment.model_validate(d) for d in data]

    async def create_experiment(
        self,
        name: str,
        compute_backend: str = "local",
        steps: list[dict] | None = None,
    ) -> Experiment:
        body: dict[str, Any] = {"name": name, "compute_backend": compute_backend}
        if steps:
            body["steps"] = steps
        data = await self._post("/api/experiments", json=body)
        return Experiment.model_validate(data)

    async def get_experiment(self, experiment_id: str) -> Experiment:
        data = await self._get(f"/api/experiments/{experiment_id}")
        return Experiment.model_validate(data)

    async def update_experiment(self, experiment_id: str, **kwargs: Any) -> Experiment:
        data = await self._put(f"/api/experiments/{experiment_id}", json=kwargs)
        return Experiment.model_validate(data)

    async def delete_experiment(self, experiment_id: str) -> dict:
        return await self._delete(f"/api/experiments/{experiment_id}")

    async def run_experiment(
        self,
        experiment_id: str,
        poll_interval: float = 1.0,
        on_step_done: Callable[[str, str, float], Any] | None = None,
    ) -> list[StepResult]:
        """Trigger a full pipeline run and poll until all steps finish.

        *on_step_done(step_name, status, execution_time_s)* is called each
        time a step transitions to completed/failed (useful for progress).
        """
        # Trigger -- returns immediately with {"status": "started", ...}
        await self._post(f"/api/experiments/{experiment_id}/run")

        # Track which steps we have already reported so we only call the
        # callback once per step.
        reported: set[str] = set()

        # Poll until every step has reached a terminal state (completed/failed).
        # Steps that remain "pending" after others have run means the pipeline
        # halted early (e.g. a dependency failed), so we treat that as done too,
        # but only after at least one step has actually executed.
        while True:
            await asyncio.sleep(poll_interval)
            exp_data = await self._get(f"/api/experiments/{experiment_id}")
            steps = exp_data.get("steps", [])

            # Report newly-finished steps
            if on_step_done:
                for s in steps:
                    sname = s["name"]
                    if sname not in reported and s["status"] in ("completed", "failed"):
                        # Try to get execution_time from the result
                        try:
                            step_data = await self._get(
                                f"/api/experiments/{experiment_id}/steps/{sname}"
                            )
                            result = step_data.get("result") or {}
                            exec_time = result.get("execution_time_s", 0)
                        except Exception:
                            exec_time = 0
                        on_step_done(sname, s["status"], exec_time)
                        reported.add(sname)

            # Check: nothing is still running
            none_running = all(
                s["status"] != "running" for s in steps
            )
            any_ran = any(s["status"] in ("completed", "failed") for s in steps)
            if none_running and any_ran:
                break

        # Collect final results -- the endpoint returns a dict keyed by step name.
        results_data = await self._get(f"/api/experiments/{experiment_id}/results")
        results: list[StepResult] = []
        if isinstance(results_data, dict):
            for _name, r in results_data.items():
                if isinstance(r, dict):
                    results.append(StepResult.model_validate(r))
        elif isinstance(results_data, list):
            for r in results_data:
                results.append(StepResult.model_validate(r))
        return results

    async def get_results(
        self, experiment_id: str, step_name: str | None = None
    ) -> dict[str, Any]:
        if step_name:
            return await self._get(
                f"/api/experiments/{experiment_id}/steps/{step_name}"
            )
        return await self._get(f"/api/experiments/{experiment_id}/results")

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    async def add_step(
        self,
        experiment_id: str,
        name: str,
        code: str = "",
        depends_on: list[str] | None = None,
        config: dict | None = None,
    ) -> Experiment:
        body = {
            "name": name,
            "code": code,
            "depends_on": depends_on or [],
            "config": config or {},
        }
        data = await self._post(f"/api/experiments/{experiment_id}/steps", json=body)
        return Experiment.model_validate(data)

    async def update_step(
        self, experiment_id: str, step_name: str, **kwargs: Any
    ) -> Experiment:
        data = await self._put(
            f"/api/experiments/{experiment_id}/steps/{step_name}", json=kwargs
        )
        return Experiment.model_validate(data)

    async def run_step(
        self,
        experiment_id: str,
        step_name: str,
        poll_interval: float = 1.0,
    ) -> StepResult:
        """Trigger a single step and poll until it completes or fails."""
        # Trigger -- returns immediately with {"status": "started", ...}
        await self._post(
            f"/api/experiments/{experiment_id}/steps/{step_name}/run"
        )

        # Poll GET /api/experiments/{id}/steps/{name} until done
        while True:
            await asyncio.sleep(poll_interval)
            data = await self._get(
                f"/api/experiments/{experiment_id}/steps/{step_name}"
            )
            step = data.get("step", {})
            status = step.get("status", "pending")
            if status in ("completed", "failed"):
                result = data.get("result")
                if result:
                    return StepResult.model_validate(result)
                # Step finished but no persisted result yet -- return minimal
                return StepResult(
                    step_name=step_name,
                    run_number=0,
                    status=status,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    execution_time_s=0,
                )

    async def stop_step(self, experiment_id: str, step_name: str) -> dict:
        return await self._post(
            f"/api/experiments/{experiment_id}/steps/{step_name}/stop"
        )

    async def inspect_namespace(self, experiment_id: str) -> dict:
        """Inspect the kernel namespace for an experiment.

        Returns a mapping of variable names to info dicts with type, repr,
        and optionally shape/len.
        """
        return await self._get(
            f"/api/experiments/{experiment_id}/kernel/namespace"
        )

    # ------------------------------------------------------------------
    # Ad-hoc execution
    # ------------------------------------------------------------------

    async def exec_code(self, code: str) -> ExecResult:
        """Execute code via the REST exec endpoint (POST /api/exec)."""
        # The exec endpoint is on the WebSocket, so we use the REST
        # approach: connect compute, then run via a temporary step.
        # For simplicity, we POST to a dedicated endpoint.
        data = await self._post("/api/exec", json={"code": code})
        return ExecResult.model_validate(data)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    async def connect_compute(
        self, backend: str = "local", config: dict | None = None
    ) -> dict:
        return await self._post(
            "/api/compute/connect",
            json={"backend": backend, "config": config or {}},
        )

    async def compute_status(self) -> dict:
        return await self._get("/api/compute/status")

    async def disconnect_compute(self) -> dict:
        return await self._post("/api/compute/disconnect")

    # ------------------------------------------------------------------
    # File transfer
    # ------------------------------------------------------------------

    async def upload(self, local: str, remote: str) -> dict:
        return await self._post("/api/upload", json={"local": local, "remote": remote})

    async def download(self, remote: str, local: str) -> dict:
        return await self._post("/api/download", json={"remote": remote, "local": local})
