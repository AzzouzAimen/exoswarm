from exoswarm.domain.models import InvestigationState


def budget_terminal_reason(state: InvestigationState) -> str | None:
    if state.step_count >= state.max_steps:
        return "MAX_STEPS_REACHED"
    if state.adaptive_experiments_used >= state.max_adaptive_experiments:
        return "ADAPTIVE_EXPERIMENT_COUNT_BUDGET_REACHED"
    if state.adaptive_cost_units_remaining == 0:
        return "ADAPTIVE_COST_BUDGET_EXHAUSTED"
    return None


def adaptive_budget_terminal_reason(state: InvestigationState) -> str | None:
    if state.adaptive_experiments_used >= state.max_adaptive_experiments:
        return "ADAPTIVE_EXPERIMENT_COUNT_BUDGET_REACHED"
    if state.adaptive_cost_units_remaining == 0:
        return "ADAPTIVE_COST_BUDGET_EXHAUSTED"
    return None


def availability_terminal_reason(*, has_available: bool, has_unaffordable: bool) -> str | None:
    if has_available:
        return None
    return (
        "NO_AFFORDABLE_VALID_ADAPTIVE_EXPERIMENT"
        if has_unaffordable
        else "NO_AVAILABLE_ADAPTIVE_ACTION"
    )
