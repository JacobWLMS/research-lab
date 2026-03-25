"""LabContext: injected into the kernel namespace as `ctx`.

This module defines the server-side LabContext and Canvas classes that
track state. The actual in-kernel version is injected as Python source
(see pipeline/runner.py), but this file provides the canonical types
for documentation, testing, and potential server-side usage.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

from research_lab.schemas import (
    CanvasState,
    ChartWidget,
    ImageWidget,
    MetricsWidget,
    TextWidget,
    Widget,
)

logger = logging.getLogger(__name__)


class Canvas:
    """AI-composed dashboard tab with typed widgets."""

    def __init__(self, name: str, *, flush_callback: Any | None = None) -> None:
        self.name = name
        self._widgets: list[Widget] = []
        self._flush_callback = flush_callback

    def add_chart(self, fig: Any, title: str = "") -> None:
        """Add a Plotly figure (serialized to JSON)."""
        try:
            plotly_json = json.loads(fig.to_json())
        except Exception:
            plotly_json = {}
            logger.warning("Could not serialize Plotly figure for canvas %s", self.name)
        self._widgets.append(ChartWidget(title=title, plotly_json=plotly_json))

    def add_metrics(self, data: dict[str, float | int | str]) -> None:
        """Add a key-value metrics strip."""
        self._widgets.append(MetricsWidget(data=dict(data)))

    def add_text(self, content: str) -> None:
        """Add a markdown text block."""
        self._widgets.append(TextWidget(content=str(content)))

    def add_image(
        self, fig_or_data: Any, title: str = "", mime: str = "image/png"
    ) -> None:
        """Add a matplotlib figure or raw base64 image."""
        b64 = ""
        try:
            buf = io.BytesIO()
            fig_or_data.savefig(buf, format="png", bbox_inches="tight")
            b64 = base64.b64encode(buf.getvalue()).decode()
        except AttributeError:
            # Maybe it's already base64
            if isinstance(fig_or_data, str):
                b64 = fig_or_data
        except Exception:
            logger.warning("Could not serialize image for canvas %s", self.name)
        self._widgets.append(ImageWidget(title=title, mime=mime, data=b64))

    def flush(self) -> None:
        """Push current canvas state to the frontend via WebSocket."""
        if self._flush_callback is not None:
            self._flush_callback(self.to_state())

    def to_state(self) -> CanvasState:
        """Serialize to a CanvasState model."""
        return CanvasState(canvas_name=self.name, widgets=self._widgets)


class LabContext:
    """Server-side LabContext tracking metrics, results, artifacts, and canvases."""

    def __init__(
        self,
        experiment_id: str,
        step_name: str,
        *,
        artifacts_dir: Any | None = None,
        flush_callback: Any | None = None,
    ) -> None:
        self.experiment_id = experiment_id
        self.step_name = step_name
        self._metrics: dict[str, float | int | str] = {}
        self._results: dict[str, Any] = {}
        self._canvases: list[Canvas] = []
        self._artifacts_dir = artifacts_dir
        self._flush_callback = flush_callback

    def log_metrics(self, **kwargs: float | int | str) -> None:
        """Record key-value metrics for this step."""
        self._metrics.update(kwargs)

    def save_result(self, name: str, value: Any) -> None:
        """Save a named result (will be auto-serialized to JSON summary)."""
        self._results[name] = value

    def save_artifact(self, name: str, data: Any, format: str = "pt") -> None:
        """Save raw bytes to the artifacts directory."""
        if self._artifacts_dir is None:
            logger.warning("No artifacts directory configured")
            return
        path = self._artifacts_dir / f"{name}.{format}"
        if format == "pt":
            try:
                import torch
                torch.save(data, path)
            except Exception:
                logger.exception("Failed to save torch artifact %s", name)
        elif format == "npy":
            try:
                import numpy as np
                np.save(path, data)
            except Exception:
                logger.exception("Failed to save numpy artifact %s", name)
        else:
            try:
                with open(path, "wb") as f:
                    f.write(data if isinstance(data, bytes) else str(data).encode())
            except Exception:
                logger.exception("Failed to save artifact %s", name)

    def log(self, msg: str) -> None:
        """Log a message (prints to stdout in the kernel)."""
        print(msg)

    def checkpoint(self) -> None:
        """Snapshot current state (metrics + results)."""
        logger.info(
            "Checkpoint: experiment=%s step=%s metrics=%s",
            self.experiment_id,
            self.step_name,
            self._metrics,
        )

    def create_canvas(self, name: str) -> Canvas:
        """Create a named canvas tab for AI-composed dashboards."""
        canvas = Canvas(name, flush_callback=self._flush_callback)
        self._canvases.append(canvas)
        return canvas
