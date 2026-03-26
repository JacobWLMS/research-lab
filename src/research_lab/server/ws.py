"""WebSocket handler: streams OutputChunks, canvas updates, GPU stats, and handles interrupts."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from research_lab.schemas import ExecResult, ImageOutput, OutputChunk
from research_lab.server.routers.system import _get_gpu_info

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Track active WebSocket connections and broadcast to them."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections = [c for c in self._connections if c is not ws]

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for conn in self._connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect(d)

    @property
    def count(self) -> int:
        return len(self._connections)


def _get_manager(ws: WebSocket) -> ConnectionManager:
    """Retrieve the shared ConnectionManager from app.state."""
    return ws.app.state.ws_manager


async def broadcast_chunk(
    mgr: ConnectionManager, experiment_id: str, step_name: str, chunk: OutputChunk
) -> None:
    """Broadcast an OutputChunk as a WebSocket message."""
    msg: dict = {
        "type": chunk.kind,
        "experiment_id": experiment_id,
        "step_name": step_name,
    }
    if chunk.kind in ("stdout", "stderr"):
        msg["text"] = chunk.text
    elif chunk.kind == "error":
        msg["text"] = chunk.text
    elif chunk.kind in ("execute_result", "display_data"):
        msg["text"] = chunk.text
        if chunk.images:
            msg["images"] = [img.model_dump() for img in chunk.images]
    elif chunk.kind == "status":
        msg["text"] = chunk.text
    await mgr.broadcast(msg)


async def broadcast_canvas_update(
    mgr: ConnectionManager,
    experiment_id: str, step_name: str, canvas_name: str, widgets: list[dict]
) -> None:
    """Broadcast a canvas update event."""
    await mgr.broadcast({
        "type": "canvas_update",
        "experiment_id": experiment_id,
        "step_name": step_name,
        "canvas_name": canvas_name,
        "widgets": widgets,
    })


async def broadcast_progress(
    mgr: ConnectionManager,
    experiment_id: str,
    step_name: str,
    current: int,
    total: int,
    message: str,
) -> None:
    """Broadcast a progress update event."""
    await mgr.broadcast({
        "type": "progress",
        "experiment_id": experiment_id,
        "step_name": step_name,
        "current": current,
        "total": total,
        "message": message,
    })


async def _gpu_stats_loop(mgr: ConnectionManager) -> None:
    """Periodically broadcast GPU stats to all connected clients."""
    while True:
        await asyncio.sleep(5)
        if mgr.count == 0:
            continue
        gpu = _get_gpu_info()
        if gpu is not None:
            await mgr.broadcast({
                "type": "gpu_stats",
                **gpu.model_dump(),
            })


@router.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    mgr = _get_manager(ws)
    await mgr.connect(ws)

    # Start GPU stats broadcast if not already running
    gpu_task = asyncio.create_task(_gpu_stats_loop(mgr))

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "interrupt":
                experiment_id = msg.get("experiment_id")
                step_name = msg.get("step_name")
                sessions = ws.app.state.sessions
                kernel = await sessions.get(experiment_id)
                if kernel is not None:
                    await kernel.interrupt()
                    await ws.send_json({
                        "type": "interrupted",
                        "experiment_id": experiment_id,
                        "step_name": step_name,
                    })

            elif msg_type == "exec":
                # Ad-hoc code execution via WebSocket
                code = msg.get("code", "")
                sessions = ws.app.state.sessions
                kernel = await sessions.get_or_create()
                stdout_parts: list[str] = []
                stderr_parts: list[str] = []
                images: list[ImageOutput] = []
                error_text: str | None = None
                result_text: str | None = None

                async for chunk in kernel.execute(code):
                    await broadcast_chunk(mgr, "__adhoc__", "__exec__", chunk)
                    if chunk.kind == "stdout":
                        stdout_parts.append(chunk.text)
                    elif chunk.kind == "stderr":
                        stderr_parts.append(chunk.text)
                    elif chunk.kind == "error":
                        error_text = chunk.text
                    elif chunk.kind == "execute_result":
                        result_text = chunk.text
                        images.extend(chunk.images)
                    elif chunk.kind == "display_data":
                        images.extend(chunk.images)

                exec_result = ExecResult(
                    success=error_text is None,
                    stdout="".join(stdout_parts),
                    stderr="".join(stderr_parts),
                    error=error_text,
                    images=images,
                    result=result_text,
                )
                await ws.send_json({
                    "type": "exec_result",
                    **exec_result.model_dump(),
                })

    except WebSocketDisconnect:
        pass
    finally:
        gpu_task.cancel()
        mgr.disconnect(ws)
