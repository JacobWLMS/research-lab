"""ComputeBackend Protocol -- abstraction for kernel provisioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class KernelConnection:
    """Information needed to connect to a provisioned kernel."""

    connection_file: str = ""
    transport: str = "tcp"
    ip: str = "127.0.0.1"
    ports: dict[str, int] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ComputeBackend(Protocol):
    """Async interface for provisioning and managing a compute target."""

    async def provision(self, config: dict[str, Any] | None = None) -> KernelConnection:
        """Provision a kernel and return connection info."""
        ...  # pragma: no cover

    async def teardown(self) -> None:
        """Tear down the compute resource."""
        ...  # pragma: no cover

    async def health_check(self) -> bool:
        """Return True if the compute target is healthy."""
        ...  # pragma: no cover

    async def upload(self, local: str, remote: str) -> None:
        """Upload a file to the compute target."""
        ...  # pragma: no cover

    async def download(self, remote: str, local: str) -> None:
        """Download a file from the compute target."""
        ...  # pragma: no cover
