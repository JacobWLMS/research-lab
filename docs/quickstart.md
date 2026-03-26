# Quick Start

## Install

```bash
pip install git+https://github.com/JacobWLMS/research-lab.git
```

## Initialize & Start

```bash
cd your-project
research-lab init
research-lab server start
```

## Create Your First Experiment

```bash
# Create an experiment
research-lab experiments create hello_world

# The server exposes a REST API at http://127.0.0.1:8470
# Add a step via the API:
curl -X POST http://127.0.0.1:8470/api/experiments/YOUR_ID/steps \
  -H "Content-Type: application/json" \
  -d '{"name": "greet", "code": "print(\"Hello from research-lab!\")\nctx.log_metrics(status=\"working\")"}'

# Run it
research-lab experiments run YOUR_ID
```

## Connect Claude Code (MCP)

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "research-lab": {
      "command": "/path/to/research-lab/.venv/bin/python",
      "args": ["-m", "research_lab.mcp.server"]
    }
  }
}
```

Then in Claude Code, use the `exec`, `create_experiment`, `run_step`, `get_results` tools natively.

## Web UI

For the full visual experience with live charts and canvas output:

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

## Next Steps

- [CLI Reference](CLI.md) -- All commands
- [LabContext API](CTX_API.md) -- The `ctx` object for structured output
- [Deployment Guide](DEPLOYMENT.md) -- RunPod, remote access, production setup
