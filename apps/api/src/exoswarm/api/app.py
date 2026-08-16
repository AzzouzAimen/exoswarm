from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from exoswarm.agents.inference_provider import FeatherlessInferenceClient
from exoswarm.agents.model_client import InferenceClient
from exoswarm.api.routes_health import router as health_router
from exoswarm.api.routes_investigations import router as investigation_router
from exoswarm.config import Settings
from exoswarm.domain.errors import (
    CapabilityNotImplementedError,
    ResultNotLockableError,
    ResultNotLockedError,
    RunNotFoundError,
    ToolPermissionError,
    UnknownToolError,
)
from exoswarm.investigation.controller import InvestigationController
from exoswarm.investigation.runner import InvestigationRunService, RunStartConflictError
from exoswarm.investigation.runtime_inputs import CandidateSourceResolver
from exoswarm.investigation.tool_registry import ScientificToolRegistry
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore
from exoswarm.services.mission_control import MissionControlService
from exoswarm.services.nasa_reveal import CachedCatalogRevealProvider
from exoswarm.services.target_registry import (
    TargetMappingNotFoundError,
    TargetRegistry,
    TargetSourceUnavailableError,
)


def create_app(
    settings: Settings | None = None,
    *,
    controller: InvestigationController | None = None,
    inference: InferenceClient | None = None,
    fallback_inference: InferenceClient | None = None,
    science_registry: ScientificToolRegistry | None = None,
    candidate_sources: CandidateSourceResolver | None = None,
    target_registry: TargetRegistry | None = None,
    run_service: InvestigationRunService | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings()
    runtime_targets = target_registry or TargetRegistry(
        runtime_settings.resolved_target_manifest_path,
        data_dir=runtime_settings.data_dir,
    )
    runtime_viewer_catalog = CachedCatalogRevealProvider(
        runtime_settings.data_dir / "ground_truth/catalog_reveal.json"
    )
    runtime_controller = controller
    if runtime_controller is None:
        if runtime_settings.agent_fallback_enabled and fallback_inference is None:
            raise ValueError(
                "AGENT_FALLBACK_ENABLED requires an explicitly configured fallback inference client"
            )
        artifacts = FileSystemRunArtifactStore(runtime_settings.runs_dir)
        runtime_inference = inference
        if runtime_inference is None and runtime_settings.featherless_api_key is not None:
            runtime_inference = FeatherlessInferenceClient.from_settings(runtime_settings)
        runtime_controller = InvestigationController(
            settings=runtime_settings,
            artifacts=artifacts,
            result_lock=ResultLockService(artifacts),
            catalog_gate=CatalogGate(
                artifacts,
                runtime_viewer_catalog,
            ),
            inference=runtime_inference,
            fallback_inference=fallback_inference,
            registry=science_registry,
            candidate_sources=candidate_sources or runtime_targets,
        )
    runtime_runner = run_service or InvestigationRunService(
        runtime_controller,
        runtime_targets,
        runs_dir=runtime_settings.runs_dir,
        timeout_seconds=runtime_settings.run_timeout_seconds,
        sse_poll_interval_seconds=runtime_settings.sse_poll_interval_seconds,
    )

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        yield
        await runtime_runner.close()

    application = FastAPI(title="ExoSwarm API", version="0.1.0", lifespan=lifespan)
    application.state.settings = runtime_settings
    application.state.controller = runtime_controller
    application.state.target_registry = runtime_targets
    application.state.viewer_catalog = runtime_viewer_catalog
    application.state.run_service = runtime_runner
    application.state.mission_control = MissionControlService(runtime_controller, runtime_runner)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(investigation_router)

    error_statuses = {
        RunNotFoundError: 404,
        ResultNotLockableError: 409,
        ResultNotLockedError: 403,
        ToolPermissionError: 403,
        UnknownToolError: 422,
        CapabilityNotImplementedError: 501,
        TargetMappingNotFoundError: 404,
        TargetSourceUnavailableError: 422,
        RunStartConflictError: 409,
    }

    for error_type, status_code in error_statuses.items():
        def handler(
            request: Request,
            exc: Exception,
            *,
            response_status: int = status_code,
        ) -> JSONResponse:
            run_id = request.path_params.get("run_id")
            payload = {
                "code": getattr(exc, "code", "EXOSWARM_ERROR"),
                "message": str(exc),
                "recoverable": response_status < 500,
            }
            if isinstance(run_id, str):
                payload["run_id"] = run_id
            return JSONResponse(
                status_code=response_status,
                content=payload,
            )

        application.add_exception_handler(error_type, handler)

    return application


app = create_app()
