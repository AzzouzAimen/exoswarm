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


class ExecutionIsolation(StrEnum):
    THREAD = "THREAD"
    SUBPROCESS = "SUBPROCESS"


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
    execution_isolation: ExecutionIsolation = ExecutionIsolation.THREAD
    max_retries: int = 0
    idempotent: bool = True
    runtime_input_schema: type[BaseModel] | None = None
    mandatory_test: str | None = None
    adaptive: bool = False
    cost_units: int = 0
    implemented: bool = True
    required_target_capabilities: frozenset[str] = frozenset()
    required_completed_tests: frozenset[str] = frozenset()
    order: int = 100

    def __post_init__(self) -> None:
        if isinstance(self.cost_units, bool) or not isinstance(self.cost_units, int):
            raise TypeError("scientific tool cost_units must be an integer")
        if self.cost_units < 0:
            raise ValueError("scientific tool cost_units cannot be negative")
        if self.adaptive and self.cost_units == 0:
            raise ValueError("adaptive scientific tools must cost at least one unit")


def unavailable_tool_result(
    *, tool_name: str, run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
) -> ScientificToolResult:
    """Return a typed unavailable-capability result without fabricated measurements."""

    return ScientificToolResult(
        tool_name=tool_name,
        status=ToolStatus.NOT_IMPLEMENTED,
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        method="unavailable:not-implemented",
        parameters=parameters,
        provenance=Provenance(
            input_artifact_refs=[],
            code_version="unavailable-capability-v1",
            source_data_ref="unavailable:not-implemented",
        ),
        reason=f"{tool_name} is unavailable for the configured data inputs.",
    )
