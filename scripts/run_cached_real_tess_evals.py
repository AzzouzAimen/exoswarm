"""Run the locked five-case cached-real TESS backend evaluation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.config import Settings
from exoswarm.domain.enums import CriticVerdict, InformationValue, Priority
from exoswarm.domain.errors import ResultNotLockedError
from exoswarm.domain.models import CriticDecision, SkepticDecision
from exoswarm.investigation.controller import InvestigationController
from exoswarm.investigation.runner import InvestigationRunService
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore
from exoswarm.services.nasa_reveal import CachedCatalogRevealProvider
from exoswarm.services.target_registry import TargetRegistry
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals/real_tess/v1/cases.json"
LOCK_PATH = ROOT / "evals/real_tess/v1/lock.json"
MANDATORY_TESTS = {"signal_quality", "odd_even", "secondary_eclipse", "contamination"}


def _stop_after_mandatory(context: BaseModel, _schema: type[BaseModel]) -> SkepticDecision:
    packet = AgentContextPacket.model_validate(context)
    return SkepticDecision(
        decision_id=f"decision_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        hypothesis_under_test=(
            packet.strongest_unresolved_alternative or "residual_false_positive"
        ),
        requested_experiment="stop",
        parameters={},
        reason_code="REAL_TESS_BASELINE_COMPLETE",
        expected_discriminating_result="Finalize from mandatory deterministic evidence.",
        predicted_outcomes={"STOP": "Preserve the completed mandatory evidence."},
        expected_information_value=InformationValue.LOW,
        priority=Priority.LOW,
        budget_units_remaining=packet.remaining_budgets.adaptive_cost_units,
        cost_of_selected_experiment=0,
        why_cost_is_justified="Stopping consumes zero deterministic experiment units.",
        concise_reason="The locked evaluator stops after mandatory evidence.",
        supporting_evidence_refs=[packet.evidence_refs[-1]],
        contradicting_evidence_refs=[],
    )


def _approve_stop(context: BaseModel, _schema: type[BaseModel]) -> CriticDecision:
    packet = AgentContextPacket.model_validate(context)
    proposal = packet.proposed_decision
    if proposal is None:
        raise ValueError("real-TESS evaluator Critic requires a Skeptic proposal")
    return CriticDecision(
        decision_id=f"critic_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        skeptic_decision_id=proposal.decision_id,
        verdict=CriticVerdict.APPROVE,
        reason_code="REAL_TESS_STOP_APPROVED",
        concise_reason="Mandatory deterministic evidence is complete.",
        supporting_evidence_refs=[packet.evidence_refs[-1]],
        contradicting_evidence_refs=[],
    )


def _load_cases() -> list[dict[str, Any]]:
    expected_digest = json.loads(LOCK_PATH.read_text(encoding="utf-8"))["cases_sha256"]
    actual_digest = hashlib.sha256(CASES_PATH.read_bytes()).hexdigest()
    if actual_digest != expected_digest:
        raise RuntimeError("real-TESS evaluation cases changed without updating the suite lock")
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return list(payload["cases"])


def _period_passed(case: dict[str, Any], recovered: float | None) -> bool:
    expected = case["expected_period_days"]
    tolerance = case["period_tolerance_days"]
    if expected is None:
        return recovered is None
    if recovered is None or tolerance is None:
        return False
    return any(
        abs(recovered - float(expected) * float(factor)) <= float(tolerance)
        for factor in case["accepted_period_factors"]
    )


async def _run_case(case: dict[str, Any], root: Path) -> dict[str, Any]:
    data_dir = ROOT / "data"
    settings = Settings(
        data_dir=data_dir,
        runs_dir=root / case["opaque_target_id"] / "runs",
        max_model_retries=0,
    )
    targets = TargetRegistry(settings.resolved_target_manifest_path, data_dir=data_dir)
    artifacts = FileSystemRunArtifactStore(settings.runs_dir)
    controller = InvestigationController(
        settings,
        artifacts,
        ResultLockService(artifacts),
        CatalogGate(
            artifacts,
            CachedCatalogRevealProvider(data_dir / "ground_truth/catalog_reveal.json"),
        ),
        inference=ScriptedInferenceClient(
            {"skeptic": [_stop_after_mandatory], "critic": [_approve_stop]},
            model_identity="scripted:real-tess-evaluator-v1",
        ),
        candidate_sources=targets,
    )
    service = InvestigationRunService(
        controller,
        targets,
        runs_dir=settings.runs_dir,
        timeout_seconds=settings.run_timeout_seconds,
        sse_poll_interval_seconds=settings.sse_poll_interval_seconds,
    )
    state = controller.create(case["opaque_target_id"])
    try:
        await service.start(state.run_id)
        execution = await service.wait(state.run_id)
    finally:
        await service.close()
    state = controller.get(state.run_id)
    recovered_period = (
        float(state.candidate_signals[0].measurements["period"].value)
        if state.candidate_signals
        else None
    )

    hash_verified = False
    catalog_disposition = None
    ground_truth_locked_before_result = False
    try:
        controller.reveal(state.run_id)
    except ResultNotLockedError:
        ground_truth_locked_before_result = True
    if state.status == "READY_TO_LOCK":
        receipt = controller.lock(state.run_id)
        locked = controller.get(state.run_id)
        result_bytes = artifacts.read_bytes(locked, "result.json")
        hash_verified = hashlib.sha256(result_bytes).hexdigest() == receipt.sha256
        reveal = controller.reveal(state.run_id)
        hash_verified = hash_verified and reveal.locked_result_sha256 == receipt.sha256
        catalog_disposition = reveal.catalog_payload["catalog_disposition"]

    checks = {
        "status": str(state.status) == case["expected_status"],
        "disposition": (
            str(state.disposition) if state.disposition is not None else None
        )
        == case["expected_disposition"],
        "period": _period_passed(case, recovered_period),
        "mandatory_tests": (
            set(state.completed_tests) == MANDATORY_TESTS
            if state.status == "READY_TO_LOCK"
            else True
        ),
        "lock_and_reveal_hash": hash_verified if state.status == "READY_TO_LOCK" else True,
        "ground_truth_locked_before_result": ground_truth_locked_before_result,
        "catalog_disposition": (
            catalog_disposition == case["expected_catalog_disposition"]
            if state.status == "READY_TO_LOCK"
            else True
        ),
        "raw_samples_in_agent_context": (
            state.inference_summary.raw_light_curve_samples_sent == 0
        ),
    }
    return {
        "id": case["id"],
        "opaque_target_id": case["opaque_target_id"],
        "passed": all(checks.values()),
        "checks": checks,
        "observed": {
            "status": str(state.status),
            "disposition": str(state.disposition) if state.disposition is not None else None,
            "terminal_reason": state.terminal_reason,
            "period_days": recovered_period,
            "completed_tests": state.completed_tests,
            "model_calls": state.model_call_count,
            "tool_calls": state.tool_call_count,
            "runner_advances": execution.advances,
            "hash_verified": hash_verified,
            "catalog_disposition_after_lock": catalog_disposition,
        },
    }


async def _run() -> dict[str, Any]:
    cases = _load_cases()
    with tempfile.TemporaryDirectory(prefix="exoswarm-real-tess-eval-") as temporary:
        results = [await _run_case(case, Path(temporary)) for case in cases]
    passed = sum(result["passed"] for result in results)
    period_cases = [
        result
        for case, result in zip(cases, results, strict=True)
        if case["expected_period_days"] is not None
    ]
    return {
        "schema_version": "1",
        "suite_id": "exoswarm-cached-real-tess-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "cases_sha256": hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
        "passed": passed == len(results),
        "passed_count": passed,
        "case_count": len(results),
        "period_recovery_passed_count": sum(
            result["checks"]["period"] for result in period_cases
        ),
        "period_recovery_expected_count": len(period_cases),
        "expected_non_detection_count": len(results) - len(period_cases),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "evals/cached_real_tess_report.json"
    )
    args = parser.parse_args()
    report = asyncio.run(_run())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"{report['suite_id']}: {report['passed_count']}/{report['case_count']} passed; "
        "period recoveries="
        f"{report['period_recovery_passed_count']}/"
        f"{report['period_recovery_expected_count']}; "
        f"JSON={args.output.resolve()}"
    )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
