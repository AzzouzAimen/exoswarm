from __future__ import annotations

import json
import re
from pathlib import Path

from exoswarm.domain.events import InvestigationEvent
from exoswarm.domain.models import EvidenceRecord, InvestigationState
from exoswarm.investigation.evidence import JsonlEvidenceLedger

SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_component(value: str) -> str:
    if not SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"unsafe artifact path component: {value!r}")
    return value


class FileSystemRunArtifactStore:
    """Durable local JSON/JSONL store with atomic snapshot replacement."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def run_dir(self, opaque_target_id: str, run_id: str) -> Path:
        target = _validate_component(opaque_target_id)
        run = _validate_component(run_id)
        return self.root / target / run

    def create(self, state: InvestigationState) -> None:
        directory = self.run_dir(state.opaque_target_id, state.run_id)
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "artifacts").mkdir()
        self.save_state(state)

    def save_state(self, state: InvestigationState) -> None:
        path = self.run_dir(state.opaque_target_id, state.run_id) / "state.json"
        self._write_json_atomic(path, state.model_dump(mode="json"))

    def append_trace(self, state: InvestigationState, event: InvestigationEvent) -> None:
        path = self.run_dir(state.opaque_target_id, state.run_id) / "trace.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event.model_dump(mode="json"), sort_keys=True) + "\n")

    def write_bytes(self, state: InvestigationState, name: str, content: bytes) -> Path:
        if name not in {"result.json", "result.json.sha256", "reveal.json"}:
            raise ValueError(f"unsupported authority artifact: {name}")
        path = self.run_dir(state.opaque_target_id, state.run_id) / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
        return path

    def read_bytes(self, state: InvestigationState, name: str) -> bytes:
        return (self.run_dir(state.opaque_target_id, state.run_id) / name).read_bytes()

    def find_state(self, run_id: str) -> InvestigationState | None:
        safe_run_id = _validate_component(run_id)
        matches = list(self.root.glob(f"*/{safe_run_id}/state.json"))
        if not matches:
            return None
        if len(matches) != 1:
            raise RuntimeError(f"run identifier is not unique: {run_id}")
        return InvestigationState.model_validate_json(matches[0].read_bytes())

    def read_trace(self, state: InvestigationState) -> list[InvestigationEvent]:
        path = self.run_dir(state.opaque_target_id, state.run_id) / "trace.jsonl"
        if not path.exists():
            return []
        return [
            InvestigationEvent.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def evidence_path(self, state: InvestigationState) -> Path:
        return self.run_dir(state.opaque_target_id, state.run_id) / "evidence.jsonl"

    def append_evidence(self, state: InvestigationState, record: EvidenceRecord) -> None:
        existing = self.read_evidence(state)
        if any(item.evidence_id == record.evidence_id for item in existing):
            raise ValueError(f"evidence already exists: {record.evidence_id}")
        if any(item.action_id == record.action_id for item in existing):
            raise ValueError(f"action already has evidence: {record.action_id}")
        JsonlEvidenceLedger(self.evidence_path(state)).append(record)

    def read_evidence(self, state: InvestigationState) -> list[EvidenceRecord]:
        path = self.evidence_path(state)
        if not path.exists():
            return []
        return [
            EvidenceRecord.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    @staticmethod
    def _write_json_atomic(path: Path, payload: object) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
