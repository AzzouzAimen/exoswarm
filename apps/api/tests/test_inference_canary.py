from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import preflight_featherless_thinking  # noqa: E402
from scripts.run_featherless_canary import (  # noqa: E402
    _canary_cases,
    _decision_quality_result,
    _proposal,
    _runtime_configuration,
    run_canary,
)

from exoswarm.config import Settings  # noqa: E402


def test_thinking_preflight_uses_normal_dotenv_settings(monkeypatch) -> None:
    settings_calls: list[dict[str, object]] = []

    class FakeSettings:
        featherless_api_key = SecretStr("configured-in-dotenv")
        featherless_base_url = "https://api.featherless.ai/v1"
        model = "deepseek-ai/DeepSeek-V4-Flash-0731"

        def __init__(self, **kwargs: object) -> None:
            settings_calls.append(kwargs)

    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    monkeypatch.setattr(preflight_featherless_thinking, "Settings", FakeSettings)
    monkeypatch.setattr(
        preflight_featherless_thinking,
        "run_preflight",
        lambda **_: {"thinking_toggle_effect_confirmed": True},
    )
    monkeypatch.setattr(sys, "argv", ["preflight_featherless_thinking.py"])

    assert preflight_featherless_thinking.main() == 0
    assert settings_calls == [{}]


def test_featherless_canary_skips_truthfully_without_credential(monkeypatch) -> None:
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    report = __import__("asyncio").run(
        run_canary(
            2,
            settings=Settings(_env_file=None, featherless_api_key=None),
        )
    )
    assert report["schema_version"] == "2"
    assert report["status"] == "SKIPPED"
    assert report["reason"] == "FEATHERLESS_API_KEY is absent"
    assert report["requested_repeats"] == 2
    assert report["provenance"]["evaluation_id"] == "featherless-canary-v2"
    assert report["provenance"]["prompt_versions"]


def test_decision_quality_rubric_grades_resolved_stop() -> None:
    case = next(item for item in _canary_cases() if item.name == "resolved")
    proposal = _proposal(case.state, experiment="stop", cost=0)

    result = _decision_quality_result(
        case=case,
        role="skeptic",
        decision=proposal,
        proposal=proposal,
    )

    assert result["selected_action"] == "stop"
    assert result["passed"] is True
    assert proposal.hypothesis_under_test == "none_material"
    assert "schema" not in proposal.concise_reason.lower()


def test_critic_canary_proposal_is_relevant_to_the_case() -> None:
    case = next(item for item in _canary_cases() if item.name == "contamination")
    proposal = _proposal(case.state, experiment="alternate_aperture", cost=1)

    assert proposal.hypothesis_under_test == "background_contamination"
    assert "aperture" in proposal.concise_reason.lower()
    assert "contamination" in proposal.expected_discriminating_result.lower()
    assert case.evidence[0].evidence_id in case.state.evidence_refs


def test_canary_provenance_uses_runtime_settings_contract() -> None:
    configuration = _runtime_configuration(Settings(_env_file=None), 10)

    assert configuration == {
        "context_schema_version": "agent-context-v4",
        "configured_max_input_tokens": 32000,
        "configured_max_output_tokens": 20000,
        "effective_role_max_output_tokens": {"critic": 700, "skeptic": 1200},
        "inference_model": "deepseek-ai/DeepSeek-V4-Flash-0731",
        "requested_repeats": 10,
        "role_thinking_modes": {"critic": "off", "skeptic": "off"},
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
    assert report["decision_quality"]["denominator"] == 4
