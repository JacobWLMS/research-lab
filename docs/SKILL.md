---
name: research-lab
description: Use when running ML experiments via the research-lab platform — creating experiments, defining pipeline steps, executing code on local or RunPod GPU kernels, reading structured results, and building visual canvas reports. Triggers on mentions of research-lab, experiments, pipelines, steps, ctx API, or canvas reports.
---

# Running ML Experiments with research-lab

## Overview

End-to-end workflow for managing ML experiments through research-lab, an AI-first experiment management platform. Experiments are pipelines of named steps executed in a persistent IPython kernel. The AI drives execution via CLI or MCP tools and reads structured JSON results; the human monitors progress and views AI-composed dashboard canvases in the web UI.

**Project location:** `~/Documents/GitHub/research-lab`

## When to Use

- Running ML experiments via research-lab (not Jupyter/Colab directly)
- When the user mentions research-lab, experiments, pipelines, steps
- Creating or managing experiment pipelines with named steps
- Connecting to RunPod or local GPU for experiment execution
- Building visual canvas reports with Plotly charts and metrics
- Any workflow involving the `ctx` API inside step code

## Setup Sequence

### 1. Initialize a project

```bash
research-lab init
```

Creates a `.research-lab/` directory in the current working directory with experiment storage, gitignore, and config.

### 2. Start the server

```bash
research-lab server start
# Options: --host 127.0.0.1 --port 8470 --project-dir /path
```

Starts the FastAPI server that manages the kernel, experiments, and WebSocket streaming. Stop with `research-lab server stop`.

### 3. Configure as MCP server in Claude Code

Add to your Claude Code MCP settings:

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

