"""Jupyter kernel wrapper using jupyter_client.AsyncKernelManager.

Parses ZMQ IOPub messages into OutputChunk objects.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from jupyter_client import AsyncKernelManager

from research_lab.schemas import ImageOutput, OutputChunk

logger = logging.getLogger(__name__)

# Message types we care about on IOPub
_STREAM = "stream"
_EXECUTE_RESULT = "execute_result"
_DISPLAY_DATA = "display_data"
_ERROR = "error"
_STATUS = "status"


class JupyterKernel:
    """Wraps an IPython kernel managed by jupyter_client.

    Speaks the Jupyter wire protocol over ZMQ and converts IOPub
    messages into structured OutputChunk objects.
    """

    def __init__(self, kernel_name: str = "python3") -> None:
        self._km = AsyncKernelManager(kernel_name=kernel_name)
        self._kc = None
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the kernel process and connect a client."""
        if self._started:
            return
        await self._km.start_kernel()
        self._kc = self._km.client()
        self._kc.start_channels()
        # Wait for kernel ready
        try:
            await asyncio.wait_for(self._kc.wait_for_ready(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning("Kernel did not become ready within 30 s")
        self._started = True
        # Enable matplotlib inline for automatic base64 PNG capture
        await self._silent_execute("%matplotlib inline")

    async def _silent_execute(self, code: str) -> None:
        """Execute code without collecting output (setup commands)."""
        if self._kc is None:
            return
        self._kc.execute(code, silent=True)
        # Drain messages briefly
        await asyncio.sleep(0.3)

    async def shutdown(self) -> None:
        """Shut down the kernel and close channels."""
        if self._kc is not None:
            self._kc.stop_channels()
            self._kc = None
        if self._km.has_kernel:
            await self._km.shutdown_kernel(now=True)
        self._started = False

    # ------------------------------------------------------------------
    # KernelBackend interface
    # ------------------------------------------------------------------

    async def execute(
        self, code: str, *, msg_timeout: float = 300
    ) -> AsyncIterator[OutputChunk]:
        """Execute *code* and yield OutputChunks from IOPub messages.

        *msg_timeout* controls how long to wait for each individual IOPub
        message (default 300 s).
        """
        if self._kc is None:
            raise RuntimeError("Kernel not started -- call start() first")

        msg_id = self._kc.execute(code)

        while True:
            try:
                msg = await asyncio.wait_for(
                    self._kc.get_iopub_msg(),
                    timeout=msg_timeout,
                )
            except asyncio.TimeoutError:
                yield OutputChunk(kind="error", text=f"Kernel message timeout ({msg_timeout} s)")
                return

            # Only process messages belonging to our execution
            parent_id = msg.get("parent_header", {}).get("msg_id")
            if parent_id != msg_id:
                continue

            msg_type = msg["msg_type"]
            content = msg["content"]

            if msg_type == _STATUS:
                state = content.get("execution_state", "")
                if state == "idle":
                    # Execution finished
                    return
                yield OutputChunk(kind="status", text=state)

            elif msg_type == _STREAM:
                name = content.get("name", "stdout")
                text = content.get("text", "")
                kind = "stdout" if name == "stdout" else "stderr"
                yield OutputChunk(kind=kind, text=text)

            elif msg_type == _EXECUTE_RESULT:
                data = content.get("data", {})
                images = _extract_images(data, "result")
                text = data.get("text/plain", "")
                yield OutputChunk(
                    kind="execute_result",
                    text=text,
                    data=data,
                    images=images,
                )

            elif msg_type == _DISPLAY_DATA:
                data = content.get("data", {})
                images = _extract_images(data, "display")
                text = data.get("text/plain", "")
                yield OutputChunk(
                    kind="display_data",
                    text=text,
                    data=data,
                    images=images,
                )

            elif msg_type == _ERROR:
                ename = content.get("ename", "Error")
                evalue = content.get("evalue", "")
                traceback_lines = content.get("traceback", [])
                tb_text = "\n".join(traceback_lines)
                yield OutputChunk(
                    kind="error",
                    text=f"{ename}: {evalue}\n{tb_text}",
                )

    async def interrupt(self) -> None:
        """Send an interrupt signal to the kernel."""
        if self._km.has_kernel:
            await self._km.interrupt_kernel()

    async def restart(self) -> None:
        """Restart the kernel, wiping all state."""
        if self._km.has_kernel:
            await self._km.restart_kernel(now=True)
            if self._kc is not None:
                try:
                    await asyncio.wait_for(self._kc.wait_for_ready(), timeout=30)
                except asyncio.TimeoutError:
                    logger.warning("Kernel did not become ready after restart")
            await self._silent_execute("%matplotlib inline")

    async def is_alive(self) -> bool:
        """Check if the kernel process is alive."""
        if not self._km.has_kernel:
            return False
        return await self._km.is_alive()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_images(data: dict, label_prefix: str) -> list[ImageOutput]:
    """Pull base64 image data from a Jupyter display_data/execute_result message."""
    images: list[ImageOutput] = []
    for mime in ("image/png", "image/jpeg", "image/svg+xml"):
        if mime in data:
            images.append(
                ImageOutput(
                    label=f"{label_prefix}_{mime.split('/')[-1]}",
                    mime=mime,
                    data=data[mime],
                )
            )
    return images
