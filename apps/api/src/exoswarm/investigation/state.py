from exoswarm.domain.enums import InvestigationStatus
from exoswarm.domain.models import InvestigationState

_FAILURE_TRANSITIONS = frozenset(
    {
        InvestigationStatus.FAILED,
        InvestigationStatus.INSUFFICIENT_EVIDENCE,
        InvestigationStatus.BUDGET_EXHAUSTED,
    }
)

ALLOWED_STATUS_TRANSITIONS: dict[InvestigationStatus, frozenset[InvestigationStatus]] = {
    InvestigationStatus.INITIALIZED: frozenset(
        {
            InvestigationStatus.PREPARING,
            InvestigationStatus.VETTING_MANDATORY,
            InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT,
            InvestigationStatus.UPDATING_EVIDENCE,
            *_FAILURE_TRANSITIONS,
        }
    ),
    InvestigationStatus.PREPARING: frozenset(
        {
            InvestigationStatus.SEARCHING,
            InvestigationStatus.VETTING_MANDATORY,
            *_FAILURE_TRANSITIONS,
        }
    ),
    InvestigationStatus.SEARCHING: frozenset(
        {InvestigationStatus.UPDATING_EVIDENCE, *_FAILURE_TRANSITIONS}
    ),
    InvestigationStatus.VETTING_MANDATORY: frozenset(
        {InvestigationStatus.RUNNING_TOOL, *_FAILURE_TRANSITIONS}
    ),
    InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT: frozenset(
        {
            InvestigationStatus.WAITING_FOR_CRITIC,
            InvestigationStatus.READY_TO_LOCK,
            *_FAILURE_TRANSITIONS,
        }
    ),
    InvestigationStatus.WAITING_FOR_CRITIC: frozenset(
        {
            InvestigationStatus.RUNNING_TOOL,
            InvestigationStatus.READY_TO_LOCK,
            *_FAILURE_TRANSITIONS,
        }
    ),
    InvestigationStatus.RUNNING_TOOL: frozenset(
        {InvestigationStatus.UPDATING_EVIDENCE, *_FAILURE_TRANSITIONS}
    ),
    InvestigationStatus.UPDATING_EVIDENCE: frozenset(
        {
            InvestigationStatus.VETTING_MANDATORY,
            InvestigationStatus.SELECTING_ADAPTIVE_EXPERIMENT,
            InvestigationStatus.READY_TO_LOCK,
            *_FAILURE_TRANSITIONS,
        }
    ),
    InvestigationStatus.READY_TO_LOCK: frozenset({InvestigationStatus.RESULT_LOCKED}),
    InvestigationStatus.RESULT_LOCKED: frozenset({InvestigationStatus.REVEALED}),
    InvestigationStatus.REVEALED: frozenset(),
    InvestigationStatus.INSUFFICIENT_EVIDENCE: frozenset(),
    InvestigationStatus.REJECTED: frozenset(),
    InvestigationStatus.FAILED: frozenset(),
    InvestigationStatus.BUDGET_EXHAUSTED: frozenset(),
}


def validate_status_transition(
    current: InvestigationStatus, requested: InvestigationStatus
) -> None:
    if current == requested:
        return
    if requested not in ALLOWED_STATUS_TRANSITIONS[current]:
        raise ValueError(f"invalid investigation status transition: {current} -> {requested}")


__all__ = ["ALLOWED_STATUS_TRANSITIONS", "InvestigationState", "validate_status_transition"]