This exposes all research-lab operations as MCP tools over stdio transport.

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `exec` | Execute Python code (pass experiment_id to use experiment's kernel) |
| `run_experiment` | Run all steps in dependency order (skips completed steps) |
| `run_step` | Run a single step (auto-runs pending dependencies) |
| `get_status` | Get server status: kernel state, GPU info, active tasks |
| `get_results` | Get structured JSON results for an experiment or step |
| `list_experiments` | List all experiments in the project |
| `create_experiment` | Create a new experiment (name, compute_backend) |
| `add_step` | Add a step with name, title, description, code, depends_on |
| `inspect_namespace` | List kernel variables with types and shapes |

**IMPORTANT: Every step MUST have a title and description.**
When adding steps, always provide:
- `name`: Technical ID (no spaces, used in code/API)
- `title`: Human-readable title (shown in pipeline bar and step cards)
- `description`: What this step does (shown below the title in the UI)

Example:
```
add_step(
    experiment_id="...",
    name="extract_embeddings",
    title="Extract Token Embeddings",
    description="Run prompts through Qwen3 text encoder and collect hidden state embeddings for each celebrity name token.",
    code="...",
    depends_on=["setup"]
)
```

## CLI Commands

```
research-lab init                                    # Initialize project
research-lab server start                            # Start FastAPI server
research-lab server stop                             # Stop server
research-lab exec "python code"                      # Execute code in kernel
research-lab status                                  # Kernel state, GPU, running tasks
research-lab results [experiment] [step]              # Read structured results as JSON
research-lab experiments list                         # List all experiments
research-lab experiments create <name>                # Create new experiment
research-lab experiments run <name>                   # Run full pipeline
research-lab experiments run <name> --step <step>     # Run specific step
research-lab upload <local> <remote>                  # Upload file to compute target
research-lab download <remote> <local>                # Download file from compute target
research-lab mcp-server                              # Start MCP server (stdio)
```

All CLI output is JSON by default. Use `--pretty` for human-readable formatting.

---

## RESEARCH METHODOLOGY (MANDATORY)

These rules are non-negotiable. They exist because previous experiments produced valuable findings that were nearly lost due to insufficient documentation, premature conclusions, and inadequate sample sizes.

### The Research Cycle

Every experiment follows this cycle. Do not skip steps.

```
HYPOTHESISE → PREDICT → DESIGN → IMPLEMENT → OBSERVE → INTERPRET → UPDATE → DECIDE
```

1. **HYPOTHESISE** — State what you believe and why
2. **PREDICT** — Write down what you expect to see if the hypothesis is correct AND incorrect, BEFORE running anything
3. **DESIGN** — Define the method, controls, sample size, and success criteria
4. **IMPLEMENT** — Write and run the code
5. **OBSERVE** — Record raw results without interpretation
6. **INTERPRET** — Explain what the results mean
7. **UPDATE** — Update state_of_affairs.md with new understanding
8. **DECIDE** — Pivot, pursue, or park this direction

### Documentation Gates

You MUST NOT proceed to the next experiment until:
- [ ] The current experiment's README.md is complete with all sections
- [ ] All numerical results are saved via `ctx.save_result()` or `ctx.log_metrics()`
- [ ] All plots are saved via `ctx.create_canvas()` and also to disk as PNG
- [ ] The master_log.md is updated with this experiment's cycle
- [ ] The state_of_affairs.md is updated if findings change our understanding
- [ ] All changes are committed and pushed to the remote repository

### Experiment README Template

Every experiment README.md MUST contain these sections. The first four MUST be written BEFORE running the experiment:

```markdown
# Experiment N: [Title]

## Date & Hardware
## Hypothesis
## Predictions
What we expect if hypothesis is correct:
What we expect if hypothesis is incorrect:
## Method
## Success Criteria (specific numbers)
## Controls

--- BELOW COMPLETED AFTER RUNNING ---

## Raw Results
## Plots
## Interpretation
## Surprises / Serendipity
## Conclusions
## Impact on State of Affairs
## Next Steps
```

### Sample Size Requirements

- **Minimum 50 seeds** for any statistical claim about identity clustering, separability, or transfer
- **Minimum 10 identities** for any claim about identity-general behaviour
- Use `--quick` mode (5 seeds) ONLY for verifying the pipeline works, NEVER for drawing conclusions
- If an experiment used insufficient samples, flag it explicitly: "N=6, PRELIMINARY, requires validation"
- NEVER describe preliminary results as confirmed findings

### Anti-Confirmation-Bias Rules

These rules exist because previous experiments showed a pattern of confirming expected results rather than testing them:

1. **Architecture-specific conclusions stay architecture-specific.** Findings on SDXL do NOT transfer to Z-Image without testing. Findings on Z-Image Turbo do NOT transfer to Z-Image Base. State which model produced each finding.

2. **When visual evidence contradicts numerical analysis, investigate the discrepancy.** Do not pick whichever supports your current narrative. Run additional tests to resolve the conflict.

3. **Write predictions BEFORE running.** If you find yourself writing predictions that match your results, you wrote them after. Be honest.

4. **Negative results are first-class findings.** Document them with the same rigour as positive results. They narrow the search space and prevent future wasted effort.

5. **Surprising results are the most valuable.** If a result surprises you, spend MORE time investigating it, not less. The Z-Image channel specialisation finding (0.64-0.88 sensitivity) was nearly dismissed because it didn't match the SDXL narrative.

6. **Check your sample size before concluding.** A finding based on 6 images is a preliminary signal, not a conclusion. Say so explicitly.

### Data Persistence Rules

ALL results must flow through the ctx API. Do not write raw files unless also saving through ctx.

```python
# CORRECT — results are structured and accessible
ctx.save_result("silhouette_scores", scores_dict)
ctx.log_metrics(mean_silhouette=0.40, best_pooling="mean", n_samples=500)

# ALSO CORRECT — save to disk AND through ctx for redundancy
df.to_csv("results/scores.csv")
ctx.save_result("scores_csv_path", "results/scores.csv")

# WRONG — data only exists in a local file that may not be committed
df.to_csv("results/scores.csv")
# No ctx.save_result, no ctx.log_metrics
```

Large reusable data (embedding databases, model weights, cached tensors) MUST be saved as artifacts:

```python
ctx.save_artifact("celebrity_db", celebrity_database, format="pt")
```

### Git Discipline

After every completed experiment:
```bash
git add -A
git commit -m "exp[N]: [title] — [one-line result summary]"
git push origin main
```

Do not batch multiple experiments into a single commit. Each experiment gets its own commit with a descriptive message that includes the key finding.

---

## Core Workflow

### Creating Experiments

```bash
# Via CLI
research-lab experiments create my_experiment

# Via MCP tool
create_experiment(name="my_experiment", compute_backend="local")

# Via API
POST /api/experiments  {"name": "my_experiment"}
```

### Adding Steps

Steps are named code blocks in a pipeline. Each step contains Python code and optional dependencies on other steps.

```
POST /api/experiments/{id}/steps
{
  "name": "train",
  "title": "Train Classifier",
  "description": "Train a linear probe on the extracted embeddings with identity labels.",
  "code": "model = train_model(data)\nctx.log_metrics(loss=final_loss)",
  "depends_on": ["preprocess"]
}
```

Steps with `depends_on` run after their dependencies. Independent steps can be run individually.

### Running Experiments

```bash
# Run full pipeline (respects dependency order, halts on failure)
research-lab experiments run my_experiment

# Run single step
research-lab experiments run my_experiment --step train

# Via MCP
run_experiment(experiment_id="my_experiment")
run_step(experiment_id="my_experiment", step_name="train")
```

### Reading Results

```bash
# All results for an experiment
research-lab results my_experiment

# Results for a specific step
research-lab results my_experiment train

# Via MCP
get_results(experiment_id="my_experiment")
get_results(experiment_id="my_experiment", step_name="train")
```

Results are structured JSON containing: metrics (key-value), stdout, stderr, images (base64), structured_data (auto-serialized variables), and canvas data.

### Checking Status

```bash
research-lab status
# Via MCP
get_status()
```

Returns: server_running, kernel_status (idle/busy/dead/not_connected), GPU info (name, utilization, memory, temperature), active_tasks, current_experiment.

## The ctx API (LabContext)

Every step's code runs in a persistent IPython kernel with a pre-injected `ctx` object. The ctx API has two layers.

### Data Layer (structured results for AI consumption)

```python
ctx.log_metrics(**kwargs)
```
Log key-value metrics. Values are merged into a flat dict, appended to JSONL, and available via `get_results`. Use for every numerical result — scores, counts, timings, sample sizes.

```python
ctx.save_result(name, value)
```
Save structured data by name. Use for JSON-serializable summaries (confusion matrices, score tables, configuration dicts). Always include the sample size and model name in saved results.

```python
ctx.save_artifact(name, data, format="pt")
```
Save raw bytes to the `artifacts/` directory. Use for tensors, model weights, embedding databases, and large arrays that other steps need. Supported formats: `"pt"` (torch.save), `"npy"` (numpy). Artifacts are `.gitignore`d by default.

```python
ctx.log(message)
```
Print a log message to stdout (streams to the Live tab in the web UI). Use for progress updates during long operations.

```python
ctx.checkpoint()
```
Snapshot all current results and namespace state. Use as a safety checkpoint in long-running steps — if the kernel dies, results up to the last checkpoint are preserved.

### Canvas Layer (visual reports for the human)

```python
canvas = ctx.create_canvas("Results")
```
Create a named canvas tab. Each step can have multiple canvases. Returns a canvas object. ALWAYS create at least one canvas per experiment step — the human needs to see what's happening.

```python
canvas.add_chart(plotly_fig, title="Loss Curve")
```
Add an interactive Plotly chart. Prefer Plotly over matplotlib for any chart the human needs to interact with (zoom, hover, pan).

```python
canvas.add_metrics({"accuracy": 0.94, "f1": 0.938, "n_samples": 500})
```
Add a metrics summary. Always include sample size in metrics so the human can assess statistical validity at a glance.

```python
canvas.add_text("Model converged at epoch 42.")
```
Add a markdown text block for analysis, interpretation, or notes. Use this to explain what the results mean, not just what they are.

```python
canvas.add_image(matplotlib_fig_or_pil_image, title="Custom Plot")
```
Add a static image. Use for matplotlib figures, generated sample images, heatmaps.

```python
canvas.flush()
```
Push current canvas state to the frontend immediately. Use during long-running steps (e.g., multi-seed generation, database building) to show incremental results. Without flush, canvases are delivered after step completion.

## Canvas Best Practices

Every experiment should produce a canvas that tells a complete story:

```python
canvas = ctx.create_canvas("Experiment Summary")

# 1. What we tested
canvas.add_text("## Hypothesis\nIdentity is linearly separable in Qwen3 embedding space.")

# 2. Key metrics with sample sizes
canvas.add_metrics({
    "silhouette_mean_pooled": 0.40,
    "silhouette_cls": 0.00,
    "n_celebrities": 100,
    "n_prompts_per_celebrity": 5,
    "total_samples": 500
})

# 3. Visual evidence
canvas.add_chart(silhouette_by_method_fig, title="Silhouette Score by Pooling Method")
canvas.add_chart(tsne_scatter_fig, title="t-SNE of Embeddings (coloured by identity)")

# 4. Interpretation
canvas.add_text("## Interpretation\nMean pooling shows strong identity clustering...")

# 5. Sample images if applicable
for img, label in sample_results[:6]:
    canvas.add_image(img, title=label)
```

## Best Practices

### Experiment Design
- **Always use `ctx.log_metrics()` for every numerical result** so results are structured and accessible, not buried in stdout.
- **Create canvases with `ctx.create_canvas()`** for every step that produces results. The AI reads JSON; the human sees the dashboard.
- **Use `ctx.save_artifact()` for reusable data** (embedding databases, model weights, cached tensors) that later steps need.
- **Use `ctx.save_result()` for summaries** that the AI needs to analyse (score tables, configuration, findings).
- **Use `canvas.flush()` during long operations** so the human can monitor progress. Flush after each major sub-result (each seed, each celebrity, each configuration).
- **Use `ctx.checkpoint()` before risky operations** and in long-running loops. If the kernel dies, results up to the checkpoint survive.

### Kernel and Steps
- **Persistent kernel namespace:** variables from step 1 are available in step 2. No need to re-import or reload data between steps.
- **Dependency ordering:** steps with `depends_on` run in order. Pipeline halts on failure.
- **Pilot first:** run a quick test with minimal parameters before committing to a long run. Use a `--quick` flag pattern in your code.

### Data Integrity
- **Always include model name, sample size, and configuration in saved results.** A score of 0.40 is meaningless without knowing it came from SDXL with 500 samples.
- **Save both raw data and summaries.** Raw data as artifacts, summaries via `ctx.save_result()`.
- **Never overwrite previous results.** Use run numbers or timestamps. The ctx API handles this automatically with JSONL append.

## Key Differences from Colab Workflow

| Colab | research-lab |
|-------|--------------|
| `!git pull` to sync code | Code lives in step definitions, no repo sync needed |
| `mcp__ide__executeCode` | `research-lab exec` or MCP `exec` / `run_step` tools |
| Subprocess execution per cell | Persistent kernel namespace across all steps |
| Manual CSV reading for results | Structured JSON results via `ctx` API |
| No visual dashboard | Canvas system for AI-composed visual reports |
| Ephemeral VM disk (save to Drive) | File-based persistence in `.research-lab/` (git-friendly) |

## Common Patterns

### Building a reusable database across steps

```python
# Step 1: Build celebrity database
celebrity_db = {}
canvas = ctx.create_canvas("Celebrity Database")
for i, name in enumerate(celebrity_names):
    embedding = extract_embedding(name)
    celebrity_db[name] = {"embedding": embedding, "arcface": arcface_vec}
    ctx.log_metrics(celebrities_processed=i+1, total=len(celebrity_names))
    if (i + 1) % 10 == 0:
        canvas.add_text(f"Processed {i+1}/{len(celebrity_names)}")
        canvas.flush()
        ctx.checkpoint()

ctx.save_artifact("celebrity_db", celebrity_db, format="pt")
canvas.add_metrics({"total_celebrities": len(celebrity_db)})
ctx.save_result("celebrity_db_summary", {
    "count": len(celebrity_db),
    "names": list(celebrity_db.keys()),
    "model": "z-image-turbo",
    "text_encoder": "qwen3-4b"
})

# Step 2: Analysis (depends_on: ["build_db"])
# celebrity_db is still in kernel namespace from step 1
scores = analyse_clustering(celebrity_db)
```

### Multi-configuration sweep with incremental canvas

```python
canvas = ctx.create_canvas("Pooling Strategy Comparison")
all_results = {}

for pooling in ["mean", "cls", "name_tokens", "non_name_tokens"]:
    for n_dims in [2, 5, 10, 20]:
        score = compute_silhouette(embeddings, labels, pooling, n_dims)
        all_results[f"{pooling}_{n_dims}d"] = score
        ctx.log_metrics(**{f"silhouette_{pooling}_{n_dims}d": score})

    canvas.add_text(f"### {pooling} pooling complete")
    canvas.flush()

# Summary chart
fig = make_heatmap(all_results)
canvas.add_chart(fig, title="Silhouette Scores: Pooling × Dimensions")
ctx.save_result("pooling_comparison", all_results)
```

### Proper experiment documentation in code

```python
# Document the experiment configuration at the start of every step
ctx.save_result("experiment_config", {
    "model": "Tongyi-MAI/Z-Image-Turbo",
    "text_encoder": "Qwen3-4B",
    "n_celebrities": 100,
    "n_prompts_per_celebrity": 5,
    "seeds": list(range(50)),
    "resolution": "512x512",
    "num_inference_steps": 9,
    "guidance_scale": 0.0,
    "gpu": "Ada 6000 48GB",
    "dtype": "bfloat16",
    "date": "2026-03-27"
})
```

## Experiment Storage

Experiments are stored as plain files in `.research-lab/experiments/{id}/`:

```
.research-lab/experiments/{experiment_id}/
  experiment.json         # Metadata + pipeline definition
  results/
    {step_name}.json      # Latest StepResult
    {step_name}.jsonl      # Incremental metrics log
    {step_name}_001.json   # Historical run
  artifacts/              # Large outputs (models, datasets) — gitignored
  code/                   # Step code snapshots
```

All JSON, all git-friendly. Artifacts (`.pt`, `.bin`, `.h5`) are `.gitignore`d by default.

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| CLI returns connection error | Server not running | `research-lab server start` |
| MCP tools not found | MCP server not configured | Add to Claude Code MCP settings |
| Step fails silently | Error in user code | Check `stderr` and `error` fields in result JSON |
| Variables missing in step 2 | Kernel restarted between steps | Re-run earlier steps or restart full pipeline |
| Canvas not showing in UI | No `create_canvas()` call | Add canvas creation to step code |
| Stale results | Reading old run | Check `run_number` in result JSON |
| Results lost between sessions | Not saved via ctx API | Always use `ctx.save_result()` and `ctx.save_artifact()` |
| Findings not reproducible | Configuration not recorded | Always save experiment config as first result |
| Premature conclusions | Insufficient sample size | Check N before interpreting. Minimum 50 for statistical claims |
