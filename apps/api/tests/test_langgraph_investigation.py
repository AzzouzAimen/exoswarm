from __future__ import annotations

from collections import Counter

import pytest
from harness_support import (
    critic_policy,
    make_controller,
    make_registry,
    policy_client,
    seed_baseline,
)

from exoswarm.agents.director import (
    DirectorRoute,
    DirectorStateView,
    FreshCycleRoute,
    determine_director_route,
)
from exoswarm.agents.graph import InvestigationGraphState
from exoswarm.agents.model_client import ScriptedInferenceClient
from exoswarm.domain.enums import CriticVerdict, InvestigationStatus, ToolExecutionStatus


def _director_view(**changes) -> DirectorStateView:
    values = {
        "status": InvestigationStatus.INITIALIZED,
        "terminal": False,
        "has_prepared_execution": False,
        "has_uncommitted_result": False,
        "skeptic_decision_id": None,
        "critic_decision_id": None,
        "critic_verdict": None,
        "critic_requires_resolution": False,
        "fresh_cycle_route": FreshCycleRoute.RUN_MANDATORY,
    }
    values.update(changes)
    return DirectorStateView(**values)


@pytest.mark.parametrize(
    ("view", "expected"),
    [
        pytest.param(
            _director_view(
                terminal=True,
                has_prepared_execution=True,
                has_uncommitted_result=True,
                skeptic_decision_id="skeptic-1",
            ),
            DirectorRoute.NOOP_TERMINAL,
            id="terminal-outranks-all-work",
        ),
        pytest.param(
            _director_view(
                has_prepared_execution=True,
                has_uncommitted_result=True,
                skeptic_decision_id="skeptic-1",
            ),
            DirectorRoute.RECOVER_PREPARED,
            id="prepared-outranks-result-and-agent-work",
        ),
        pytest.param(
            _director_view(
                has_uncommitted_result=True,
                skeptic_decision_id="skeptic-1",
            ),
            DirectorRoute.EVALUATE_RESULT,
            id="result-outranks-agent-work",
        ),
        pytest.param(
            _director_view(skeptic_decision_id="skeptic-1", fresh_cycle_route=None),
            DirectorRoute.RESUME_CRITIC,
            id="skeptic-awaits-critic",
        ),
        pytest.param(
            _director_view(
                skeptic_decision_id="skeptic-1",
                critic_decision_id="critic-1",
                critic_verdict=CriticVerdict.REVISE,
                critic_requires_resolution=True,
                fresh_cycle_route=None,
            ),
            DirectorRoute.RESUME_CRITIC,
            id="revision-awaits-budget-resolution",
        ),
        pytest.param(
            _director_view(
                skeptic_decision_id="skeptic-1",
                critic_decision_id="critic-1",
                critic_verdict=CriticVerdict.VETO,
                fresh_cycle_route=None,
            ),
            DirectorRoute.FINALIZE,
            id="veto-finalizes",
        ),
        pytest.param(
            _director_view(
                skeptic_decision_id="skeptic-1",
                critic_decision_id="critic-1",
                critic_verdict=CriticVerdict.APPROVE,
                fresh_cycle_route=None,
            ),
            DirectorRoute.EXECUTE_APPROVED_ACTION,
            id="approval-executes",
        ),
        pytest.param(
            _director_view(fresh_cycle_route=FreshCycleRoute.RUN_MANDATORY),
            DirectorRoute.RUN_MANDATORY,
            id="fresh-mandatory",
        ),
        pytest.param(
            _director_view(fresh_cycle_route=FreshCycleRoute.CALL_SKEPTIC),
            DirectorRoute.CALL_SKEPTIC,
            id="fresh-skeptic",
        ),
        pytest.param(
            _director_view(fresh_cycle_route=FreshCycleRoute.FINALIZE),
            DirectorRoute.FINALIZE,
            id="fresh-finalize",
        ),
        pytest.param(
            _director_view(fresh_cycle_route=FreshCycleRoute.TERMINATE),
            DirectorRoute.TERMINATE,
            id="fresh-terminate",
        ),
    ],
)
def test_director_route_precedence_is_locked(
    view: DirectorStateView, expected: DirectorRoute
) -> None:
    assert determine_director_route(view) == expected


def test_director_rejects_nonterminal_state_without_policy_route() -> None:
    with pytest.raises(ValueError, match="no controller policy route"):
        determine_director_route(_director_view(fresh_cycle_route=None))


def test_compiled_langgraph_is_the_only_controller_topology(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))

    assert not hasattr(controller, "_advance_locked")
    assert controller._investigation_graph.checkpointer is None  # noqa: SLF001
    assert {
        "recover_prepared_execution",
        "director_route",
        "run_mandatory_action",
        "skeptic_decision",
        "critic_review",
        "critic_route",
        "execute_adaptive",
        "evaluate_result",
        "finalize",
        "terminate",
    }.issubset(controller._investigation_graph.nodes)  # noqa: SLF001

    graph = controller._investigation_graph.get_graph()  # noqa: SLF001
    actual_edges = {
        (edge.source, edge.target, edge.data, edge.conditional) for edge in graph.edges
    }
    expected_edges = {
        ("__start__", "recover_prepared_execution", None, False),
        ("recover_prepared_execution", "director_route", None, False),
        ("director_route", "recover_prepared_execution", "RECOVER_PREPARED", True),
        ("director_route", "run_mandatory_action", "RUN_MANDATORY", True),
        ("director_route", "skeptic_decision", "CALL_SKEPTIC", True),
        ("director_route", "critic_review", "RESUME_CRITIC", True),
        ("director_route", "execute_adaptive", "EXECUTE_APPROVED_ACTION", True),
        ("director_route", "evaluate_result", "EVALUATE_RESULT", True),
        ("director_route", "finalize", "FINALIZE", True),
        ("director_route", "terminate", "TERMINATE", True),
        ("director_route", "__end__", "NOOP_TERMINAL", True),
        ("run_mandatory_action", "evaluate_result", None, False),
        ("skeptic_decision", "critic_review", None, False),
        ("critic_review", "critic_route", None, False),
        ("critic_route", "execute_adaptive", "EXECUTE_APPROVED_ACTION", True),
        ("critic_route", "finalize", "FINALIZE", True),
        ("execute_adaptive", "evaluate_result", None, False),
        ("evaluate_result", "__end__", None, False),
        ("finalize", "__end__", None, False),
        ("terminate", "__end__", None, False),
    }
    assert actual_edges == expected_edges
    assert set(InvestigationGraphState.__annotations__) == {"run_id", "current_route"}


@pytest.mark.asyncio
async def test_selected_director_route_is_persisted_as_audit_event(tmp_path) -> None:
    controller = make_controller(tmp_path, policy_client(), make_registry("clean"))
    state = controller.create("TARGET-X17")

    await controller.advance(state.run_id)

    route = next(
        event for event in controller.events(state.run_id) if event.type == "director.route"
    )
    assert route.payload == {
        "route": DirectorRoute.RUN_MANDATORY.value,
        "source": "director",
        "status": InvestigationStatus.INITIALIZED.value,
    }


@pytest.mark.asyncio
async def test_restart_after_skeptic_resumes_at_critic_without_second_skeptic_call(
    tmp_path,
) -> None:
    calls: Counter[str] = Counter()
    registry = make_registry("eclipsing_binary", calls=calls)
    first = make_controller(tmp_path, policy_client(), registry)
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "eclipsing_binary")

    assert first.determine_route(state.run_id) == DirectorRoute.CALL_SKEPTIC
    await first.run_skeptic_node(state.run_id)

    restarted = make_controller(
        tmp_path,
        ScriptedInferenceClient({"critic": [critic_policy]}),
        registry,
    )
    final = await restarted.advance(state.run_id)

    assert final.status == InvestigationStatus.READY_TO_LOCK
    assert final.step_count == 1
    assert final.model_call_count == 2
    assert len(final.accepted_decisions) == 1
    assert len(final.critic_decisions) == 1
    assert calls["harmonic_test"] == 1
    critic_route = next(
        event
        for event in restarted.events(state.run_id)
        if event.type == "director.route" and event.payload["source"] == "critic_verdict"
    )
    assert critic_route.payload["route"] == DirectorRoute.EXECUTE_APPROVED_ACTION.value


@pytest.mark.asyncio
async def test_restart_after_critic_executes_without_repeating_either_model_call(
    tmp_path,
) -> None:
    calls: Counter[str] = Counter()
    registry = make_registry("contamination", calls=calls)
    first = make_controller(tmp_path, policy_client(), registry)
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "contamination")
    assert first.determine_route(state.run_id) == DirectorRoute.CALL_SKEPTIC
    await first.run_skeptic_node(state.run_id)
    await first.run_critic_node(state.run_id)

    restarted = make_controller(tmp_path, ScriptedInferenceClient({}), registry)
    final = await restarted.advance(state.run_id)

    assert final.status == InvestigationStatus.READY_TO_LOCK
    assert final.model_call_count == 2
    assert len(final.accepted_decisions) == 1
    assert len(final.critic_decisions) == 1
    assert final.critic_revision_count == 1
    assert calls["harmonic_test"] == 0
    assert calls["centroid_localization"] == 1


@pytest.mark.asyncio
async def test_restart_after_evidence_commit_only_evaluates_durable_result(tmp_path) -> None:
    calls: Counter[str] = Counter()
    registry = make_registry("eclipsing_binary", calls=calls)
    first = make_controller(tmp_path, policy_client(), registry)
    state = first.create("TARGET-X17")
    seed_baseline(first, state.run_id, "eclipsing_binary")
    assert first.determine_route(state.run_id) == DirectorRoute.CALL_SKEPTIC
    await first.run_skeptic_node(state.run_id)
    await first.run_critic_node(state.run_id)
    assert first.resolve_critic_verdict(state.run_id) == DirectorRoute.EXECUTE_APPROVED_ACTION
    await first.run_adaptive_cycle(state.run_id)
    interrupted = first.get(state.run_id)
    assert interrupted.status == InvestigationStatus.UPDATING_EVIDENCE
    assert interrupted.tool_executions[-1].status == ToolExecutionStatus.COMPLETED

    restarted = make_controller(tmp_path, ScriptedInferenceClient({}), registry)
    final = await restarted.advance(state.run_id)

    assert final.status == InvestigationStatus.READY_TO_LOCK
    assert final.model_call_count == 2
    assert calls["harmonic_test"] == 1
    assert len(restarted.evidence(state.run_id)) == 5
