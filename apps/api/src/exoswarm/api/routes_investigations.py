from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from exoswarm.api.dependencies import get_controller
from exoswarm.api.sse import encode_sse
from exoswarm.domain.models import InvestigationState, LockReceipt, RevealResult
from exoswarm.investigation.controller import InvestigationController
from exoswarm.security.blinding import agent_safe_state
from exoswarm.services.target_registry import TargetRegistry

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


@router.get("/targets")
def list_targets(request: Request) -> list[dict[str, object]]:
    registry = TargetRegistry(request.app.state.settings.data_dir / "targets/manifest.example.json")
    return registry.list_agent_safe()


@router.post("/investigations", response_model=CreateInvestigationResponse, status_code=201)
def create_investigation(
    body: CreateInvestigationRequest, controller: Controller
) -> CreateInvestigationResponse:
    state = controller.create(body.opaque_target_id)
    return CreateInvestigationResponse(
        run_id=state.run_id,
        opaque_target_id=state.opaque_target_id,
        status=state.status,
        lock_state=state.lock_state,
        event_stream_url=f"/api/investigations/{state.run_id}/events",
    )


@router.get("/investigations/{run_id}")
def read_investigation(run_id: str, controller: Controller) -> dict[str, object]:
    return agent_safe_state(controller.get(run_id))


@router.get("/investigations/{run_id}/events")
def stream_events(run_id: str, controller: Controller) -> StreamingResponse:
    return StreamingResponse(
        encode_sse(controller.events(run_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/investigations/{run_id}/lock", response_model=LockReceipt)
def lock_investigation(run_id: str, controller: Controller) -> LockReceipt:
    return controller.lock(run_id)


@router.post("/investigations/{run_id}/reveal", response_model=RevealResult)
def reveal_investigation(run_id: str, controller: Controller) -> RevealResult:
    return controller.reveal(run_id)


@router.get("/investigations/{run_id}/artifacts")
def artifact_metadata(run_id: str, controller: Controller) -> dict[str, object]:
    state: InvestigationState = controller.get(run_id)
    return {"run_id": run_id, "opaque_target_id": state.opaque_target_id, "artifacts": []}

