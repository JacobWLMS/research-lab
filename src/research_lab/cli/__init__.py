"""CLI entry point: Click group with --json/--pretty flag."""

from __future__ import annotations

import click

from research_lab.cli.commands import (
    download_cmd,
    exec_cmd,
    experiments_group,
    init_cmd,
    inspect_cmd,
    results_cmd,
    server_group,
    status_cmd,
    tail_cmd,
    upload_cmd,
)


@click.group()
@click.option("--json", "output_json", is_flag=True, default=True, hidden=True, help="JSON output (default)")
@click.option("--pretty", is_flag=True, default=False, help="Human-readable output")
@click.pass_context
def cli(ctx: click.Context, output_json: bool, pretty: bool) -> None:
    """research-lab: AI-First ML Experiment Management."""
    ctx.ensure_object(dict)
    ctx.obj["pretty"] = pretty


# Register subcommands
cli.add_command(init_cmd, "init")
cli.add_command(exec_cmd, "exec")
cli.add_command(status_cmd, "status")
cli.add_command(results_cmd, "results")
cli.add_command(server_group, "server")
cli.add_command(experiments_group, "experiments")
cli.add_command(upload_cmd, "upload")
cli.add_command(download_cmd, "download")
cli.add_command(inspect_cmd, "inspect")
cli.add_command(tail_cmd, "tail")


# Hidden mcp-server command
@cli.command("mcp-server", hidden=True)
def mcp_server_cmd() -> None:
    """Start the MCP server (stdio transport)."""
    from research_lab.mcp.server import run_mcp_server
    run_mcp_server()
