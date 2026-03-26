# REST API Reference

Base URL: `http://{host}:{port}` (default `http://127.0.0.1:8470`)

## Authentication

No authentication is required. The server binds to `127.0.0.1` by default for local-only access. For remote access, use a tunnel (e.g., Cloudflare Tunnel) and configure `RESEARCH_LAB_URL`.

---

## System Endpoints

### GET /api/health

Health check.

**Response:**

```json
{"status": "ok"}
```

---

### GET /api/status

Server status including kernel state, GPU info, and active tasks.

**Response Model:** `StatusResponse`

```json
{
  "server_running": true,
  "kernel_status": "idle",
  "gpu": {
    "name": "NVIDIA RTX 4090",
    "utilization_pct": 45.0,
    "memory_used_gb": 8.2,
    "memory_total_gb": 24.0,
    "temperature_c": 62.0
  },
  "active_tasks": ["my-experiment-a1b2c3"],
  "current_experiment": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `server_running` | `bool` | Always `true` when reachable |
| `kernel_status` | `"idle" \| "busy" \| "dead" \| "not_connected"` | Current kernel state |
| `gpu` | `GpuInfo \| null` | GPU info from `nvidia-smi`, or `null` if unavailable |
| `active_tasks` | `list[str]` | Experiment IDs with active kernels |
| `current_experiment` | `str \| null` | Currently running experiment |

---

### POST /api/exec

Execute ad-hoc Python code in the shared IPython kernel.

**Request Body:**

```json
{"code": "import torch; print(torch.cuda.is_available())"}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | `string` | Yes | Python code to execute |

**Response Model:** `ExecResult`

