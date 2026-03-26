# Architecture

## Component Diagram

```
                          +------------------+
                          |    Web UI (Vue)   |
                          | Port 5173 (dev)   |
                          +--------+---------+
                                   |
                                   | HTTP + WebSocket
                                   |
+-------------+   HTTP    +--------v---------+   ZMQ/IOPub   +------------------+
| CLI (Click) +---------->|  FastAPI Server   +-------------->| IPython Kernel   |
+-------------+           |  Port 8470        |               | (jupyter_client) |
                          |                   |               |                  |
+-------------+   HTTP    |  - REST API       |               | - Persistent     |
| MCP Server  +---------->|  - WebSocket      |               | - One per        |
| (FastMCP)   |           |  - Static files   |               |   experiment     |
+-------------+           +--------+----------+               | - Shared ad-hoc  |
      ^                            |                          +------------------+
      |                            |
   stdio                  +--------v----------+
      |                   |  ExperimentStore   |
+-----+-------+           |  (File-based JSON) |
| Claude Code |           +-------------------+
| / AI Agent  |           |  .research-lab/    |
+-------------+           |    experiments/    |
                          |    logs/           |
                          |    server.lock     |
                          +-------------------+
```

---

## Data Flow

### 1. Code Submission

Code enters the system through three interfaces, all converging on the same FastAPI server:

```
CLI command          -->  ResearchLabClient (httpx)  -->  POST /api/...
MCP tool call        -->  ResearchLabClient (httpx)  -->  POST /api/...
Web UI action        -->  fetch() / WebSocket        -->  POST /api/... or WS message
```

### 2. Experiment Execution

When a pipeline or step is triggered:

```
POST /api/experiments/{id}/run
  |
  v
asyncio.create_task(_run_pipeline_background)
  |
  v
PipelineRunner.run_pipeline()
  |
  +---> topological_sort(steps)        # Resolve dependency order
  |
  +---> For each step in order:
        |
        +---> Inject LabContext (ctx)   # Python code injected into kernel
        |     into kernel namespace
        |
        +---> kernel.execute(step.code) # Send to IPython via ZMQ
        |
        +---> Stream OutputChunks:      # IOPub messages -> OutputChunk objects
        |     stdout, stderr, images,
        |     errors, display_data
        |
        +---> Broadcast via WebSocket   # Real-time to all connected clients
        |
        +---> Extract ctx._metrics      # Pull structured data from kernel
        |     Extract ctx._results
        |     Extract ctx._canvases
        |     Extract ctx._gpu_snapshots
        |
        +---> Persist StepResult        # Write JSON to disk
              Persist canvases
              Persist code snapshot
```

### 3. Result Retrieval

```
AI agent: get_results(experiment_id) --> GET /api/experiments/{id}/results
  |
  v
ExperimentStore.get_all_results()  -->  Read JSON files from disk
  |
  v
JSON response with metrics, structured data, canvases
  |
  v
MCP server: cap oversized images --> Return to AI agent
```

---

## File Structure

```
research-lab/
  src/research_lab/
    __init__.py
    schemas.py              # Pydantic models (single data contract)
    config.py               # Settings, project detection, lockfile
    context.py              # Server-side LabContext (canonical types)
    client.py               # Async HTTP client (httpx)
    cli/
      __init__.py           # Click group with --pretty flag
      commands.py           # All CLI command implementations
    server/
      app.py                # FastAPI application factory + lifespan
      ws.py                 # WebSocket handler + ConnectionManager
      routers/
        system.py           # /api/health, /api/status, /api/exec
        experiments.py      # /api/experiments CRUD + run pipeline
        steps.py            # /api/experiments/{id}/steps CRUD + run/stop
        compute.py          # /api/compute connect/status/disconnect
    pipeline/
      runner.py             # PipelineRunner, topological sort, ctx injection
      store.py              # ExperimentStore (file-based JSON persistence)
      serializer.py         # Smart serialization (tensor/array/df summaries)
    engine/
      base.py               # KernelBackend protocol (abstract interface)
      jupyter.py            # JupyterKernel (jupyter_client + ZMQ)
      session.py            # SessionManager (one kernel per experiment)
    mcp/
      server.py             # FastMCP server with all tools
    compute/
      local.py              # LocalBackend implementation
  frontend/                 # Vue 3 + TypeScript + Vite + Tailwind
  tests/
  pyproject.toml
  CLAUDE.md                 # AI agent instructions
```

---

## Persistence Model

All data is stored as files within the `.research-lab/` directory:

