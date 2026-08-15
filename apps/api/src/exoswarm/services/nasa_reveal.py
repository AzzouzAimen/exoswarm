from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from exoswarm.domain.errors import CapabilityNotImplementedError
from exoswarm.domain.models import LockedResult, RevealResult


class CatalogRevealProvider(Protocol):
    def reveal(self, locked_result: LockedResult, locked_sha256: str) -> RevealResult: ...


class UnconfiguredCatalogRevealProvider:
    def reveal(self, locked_result: LockedResult, locked_sha256: str) -> RevealResult:
        del locked_result, locked_sha256
        raise CapabilityNotImplementedError(
            "catalog reveal is gated correctly but no live or cached catalog provider is configured"
        )


class _CachedCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opaque_target_id: str = Field(pattern=r"^TARGET-[A-Z0-9-]+$")
    target_name: str = Field(min_length=1)
    tic_id: str = Field(pattern=r"^[0-9]+$")
    catalog_disposition: str = Field(min_length=1)
    catalog_source: str = Field(min_length=1)
    catalog_source_url: str = Field(pattern=r"^https://")
    known_values: dict[str, float | int | str]


class _CachedCatalogManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(pattern=r"^1$")
    targets: list[_CachedCatalogEntry]


class CachedCatalogRevealProvider:
    """Backend-only reveal from a versioned cache of official catalog records."""

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path.resolve()
        if not self.manifest_path.is_file():
            self._entries: dict[str, _CachedCatalogEntry] = {}
            return
        manifest = _CachedCatalogManifest.model_validate_json(
            self.manifest_path.read_bytes()
        )
        self._entries = {entry.opaque_target_id: entry for entry in manifest.targets}
        if len(self._entries) != len(manifest.targets):
            raise ValueError("cached catalog reveal manifest contains duplicate targets")

    def reveal(self, locked_result: LockedResult, locked_sha256: str) -> RevealResult:
        entry = self._entries.get(locked_result.opaque_target_id)
        if entry is None:
            raise CapabilityNotImplementedError(
                "no cached catalog comparison is configured for this opaque target"
            )
        return RevealResult(
            run_id=locked_result.run_id,
            opaque_target_id=locked_result.opaque_target_id,
            locked_result_sha256=locked_sha256,
            catalog_source=entry.catalog_source,
            catalog_payload={
                "target_name": entry.target_name,
                "tic_id": entry.tic_id,
                "catalog_disposition": entry.catalog_disposition,
                "catalog_source_url": entry.catalog_source_url,
                "known_values": entry.known_values,
                "locked_exoswarm_result": {
                    "disposition": locked_result.disposition,
                    "terminal_reason": locked_result.terminal_reason,
                    "evidence_refs": locked_result.evidence_refs,
                },
            },
        )
