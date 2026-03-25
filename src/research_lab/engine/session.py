"""Session manager: maps experiment_id to kernel instance and handles lifecycle."""

from __future__ import annotations

import logging

from research_lab.engine.jupyter import JupyterKernel

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages one kernel per experiment (or a shared ad-hoc kernel)."""

    ADHOC_KEY = "__adhoc__"

    def __init__(self) -> None:
        self._kernels: dict[str, JupyterKernel] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_create(self, experiment_id: str | None = None) -> JupyterKernel:
        """Return an existing kernel for *experiment_id*, or create one.

        If *experiment_id* is None, a shared ad-hoc kernel is used.
        """
        key = experiment_id or self.ADHOC_KEY
        if key not in self._kernels:
            kernel = JupyterKernel()
            await kernel.start()
            self._kernels[key] = kernel
            logger.info("Started kernel for %s", key)
        return self._kernels[key]

    async def get(self, experiment_id: str | None = None) -> JupyterKernel | None:
        """Return the kernel for *experiment_id* without creating one."""
        key = experiment_id or self.ADHOC_KEY
        return self._kernels.get(key)

    async def shutdown(self, experiment_id: str | None = None) -> None:
        """Shut down a specific kernel."""
        key = experiment_id or self.ADHOC_KEY
        kernel = self._kernels.pop(key, None)
        if kernel is not None:
            await kernel.shutdown()
            logger.info("Shut down kernel for %s", key)

    async def shutdown_all(self) -> None:
        """Shut down every managed kernel (called on server shutdown)."""
        keys = list(self._kernels.keys())
        for key in keys:
            kernel = self._kernels.pop(key, None)
            if kernel is not None:
                try:
                    await kernel.shutdown()
                except Exception:
                    logger.exception("Error shutting down kernel %s", key)
        logger.info("All kernels shut down")

    async def is_alive(self, experiment_id: str | None = None) -> bool:
        """Check if the kernel for *experiment_id* is alive."""
        key = experiment_id or self.ADHOC_KEY
        kernel = self._kernels.get(key)
        if kernel is None:
            return False
        return await kernel.is_alive()

    def active_experiments(self) -> list[str]:
        """Return experiment IDs with active kernels."""
        return [k for k in self._kernels if k != self.ADHOC_KEY]

    @property
    def kernel_count(self) -> int:
        return len(self._kernels)
