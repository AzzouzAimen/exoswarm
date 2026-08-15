from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.harness_suite import markdown_summary, run_suite  # noqa: E402


@pytest.fixture(scope="module")
def harness_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return run_suite(tmp_path_factory.mktemp("locked-harness-evals"))


def test_locked_harness_suite_passes_and_reloads_every_artifact(harness_report: dict) -> None:
    assert harness_report["passed"] is True
    assert harness_report["scenario_count"] == 24
    assert harness_report["failed_count"] == 0
    assert harness_report["metrics"] == {
        "branch_count": 4,
        "cost_budget_status": "graded",
        "repeated_tool_calls": 0,
        "artifact_reload_cases": 24,
        "unnecessary_tool_calls": 0,
    }
    assert all(item["passed"] for item in harness_report["scenarios"])


def test_evaluation_report_is_machine_readable_and_has_no_ephemeral_run_ids(
    harness_report: dict,
) -> None:
    rendered = json.dumps(harness_report, sort_keys=True)
    assert '"suite_id": "exoswarm-harness-adversarial-v1"' in rendered
    assert "run_" not in rendered
    summary = markdown_summary(harness_report)
    assert "Result: **PASS**" in summary
    assert "24/24 scenarios passed" in summary


def test_unnecessary_tool_metric_compares_against_locked_trajectory() -> None:
    from evals.harness_suite import _unnecessary_tool_call_count

    assert _unnecessary_tool_call_count(["harmonic_test"], ["harmonic_test"]) == 0
    assert _unnecessary_tool_call_count(["centroid_localization"], []) == 1
    assert _unnecessary_tool_call_count(
        ["harmonic_test", "harmonic_test"], ["harmonic_test"]
    ) == 1