```json
{
  "success": true,
  "stdout": "True\n",
  "stderr": "",
  "error": null,
  "images": [],
  "result": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `true` if no error occurred |
| `stdout` | `string` | Captured stdout |
| `stderr` | `string` | Captured stderr |
| `error` | `string \| null` | Error message with traceback if failed |
| `images` | `list[ImageOutput]` | Base64-encoded images (matplotlib plots, etc.) |
| `result` | `string \| null` | `repr()` of the last expression |

---

## File Transfer Endpoints

### POST /api/upload

Copy a file from a local path to a remote (or another local) path.

**Request Body:**

```json
{"local": "/home/user/data.csv", "remote": "/workspace/data.csv"}
```

**Response:**

```json
{"status": "uploaded", "local": "/home/user/data.csv", "remote": "/workspace/data.csv"}
```

---

### POST /api/download

Copy a file from a remote path to a local path.

**Request Body:**

```json
{"remote": "/workspace/model.pt", "local": "/home/user/model.pt"}
```

**Response:**

```json
{"status": "downloaded", "remote": "/workspace/model.pt", "local": "/home/user/model.pt"}
```

---

## Compute Endpoints

### POST /api/compute/connect

Connect a compute backend and provision a kernel.

**Request Body:**

```json
{"backend": "local", "config": {}}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend` | `string` | `"local"` | Backend type (`"local"`) |
| `config` | `object` | `{}` | Backend-specific configuration |

**Response:**

```json
{
  "status": "connected",
  "backend": "local",
  "connection": {"transport": "tcp", "ip": "127.0.0.1"}
}
```

---

### GET /api/compute/status

Check the compute backend status.

**Response:**

```json
{
  "connected": true,
  "kernel_count": 2,
  "active_experiments": ["my-experiment-a1b2c3"]
}
```

---

### POST /api/compute/disconnect

Shut down all kernels and disconnect.

**Response:**

```json
{"status": "disconnected"}
```

---

## Experiment Endpoints

### GET /api/experiments

List all experiments, sorted by creation time (newest first).

**Response:** `list[Experiment]`

```json
[
  {
    "id": "train-gpt2-a1b2c3",
    "name": "Train GPT-2",
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T11:45:00Z",
    "compute_backend": "local",
    "steps": [
      {
        "name": "setup",
        "code": "import torch\n...",
        "depends_on": [],
        "config": {},
        "status": "completed"
      }
    ]
  }
]
```

---

### POST /api/experiments

Create a new experiment.

**Request Body:**

```json
{
  "name": "Train GPT-2",
  "compute_backend": "local",
  "steps": [
    {
      "name": "setup",
      "code": "import torch",
      "depends_on": [],
      "config": {}
    }
  ]
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `string` | Yes | - | Experiment name |
| `compute_backend` | `string` | No | `"local"` | Compute backend |
| `steps` | `list[Step]` | No | `[]` | Initial steps |

**Response:** `Experiment` (status 201)

The experiment ID is auto-generated as a URL-safe slug: `{name-slug}-{6-hex-chars}`.

---

### GET /api/experiments/{experiment_id}

Get a single experiment by ID.

**Response:** `Experiment`

**Errors:** 404 if not found.

---

### PUT /api/experiments/{experiment_id}

Update experiment metadata.

**Request Body:**

```json
{"name": "New Name", "compute_backend": "local"}
```

Both fields are optional.

**Response:** `Experiment`

---

### DELETE /api/experiments/{experiment_id}

Delete an experiment and all its data (results, artifacts, code).

**Response:**

```json
{"deleted": true}
```

Broadcasts `experiment_deleted` via WebSocket.

---

### POST /api/experiments/{experiment_id}/run

Run the full pipeline in the background. Steps execute in dependency order. Results stream via WebSocket.

**Response (immediate):**

```json
{"status": "started", "experiment_id": "train-gpt2-a1b2c3"}
```

The pipeline runs asynchronously. Monitor progress via WebSocket events (`step_started`, `step_completed`, `pipeline_completed`).

---

### GET /api/experiments/{experiment_id}/results

Get all step results for an experiment.

**Response:** `dict[step_name, StepResult]`

```json
{
  "setup": {
    "step_name": "setup",
    "run_number": 1,
    "status": "completed",
    "started_at": "2025-01-15T10:30:00Z",
    "completed_at": "2025-01-15T10:30:05Z",
    "execution_time_s": 4.832,
    "stdout": "Setup complete.\n",
    "stderr": "",
    "error": null,
    "images": [],
    "metrics": {"gpu_memory_mb": 2048},
    "structured_data": {},
    "canvases": []
  }
}
```

---

### GET /api/experiments/{experiment_id}/kernel/namespace

Inspect the kernel namespace for a running experiment.

**Response:** `dict[variable_name, info]`

```json
{
  "model": {
    "type": "GPT2Model",
    "repr": "GPT2Model(\n  (wte): Embedding(50257, 768)\n...",
    "shape": null,
    "len": null
  },
  "optimizer": {
    "type": "AdamW",
    "repr": "AdamW (\nParameter Group 0\n..."
  },
  "data": {
    "type": "Tensor",
    "repr": "tensor([[1, 2, 3], ...])",
    "shape": "torch.Size([1000, 128])"
  }
}
```

Excludes private variables (starting with `_`), built-ins, and the `ctx` object.

---

## Step Endpoints

All step endpoints are nested under `/api/experiments/{experiment_id}/steps`.

### POST /api/experiments/{experiment_id}/steps

Add a step to an experiment.

**Request Body:**

```json
{
  "name": "train",
  "code": "for epoch in range(10):\n    ...",
  "depends_on": ["setup"],
  "config": {"timeout_seconds": 600, "watchdog_seconds": 120}
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `string` | Yes | - | Unique step name |
| `code` | `string` | No | `""` | Python code to execute |
| `depends_on` | `list[string]` | No | `[]` | Steps that must complete first |
| `config` | `object` | No | `{}` | Step configuration (timeouts, etc.) |

**Response:** `Experiment` (status 201) -- the full experiment with the new step.

Broadcasts `step_added` via WebSocket.

---

### GET /api/experiments/{experiment_id}/steps/{step_name}

Get step details, latest result, and canvas data.

**Response:**

```json
{
  "step": {
    "name": "train",
    "code": "...",
    "depends_on": ["setup"],
    "config": {},
    "status": "completed"
  },
  "result": { "...StepResult..." },
  "canvases": [{ "canvas_name": "Results", "widgets": [...] }]
}
```

---

### PUT /api/experiments/{experiment_id}/steps/{step_name}

Update step fields.

**Request Body:**

```json
{"code": "updated code...", "depends_on": ["new_dep"], "config": {"timeout_seconds": 300}}
```

All fields are optional.

**Response:** `Experiment`

---

### DELETE /api/experiments/{experiment_id}/steps/{step_name}

Remove a step from the experiment.

**Response:** `Experiment`

---

### POST /api/experiments/{experiment_id}/steps/{step_name}/run

Run a single step in the background. Automatically runs pending dependencies first.

**Response (immediate):**

```json
{"status": "started", "experiment_id": "...", "step_name": "train"}
```

---

### POST /api/experiments/{experiment_id}/steps/{step_name}/stop

Interrupt the kernel running this step.

**Response:**

```json
{"status": "interrupted"}
```

---

## WebSocket Protocol

### Connection

```
ws://{host}:{port}/api/ws
```

The WebSocket connection is bidirectional. The server broadcasts events to all connected clients. Clients can send commands.

### Server -> Client Messages

| Type | Fields | Description |
|------|--------|-------------|
| `stdout` | `experiment_id`, `step_name`, `text` | Stdout output chunk |
| `stderr` | `experiment_id`, `step_name`, `text` | Stderr output chunk |
| `error` | `experiment_id`, `step_name`, `text` | Error with traceback |
| `execute_result` | `experiment_id`, `step_name`, `text`, `images?` | Last expression result |
| `display_data` | `experiment_id`, `step_name`, `text`, `images?` | Display output (plots) |
| `status` | `experiment_id`, `step_name`, `text` | Kernel status change |
| `step_started` | `experiment_id`, `step_name` | Step execution began |
| `step_completed` | `experiment_id`, `step_name`, `status`, `duration_s` | Step finished |
| `pipeline_completed` | `experiment_id`, `status?` | All steps done |
| `step_added` | `experiment_id`, `step_name`, `experiment` | Step was added |
| `experiment_created` | `experiment` | New experiment created |
| `experiment_deleted` | `experiment_id` | Experiment removed |
| `canvas_update` | `experiment_id`, `step_name`, `canvas_name`, `widgets` | Canvas data pushed |
| `progress` | `experiment_id`, `step_name`, `current`, `total`, `message` | Progress update |
| `gpu_stats` | `name`, `utilization_pct`, `memory_used_gb`, `memory_total_gb`, `temperature_c` | Periodic GPU stats (every 5s) |
| `interrupted` | `experiment_id`, `step_name` | Kernel was interrupted |
| `exec_result` | `success`, `stdout`, `stderr`, `error`, `images`, `result` | Ad-hoc exec result |

### Client -> Server Messages

| Type | Fields | Description |
|------|--------|-------------|
| `interrupt` | `experiment_id`, `step_name` | Interrupt a running step |
| `exec` | `code` | Execute ad-hoc code, results stream back via WebSocket |

**Example:**

```json
{"type": "interrupt", "experiment_id": "my-exp-abc123", "step_name": "train"}
```

```json
{"type": "exec", "code": "print('hello from websocket')"}
```

### Images in WebSocket Messages

Images are sent as base64-encoded strings:

```json
{
  "type": "display_data",
  "experiment_id": "...",
  "step_name": "...",
  "text": "",
  "images": [
    {
      "label": "display_png",
      "mime": "image/png",
      "data": "iVBORw0KGgo..."
    }
  ]
}
```

---

## Error Responses

All error responses follow the standard FastAPI format:

```json
{"detail": "Experiment 'missing-id' not found"}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request (unknown backend, invalid input) |
| 404 | Resource not found (experiment, step, kernel) |
| 500 | Internal server error (kernel error, serialization failure) |

---

## Data Models

### Experiment

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | URL-safe slug ID |
| `name` | `string` | Human-readable name |
| `created_at` | `datetime` | UTC creation time |
| `updated_at` | `datetime` | UTC last update time |
| `compute_backend` | `string` | Backend type (default `"local"`) |
| `steps` | `list[Step]` | Ordered pipeline steps |

### Step

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Unique name within the experiment |
| `code` | `string` | Python source code |
| `depends_on` | `list[string]` | Names of dependency steps |
| `config` | `object` | Step configuration (timeouts, etc.) |
| `status` | `"pending" \| "running" \| "completed" \| "failed"` | Current status |

### StepResult

| Field | Type | Description |
|-------|------|-------------|
| `step_name` | `string` | Step this result belongs to |
| `run_number` | `int` | Run number (1-indexed, increments on re-runs) |
| `status` | `"completed" \| "failed"` | Final status |
| `started_at` | `datetime` | UTC start time |
| `completed_at` | `datetime` | UTC completion time |
| `execution_time_s` | `float` | Wall-clock seconds |
| `stdout` | `string` | Full stdout |
| `stderr` | `string` | Full stderr |
| `error` | `string \| null` | Error text if failed |
| `images` | `list[ImageOutput]` | Captured images |
| `metrics` | `object` | Metrics from `ctx.log_metrics()` |
| `structured_data` | `object` | Data from `ctx.save_result()` |
| `canvases` | `list[CanvasState]` | Canvas reports |

### ImageOutput

| Field | Type | Description |
|-------|------|-------------|
| `label` | `string` | Descriptive label |
| `mime` | `string` | MIME type (default `"image/png"`) |
| `data` | `string` | Base64-encoded image data |
