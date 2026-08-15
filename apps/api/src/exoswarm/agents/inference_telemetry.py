from __future__ import annotations

from statistics import median

from exoswarm.domain.models import InferenceRate, InferenceSummary, InferenceTraceRecord


def _rate(numerator: int, denominator: int) -> InferenceRate:
    return InferenceRate(
        numerator=numerator,
        denominator=denominator,
        rate=(numerator / denominator if denominator else "not_applicable"),
    )


def derive_inference_summary(records: list[InferenceTraceRecord]) -> InferenceSummary:
    """Derive run metrics exclusively from persisted-safe attempt records."""

    if not records:
        return InferenceSummary()

    live_records = [record for record in records if not record.fallback_used]
    identity_records = live_records or records
    providers = sorted({record.provider for record in identity_records})
    identities = sorted({record.model_identity for record in identity_records})
    all_input_measured = all(record.input_tokens is not None for record in records)
    all_output_measured = all(record.output_tokens is not None for record in records)
    all_latency_measured = all(record.latency_ms is not None for record in records)
    measured_input = [record.input_tokens for record in records if record.input_tokens is not None]
    measured_output = [
        record.output_tokens for record in records if record.output_tokens is not None
    ]
    measured_latency = [record.latency_ms for record in records if record.latency_ms is not None]
    decisions = {
        (record.step_id, record.role, record.context_fingerprint) for record in records
    }
    first_attempt_by_decision: dict[tuple[str, str, str], InferenceTraceRecord] = {}
    for record in records:
        if record.fallback_used:
            continue
        first_attempt_by_decision.setdefault(
            (record.step_id, record.role, record.context_fingerprint), record
        )
    first_attempts = list(first_attempt_by_decision.values())
    repair_eligible = {
        (record.step_id, record.role, record.context_fingerprint)
        for record in records
        if not record.fallback_used
        and record.attempt_kind == "primary"
        and record.status in {"INVALID", "OUTPUT_TRUNCATED"}
    }
    repairs = {
        (record.step_id, record.role, record.context_fingerprint)
        for record in records
        if not record.fallback_used and record.attempt_kind == "repair"
    }
    fallback_decisions = {
        (record.step_id, record.role, record.context_fingerprint)
        for record in records
        if record.fallback_used
    }

    return InferenceSummary(
        provider=providers[0] if len(providers) == 1 else "mixed:" + ",".join(providers),
        model_identity=(identities[0] if len(identities) == 1 else "mixed:" + ",".join(identities)),
        agent_calls=len(records),
        input_tokens=sum(measured_input) if all_input_measured else "not_measured",
        output_tokens=sum(measured_output) if all_output_measured else "not_measured",
        median_input_tokens=(
            float(median(measured_input)) if all_input_measured else "not_measured"
        ),
        max_input_tokens=max(measured_input) if all_input_measured else "not_measured",
        median_latency_ms=(
            float(median(measured_latency)) if all_latency_measured else "not_measured"
        ),
        first_attempt_schema_valid=_rate(
            sum(record.schema_valid for record in first_attempts), len(first_attempts)
        ),
        repairs=_rate(len(repairs), len(repair_eligible)),
        fallbacks=_rate(len(fallback_decisions), len(decisions)),
        provider_errors_timeouts=sum(
            record.status in {"PROVIDER_ERROR", "TIMEOUT"} for record in records
        ),
        raw_light_curve_samples_sent=sum(
            record.raw_light_curve_samples_sent for record in records
        ),
    )


def concise_inference_summary(summary: InferenceSummary) -> str:
    return (
        "INFERENCE LAYER — "
        f"{summary.provider}; model={summary.model_identity}; calls={summary.agent_calls}; "
        f"tokens={summary.input_tokens}/{summary.output_tokens}; "
        f"median_latency_ms={summary.median_latency_ms}; "
        f"repairs={summary.repairs.numerator}/{summary.repairs.denominator}; "
        f"fallbacks={summary.fallbacks.numerator}/{summary.fallbacks.denominator}; "
        f"provider_errors_timeouts={summary.provider_errors_timeouts}; raw_samples=0"
    )
