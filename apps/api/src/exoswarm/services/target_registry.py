from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TargetRegistry:
    """Reads only the public opaque-target manifest used by pre-lock APIs."""

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path

    def list_agent_safe(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return [
            {
                "opaque_target_id": item["opaque_target_id"],
                "cached_lightcurve_available": bool(item.get("cached_lightcurve_available", False)),
                "cached_tpf_available": bool(item.get("cached_tpf_available", False)),
            }
            for item in payload.get("targets", [])
        ]

