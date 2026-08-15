from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_featherless_canary import run_canary  # noqa: E402


def test_featherless_canary_skips_truthfully_without_credential(monkeypatch) -> None:
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    report = __import__("asyncio").run(run_canary(2))
    assert report == {
        "schema_version": "1",
        "status": "SKIPPED",
        "reason": "FEATHERLESS_API_KEY is absent",
        "requested_repeats": 2,
    }


@pytest.mark.canary
@pytest.mark.asyncio
@pytest.mark.skipif(
    not (
        os.environ.get("FEATHERLESS_API_KEY") and os.environ.get("EXOSWARM_RUN_LIVE_CANARY") == "1"
    ),
    reason="live canary requires FEATHERLESS_API_KEY and EXOSWARM_RUN_LIVE_CANARY=1",
)
async def test_real_featherless_repeated_skeptic_critic_schema_canary() -> None:
    report = await run_canary(2)
    assert report["status"] == "COMPLETED"
    assert report["decisions"] == 4
    assert report["attempts"] >= 4
    assert report["model_identities"]
    assert report["raw_light_curve_samples_sent"] == 0
