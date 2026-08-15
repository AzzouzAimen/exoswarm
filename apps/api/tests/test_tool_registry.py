import pytest

from exoswarm.domain.enums import ToolStatus
from exoswarm.domain.errors import ToolPermissionError, UnknownToolError
from exoswarm.investigation.tool_registry import scaffold_tool_registry


def test_unknown_tool_is_rejected() -> None:
    registry = scaffold_tool_registry()
    with pytest.raises(UnknownToolError, match="unknown scientific tool"):
        registry.execute(
            "lookup_ground_truth",
            run_id="run_1",
            action_id="action_1",
            target_id="TARGET-X17",
        )


def test_registered_science_stub_fails_explicitly_without_measurements() -> None:
    result = scaffold_tool_registry().execute(
        "odd_even",
        run_id="run_1",
        action_id="action_1",
        target_id="TARGET-X17",
        granted_scopes={"science:execute"},
    )
    assert result.status == ToolStatus.NOT_IMPLEMENTED
    assert result.measurements == {}
    assert result.provenance.source_data_ref == "unavailable:not-implemented"


def test_registered_tool_requires_declared_scope() -> None:
    with pytest.raises(ToolPermissionError, match="science:execute"):
        scaffold_tool_registry().execute(
            "odd_even",
            run_id="run_1",
            action_id="action_1",
            target_id="TARGET-X17",
        )
