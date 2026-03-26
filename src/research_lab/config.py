"""Settings, project detection, and server lockfile management."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Application settings loaded from env vars / .env file."""

    model_config = {"env_prefix": "RESEARCH_LAB_", "env_file": ".env", "extra": "ignore"}

    host: str = "127.0.0.1"
    port: int = 8470
    project_dir: Path = Field(default_factory=lambda: Path.cwd())
    log_level: str = "info"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    @property
    def lab_dir(self) -> Path:
        """Return the .research-lab directory inside the project."""
        return self.project_dir / ".research-lab"

    @property
    def experiments_dir(self) -> Path:
        return self.lab_dir / "experiments"

    @property
    def lockfile_path(self) -> Path:
        return self.lab_dir / "server.lock"


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for a .research-lab directory."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / ".research-lab").is_dir():
            return directory
    return None


def ensure_lab_dir(project_dir: Path) -> Path:
    """Create the .research-lab structure if it doesn't exist."""
    lab = project_dir / ".research-lab"
    lab.mkdir(parents=True, exist_ok=True)
    (lab / "experiments").mkdir(exist_ok=True)
    (lab / "logs").mkdir(exist_ok=True)
    return lab


# ---------------------------------------------------------------------------
# Server lockfile
# ---------------------------------------------------------------------------

def write_lockfile(settings: Settings) -> None:
    """Write the server lockfile so clients can discover us."""
    ensure_lab_dir(settings.project_dir)
    data = {
        "host": settings.host,
        "port": settings.port,
        "pid": os.getpid(),
        "url": f"http://{settings.host}:{settings.port}",
    }
    settings.lockfile_path.write_text(json.dumps(data, indent=2))


def read_lockfile(project_dir: Path | None = None) -> dict | None:
    """Read the server lockfile. Searches multiple locations:
    1. Explicit project_dir
    2. Walk up from CWD
    3. Home directory
    4. RESEARCH_LAB_PROJECT_DIR env var
    5. The research-lab package install directory
    """
    candidates: list[Path] = []

    if project_dir:
        candidates.append(project_dir)

    # Walk up from CWD
    root = find_project_root()
    if root:
        candidates.append(root)

    # Home directory
    candidates.append(Path.home())

    # Env var
    env_dir = os.environ.get("RESEARCH_LAB_PROJECT_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    # Common locations
    candidates.append(Path.home() / "Documents" / "GitHub" / "research-lab")
    candidates.append(Path("/root"))

    for candidate in candidates:
        lockfile = candidate / ".research-lab" / "server.lock"
        if lockfile.exists():
            try:
                data = json.loads(lockfile.read_text())
                # Verify the server is actually running by checking PID
                pid = data.get("pid")
                if pid and _pid_alive(pid):
                    return data
            except (json.JSONDecodeError, OSError):
                continue
    return None


def _pid_alive(pid: int) -> bool:
    """Check if a process is alive (works on Linux/macOS)."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def remove_lockfile(settings: Settings) -> None:
    """Remove the server lockfile on shutdown."""
    try:
        settings.lockfile_path.unlink(missing_ok=True)
    except OSError:
        pass
