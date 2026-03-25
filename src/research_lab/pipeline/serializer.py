"""Smart serialization: convert large ML objects to JSON-safe summaries.

Detection order:
  torch.Tensor -> numpy.ndarray -> pandas.DataFrame -> PIL.Image
  -> json.dumps() -> str() fallback
"""

from __future__ import annotations

import base64
import io
import json
from typing import Any


def serialize_value(obj: Any) -> Any:
    """Convert *obj* to a JSON-safe summary representation.

    Returns a dict with type info and summary statistics for ML types,
    or a string fallback for unknown objects.
    """
    # -- torch.Tensor ------------------------------------------------
    try:
        import torch

        if isinstance(obj, torch.Tensor):
            return _serialize_tensor(obj)
    except ImportError:
        pass

    # -- numpy.ndarray -----------------------------------------------
    try:
        import numpy as np

        if isinstance(obj, np.ndarray):
            return _serialize_ndarray(obj)
    except ImportError:
        pass

    # -- pandas.DataFrame --------------------------------------------
    try:
        import pandas as pd

        if isinstance(obj, pd.DataFrame):
            return _serialize_dataframe(obj)
    except ImportError:
        pass

    # -- PIL.Image ---------------------------------------------------
    try:
        from PIL import Image

        if isinstance(obj, Image.Image):
            return _serialize_pil_image(obj)
    except ImportError:
        pass

    # -- JSON-native types -------------------------------------------
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError, OverflowError):
        pass

    # -- Fallback ----------------------------------------------------
    return {"type": "unknown", "repr": str(obj)[:500]}


# ---------------------------------------------------------------------------
# Type-specific serializers
# ---------------------------------------------------------------------------

def _serialize_tensor(tensor: Any) -> dict[str, Any]:
    """Torch tensor -> summary stats."""
    import torch

    t = tensor.detach().float().cpu()
    result: dict[str, Any] = {
        "type": "tensor",
        "shape": list(tensor.shape),
        "dtype": str(tensor.dtype),
        "device": str(tensor.device),
        "stats": {
            "mean": round(t.mean().item(), 6),
            "std": round(t.std().item(), 6),
            "min": round(t.min().item(), 6),
            "max": round(t.max().item(), 6),
        },
    }
    # Per-channel means for >= 3D tensors with a channel dim
    if t.ndim >= 3:
        # Assume channel dim is 1 for NCHW or 0 for CHW
        ch_dim = 1 if t.ndim >= 4 else 0
        ch_count = t.shape[ch_dim]
        if ch_count <= 128:  # only if reasonable
            dims_to_reduce = [i for i in range(t.ndim) if i != ch_dim]
            per_ch_mean = t.mean(dim=dims_to_reduce)
            result["per_channel_mean"] = [round(v.item(), 6) for v in per_ch_mean]
    return result


def _serialize_ndarray(arr: Any) -> dict[str, Any]:
    """Numpy array -> summary stats."""
    import numpy as np

    result: dict[str, Any] = {
        "type": "ndarray",
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
    }
    if np.issubdtype(arr.dtype, np.number) and arr.size > 0:
        result["stats"] = {
            "mean": round(float(np.nanmean(arr)), 6),
            "std": round(float(np.nanstd(arr)), 6),
            "min": round(float(np.nanmin(arr)), 6),
            "max": round(float(np.nanmax(arr)), 6),
        }
        # Per-channel means
        if arr.ndim >= 3:
            ch_dim = 1 if arr.ndim >= 4 else 0
            ch_count = arr.shape[ch_dim]
            if ch_count <= 128:
                axes = tuple(i for i in range(arr.ndim) if i != ch_dim)
                per_ch = np.nanmean(arr, axis=axes)
                result["per_channel_mean"] = [round(float(v), 6) for v in per_ch]
    return result


def _serialize_dataframe(df: Any) -> dict[str, Any]:
    """Pandas DataFrame -> describe() + shape + dtypes."""
    return {
        "type": "dataframe",
        "shape": list(df.shape),
        "columns": list(df.columns),
        "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
        "describe": df.describe(include="all").to_dict(),
    }


def _serialize_pil_image(img: Any) -> dict[str, Any]:
    """PIL Image -> metadata + 64px thumbnail base64."""
    result: dict[str, Any] = {
        "type": "image",
        "size": list(img.size),
        "mode": img.mode,
    }
    try:
        thumb = img.copy()
        thumb.thumbnail((64, 64))
        buf = io.BytesIO()
        thumb.save(buf, format="PNG")
        result["thumbnail_base64"] = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    return result
