from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from exoswarm.domain.models import EvidenceRecord


class EvidenceLedgerWriter(Protocol):
    def append(self, record: EvidenceRecord) -> None: ...


class JsonlEvidenceLedger:
    """Append-only evidence writer; existing records are never rewritten."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: EvidenceRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")

