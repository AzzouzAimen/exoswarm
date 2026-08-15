"""Deterministic route oracle plus a result-safe Director prompt adapter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from exoswarm.agents.role_context import DirectorContext
from exoswarm.domain.enums import CriticVerdict, InvestigationStatus

DIRECTOR_PROMPT_VERSION = "director-ratification-v1"


class DirectorRoute(StrEnum):
    RECOVER_PREPARED = "RECOVER_PREPARED"
    RUN_MANDATORY = "RUN_MANDATORY"
    CALL_SKEPTIC = "CALL_SKEPTIC"
    RUN_SPECIALIST_BRIEFING = "RUN_SPECIALIST_BRIEFING"
    CALL_DIRECTOR_BRIEFING = "CALL_DIRECTOR_BRIEFING"
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
    approved_action_is_stop: bool = False
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
        if view.approved_action_is_stop:
            return DirectorRoute.FINALIZE
        return DirectorRoute.EXECUTE_APPROVED_ACTION
    if view.fresh_cycle_route is None:
        raise ValueError("non-terminal durable state has no controller policy route")
    return DirectorRoute(view.fresh_cycle_route)


def build_director_messages(
    *, context: DirectorContext, output_schema: type[BaseModel], repair_feedback=None
) -> list[dict[str, str]]:
    """Render a Director request; the deterministic route remains binding."""

    from exoswarm.agents.prompt_registry import render_role_prompt

    return render_role_prompt(
        role="director",
        context=context,
        output_schema=output_schema,
        repair_feedback=repair_feedback,
    ).messages


__all__ = [
    "DirectorRoute",
    "DirectorStateView",
    "DIRECTOR_PROMPT_VERSION",
    "FreshCycleRoute",
    "build_director_messages",
    "determine_director_route",
]
