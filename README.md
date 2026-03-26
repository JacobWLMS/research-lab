<div align="center">

# research-lab

**AI-first experiment management platform**

Run experiments as pipelines of named steps. Get structured JSON for AI analysis. Get rich visual output for human review. Share the same kernel, same data, same results.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue_3-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://vuejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Quick Start](#quick-start) &bull; [Features](#features) &bull; [Documentation](#documentation) &bull; [Architecture](#architecture)

</div>

---

## The Problem

ML research with AI coding assistants means cobbling together SSH, Jupyter APIs, and log tailing. The AI can't see plots. The human can't see AI-executed code in real-time. Results aren't saved incrementally. Notebooks get messy, scattered, and unmanageable at scale.

## The Solution

A shared platform where the **AI drives execution** and the **human monitors results** -- both looking at the same experiments, same kernel, same data.

```
AI (Claude Code)                          Human (Web UI)
     |                                         |
     |  create_experiment("token_swap")        |
     |  run_step("setup")                      |  sees step running, live stdout
     |  run_step("generate")                   |  sees progress bar, GPU stats
     |  get_results("token_swap")              |  clicks "View Output" -> charts, images
     |                                         |
     v                                         v
   Structured JSON                    Interactive Plotly charts
   Metrics, tensors                   Canvas dashboards, images
   Machine-readable                   Human-readable
```

## Quick Start

```bash
pip install git+https://github.com/JacobWLMS/research-lab.git

cd your-project
research-lab init
research-lab server start
```

## Features

### Pipeline Execution
Experiments are pipelines of named steps with dependencies. Steps share a persistent IPython kernel -- variables from step 1 are available in step 2.

```bash
research-lab experiments create my_experiment
research-lab experiments run my_experiment
```

### LabContext API
Every step has access to `ctx` for structured output:

```python
# Metrics (JSON for AI)
ctx.log_metrics(epoch=10, loss=0.05, accuracy=0.94)

# Progress bar (renders in web UI)
ctx.progress(3, 15, message="seed 3/15 done")

# GPU memory tracking
ctx.gpu_snapshot("before_training")

# Artifacts (raw tensors for other steps)
ctx.save_artifact("model", state_dict, format="safetensors")
weights = ctx.load_artifact("model")  # auto-detects format

# Visual output (interactive charts for the human)
canvas = ctx.create_canvas("Results")
canvas.add_chart(plotly_figure, title="Loss Curve")
canvas.add_metrics({"accuracy": 0.94, "f1": 0.938})
canvas.add_text("Model converged after 42 epochs.")
canvas.add_image(pil_image, title="Generated Sample")
```

### Three Interfaces

| Interface | For | How |
|-----------|-----|-----|
| **CLI** | AI + Human | `research-lab exec "code"` -- JSON output by default |
| **MCP Server** | AI (Claude Code) | Native tool calls: `exec`, `run_step`, `get_results`, `inspect_namespace` |
| **Web UI** | Human | Vue 3 + Tailwind, light/dark mode, real-time WebSocket updates |

### Web UI Highlights
- Master-detail layout with experiment list and pipeline visualization
- **Live stdout streaming** during step execution via WebSocket
- **Pipeline bar** with step nodes showing status, timing, and preview images
- **Full-screen output viewer** with interactive Plotly charts, metrics, images, text
- Light/dark mode (Gruvbox theme), zoom controls, keyboard shortcuts
- GPU stats with VRAM color indicator (green/yellow/red)
- Toast notifications for step completion, connection status
- Responsive design with collapsible sidebar

### Smart Serialization
Large tensors and arrays are summarized, not dumped raw:
- `torch.Tensor [1, 16, 128, 128]` &rarr; shape, dtype, mean/std/min/max, per-channel stats
- `pandas.DataFrame` &rarr; `.describe()` + shape + dtypes
- `PIL.Image` &rarr; dimensions + mode + base64 thumbnail

### Compute Backends
- **Local**: IPython kernel on your machine
- **RunPod**: Install on pod, expose via Cloudflare tunnel, connect MCP via `RESEARCH_LAB_URL`

## Architecture

```
CLI (Click) ──┐
MCP (FastMCP) ─┤──→ ResearchLabClient ──→ FastAPI Server ──→ IPython Kernel
Web UI (Vue)  ─┘        (httpx)           (REST + WebSocket)  (jupyter_client/ZMQ)
```

All three interfaces share the same client library. The server owns the kernel, stores results as git-friendly JSON, and broadcasts events via WebSocket.

## Documentation

| Document | Description |
|----------|-------------|
| **[API Reference](docs/API.md)** | 18 REST endpoints + WebSocket protocol (16 event types) |
| **[CLI Reference](docs/CLI.md)** | 12 commands with usage, options, and examples |
| **[MCP Reference](docs/MCP.md)** | 8 tools, setup, auto-start, troubleshooting |
| **[LabContext (ctx) API](docs/CTX_API.md)** | 10 ctx methods + 5 Canvas methods |
| **[Architecture](docs/ARCHITECTURE.md)** | Component diagrams, data flow, persistence model |
| **[Deployment Guide](docs/DEPLOYMENT.md)** | Local dev, RunPod, frontend, MCP configuration |
| **[AI Agent Instructions](CLAUDE.md)** | Quick reference for AI coding assistants |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Server** | Python 3.11+, FastAPI, uvicorn |
| **Kernel** | jupyter_client, IPython, ZMQ |
| **Frontend** | Vue 3, TypeScript, Vite, Tailwind CSS 4 |
| **Charts** | Plotly.js (interactive), matplotlib/PIL (static) |
| **CLI** | Click |
| **MCP** | FastMCP (stdio transport) |
| **Storage** | File-based JSON (git-friendly, no database) |

## Development

```bash
git clone https://github.com/JacobWLMS/research-lab.git
cd research-lab

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest  # 17 tests

# Frontend
cd frontend && npm install && npm run dev
```

## License

MIT
