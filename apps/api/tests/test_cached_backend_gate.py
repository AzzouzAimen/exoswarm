from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.config import Settings
from exoswarm.domain.enums import (
    CriticVerdict,
    Disposition,
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

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"


def _stop_policy(context: BaseModel, _schema: type[BaseModel]) -> SkepticDecision:
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
        reason_code="CACHED_GATE_BASELINE_SUFFICIENT",
        expected_discriminating_result="Finalize from mandatory deterministic evidence.",
        predicted_outcomes={"STOP": "Preserve the bounded cached baseline."},
        expected_information_value=InformationValue.LOW,
        priority=Priority.LOW,
        budget_units_remaining=packet.remaining_budgets.adaptive_cost_units,
        cost_of_selected_experiment=0,
        why_cost_is_justified="Stopping consumes zero experiment cost units.",
        concise_reason="The cached gate stops after mandatory evidence.",
    )


def _approve_stop(context: BaseModel, _schema: type[BaseModel]) -> CriticDecision:
    packet = AgentContextPacket.model_validate(context)
    proposal = packet.proposed_decision
    assert proposal is not None
    return CriticDecision(
        decision_id=f"critic_{packet.step_id}",
        run_id=packet.run_id,
        step_id=packet.step_id,
        context_version=packet.context_version,
        skeptic_decision_id=proposal.decision_id,
        verdict=CriticVerdict.APPROVE,
        reason_code="CACHED_GATE_STOP_APPROVED",
        concise_reason="The zero-cost stop is consistent with the cached gate policy.",
    )


async def _run_cached_target(tmp_path: Path, target_id: str):
    settings = Settings(
        data_dir=DATA_DIR,
        runs_dir=tmp_path / target_id / "runs",
        max_model_retries=0,
    )
    targets = TargetRegistry(
        settings.resolved_target_manifest_path,
        data_dir=DATA_DIR,
    )
    artifacts = FileSystemRunArtifactStore(settings.runs_dir)
    inference = ScriptedInferenceClient(
        {"skeptic": [_stop_policy], "critic": [_approve_stop]},
        model_identity="scripted:cached-backend-gate-v1",
    )
    controller = InvestigationController(
        settings,
        artifacts,
        ResultLockService(artifacts),
        CatalogGate(
            artifacts,
            CachedCatalogRevealProvider(
                DATA_DIR / "ground_truth/catalog_reveal.json"
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
    state = controller.create(target_id)
    try:
        await service.start(state.run_id)
        await service.wait(state.run_id)
    finally:
        await service.close()
    return controller.get(state.run_id)


@pytest.mark.asyncio
async def test_three_cached_targets_cover_distinct_backend_trajectories(tmp_path) -> None:
    for target_id, relative_path in (
        ("TARGET-X17", "cached/lightcurves/TARGET-X17-sector-2-lc.fits"),
        ("TARGET-P21", "cached/lightcurves/TARGET-P21-sector-14-lc.fits"),
        ("TARGET-D31", "cached/lightcurves/TARGET-D31-sector-3-lc.fits"),
    ):
        source = DATA_DIR / relative_path
        metadata_name = (
            "cached_real_tess_acquisition.json"
            if target_id == "TARGET-X17"
            else f"{target_id}-acquisition.json"
        )
        acquisition = json.loads(
            (DATA_DIR / "ground_truth" / metadata_name).read_text(encoding="utf-8")
        )
        assert hashlib.sha256(source.read_bytes()).hexdigest() == acquisition["cache"][
            "sha256"
        ]

    rejected = await _run_cached_target(tmp_path, "TARGET-X17")
    agent_reviewed = await _run_cached_target(tmp_path, "TARGET-P21")
    insufficient = await _run_cached_target(tmp_path, "TARGET-D31")

    assert rejected.status == InvestigationStatus.READY_TO_LOCK
    assert rejected.disposition == Disposition.PLANETARY_INTERPRETATION_REJECTED
    assert rejected.model_call_count == 0

    assert agent_reviewed.status == InvestigationStatus.READY_TO_LOCK
    assert agent_reviewed.disposition == Disposition.PLANETARY_INTERPRETATION_WEAK
    assert agent_reviewed.model_call_count == 2
    assert agent_reviewed.accepted_decisions[-1].requested_experiment == "stop"
    assert agent_reviewed.candidate_signals[0].measurements["period"].value == pytest.approx(
        2.204, abs=0.02
    )

    assert insufficient.status == InvestigationStatus.INSUFFICIENT_EVIDENCE
    assert insufficient.disposition is None
    assert insufficient.model_call_count == 0

    trajectories = {
        (
            rejected.status,
            rejected.disposition,
            tuple(rejected.completed_tests),
            rejected.model_call_count,
        ),
        (
            agent_reviewed.status,
            agent_reviewed.disposition,
            tuple(agent_reviewed.completed_tests),
            agent_reviewed.model_call_count,
        ),
        (
            insufficient.status,
            insufficient.disposition,
            tuple(insufficient.completed_tests),
            insufficient.model_call_count,
        ),
    }
    assert len(trajectories) == 3
