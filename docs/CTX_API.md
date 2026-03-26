# LabContext (ctx) API Reference

Every step in a research-lab pipeline has access to a `ctx` object -- an instance of `LabContext` that is injected into the kernel namespace before the step code runs.

The `ctx` object provides methods for structured data output (metrics, results, artifacts), progress reporting, GPU monitoring, and visual canvas reports.

---

## Data Layer

### ctx.log_metrics(**kwargs)

Record key-value metrics for this step. Metrics are extracted after execution and included in the `StepResult.metrics` field.

```python
ctx.log_metrics(epoch=10, loss=0.05, accuracy=0.94, lr=1e-4)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `**kwargs` | `float \| int \| str` | Metric key-value pairs |

Metrics accumulate -- calling `log_metrics()` multiple times merges the values. Later calls overwrite earlier values for the same key.

```python
ctx.log_metrics(loss=0.5)
ctx.log_metrics(loss=0.3, accuracy=0.92)
# Final metrics: {"loss": 0.3, "accuracy": 0.92}
```

---

### ctx.save_result(name, value)

Save a named structured result. Results are extracted after execution and included in `StepResult.structured_data`.

```python
ctx.save_result("confusion_matrix", {"tp": 42, "fp": 3, "fn": 5, "tn": 50})
ctx.save_result("best_hyperparams", {"lr": 1e-4, "batch_size": 32, "epochs": 42})
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique name for this result |
| `value` | `Any` | Any Python object (truncated to 1000 chars in repr for JSON) |

---

### ctx.save_artifact(name, data, format="pt")

Save raw binary data to the experiment's artifacts directory.

```python
# PyTorch state dict
ctx.save_artifact("model", model.state_dict(), format="pt")

# Safetensors
ctx.save_artifact("weights", state_dict, format="safetensors")

# NumPy array
ctx.save_artifact("embeddings", np_array, format="npy")

# JSON
ctx.save_artifact("config", {"lr": 1e-4, "warmup": 100}, format="json")

# Raw bytes
ctx.save_artifact("output", raw_bytes, format="bin")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | - | Artifact name (no extension) |
| `data` | `Any` | - | Data to save |
| `format` | `str` | `"pt"` | Format: `"pt"`, `"safetensors"`, `"npy"`, `"json"`, or any extension |

**Supported formats:**

| Format | Library | Description |
|--------|---------|-------------|
| `pt` | `torch.save()` | PyTorch tensors, state dicts, any picklable object |
| `safetensors` | `safetensors.torch.save_file()` | Safe tensor format (dict of tensors) |
| `npy` | `numpy.save()` | NumPy arrays |
| `json` | `json.dump()` | JSON-serializable data |
| (other) | Raw write | Writes bytes (or `str(data).encode()`) |

Artifacts are stored at:
```
.research-lab/experiments/{experiment_id}/artifacts/{name}.{format}
```

Prints confirmation: `Artifact saved: .research-lab/experiments/.../artifacts/model.pt`

---

### ctx.load_artifact(name, format=None)

Load a previously saved artifact. Auto-detects format from the file extension.

```python
weights = ctx.load_artifact("model")       # Loads .pt file via torch.load()
config = ctx.load_artifact("config")       # Loads .json file, returns dict
embeddings = ctx.load_artifact("embeddings")  # Loads .npy file via numpy.load()
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | - | Artifact name (no extension) |
| `format` | `str \| None` | `None` | Not used; format is detected from file extension |

Searches the experiment's artifacts directory for any file matching `{name}.*`.

**Raises:** `FileNotFoundError` if no artifact with that name exists.

---

### ctx.log(msg)

Print a message to stdout. Equivalent to `print(msg)` but provided for semantic clarity.

