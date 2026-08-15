from exoswarm.domain.models import InvestigationState


def budget_terminal_reason(state: InvestigationState) -> str | None:
    if state.step_count >= state.max_steps:
        return "MAX_STEPS_REACHED"
    if state.adaptive_experiments_used >= state.max_adaptive_experiments:
        return "ADAPTIVE_EXPERIMENT_COUNT_BUDGET_REACHED"
    if state.adaptive_cost_units_remaining == 0:
        return "ADAPTIVE_COST_BUDGET_EXHAUSTED"
    return None
