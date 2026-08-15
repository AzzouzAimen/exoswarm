from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
for import_root in (ROOT, API_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from evals.harness_suite import markdown_summary, run_suite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the locked deterministic ExoSwarm harness evaluation suite."
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=ROOT / "evals" / "report.json",
        help="machine-readable report path",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=ROOT / "evals" / "report.md",
        help="concise Markdown summary path",
    )
    parser.add_argument(
        "--keep-runs",
        type=Path,
        help="optional directory for retaining per-scenario persisted run artifacts",
    )
    args = parser.parse_args()

    report = run_suite(args.keep_runs)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(markdown_summary(report), encoding="utf-8")
    print(
        f"{report['suite_id']}: {report['passed_count']}/{report['scenario_count']} passed; "
        f"JSON={args.json}; Markdown={args.markdown}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
