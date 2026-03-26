"""Tests for the FastAPI server."""

import base64
import io
import json
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from research_lab.config import Settings
from research_lab.pipeline.store import ExperimentStore
from research_lab.schemas import Experiment, ImageOutput, Step, StepResult
from research_lab.server.app import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(project_dir=tmp_path)
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_status(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["server_running"] is True


def test_experiments_crud(client):
    # Create
    r = client.post("/api/experiments", json={"name": "Test Experiment"})
    assert r.status_code == 201
    exp = r.json()
    exp_id = exp["id"]
    assert exp["name"] == "Test Experiment"

    # List
    r = client.get("/api/experiments")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Get
    r = client.get(f"/api/experiments/{exp_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Test Experiment"

    # Update
    r = client.put(f"/api/experiments/{exp_id}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"

    # Delete
    r = client.delete(f"/api/experiments/{exp_id}")
    assert r.status_code == 200

    # Verify deleted
    r = client.get(f"/api/experiments/{exp_id}")
    assert r.status_code == 404


def test_step_crud(client):
    # Create experiment
    r = client.post("/api/experiments", json={"name": "Step Test"})
    exp_id = r.json()["id"]

    # Add step
    r = client.post(
        f"/api/experiments/{exp_id}/steps",
        json={"name": "train", "code": "print('hello')"},
    )
    assert r.status_code == 201
    assert len(r.json()["steps"]) == 1

    # Get step
    r = client.get(f"/api/experiments/{exp_id}/steps/train")
    assert r.status_code == 200
    assert r.json()["step"]["name"] == "train"

    # Update step
    r = client.put(
        f"/api/experiments/{exp_id}/steps/train",
        json={"code": "print('updated')"},
    )
    assert r.status_code == 200

    # Delete step
    r = client.delete(f"/api/experiments/{exp_id}/steps/train")
    assert r.status_code == 200
    assert len(r.json()["steps"]) == 0


def test_get_step_includes_canvases(client):
    """GET /steps/{name} should include a canvases key in the response."""
    r = client.post("/api/experiments", json={"name": "Canvas Step Test"})
    exp_id = r.json()["id"]

    r = client.post(
        f"/api/experiments/{exp_id}/steps",
        json={"name": "analyze", "code": "pass"},
    )
    assert r.status_code == 201

    r = client.get(f"/api/experiments/{exp_id}/steps/analyze")
    assert r.status_code == 200
    data = r.json()
    assert "canvases" in data
    assert data["canvases"] == []  # no canvases yet


def test_get_all_results_includes_canvases(client):
    """GET /experiments/{id}/results should include canvases for each step."""
    r = client.post("/api/experiments", json={"name": "Results Canvas Test"})
    exp_id = r.json()["id"]

    # Just verify the endpoint returns without error when empty
    r = client.get(f"/api/experiments/{exp_id}/results")
    assert r.status_code == 200
    assert r.json() == {}


# ---------------------------------------------------------------------------
# Asset library endpoint tests
# ---------------------------------------------------------------------------

def _create_experiment_with_images(client) -> str:
    """Helper: create an experiment, add a step, and save a result with images."""
    r = client.post("/api/experiments", json={"name": "Asset Test"})
    assert r.status_code == 201
    exp_id = r.json()["id"]

    # Add a step
    r = client.post(
        f"/api/experiments/{exp_id}/steps",
        json={"name": "generate", "code": "pass"},
    )
    assert r.status_code == 201

    # Write a result with a fake image directly via the store
    store: ExperimentStore = client.app.state.store
    now = datetime.now(timezone.utc)
    # Minimal 1x1 red PNG encoded as base64
    pixel_png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
        "nGP4z8BQDwAEgAF/pooBPQAAAABJRU5ErkJggg=="
    )
    result = StepResult(
        step_name="generate",
        run_number=1,
        status="completed",
        started_at=now,
        completed_at=now,
        execution_time_s=1.5,
        images=[
            ImageOutput(label="Red Pixel", mime="image/png", data=pixel_png),
        ],
    )
    store.save_result(exp_id, result)

    # Also save a canvas with an image widget
    canvases = [
        {
            "canvas_name": "Results",
            "widgets": [
                {"kind": "image", "title": "Canvas Image", "mime": "image/png", "data": pixel_png},
            ],
        }
    ]
    store.save_canvases(exp_id, "generate", canvases)

    # Write a small artifact file
    art_path = store.artifact_path(exp_id, "weights.npy")
    art_path.write_bytes(b"FAKE_NUMPY_DATA_1234567890")

    return exp_id


def test_get_assets_empty(client):
    """GET /assets on an experiment with no results returns empty lists."""
    r = client.post("/api/experiments", json={"name": "Empty Assets"})
    exp_id = r.json()["id"]

    r = client.get(f"/api/experiments/{exp_id}/assets")
    assert r.status_code == 200
    data = r.json()
    assert data["images"] == []
    assert data["artifacts"] == []


def test_get_assets_with_images(client):
    """GET /assets collects images from results and canvases."""
    exp_id = _create_experiment_with_images(client)

    r = client.get(f"/api/experiments/{exp_id}/assets")
    assert r.status_code == 200
    data = r.json()

    # Should have 2 images: one from result, one from canvas
    assert len(data["images"]) == 2
    assert data["images"][0]["source"] == "result"
    assert data["images"][0]["title"] == "Red Pixel"
    assert data["images"][1]["source"] == "canvas"
    assert data["images"][1]["canvas_name"] == "Results"

    # Should have 1 artifact
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["name"] == "weights.npy"
    assert data["artifacts"][0]["format"] == "npy"
    assert data["artifacts"][0]["size_bytes"] > 0


def test_get_assets_404(client):
    """GET /assets on a non-existent experiment returns 404."""
    r = client.get("/api/experiments/does-not-exist/assets")
    assert r.status_code == 404


def test_get_asset_by_index(client):
    """GET /assets/{index} returns the raw image bytes."""
    exp_id = _create_experiment_with_images(client)

    r = client.get(f"/api/experiments/{exp_id}/assets/0")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    # Should be valid decodable PNG bytes
    assert r.content[:4] == b"\x89PNG"


def test_get_asset_by_index_404(client):
    """GET /assets/{index} returns 404 for invalid index."""
    exp_id = _create_experiment_with_images(client)

    r = client.get(f"/api/experiments/{exp_id}/assets/999")
    assert r.status_code == 404


def test_download_assets_zip(client):
    """GET /assets/download returns a valid zip with images and artifacts."""
    exp_id = _create_experiment_with_images(client)

    r = client.get(f"/api/experiments/{exp_id}/assets/download")
    assert r.status_code == 200
    assert "application/zip" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")

    # Verify it's a valid zip file with expected contents
    buf = io.BytesIO(r.content)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
        # Should contain images and artifacts
        image_files = [n for n in names if n.startswith("images/")]
        artifact_files = [n for n in names if n.startswith("artifacts/")]
        assert len(image_files) == 2
        assert len(artifact_files) == 1
        assert "artifacts/weights.npy" in names
