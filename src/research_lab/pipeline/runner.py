"""Pipeline orchestrator: dependency resolution, step execution, result collection."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from research_lab.engine.jupyter import JupyterKernel
from research_lab.pipeline.serializer import serialize_value
from research_lab.pipeline.store import ExperimentStore
from research_lab.schemas import (
    ImageOutput,
    OutputChunk,
    Step,
    StepResult,
    StepStatus,
)

_PROGRESS_SENTINEL = "__RL_PROGRESS__:"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

def topological_sort(steps: list[Step]) -> list[Step]:
    """Return steps in dependency order. Raises ValueError on cycles."""
    name_to_step = {s.name: s for s in steps}
    in_degree: dict[str, int] = defaultdict(int)
    graph: dict[str, list[str]] = defaultdict(list)

    for s in steps:
        in_degree.setdefault(s.name, 0)
        for dep in s.depends_on:
            graph[dep].append(s.name)
            in_degree[s.name] += 1

    queue: deque[str] = deque(n for n, d in in_degree.items() if d == 0)
    ordered: list[Step] = []

    while queue:
        name = queue.popleft()
        if name in name_to_step:
            ordered.append(name_to_step[name])
        for child in graph[name]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(ordered) != len(steps):
        raise ValueError("Cycle detected in step dependencies")
    return ordered


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class PipelineRunner:
    """Execute an experiment pipeline step by step."""

    def __init__(
        self,
        kernel: JupyterKernel,
        store: ExperimentStore,
        *,
        on_chunk: Any | None = None,
        on_canvas: Any | None = None,
        on_progress: Any | None = None,
    ) -> None:
        self._kernel = kernel
        self._store = store
        # Optional async callback(experiment_id, step_name, chunk) for streaming
        self._on_chunk = on_chunk
        # Optional async callback(experiment_id, step_name, canvas_name, widgets) for canvas updates
        self._on_canvas = on_canvas
        # Optional async callback(experiment_id, step_name, current, total, message) for progress
        self._on_progress = on_progress

    async def run_pipeline(self, experiment_id: str) -> list[StepResult]:
        """Run all steps in dependency order. Returns results."""
        exp = self._store.get(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment {experiment_id!r} not found")

        ordered = topological_sort(exp.steps)
        results: list[StepResult] = []

        for step in ordered:
            result = await self.run_step(experiment_id, step.name)
            results.append(result)
            if result.status == "failed":
                logger.warning(
                    "Step %s failed in experiment %s, halting pipeline",
                    step.name,
                    experiment_id,
                )
                break

        return results

    async def run_step(self, experiment_id: str, step_name: str) -> StepResult:
        """Execute a single step and persist the result.

        Automatically runs any dependencies that have not yet completed.
        """
        exp = self._store.get(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment {experiment_id!r} not found")

        step = next((s for s in exp.steps if s.name == step_name), None)
        if step is None:
            raise ValueError(f"Step {step_name!r} not found")

        # Auto-run pending dependencies (recursively)
        for dep_name in step.depends_on:
            dep_step = next((s for s in exp.steps if s.name == dep_name), None)
            if dep_step is None:
                raise ValueError(
                    f"Dependency {dep_name!r} of step {step_name!r} not found"
                )
            if dep_step.status != StepStatus.completed:
                logger.info(
                    "Auto-running dependency %r before %r in experiment %s",
                    dep_name,
                    step_name,
                    experiment_id,
                )
                dep_result = await self.run_step(experiment_id, dep_name)
                if dep_result.status == "failed":
                    raise ValueError(
                        f"Dependency {dep_name!r} failed; cannot run {step_name!r}"
                    )
                # Refresh experiment state after dependency ran
                exp = self._store.get(experiment_id)
                if exp is None:
                    raise ValueError(f"Experiment {experiment_id!r} not found")

        # Mark running
        self._store.update_step(experiment_id, step_name, {"status": StepStatus.running})

        run_number = self._store.next_run_number(experiment_id, step_name)
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        images: list[ImageOutput] = []
        error_text: str | None = None
        last_result_text: str = ""

        # Inject LabContext into the kernel before running user code
        ctx_code = _build_context_injection(experiment_id, step_name)
        async for _ in self._kernel.execute(ctx_code):
            pass  # silently inject

        # Save code snapshot
        self._store.save_code(experiment_id, step_name, step.code)

        # Watchdog: configurable inactivity timeout
        watchdog_seconds = step.config.get("watchdog_seconds", 300)
        step_timeout = step.config.get("timeout_seconds", None)

        # Execute user code
        try:
            last_activity = time.monotonic()
            watchdog_warned = False

            async for chunk in self._kernel.execute(step.code):
                now_mono = time.monotonic()

                # Check step-level timeout
                if step_timeout and (now_mono - t0) > step_timeout:
                    error_text = f"Step timed out after {step_timeout}s"
                    await self._emit(
                        experiment_id, step_name,
                        OutputChunk(kind="error", text=error_text),
                    )
                    # Interrupt the kernel to stop execution
                    try:
                        await self._kernel.interrupt()
                    except Exception:
                        pass
                    break

                # Watchdog: warn if no output for a long time
                if not watchdog_warned and (now_mono - last_activity) > watchdog_seconds:
                    warn_msg = f"WARNING: No output for {watchdog_seconds}s - step may be stuck\n"
                    await self._emit(
                        experiment_id, step_name,
                        OutputChunk(kind="stderr", text=warn_msg),
                    )
                    stderr_parts.append(warn_msg)
                    watchdog_warned = True

                last_activity = now_mono

                # Handle progress sentinel in stdout
                if chunk.kind == "stdout" and _PROGRESS_SENTINEL in chunk.text:
                    filtered_lines = []
                    for line in chunk.text.splitlines(keepends=True):
                        stripped = line.strip()
                        if stripped.startswith(_PROGRESS_SENTINEL):
                            # Parse progress JSON and broadcast
                            try:
                                payload = json.loads(stripped[len(_PROGRESS_SENTINEL):])
                                await self._emit_progress(
                                    experiment_id,
                                    step_name,
                                    payload.get("current", 0),
                                    payload.get("total", 0),
                                    payload.get("message", ""),
                                )
                            except (json.JSONDecodeError, Exception):
                                # If parsing fails, keep the line as stdout
                                filtered_lines.append(line)
                        else:
                            filtered_lines.append(line)
                    # Only emit and capture the non-sentinel lines
                    remaining = "".join(filtered_lines)
                    if remaining:
                        filtered_chunk = OutputChunk(kind="stdout", text=remaining)
                        await self._emit(experiment_id, step_name, filtered_chunk)
                        stdout_parts.append(remaining)
                    continue

                await self._emit(experiment_id, step_name, chunk)
                if chunk.kind == "stdout":
                    stdout_parts.append(chunk.text)
                elif chunk.kind == "stderr":
                    stderr_parts.append(chunk.text)
                elif chunk.kind == "error":
                    error_text = chunk.text
                elif chunk.kind in ("execute_result", "display_data"):
                    images.extend(chunk.images)
                    if chunk.text:
                        last_result_text = chunk.text
        except Exception as exc:
            error_text = str(exc)

        elapsed = time.monotonic() - t0
        completed_at = datetime.now(timezone.utc)
        status = "failed" if error_text else "completed"

        # Try to extract metrics from kernel namespace
        metrics = await self._extract_metrics(experiment_id, step_name)

        # Extract GPU snapshots and merge into metrics
        gpu_snapshots = await self._extract_gpu_snapshots(experiment_id, step_name)
        if gpu_snapshots:
            metrics["_gpu_snapshots"] = gpu_snapshots

        structured = await self._extract_structured(experiment_id, step_name)

        # Extract canvas data from kernel namespace
        canvases = await self._extract_canvases(experiment_id, step_name)

        result = StepResult(
            step_name=step_name,
            run_number=run_number,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            execution_time_s=round(elapsed, 3),
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            error=error_text,
            images=images,
            metrics=metrics,
            structured_data=structured,
            canvases=canvases,
        )

        # Persist
        self._store.save_result(experiment_id, result)
        self._store.update_step(
            experiment_id,
            step_name,
            {"status": StepStatus.completed if status == "completed" else StepStatus.failed},
        )

        # Persist and broadcast canvas data
        if canvases:
            self._store.save_canvases(experiment_id, step_name, canvases)
            for canvas_data in canvases:
                await self._emit_canvas(
                    experiment_id,
                    step_name,
                    canvas_data.get("canvas_name", ""),
                    canvas_data.get("widgets", []),
                )

        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _emit(self, experiment_id: str, step_name: str, chunk: OutputChunk) -> None:
        if self._on_chunk is not None:
            try:
                await self._on_chunk(experiment_id, step_name, chunk)
            except Exception:
                logger.exception("on_chunk callback failed")

    async def _emit_progress(
        self, experiment_id: str, step_name: str, current: int, total: int, message: str
    ) -> None:
        if self._on_progress is not None:
            try:
                await self._on_progress(experiment_id, step_name, current, total, message)
            except Exception:
                logger.exception("on_progress callback failed")

    async def _extract_gpu_snapshots(self, experiment_id: str, step_name: str) -> list[dict]:
        """Pull ctx._gpu_snapshots from the kernel namespace."""
        code = "import json as _j; print(_j.dumps(ctx._gpu_snapshots))"
        text = ""
        try:
            async for chunk in self._kernel.execute(code):
                if chunk.kind == "stdout":
                    text += chunk.text
            if text.strip():
                return json.loads(text.strip())
        except Exception:
            pass
        return []

    async def _extract_metrics(self, experiment_id: str, step_name: str) -> dict:
        """Pull ctx._metrics from the kernel namespace."""
        code = "import json as _j; print(_j.dumps(ctx._metrics))"
        text = ""
        try:
            async for chunk in self._kernel.execute(code):
                if chunk.kind == "stdout":
                    text += chunk.text
            if text.strip():
                return json.loads(text.strip())
        except Exception:
            pass
        return {}

    async def _emit_canvas(
        self, experiment_id: str, step_name: str, canvas_name: str, widgets: list[dict]
    ) -> None:
        if self._on_canvas is not None:
            try:
                await self._on_canvas(experiment_id, step_name, canvas_name, widgets)
            except Exception:
                logger.exception("on_canvas callback failed")

    async def _extract_canvases(self, experiment_id: str, step_name: str) -> list[dict]:
        """Pull ctx._canvases from the kernel namespace and return serialized list."""
        code = "import json as _j; print(_j.dumps([c.to_dict() for c in ctx._canvases]))"
        text = ""
        try:
            async for chunk in self._kernel.execute(code):
                if chunk.kind == "stdout":
                    text += chunk.text
            if text.strip():
                return json.loads(text.strip())
        except Exception:
            logger.debug("Could not extract canvases for %s/%s", experiment_id, step_name)
        return []

    async def _extract_structured(self, experiment_id: str, step_name: str) -> dict:
        """Pull ctx._results from the kernel and serialize them."""
        code = "import json as _j; print(_j.dumps(list(ctx._results.keys())))"
        text = ""
        try:
            async for chunk in self._kernel.execute(code):
                if chunk.kind == "stdout":
                    text += chunk.text
            if not text.strip():
                return {}
            keys = json.loads(text.strip())
        except Exception:
            return {}

        structured: dict[str, Any] = {}
        for key in keys:
            # Retrieve and serialize each saved result
            val_code = f"print(repr(ctx._results[{key!r}]))"
            val_text = ""
            try:
                async for chunk in self._kernel.execute(val_code):
                    if chunk.kind == "stdout":
                        val_text += chunk.text
                structured[key] = val_text.strip()[:1000]
            except Exception:
                structured[key] = "<serialization error>"

        return structured


# ---------------------------------------------------------------------------
# LabContext injection code
# ---------------------------------------------------------------------------

def _build_context_injection(experiment_id: str, step_name: str) -> str:
    """Return Python code that creates a LabContext as `ctx` in the kernel."""
    return f'''
import json as _rljson

class _LabCanvas:
    def __init__(self, name):
        self.name = name
        self._widgets = []
    def add_chart(self, fig, title=""):
        try:
            pj = fig.to_json()
            self._widgets.append({{"kind": "chart", "title": title, "plotly_json": _rljson.loads(pj)}})
        except Exception:
            self._widgets.append({{"kind": "text", "content": f"[chart: {{title}}]"}})
    def add_metrics(self, data):
        self._widgets.append({{"kind": "metrics", "data": dict(data)}})
    def add_text(self, content):
        self._widgets.append({{"kind": "text", "content": str(content)}})
    def add_image(self, fig_or_data, title="", mime="image/png"):
        import base64, io
        try:
            buf = io.BytesIO()
            # Check if it is a PIL Image (has .save and .mode)
            if hasattr(fig_or_data, "save") and hasattr(fig_or_data, "mode"):
                fig_or_data.save(buf, format="PNG")
            elif hasattr(fig_or_data, "savefig"):
                fig_or_data.savefig(buf, format="png", bbox_inches="tight")
            else:
                raise ValueError("Unknown image type")
            b64 = base64.b64encode(buf.getvalue()).decode()
            self._widgets.append({{"kind": "image", "title": title, "mime": mime, "data": b64}})
        except Exception:
            self._widgets.append({{"kind": "text", "content": f"[image: {{title}}]"}})
    def flush(self):
        pass  # In-kernel flush is a no-op; server pulls canvas state
    def to_dict(self):
        return {{"canvas_name": self.name, "widgets": self._widgets}}

class _LabContext:
    def __init__(self, experiment_id, step_name):
        self.experiment_id = experiment_id
        self.step_name = step_name
        self._metrics = {{}}
        self._results = {{}}
        self._canvases = []
        self._gpu_snapshots = []
    def log_metrics(self, **kwargs):
        self._metrics.update(kwargs)
    def save_result(self, name, value):
        self._results[name] = value
    def save_artifact(self, name, data, format="pt"):
        import os
        art_dir = os.path.join(".research-lab", "experiments", self.experiment_id, "artifacts")
        os.makedirs(art_dir, exist_ok=True)
        path = os.path.join(art_dir, f"{{name}}.{{format}}")

        if format == "pt":
            import torch
            torch.save(data, path)
        elif format == "npy":
            import numpy as np
            np.save(path, data)
        elif format == "safetensors":
            from safetensors.torch import save_file
            save_file(data, path)
        elif format == "json":
            import json
            with open(path, "w") as f:
                json.dump(data, f)
        else:
            with open(path, "wb") as f:
                f.write(data if isinstance(data, bytes) else str(data).encode())

        print(f"Artifact saved: {{path}}")
        return path
    def load_artifact(self, name, format=None):
        import os, glob as _rlglob
        art_dir = os.path.join(".research-lab", "experiments", self.experiment_id, "artifacts")
        matches = _rlglob.glob(os.path.join(art_dir, f"{{name}}.*"))
        if not matches:
            raise FileNotFoundError(f"No artifact named '{{name}}' found in {{art_dir}}")
        path = matches[0]
        ext = os.path.splitext(path)[1]

        if ext == ".pt":
            import torch
            return torch.load(path, weights_only=False)
        elif ext == ".npy":
            import numpy as np
            return np.load(path)
        elif ext == ".safetensors":
            from safetensors.torch import load_file
            return load_file(path)
        elif ext == ".json":
            import json
            with open(path) as f:
                return json.load(f)
        else:
            with open(path, "rb") as f:
                return f.read()
    def progress(self, current, total, message=""):
        import json as _rlpjson
        print(f"__RL_PROGRESS__:" + _rlpjson.dumps({{"current": current, "total": total, "message": message}}))
    def gpu_snapshot(self, label=""):
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,memory.free,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            parts = result.stdout.strip().split(", ")
            snapshot = {{
                "label": label,
                "memory_used_mb": int(parts[0]),
                "memory_total_mb": int(parts[1]),
                "memory_free_mb": int(parts[2]),
                "gpu_util_pct": int(parts[3])
            }}
            self._gpu_snapshots.append(snapshot)
            print(f"GPU: {{parts[0]}}MB / {{parts[1]}}MB used ({{parts[3]}}% util) [{{label}}]")
            return snapshot
        except Exception:
            return None
    def log(self, msg):
        print(msg)
    def checkpoint(self):
        pass  # Handled server-side
    def create_canvas(self, name):
        c = _LabCanvas(name)
        self._canvases.append(c)
        return c

ctx = _LabContext({experiment_id!r}, {step_name!r})
'''
