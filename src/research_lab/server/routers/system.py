"""System endpoints: health, status, GPU info, exec, upload, download."""

from __future__ import annotations

import shutil
import subprocess

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from research_lab.schemas import ExecResult, GpuInfo, ImageOutput, KernelStatus, StatusResponse

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status", response_model=StatusResponse)
async def status(request: Request) -> StatusResponse:
    sessions = request.app.state.sessions
    gpu = _get_gpu_info()

    # Determine kernel status
    if sessions.kernel_count == 0:
        kernel_status = KernelStatus.not_connected
    else:
        # Check the ad-hoc kernel first, then any experiment kernel
        alive = await sessions.is_alive()
        kernel_status = KernelStatus.idle if alive else KernelStatus.dead

    return StatusResponse(
        server_running=True,
        kernel_status=kernel_status,
        gpu=gpu,
        active_tasks=sessions.active_experiments(),
    )


# ---------------------------------------------------------------------------
# Ad-hoc exec
# ---------------------------------------------------------------------------

class ExecRequest(BaseModel):
    code: str


@router.post("/exec", response_model=ExecResult)
async def exec_code(body: ExecRequest, request: Request) -> ExecResult:
    """Execute ad-hoc Python code in the kernel."""
    sessions = request.app.state.sessions
    kernel = await sessions.get_or_create()

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    images: list[ImageOutput] = []
    error_text: str | None = None
    result_text: str | None = None

    async for chunk in kernel.execute(body.code):
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

    return ExecResult(
        success=error_text is None,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
        error=error_text,
        images=images,
        result=result_text,
    )


# ---------------------------------------------------------------------------
# File transfer
# ---------------------------------------------------------------------------

class TransferRequest(BaseModel):
    local: str
    remote: str


@router.post("/upload")
async def upload_file(body: TransferRequest, request: Request) -> dict[str, str]:
    """Upload (copy) a file. For local backend this is a simple copy."""
    import shutil as sh
    from pathlib import Path

    src = Path(body.local)
    dst = Path(body.remote)
    if not src.exists():
        raise HTTPException(404, f"Source file not found: {body.local}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    sh.copy2(str(src), str(dst))
    return {"status": "uploaded", "local": body.local, "remote": body.remote}


@router.post("/download")
async def download_file(body: TransferRequest, request: Request) -> dict[str, str]:
    """Download (copy) a file. For local backend this is a simple copy."""
    import shutil as sh
    from pathlib import Path

    src = Path(body.remote)
    dst = Path(body.local)
    if not src.exists():
        raise HTTPException(404, f"Source file not found: {body.remote}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    sh.copy2(str(src), str(dst))
    return {"status": "downloaded", "remote": body.remote, "local": body.local}


def _get_gpu_info() -> GpuInfo | None:
    """Try to read GPU info via nvidia-smi."""
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            return None
        parts = out.stdout.strip().split(", ")
        if len(parts) < 5:
            return None
        return GpuInfo(
            name=parts[0],
            utilization_pct=float(parts[1]),
            memory_used_gb=float(parts[2]) / 1024,
            memory_total_gb=float(parts[3]) / 1024,
            temperature_c=float(parts[4]),
        )
    except Exception:
        return None