```python
ctx.log("Starting training loop...")
ctx.log(f"Epoch {epoch}: loss={loss:.4f}")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `msg` | `str` | Message to print |

---

### ctx.checkpoint()

Snapshot the current state. Currently a no-op in the kernel (handled server-side for logging).

```python
ctx.checkpoint()  # Logs current metrics server-side
```

---

### ctx.progress(current, total, message="")

Report progress for long-running operations. Progress updates are broadcast via WebSocket and rendered in the web UI.

```python
for i in range(num_epochs):
    train_one_epoch()
    ctx.progress(i + 1, num_epochs, message=f"epoch {i+1}/{num_epochs}")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `current` | `int` | - | Current step number |
| `total` | `int` | - | Total number of steps |
| `message` | `str` | `""` | Optional descriptive message |

Progress is transmitted via a sentinel string in stdout (`__RL_PROGRESS__:`) that the pipeline runner intercepts and converts to a WebSocket `progress` event. The sentinel line is stripped from the captured stdout.

---

### ctx.gpu_snapshot(label="")

Take a GPU memory and utilization snapshot using `nvidia-smi`. Snapshots are appended to a list and included in `StepResult.metrics._gpu_snapshots`.

```python
ctx.gpu_snapshot("before_training")
# ... training code ...
ctx.gpu_snapshot("after_training")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | `str` | `""` | Descriptive label for this snapshot |

**Returns:** `dict | None` -- snapshot data, or `None` if `nvidia-smi` is unavailable.

**Snapshot fields:**

| Field | Type | Description |
|-------|------|-------------|
| `label` | `str` | The label passed in |
| `memory_used_mb` | `int` | GPU memory used (MB) |
| `memory_total_mb` | `int` | Total GPU memory (MB) |
| `memory_free_mb` | `int` | Free GPU memory (MB) |
| `gpu_util_pct` | `int` | GPU utilization percentage |

Prints a summary line: `GPU: 8192MB / 24576MB used (45% util) [before_training]`

---

## Canvas Layer

Canvases are visual reports composed of widgets (charts, metrics, text, images). They are rendered in the web UI's full-screen report viewer.

### ctx.create_canvas(name)

Create a named canvas tab.

```python
canvas = ctx.create_canvas("Training Results")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Canvas tab name |

**Returns:** `Canvas` object.

Multiple canvases can be created per step. Each appears as a separate tab in the UI.

---

### Canvas.add_chart(fig, title="")

Add a Plotly figure as an interactive chart widget.

```python
import plotly.express as px

fig = px.line(x=epochs, y=losses, title="Loss Curve")
canvas.add_chart(fig, title="Training Loss")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fig` | Plotly figure | - | Any Plotly figure object (must have `.to_json()`) |
| `title` | `str` | `""` | Widget title |

The figure is serialized via `fig.to_json()` and stored as Plotly JSON. If serialization fails, a text placeholder is added instead.

---

### Canvas.add_metrics(data)

Add a key-value metrics strip (rendered as chips/cards in the UI).

```python
canvas.add_metrics({
    "accuracy": 0.94,
    "f1_score": 0.938,
    "total_params": "124M",
    "training_time": "2h 15m"
})
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | `dict[str, float \| int \| str]` | Key-value pairs |

---

### Canvas.add_text(content)

Add a markdown text block.

```python
canvas.add_text("## Summary\n\nModel converged after **42 epochs** with final loss of 0.05.")
canvas.add_text(f"Best checkpoint at epoch {best_epoch}")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | `str` | Text content (supports markdown) |

---

### Canvas.add_image(fig_or_data, title="", mime="image/png")

Add a static image from a matplotlib figure or PIL Image.

```python
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.matshow(confusion_matrix)
canvas.add_image(fig, title="Confusion Matrix")

from PIL import Image
img = Image.open("generated.png")
canvas.add_image(img, title="Generated Sample")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fig_or_data` | matplotlib figure, PIL Image | - | Image source |
| `title` | `str` | `""` | Widget title |
| `mime` | `str` | `"image/png"` | MIME type |

**Supported input types:**

| Type | Detection | Serialization |
|------|-----------|---------------|
| PIL Image | Has `.save` and `.mode` attributes | `img.save(buf, format="PNG")` |
| Matplotlib figure | Has `.savefig` attribute | `fig.savefig(buf, format="png", bbox_inches="tight")` |

Images are base64-encoded and embedded in the canvas data.

