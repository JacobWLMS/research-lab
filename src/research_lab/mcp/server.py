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
        "AI-first ML experiment management. Use these tools to execute code, "
        "manage experiments, and retrieve structured results from the research-lab server."
    ),
)


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
async def exec(code: str) -> dict[str, Any]:
    """Execute Python code in the persistent IPython kernel.

    Returns structured output including stdout, stderr, images, and the
    result of the last expression.
    """
    async with _get_client() as client:
        result = await client.exec_code(code)
        return result.model_dump()


@mcp.tool()
async def run_experiment(experiment_id: str) -> list[dict[str, Any]]:
    """Run all steps of an experiment in dependency order.

    Returns a list of StepResult objects with execution results.
    """
    async with _get_client() as client:
        results = await client.run_experiment(experiment_id)
        return [r.model_dump() for r in results]


@mcp.tool()
async def run_step(experiment_id: str, step_name: str) -> dict[str, Any]:
    """Run a single step within an experiment.

    Returns the StepResult with stdout, stderr, images, metrics, etc.
    """
    async with _get_client() as client:
        result = await client.run_step(experiment_id, step_name)
        return result.model_dump()


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
        return await client.get_results(experiment_id, step_name)


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
