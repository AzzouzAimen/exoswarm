# Data, Artifacts, Blinding, and Result Lock

## Cached real inputs

The demonstrated investigations should run from cached real TESS products so the judged path does not depend on MAST/Gaia/network availability. Caching removes network fragility; it must not fabricate or alter the scientific source data.

Store provenance for every cached input, including enough metadata to identify the original data product outside the agent context.

## Identity boundary

Agent-visible identity:

```text
TARGET-X17
```

Backend-only mapping:

```text
TARGET-X17 -> real TESS/TIC/TOI identity
```

The real mapping is used only by deterministic backend capabilities that require it. It must not be serialized into agent context or pre-lock UI payloads.

## Before lock

Allowed:

- opaque target ID,
- cached TESS analysis tools,
- compact scientific evidence,
- permitted non-ground-truth contextual summaries,
- artifact references.

Unavailable:

- target identity reveal,
- NASA known planet parameters,
- confirmation status,
- ground-truth lookup tool/service.

## Evidence Ledger

Use append-only JSONL. A ledger record should include:

- evidence ID,
- timestamp,
- run/step/action IDs,
- opaque target ID,
- tool name,
- tool status,
- structured measurements with units,
- uncertainty/significance/tolerance where available,
- diagnostics/warnings,
- method and parameters,
- provenance/artifact references,
- interpretation code or deterministic hypothesis update reference,
- agent decision ID and Critic decision ID when applicable.

The ledger powers agent context, audit trails, UI state, final disposition, evaluation, and reproducibility.

## Run artifacts

Recommended scaffold layout:

```text
runs/
  TARGET-X17/
    <run-id>/
      state.json
      trace.jsonl
      result.json
      result.json.sha256
      reveal.json
      artifacts/
        raw_lightcurve.png
        cleaned_lightcurve.png
        bls_periodogram.png
        folded_lightcurve.png
        odd_even.png
        secondary_eclipse.png
        centroid.png
```

Files may be absent when their corresponding tool has not run. Do not create placeholder plots containing fake scientific values.

## Lock protocol

1. investigation reaches a lock-eligible terminal scientific disposition,
2. construct `LockedResult` only from deterministic evidence/state,
3. serialize deterministically/canonically,
4. write `result.json`,
5. compute SHA-256 over the exact locked bytes and write `result.json.sha256`,
6. persist `RESULT_LOCKED` event and lock state,
7. only now enable the ground-truth reveal capability,
8. reveal writes `reveal.json` for the same run ID and target.

The exact JSON canonicalization strategy is a scaffold implementation detail, but it must be deterministic and tested.

## Reveal protocol

`reveal.json` is a comparison artifact. It may include:

- real target identity,
- external catalog source/reference metadata,
- known period/other selected ground-truth values,
- ExoSwarm locked values,
- absolute/relative error where meaningful,
- catalog confirmation status clearly attributed to the catalog.

Do not rewrite `result.json` after reveal.

## Blind-protocol tests

CI should prove:

- ground-truth lookup cannot be called before lock,
- agent modules do not import the reveal implementation,
- pre-lock API/SSE payloads do not contain recognizable identity/ground-truth fields,
- `result.json` hash is stable for unchanged content,
- reveal refers to the same locked run,
- a reset restores the pre-reveal lock boundary.
