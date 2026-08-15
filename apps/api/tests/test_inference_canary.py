from __future__ import annotations

import os

import pytest

from exoswarm.agents.context import assemble_context
from exoswarm.agents.inference_provider import FeatherlessInferenceClient
from exoswarm.config import Settings
from exoswarm.domain.models import InvestigationState, SkepticDecision


@pytest.mark.canary
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("FEATHERLESS_API_KEY"),
    reason="real Featherless canary requires FEATHERLESS_API_KEY",
)
async def test_real_featherless_skeptic_schema_canary() -> None:
    settings = Settings(_env_file=None)
    client = FeatherlessInferenceClient.from_settings(settings)
    state = InvestigationState(
        run_id="run_canary_safe",
        opaque_target_id="TARGET-CANARY",
        step_count=1,
    )
    context = assemble_context(state, available_experiments=("harmonic_test",))

    outcome = await client.decide_attempt(
        role="skeptic",
        context=context,
        output_schema=SkepticDecision,
        attempt_kind="primary",
    )

    assert outcome.call.provider == "featherless"
    assert outcome.call.model_identity
    assert outcome.call.latency_ms is not None
    assert outcome.call.status in {"SUCCESS", "INVALID"}
