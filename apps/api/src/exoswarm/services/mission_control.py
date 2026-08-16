from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from exoswarm.api.mission_control_models import (
    AgentCheckpointView,
    BudgetView,
    CandidateSignalView,
    CriticDecisionView,
    EvidenceView,
    FailureView,
    LockProjection,
    MeasurementView,
    MissionControlSnapshot,
    PlotReadout,
    PlotTraceView,
    PlotView,
    RevealProjection,
    SkepticDecisionView,
    ToolExecutionView,
)
from exoswarm.domain.enums import LockState
from exoswarm.domain.models import (
    AgentDecisionRecord,
    EvidenceRecord,
    InvestigationState,
    Measurement,
)
from exoswarm.investigation.controller import InvestigationController
from exoswarm.investigation.runner import InvestigationRunService
from exoswarm.science.plot_projection import (
    PLOT_MODES,
    PlotMode,
    candidate_plot,
    load_plot_artifact,
)

_DIAGNOSTIC_KEYS = frozenset(
    {
        "interpretation_code",
        "phase_convention",
        "parity_convention",
        "input_sample_count",
        "retained_sample_count",
        "quality_removed_count",
        "invalid_removed_count",
        "outlier_removed_count",
        "odd_transit_count",
        "even_transit_count",
        "odd_in_transit_sample_count",
        "even_in_transit_sample_count",
        "baseline_sample_count",
        "tested_phase_count",
        "candidate_period_days",
        "candidate_epoch_btjd",
        "candidate_duration_hours",
        "strongest_alternative",
        "trial_factors",
    }
)


