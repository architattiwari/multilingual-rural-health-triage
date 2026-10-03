"""Runs the evaluation dataset as a regression gate. Not evidence of clinical accuracy."""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.safety


def _load():
    path = Path(__file__).resolve().parents[2] / "evaluation" / "run_eval.py"
    spec = importlib.util.spec_from_file_location("run_eval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_emergency_example_escalates_and_nothing_regresses():
    report = _load().run()
    assert report["emergency_recall"] == 1.0, report["failures"]
    assert report["false_emergency_rate"] == 0.0
    assert report["symptom_f1"] >= 0.95 and report["language_detection_accuracy"] >= 0.95
    assert report["failures"] == []
