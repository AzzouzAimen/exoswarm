# Data, Artifacts, and Viewer/Agent Isolation

## Cached real inputs

The demonstrated investigations should run from cached real TESS products so the judged path does not depend on MAST/Gaia/network availability. Caching removes network fragility; it must not fabricate or alter the scientific source data.

Store provenance for every cached input, including enough metadata to identify the original data product outside the agent context.

## Identity boundary

Agent-visible identity:

```text
TARGET-X17
```

Backend mapping:

```text
TARGET-X17 -> real TESS/TIC/TOI identity
```

The real mapping is used by deterministic backend capabilities and by a separate human-viewer
projection. It must never be serialized into agent context, investigation state, agent-safe API
payloads, SSE events, or agent tools.

## Agent-visible data throughout the run

Allowed:

- opaque target ID,
- cached TESS analysis tools,
- compact scientific evidence,
- permitted non-ground-truth contextual summaries,
- artifact references.

Always unavailable to agents:

- target identity,
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
      inference_summary.json
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

`inference_summary.json` is derived from model-call trace records at terminal state. It contains the
measured fields defined in `docs/inference.md`; unavailable provider usage is serialized as null or
an explicit `not_measured` state, never an estimate. It must not contain prompts with hidden data,
secrets, or chain-of-thought.

## Internal audit lock

The primary demo does not ask the user to commit or reveal anything. The viewer reference is already
visible and the final comparison opens automatically. The existing lock artifacts remain useful for
offline reproduction and tamper-evidence only:

1. investigation reaches a lock-eligible terminal scientific disposition,
2. construct `LockedResult` only from deterministic evidence/state,
3. serialize deterministically/canonically,
4. write `result.json`,
5. compute SHA-256 over the exact locked bytes and write `result.json.sha256`,
6. persist `RESULT_LOCKED` event and lock state,
7. optionally write the legacy `reveal.json` comparison artifact for reproduction tooling.

The exact JSON canonicalization strategy is a scaffold implementation detail, but it must be deterministic and tested.

## Legacy comparison artifact

`reveal.json` is retained as an internal reproduction artifact; it is not the viewer UI's source or
a manual product step. It may include:

- real target identity,
- external catalog source/reference metadata,
- known period/other selected ground-truth values,
- ExoSwarm locked values,
- absolute/relative error where meaningful,
- catalog confirmation status clearly attributed to the catalog.

Do not rewrite `result.json` after reveal.

## Blind-protocol tests

CI should prove:

- viewer catalog data is available without creating or mutating a run,
- agent modules do not import the reveal implementation,
- agent-safe API/SSE/context payloads do not contain recognizable identity/ground-truth fields,
- `result.json` hash is stable for unchanged content,
- reveal refers to the same locked run,
- resetting or refreshing does not leak viewer data into investigation state.