```
.research-lab/
  server.lock                           # Server discovery (host, port, pid, url)
  logs/
  experiments/
    {experiment-id}/
      experiment.json                   # Experiment metadata + step definitions
      results/
        {step_name}.json                # Latest StepResult for each step
        {step_name}_001.json            # Historical run #1
        {step_name}_002.json            # Historical run #2
        {step_name}_canvases.json       # Canvas data for each step
      artifacts/
        model.pt                        # PyTorch artifacts
        embeddings.npy                  # NumPy artifacts
        config.json                     # JSON artifacts
        weights.safetensors             # Safetensors artifacts
      code/
        {step_name}.py                  # Code snapshot for each step
```

### Key Design Decisions

- **JSON-based:** All metadata and results are human-readable JSON. Git-friendly for tracking experiment history.
- **File-per-step results:** Each step's latest result is at `{step_name}.json`. Historical results are kept with `_NNN` suffixes.
- **Artifacts separate from results:** Large binary artifacts (models, tensors) live in `artifacts/`, not in JSON.
- **Code snapshots:** The exact code that ran is saved in `code/`, enabling reproducibility.
- **Run numbers are 1-indexed** and auto-increment based on existing historical files.

### Lockfile

The server lockfile at `.research-lab/server.lock` enables client discovery:

```json
{
  "host": "127.0.0.1",
  "port": 8470,
  "pid": 12345,
  "url": "http://127.0.0.1:8470"
}
```

Clients verify the PID is alive before using a lockfile. Stale lockfiles (dead PID) are ignored.

---

## WebSocket Event Flow

```
Client connects to /api/ws
  |
  +---> Server accepts, adds to ConnectionManager
  |
  +---> GPU stats loop starts (every 5s, broadcasts gpu_stats)
  |
  v
Server broadcasts events as they happen:
  |
  +-- experiment_created    (on POST /api/experiments)
  +-- experiment_deleted    (on DELETE /api/experiments/{id})
  +-- step_added            (on POST /api/experiments/{id}/steps)
  +-- step_started          (on pipeline/step run begin)
  +-- stdout / stderr       (during execution, per OutputChunk)
  +-- error                 (on kernel error)
  +-- execute_result        (last expression result)
  +-- display_data          (matplotlib plots, etc.)
  +-- progress              (from ctx.progress() calls)
  +-- canvas_update         (canvas data extracted after step)
  +-- step_completed        (on step finish, with status + duration)
  +-- pipeline_completed    (all steps done)
  +-- gpu_stats             (periodic, every 5 seconds)
  |
Client can send:
  +-- interrupt             (sends SIGINT to kernel)
  +-- exec                  (ad-hoc code execution, results stream back)
```

All messages are JSON objects with a `type` field. Most execution-related messages include `experiment_id` and `step_name` for filtering.

---

## Compute Backend Abstraction

The kernel execution is abstracted behind the `KernelBackend` protocol:

```python
class KernelBackend(Protocol):
    async def execute(self, code: str) -> AsyncIterator[OutputChunk]: ...
    async def interrupt(self) -> None: ...
    async def restart(self) -> None: ...
    async def is_alive(self) -> bool: ...
    async def shutdown(self) -> None: ...
```

### Current Implementation

**JupyterKernel** -- Uses `jupyter_client.AsyncKernelManager` to manage an IPython kernel process. Communication happens over ZMQ (IOPub channel). The kernel:

- Starts with `%matplotlib inline` enabled for automatic image capture
- Parses IOPub messages (stream, execute_result, display_data, error, status) into `OutputChunk` objects
- Supports interrupt (SIGINT) and restart operations
- Configurable message timeout (default 300s per IOPub message)

### Session Management

**SessionManager** maps experiment IDs to kernel instances:

- One kernel per experiment (isolated namespaces)
- One shared ad-hoc kernel for `exec` operations (key: `__adhoc__`)
- Kernels are created on-demand and persist until server shutdown
- All kernels are shut down cleanly on server stop

### LabContext Injection

Before each step executes, the `PipelineRunner` injects Python source code into the kernel that defines the `_LabContext` and `_LabCanvas` classes and creates a `ctx` instance. This is pure Python -- no imports from the research-lab package are needed in the kernel.

After execution, the runner extracts data from the kernel namespace:
- `ctx._metrics` -- via JSON serialization
- `ctx._results` -- via key enumeration + repr
- `ctx._canvases` -- via `to_dict()` serialization
- `ctx._gpu_snapshots` -- via JSON serialization
