from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from exoswarm.domain.errors import ExoSwarmError
from exoswarm.investigation.runtime_inputs import CachedCandidateSource


class TargetManifestError(ExoSwarmError):
    code = "TARGET_MANIFEST_INVALID"


class TargetMappingNotFoundError(ExoSwarmError, LookupError):
    code = "TARGET_MAPPING_NOT_FOUND"


class TargetSourceUnavailableError(ExoSwarmError, LookupError):
    code = "TARGET_SOURCE_UNAVAILABLE"


class _TargetEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opaque_target_id: str = Field(pattern=r"^TARGET-[A-Z0-9-]+$")
    cached_lightcurve_path: str | None = None
    cached_tpf_path: str | None = None

    @field_validator("cached_lightcurve_path", "cached_tpf_path")
    @classmethod
    def source_paths_are_relative(cls, value: str | None) -> str | None:
        if value is not None and Path(value).is_absolute():
            raise ValueError("backend source paths must be relative to the data directory")
        return value


class _TargetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    targets: list[_TargetEntry] = Field(default_factory=list)


class TargetRegistry:
    """Loads the backend-only source manifest and exposes a separate safe view."""

    def __init__(self, manifest_path: Path, *, data_dir: Path | None = None) -> None:
        self.manifest_path = manifest_path.resolve()
        self.data_dir = (data_dir or self.manifest_path.parent.parent).resolve()
        self._targets = self._load()

    def _load(self) -> dict[str, _TargetEntry]:
        if not self.manifest_path.exists():
            return {}
        try:
            manifest = _TargetManifest.model_validate_json(
                self.manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError, json.JSONDecodeError) as exc:
            raise TargetManifestError(
                f"backend target manifest is invalid: {self.manifest_path.name}"
            ) from exc
        entries: dict[str, _TargetEntry] = {}
        for item in manifest.targets:
            if item.opaque_target_id in entries:
                raise TargetManifestError(
                    f"backend target manifest contains duplicate opaque ID: "
                    f"{item.opaque_target_id}"
                )
            entries[item.opaque_target_id] = item
        return entries

    def _source_path(self, value: str) -> Path:
        resolved = (self.data_dir / value).resolve()
        if not resolved.is_relative_to(self.data_dir):
            raise TargetManifestError("backend target source escapes the configured data directory")
        return resolved

    def resolve(self, opaque_target_id: str) -> CachedCandidateSource:
        try:
            entry = self._targets[opaque_target_id]
        except KeyError as exc:
            raise TargetMappingNotFoundError(
                f"no backend source mapping exists for {opaque_target_id}"
            ) from exc
        if entry.cached_lightcurve_path is None:
            raise TargetSourceUnavailableError(
                f"no cached light curve is configured for {opaque_target_id}"
            )
        source_path = self._source_path(entry.cached_lightcurve_path)
        if not source_path.is_file():
            raise TargetSourceUnavailableError(
                f"the cached light curve for {opaque_target_id} is unavailable"
            )
        return CachedCandidateSource(cached_path=source_path)

    def list_agent_safe(self) -> list[dict[str, Any]]:
        return [
            {
                "opaque_target_id": item.opaque_target_id,
                "cached_lightcurve_available": bool(
                    item.cached_lightcurve_path
                    and self._source_path(item.cached_lightcurve_path).is_file()
                ),
                "cached_tpf_available": bool(
                    item.cached_tpf_path and self._source_path(item.cached_tpf_path).is_file()
                ),
            }
            for item in sorted(self._targets.values(), key=lambda value: value.opaque_target_id)
        ]


__all__ = [
    "TargetManifestError",
    "TargetMappingNotFoundError",
    "TargetRegistry",
    "TargetSourceUnavailableError",
]
