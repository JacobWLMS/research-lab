"""File-based JSON persistence for experiments.

Each experiment lives in its own directory:
    {project_dir}/.research-lab/experiments/{experiment_id}/
        experiment.json
        results/{step_name}.json
        results/{step_name}_NNN.json   (historical)
        artifacts/
        code/
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from research_lab.schemas import Experiment, Step, StepResult


class ExperimentStore:
    """CRUD operations on the file-backed experiment store."""

    def __init__(self, experiments_dir: Path) -> None:
        self._root = experiments_dir
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _exp_dir(self, experiment_id: str) -> Path:
        return self._root / experiment_id

    def _exp_file(self, experiment_id: str) -> Path:
        return self._exp_dir(experiment_id) / "experiment.json"

    def _results_dir(self, experiment_id: str) -> Path:
        d = self._exp_dir(experiment_id) / "results"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _artifacts_dir(self, experiment_id: str) -> Path:
        d = self._exp_dir(experiment_id) / "artifacts"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _code_dir(self, experiment_id: str) -> Path:
        d = self._exp_dir(experiment_id) / "code"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ------------------------------------------------------------------
    # Experiment CRUD
    # ------------------------------------------------------------------

    def create(self, experiment: Experiment) -> Experiment:
        """Persist a new experiment to disk."""
        exp_dir = self._exp_dir(experiment.id)
        exp_dir.mkdir(parents=True, exist_ok=True)
        (exp_dir / "results").mkdir(exist_ok=True)
        (exp_dir / "artifacts").mkdir(exist_ok=True)
        (exp_dir / "code").mkdir(exist_ok=True)
        self._write_experiment(experiment)
        return experiment

    def get(self, experiment_id: str) -> Experiment | None:
        """Load an experiment from disk."""
        path = self._exp_file(experiment_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Experiment.model_validate(data)

    def list_all(self) -> list[Experiment]:
        """Return all experiments, sorted by creation time descending."""
        experiments: list[Experiment] = []
        if not self._root.exists():
            return experiments
        for d in sorted(self._root.iterdir()):
            if d.is_dir() and (d / "experiment.json").exists():
                try:
                    exp = Experiment.model_validate(
                        json.loads((d / "experiment.json").read_text())
                    )
                    experiments.append(exp)
                except Exception:
                    continue
        experiments.sort(key=lambda e: e.created_at, reverse=True)
        return experiments

    def update(self, experiment: Experiment) -> Experiment:
        """Overwrite the experiment metadata on disk."""
        experiment.updated_at = datetime.now(timezone.utc)
        self._write_experiment(experiment)
        return experiment

    def delete(self, experiment_id: str) -> bool:
        """Delete an experiment directory entirely."""
        exp_dir = self._exp_dir(experiment_id)
        if not exp_dir.exists():
            return False
        shutil.rmtree(exp_dir)
        return True

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def add_step(self, experiment_id: str, step: Step) -> Experiment | None:
        """Add a step to an existing experiment."""
        exp = self.get(experiment_id)
        if exp is None:
            return None
        if any(s.name == step.name for s in exp.steps):
            return None  # duplicate name
        exp.steps.append(step)
        return self.update(exp)

    def update_step(self, experiment_id: str, step_name: str, updates: dict) -> Experiment | None:
        """Update fields on a specific step."""
        exp = self.get(experiment_id)
        if exp is None:
            return None
        for s in exp.steps:
            if s.name == step_name:
                for k, v in updates.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
                return self.update(exp)
        return None

    def delete_step(self, experiment_id: str, step_name: str) -> Experiment | None:
        """Remove a step from an experiment."""
        exp = self.get(experiment_id)
        if exp is None:
            return None
        exp.steps = [s for s in exp.steps if s.name != step_name]
        return self.update(exp)

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def save_result(self, experiment_id: str, result: StepResult) -> None:
        """Write a StepResult to disk."""
        results_dir = self._results_dir(experiment_id)
        # Latest result
        latest = results_dir / f"{result.step_name}.json"
        latest.write_text(result.model_dump_json(indent=2))
        # Historical copy
        hist = results_dir / f"{result.step_name}_{result.run_number:03d}.json"
        hist.write_text(result.model_dump_json(indent=2))

    def get_result(self, experiment_id: str, step_name: str) -> StepResult | None:
        """Load the latest result for a step."""
        path = self._results_dir(experiment_id) / f"{step_name}.json"
        if not path.exists():
            return None
        return StepResult.model_validate_json(path.read_text())

    def get_all_results(self, experiment_id: str) -> dict[str, StepResult]:
        """Load the latest result for every step in an experiment."""
        results: dict[str, StepResult] = {}
        results_dir = self._exp_dir(experiment_id) / "results"
        if not results_dir.exists():
            return results
        for f in results_dir.iterdir():
            # Only pick up latest files (no _NNN suffix)
            if f.suffix == ".json" and "_" not in f.stem:
                try:
                    r = StepResult.model_validate_json(f.read_text())
                    results[r.step_name] = r
                except Exception:
                    continue
        return results

    def next_run_number(self, experiment_id: str, step_name: str) -> int:
        """Return the next run number for a step (1-indexed)."""
        results_dir = self._exp_dir(experiment_id) / "results"
        if not results_dir.exists():
            return 1
        existing = [
            f for f in results_dir.glob(f"{step_name}_*.json")
            if not f.stem.endswith("_canvases")
        ]
        return len(existing) + 1

    # ------------------------------------------------------------------
    # Canvas persistence
    # ------------------------------------------------------------------

    def save_canvases(self, experiment_id: str, step_name: str, canvases: list[dict]) -> None:
        """Write canvas data for a step to disk."""
        results_dir = self._results_dir(experiment_id)
        path = results_dir / f"{step_name}_canvases.json"
        path.write_text(json.dumps(canvases, indent=2))

    def get_canvases(self, experiment_id: str, step_name: str) -> list[dict]:
        """Load canvas data for a step from disk."""
        results_dir = self._exp_dir(experiment_id) / "results"
        path = results_dir / f"{step_name}_canvases.json"
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text())
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Code snapshots
    # ------------------------------------------------------------------

    def save_code(self, experiment_id: str, step_name: str, code: str) -> None:
        """Save a code snapshot for a step."""
        code_dir = self._code_dir(experiment_id)
        (code_dir / f"{step_name}.py").write_text(code)

    # ------------------------------------------------------------------
    # Artifact paths
    # ------------------------------------------------------------------

    def artifact_path(self, experiment_id: str, name: str) -> Path:
        """Return the full path for an artifact file."""
        return self._artifacts_dir(experiment_id) / name

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_experiment(self, experiment: Experiment) -> None:
        path = self._exp_file(experiment.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(experiment.model_dump_json(indent=2))
