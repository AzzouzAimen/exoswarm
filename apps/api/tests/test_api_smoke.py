from fastapi.testclient import TestClient

from exoswarm.api.app import create_app
from exoswarm.config import Settings
from exoswarm.security.blinding import FORBIDDEN_AGENT_FIELDS


def test_health_create_read_stream_and_prelock_guards(tmp_path) -> None:
    settings = Settings(runs_dir=tmp_path / "runs", data_dir=tmp_path / "data")
    client = TestClient(create_app(settings))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "exoswarm-api"}

    created = client.post(
        "/api/investigations", json={"opaque_target_id": "TARGET-X17"}
    )
    assert created.status_code == 201
    run_id = created.json()["run_id"]

    state_response = client.get(f"/api/investigations/{run_id}")
    assert state_response.status_code == 200
    assert not FORBIDDEN_AGENT_FIELDS.intersection(state_response.json())

    stream = client.get(f"/api/investigations/{run_id}/events")
    assert stream.status_code == 200
    assert "event: investigation.created" in stream.text
    assert f'"run_id":"{run_id}"' in stream.text
    assert '"step_id":"step_0000"' in stream.text
    assert '"action_id":"action_' in stream.text
    assert not any(field in stream.text for field in FORBIDDEN_AGENT_FIELDS)

    reveal = client.post(f"/api/investigations/{run_id}/reveal")
    assert reveal.status_code == 403
    assert reveal.json()["code"] == "RESULT_NOT_LOCKED"

    lock = client.post(f"/api/investigations/{run_id}/lock")
    assert lock.status_code == 409
    assert lock.json()["code"] == "RESULT_NOT_LOCKABLE"
