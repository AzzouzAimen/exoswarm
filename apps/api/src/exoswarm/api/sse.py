from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from exoswarm.domain.events import InvestigationEvent


def encode_sse(events: Iterable[InvestigationEvent]) -> Iterator[str]:
    for event in events:
        data = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
        yield f"id: {event.event_id}\nevent: {event.type}\ndata: {data}\n\n"

