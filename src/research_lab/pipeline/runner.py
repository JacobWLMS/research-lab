"""Pipeline orchestrator: dependency resolution, step execution, result collection."""

from __future__ import annotations

import asyncio
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
    ) -> None:
        self._kernel = kernel
        self._store = store
        # Optional async callback(experiment_id, step_name, chunk) for streaming
        self._on_chunk = on_chunk
        # Optional async callback(experiment_id, step_name, canvas_name, widgets) for canvas updates
        self._on_canvas = on_canvas

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
        """Execute a single step and persist the result."""
        exp = self._store.get(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment {experiment_id!r} not found")

        step = next((s for s in exp.steps if s.name == step_name), None)
        if step is None:
            raise ValueError(f"Step {step_name!r} not found")

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

        # Execute user code
        try:
            async for chunk in self._kernel.execute(step.code):
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

    async def _extract_metrics(self, experiment_id: str, step_name: str) -> dict:
        """Pull ctx._metrics from the kernel namespace."""
        code = "import json as _j; print(_j.dumps(ctx._metrics))"
        text = ""
        try:
            async for chunk in self._kernel.execute(code):
                if chunk.kind == "stdout":
                    text += chunk.text
            if text.strip():
                import json
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
                import json
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
            import json
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
            fig_or_data.savefig(buf, format="png", bbox_inches="tight")
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
    def log_metrics(self, **kwargs):
        self._metrics.update(kwargs)
    def save_result(self, name, value):
        self._results[name] = value
    def save_artifact(self, name, data, format="pt"):
        pass  # Handled server-side
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
