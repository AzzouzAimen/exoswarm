from __future__ import annotations

import json

from pydantic import BaseModel

from exoswarm.agents.context import AgentContextPacket
from exoswarm.agents.skeptic import SafeRepairFeedback

CRITIC_PROMPT_VERSION = "critic-review-v1"


def build_critic_messages(
    *,
    context: AgentContextPacket,
    output_schema: type[BaseModel],
    repair_feedback: SafeRepairFeedback | None = None,
) -> list[dict[str, str]]:
    """Build an independent, versioned Critic review request."""

    system = (
        "You are ExoSwarm's Critic. Independently review the Skeptic proposal. Check its "
        "relevance to the strongest unresolved alternative, duplication, deterministic "
        "preconditions, cost justification, and whether possible results can actually "
        "discriminate the competing hypotheses. APPROVE only when all checks pass; otherwise "
        "REVISE with at most one allowed alternative or VETO. Use only supplied evidence and "
        "experiment metadata. Deterministic Python owns measurements, costs, permissions, and "
        "execution. Never calculate or invent measurements. Return one JSON object exactly "
        "matching the schema: no markdown, extra keys, hidden reasoning, or confidence percent."
    )
    if repair_feedback is not None:
        system += " This is the single repair attempt; use only the bounded repair feedback."
    payload: dict[str, object] = {
        "prompt_version": CRITIC_PROMPT_VERSION,
        "review_protocol": {
            "checks": [
                "relevance",
                "duplication",
                "preconditions",
                "cost_justification",
                "hypothesis_discrimination",
            ],
            "allowed_verdicts": ["APPROVE", "REVISE", "VETO"],
            "maximum_revisions": 1,
            "reasoning_output": "concise_reason and bounded reason fields only",
        },
        "context": context.model_dump(mode="json"),
        "output_schema": output_schema.model_json_schema(),
    }
    if repair_feedback is not None:
        payload["repair_feedback"] = repair_feedback.model_dump(mode="json")
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": json.dumps(payload, separators=(",", ":"), sort_keys=True),
        },
    ]
