# MCP Server Reference

The research-lab MCP server exposes experiment management tools to AI assistants via the [Model Context Protocol](https://modelcontextprotocol.io/) using stdio transport.

---

## Setup

### Claude Code (settings.json)

Add to `~/.claude/settings.json`:

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

### Per-Project (.mcp.json)

Add to your project root `.mcp.json`:

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

### With a Virtual Environment

If research-lab is installed in a venv:

```json
{
  "mcpServers": {
    "research-lab": {
      "command": "/path/to/venv/bin/research-lab",
      "args": ["mcp-server"]
    }
  }
}
```

### Remote Server (RunPod, etc.)

When connecting to a remote server through a tunnel, set the URL as an environment variable:

```json
{
  "mcpServers": {
    "research-lab": {
      "command": "research-lab",
      "args": ["mcp-server"],
      "env": {
        "RESEARCH_LAB_URL": "https://your-tunnel.trycloudflare.com"
      }
    }
  }
}
```

---

## Auto-Start Behavior

When the MCP server receives a tool call and cannot find a running research-lab server (no lockfile), it attempts to start one automatically:

1. Searches for a project root (directory containing `.research-lab/`)
2. Falls back to the home directory
3. Launches `uvicorn research_lab.server.app:create_app --factory` in the background
4. Waits 3 seconds for the server to start
5. Retries the lockfile lookup

If auto-start fails, tools return a connection error.

---

## Image Capping

MCP responses have limited token budgets. Large base64-encoded images can overwhelm the context window. The MCP server automatically caps oversized images:

- Images larger than `RESEARCH_LAB_IMAGE_MAX_BYTES` (default: 100,000 bytes / ~100KB) are replaced with: `[image too large for MCP response - view in web UI]`
- This applies to both `images` in step results and `image` widgets in canvases
- Adjust the threshold with the `RESEARCH_LAB_IMAGE_MAX_BYTES` environment variable
- Charts (Plotly JSON) are not affected -- they are always included as structured data

---

## Tools

### exec

Execute Python code in the persistent IPython kernel.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | `string` | Yes | Python code to execute |

**Returns:** `ExecResult` dict with `success`, `stdout`, `stderr`, `error`, `images`, `result`.

**Example:**

```
exec(code="import torch; print(torch.cuda.device_count())")
```

```json
{"success": true, "stdout": "1\n", "stderr": "", "error": null, "images": [], "result": null}
```

---

### create_experiment

Create a new experiment.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | `string` | Yes | - | Experiment name |
| `compute_backend` | `string` | No | `"local"` | Compute backend type |

**Returns:** `Experiment` dict with `id`, `name`, `created_at`, `steps`.

**Example:**

```
create_experiment(name="LoRA Fine-tune", compute_backend="local")
```

---

### list_experiments

List all experiments in the project.

**Parameters:** None.

**Returns:** List of `Experiment` dicts.

---

### run_experiment

Run all steps of an experiment in dependency order.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `experiment_id` | `string` | Yes | Experiment ID |

**Returns:** List of `StepResult` dicts.

The tool blocks until all steps complete or one fails (halting the pipeline).

---

### run_step

Run a single step within an experiment. Automatically runs pending dependencies first.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `experiment_id` | `string` | Yes | Experiment ID |
| `step_name` | `string` | Yes | Step name |

**Returns:** `StepResult` dict with `status`, `stdout`, `stderr`, `metrics`, `images`, `canvases`, etc.

---

### get_results

Get structured results for an experiment or a specific step.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `experiment_id` | `string` | Yes | Experiment ID |
| `step_name` | `string` | No | If provided, returns that step's result only |

**Returns:** Dict keyed by step name (all results) or a single step result dict.

---

### get_status

Get the current server status including kernel state, GPU info, and active tasks.

**Parameters:** None.

**Returns:** `StatusResponse` dict with `server_running`, `kernel_status`, `gpu`, `active_tasks`.

---

### inspect_namespace

Inspect the kernel namespace for a running experiment.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `experiment_id` | `string` | Yes | Experiment ID |

**Returns:** Dict mapping variable names to info objects:

```json
{
  "model": {"type": "GPT2Model", "repr": "GPT2Model(...)", "shape": null},
  "loss_history": {"type": "list", "repr": "[0.5, 0.3, 0.1]", "len": 3}
}
```

Each info object contains:

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | Python type name |
| `repr` | `string` | Truncated repr (max 200 chars) |
| `shape` | `string \| null` | Tensor/array shape if applicable |
| `len` | `int \| null` | Collection length if applicable |

---

## Troubleshooting

### "Could not discover research-lab server"

The MCP server cannot find a running research-lab server.

**Fixes:**
1. Start the server: `research-lab server start`
2. Check the lockfile exists: `cat .research-lab/server.lock`
3. For remote servers, set `RESEARCH_LAB_URL` in the MCP env config
4. Ensure you are in a directory that is (or is under) a research-lab project

### Stale lockfile

If the server crashed without cleaning up the lockfile, the MCP server will detect that the PID is no longer alive and ignore the stale lockfile.

To manually clean up: `rm .research-lab/server.lock`

### MCP server not found by Claude Code

1. Verify the command path: `which research-lab`
2. If installed in a venv, use the full path to the binary in your MCP config
3. Check Claude Code logs for MCP server startup errors
4. Try running `research-lab mcp-server` directly to verify it starts

### Images showing as placeholders

Images over `RESEARCH_LAB_IMAGE_MAX_BYTES` (default 100KB) are replaced with placeholder text. To see the full images:
- Open the web UI
- Increase the limit: set `RESEARCH_LAB_IMAGE_MAX_BYTES=500000` in your MCP config env

### Server auto-start not working

Auto-start requires:
- A `.research-lab/` directory somewhere in the parent directory chain (or home directory)
- `uvicorn` installed in the same Python environment
- The MCP server process has permission to spawn subprocesses
