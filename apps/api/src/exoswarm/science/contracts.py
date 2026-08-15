from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from exoswarm.domain.enums import ToolStatus
from exoswarm.domain.models import Provenance, ScientificToolResult


class SideEffectLevel(StrEnum):
    READ_ONLY = "READ_ONLY"
    ARTIFACT_WRITE = "ARTIFACT_WRITE"


class ApprovalRequirement(StrEnum):
    NONE = "NONE"
    RUNTIME_POLICY = "RUNTIME_POLICY"


ToolHandler = Callable[[str, str, str, dict[str, Any]], ScientificToolResult]


class NoParameters(BaseModel):
    """Explicit strict contract for actions that accept no model-selected parameters."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True, slots=True)
class ScientificToolSpec:
    name: str
    handler: ToolHandler
    parameter_schema: type[BaseModel]
    side_effect_level: SideEffectLevel = SideEffectLevel.ARTIFACT_WRITE
    approval: ApprovalRequirement = ApprovalRequirement.RUNTIME_POLICY
    required_scopes: frozenset[str] = frozenset({"science:execute"})
    timeout_seconds: int = 60
    max_retries: int = 0
    idempotent: bool = True
    runtime_input_schema: type[BaseModel] | None = None
    mandatory_test: str | None = None
    adaptive: bool = False
    required_completed_tests: frozenset[str] = frozenset()
    order: int = 100


def not_implemented_result(
    *, tool_name: str, run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
) -> ScientificToolResult:
    """Return an explicit empty scaffold result; never fabricate measurements."""

    return ScientificToolResult(
        tool_name=tool_name,
        status=ToolStatus.NOT_IMPLEMENTED,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        method="scaffold:not-implemented",
        parameters=parameters,
        provenance=Provenance(
            input_artifact_refs=[],
            code_version="scaffold",
            source_data_ref="unavailable:not-implemented",
        ),
        reason=f"{tool_name} has no numerical implementation in the repository scaffold.",
    )
