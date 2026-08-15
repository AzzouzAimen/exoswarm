from __future__ import annotations

from typing import Protocol

from exoswarm.domain.events import InvestigationEvent
from exoswarm.domain.models import InvestigationState


class RunStateStore(Protocol):
    def create(self, state: InvestigationState) -> None: ...

    def save_state(self, state: InvestigationState) -> None: ...

    def append_trace(self, state: InvestigationState, event: InvestigationEvent) -> None: ...

