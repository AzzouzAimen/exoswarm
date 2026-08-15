"""Run the cached-real deterministic candidate path without network access."""

import json
import math
import tempfile
from pathlib import Path

from exoswarm.domain.enums import ToolStatus
from exoswarm.science.pipeline import analyze_cached_candidate


def main() -> None:
    case_path = Path("evals/fixtures/cached_real_tess_case.json")
    if not case_path.exists():
        raise FileNotFoundError("cached-real validation manifest is unavailable")
    case = json.loads(case_path.read_text(encoding="utf-8"))
    cached_path = Path(case["cached_path"])
    if not cached_path.is_file():
        raise FileNotFoundError(f"cached-real FITS is unavailable: {cached_path}")

    with tempfile.TemporaryDirectory(prefix="exoswarm-reproduce-") as temporary:
        temporary_path = Path(temporary)
        parameters = {
            "cached_path": str(cached_path),
            "artifact_dir": str(temporary_path / "artifacts"),
            "ledger_path": str(temporary_path / "evidence.jsonl"),
            "step_id": "step_reproduce",
            "preprocessing": {
                "quality_bitmask": 175,
                "outlier_sigma": 8.0,
                "detrend_window_days": 1.0,
                "gap_threshold_cadences": 5.0,
                "minimum_samples": 200,
            },
            "search": case["search"],
        }
        result = analyze_cached_candidate(
            run_id="run_reproduce",
            action_id="action_reproduce",
            target_id=case["opaque_target_id"],
            parameters=parameters,
        )

    expected = case["expected"]
    period_measurement = result.measurements.get("period")
    period = float(period_measurement.value) if period_measurement else math.nan
    if result.status != ToolStatus.SUCCESS or not (
        expected["period_days_min"] <= period <= expected["period_days_max"]
    ):
        raise RuntimeError(f"cached-real reproduction failed: {result.model_dump_json()}")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
