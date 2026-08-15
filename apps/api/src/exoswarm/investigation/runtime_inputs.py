from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class CachedCandidateSource(BaseModel):
    """Backend-only source for deterministic candidate analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cached_path: Path


class CandidateSourceResolver(Protocol):
    def resolve(self, opaque_target_id: str) -> CachedCandidateSource: ...


class MappingCandidateSourceResolver:
    """Small injectable opaque-ID mapping; callers retain ownership of local paths."""

    def __init__(self, sources: Mapping[str, CachedCandidateSource]) -> None:
        self._sources = dict(sources)

    def resolve(self, opaque_target_id: str) -> CachedCandidateSource:
        try:
            return self._sources[opaque_target_id]
        except KeyError as exc:
            raise LookupError(
                f"no backend-owned cached candidate source for {opaque_target_id}"
            ) from exc


__all__ = [
    "CachedCandidateSource",
    "CandidateSourceResolver",
    "MappingCandidateSourceResolver",
]
