from __future__ import annotations

import hashlib

from pydantic import ValidationError

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
        if state.lock_state not in {LockState.RESULT_LOCKED, LockState.CATALOG_REVEALED}:
            raise ResultNotLockedError("ground-truth reveal is unavailable before result lock")

        if self.artifacts.authority_exists(state, "reveal.json"):
            return self.read_reveal(state)

        locked_result, actual_digest = self._verified_locked_result(state)
        reveal = self.provider.reveal(locked_result, actual_digest)
        self._validate_reveal(state, reveal, actual_digest)
        self.artifacts.write_bytes(
            state,
            "reveal.json",
            (reveal.model_dump_json(indent=2) + "\n").encode("utf-8"),
        )
        return reveal

    def read_reveal(self, state: InvestigationState) -> RevealResult:
        _, actual_digest = self._verified_locked_result(state)
        try:
            reveal = RevealResult.model_validate_json(
                self.artifacts.read_bytes(state, "reveal.json")
            )
        except (OSError, ValidationError) as exc:
            raise ResultNotLockedError("persisted catalog reveal is invalid") from exc
        self._validate_reveal(state, reveal, actual_digest)
        return reveal

    def _verified_locked_result(self, state: InvestigationState) -> tuple[LockedResult, str]:
        if state.lock_state not in {LockState.RESULT_LOCKED, LockState.CATALOG_REVEALED}:
            raise ResultNotLockedError("ground-truth reveal is unavailable before result lock")
        try:
            result_bytes = self.artifacts.read_bytes(state, "result.json")
            persisted_digest = (
                self.artifacts.read_bytes(state, "result.json.sha256").decode().strip()
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise ResultNotLockedError("locked result artifacts are invalid") from exc
        actual_digest = hashlib.sha256(result_bytes).hexdigest()
        if persisted_digest != actual_digest:
            raise ResultNotLockedError("locked result hash verification failed")
        try:
            locked_result = LockedResult.model_validate_json(result_bytes)
        except ValidationError as exc:
            raise ResultNotLockedError("locked result artifact is invalid") from exc
        if (
            locked_result.run_id != state.run_id
            or locked_result.opaque_target_id != state.opaque_target_id
        ):
            raise ResultNotLockedError("locked result belongs to a different run")
        return locked_result, actual_digest

    @staticmethod
    def _validate_reveal(
        state: InvestigationState, reveal: RevealResult, locked_digest: str
    ) -> None:
        if (
            reveal.run_id != state.run_id
            or reveal.opaque_target_id != state.opaque_target_id
            or reveal.locked_result_sha256 != locked_digest
        ):
            raise ResultNotLockedError("catalog reveal does not match the locked run")

