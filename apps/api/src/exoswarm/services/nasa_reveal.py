from __future__ import annotations

from typing import Protocol

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