class MissionControlService:
    def __init__(
        self, controller: InvestigationController, runner: InvestigationRunService
    ) -> None:
        self.controller = controller
        self.runner = runner

    def snapshot(self, run_id: str) -> MissionControlSnapshot:
        with self.controller.run_boundary(run_id):
            state = self.controller.get(run_id)
            evidence = self.controller.artifacts.read_evidence(state)
            records = self.controller.artifacts.read_agent_decisions(state)
            events = self.controller.events(run_id)
            artifacts = self.controller.artifacts.list_artifacts(state)
            artifact_ids = {item.relative_path: item.artifact_id for item in artifacts}
            evidence_views = [self._evidence_view(item, artifact_ids) for item in evidence]
            lock = self._lock_projection(state)
            reveal = self._reveal_projection(state)
            return MissionControlSnapshot(
                run_id=state.run_id,
                opaque_target_id=state.opaque_target_id,
                status=state.status,
                lock_state=state.lock_state,
                disposition=state.disposition,
                terminal_reason=state.terminal_reason,
                completed_tests=list(state.completed_tests),
                available_tests=list(state.available_tests),
                evidence_refs=list(state.evidence_refs),
                active_hypotheses=list(state.active_hypotheses),
                strongest_unresolved_alternative=state.strongest_unresolved_alternative,
                unresolved_questions=list(state.unresolved_questions),
                candidate_signals=[
                    self._candidate_view(item, artifact_ids)
                    for item in state.candidate_signals
                ],
                evidence=evidence_views,
                accepted_decisions=[
                    self._skeptic_view(item) for item in state.accepted_decisions
                ],
                critic_decisions=[
                    self._critic_view(item) for item in state.critic_decisions
                ],
                role_checkpoints=self._checkpoint_views(state, records, events),
                tool_executions=[self._tool_view(item) for item in state.tool_executions],
                failures=[self._failure_view(item) for item in state.failures],
                inference_summary=state.inference_summary,
                budgets=BudgetView(
                    step_count=state.step_count,
                    adaptive_cost_units_used=state.adaptive_cost_units_used,
                    adaptive_cost_units_remaining=state.adaptive_cost_units_remaining,
                    max_adaptive_cost_units=state.max_adaptive_cost_units,
                    adaptive_experiments_used=state.adaptive_experiments_used,
                    max_adaptive_experiments=state.max_adaptive_experiments,
                    model_call_count=state.model_call_count,
                    max_model_calls=state.max_model_calls,
                    tool_call_count=state.tool_call_count,
                    max_tool_calls=state.max_tool_calls,
                    critic_revision_count=state.critic_revision_count,
                    max_critic_revisions=state.max_critic_revisions,
                    model_retry_count=state.model_retry_count,
                    max_model_retries=state.max_model_retries,
                ),
                execution=self.runner.inspect(run_id),
                lock=lock,
                reveal=reveal,
                available_plot_modes=self._available_plot_modes(state, evidence),
                plot_evidence_refs=[
                    item.evidence_id for item in evidence if item.tool_name == "search_bls"
                ],
                last_sequence=len(events),
                updated_at=state.updated_at,
            )

    def plot(self, run_id: str, mode: str) -> PlotView:
        if mode not in PLOT_MODES:
            raise ValueError(f"unknown plot mode: {mode}")
        selected = mode  # Narrowed after allowlist validation.
        state = self.controller.get(run_id)
        evidence = self.controller.artifacts.read_evidence(state)
        if selected in {"raw", "bls", "phase-fold"}:
            record = self._latest_success(evidence, "search_bls")
            if record is None:
                return self._unavailable(
                    selected, "search_bls has not produced a successful candidate artifact"
                )
            artifact_ref = record.result.diagnostics.get("masks_artifact_ref")
            if not isinstance(artifact_ref, str):
                return self._unavailable(selected, "candidate artifact reference is unavailable")
            try:
                artifact = load_plot_artifact(
                    self.controller.artifacts.resolve_science_artifact(state, artifact_ref)
                )
            except (OSError, ValueError) as exc:
                return self._unavailable(selected, str(exc))
            series = candidate_plot(
                selected, artifact, evidence_ref=record.evidence_id, artifact_ref=artifact_ref
            )
            return PlotView(
                mode=selected,
                available=True,
                evidence_refs=[record.evidence_id, self._artifact_id(state, artifact_ref)],
                traces=[
                    PlotTraceView(
                        name=series.name, x=series.x, y=series.y, kind=series.kind, tone="science"
                    )
                ],
                x_label={"raw": "BTJD", "bls": "period (days)", "phase-fold": "orbital phase"}[
                    selected
                ],
                y_label={
                    "raw": "relative flux fraction",
                    "bls": "periodogram depth SNR",
                    "phase-fold": "relative flux fraction",
                }[selected],
                annotation=(
                    "Deterministic Astropy BoxLeastSquares repeat search."
                    if selected == "bls"
                    else "Phase zero is mid-transit; phase range is [-0.5, 0.5)."
                    if selected == "phase-fold"
                    else "Cleaned light curve; flux is relative to deterministic normalization."
                ),
                readouts=self._candidate_readouts(record),
            )
        if selected == "odd-even":
            record = self._latest_success_or_negative(evidence, "odd_even")
            return self._summary_plot(
                selected, record, ("odd_depth", "even_depth"), ("odd depth", "even depth")
            )
        if selected == "secondary":
            record = self._latest_success_or_negative(evidence, "secondary_eclipse")
            return self._summary_plot(
                selected,
                record,
                ("strongest_secondary_phase", "strongest_secondary_depth"),
                ("phase", "depth"),
            )
        record = self._latest_success_or_negative(evidence, "harmonic_test")
        return self._summary_plot(
            selected,
            record,
            ("half_period_snr", "same_period_snr", "double_period_snr"),
            ("P/2 SNR", "P SNR", "2P SNR"),
        )

    def _evidence_view(self, record: EvidenceRecord, artifact_ids: dict[str, str]) -> EvidenceView:
        refs = [
            self._safe_ref(measurement.evidence_ref, artifact_ids)
            for measurement in record.result.measurements.values()
        ]
        refs = list(dict.fromkeys(ref for ref in refs if ref is not None))
        measurements = {
            name: self._measurement_view(item, artifact_ids, record.evidence_id)
            for name, item in record.result.measurements.items()
        }
        diagnostics = {
            key: value
            for key, value in record.result.diagnostics.items()
            if key in _DIAGNOSTIC_KEYS and isinstance(value, (str, int, float, bool))
        }
        summary = record.result.reason or record.interpretation_code or record.result.status.value
        return EvidenceView(
            evidence_id=record.evidence_id,
            timestamp=record.timestamp,
            step_id=record.step_id,
            action_id=record.action_id,
            tool_name=record.tool_name,
            status=record.tool_status,
            interpretation_code=record.interpretation_code,
            summary=summary,
            measurements=measurements,
            diagnostics=diagnostics,
            method=record.result.method,
            evidence_ref=record.evidence_id,
            artifact_refs=refs,
        )

    def _measurement_view(
        self,
        measurement: Measurement,
        artifact_ids: dict[str, str],
        evidence_id: str,
    ) -> MeasurementView:
        unit = measurement.unit or ""
        return MeasurementView(
            value=measurement.value,
            display_value=f"{measurement.value:g} {unit}".strip()
            if isinstance(measurement.value, (int, float))
            and not isinstance(measurement.value, bool)
            else str(measurement.value),
            unit=measurement.unit,
            uncertainty=measurement.uncertainty,
            tolerance=measurement.tolerance,
            evidence_ref=self._safe_ref(measurement.evidence_ref, artifact_ids) or evidence_id,
        )

    def _candidate_view(self, candidate: Any, artifact_ids: dict[str, str]) -> CandidateSignalView:
        return CandidateSignalView(
            candidate_id=candidate.candidate_id,
            evidence_refs=list(candidate.evidence_refs),
            measurements={
                name: MeasurementView(
                    value=item.value,
                    display_value=f"{item.value:g} {item.unit or ''}".strip()
                    if isinstance(item.value, (int, float)) and not isinstance(item.value, bool)
                    else str(item.value),
                    unit=item.unit,
                    uncertainty=item.uncertainty,
                    tolerance=item.tolerance,
                    evidence_ref=self._safe_ref(item.evidence_ref, artifact_ids) or "unavailable",
                )
                for name, item in candidate.measurements.items()
            },
        )

    @staticmethod
    def _skeptic_view(decision: Any) -> SkepticDecisionView:
        return SkepticDecisionView(
            decision_id=decision.decision_id,
            step_id=decision.step_id,
            context_version=decision.context_version,
            hypothesis_under_test=decision.hypothesis_under_test,
            requested_experiment=decision.requested_experiment,
            reason_code=decision.reason_code,
            expected_discriminating_result=decision.expected_discriminating_result,
            expected_information_value=decision.expected_information_value.value,
            priority=decision.priority.value,
            cost_of_selected_experiment=decision.cost_of_selected_experiment,
            concise_reason=decision.concise_reason,
            supporting_evidence_refs=list(decision.supporting_evidence_refs),
            contradicting_evidence_refs=list(decision.contradicting_evidence_refs),
        )

    @staticmethod
    def _critic_view(decision: Any) -> CriticDecisionView:
        return CriticDecisionView(
            decision_id=decision.decision_id,
            step_id=decision.step_id,
            context_version=decision.context_version,
            skeptic_decision_id=decision.skeptic_decision_id,
            verdict=decision.verdict,
            reason_code=decision.reason_code,
            concise_reason=decision.concise_reason,
            revised_experiment=decision.revised_experiment,
            supporting_evidence_refs=list(decision.supporting_evidence_refs),
            contradicting_evidence_refs=list(decision.contradicting_evidence_refs),
        )

    @staticmethod
    def _tool_view(item: Any) -> ToolExecutionView:
        return ToolExecutionView(
            action_id=item.action_id,
            step_id=item.step_id,
            tool_name=item.tool_name,
            status=item.status,
            adaptive=item.adaptive,
            adaptive_cost_units=item.adaptive_cost_units,
            agent_decision_id=item.agent_decision_id,
            critic_decision_id=item.critic_decision_id,
            result_status=item.result_status,
            evidence_ref=item.evidence_ref,
            failure_kind=item.failure_kind.value if item.failure_kind else None,
            failure_reason=item.failure_reason,
        )

    @staticmethod
    def _failure_view(item: Any) -> FailureView:
        return FailureView(
            step_id=item.step_id,
            kind=item.kind.value,
            concise_reason=item.concise_reason,
            recoverable=item.recoverable,
            retry_count=item.retry_count,
        )

    def _checkpoint_views(
        self, state: InvestigationState, records: list[AgentDecisionRecord], events: Iterable[Any]
    ) -> list[AgentCheckpointView]:
        attempts = [event.payload for event in events if event.type == "inference.attempt"]
        views: list[AgentCheckpointView] = []
        for checkpoint in state.role_checkpoints:
            record = next(
                (
                    item
                    for item in records
                    if item.role == checkpoint.role
                    and item.phase == checkpoint.phase
                    and item.context_version == checkpoint.context_version
                ),
                None,
            )
            decision = record.decision if record else None
            attempt = None
            if record is not None:
                attempt = next(
                    (
                        item
                        for item in reversed(attempts)
                        if item.get("role") == checkpoint.role.value
                        and item.get("step_id") == record.step_id
                    ),
                    None,
                )
            views.append(
                AgentCheckpointView(
                    role=checkpoint.role,
                    phase=checkpoint.phase,
                    status=checkpoint.status,
                    decision_id=checkpoint.decision_id,
                    context_version=checkpoint.context_version,
                    evidence_refs=list(record.evidence_refs) if record else [],
                    summary=self._decision_summary(decision),
                    action=(decision or {}).get("requested_experiment") if decision else None,
                    expected_discriminator=(decision or {}).get("expected_discriminating_result")
                    if decision
                    else None,
                    model_identity=record.model_identity if record else None,
                    provider=attempt.get("provider") if attempt else None,
                    latency_ms=attempt.get("latency_ms") if attempt else None,
                    schema_valid=attempt.get("schema_valid") if attempt else None,
                    fallback_code=record.fallback_code if record else None,
                )
            )
        return views

    @staticmethod
    def _decision_summary(decision: dict[str, Any] | None) -> str | None:
        if not decision:
            return None
        return str(
            decision.get("concise_reason")
            or decision.get("mission_brief")
            or decision.get("observation_limitations")
            or ""
        )

    def _lock_projection(self, state: InvestigationState) -> LockProjection:
        if state.lock_state not in {LockState.RESULT_LOCKED, LockState.CATALOG_REVEALED}:
            return LockProjection(state=state.lock_state, reveal_available=False)
        receipt = self.controller.result_lock.receipt(state)
        return LockProjection(
            state=state.lock_state,
            sha256=receipt.sha256,
            locked_at=receipt.locked_at,
            reveal_available=state.lock_state
            in {LockState.RESULT_LOCKED, LockState.CATALOG_REVEALED},
        )

    def _reveal_projection(self, state: InvestigationState) -> RevealProjection | None:
        if state.lock_state != LockState.CATALOG_REVEALED:
            return None
        reveal = self.controller.catalog_gate.read_reveal(state)
        return RevealProjection(**reveal.model_dump(mode="python"))

    def _available_plot_modes(
        self, state: InvestigationState, evidence: list[EvidenceRecord]
    ) -> list[str]:
        modes: list[str] = []
        candidate = self._latest_success(evidence, "search_bls")
        if candidate is not None and self._candidate_plot_is_usable(state, candidate):
            modes.extend(("raw", "bls", "phase-fold"))
        summaries = {
            "odd-even": ("odd_even", ("odd_depth", "even_depth")),
            "secondary": (
                "secondary_eclipse",
                ("strongest_secondary_phase", "strongest_secondary_depth"),
            ),
            "harmonic": (
                "harmonic_test",
                ("half_period_snr", "same_period_snr", "double_period_snr"),
            ),
        }
        for mode, (tool_name, names) in summaries.items():
            record = self._latest_success_or_negative(evidence, tool_name)
            if self._summary_is_usable(record, names):
                modes.append(mode)
        return modes

    @staticmethod
    def _latest_success(evidence: list[EvidenceRecord], tool_name: str) -> EvidenceRecord | None:
        return next(
            (
                item
                for item in reversed(evidence)
                if item.tool_name == tool_name and item.tool_status.value == "SUCCESS"
            ),
            None,
        )

    @staticmethod
    def _latest_success_or_negative(
        evidence: list[EvidenceRecord], tool_name: str
    ) -> EvidenceRecord | None:
        return next((item for item in reversed(evidence) if item.tool_name == tool_name), None)

    def _summary_plot(
        self,
        mode: PlotMode,
        record: EvidenceRecord | None,
        names: tuple[str, ...],
        labels: tuple[str, ...],
    ) -> PlotView:
        if not self._summary_is_usable(record, names):
            return self._unavailable(mode, f"{mode} has not produced usable deterministic evidence")
        assert record is not None
        measurements = [record.result.measurements[name] for name in names]
        values = [float(measurement.value) for measurement in measurements]
        return PlotView(
            mode=mode,
            available=True,
            evidence_refs=[record.evidence_id],
            traces=[],
            x_label="",
            y_label="",
            annotation="Measurement readouts from the completed diagnostics.",
            readouts=[
                PlotReadout(
                    label=label,
                    value=f"{value:g} {measurement.unit or ''}".strip(),
                    evidence_ref=record.evidence_id,
                )
                for label, value, measurement in zip(
                    labels, values, measurements, strict=True
                )
            ],
        )

    def _candidate_plot_is_usable(self, state: InvestigationState, record: EvidenceRecord) -> bool:
        artifact_ref = record.result.diagnostics.get("masks_artifact_ref")
        if not isinstance(artifact_ref, str):
            return False
        try:
            path = self.controller.artifacts.resolve_science_artifact(state, artifact_ref)
            load_plot_artifact(path)
        except (OSError, ValueError):
            return False
        return True

    @staticmethod
    def _summary_is_usable(
        record: EvidenceRecord | None, names: tuple[str, ...]
    ) -> bool:
        if record is None or record.tool_status.value == "FAILED":
            return False
        measurements = record.result.measurements
        if not all(name in measurements for name in names):
            return False
        return all(
            isinstance(measurements[name].value, (int, float))
            and not isinstance(measurements[name].value, bool)
            and math.isfinite(float(measurements[name].value))
            for name in names
        )

    @staticmethod
    def _unavailable(mode: PlotMode, reason: str) -> PlotView:
        return PlotView(
            mode=mode,
            available=False,
            unavailable_reason=reason,
            x_label="",
            y_label="",
            annotation="No deterministic plot data is available.",
        )

    @staticmethod
    def _safe_ref(ref: str | None, artifact_ids: dict[str, str]) -> str | None:
        if ref is None:
            return None
        return artifact_ids.get(ref, ref if ref.startswith("evidence_") else None)

    def _artifact_id(self, state: InvestigationState, ref: str) -> str:
        return next(
            item.artifact_id
            for item in self.controller.artifacts.list_artifacts(state)
            if item.relative_path == ref
        )

    def _candidate_readouts(self, record: EvidenceRecord) -> list[PlotReadout]:
        return [
            PlotReadout(
                label=name,
                value=f"{measurement.value:g} {measurement.unit or ''}".strip(),
                evidence_ref=record.evidence_id,
            )
            for name, measurement in record.result.measurements.items()
            if name in {"period", "depth", "duration", "snr"}
            and isinstance(measurement.value, (int, float))
            and not isinstance(measurement.value, bool)
        ]


__all__ = ["MissionControlService"]
