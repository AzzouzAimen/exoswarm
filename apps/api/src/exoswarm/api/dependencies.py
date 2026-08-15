from fastapi import Request

from exoswarm.investigation.controller import InvestigationController


def get_controller(request: Request) -> InvestigationController:
    return request.app.state.controller

