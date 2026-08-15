"""Bounded shadow-mode Observer prompt adapter."""

from pydantic import BaseModel

from exoswarm.agents.role_context import ObserverContext

OBSERVER_PROMPT_VERSION = "observer-assessment-v1"


def build_observer_messages(
    *, context: ObserverContext, output_schema: type[BaseModel], repair_feedback=None
) -> list[dict[str, str]]:
    from exoswarm.agents.prompt_registry import render_role_prompt

    return render_role_prompt(
        role="observer",
        context=context,
        output_schema=output_schema,
        repair_feedback=repair_feedback,
    ).messages


__all__ = ["OBSERVER_PROMPT_VERSION", "build_observer_messages"]
