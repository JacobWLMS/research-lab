"""KernelBackend Protocol -- the execution abstraction."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from research_lab.schemas import OutputChunk


@runtime_checkable
class KernelBackend(Protocol):
    """Async interface for executing code in a persistent kernel."""

    async def execute(self, code: str) -> AsyncIterator[OutputChunk]:
        """Execute *code* and yield OutputChunk objects as they arrive.

        Yields chunks of type stdout, stderr, execute_result,
        display_data (images), error, or status.
        """
        ...  # pragma: no cover

    async def interrupt(self) -> None:
        """Send SIGINT to the running kernel."""
        ...  # pragma: no cover

    async def restart(self) -> None:
        """Restart the kernel, clearing all state."""
        ...  # pragma: no cover

    async def is_alive(self) -> bool:
        """Return True if the kernel process is still running."""
        ...  # pragma: no cover

    async def shutdown(self) -> None:
        """Shut down the kernel permanently."""
        ...  # pragma: no cover
