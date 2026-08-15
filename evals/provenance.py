from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from exoswarm.agents.critic import CRITIC_PROMPT_VERSION
from exoswarm.agents.skeptic import SKEPTIC_PROMPT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip()
    return commit if completed.returncode == 0 and commit else "unavailable"


def _git_worktree_dirty() -> bool | str:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return "unavailable"
    return bool(completed.stdout.strip())


def evaluation_provenance(
    *, evaluation_id: str, configuration: dict[str, Any]
) -> dict[str, Any]:
    """Return secret-free, reproducible metadata for an evaluation report."""

    canonical_configuration = json.dumps(
        configuration, separators=(",", ":"), sort_keys=True
    ).encode()
    return {
        "evaluation_id": evaluation_id,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "git_worktree_dirty": _git_worktree_dirty(),
        "prompt_versions": {
            "critic": CRITIC_PROMPT_VERSION,
            "skeptic": SKEPTIC_PROMPT_VERSION,
        },
        "configuration": configuration,
        "configuration_sha256": hashlib.sha256(canonical_configuration).hexdigest(),
    }


__all__ = ["evaluation_provenance"]
