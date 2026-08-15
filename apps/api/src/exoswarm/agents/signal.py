"""Bounded shadow-mode Signal Analyst prompt adapter."""

from pydantic import BaseModel

from exoswarm.agents.role_context import SignalContext

SIGNAL_PROMPT_VERSION = "signal-assessment-v1"


def build_signal_messages(
    *, context: SignalContext, output_schema: type[BaseModel], repair_feedback=None
) -> list[dict[str, str]]:
    from exoswarm.agents.prompt_registry import render_role_prompt

    return render_role_prompt(
        role="signal",
        context=context,
        output_schema=output_schema,
        repair_feedback=repair_feedback,
    ).messages


__all__ = ["SIGNAL_PROMPT_VERSION", "build_signal_messages"]
