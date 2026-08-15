from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from exoswarm.domain.enums import InvestigationStatus, ToolStatus
from exoswarm.domain.events import InvestigationEvent
from exoswarm.domain.models import InvestigationState, ScientificToolResult


def test_scientific_result_requires_status_and_provenance() -> None:
    with pytest.raises(ValidationError):
        ScientificToolResult.model_validate(
            {
                "tool_name": "odd_even",
                "run_id": "run_1",
                "action_id": "action_1",
                "target_id": "TARGET-X17",
                "method": "fixture",
            }
        )


def test_scientific_result_accepts_explicit_not_implemented() -> None:
    result = ScientificToolResult.model_validate(
        {
            "tool_name": "odd_even",
            "status": ToolStatus.NOT_IMPLEMENTED,
            "run_id": "run_1",
            "action_id": "action_1",
            "target_id": "TARGET-X17",
            "method": "scaffold:not-implemented",
            "provenance": {
                "input_artifact_refs": [],
                "code_version": "scaffold",
                "source_data_ref": "unavailable:not-implemented",
            },
        }
    )
    assert result.measurements == {}


def test_terminal_state_requires_reason() -> None:
    with pytest.raises(ValidationError, match="terminal_reason"):
        InvestigationState(
            run_id="run_1",
            opaque_target_id="TARGET-X17",
            status=InvestigationStatus.FAILED,
        )


def test_event_requires_run_and_step_identifiers() -> None:
    with pytest.raises(ValidationError):
        InvestigationEvent(
            event_id="evt_1",
            sequence=1,
            timestamp=datetime.now(UTC),
            type="status.changed",
        )

