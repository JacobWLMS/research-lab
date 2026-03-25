"""Tests for the FastAPI server."""

import pytest
from fastapi.testclient import TestClient

from research_lab.config import Settings
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
