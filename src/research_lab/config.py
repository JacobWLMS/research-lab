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
    """Read the server lockfile. Returns None if not found."""
    root = project_dir or find_project_root()
    if root is None:
        return None
    lockfile = root / ".research-lab" / "server.lock"
    if not lockfile.exists():
        return None
    try:
        return json.loads(lockfile.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def remove_lockfile(settings: Settings) -> None:
    """Remove the server lockfile on shutdown."""
    try:
        settings.lockfile_path.unlink(missing_ok=True)
    except OSError:
        pass
