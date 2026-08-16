from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from exoswarm.domain.enums import InvestigationStatus, LockState
from exoswarm.domain.errors import ResultNotLockableError
from exoswarm.domain.models import InvestigationState, LockedResult, LockReceipt
from exoswarm.services.artifacts import FileSystemRunArtifactStore


def canonical_result_bytes(result: LockedResult) -> bytes:
    payload = result.model_dump(mode="json")
    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


class ResultLockService:
    def __init__(self, artifacts: FileSystemRunArtifactStore) -> None:
        self.artifacts = artifacts

    def lock(self, state: InvestigationState) -> tuple[InvestigationState, LockReceipt]:
        if state.lock_state in {LockState.RESULT_LOCKED, LockState.CATALOG_REVEALED}:
            return state, self.receipt(state)
        if state.status != InvestigationStatus.READY_TO_LOCK:
            raise ResultNotLockableError(
                f"run {state.run_id} is {state.status}; READY_TO_LOCK is required"
            )
        if state.disposition is None or not state.terminal_reason:
            raise ResultNotLockableError("lock requires a disposition and terminal reason")

        locked_at = datetime.now(UTC)
        result = LockedResult(
            run_id=state.run_id,
            opaque_target_id=state.opaque_target_id,
            disposition=state.disposition,
            evidence_refs=state.evidence_refs,
            terminal_reason=state.terminal_reason,
            locked_at=locked_at,
        )
        content = canonical_result_bytes(result)
        digest = hashlib.sha256(content).hexdigest()
        self.artifacts.write_bytes(state, "result.json", content)
        self.artifacts.write_bytes(state, "result.json.sha256", f"{digest}\n".encode())

        updated_payload = state.model_dump(mode="json")
        updated_payload.update(
            {
                "status": InvestigationStatus.RESULT_LOCKED,
                "lock_state": LockState.RESULT_LOCKED,
                "updated_at": locked_at,
            }
        )
        updated = InvestigationState.model_validate(updated_payload)
        self.artifacts.save_state(updated)
        return updated, LockReceipt(
            run_id=state.run_id,
            opaque_target_id=state.opaque_target_id,
            sha256=digest,
            result_path="result.json",
            locked_at=locked_at,
        )

    def receipt(self, state: InvestigationState) -> LockReceipt:
        if state.lock_state not in {LockState.RESULT_LOCKED, LockState.CATALOG_REVEALED}:
            raise ResultNotLockableError("result has not been locked")
        try:
            content = self.artifacts.read_bytes(state, "result.json")
            persisted = self.artifacts.read_bytes(state, "result.json.sha256").decode().strip()
        except (OSError, UnicodeDecodeError) as exc:
            raise ResultNotLockableError("locked result artifacts are invalid") from exc
        actual = hashlib.sha256(content).hexdigest()
        if persisted != actual:
            raise ResultNotLockableError("locked result hash verification failed")
        try:
            result = LockedResult.model_validate_json(content)
        except ValueError as exc:
            raise ResultNotLockableError("locked result artifact is invalid") from exc
        if result.run_id != state.run_id or result.opaque_target_id != state.opaque_target_id:
            raise ResultNotLockableError("locked result belongs to a different run")
        return LockReceipt(
            run_id=result.run_id,
            opaque_target_id=result.opaque_target_id,
            sha256=actual,
            result_path="result.json",
            locked_at=result.locked_at,
        )
