# research-lab

AI-first ML experiment management platform. Run experiments as pipelines of named steps, get structured JSON results for AI analysis, and rich visual canvas reports for human review.

## Quick Start

```bash
# Install
pip install git+https://github.com/JacobWLMS/research-lab.git

# Initialize a project
cd your-project
research-lab init

# Start the server
research-lab server start

# Start the web UI (requires Node.js)
cd frontend && npm install && npm run dev
```

## What It Does

**The problem:** ML research with AI coding assistants involves cobbling together SSH, Jupyter APIs, and log tailing. The AI can't see plots, the human can't see AI-executed code in real-time, and results aren't saved incrementally.

**The solution:** A shared experiment platform where:
- The **AI** drives execution via CLI or MCP tools and reads structured JSON
- The **human** monitors via a web UI with interactive charts and canvas reports
- Both share the same IPython kernel, same data, same experiment

## Architecture

```
CLI (Click) ──┐
MCP (FastMCP) ─┤──→ ResearchLabClient ──→ FastAPI Server ──→ IPython Kernel
Web UI (Vue)  ─┘        (httpx)            (REST + WS)       (jupyter_client)
```

## Features

### Pipeline Execution
Experiments are pipelines of named steps with optional dependencies:
```bash
research-lab experiments create my_experiment
research-lab experiments run my_experiment
```

Steps execute in dependency order in a persistent IPython kernel — variables from step 1 are available in step 2.

### LabContext API
Every step has access to a `ctx` object for structured output:

```python
# Metrics (structured JSON for AI)
ctx.log_metrics(epoch=10, loss=0.05, accuracy=0.94)

# Save structured results
ctx.save_result("confusion_matrix", {"tp": 42, "fp": 3, "fn": 5, "tn": 50})

# Save raw artifacts (tensors, models)
ctx.save_artifact("model", model.state_dict(), format="pt")

# Create visual canvas reports (for human review)
canvas = ctx.create_canvas("Training Results")
canvas.add_chart(plotly_figure, title="Loss Curve")
canvas.add_metrics({"accuracy": 0.94, "f1": 0.938})
canvas.add_text("Model converged after 42 epochs.")
canvas.add_image(matplotlib_fig, title="Confusion Matrix")
```

### Canvas Reports
Each step can have AI-composed visual reports with:
- Interactive Plotly charts
- Metrics summary chips
- Markdown text blocks
- Static images (matplotlib, PIL, raw PNG)

Click "View Report" on any step to open the full-screen canvas.

### Three Interfaces

**CLI** — AI-friendly, JSON output by default:
```bash
research-lab exec "print('hello')"
research-lab status
research-lab results my_experiment train_step
```

**MCP Server** — native Claude Code integration:
```json
{
  "mcpServers": {
    "research-lab": {
      "command": "research-lab",
      "args": ["mcp-server"]
    }
  }
}
```

**Web UI** — Vue 3 + Tailwind with Gruvbox theme:
- Master-detail layout with experiment list and pipeline visualization
- Light/dark mode, zoom controls, keyboard shortcuts
- Real-time WebSocket updates during execution
- Full-screen canvas report viewer

### Compute Backends
- **Local**: IPython kernel on your machine
- **RunPod**: SSH tunnel to remote GPU kernel

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python, FastAPI, jupyter_client, ZMQ |
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS 4 |
| Charts | Plotly.js (interactive), matplotlib (static) |
| CLI | Click |
| MCP | FastMCP (stdio transport) |
| Persistence | File-based JSON (git-friendly) |

## Development

```bash
git clone https://github.com/JacobWLMS/research-lab.git
cd research-lab

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest

# Frontend
cd frontend && npm install && npm run dev
```

## License

MIT
