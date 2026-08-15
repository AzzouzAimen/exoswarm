"""Deterministic hypothesis and disposition rules derived from committed evidence."""

from collections.abc import Collection

from exoswarm.domain.models import InvestigationState

DECISIVE_INTERPRETATIONS = frozenset(
    {
        "CLEAN_PLANET_LIKE",
        "ODD_EVEN_MISMATCH",
        "CONTAMINATION_LIKELY",
        "WEAK_NOISY",
    }
)
WEAK_PLANETARY_INTERPRETATIONS = frozenset(
    {
        "SECONDARY_ECLIPSE_DETECTED",
        "CONTAMINATION_POSSIBLE",
        "HARMONIC_ALIAS_PREFERRED",
    }
)
_HYPOTHESIS_UPDATES = {
    "CLEAN_PLANET_LIKE": (["planetary_transit"], "eclipsing_binary"),
    "ODD_EVEN_MISMATCH": (["eclipsing_binary"], "planetary_transit"),
    "CONTAMINATION_LIKELY": (["background_contamination"], "planetary_transit"),
    "WEAK_NOISY": (["instrumental_or_variable_noise"], "planetary_transit"),
}


def updated_hypotheses(
    state: InvestigationState, interpretation_code: str | None
) -> tuple[list[str], str | None]:
    hypotheses, strongest = _HYPOTHESIS_UPDATES.get(
        interpretation_code,
        (state.active_hypotheses, state.strongest_unresolved_alternative),
    )
    return list(hypotheses), strongest


def decisive_interpretation(codes: Collection[str]) -> str | None:
    matches = sorted(DECISIVE_INTERPRETATIONS.intersection(codes))
    return matches[0] if matches else None


def has_weak_planetary_interpretation(codes: Collection[str]) -> bool:
    return bool(WEAK_PLANETARY_INTERPRETATIONS.intersection(codes))
