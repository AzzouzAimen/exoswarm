from __future__ import annotations

import json
import re
from typing import Any

from exoswarm.domain.models import InvestigationState

FORBIDDEN_AGENT_FIELDS = frozenset(
    {
        "cached_path",
        "catalog_disposition",
        "catalog_payload",
        "fits_path",
        "ground_truth",
        "known_period",
        "local_path",
        "private_provenance",
        "private_provenance_path",
        "provenance",
        "source_data_ref",
        "source_path",
        "target_name",
        "tic_id",
        "toi_id",
    }
)

_WINDOWS_PATH = re.compile(r"(?i)(?:\b[a-z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+)")
_POSIX_PATH = re.compile(
    r"(?:^|[\s\"'(])/(?!/)[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)*"
)
_LOCAL_FILE_SUFFIX = re.compile(
    r"(?i)\.(?:fits?|fts|csv|tsv|npy|npz|parquet)(?:\b|$)"
)
_RECOGNIZABLE_TARGET = re.compile(
    r"(?i)\b(?:tic|toi)\s*[-:#]?\s*\d+[a-z]?\b|"
    r"\b(?:kepler|k2|wasp|hat-p|tres|gj|hd)\s*[- ]?\s*\d+[a-z]?\b"
)
_RAW_ARRAY_KEYS = frozenset(
    {
        "flux",
        "invalid_removed_indices",
        "outlier_removed_indices",
        "period_grid_days",
        "periodogram_depth_snr",
        "phase",
        "quality_removed_indices",
        "relative_flux",
        "relative_flux_error",
        "retained_source_indices",
        "samples",
        "time",
        "time_btjd",
        "trend",
    }
)


def assert_agent_safe_payload(payload: Any) -> None:
    """Reject hidden authority, local sources, identities, and raw arrays recursively."""

    def reject_unsafe_string(value: str, key: str | None) -> None:
        if value.lower().startswith("file:") or "file://" in value.lower():
            raise RuntimeError("public agent payload contains a local file URI")
        if _WINDOWS_PATH.search(value) or _POSIX_PATH.search(value):
            raise RuntimeError("public agent payload contains a local source path")
        if _LOCAL_FILE_SUFFIX.search(value):
            raise RuntimeError("public agent payload contains a cached source location")
        if _RECOGNIZABLE_TARGET.search(value):
            raise RuntimeError("public agent payload contains recognizable target identity")
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list) and (
                len(decoded) >= 32 or (key in _RAW_ARRAY_KEYS and len(decoded) >= 3)
            ):
                raise RuntimeError("public agent payload contains a raw observation array")

    def inspect(value: Any, key: str | None = None) -> None:
        normalized_key = key.lower() if key is not None else None
        if normalized_key in FORBIDDEN_AGENT_FIELDS:
            raise RuntimeError(f"public agent payload contains private field: {key}")
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                inspect(child_value, str(child_key))
        elif isinstance(value, (list, tuple)):
            numeric = all(
                isinstance(child, (int, float)) and not isinstance(child, bool)
                for child in value
            )
            if numeric and (
                len(value) >= 32
                or (normalized_key in _RAW_ARRAY_KEYS and len(value) >= 3)
            ):
                raise RuntimeError("public agent payload contains a raw numerical array")
            for child in value:
                inspect(child)
        elif isinstance(value, str):
            reject_unsafe_string(value, normalized_key)

    inspect(payload)


def agent_safe_state(state: InvestigationState) -> dict[str, Any]:
    """Serialize the typed state and fail closed if a forbidden key is ever introduced."""

    payload = state.model_dump(mode="json")
    assert_agent_safe_payload(payload)
    return payload


__all__ = ["FORBIDDEN_AGENT_FIELDS", "agent_safe_state", "assert_agent_safe_payload"]
