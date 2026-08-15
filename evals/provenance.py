from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from exoswarm.agents.prompt_registry import PROMPT_REGISTRY, prompt_template_sha256
from exoswarm.evaluation.outcomes import (
    ScientificOutcomeComparison,
    compare_scientific_outcomes,
    scientific_outcome_projection,
)

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
            role.value: registration.prompt_version
            for role, registration in PROMPT_REGISTRY.items()
            if role.value in {"skeptic", "critic"}
        },
        "prompts": {
            role.value: {
                "version": registration.prompt_version,
                "template_sha256": prompt_template_sha256(role),
                "example_set_version": registration.example_set_version,
            }
            for role, registration in PROMPT_REGISTRY.items()
        },
        "configuration": configuration,
        "configuration_sha256": hashlib.sha256(canonical_configuration).hexdigest(),
    }


__all__ = [
    "ScientificOutcomeComparison",
    "compare_scientific_outcomes",
    "evaluation_provenance",
    "scientific_outcome_projection",
]
