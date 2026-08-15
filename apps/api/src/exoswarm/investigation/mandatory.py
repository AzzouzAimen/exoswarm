MANDATORY_TESTS = frozenset({"signal_quality", "odd_even", "secondary_eclipse", "contamination"})


def missing_mandatory_tests(completed: set[str]) -> frozenset[str]:
    return MANDATORY_TESTS.difference(completed)

