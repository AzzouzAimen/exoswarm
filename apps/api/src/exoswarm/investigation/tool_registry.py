from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from exoswarm.domain.errors import ActionValidationError, ToolPermissionError, UnknownToolError
from exoswarm.domain.models import ScientificToolResult
from exoswarm.science.bls import search_bls
from exoswarm.science.centroid import localize_centroid
from exoswarm.science.contracts import ScientificToolSpec, not_implemented_result
from exoswarm.science.harmonic import test_harmonics
from exoswarm.science.io import load_cached_lightcurve, load_cached_tpf
from exoswarm.science.odd_even import compare_odd_even
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
        granted_scopes: set[str] | frozenset[str] = frozenset(),
    ) -> ScientificToolResult:
        spec = self.resolve(name)
        missing_scopes = spec.required_scopes.difference(granted_scopes)
        if missing_scopes:
            raise ToolPermissionError(
                f"tool {name} requires missing scopes: {sorted(missing_scopes)}"
            )
        return spec.handler(run_id, action_id, target_id, parameters or {})

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
        if spec.parameter_schema is None:
            return spec, parameters
        try:
            validated = spec.parameter_schema.model_validate(parameters, strict=True)
        except ValidationError as exc:
            raise ActionValidationError(
                f"parameters for {name} do not satisfy its strict schema: {exc}"
            ) from exc
        return spec, validated.model_dump(mode="python")


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
    return ScientificToolRegistry(
        ScientificToolSpec(name=name, handler=handler, **metadata.get(name, {}))
        for name, handler in handlers.items()
    )
