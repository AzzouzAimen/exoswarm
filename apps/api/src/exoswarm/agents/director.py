"""Deterministic routing adapter for the investigation LangGraph.

The Scientific Director does not call a model and does not decide scientific
policy.  The controller supplies a compact durable-state view plus the next
guarded policy action; this module translates that information into a graph
route.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from exoswarm.domain.enums import CriticVerdict, InvestigationStatus


class DirectorRoute(StrEnum):
    RECOVER_PREPARED = "RECOVER_PREPARED"
    RUN_MANDATORY = "RUN_MANDATORY"
    CALL_SKEPTIC = "CALL_SKEPTIC"
    RESUME_CRITIC = "RESUME_CRITIC"
    EXECUTE_APPROVED_ACTION = "EXECUTE_APPROVED_ACTION"
    EVALUATE_RESULT = "EVALUATE_RESULT"
    FINALIZE = "FINALIZE"
    TERMINATE = "TERMINATE"
    NOOP_TERMINAL = "NOOP_TERMINAL"


class FreshCycleRoute(StrEnum):
    """Controller-owned policy outcome for a newly begun durable cycle."""

    RUN_MANDATORY = "RUN_MANDATORY"
    CALL_SKEPTIC = "CALL_SKEPTIC"
    FINALIZE = "FINALIZE"
    TERMINATE = "TERMINATE"


@dataclass(frozen=True, slots=True)
class DirectorStateView:
    """Only the durable lifecycle facts needed to choose the next graph node."""

    status: InvestigationStatus
    terminal: bool
    has_prepared_execution: bool
    has_uncommitted_result: bool
    skeptic_decision_id: str | None
    critic_decision_id: str | None
    critic_verdict: CriticVerdict | None
    critic_requires_resolution: bool = False
    fresh_cycle_route: FreshCycleRoute | None = None


def determine_director_route(view: DirectorStateView) -> DirectorRoute:
    """Translate durable lifecycle state into one typed LangGraph route."""

    if view.terminal:
        return DirectorRoute.NOOP_TERMINAL
    if view.has_prepared_execution:
        return DirectorRoute.RECOVER_PREPARED
    if view.has_uncommitted_result:
        return DirectorRoute.EVALUATE_RESULT
    if view.skeptic_decision_id is not None:
        if view.critic_decision_id is None:
            return DirectorRoute.RESUME_CRITIC
        if view.critic_requires_resolution:
            return DirectorRoute.RESUME_CRITIC
        if view.critic_verdict == CriticVerdict.VETO:
            return DirectorRoute.FINALIZE
        return DirectorRoute.EXECUTE_APPROVED_ACTION
    if view.fresh_cycle_route is None:
        raise ValueError("non-terminal durable state has no controller policy route")
    return DirectorRoute(view.fresh_cycle_route)


__all__ = [
    "DirectorRoute",
    "DirectorStateView",
    "FreshCycleRoute",
    "determine_director_route",
]