---

### Canvas.flush()

No-op in the kernel. The server extracts canvas state after step execution completes.

```python
canvas.flush()  # Safe to call, does nothing in-kernel
```

Canvas data is automatically pulled from the kernel namespace after execution, so explicit flushing is not required.

---

## Complete Example

```python
import plotly.express as px
import matplotlib.pyplot as plt
import numpy as np

# Track metrics
ctx.gpu_snapshot("start")
losses = []

for epoch in range(50):
    loss = train_one_epoch(model, data)
    losses.append(loss)
    ctx.log_metrics(epoch=epoch, loss=loss, lr=scheduler.get_last_lr()[0])
    ctx.progress(epoch + 1, 50, message=f"loss={loss:.4f}")

ctx.gpu_snapshot("after_training")

# Save artifacts
ctx.save_artifact("model", model.state_dict(), format="pt")
ctx.save_artifact("config", {"epochs": 50, "lr": 1e-4}, format="json")

# Evaluate
accuracy = evaluate(model, test_data)
ctx.log_metrics(accuracy=accuracy)
ctx.save_result("test_metrics", {"accuracy": accuracy, "loss": losses[-1]})

# Build canvas report
canvas = ctx.create_canvas("Training Report")

fig = px.line(x=list(range(len(losses))), y=losses, title="Loss Curve")
canvas.add_chart(fig, title="Training Loss")

canvas.add_metrics({"accuracy": accuracy, "final_loss": losses[-1], "epochs": 50})

canvas.add_text(f"## Results\n\nModel achieved **{accuracy:.1%}** accuracy after 50 epochs.")

fig_cm, ax = plt.subplots(figsize=(8, 6))
ax.matshow(confusion_matrix)
canvas.add_image(fig_cm, title="Confusion Matrix")
plt.close(fig_cm)
```

---

## Serialization Behavior

When `ctx.save_result()` is used, values are extracted from the kernel after execution. The server retrieves each value's `repr()` truncated to 1000 characters.

For the MCP and REST API, the smart serializer (`pipeline/serializer.py`) converts large ML objects to JSON-safe summaries:

| Type | Serialized Form |
|------|----------------|
| `torch.Tensor` | `{"type": "tensor", "shape": [...], "dtype": "...", "device": "...", "stats": {"mean": ..., "std": ..., "min": ..., "max": ...}, "per_channel_mean": [...]}` |
| `numpy.ndarray` | `{"type": "ndarray", "shape": [...], "dtype": "...", "stats": {"mean": ..., "std": ..., "min": ..., "max": ...}}` |
| `pandas.DataFrame` | `{"type": "dataframe", "shape": [...], "columns": [...], "dtypes": {...}, "describe": {...}}` |
| `PIL.Image` | `{"type": "image", "size": [w, h], "mode": "RGB", "thumbnail_base64": "..."}` |
| JSON-native types | Passed through unchanged |
| Unknown objects | `{"type": "unknown", "repr": "..."}` (truncated to 500 chars) |

For tensors and arrays with 3+ dimensions, per-channel means are included if the channel dimension has 128 or fewer channels.

---

## Step Timeout and Watchdog Configuration

Steps support two timeout mechanisms via their `config` dict:

### timeout_seconds

Hard timeout. The step is interrupted after this many seconds.

```python
step.config = {"timeout_seconds": 600}  # 10-minute hard limit
```

When the timeout fires:
1. An error message is emitted: `"Step timed out after 600s"`
2. The kernel is interrupted (`SIGINT`)
3. The step status is set to `"failed"`

### watchdog_seconds

Soft warning for inactivity. If no output is produced for this many seconds, a warning is emitted to stderr.

```python
step.config = {"watchdog_seconds": 120}  # Warn after 2 minutes of silence
```

Default: 300 seconds (5 minutes). The warning is emitted once per step execution.

Both can be combined:

```python
step.config = {
    "timeout_seconds": 3600,    # Hard kill after 1 hour
    "watchdog_seconds": 300,    # Warn if silent for 5 minutes
}
```
