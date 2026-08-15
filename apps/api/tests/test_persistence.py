from exoswarm.api.app import create_app
from exoswarm.config import Settings


def test_controller_recovers_state_and_trace_from_artifacts(tmp_path) -> None:
    settings = Settings(runs_dir=tmp_path / "runs", data_dir=tmp_path / "data")
    first = create_app(settings).state.controller
    created = first.create("TARGET-X17")

    restarted = create_app(settings).state.controller
    recovered = restarted.get(created.run_id)
    events = restarted.events(created.run_id)

    assert recovered == created
    assert len(events) == 1
    assert events[0].run_id == created.run_id
    assert events[0].action_id.startswith("action_")
