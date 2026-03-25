"""Local compute backend: starts ipykernel via jupyter_client."""

from __future__ import annotations

import logging
import shutil
from typing import Any

from research_lab.compute.base import ComputeBackend, KernelConnection
from research_lab.engine.jupyter import JupyterKernel

logger = logging.getLogger(__name__)


class LocalBackend:
    """Starts an IPython kernel as a local subprocess.

    Upload/download are no-ops since we share the filesystem.
    """

    def __init__(self) -> None:
        self._kernel: JupyterKernel | None = None

    async def provision(self, config: dict[str, Any] | None = None) -> KernelConnection:
        """Start a local IPython kernel."""
        self._kernel = JupyterKernel()
        await self._kernel.start()
        logger.info("Local kernel provisioned")
        return KernelConnection(
            transport="tcp",
            ip="127.0.0.1",
            extra={"backend": "local"},
        )

    async def teardown(self) -> None:
        """Shut down the local kernel."""
        if self._kernel is not None:
            await self._kernel.shutdown()
            self._kernel = None
            logger.info("Local kernel torn down")

    async def health_check(self) -> bool:
        """Check if the local kernel is alive."""
        if self._kernel is None:
            return False
        return await self._kernel.is_alive()

    async def upload(self, local: str, remote: str) -> None:
        """Copy a local file to another local path (same filesystem)."""
        shutil.copy2(local, remote)

    async def download(self, remote: str, local: str) -> None:
        """Copy a local file to another local path (same filesystem)."""
        shutil.copy2(remote, local)

    @property
    def kernel(self) -> JupyterKernel | None:
        return self._kernel


# Verify protocol compliance at import time
_: ComputeBackend = LocalBackend()  # type: ignore[assignment]
