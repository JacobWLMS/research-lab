"""Pydantic models -- the single data contract for research-lab."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class KernelStatus(str, Enum):
    idle = "idle"
    busy = "busy"
    dead = "dead"
    not_connected = "not_connected"


# ---------------------------------------------------------------------------
# Core experiment models
# ---------------------------------------------------------------------------

class Step(BaseModel):
    """A single step within an experiment pipeline."""

    model_config = {"from_attributes": True}

    name: str
    code: str = ""
    depends_on: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = StepStatus.pending


class Experiment(BaseModel):
    """Top-level experiment with an ordered pipeline of steps."""

    model_config = {"from_attributes": True}

    id: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    compute_backend: str = "local"
    steps: list[Step] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution results
# ---------------------------------------------------------------------------

class ImageOutput(BaseModel):
    """A base64-encoded image captured during step execution."""

    label: str
    mime: str = "image/png"
    data: str  # base64


class StepResult(BaseModel):
    """Structured output produced by running one step."""

    model_config = {"from_attributes": True}

    step_name: str
    run_number: int
    status: Literal["completed", "failed"]
    started_at: datetime
    completed_at: datetime
    execution_time_s: float
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    images: list[ImageOutput] = Field(default_factory=list)
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    structured_data: dict[str, Any] = Field(default_factory=dict)
    canvases: list[dict[str, Any]] = Field(default_factory=list)  # [{canvas_name, widgets}]


# ---------------------------------------------------------------------------
# System / status
# ---------------------------------------------------------------------------

class GpuInfo(BaseModel):
    name: str
    utilization_pct: float
    memory_used_gb: float
    memory_total_gb: float
    temperature_c: float


class StatusResponse(BaseModel):
    server_running: bool
    kernel_status: KernelStatus = KernelStatus.not_connected
    gpu: GpuInfo | None = None
    active_tasks: list[str] = Field(default_factory=list)
    current_experiment: str | None = None


# ---------------------------------------------------------------------------
# Canvas / widget models (AI-composed dashboard)
# ---------------------------------------------------------------------------

class WidgetKind(str, Enum):
    chart = "chart"
    metrics = "metrics"
    text = "text"
    image = "image"


class ChartWidget(BaseModel):
    kind: Literal["chart"] = "chart"
    title: str = ""
    plotly_json: dict[str, Any] = Field(default_factory=dict)


class MetricsWidget(BaseModel):
    kind: Literal["metrics"] = "metrics"
    data: dict[str, float | int | str] = Field(default_factory=dict)


class TextWidget(BaseModel):
    kind: Literal["text"] = "text"
    content: str = ""


class ImageWidget(BaseModel):
    kind: Literal["image"] = "image"
    title: str = ""
    mime: str = "image/png"
    data: str = ""  # base64


Widget = ChartWidget | MetricsWidget | TextWidget | ImageWidget


class CanvasState(BaseModel):
    """Snapshot of an AI-composed canvas tab."""

    canvas_name: str
    widgets: list[Widget] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution engine output chunks
# ---------------------------------------------------------------------------

class OutputChunk(BaseModel):
    """A single unit of output from kernel execution."""

    kind: Literal["stdout", "stderr", "execute_result", "display_data", "error", "status"]
    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    images: list[ImageOutput] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Ad-hoc execution
# ---------------------------------------------------------------------------

class ExecResult(BaseModel):
    """Result of ad-hoc code execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    images: list[ImageOutput] = Field(default_factory=list)
    result: str | None = None  # repr of last expression


# ---------------------------------------------------------------------------
# WebSocket message envelopes
# ---------------------------------------------------------------------------

class WSMessage(BaseModel):
    """Generic WebSocket message envelope."""

    type: str
    experiment_id: str | None = None
    step_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
