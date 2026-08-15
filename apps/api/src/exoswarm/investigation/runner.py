from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from secrets import token_hex
from typing import BinaryIO

from pydantic import BaseModel, ConfigDict, Field

from exoswarm.domain.enums import TERMINAL_STATUSES, InvestigationStatus
from exoswarm.domain.errors import ExoSwarmError
from exoswarm.domain.events import InvestigationEvent
from exoswarm.domain.models import InvestigationState
from exoswarm.investigation.controller import InvestigationController
from exoswarm.services.target_registry import TargetRegistry

_STOP_STATUSES = frozenset({InvestigationStatus.READY_TO_LOCK, *TERMINAL_STATUSES})


class RunExecutionStatus(StrEnum):
    PAUSED = "PAUSED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class RunStartConflictError(ExoSwarmError):
    code = "RUN_START_CONFLICT"


class RunExecutionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    status: RunExecutionStatus
    active: bool
    advances: int = Field(default=0, ge=0)
    stop_reason: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class _FileLease:
    """Process-scoped advisory lease released automatically when the process exits."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream: BinaryIO | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            return False
        self._stream = stream
        return True

    def release(self) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()
            self._stream = None


class InvestigationRunService:
    """Application boundary that drives one bounded controller loop per durable run."""

    def __init__(
        self,
        controller: InvestigationController,
        target_registry: TargetRegistry,
        *,
        runs_dir: Path,
        timeout_seconds: float,
        sse_poll_interval_seconds: float = 0.05,
    ) -> None:
        self.controller = controller
        self.target_registry = target_registry
        self.runs_dir = runs_dir.resolve()
        self.timeout_seconds = timeout_seconds
        self.sse_poll_interval_seconds = sse_poll_interval_seconds
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._leases: dict[str, _FileLease] = {}
        self._records: dict[str, RunExecutionSnapshot] = {}
        self._start_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()

    async def create_and_start(
        self, opaque_target_id: str, idempotency_key: str
    ) -> tuple[InvestigationState, RunExecutionSnapshot]:
        key = idempotency_key.strip()
        if not key or len(key) > 128:
            raise ValueError("idempotency key must contain between 1 and 128 characters")
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        async with self._request_lock:
            lease = await self._acquire_bounded(
                self.runs_dir / ".runner-locks" / f"request-{digest}.lock"
            )
            try:
                request_path = self.runs_dir / ".start-requests" / f"{digest}.json"
                existing = self._read_start_request(request_path)
                if existing is not None:
                    if existing["opaque_target_id"] != opaque_target_id:
                        raise RunStartConflictError(
                            "idempotency key has already been used for another opaque target"
                        )
                    state = self.controller.get(existing["run_id"])
                else:
                    self.target_registry.resolve(opaque_target_id)
                    state = self.controller.create(opaque_target_id)
                    self._write_start_request(request_path, state)
            finally:
                lease.release()
        execution = await self.start(state.run_id)
        return self.controller.get(state.run_id), execution

    async def start(self, run_id: str) -> RunExecutionSnapshot:
        state = self.controller.get(run_id)
        if state.status in _STOP_STATUSES:
            snapshot = self._stopped_snapshot(state)
            self._records[run_id] = snapshot
            return snapshot

        # Validate the backend-only mapping before a task is scheduled. The path is
        # intentionally discarded here; only the controller receives it at execution.
        self.target_registry.resolve(state.opaque_target_id)
        async with self._start_lock:
            task = self._tasks.get(run_id)
            if task is not None and not task.done():
                return self._records[run_id]

            lease = _FileLease(self.runs_dir / ".runner-locks" / f"run-{run_id}.lock")
            if not lease.acquire():
                snapshot = RunExecutionSnapshot(
                    run_id=run_id,
                    status=RunExecutionStatus.RUNNING,
                    active=True,
                    stop_reason="ACTIVE_IN_ANOTHER_PROCESS",
                )
                self._records[run_id] = snapshot
                return snapshot

            started_at = datetime.now(UTC)
            snapshot = RunExecutionSnapshot(
                run_id=run_id,
                status=RunExecutionStatus.RUNNING,
                active=True,
                started_at=started_at,
            )
            self._leases[run_id] = lease
            self._records[run_id] = snapshot
            self._tasks[run_id] = asyncio.create_task(
                self._drive(run_id, started_at), name=f"investigation:{run_id}"
            )
            return snapshot

    async def resume(self, run_id: str) -> tuple[InvestigationState, RunExecutionSnapshot]:
        execution = await self.start(run_id)
        return self.controller.get(run_id), execution

    def inspect(self, run_id: str) -> RunExecutionSnapshot:
        state = self.controller.get(run_id)
        if state.status in _STOP_STATUSES:
            snapshot = self._stopped_snapshot(state, previous=self._records.get(run_id))
            self._records[run_id] = snapshot
            return snapshot
        return self._records.get(
            run_id,
            RunExecutionSnapshot(
                run_id=run_id,
                status=RunExecutionStatus.PAUSED,
                active=False,
                stop_reason="AWAITING_START_OR_RESUME",
            ),
        )

    async def wait(self, run_id: str) -> RunExecutionSnapshot:
        task = self._tasks.get(run_id)
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                raise
        return self.inspect(run_id)

    async def stream_events(
        self, run_id: str, *, after_sequence: int = 0
    ) -> AsyncIterator[InvestigationEvent]:
        next_sequence = after_sequence + 1
        while True:
            events = self.controller.events(run_id)
            self._validate_event_order(events)
            for event in events:
                if event.sequence >= next_sequence:
                    yield event
                    next_sequence = event.sequence + 1

            execution = self.inspect(run_id)
            if not execution.active and next_sequence > len(events):
                return
            await asyncio.sleep(self.sse_poll_interval_seconds)

    async def close(self) -> None:
        active = [task for task in self._tasks.values() if not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        for lease in tuple(self._leases.values()):
            lease.release()
        self._leases.clear()

    async def _drive(self, run_id: str, started_at: datetime) -> None:
        advances = 0
        state = self.controller.get(run_id)
        advance_budget = max(1, state.max_steps - state.step_count + 1)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout_seconds
        try:
            while advances < advance_budget:
                state = self.controller.get(run_id)
                if state.status in _STOP_STATUSES:
                    self._records[run_id] = self._stopped_snapshot(
                        state,
                        previous=self._records.get(run_id),
                        advances=advances,
                    )
                    return
                before = self._progress_signature(state)
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise TimeoutError
                state = await asyncio.wait_for(
                    self.controller.advance(run_id), timeout=remaining
                )
                advances += 1
                if state.status in _STOP_STATUSES:
                    self._records[run_id] = self._stopped_snapshot(
                        state,
                        previous=self._records.get(run_id),
                        advances=advances,
                    )
                    return
                if self._progress_signature(state) == before:
                    self.controller.fail_run(
                        run_id,
                        "RUNNER_NO_PROGRESS: controller returned without durable state progress",
                    )
                    self._records[run_id] = self._failed_snapshot(
                        run_id,
                        started_at,
                        advances,
                        "NO_DURABLE_PROGRESS",
                    )
                    return

            self.controller.fail_run(
                run_id,
                "RUNNER_ADVANCE_BUDGET_EXHAUSTED: outer loop advance budget reached",
                recoverable=False,
            )
            self._records[run_id] = self._failed_snapshot(
                run_id,
                started_at,
                advances,
                "ADVANCE_BUDGET_EXHAUSTED",
            )
        except TimeoutError:
            self.controller.fail_run(
                run_id,
                "RUNNER_TIMEOUT: wall-clock execution budget reached",
            )
            self._records[run_id] = self._failed_snapshot(
                run_id, started_at, advances, "WALL_CLOCK_TIMEOUT"
            )
        except asyncio.CancelledError:
            self._records[run_id] = RunExecutionSnapshot(
                run_id=run_id,
                status=RunExecutionStatus.PAUSED,
                active=False,
                advances=advances,
                stop_reason="SERVICE_SHUTDOWN",
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
            raise
        except Exception as exc:
            self.controller.fail_run(
                run_id,
                f"RUNNER_FAILURE:{type(exc).__name__}",
            )
            self._records[run_id] = self._failed_snapshot(
                run_id,
                started_at,
                advances,
                f"UNEXPECTED_{type(exc).__name__.upper()}",
            )
        finally:
            lease = self._leases.pop(run_id, None)
            if lease is not None:
                lease.release()

    async def _acquire_bounded(self, path: Path) -> _FileLease:
        for _ in range(50):
            lease = _FileLease(path)
            if lease.acquire():
                return lease
            await asyncio.sleep(0.02)
        raise RunStartConflictError("another process is handling this start request")

    @staticmethod
    def _read_start_request(path: Path) -> dict[str, str] | None:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if set(payload) != {"run_id", "opaque_target_id"} or not all(
            isinstance(value, str) for value in payload.values()
        ):
            raise RunStartConflictError("durable idempotency record is invalid")
        return payload

    @staticmethod
    def _write_start_request(path: Path, state: InvestigationState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{token_hex(6)}.tmp")
        temporary.write_text(
            json.dumps(
                {"run_id": state.run_id, "opaque_target_id": state.opaque_target_id},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _progress_signature(state: InvestigationState) -> str:
        payload = state.model_dump(mode="json", exclude={"updated_at"})
        return hashlib.sha256(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _validate_event_order(events: tuple[InvestigationEvent, ...]) -> None:
        sequences = [event.sequence for event in events]
        expected = list(range(1, len(events) + 1))
        if sequences != expected:
            raise RuntimeError("investigation trace sequence is not contiguous and monotonic")

    @staticmethod
    def _stopped_snapshot(
        state: InvestigationState,
        *,
        previous: RunExecutionSnapshot | None = None,
        advances: int | None = None,
    ) -> RunExecutionSnapshot:
        return RunExecutionSnapshot(
            run_id=state.run_id,
            status=(
                RunExecutionStatus.FAILED
                if state.status == InvestigationStatus.FAILED
                else RunExecutionStatus.STOPPED
            ),
            active=False,
            advances=advances if advances is not None else (previous.advances if previous else 0),
            stop_reason=(
                previous.stop_reason
                if previous is not None and previous.status == RunExecutionStatus.FAILED
                else state.terminal_reason or state.status
            ),
            started_at=previous.started_at if previous else None,
            finished_at=(
                previous.finished_at
                if previous is not None and previous.finished_at is not None
                else datetime.now(UTC)
            ),
        )

    @staticmethod
    def _failed_snapshot(
        run_id: str, started_at: datetime, advances: int, reason: str
    ) -> RunExecutionSnapshot:
        return RunExecutionSnapshot(
            run_id=run_id,
            status=RunExecutionStatus.FAILED,
            active=False,
            advances=advances,
            stop_reason=reason,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )


__all__ = [
    "InvestigationRunService",
    "RunExecutionSnapshot",
    "RunExecutionStatus",
    "RunStartConflictError",
]
