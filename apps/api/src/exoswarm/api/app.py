from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from exoswarm.security.catalog_gate import CatalogGate
from exoswarm.security.result_lock import ResultLockService
from exoswarm.services.artifacts import FileSystemRunArtifactStore
from exoswarm.services.nasa_reveal import UnconfiguredCatalogRevealProvider


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()
    artifacts = FileSystemRunArtifactStore(runtime_settings.runs_dir)
    controller = InvestigationController(
        settings=runtime_settings,
        artifacts=artifacts,
        result_lock=ResultLockService(artifacts),
        catalog_gate=CatalogGate(artifacts, UnconfiguredCatalogRevealProvider()),
    )

    application = FastAPI(title="ExoSwarm API", version="0.1.0")
    application.state.settings = runtime_settings
    application.state.controller = controller
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
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
    }

    for error_type, status_code in error_statuses.items():
        def handler(
            request: Request,
            exc: Exception,
            *,
            response_status: int = status_code,
        ) -> JSONResponse:
            del request
            return JSONResponse(
                status_code=response_status,
                content={
                    "code": getattr(exc, "code", "EXOSWARM_ERROR"),
                    "message": str(exc),
                    "recoverable": response_status < 500,
                },
            )

        application.add_exception_handler(error_type, handler)

    return application


app = create_app()
