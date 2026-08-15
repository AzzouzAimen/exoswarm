from __future__ import annotations

from pydantic import BaseModel

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.skeptic import SafeRepairFeedback

CRITIC_PROMPT_VERSION = "critic-review-v5"


def build_critic_messages(
    *,
    context: AgentContextPacket,
    output_schema: type[BaseModel],
    repair_feedback: SafeRepairFeedback | None = None,
) -> list[dict[str, str]]:
    """Build an independent, versioned Critic review request."""

    from exoswarm.agents.prompt_registry import render_role_prompt

    return render_role_prompt(
        role="critic",
        context=context,
        output_schema=output_schema,
        repair_feedback=repair_feedback,
    ).messages
