# research-lab

**AI-first experiment management platform**

Run experiments as pipelines of named steps. Get structured JSON for AI analysis. Get rich visual output for human review. Share the same kernel, same data, same results.

## Why research-lab?

| Without research-lab | With research-lab |
|---------------------|-------------------|
| Cobbled-together SSH + Jupyter | Single platform for AI + human |
| AI can't see plots | AI gets structured JSON metrics |
| Human can't see AI-executed code | Human sees live output + canvas dashboards |
| Scattered notebooks | Organized experiment pipelines |
| Results lost on kernel restart | Persistent JSON results, git-friendly |
| No GPU monitoring | Live VRAM tracking with OOM warnings |

## How It Works

```
AI (Claude Code)                          Human (Web UI)
     |                                         |
     |  create_experiment("my_exp")            |
     |  run_step("setup")                      |  sees step running, live stdout
     |  run_step("train")                      |  sees progress bar, GPU stats
     |  get_results("my_exp")                  |  clicks "View Output" -> charts
     |                                         |
     v                                         v
   Structured JSON                    Interactive Plotly charts
   Metrics, tensors                   Canvas dashboards, images
```

## Quick Links

- [Quick Start](quickstart.md) -- Get up and running in 2 minutes
- [CLI Reference](CLI.md) -- All commands and options
- [MCP Reference](MCP.md) -- Claude Code integration
- [LabContext API](CTX_API.md) -- The `ctx` object available in every step
- [Architecture](ARCHITECTURE.md) -- How it all fits together
