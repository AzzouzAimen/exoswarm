from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from exoswarm.domain.models import InvestigationState


class AgentContextPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    opaque_target_id: str
    status: str
    evidence_refs: tuple[str, ...]
    completed_tests: tuple[str, ...]
    available_tests: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    context_version: str


def assemble_context(state: InvestigationState) -> AgentContextPacket:
    """Build the explicitly agent-safe subset of durable state."""

    return AgentContextPacket(
        run_id=state.run_id,
        opaque_target_id=state.opaque_target_id,
        status=state.status,
        evidence_refs=tuple(state.evidence_refs),
        completed_tests=tuple(state.completed_tests),
        available_tests=tuple(state.available_tests),
        unresolved_questions=tuple(state.unresolved_questions),
        context_version=state.context_version,
    )

