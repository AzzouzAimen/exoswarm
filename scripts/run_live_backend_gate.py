"""Run one real cached target through FastAPI, Featherless, lock, and reveal."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exoswarm.agents.context import CONTEXT_SCHEMA_VERSION
from exoswarm.api.app import create_app
from exoswarm.config import Settings
from fastapi.testclient import TestClient

from evals.provenance import evaluation_provenance


def _require_success(response, operation: str) -> dict[str, Any]:
    if not response.is_success:
        raise RuntimeError(
            f"{operation} failed with HTTP {response.status_code}: {response.text}"
        )
    return response.json()


def _event_payloads(stream_text: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in stream_text.splitlines()
        if line.startswith("data: ")
    ]


def run_gate(*, target_id: str, timeout_seconds: float) -> dict[str, Any]:
    configured = Settings()
    if configured.featherless_api_key is None:
        raise RuntimeError("FEATHERLESS_API_KEY is required for the live backend gate")

    with tempfile.TemporaryDirectory(prefix="exoswarm-live-backend-") as temporary:
        settings = configured.model_copy(
            update={
                "data_dir": ROOT / "data",
                "runs_dir": Path(temporary) / "runs",
                "run_timeout_seconds": timeout_seconds,
            }
        )
        with TestClient(create_app(settings)) as client:
            created = _require_success(
                client.post(
                    "/api/investigations",
                    json={"opaque_target_id": target_id},
                    headers={"Idempotency-Key": f"live-backend-gate-{target_id}"},
                ),
                "create investigation",
            )
            run_id = created["run_id"]
            deadline = time.monotonic() + timeout_seconds
            while True:
                state = _require_success(
                    client.get(f"/api/investigations/{run_id}"),
                    "read investigation",
                )
                if not state["execution"]["active"]:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"live backend gate exceeded {timeout_seconds:.0f} seconds"
                    )
                time.sleep(0.1)

            stream = client.get(f"/api/investigations/{run_id}/events")
            stream.raise_for_status()
            events = _event_payloads(stream.text)
            if state["status"] != "READY_TO_LOCK":
                attempts = [
                    event["payload"]
                    for event in events
                    if event["type"] == "inference.attempt"
                ]
                raise RuntimeError(
                    "live target did not reach READY_TO_LOCK: "
                    f"{state['status']} / {state.get('terminal_reason')}; "
                    f"sanitized_inference_attempts={json.dumps(attempts, sort_keys=True)}"
                )
            if state["model_call_count"] < 2:
                raise RuntimeError("live target did not exercise both agent roles")

            locked = _require_success(
                client.post(f"/api/investigations/{run_id}/lock"),
                "lock investigation",
            )
            artifacts = _require_success(
                client.get(f"/api/investigations/{run_id}/artifacts"),
                "list artifacts",
            )["artifacts"]
            revealed = _require_success(
                client.post(f"/api/investigations/{run_id}/reveal"),
                "reveal catalog comparison",
            )
            if revealed["locked_result_sha256"] != locked["sha256"]:
                raise RuntimeError("reveal does not reference the locked result hash")

            inference = state["inference_summary"]
            return {
                "schema_version": "1",
                "status": "PASS",
                "provenance": evaluation_provenance(
                    evaluation_id="live-backend-gate-v1",
                    configuration={
                        "inference_model": settings.model,
                        "context_schema_version": CONTEXT_SCHEMA_VERSION,
                        "max_output_tokens": settings.inference_max_output_tokens,
                        "target_id": target_id,
                        "timeout_seconds": timeout_seconds,
                    },
                ),
                "opaque_target_id": target_id,
                "run_status_before_lock": state["status"],
                "disposition": state["disposition"],
                "terminal_reason": state["terminal_reason"],
                "completed_tests": state["completed_tests"],
                "adaptive_actions": [
                    decision["requested_experiment"]
                    for decision in state["accepted_decisions"]
                ],
                "model_calls": state["model_call_count"],
                "tool_calls": state["tool_call_count"],
                "inference": inference,
                "event_count": len(events),
                "event_types": sorted({event["type"] for event in events}),
                "artifact_count": len(artifacts),
                "artifact_paths": sorted(item["relative_path"] for item in artifacts),
                "locked_sha256": locked["sha256"],
                "reveal_hash_verified": True,
                "catalog_source": revealed["catalog_source"],
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="TARGET-P21")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "evals/live_backend_gate.json",
    )
    args = parser.parse_args()
    report = run_gate(target_id=args.target, timeout_seconds=args.timeout)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
