from exoswarm.science.contracts import not_implemented_result


def measure_transit(run_id, action_id, target_id, parameters):
    return not_implemented_result(
        tool_name="measure_transit",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )

