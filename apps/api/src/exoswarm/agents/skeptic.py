from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from exoswarm.agents.context import AgentContextPacket

SKEPTIC_PROMPT_VERSION = "skeptic-decision-v6"

RepairCategory = Literal[
    "structure",
    "identity",
    "action",
    "parameters",
    "precondition",
    "duplication",
    "budget",
    "grounding",
]

_SAFE_REPAIR_CODES: dict[str, RepairCategory] = {
    "INVALID_MODEL_OUTPUT": "structure",
    "OUTPUT_TRUNCATED": "structure",
    "UNKNOWN_ACTION": "action",
    "UNAVAILABLE_ACTION": "action",
    "MALFORMED_PARAMETERS": "parameters",
    "UNAUTHORIZED_ACTION": "action",
    "PRECONDITION_FAILED": "precondition",
    "REPEATED_ACTION": "duplication",
    "BUDGET_EXHAUSTED": "budget",
    "IDENTITY_BINDING_MISMATCH": "identity",
    "CITATION_REQUIRED": "grounding",
    "CITATION_OUT_OF_CONTEXT": "grounding",
    "NUMERIC_NARRATIVE_UNSUPPORTED": "grounding",
    "DIRECTOR_ROUTE_MISMATCH": "identity",
    "DIRECTOR_DISPOSITION_MISMATCH": "identity",
    "DIRECTOR_PHASE_MISMATCH": "identity",
    "DIRECTOR_FOCUS_OUT_OF_SCOPE": "grounding",
    "TRANSIT_CANDIDATE_OUT_OF_SCOPE": "grounding",
    "TRANSIT_ACTION_OUT_OF_SCOPE": "action",
}


class SafeRepairFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal[
        "INVALID_MODEL_OUTPUT",
        "OUTPUT_TRUNCATED",
        "UNKNOWN_ACTION",
        "UNAVAILABLE_ACTION",
        "MALFORMED_PARAMETERS",
        "UNAUTHORIZED_ACTION",
        "PRECONDITION_FAILED",
        "REPEATED_ACTION",
        "BUDGET_EXHAUSTED",
        "IDENTITY_BINDING_MISMATCH",
        "CITATION_REQUIRED",
        "CITATION_OUT_OF_CONTEXT",
        "NUMERIC_NARRATIVE_UNSUPPORTED",
        "DIRECTOR_ROUTE_MISMATCH",
        "DIRECTOR_DISPOSITION_MISMATCH",
        "DIRECTOR_PHASE_MISMATCH",
        "DIRECTOR_FOCUS_OUT_OF_SCOPE",
        "TRANSIT_CANDIDATE_OUT_OF_SCOPE",
        "TRANSIT_ACTION_OUT_OF_SCOPE",
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

    from exoswarm.agents.prompt_registry import render_role_prompt

    return render_role_prompt(
        role="skeptic",
        context=context,
        output_schema=output_schema,
        repair_feedback=repair_feedback,
    ).messages
