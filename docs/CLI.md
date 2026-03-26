# CLI Reference

```
research-lab [--pretty] <command> [args...]
```

All commands output JSON by default (machine-readable). Use `--pretty` for indented, human-readable JSON.

The CLI communicates with a running server via HTTP. It discovers the server through the lockfile at `.research-lab/server.lock`.

---

## Global Options

| Option | Description |
|--------|-------------|
| `--pretty` | Pretty-print JSON output (indented) |
| `--help` | Show help for any command |

---

## Commands

### init

Initialize a research-lab project in the current directory.

```bash
research-lab init
```

Creates the `.research-lab/` directory structure:

```
.research-lab/
  experiments/
  logs/
  .gitignore       # Ignores server.lock and logs/
```

**Output:**

```json
{"status": "initialized", "project_dir": "/home/user/my-project", "lab_dir": "/home/user/my-project/.research-lab"}
```

---

### server start

Start the FastAPI server.

```bash
research-lab server start [--host HOST] [--port PORT] [--project-dir DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8470` | Bind port |
| `--project-dir` | Current directory | Project root |

**Example:**

```bash
research-lab server start --port 9000
research-lab server start --host 0.0.0.0 --port 8470 --project-dir /workspace
```

The server writes a lockfile to `.research-lab/server.lock` for client discovery.

---

### server stop

Stop the running server by sending SIGTERM to the process found in the lockfile.

```bash
research-lab server stop
```

**Output:**

```json
{"status": "stopped", "pid": 12345}
```

---

### exec

Execute Python code in the persistent IPython kernel.

```bash
research-lab exec "CODE"
```

**Example:**

```bash
research-lab exec "import torch; print(torch.cuda.is_available())"
research-lab exec "x = 42; print(x ** 2)"
```

**Output:**

```json
{"success": true, "stdout": "True\n", "stderr": "", "error": null, "images": [], "result": null}
```

---

### status

Show server, kernel, and GPU status.

```bash
research-lab status
```

**Output:**

```json
{
  "server_running": true,
  "kernel_status": "idle",
  "gpu": {"name": "NVIDIA RTX 4090", "utilization_pct": 12.0, "memory_used_gb": 4.1, "memory_total_gb": 24.0, "temperature_c": 55.0},
  "active_tasks": [],
  "current_experiment": null
}
```

---

### experiments list

List all experiments.

```bash
research-lab experiments list
```

**Output:**

```json
[
  {"id": "train-gpt2-a1b2c3", "name": "Train GPT-2", "created_at": "2025-01-15T10:30:00Z", "steps": [...]}
]
```

---

### experiments create

Create a new experiment.

```bash
research-lab experiments create "NAME"
```

**Example:**

```bash
research-lab experiments create "Train LoRA adapter"
```

**Output:**

```json
{"id": "train-lora-adapter-f3e8a1", "name": "Train LoRA adapter", "created_at": "...", "steps": []}
```

---

### experiments run

Run an experiment (all steps) or a specific step.

```bash
research-lab experiments run EXPERIMENT_ID [--step STEP_NAME]
```

**Examples:**

```bash
# Run the full pipeline
research-lab experiments run train-lora-adapter-f3e8a1

# Run a single step
research-lab experiments run train-lora-adapter-f3e8a1 --step train
```

Progress is printed to stderr as each step completes:

```
Running train-lora-adapter-f3e8a1...
  * setup: completed (2.10s)
  * train: completed (45.32s)
  * evaluate: completed (8.17s)
Done.
```

JSON results are printed to stdout.

---

### results

Read structured results as JSON.

```bash
research-lab results [EXPERIMENT_ID] [STEP_NAME]
```

| Arguments | Behavior |
|-----------|----------|
| (none) | List all experiments |
| `EXPERIMENT_ID` | All step results for that experiment |
| `EXPERIMENT_ID STEP_NAME` | Result for a specific step |

**Examples:**

```bash
# All results for an experiment
research-lab results train-lora-adapter-f3e8a1

# Single step result
research-lab results train-lora-adapter-f3e8a1 train
```

---

### inspect

Inspect the kernel namespace for a running experiment.

```bash
research-lab inspect EXPERIMENT_ID
```

**Output:**

```json
{
  "model": {"type": "GPT2Model", "repr": "GPT2Model(...)", "shape": null},
  "loss_history": {"type": "list", "repr": "[0.5, 0.3, 0.1]", "len": 3},
  "data": {"type": "Tensor", "repr": "tensor(...)", "shape": "torch.Size([1000, 128])"}
}
```

---

### tail

Stream live output from a running step via WebSocket.

```bash
research-lab tail EXPERIMENT_ID STEP_NAME
```

Requires the `websockets` package (`pip install websockets`).

Connects to the server's WebSocket, filters for the specified experiment/step, and streams:
- stdout to stdout
- stderr to stderr
- progress updates to stderr
- Exits when `step_completed` is received

Press Ctrl+C to disconnect.

**Example:**

```bash
research-lab tail train-lora-adapter-f3e8a1 train
```

```
Connecting to ws://127.0.0.1:8470/api/ws ...
Streaming output for train-lora-adapter-f3e8a1/train (Ctrl+C to stop)
Epoch 1/10, loss=0.532
Epoch 2/10, loss=0.421
[progress] 2/10 - epoch 2/10 done

Step completed: completed
```

---

### upload

Upload (copy) a file to the compute target.

```bash
research-lab upload LOCAL_PATH REMOTE_PATH
```

**Example:**

```bash
research-lab upload ./data.csv /workspace/data.csv
```

---

### download

Download (copy) a file from the compute target.

```bash
research-lab download REMOTE_PATH LOCAL_PATH
```

**Example:**

```bash
research-lab download /workspace/model.pt ./model.pt
```

---

### mcp-server (hidden)

Start the MCP server with stdio transport. Used internally by Claude Code.

```bash
research-lab mcp-server
```

This command is hidden from `--help` output. See [MCP.md](MCP.md) for configuration details.

---

## Environment Variables

All settings use the `RESEARCH_LAB_` prefix and can be set as environment variables or in a `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEARCH_LAB_HOST` | `127.0.0.1` | Server bind address |
| `RESEARCH_LAB_PORT` | `8470` | Server bind port |
| `RESEARCH_LAB_PROJECT_DIR` | Current directory | Project root path |
| `RESEARCH_LAB_LOG_LEVEL` | `info` | Log level (`debug`, `info`, `warning`, `error`) |
| `RESEARCH_LAB_CORS_ORIGINS` | `["*"]` | Allowed CORS origins |
| `RESEARCH_LAB_IMAGE_MAX_BYTES` | `100000` | Max base64 image size for MCP responses |
| `RESEARCH_LAB_URL` | (none) | Override server URL for client (e.g., remote tunnel) |
| `RESEARCHLAB_STATIC_DIR` | (none) | Override frontend static files directory |

### Server Discovery

The CLI and MCP client discover the server by searching for `.research-lab/server.lock` in this order:

1. Explicit `project_dir` parameter
2. Walk up from the current directory looking for `.research-lab/`
3. Home directory (`~/.research-lab/server.lock`)
4. `RESEARCH_LAB_PROJECT_DIR` environment variable
5. `~/Documents/GitHub/research-lab`
6. `/root`

The `RESEARCH_LAB_URL` environment variable bypasses lockfile discovery entirely, pointing directly at a remote server.
