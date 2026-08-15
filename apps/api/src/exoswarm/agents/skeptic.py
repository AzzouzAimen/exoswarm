from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from exoswarm.agents.context import AgentContextPacket

SKEPTIC_PROMPT_VERSION = "skeptic-decision-v1"

RepairCategory = Literal[
    "structure",
    "identity",
    "action",
    "parameters",
    "precondition",
    "duplication",
    "budget",
]

_SAFE_REPAIR_CODES: dict[str, RepairCategory] = {
    "INVALID_MODEL_OUTPUT": "structure",
    "UNKNOWN_ACTION": "action",
    "UNAVAILABLE_ACTION": "action",
    "MALFORMED_PARAMETERS": "parameters",
    "UNAUTHORIZED_ACTION": "action",
    "PRECONDITION_FAILED": "precondition",
    "REPEATED_ACTION": "duplication",
    "BUDGET_EXHAUSTED": "budget",
}


class SafeRepairFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal[
        "INVALID_MODEL_OUTPUT",
        "UNKNOWN_ACTION",
        "UNAVAILABLE_ACTION",
        "MALFORMED_PARAMETERS",
        "UNAUTHORIZED_ACTION",
        "PRECONDITION_FAILED",
        "REPEATED_ACTION",
        "BUDGET_EXHAUSTED",
    ]
    category: RepairCategory


def safe_repair_feedback(error_code: object | None) -> SafeRepairFeedback:
    """Reduce any validation failure to a bounded, non-reflective repair signal."""

    candidate = str(error_code) if error_code is not None else "INVALID_MODEL_OUTPUT"
    if candidate not in _SAFE_REPAIR_CODES:
        candidate = "INVALID_MODEL_OUTPUT"
    return SafeRepairFeedback(
        code=candidate,  # type: ignore[arg-type]
        category=_SAFE_REPAIR_CODES[candidate],
    )


def build_skeptic_messages(
    *,
    context: AgentContextPacket,
    output_schema: type[BaseModel],
    repair_feedback: SafeRepairFeedback | None = None,
) -> list[dict[str, str]]:
    """Build the versioned Skeptic request without conversational history."""

    system = (
        "You are ExoSwarm's Skeptic. Identify the strongest unresolved non-planetary "
        "alternative, then choose the available, affordable, unexecuted action that most "
        "directly discriminates it from the planetary hypothesis. Use only supplied evidence "
        "and experiment metadata. Deterministic Python owns measurements, costs, permissions, "
        "and execution. Never calculate or invent measurements. Return one JSON object exactly "
        "matching the schema: no markdown, extra keys, hidden reasoning, or confidence percent."
    )
    if repair_feedback is not None:
        system += " This is the single repair attempt; use only the bounded repair feedback."
    payload: dict[str, object] = {
        "prompt_version": SKEPTIC_PROMPT_VERSION,
        "decision_protocol": {
            "select_only_when": "availability_reason is null and already_executed is false",
            "rank_by": "discrimination of strongest_unresolved_alternative per deterministic cost",
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
