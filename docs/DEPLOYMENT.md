# Deployment Guide

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the frontend)
- pip or uv

### Install

```bash
git clone https://github.com/JacobWLMS/research-lab.git
cd research-lab

# Create venv and install
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
pip install -e ".[dev]"

# Initialize the project
research-lab init

# Start the server
research-lab server start
```

The server starts at `http://127.0.0.1:8470` by default.

### Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server starts at `http://localhost:5173` with hot reload. It proxies API requests to the backend at port 8470.

### Frontend (Production Build)

```bash
cd frontend
npm run build
```

This produces a `frontend/dist/` directory. The FastAPI server automatically serves it as static files if it finds `dist/index.html`.

### Run Tests

```bash
pytest
```

---

## RunPod Deployment

For running on remote GPU machines (RunPod, Lambda Labs, etc.).

### 1. Install on the Remote Machine

```bash
pip install git+https://github.com/JacobWLMS/research-lab.git
```

### 2. Initialize and Start

```bash
# Create the project directory
mkdir -p /workspace/my-project
cd /workspace/my-project
research-lab init

# Start the server on all interfaces
research-lab server start --host 0.0.0.0 --port 8470
```

### 3. Cloudflare Tunnel (Recommended)

Set up a Cloudflare quick tunnel for secure external access without opening ports:

```bash
# Install cloudflared
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Start the tunnel
cloudflared tunnel --url http://localhost:8470
```

This prints a URL like `https://random-name.trycloudflare.com`. Use this as your `RESEARCH_LAB_URL`.

### 4. Connect from Local Machine

Set the tunnel URL so the CLI and MCP tools connect to the remote server:

```bash
export RESEARCH_LAB_URL=https://random-name.trycloudflare.com
research-lab status
```

### RunPod Start Script Example

A typical RunPod start script:

```bash
#!/bin/bash
pip install git+https://github.com/JacobWLMS/research-lab.git

cd /workspace
research-lab init

# Start server in background
research-lab server start --host 0.0.0.0 &

# Start tunnel
cloudflared tunnel --url http://localhost:8470
```

---

## Frontend Deployment

The FastAPI server can serve the frontend as static files. It searches these locations in order:

1. `RESEARCHLAB_STATIC_DIR` environment variable
2. `frontend/dist/` relative to the package install
3. `{project_dir}/research-lab-frontend/`
4. `/root/research-lab-frontend/`

### Option A: Build Alongside the Server

```bash
cd research-lab/frontend
npm run build
# The server auto-detects frontend/dist/ and serves it
```

### Option B: Deploy Pre-Built Frontend

```bash
# Copy build output to a known location
cp -r frontend/dist/ /root/research-lab-frontend/

# Or set the env var
export RESEARCHLAB_STATIC_DIR=/path/to/frontend/dist
```

### Option C: Separate Static Hosting

Build the frontend and deploy to any static host (Vercel, Netlify, S3). Configure the API URL in the frontend's environment.

---

## MCP Configuration for Claude Code

### Local Server

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

Place in `~/.claude/settings.json` (global) or `.mcp.json` (per-project).

### Remote Server

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

### With Virtual Environment

```json
{
  "mcpServers": {
    "research-lab": {
      "command": "/home/user/project/.venv/bin/research-lab",
      "args": ["mcp-server"]
    }
  }
}
```

---

## Environment Variables Reference

### Server Settings

All use the `RESEARCH_LAB_` prefix. Can also be set in a `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEARCH_LAB_HOST` | `127.0.0.1` | Server bind address |
| `RESEARCH_LAB_PORT` | `8470` | Server bind port |
| `RESEARCH_LAB_PROJECT_DIR` | CWD | Project root directory |
| `RESEARCH_LAB_LOG_LEVEL` | `info` | Logging level |
| `RESEARCH_LAB_CORS_ORIGINS` | `["*"]` | Allowed CORS origins (JSON array) |
| `RESEARCH_LAB_IMAGE_MAX_BYTES` | `100000` | Max image size for MCP responses |

### Client Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEARCH_LAB_URL` | (auto-discover) | Override server URL. Bypasses lockfile discovery. Use for remote servers. |

### Frontend Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEARCHLAB_STATIC_DIR` | (auto-detect) | Path to frontend build directory |

### Example .env File

```env
RESEARCH_LAB_HOST=0.0.0.0
RESEARCH_LAB_PORT=8470
RESEARCH_LAB_PROJECT_DIR=/workspace/my-project
RESEARCH_LAB_LOG_LEVEL=info
RESEARCH_LAB_IMAGE_MAX_BYTES=200000
```

---

## RESEARCH_LAB_URL for Remote Connections

The `RESEARCH_LAB_URL` environment variable is the primary mechanism for connecting to a remote research-lab server. When set, it completely bypasses the lockfile discovery mechanism.

### Use Cases

1. **Cloudflare Tunnel to RunPod:**
   ```bash
   export RESEARCH_LAB_URL=https://random-name.trycloudflare.com
   ```

2. **SSH port forward:**
   ```bash
   ssh -L 8470:localhost:8470 user@gpu-server
   export RESEARCH_LAB_URL=http://localhost:8470
   ```

3. **Direct IP (not recommended for production):**
   ```bash
   export RESEARCH_LAB_URL=http://192.168.1.100:8470
   ```

### Precedence

The client resolves the server URL in this order:

1. `RESEARCH_LAB_URL` environment variable (highest priority)
2. Lockfile discovery (walks directory tree)
3. Error: "Could not discover research-lab server"
