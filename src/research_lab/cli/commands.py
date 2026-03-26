"""All CLI commands for research-lab."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from pathlib import Path

import click


def _output(data: dict | list | str, ctx: click.Context) -> None:
    """Print output as JSON (default) or pretty-printed."""
    pretty = ctx.obj.get("pretty", False)
    if isinstance(data, str):
        click.echo(data)
    elif pretty:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(json.dumps(data, default=str))


def _run(coro):
    """Run an async coroutine in a new event loop."""
    return asyncio.run(coro)


def _get_client():
    """Create a ResearchLabClient."""
    from research_lab.client import ResearchLabClient
    return ResearchLabClient()


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@click.command()
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    """Initialize a research-lab project in the current directory."""
    from research_lab.config import ensure_lab_dir

    project_dir = Path.cwd()
    lab_dir = ensure_lab_dir(project_dir)

    # Create .gitignore for the .research-lab directory
    gitignore = project_dir / ".research-lab" / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "server.lock\nlogs/\n"
        )

    _output({"status": "initialized", "project_dir": str(project_dir), "lab_dir": str(lab_dir)}, ctx)


# ---------------------------------------------------------------------------
# exec
# ---------------------------------------------------------------------------

@click.command()
@click.argument("code")
@click.pass_context
def exec_cmd(ctx: click.Context, code: str) -> None:
    """Execute Python code in the kernel."""
    async def _run_exec():
        client = _get_client()
        async with client:
            result = await client.exec_code(code)
            return result.model_dump()

    data = _run(_run_exec())
    _output(data, ctx)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@click.command()
@click.pass_context
def status_cmd(ctx: click.Context) -> None:
    """Show server / kernel / GPU status."""
    async def _run_status():
        client = _get_client()
        async with client:
            status = await client.get_status()
            return status.model_dump()

    data = _run(_run_status())
    _output(data, ctx)


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------

@click.command()
@click.argument("experiment", required=False)
@click.argument("step", required=False)
@click.pass_context
def results_cmd(ctx: click.Context, experiment: str | None, step: str | None) -> None:
    """Read structured results as JSON."""
    async def _run_results():
        client = _get_client()
        async with client:
            if experiment is None:
                # List all experiments
                exps = await client.list_experiments()
                return [e.model_dump() for e in exps]
            return await client.get_results(experiment, step)

    data = _run(_run_results())
    _output(data, ctx)


# ---------------------------------------------------------------------------
# server group
# ---------------------------------------------------------------------------

@click.group()
def server_group() -> None:
    """Manage the research-lab server."""
    pass


@server_group.command("start")
@click.option("--host", default="127.0.0.1", help="Bind host")
@click.option("--port", default=8470, type=int, help="Bind port")
@click.option("--project-dir", default=None, type=click.Path(exists=True), help="Project directory")
@click.pass_context
def server_start(ctx: click.Context, host: str, port: int, project_dir: str | None) -> None:
    """Start the FastAPI server."""
    import uvicorn

    from research_lab.config import Settings
    from research_lab.server.app import create_app

    settings = Settings(
        host=host,
        port=port,
        project_dir=Path(project_dir) if project_dir else Path.cwd(),
    )
    app = create_app(settings)

    _output({"status": "starting", "host": host, "port": port}, ctx)

    uvicorn.run(app, host=host, port=port, log_level=settings.log_level)


@server_group.command("stop")
@click.pass_context
def server_stop(ctx: click.Context) -> None:
    """Stop the running server."""
    from research_lab.config import read_lockfile

    lock = read_lockfile()
    if lock is None:
        _output({"status": "not_running"}, ctx)
        return

    pid = lock.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            _output({"status": "stopped", "pid": pid}, ctx)
        except ProcessLookupError:
            _output({"status": "not_running", "stale_pid": pid}, ctx)
    else:
        _output({"status": "no_pid_in_lockfile"}, ctx)


# ---------------------------------------------------------------------------
# experiments group
# ---------------------------------------------------------------------------

@click.group()
def experiments_group() -> None:
    """Manage experiments."""
    pass


@experiments_group.command("list")
@click.pass_context
def experiments_list(ctx: click.Context) -> None:
    """List all experiments."""
    async def _run_list():
        client = _get_client()
        async with client:
            exps = await client.list_experiments()
            return [e.model_dump() for e in exps]

    data = _run(_run_list())
    _output(data, ctx)


@experiments_group.command("create")
@click.argument("name")
@click.pass_context
def experiments_create(ctx: click.Context, name: str) -> None:
    """Create a new experiment."""
    async def _run_create():
        client = _get_client()
        async with client:
            exp = await client.create_experiment(name)
            return exp.model_dump()

    data = _run(_run_create())
    _output(data, ctx)


@experiments_group.command("run")
@click.argument("name")
@click.option("--step", default=None, help="Run a specific step only")
@click.pass_context
def experiments_run(ctx: click.Context, name: str, step: str | None) -> None:
    """Run an experiment (or a specific step)."""
    async def _run_exp():
        client = _get_client()
        async with client:
            if step:
                click.echo(f"Running {name} step {step}...", err=True)
                result = await client.run_step(name, step)
                click.echo(
                    f"  \u25cf {step}: {result.status} ({result.execution_time_s:.2f}s)",
                    err=True,
                )
                click.echo("Done.", err=True)
                return result.model_dump()
            else:
                click.echo(f"Running {name}...", err=True)

                def _on_step_done(step_name: str, status: str, exec_time: float) -> None:
                    click.echo(
                        f"  \u25cf {step_name}: {status} ({exec_time:.2f}s)",
                        err=True,
                    )

                results = await client.run_experiment(
                    name, on_step_done=_on_step_done
                )
                click.echo("Done.", err=True)
                return [r.model_dump() for r in results]

    data = _run(_run_exp())
    _output(data, ctx)


# ---------------------------------------------------------------------------
# upload / download
# ---------------------------------------------------------------------------

@click.command()
@click.argument("local_path")
@click.argument("remote_path")
@click.pass_context
def upload_cmd(ctx: click.Context, local_path: str, remote_path: str) -> None:
    """Upload a file to the compute target."""
    async def _run_upload():
        client = _get_client()
        async with client:
            return await client.upload(local_path, remote_path)

    data = _run(_run_upload())
    _output(data, ctx)


@click.command()
@click.argument("remote_path")
@click.argument("local_path")
@click.pass_context
def download_cmd(ctx: click.Context, remote_path: str, local_path: str) -> None:
    """Download a file from the compute target."""
    async def _run_download():
        client = _get_client()
        async with client:
            return await client.download(remote_path, local_path)

    data = _run(_run_download())
    _output(data, ctx)


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

@click.command()
@click.argument("experiment_id")
@click.pass_context
def inspect_cmd(ctx: click.Context, experiment_id: str) -> None:
    """Inspect the kernel namespace for an experiment."""
    async def _run_inspect():
        client = _get_client()
        async with client:
            return await client.inspect_namespace(experiment_id)

    data = _run(_run_inspect())
    _output(data, ctx)


# ---------------------------------------------------------------------------
# tail
# ---------------------------------------------------------------------------

@click.command()
@click.argument("experiment_id")
@click.argument("step_name")
@click.pass_context
def tail_cmd(ctx: click.Context, experiment_id: str, step_name: str) -> None:
    """Stream live output from a running step via WebSocket."""
    import httpx

    from research_lab.config import read_lockfile

    lock = read_lockfile()
    if lock is None:
        click.echo("Error: Could not discover research-lab server.", err=True)
        sys.exit(1)

    base_url = lock["url"].rstrip("/")
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/ws"

    async def _stream():
        async with httpx.AsyncClient() as _unused:
            try:
                import websockets
            except ImportError:
                click.echo(
                    "Error: 'websockets' package required for tail. "
                    "Install with: pip install websockets",
                    err=True,
                )
                return

            click.echo(f"Connecting to {ws_url} ...", err=True)
            click.echo(
                f"Streaming output for {experiment_id}/{step_name} (Ctrl+C to stop)",
                err=True,
            )
            try:
                async with websockets.connect(ws_url) as ws:
                    while True:
                        raw = await ws.recv()
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        msg_exp = msg.get("experiment_id", "")
                        msg_step = msg.get("step_name", "")

                        # Filter for our experiment/step
                        if msg_exp != experiment_id or msg_step != step_name:
                            continue

                        msg_type = msg.get("type", "")
                        if msg_type == "stdout":
                            click.echo(msg.get("text", ""), nl=False)
                        elif msg_type == "stderr":
                            click.echo(msg.get("text", ""), nl=False, err=True)
                        elif msg_type == "error":
                            click.echo(f"ERROR: {msg.get('text', '')}", err=True)
                        elif msg_type == "progress":
                            current = msg.get("current", 0)
                            total = msg.get("total", 0)
                            message = msg.get("message", "")
                            pct = f"{current}/{total}"
                            if message:
                                pct += f" - {message}"
                            click.echo(f"[progress] {pct}", err=True)
                        elif msg_type == "step_completed":
                            status = msg.get("status", "unknown")
                            click.echo(f"\nStep completed: {status}", err=True)
                            break
            except KeyboardInterrupt:
                click.echo("\nDisconnected.", err=True)
            except Exception as exc:
                click.echo(f"WebSocket error: {exc}", err=True)

    _run(_stream())
