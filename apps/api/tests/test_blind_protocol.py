from __future__ import annotations

import ast
from pathlib import Path

import pytest

from exoswarm.domain.enums import Disposition, InvestigationStatus
from exoswarm.domain.errors import ResultNotLockedError
from exoswarm.domain.models import InvestigationState, RevealResult
from exoswarm.security.blinding import assert_agent_safe_payload
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore


class SpyRevealProvider:
    called = False

    def reveal(self, locked_result, locked_sha256):
        self.called = True
        raise AssertionError((locked_result, locked_sha256))


class FixtureRevealProvider:
    def reveal(self, locked_result, locked_sha256):
        return RevealResult(
            run_id=locked_result.run_id,
            opaque_target_id=locked_result.opaque_target_id,
            locked_result_sha256=locked_sha256,
            catalog_source="test-fixture",
            catalog_payload={"fixture": "backend-only"},
        )


def test_reveal_capability_is_unavailable_before_lock(tmp_path) -> None:
    state = InvestigationState(run_id="run_fixture", opaque_target_id="TARGET-X17")
    store = FileSystemRunArtifactStore(tmp_path)
    store.create(state)
    provider = SpyRevealProvider()

    with pytest.raises(ResultNotLockedError, match="before result lock"):
        CatalogGate(store, provider).reveal(state)
    assert provider.called is False
    assert not (store.run_dir(state.opaque_target_id, state.run_id) / "reveal.json").exists()


def test_reveal_is_tied_to_the_same_locked_run(tmp_path) -> None:
    state = InvestigationState(
        run_id="run_fixture",
        opaque_target_id="TARGET-X17",
        status=InvestigationStatus.READY_TO_LOCK,
        disposition=Disposition.INCONCLUSIVE_ADDITIONAL_DATA_REQUIRED,
        terminal_reason="TEST_FIXTURE_COMPLETE",
    )
    store = FileSystemRunArtifactStore(tmp_path)
    store.create(state)
    locked_state, receipt = ResultLockService(store).lock(state)

    reveal = CatalogGate(store, FixtureRevealProvider()).reveal(locked_state)

    assert reveal.run_id == locked_state.run_id
    assert reveal.locked_result_sha256 == receipt.sha256
    assert (store.run_dir(state.opaque_target_id, state.run_id) / "reveal.json").exists()


def test_agent_modules_do_not_import_reveal_authority() -> None:
    agents_dir = Path(__file__).parents[1] / "src" / "exoswarm" / "agents"
    forbidden = {"exoswarm.services.nasa_reveal", "exoswarm.security.catalog_gate"}
    violations: list[str] = []

    for path in agents_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported = {node.module or ""}
            else:
                continue
            if any(name in forbidden for name in imported):
                violations.append(f"{path.name}: {sorted(imported)}")

    assert violations == []


@pytest.mark.parametrize(
    "unsafe",
    [
        {"nested": {"tic_id": "123"}},
        {"reason": "Compare against TIC 123456789"},
        {"reason": "Read C:\\private\\target.fits"},
        {"reason": "/private/cache/target.csv"},
        {"samples": "[1.0, 2.0, 3.0]"},
        {"samples": [1.0, 2.0, 3.0]},
    ],
)
def test_public_agent_payload_rejects_nested_authority_and_raw_sources(unsafe) -> None:
    with pytest.raises(RuntimeError):
        assert_agent_safe_payload(unsafe)


def test_public_agent_payload_accepts_opaque_structured_state() -> None:
    assert_agent_safe_payload(
        {
            "opaque_target_id": "TARGET-X17",
            "measurements": {"period": {"value": 2.2, "unit": "day"}},
            "evidence_refs": ["evidence_1", "evidence_2"],
            "parameters": {"durations_hours": [1.5, 2.0, 3.0, 4.5, 6.0]},
        }
    )
