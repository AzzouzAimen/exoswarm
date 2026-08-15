from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from exoswarm.domain.errors import ActionValidationError, ToolPermissionError, UnknownToolError
from exoswarm.domain.models import ScientificToolResult
from exoswarm.science.bls import search_bls
from exoswarm.science.centroid import localize_centroid
from exoswarm.science.contracts import NoParameters, ScientificToolSpec, not_implemented_result
from exoswarm.science.harmonic import test_harmonics
from exoswarm.science.io import load_cached_lightcurve, load_cached_tpf
from exoswarm.science.odd_even import compare_odd_even
from exoswarm.science.pipeline import (
    CandidateSearchParameters,
    CandidateSearchRuntimeInputs,
    PreprocessingParameters,
)
from exoswarm.science.preprocessing import preprocess
from exoswarm.science.secondary import search_secondary
from exoswarm.science.transit import measure_transit


def _contamination_screening_stub(
    run_id: str, action_id: str, target_id: str, parameters: dict[str, Any]
) -> ScientificToolResult:
    return not_implemented_result(
        tool_name="contamination_screening",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )


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
        "load_cached_lightcurve": load_cached_lightcurve,
        "load_cached_tpf": load_cached_tpf,
        "preprocess": preprocess,
        "search_bls": search_bls,
        "measure_transit": measure_transit,
        "odd_even": compare_odd_even,
        "secondary_eclipse": search_secondary,
        "harmonic_test": test_harmonics,
        "centroid_localization": localize_centroid,
        "contamination_screening": _contamination_screening_stub,
    }
    metadata = {
        "search_bls": {"mandatory_test": "signal_quality", "order": 10},
        "odd_even": {"mandatory_test": "odd_even", "order": 20},
        "secondary_eclipse": {"mandatory_test": "secondary_eclipse", "order": 30},
        "contamination_screening": {"mandatory_test": "contamination", "order": 40},
        "harmonic_test": {"adaptive": True, "order": 50},
        "centroid_localization": {"adaptive": True, "order": 60},
    }
    parameter_schemas = {
        "preprocess": PreprocessingParameters,
        "search_bls": CandidateSearchParameters,
    }
    runtime_schemas = {"search_bls": CandidateSearchRuntimeInputs}
    return ScientificToolRegistry(
        ScientificToolSpec(
            name=name,
            handler=handler,
            parameter_schema=parameter_schemas.get(name, NoParameters),
            runtime_input_schema=runtime_schemas.get(name),
            **metadata.get(name, {}),
        )
        for name, handler in handlers.items()
    )
