import hashlib

import pytest

from exoswarm.domain.enums import Disposition, InvestigationStatus, LockState
from exoswarm.domain.models import InvestigationState
from exoswarm.investigation.state import validate_status_transition
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore


def ready_state() -> InvestigationState:
    return InvestigationState(
        run_id="run_fixture",
        opaque_target_id="TARGET-X17",
        status=InvestigationStatus.READY_TO_LOCK,
        disposition=Disposition.INCONCLUSIVE_ADDITIONAL_DATA_REQUIRED,
        terminal_reason="SCAFFOLD_FIXTURE_COMPLETE",
    )


def test_result_lock_writes_stable_hash_of_exact_bytes(tmp_path) -> None:
    state = ready_state()
    store = FileSystemRunArtifactStore(tmp_path)
    store.create(state)

    updated, receipt = ResultLockService(store).lock(state)
    result_bytes = store.read_bytes(updated, "result.json")
    persisted_hash = store.read_bytes(updated, "result.json.sha256").decode().strip()

    assert receipt.sha256 == hashlib.sha256(result_bytes).hexdigest() == persisted_hash
    assert updated.status == InvestigationStatus.RESULT_LOCKED
    assert updated.lock_state == LockState.RESULT_LOCKED


def test_locked_result_can_transition_to_revealed_but_not_back_to_science() -> None:
    validate_status_transition(
        InvestigationStatus.RESULT_LOCKED, InvestigationStatus.REVEALED
    )

    with pytest.raises(ValueError, match="invalid investigation status transition"):
        validate_status_transition(
            InvestigationStatus.RESULT_LOCKED,
            InvestigationStatus.UPDATING_EVIDENCE,
        )
