"""FastMCP server with tools for research-lab.

Exposes the same operations as the CLI as MCP tools, using stdio transport.
All tools return Pydantic models for structured content.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from research_lab.client import ResearchLabClient
from research_lab.schemas import (
    ExecResult,
    Experiment,
    StatusResponse,
    StepResult,
)

mcp = FastMCP(
    "research-lab",
    instructions=(
        "AI-first ML experiment management platform.\n\n"
        "WORKFLOW: Always create experiments with named steps for real work. "
        "Do NOT use exec() for experiments — create proper pipeline steps so results "
        "appear in the web UI with canvases, metrics, and visual reports.\n\n"
        "1. create_experiment('name') to create an experiment\n"
        "2. Add steps via the API (POST /api/experiments/{id}/steps)\n"
        "3. run_experiment(id) or run_step(id, step) to execute\n"
        "4. get_results(id) to read structured results\n\n"
        "Use exec() ONLY for quick debugging or one-off queries. "
        "Pass experiment_id to exec() to run in an experiment's kernel namespace.\n\n"
        "Steps should use ctx.log_metrics(), ctx.create_canvas(), ctx.save_result() "
        "to produce structured output visible in the web UI."
    ),
)

_PLACEHOLDER = "[image too large for MCP response - view in web UI]"


def _get_image_max_bytes() -> int:
    """Read image_max_bytes from settings, falling back to 100_000."""
    try:
        from research_lab.config import Settings
        return Settings().image_max_bytes
    except Exception:
        return 100_000


def _cap_images(result_dict: dict[str, Any], max_bytes: int | None = None) -> dict[str, Any]:
    """Replace oversized base64 image data with a placeholder message.

    Mutates *result_dict* in place and also returns it for convenience.
    """
    if max_bytes is None:
        max_bytes = _get_image_max_bytes()
    for img in result_dict.get("images", []):
        if len(img.get("data", "")) > max_bytes:
            img["data"] = _PLACEHOLDER
    for canvas in result_dict.get("canvases", []):
        for widget in canvas.get("widgets", []):
            if widget.get("kind") == "image" and len(widget.get("data", "")) > max_bytes:
                widget["data"] = _PLACEHOLDER
    return result_dict


def _get_client() -> ResearchLabClient:
    """Get a client, auto-starting the server if needed."""
    from research_lab.config import read_lockfile
    lock = read_lockfile()
    if lock is None:
        # Try to start the server automatically
        _auto_start_server()
        lock = read_lockfile()
    if lock:
        return ResearchLabClient(base_url=lock["url"])
    return ResearchLabClient()


def _auto_start_server() -> None:
    """Attempt to start the research-lab server in the background."""
    import subprocess
    import sys
    import time
    try:
        # Find project dir — check common locations
        from research_lab.config import find_project_root
        from pathlib import Path
        root = find_project_root()
        if root is None:
            # Try home dir
            home_lab = Path.home() / ".research-lab"
            if home_lab.is_dir():
                root = Path.home()
            else:
                return  # Can't find a project
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn",
             "research_lab.server.app:create_app", "--factory",
             "--host", "127.0.0.1", "--port", "8470"],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait briefly for it to start
        time.sleep(3)
    except Exception:
        pass  # Best effort


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def exec(code: str, experiment_id: str | None = None) -> dict[str, Any]:
    """Execute Python code in an IPython kernel.

    If experiment_id is provided, runs in that experiment's kernel (shared namespace
    with its steps — use this to debug or inspect experiment state).
    If experiment_id is omitted, runs in a shared ad-hoc kernel.

    IMPORTANT: Always create proper experiments with steps for real work.
    Use exec only for quick one-off queries or debugging.
    """
    async with _get_client() as client:
        result = await client.exec_code(code, experiment_id=experiment_id)
        return _cap_images(result.model_dump())


@mcp.tool()
async def run_experiment(experiment_id: str) -> list[dict[str, Any]]:
    """Run all steps of an experiment in dependency order.

    Returns a list of StepResult objects with execution results.
    """
    async with _get_client() as client:
        results = await client.run_experiment(experiment_id)
        return [_cap_images(r.model_dump()) for r in results]


@mcp.tool()
async def run_step(experiment_id: str, step_name: str) -> dict[str, Any]:
    """Run a single step within an experiment.

    Returns the StepResult with stdout, stderr, images, metrics, etc.
    """
    async with _get_client() as client:
        result = await client.run_step(experiment_id, step_name)
        return _cap_images(result.model_dump())


@mcp.tool()
async def get_status() -> dict[str, Any]:
    """Get the current server status including kernel state, GPU info, and active tasks."""
    async with _get_client() as client:
        status = await client.get_status()
        return status.model_dump()


@mcp.tool()
async def get_results(
    experiment_id: str, step_name: str | None = None
) -> dict[str, Any]:
    """Get structured results for an experiment or a specific step.

    If step_name is provided, returns that step's result.
    Otherwise returns all step results for the experiment.
    """
    async with _get_client() as client:
        data = await client.get_results(experiment_id, step_name)
        # Cap images in each step result (data is either a single result dict
        # or a dict keyed by step name containing result dicts).
        if isinstance(data, dict):
            # Check if this looks like a per-step mapping (keys are step names)
            # vs a single result dict (has "step_name" key).
            if "step_name" in data or "images" in data:
                _cap_images(data)
            else:
                for _key, val in data.items():
                    if isinstance(val, dict):
                        _cap_images(val)
        return data


@mcp.tool()
async def list_experiments() -> list[dict[str, Any]]:
    """List all experiments in the project."""
    async with _get_client() as client:
        exps = await client.list_experiments()
        return [e.model_dump() for e in exps]


@mcp.tool()
async def create_experiment(
    name: str, compute_backend: str = "local"
) -> dict[str, Any]:
    """Create a new experiment with the given name.

    Returns the created Experiment object.
    """
    async with _get_client() as client:
        exp = await client.create_experiment(name, compute_backend)
        return exp.model_dump()


@mcp.tool()
async def add_step(
    experiment_id: str,
    name: str,
    title: str = "",
    description: str = "",
    code: str = "",
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    """Add a step to an experiment.

    Every step should have a clear title and description so the human
    understands what it does when viewing the pipeline in the web UI.

    Args:
        experiment_id: The experiment to add the step to
        name: Technical name (used as identifier, no spaces)
        title: Human-readable title (e.g., "Extract Token Embeddings")
        description: What this step does (shown below the title in the UI)
        code: Python code to execute
        depends_on: List of step names this step depends on
    """
    async with _get_client() as client:
        exp = await client.add_step(
            experiment_id, name, title=title, description=description,
            code=code, depends_on=depends_on or [],
        )
        return exp.model_dump()


@mcp.tool()
async def inspect_namespace(experiment_id: str) -> dict[str, Any]:
    """Inspect the kernel namespace for a running experiment.

    Returns a mapping of variable names to info dicts containing:
    - type: the Python type name
    - repr: a truncated repr (max 200 chars)
    - shape: (if applicable) tensor/array shape
    - len: (if applicable) collection length

    Useful for debugging, checking what variables are in scope,
    and verifying tensor shapes during ML workflows.
    """
    async with _get_client() as client:
        return await client.inspect_namespace(experiment_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_mcp_server() -> None:
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_mcp_server()
