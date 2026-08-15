from exoswarm.science.contracts import not_implemented_result


def load_cached_lightcurve(run_id, action_id, target_id, parameters):
    return not_implemented_result(
        tool_name="load_cached_lightcurve",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )


def load_cached_tpf(run_id, action_id, target_id, parameters):
    return not_implemented_result(
        tool_name="load_cached_tpf",
        run_id=run_id,
        action_id=action_id,
        target_id=target_id,
        parameters=parameters,
    )

