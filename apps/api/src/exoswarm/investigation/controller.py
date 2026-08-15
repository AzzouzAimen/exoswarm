from __future__ import annotations

from datetime import UTC, datetime
from secrets import token_hex

from exoswarm.config import Settings
from exoswarm.domain.enums import InvestigationStatus, LockState
from exoswarm.domain.errors import CapabilityNotImplementedError, RunNotFoundError
from exoswarm.domain.events import InvestigationEvent
from exoswarm.domain.models import InvestigationState, LockReceipt, RevealResult
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore


class InvestigationController:
    """Small scaffold controller around durable state, traces, and authority services."""

    def __init__(
        self,
        settings: Settings,
        artifacts: FileSystemRunArtifactStore,
        result_lock: ResultLockService,
        catalog_gate: CatalogGate,
    ) -> None:
        self.settings = settings
        self.artifacts = artifacts
        self.result_lock = result_lock
        self.catalog_gate = catalog_gate
        self._states: dict[str, InvestigationState] = {}
        self._events: dict[str, list[InvestigationEvent]] = {}

    def create(self, opaque_target_id: str) -> InvestigationState:
        run_id = f"run_{token_hex(8)}"
        state = InvestigationState(
            run_id=run_id,
            opaque_target_id=opaque_target_id,
            max_steps=self.settings.max_steps,
            max_adaptive_experiments=self.settings.max_adaptive_experiments,
        )
        event = InvestigationEvent(
            event_id=f"evt_{token_hex(8)}",
            run_id=run_id,
            step_id="step_0000",
            action_id=f"action_{token_hex(8)}",
            sequence=1,
            type="investigation.created",
            payload={"status": state.status, "opaque_target_id": opaque_target_id},
        )
        self.artifacts.create(state)
        self.artifacts.append_trace(state, event)
        self._states[run_id] = state
        self._events[run_id] = [event]
        return state

    def get(self, run_id: str) -> InvestigationState:
        state = self._states.get(run_id)
        if state is None:
            state = self.artifacts.find_state(run_id)
            if state is None:
                raise RunNotFoundError(f"investigation not found: {run_id}")
            self._states[run_id] = state
            self._events[run_id] = self.artifacts.read_trace(state)
        return state

    def events(self, run_id: str) -> tuple[InvestigationEvent, ...]:
        self.get(run_id)
        return tuple(self._events[run_id])

    def lock(self, run_id: str) -> LockReceipt:
        state = self.get(run_id)
        updated, receipt = self.result_lock.lock(state)
        event = self._event(updated, "result.locked", {"sha256": receipt.sha256})
        self._states[run_id] = updated
        self._events[run_id].append(event)
        self.artifacts.append_trace(updated, event)
        return receipt

    def reveal(self, run_id: str) -> RevealResult:
        state = self.get(run_id)
        reveal = self.catalog_gate.reveal(state)
        updated_payload = state.model_dump(mode="json")
        updated_payload.update(
            {
                "status": InvestigationStatus.REVEALED,
                "lock_state": LockState.CATALOG_REVEALED,
                "updated_at": datetime.now(UTC),
            }
        )
        updated = InvestigationState.model_validate(updated_payload)
        event = self._event(updated, "catalog.revealed", {"catalog_source": reveal.catalog_source})
        self._states[run_id] = updated
        self._events[run_id].append(event)
        self.artifacts.save_state(updated)
        self.artifacts.append_trace(updated, event)
        return reveal

    def advance(self, run_id: str) -> None:
        self.get(run_id)
        raise CapabilityNotImplementedError(
            "the bounded investigation loop is intentionally not implemented in the scaffold"
        )

    def _event(
        self, state: InvestigationState, event_type: str, payload: dict[str, object]
    ) -> InvestigationEvent:
        sequence = len(self._events[state.run_id]) + 1
        return InvestigationEvent(
            event_id=f"evt_{token_hex(8)}",
            run_id=state.run_id,
            step_id=f"step_{state.step_count:04d}",
            action_id=f"action_{token_hex(8)}",
            sequence=sequence,
            timestamp=datetime.now(UTC),
            type=event_type,
            payload=payload,
        )
