class ExoSwarmError(Exception):
    code = "EXOSWARM_ERROR"


class UnknownToolError(ExoSwarmError):
    code = "UNKNOWN_TOOL"


class ToolPermissionError(ExoSwarmError):
    code = "TOOL_PERMISSION_DENIED"


class RunNotFoundError(ExoSwarmError):
    code = "RUN_NOT_FOUND"


class ResultNotLockableError(ExoSwarmError):
    code = "RESULT_NOT_LOCKABLE"


class ResultNotLockedError(ExoSwarmError):
    code = "RESULT_NOT_LOCKED"


class ModelNotConfiguredError(ExoSwarmError):
    code = "MODEL_NOT_CONFIGURED"


class CapabilityNotImplementedError(ExoSwarmError):
    code = "NOT_IMPLEMENTED"
