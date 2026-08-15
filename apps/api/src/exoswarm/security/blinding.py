from __future__ import annotations

from typing import Any

from exoswarm.domain.models import InvestigationState

FORBIDDEN_AGENT_FIELDS = frozenset(
    {"tic_id", "toi_id", "target_name", "catalog_disposition", "known_period", "ground_truth"}
)


def agent_safe_state(state: InvestigationState) -> dict[str, Any]:
    """Serialize the typed state and fail closed if a forbidden key is ever introduced."""

    payload = state.model_dump(mode="json")
    forbidden = FORBIDDEN_AGENT_FIELDS.intersection(payload)
    if forbidden:
        raise RuntimeError(f"agent-visible state contains forbidden fields: {sorted(forbidden)}")
    return payload

