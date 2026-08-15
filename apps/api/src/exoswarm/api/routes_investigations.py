from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from exoswarm.api.dependencies import get_controller
from exoswarm.api.sse import encode_sse
from exoswarm.domain.models import ArtifactMetadata, InvestigationState, LockReceipt, RevealResult
from exoswarm.investigation.controller import InvestigationController
from exoswarm.investigation.runner import InvestigationRunService, RunExecutionSnapshot
from exoswarm.security.blinding import agent_safe_state, assert_agent_safe_payload

router = APIRouter(prefix="/api", tags=["investigations"])
Controller = Annotated[InvestigationController, Depends(get_controller)]

class CreateInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opaque_target_id: str = Field(pattern=r"^TARGET-[A-Z0-9-]+$")


class CreateInvestigationResponse(BaseModel):
    run_id: str
    opaque_target_id: str
    status: str
    lock_state: str
    event_stream_url: str
    execution: RunExecutionSnapshot


class ArtifactListResponse(BaseModel):
    run_id: str
    opaque_target_id: str
    artifacts: list[ArtifactMetadata]


def _runner(request: Request) -> InvestigationRunService:
    return request.app.state.run_service


@router.get("/targets")
def list_targets(request: Request) -> list[dict[str, object]]:
    payload = request.app.state.target_registry.list_agent_safe()
    assert_agent_safe_payload(payload)
    return payload


@router.post("/investigations", response_model=CreateInvestigationResponse, status_code=202)
async def create_investigation(
    body: CreateInvestigationRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128),
    ],
) -> CreateInvestigationResponse:
    state, execution = await _runner(request).create_and_start(
        body.opaque_target_id, idempotency_key
    )
    return CreateInvestigationResponse(
        run_id=state.run_id,
        opaque_target_id=state.opaque_target_id,
        status=state.status,
        lock_state=state.lock_state,
        event_stream_url=f"/api/investigations/{state.run_id}/events",
        execution=execution,
    )


@router.post(
    "/investigations/{run_id}/resume",
    response_model=CreateInvestigationResponse,
    status_code=202,
)
async def resume_investigation(
    run_id: str, request: Request
) -> CreateInvestigationResponse:
    state, execution = await _runner(request).resume(run_id)
    return CreateInvestigationResponse(
        run_id=state.run_id,
        opaque_target_id=state.opaque_target_id,
        status=state.status,
        lock_state=state.lock_state,
        event_stream_url=f"/api/investigations/{state.run_id}/events",
        execution=execution,
    )


@router.get("/investigations/{run_id}")
def read_investigation(
    run_id: str, request: Request, controller: Controller
) -> dict[str, object]:
    payload = agent_safe_state(controller.get(run_id))
    payload["execution"] = _runner(request).inspect(run_id).model_dump(mode="json")
    assert_agent_safe_payload(payload)
    return payload


@router.get("/investigations/{run_id}/events")
def stream_events(
    run_id: str,
    request: Request,
    controller: Controller,
    after_sequence: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    controller.get(run_id)

    async def public_events() -> AsyncIterator[str]:
        async for event in _runner(request).stream_events(
            run_id, after_sequence=after_sequence
        ):
            assert_agent_safe_payload(event.model_dump(mode="json"))
            for encoded in encode_sse((event,)):
                yield encoded

    return StreamingResponse(
        public_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/investigations/{run_id}/lock", response_model=LockReceipt)
def lock_investigation(run_id: str, controller: Controller) -> LockReceipt:
    return controller.lock(run_id)


@router.post("/investigations/{run_id}/reveal", response_model=RevealResult)
def reveal_investigation(run_id: str, controller: Controller) -> RevealResult:
    return controller.reveal(run_id)


@router.get("/investigations/{run_id}/artifacts", response_model=ArtifactListResponse)
def artifact_metadata(run_id: str, controller: Controller) -> ArtifactListResponse:
    state: InvestigationState = controller.get(run_id)
    payload = ArtifactListResponse(
        run_id=run_id,
        opaque_target_id=state.opaque_target_id,
        artifacts=controller.artifacts.list_artifacts(state),
    )
    assert_agent_safe_payload(payload.model_dump(mode="json"))
    return payload
