from typing import Any

from exoswarm.domain.models import ScientificToolResult
from exoswarm.science.contracts import unavailable_tool_result


def localize_centroid(
    run_id: str,
    action_id: str,
    target_id: str,
    parameters: dict[str, Any],
) -> ScientificToolResult:
    """Report the unavailable centroid capability through the standard tool contract."""

    return unavailable_tool_result(
        tool_name="centroid_localization",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )
