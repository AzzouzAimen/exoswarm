"""The sole investigation topology, implemented with LangGraph."""

from __future__ import annotations

from typing import Protocol, Required, TypedDict

from langgraph.graph import END, START, StateGraph

from exoswarm.agents.director import DirectorRoute


class InvestigationGraphState(TypedDict, total=False):
    """Disposable routing envelope; durable investigation data lives in artifacts."""

    run_id: Required[str]
    current_route: DirectorRoute


class InvestigationGraphUpdate(TypedDict, total=False):
    """Partial node update; durable scientific state is never copied into the graph."""

    current_route: DirectorRoute


class InvestigationGraphRuntime(Protocol):
    """Guarded controller operations consumed by graph node adapters."""

    async def recover_prepared_execution(self, run_id: str) -> InvestigationGraphUpdate: ...

    def determine_route(self, run_id: str) -> DirectorRoute: ...

    def record_director_route(
        self, run_id: str, route: DirectorRoute, *, source: str
    ) -> None: ...

    async def run_mandatory_cycle(self, run_id: str) -> InvestigationGraphUpdate: ...

    async def run_skeptic_node(self, run_id: str) -> InvestigationGraphUpdate: ...

    async def run_critic_node(self, run_id: str) -> InvestigationGraphUpdate: ...

    def resolve_critic_verdict(self, run_id: str) -> DirectorRoute: ...

    async def run_adaptive_cycle(self, run_id: str) -> InvestigationGraphUpdate: ...

    def evaluate_cycle_result(self, run_id: str) -> InvestigationGraphUpdate: ...

    def finalize_cycle(self, run_id: str) -> InvestigationGraphUpdate: ...

    def terminate_cycle(self, run_id: str) -> InvestigationGraphUpdate: ...


def build_investigation_graph(runtime: InvestigationGraphRuntime):
    """Compile one stateless durable-cycle graph around controller operations.

    No LangGraph checkpointer is installed.  Every node reloads ExoSwarm's
    authoritative artifacts through ``run_id``, and every side effect is made
    durable by the controller before the node returns.
    """

    async def recover_prepared_execution(
        state: InvestigationGraphState,
    ) -> InvestigationGraphUpdate:
        return await runtime.recover_prepared_execution(state["run_id"])

    def director_route(state: InvestigationGraphState) -> InvestigationGraphUpdate:
        route = runtime.determine_route(state["run_id"])
        runtime.record_director_route(state["run_id"], route, source="director")
        return {"current_route": route}

    async def run_mandatory_action(
        state: InvestigationGraphState,
    ) -> InvestigationGraphUpdate:
        return await runtime.run_mandatory_cycle(state["run_id"])

    async def skeptic_decision(
        state: InvestigationGraphState,
    ) -> InvestigationGraphUpdate:
        return await runtime.run_skeptic_node(state["run_id"])

    async def critic_review(state: InvestigationGraphState) -> InvestigationGraphUpdate:
        return await runtime.run_critic_node(state["run_id"])

    def critic_route(state: InvestigationGraphState) -> InvestigationGraphUpdate:
        route = runtime.resolve_critic_verdict(state["run_id"])
        runtime.record_director_route(state["run_id"], route, source="critic_verdict")
        return {"current_route": route}

    async def execute_adaptive(
        state: InvestigationGraphState,
    ) -> InvestigationGraphUpdate:
        return await runtime.run_adaptive_cycle(state["run_id"])

    def evaluate_result(state: InvestigationGraphState) -> InvestigationGraphUpdate:
        return runtime.evaluate_cycle_result(state["run_id"])

    def finalize(state: InvestigationGraphState) -> InvestigationGraphUpdate:
        return runtime.finalize_cycle(state["run_id"])

    def terminate(state: InvestigationGraphState) -> InvestigationGraphUpdate:
        return runtime.terminate_cycle(state["run_id"])

    def selected_route(state: InvestigationGraphState) -> DirectorRoute:
        return state["current_route"]

    builder = StateGraph(InvestigationGraphState)
    builder.add_node("recover_prepared_execution", recover_prepared_execution)
    builder.add_node("director_route", director_route)
    builder.add_node("run_mandatory_action", run_mandatory_action)
    builder.add_node("skeptic_decision", skeptic_decision)
    builder.add_node("critic_review", critic_review)
    builder.add_node("critic_route", critic_route)
    builder.add_node("execute_adaptive", execute_adaptive)
    builder.add_node("evaluate_result", evaluate_result)
    builder.add_node("finalize", finalize)
    builder.add_node("terminate", terminate)

    builder.add_edge(START, "recover_prepared_execution")
    builder.add_edge("recover_prepared_execution", "director_route")
    builder.add_conditional_edges(
        "director_route",
        selected_route,
        {
            DirectorRoute.RECOVER_PREPARED: "recover_prepared_execution",
            DirectorRoute.RUN_MANDATORY: "run_mandatory_action",
            DirectorRoute.CALL_SKEPTIC: "skeptic_decision",
            DirectorRoute.RESUME_CRITIC: "critic_review",
            DirectorRoute.EXECUTE_APPROVED_ACTION: "execute_adaptive",
            DirectorRoute.EVALUATE_RESULT: "evaluate_result",
            DirectorRoute.FINALIZE: "finalize",
            DirectorRoute.TERMINATE: "terminate",
            DirectorRoute.NOOP_TERMINAL: END,
        },
    )
    builder.add_edge("run_mandatory_action", "evaluate_result")
    builder.add_edge("skeptic_decision", "critic_review")
    builder.add_edge("critic_review", "critic_route")
    builder.add_conditional_edges(
        "critic_route",
        selected_route,
        {
            DirectorRoute.EXECUTE_APPROVED_ACTION: "execute_adaptive",
            DirectorRoute.FINALIZE: "finalize",
        },
    )
    builder.add_edge("execute_adaptive", "evaluate_result")
    builder.add_edge("evaluate_result", END)
    builder.add_edge("finalize", END)
    builder.add_edge("terminate", END)

    return builder.compile()


__all__ = [
    "InvestigationGraphRuntime",
    "InvestigationGraphState",
    "InvestigationGraphUpdate",
    "build_investigation_graph",
]
