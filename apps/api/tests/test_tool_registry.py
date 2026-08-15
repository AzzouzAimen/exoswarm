import pytest

from exoswarm.domain.errors import (
    ActionValidationError,
    ToolPermissionError,
    UnknownToolError,
)
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


def test_vetting_tool_requires_backend_owned_runtime_input() -> None:
    with pytest.raises(ActionValidationError, match="backend runtime inputs"):
        scaffold_tool_registry().execute(
            "odd_even",
            run_id="run_1",
            action_id="action_1",
            target_id="TARGET-X17",
            granted_scopes={"science:execute"},
        )


def test_registered_tool_requires_declared_scope() -> None:
    with pytest.raises(ToolPermissionError, match="science:execute"):
        scaffold_tool_registry().execute(
            "odd_even",
            run_id="run_1",
            action_id="action_1",
            target_id="TARGET-X17",
        )


def test_every_production_tool_has_an_explicit_strict_parameter_schema() -> None:
    registry = scaffold_tool_registry()

    assert all(spec.parameter_schema is not None for spec in registry.specs)
    for tool_name in {
        "load_cached_lightcurve",
        "load_cached_tpf",
        "measure_transit",
        "odd_even",
        "secondary_eclipse",
        "harmonic_test",
        "centroid_localization",
        "contamination_screening",
    }:
        with pytest.raises(ActionValidationError, match="strict schema"):
            registry.validate_request(
                tool_name,
                parameters={"unexpected": True},
                granted_scopes={"science:execute"},
            )


@pytest.mark.parametrize(
    "parameters",
    [
        {"search": {"minimum_snr": "6.0"}},
        {"search": {"minimum_snr": 0.0}},
        {"preprocessing": {"minimum_samples": 19}},
        {"unknown": "field"},
    ],
)
def test_production_candidate_parameters_reject_wrong_types_ranges_and_fields(
    parameters,
) -> None:
    with pytest.raises(ActionValidationError, match="strict schema"):
        scaffold_tool_registry().validate_request(
            "search_bls",
            parameters=parameters,
            granted_scopes={"science:execute"},
        )


def test_registry_execute_cannot_bypass_parameter_validation() -> None:
    with pytest.raises(ActionValidationError, match="strict schema"):
        scaffold_tool_registry().execute(
            "odd_even",
            run_id="run_1",
            action_id="action_1",
            target_id="TARGET-X17",
            parameters={"unexpected": True},
            granted_scopes={"science:execute"},
        )
