"""Report readiness of the cached-real deterministic reproduction path."""

from pathlib import Path


def main() -> None:
    case_path = Path("evals/fixtures/cached_real_tess_case.json")
    if not case_path.exists():
        print(
            "ExoSwarm cached candidate pipeline is implemented, but reproduction is blocked: "
            "add evals/fixtures/cached_real_tess_case.json and its referenced local SPOC FITS."
        )
        return
    print(
        "Cached-real manifest found. Automated locked-result reproduction remains outside this "
        "milestone; run the cached-real science acceptance test."
    )


if __name__ == "__main__":
    main()
