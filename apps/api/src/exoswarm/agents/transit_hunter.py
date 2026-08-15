"""Bounded shadow-mode Transit Hunter prompt adapter."""

from pydantic import BaseModel

from exoswarm.agents.role_context import TransitHunterContext

TRANSIT_HUNTER_PROMPT_VERSION = "transit-hunter-brief-v1"


def build_transit_hunter_messages(
    *, context: TransitHunterContext, output_schema: type[BaseModel], repair_feedback=None
) -> list[dict[str, str]]:
    from exoswarm.agents.prompt_registry import render_role_prompt

    return render_role_prompt(
        role="transit_hunter",
        context=context,
        output_schema=output_schema,
        repair_feedback=repair_feedback,
    ).messages


__all__ = ["TRANSIT_HUNTER_PROMPT_VERSION", "build_transit_hunter_messages"]
