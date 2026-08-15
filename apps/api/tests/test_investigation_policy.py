from exoswarm.domain.models import InvestigationState
from exoswarm.investigation.hypotheses import (
    decisive_interpretation,
    has_weak_planetary_interpretation,
    updated_hypotheses,
)
from exoswarm.investigation.stopping import (
    adaptive_budget_terminal_reason,
    availability_terminal_reason,
)


def test_hypothesis_rules_are_deterministic_and_preserve_unknown_evidence() -> None:
    state = InvestigationState(
        run_id="run_policy",
        opaque_target_id="TARGET-X17",
        active_hypotheses=["planetary_transit", "eclipsing_binary"],
        strongest_unresolved_alternative="eclipsing_binary",
    )

    assert updated_hypotheses(state, "ODD_EVEN_MISMATCH") == (
        ["eclipsing_binary"],
        "planetary_transit",
    )
    assert updated_hypotheses(state, "UNRECOGNIZED") == (
        state.active_hypotheses,
        state.strongest_unresolved_alternative,
    )
    assert decisive_interpretation({"CONTAMINATION_LIKELY", "ODD_EVEN_MISMATCH"}) == (
        "CONTAMINATION_LIKELY"
    )
    assert has_weak_planetary_interpretation({"CONTAMINATION_POSSIBLE"})


def test_stopping_rules_return_explicit_budget_and_availability_reasons() -> None:
    budgeted = InvestigationState(
        run_id="run_budget",
        opaque_target_id="TARGET-X17",
        max_adaptive_experiments=1,
        adaptive_experiments_used=1,
        max_adaptive_cost_units=4,
    )

    assert (
        adaptive_budget_terminal_reason(budgeted)
        == "ADAPTIVE_EXPERIMENT_COUNT_BUDGET_REACHED"
    )
    assert (
        availability_terminal_reason(has_available=False, has_unaffordable=True)
        == "NO_AFFORDABLE_VALID_ADAPTIVE_EXPERIMENT"
    )
    assert availability_terminal_reason(has_available=True, has_unaffordable=True) is None
