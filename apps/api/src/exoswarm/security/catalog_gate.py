from __future__ import annotations

import hashlib

from exoswarm.domain.enums import LockState
from exoswarm.domain.errors import ResultNotLockedError
from exoswarm.domain.models import InvestigationState, LockedResult, RevealResult
from exoswarm.services.artifacts import FileSystemRunArtifactStore
from exoswarm.services.nasa_reveal import CatalogRevealProvider


class CatalogGate:
    """The only service allowed to invoke backend ground-truth reveal capability."""

    def __init__(
        self, artifacts: FileSystemRunArtifactStore, provider: CatalogRevealProvider
    ) -> None:
        self.artifacts = artifacts
        self.provider = provider

    def reveal(self, state: InvestigationState) -> RevealResult:
        if state.lock_state != LockState.RESULT_LOCKED:
            raise ResultNotLockedError("ground-truth reveal is unavailable before result lock")

        result_bytes = self.artifacts.read_bytes(state, "result.json")
        persisted_digest = self.artifacts.read_bytes(state, "result.json.sha256").decode().strip()
        actual_digest = hashlib.sha256(result_bytes).hexdigest()
        if persisted_digest != actual_digest:
            raise ResultNotLockedError("locked result hash verification failed")

        locked_result = LockedResult.model_validate_json(result_bytes)
        if locked_result.run_id != state.run_id:
            raise ResultNotLockedError("locked result belongs to a different run")
        reveal = self.provider.reveal(locked_result, actual_digest)
        self.artifacts.write_bytes(
            state,
            "reveal.json",
            (reveal.model_dump_json(indent=2) + "\n").encode("utf-8"),
        )
        return reveal

