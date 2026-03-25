"""Tests for the pipeline module."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from research_lab.pipeline.runner import topological_sort
from research_lab.pipeline.serializer import serialize_value
from research_lab.pipeline.store import ExperimentStore
from research_lab.schemas import Experiment, Step, StepResult


def test_topological_sort_linear():
    """Steps with linear dependencies should sort correctly."""
    steps = [
        Step(name="c", depends_on=["b"]),
        Step(name="a"),
        Step(name="b", depends_on=["a"]),
    ]
    ordered = topological_sort(steps)
    names = [s.name for s in ordered]
    assert names == ["a", "b", "c"]


def test_topological_sort_no_deps():
    """Steps without dependencies should preserve some order."""
    steps = [Step(name="a"), Step(name="b"), Step(name="c")]
    ordered = topological_sort(steps)
    assert len(ordered) == 3


def test_serialize_primitive():
    """Primitives should pass through unchanged."""
    assert serialize_value(42) == 42
    assert serialize_value("hello") == "hello"
    assert serialize_value([1, 2, 3]) == [1, 2, 3]


def test_serialize_unknown():
    """Unknown types should produce a fallback dict."""
    result = serialize_value(object())
    assert isinstance(result, dict)
    assert result["type"] == "unknown"


def test_experiment_store_crud():
    """ExperimentStore should handle basic CRUD."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ExperimentStore(Path(tmpdir))
        now = datetime.now(timezone.utc)

        exp = Experiment(id="test-1", name="Test", created_at=now, updated_at=now)
        store.create(exp)

        loaded = store.get("test-1")
        assert loaded is not None
        assert loaded.name == "Test"

        all_exps = store.list_all()
        assert len(all_exps) == 1

        store.delete("test-1")
        assert store.get("test-1") is None


def test_store_save_and_get_canvases():
    """ExperimentStore should persist and retrieve canvas data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ExperimentStore(Path(tmpdir))
        now = datetime.now(timezone.utc)

        exp = Experiment(id="canvas-exp", name="Canvas Test", created_at=now, updated_at=now)
        store.create(exp)

        canvases = [
            {
                "canvas_name": "Results",
                "widgets": [
                    {"kind": "metrics", "data": {"total": 100, "mean": 50}},
                    {"kind": "text", "content": "## Summary"},
                ],
            },
            {
                "canvas_name": "Distribution",
                "widgets": [
                    {"kind": "metrics", "data": {"variance": 833.25}},
                ],
            },
        ]

        store.save_canvases("canvas-exp", "analyze", canvases)
        loaded = store.get_canvases("canvas-exp", "analyze")
        assert len(loaded) == 2
        assert loaded[0]["canvas_name"] == "Results"
        assert loaded[0]["widgets"][0]["data"]["total"] == 100
        assert loaded[1]["canvas_name"] == "Distribution"


def test_store_get_canvases_missing():
    """get_canvases should return empty list when no canvas file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ExperimentStore(Path(tmpdir))
        now = datetime.now(timezone.utc)

        exp = Experiment(id="no-canvas", name="No Canvas", created_at=now, updated_at=now)
        store.create(exp)

        assert store.get_canvases("no-canvas", "train") == []


def test_store_canvases_dont_pollute_run_numbers():
    """Canvas files should not inflate the run number counter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ExperimentStore(Path(tmpdir))
        now = datetime.now(timezone.utc)

        exp = Experiment(
            id="run-num-test", name="Run Number Test",
            created_at=now, updated_at=now,
            steps=[Step(name="train")],
        )
        store.create(exp)

        # Save a result (creates train_001.json)
        result = StepResult(
            step_name="train", run_number=1, status="completed",
            started_at=now, completed_at=now, execution_time_s=1.0,
        )
        store.save_result("run-num-test", result)

        # Save canvases (creates train_canvases.json)
        store.save_canvases("run-num-test", "train", [{"canvas_name": "X", "widgets": []}])

        # Next run number should be 2, not 3
        assert store.next_run_number("run-num-test", "train") == 2


def test_step_result_canvases_field():
    """StepResult should accept a canvases field."""
    now = datetime.now(timezone.utc)
    result = StepResult(
        step_name="test",
        run_number=1,
        status="completed",
        started_at=now,
        completed_at=now,
        execution_time_s=0.5,
        canvases=[{"canvas_name": "Results", "widgets": [{"kind": "text", "content": "hi"}]}],
    )
    assert len(result.canvases) == 1
    assert result.canvases[0]["canvas_name"] == "Results"

    # Default should be empty list
    result2 = StepResult(
        step_name="test2", run_number=1, status="completed",
        started_at=now, completed_at=now, execution_time_s=0.5,
    )
    assert result2.canvases == []
