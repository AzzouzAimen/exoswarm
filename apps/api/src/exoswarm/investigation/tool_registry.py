from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from exoswarm.domain.errors import ToolPermissionError, UnknownToolError
from exoswarm.domain.models import ScientificToolResult
from exoswarm.science.bls import search_bls
from exoswarm.science.centroid import localize_centroid
from exoswarm.science.contracts import ScientificToolSpec
from exoswarm.science.harmonic import test_harmonics
from exoswarm.science.io import load_cached_lightcurve, load_cached_tpf
from exoswarm.science.odd_even import compare_odd_even
from exoswarm.science.preprocessing import preprocess
from exoswarm.science.secondary import search_secondary
from exoswarm.science.transit import measure_transit


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
    }
    return ScientificToolRegistry(
        ScientificToolSpec(name=name, handler=handler) for name, handler in handlers.items()
    )
