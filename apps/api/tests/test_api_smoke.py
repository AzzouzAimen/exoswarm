import asyncio
import json
import time

from fastapi.testclient import TestClient
from harness_support import (
    critic_policy,
    make_controller,
    make_registry,
    policy_client,
    seed_baseline,
    skeptic_policy,
)

from exoswarm.agents.inference_provider import FeatherlessInferenceClient
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.api.app import create_app
from exoswarm.config import Settings
from exoswarm.security.blinding import FORBIDDEN_AGENT_FIELDS
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.services.nasa_reveal import CachedCatalogRevealProvider
from exoswarm.services.target_registry import TargetRegistry


def test_health_create_read_stream_and_prelock_guards(tmp_path) -> None:
    settings = Settings(runs_dir=tmp_path / "runs", data_dir=tmp_path / "data")
    source = settings.data_dir / "cached/lightcurves/private-source.fits"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture")
    manifest = settings.data_dir / "targets/source_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "targets": [
                    {
                        "opaque_target_id": "TARGET-X17",
                        "cached_lightcurve_path": "cached/lightcurves/private-source.fits",
                        "cached_tpf_path": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    targets = TargetRegistry(manifest, data_dir=settings.data_dir)
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    client = TestClient(
        create_app(settings, controller=controller, target_registry=targets)
    )
    client.__enter__()

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "exoswarm-api"}

    targets_response = client.get("/api/targets")
    assert targets_response.status_code == 200
    assert targets_response.json() == [
        {
            "opaque_target_id": "TARGET-X17",
            "cached_lightcurve_available": True,
            "cached_tpf_available": False,
        }
    ]
    assert "private-source.fits" not in targets_response.text

    created = client.post(
        "/api/investigations",
        json={"opaque_target_id": "TARGET-X17"},
        headers={"Idempotency-Key": "api-smoke-request"},
    )
    assert created.status_code == 202
    run_id = created.json()["run_id"]

    duplicate = client.post(
        "/api/investigations",
        json={"opaque_target_id": "TARGET-X17"},
        headers={"Idempotency-Key": "api-smoke-request"},
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["run_id"] == run_id

    missing = client.post(
        "/api/investigations",
        json={"opaque_target_id": "TARGET-MISSING"},
        headers={"Idempotency-Key": "missing-api-request"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "TARGET_MAPPING_NOT_FOUND"

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        state_response = client.get(f"/api/investigations/{run_id}")
        if not state_response.json()["execution"]["active"]:
            break
        time.sleep(0.01)

    assert state_response.status_code == 200
    assert not FORBIDDEN_AGENT_FIELDS.intersection(state_response.json())
    assert "private-source.fits" not in state_response.text

    stream = client.get(f"/api/investigations/{run_id}/events")
    assert stream.status_code == 200
    assert "event: investigation.created" in stream.text
    assert f'"run_id":"{run_id}"' in stream.text
    assert '"step_id":"step_0000"' in stream.text
    assert '"action_id":"action_' in stream.text
    assert not any(field in stream.text for field in FORBIDDEN_AGENT_FIELDS)
    assert "private-source.fits" not in stream.text
    event_payloads = [
        json.loads(line.removeprefix("data: "))
        for line in stream.text.splitlines()
        if line.startswith("data: ")
    ]
    sequences = [event["sequence"] for event in event_payloads]
    assert sequences == list(range(1, len(sequences) + 1))

    resumed = client.post(f"/api/investigations/{run_id}/resume")
    assert resumed.status_code == 202
    assert resumed.json()["run_id"] == run_id
    assert not resumed.json()["execution"]["active"]

    reveal = client.post(f"/api/investigations/{run_id}/reveal")
    assert reveal.status_code == 403
    assert reveal.json()["code"] == "RESULT_NOT_LOCKED"

    lock = client.post(f"/api/investigations/{run_id}/lock")
    assert lock.status_code == 200
    client.__exit__(None, None, None)


def test_app_composes_live_inference_only_when_configured(tmp_path, monkeypatch) -> None:
    scripted = policy_client()
    settings = Settings(
        runs_dir=tmp_path / "runs",
        data_dir=tmp_path / "data",
        featherless_api_key="test-secret",
    )
    monkeypatch.setattr(
        FeatherlessInferenceClient,
        "from_settings",
        classmethod(lambda cls, configured: scripted),
    )

    configured = create_app(settings)
    assert configured.state.controller.inference is scripted

    injected = policy_client()
    explicit = create_app(settings, inference=injected)
    assert explicit.state.controller.inference is injected


def test_api_artifacts_reveal_success_and_tampered_hash_failure(tmp_path) -> None:
    settings = Settings(runs_dir=tmp_path / "runs", data_dir=tmp_path / "data")
    catalog_path = settings.data_dir / "ground_truth/catalog_reveal.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "targets": [
                    {
                        "opaque_target_id": "TARGET-X17",
                        "target_name": "Backend-only fixture identity",
                        "tic_id": "123456789",
                        "catalog_disposition": "TEST_FIXTURE",
                        "catalog_source": "NASA Exoplanet Archive test fixture",
                        "catalog_source_url": "https://exoplanetarchive.ipac.caltech.edu/",
                        "known_values": {"period_days": 3.2},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    controller = make_controller(
        tmp_path,
        ScriptedInferenceClient(
            {
                "skeptic": [skeptic_policy, skeptic_policy],
                "critic": [critic_policy, critic_policy],
            }
        ),
        make_registry("clean"),
    )
    controller.catalog_gate = CatalogGate(
        controller.artifacts, CachedCatalogRevealProvider(catalog_path)
    )
    ready_runs = []
    for _ in range(2):
        state = controller.create("TARGET-X17")
        seed_baseline(controller, state.run_id, "clean")
        ready_runs.append(asyncio.run(controller.advance(state.run_id)).run_id)

    targets = TargetRegistry(
        settings.data_dir / "targets/source_manifest.json",
        data_dir=settings.data_dir,
    )
    with TestClient(
        create_app(settings, controller=controller, target_registry=targets)
    ) as client:
        public_paths = client.get("/openapi.json").json()["paths"]
        assert "/api/investigations/{run_id}/lock" not in public_paths
        assert "/api/investigations/{run_id}/reveal" not in public_paths
        viewer_targets = client.get("/api/viewer/targets")
        assert viewer_targets.status_code == 200
        assert viewer_targets.json()[0]["target_name"] == "Backend-only fixture identity"
        assert viewer_targets.json()[0]["catalog_disposition"] == "TEST_FIXTURE"
        viewer_target = client.get("/api/viewer/targets/TARGET-X17")
        assert viewer_target.status_code == 200
        assert viewer_target.json()["known_values"] == {"period_days": 3.2}
        assert client.get("/api/viewer/targets/TARGET-MISSING").status_code == 404

        successful_run, tampered_run = ready_runs
        artifacts_before_lock = client.get(
            f"/api/investigations/{successful_run}/artifacts"
        )
        assert artifacts_before_lock.status_code == 200
        listed = artifacts_before_lock.json()["artifacts"]
        assert listed
        assert {item["relative_path"] for item in listed}.issuperset(
            {"evidence.jsonl", "trace.jsonl", "inference_summary.json"}
        )
        assert str(tmp_path) not in artifacts_before_lock.text

        locked = client.post(f"/api/investigations/{successful_run}/lock")
        assert locked.status_code == 200
        revealed = client.post(f"/api/investigations/{successful_run}/reveal")
        assert revealed.status_code == 200
        assert revealed.json()["locked_result_sha256"] == locked.json()["sha256"]

        tampered_lock = client.post(f"/api/investigations/{tampered_run}/lock")
        assert tampered_lock.status_code == 200
        tampered_state = controller.get(tampered_run)
        controller.artifacts.write_bytes(tampered_state, "result.json", b"{}")
        rejected = client.post(f"/api/investigations/{tampered_run}/reveal")
        assert rejected.status_code == 403
        assert rejected.json()["code"] == "RESULT_NOT_LOCKED"
        assert "hash verification failed" in rejected.json()["message"]
