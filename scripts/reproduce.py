"""Reproduce a complete cached investigation, lock, hash, and reveal verification."""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.config import Settings
from exoswarm.domain.enums import (
    CriticVerdict,
    InformationValue,
    InvestigationStatus,
    Priority,
)
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
REPRODUCE_TARGET = "TARGET-P21"


def _stop_after_mandatory(
    context: BaseModel, _schema: type[BaseModel]
) -> SkepticDecision:
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
        reason_code="REPRODUCTION_BASELINE_SUFFICIENT",
        expected_discriminating_result=(
            "No additional cached experiment is required for hash reproduction."
        ),
        predicted_outcomes={"STOP": "Finalize from deterministic mandatory evidence."},
        expected_information_value=InformationValue.LOW,
        priority=Priority.LOW,
        budget_units_remaining=packet.remaining_budgets.adaptive_cost_units,
        cost_of_selected_experiment=0,
        why_cost_is_justified="Stopping consumes zero deterministic experiment units.",
        concise_reason="The reproduction policy stops after the mandatory evidence gate.",
    )


def _approve_stop(context: BaseModel, _schema: type[BaseModel]) -> CriticDecision:
    packet = AgentContextPacket.model_validate(context)
    proposal = packet.proposed_decision
    if proposal is None:
        raise ValueError("reproduction Critic requires the durable Skeptic proposal")
    return CriticDecision(
        decision_id=f"critic_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        skeptic_decision_id=proposal.decision_id,
        verdict=CriticVerdict.APPROVE,
        reason_code="REPRODUCTION_STOP_APPROVED",
        concise_reason="The zero-cost stop preserves the bounded reproduction contract.",
    )


async def _reproduce() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="exoswarm-reproduce-") as temporary:
        data_dir = ROOT / "data"
        settings = Settings(
            runs_dir=Path(temporary) / "runs",
            data_dir=data_dir,
            max_model_retries=0,
        )
        targets = TargetRegistry(
            settings.resolved_target_manifest_path,
            data_dir=data_dir,
        )
        artifacts = FileSystemRunArtifactStore(settings.runs_dir)
        inference = ScriptedInferenceClient(
            {
                "skeptic": [_stop_after_mandatory],
                "critic": [_approve_stop],
            },
            model_identity="scripted:reproduction-policy-v1",
        )
        controller = InvestigationController(
            settings,
            artifacts,
            ResultLockService(artifacts),
            CatalogGate(
                artifacts,
                CachedCatalogRevealProvider(
                    data_dir / "ground_truth/catalog_reveal.json"
                ),
            ),
            inference=inference,
            candidate_sources=targets,
        )
        service = InvestigationRunService(
            controller,
            targets,
            runs_dir=settings.runs_dir,
            timeout_seconds=settings.run_timeout_seconds,
            sse_poll_interval_seconds=settings.sse_poll_interval_seconds,
        )
        state = controller.create(REPRODUCE_TARGET)
        try:
            await service.start(state.run_id)
            execution = await service.wait(state.run_id)
        finally:
            await service.close()
        state = controller.get(state.run_id)
        if state.status != InvestigationStatus.READY_TO_LOCK:
            raise RuntimeError(
                f"cached investigation did not reach READY_TO_LOCK: {state.terminal_reason}"
            )

        receipt = controller.lock(state.run_id)
        locked_state = controller.get(state.run_id)
        result_bytes = artifacts.read_bytes(locked_state, "result.json")
        actual_sha256 = hashlib.sha256(result_bytes).hexdigest()
        persisted_sha256 = (
            artifacts.read_bytes(locked_state, "result.json.sha256").decode().strip()
        )
        if receipt.sha256 != actual_sha256 or persisted_sha256 != actual_sha256:
            raise RuntimeError("locked result hash does not match the exact result bytes")

        reveal = controller.reveal(state.run_id)
        if reveal.locked_result_sha256 != actual_sha256:
            raise RuntimeError("catalog reveal does not reference the verified locked hash")

        return {
            "schema_version": "1",
            "status": "PASS",
            "opaque_target_id": REPRODUCE_TARGET,
            "run_status_before_lock": InvestigationStatus.READY_TO_LOCK,
            "runner_advances": execution.advances,
            "mandatory_tests": state.completed_tests,
            "model_calls": state.model_call_count,
            "tool_calls": state.tool_call_count,
            "locked_sha256": actual_sha256,
            "reveal_hash_verified": True,
            "catalog_source": reveal.catalog_source,
            "artifact_count": len(artifacts.list_artifacts(controller.get(state.run_id))),
        }


def main() -> None:
    print(json.dumps(asyncio.run(_reproduce()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
