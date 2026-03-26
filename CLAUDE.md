# research-lab — AI Agent Instructions

## What This Is

An ML experiment management platform. You (the AI) drive experiments via MCP tools or CLI commands. The human monitors via a web UI.

## MCP Tools Available

When the `research-lab` MCP server is configured, you have these tools:

- `exec(code)` — Execute Python code in a persistent IPython kernel. Returns stdout, stderr, images, result.
- `create_experiment(name)` — Create a new experiment.
- `list_experiments()` — List all experiments.
- `run_experiment(experiment_id)` — Run all steps in dependency order.
- `run_step(experiment_id, step_name)` — Run a single step.
- `get_results(experiment_id, step_name?)` — Get structured JSON results.
- `get_status()` — Server status, kernel state, GPU info.
- `inspect_namespace(experiment_id)` — Inspect kernel variables (types, shapes, reprs).

## CLI Alternative

If MCP tools aren't available, use the CLI via Bash:

```bash
research-lab exec "print('hello')"
research-lab experiments create my_experiment
research-lab experiments list
research-lab experiments run <experiment_id>
research-lab experiments run <experiment_id> --step <step_name>
research-lab results <experiment_id> [step_name]
research-lab status
research-lab inspect <experiment_id>              # inspect kernel namespace
research-lab tail <experiment_id> <step_name>     # stream live step output
```

All CLI output is JSON by default.

## Writing Step Code

Steps run in a persistent IPython kernel. Variables from step 1 are available in step 2. Every step has a `ctx` object:

```python
# Log metrics (structured JSON, available via get_results)
ctx.log_metrics(epoch=10, loss=0.05, accuracy=0.94)

# Save structured data
ctx.save_result("confusion_matrix", {"tp": 42, "fp": 3})

# Save raw artifacts (tensors, models, numpy arrays, safetensors, JSON)
ctx.save_artifact("model", model.state_dict(), format="pt")
ctx.save_artifact("weights", state_dict, format="safetensors")
ctx.save_artifact("embeddings", np_array, format="npy")
ctx.save_artifact("config", {"lr": 1e-4}, format="json")

# Load artifacts saved by previous steps
weights = ctx.load_artifact("model")       # auto-detects format from extension
config = ctx.load_artifact("config")       # returns dict for .json

# Report progress (broadcasts to WebSocket, renders in UI)
for i in range(num_seeds):
    # ... do work ...
    ctx.progress(i + 1, num_seeds, message=f"seed {i+1}/{num_seeds} done")

# Take GPU memory snapshots (logged to metrics)
ctx.gpu_snapshot("before_training")
# ... training loop ...
ctx.gpu_snapshot("after_training")

# Print to stdout (streamed to UI and captured in results)
print(f"Training epoch {epoch}...")

# Create visual canvas reports (rendered in the web UI for the human)
canvas = ctx.create_canvas("Results")
canvas.add_chart(plotly_figure, title="Loss Curve")     # Plotly figure
canvas.add_metrics({"accuracy": 0.94, "f1": 0.938})     # Key-value chips
canvas.add_text("Model converged after 42 epochs.")      # Markdown text
canvas.add_image(matplotlib_fig, title="Confusion Matrix") # Matplotlib figure
canvas.add_image(pil_image, title="Generated Sample")     # PIL Image
```

## Step Timeout / Watchdog

Steps support configurable timeouts via their `config` dict:

```python
# Hard timeout: step is interrupted after 600 seconds
step.config = {"timeout_seconds": 600}

# Watchdog: warn if no output for 120 seconds (default 300s)
step.config = {"watchdog_seconds": 120}
```

## Important Notes

- The server must be running (`research-lab server start`) before using MCP tools or CLI
- The kernel is persistent — imports and variables survive across step executions
- All results are JSON — you read structured data, the human sees visual dashboards
- Use `ctx.log_metrics()` in training loops so you can track progress via `get_results`
- Use `ctx.progress()` in long loops (e.g., seed sweeps) to broadcast real-time progress
- Use `ctx.gpu_snapshot()` before/after heavy operations to track VRAM usage
- Use `ctx.save_artifact()` / `ctx.load_artifact()` for tensor/model persistence between steps
- Use `ctx.create_canvas()` to build visual reports the human can review in the web UI
- Use `inspect_namespace` (MCP tool or `research-lab inspect`) to check kernel variable state
- Use `research-lab tail <experiment_id> <step_name>` to stream live output from a running step
