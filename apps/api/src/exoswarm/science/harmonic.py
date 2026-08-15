from __future__ import annotations

from dataclasses import dataclass

from exoswarm.science.contracts import not_implemented_result


@dataclass(frozen=True, slots=True)
class HarmonicRelation:
    relation: str
    ratio: float
    relative_error: float


def classify_harmonic_relation(
    candidate_period_days: float,
    reference_period_days: float,
    *,
    relative_tolerance: float = 0.02,
) -> HarmonicRelation:
    """Classify equality, half-period, or double-period agreement explicitly."""

    if candidate_period_days <= 0 or reference_period_days <= 0:
        raise ValueError("periods must be positive")
    if relative_tolerance <= 0:
        raise ValueError("relative tolerance must be positive")
    ratio = candidate_period_days / reference_period_days
    relations = {"HALF_PERIOD": 0.5, "SAME_PERIOD": 1.0, "DOUBLE_PERIOD": 2.0}
    relation, expected = min(relations.items(), key=lambda item: abs(ratio - item[1]))
    relative_error = abs(ratio - expected) / expected
    if relative_error > relative_tolerance:
        relation = "NONE"
    return HarmonicRelation(relation=relation, ratio=ratio, relative_error=relative_error)


def test_harmonics(run_id, action_id, target_id, parameters):
    return not_implemented_result(
        tool_name="harmonic_test",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )
