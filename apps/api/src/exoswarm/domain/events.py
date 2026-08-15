from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class InvestigationEvent(BaseModel):
    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    timestamp: datetime = Field(default_factory=utc_now)
    type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: Literal["1"] = "1"
