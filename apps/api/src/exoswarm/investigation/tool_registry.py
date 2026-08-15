from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from exoswarm.domain.errors import ActionValidationError, ToolPermissionError, UnknownToolError
from exoswarm.domain.models import ScientificToolResult
from exoswarm.science.bls import search_bls
from exoswarm.science.candidate_artifact import CandidateArtifactRuntimeInputs
from exoswarm.science.centroid import localize_centroid
from exoswarm.science.contamination import ContaminationRuntimeInputs, screen_contamination
from exoswarm.science.contracts import ExecutionIsolation, NoParameters, ScientificToolSpec
from exoswarm.science.harmonic import test_harmonics
from exoswarm.science.odd_even import compare_odd_even
from exoswarm.science.pipeline import (
    CandidateSearchParameters,
    CandidateSearchRuntimeInputs,
)
from exoswarm.science.secondary import search_secondary

STOP_ACTION = "stop"


class ScientificToolRegistry:
    """Allowlisted action registry; unregistered model requests never execute."""

    def __init__(self, specs: Iterable[ScientificToolSpec] = ()) -> None:
        self._specs = {spec.name: spec for spec in specs}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def register(self, spec: ScientificToolSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"tool already registered: {spec.name}")
        self._specs[spec.name] = spec

    @property
    def specs(self) -> tuple[ScientificToolSpec, ...]:
        return tuple(sorted(self._specs.values(), key=lambda spec: (spec.order, spec.name)))

    def resolve(self, name: str) -> ScientificToolSpec:
        try:
            return self._specs[name]
        except KeyError as exc:
            raise UnknownToolError(f"unknown scientific tool: {name}") from exc

    def execute(
        self,
        name: str,
        *,
        run_id: str,
        action_id: str,
        target_id: str,
        parameters: dict[str, Any] | None = None,
        runtime_inputs: dict[str, Any] | None = None,
        granted_scopes: set[str] | frozenset[str] = frozenset(),
    ) -> ScientificToolResult:
        spec, validated_parameters = self.validate_request(
            name,
            parameters=parameters or {},
            granted_scopes=granted_scopes,
        )
        validated_runtime_inputs = self.validate_runtime_inputs(spec, runtime_inputs)
        invocation = self.invocation_parameters(
            name,
            validated_parameters=validated_parameters,
            validated_runtime_inputs=validated_runtime_inputs,
        )
        return spec.handler(run_id, action_id, target_id, invocation)

    def validate_request(
        self,
        name: str,
        *,
        parameters: dict[str, Any],
        granted_scopes: set[str] | frozenset[str],
    ) -> tuple[ScientificToolSpec, dict[str, Any]]:
        spec = self.resolve(name)
        missing_scopes = spec.required_scopes.difference(granted_scopes)
        if missing_scopes:
            raise ToolPermissionError(
                f"tool {name} requires missing scopes: {sorted(missing_scopes)}"
            )
        return self.validate_parameters(name, parameters=parameters)

    def validate_parameters(
        self,
        name: str,
        *,
        parameters: dict[str, Any],
    ) -> tuple[ScientificToolSpec, dict[str, Any]]:
        spec = self.resolve(name)
        try:
            validated = spec.parameter_schema.model_validate(parameters, strict=True)
        except ValidationError as exc:
            raise ActionValidationError(
                f"parameters for {name} do not satisfy its strict schema: {exc}"
            ) from exc
        return spec, validated.model_dump(mode="python")

    @staticmethod
    def validate_runtime_inputs(
        spec: ScientificToolSpec, runtime_inputs: dict[str, Any] | None
    ) -> dict[str, Any]:
        supplied = runtime_inputs or {}
        if spec.runtime_input_schema is None:
            if supplied:
                raise ActionValidationError(
                    f"tool {spec.name} does not accept backend runtime inputs"
                )
            return {}
        try:
            validated = spec.runtime_input_schema.model_validate(supplied, strict=True)
        except ValidationError as exc:
            raise ActionValidationError(
                f"backend runtime inputs for {spec.name} do not satisfy their strict schema: "
                f"{exc}"
            ) from exc
        return validated.model_dump(mode="python")

    @staticmethod
    def invocation_parameters(
        name: str,
        *,
        validated_parameters: dict[str, Any],
        validated_runtime_inputs: dict[str, Any],
    ) -> dict[str, Any]:
        overlap = validated_parameters.keys() & validated_runtime_inputs.keys()
        if overlap:
            raise ActionValidationError(
                f"model and backend inputs overlap for {name}: {sorted(overlap)}"
            )
        return {**validated_parameters, **validated_runtime_inputs}


def scaffold_tool_registry() -> ScientificToolRegistry:
    handlers = {
        "search_bls": search_bls,
        "odd_even": compare_odd_even,
        "secondary_eclipse": search_secondary,
        "harmonic_test": test_harmonics,
        "centroid_localization": localize_centroid,
        "contamination_screening": screen_contamination,
    }
    metadata = {
        "search_bls": {"mandatory_test": "signal_quality", "order": 10},
        "odd_even": {"mandatory_test": "odd_even", "order": 20},
        "secondary_eclipse": {"mandatory_test": "secondary_eclipse", "order": 30},
        "contamination_screening": {"mandatory_test": "contamination", "order": 40},
        "harmonic_test": {"adaptive": True, "cost_units": 1, "order": 50},
        "centroid_localization": {
            "adaptive": True,
            "cost_units": 2,
            "implemented": False,
            "required_target_capabilities": frozenset({"cached_tpf"}),
            "order": 60,
        },
    }
    parameter_schemas = {"search_bls": CandidateSearchParameters}
    runtime_schemas = {
        "search_bls": CandidateSearchRuntimeInputs,
        "odd_even": CandidateArtifactRuntimeInputs,
        "secondary_eclipse": CandidateArtifactRuntimeInputs,
        "harmonic_test": CandidateArtifactRuntimeInputs,
        "contamination_screening": ContaminationRuntimeInputs,
    }
    return ScientificToolRegistry(
        ScientificToolSpec(
            name=name,
            handler=handler,
            parameter_schema=parameter_schemas.get(name, NoParameters),
            runtime_input_schema=runtime_schemas.get(name),
            execution_isolation=ExecutionIsolation.SUBPROCESS,
            **metadata.get(name, {}),
        )
        for name, handler in handlers.items()
    )
