# Deterministic Science Contracts

## Rule

Scientific measurements come from deterministic Python, cached/catalog data, or an explicitly defined statistical method. The LLM never reconstructs measurements from a plot, prose, or raw sample array.

## Implemented scientific pipeline

```text
cached TESS light curve
  -> quality filtering
  -> normalization / detrending
  -> BLS candidate search
  -> phase folding
  -> period / epoch / depth / duration / SNR
  -> odd/even comparison
  -> secondary-eclipse test
  -> P/2, P, 2P harmonic test
  -> basic contamination/neighbor context
```

Pixel/centroid localization remains unavailable because the committed targets do not include
cached target-pixel files. The implemented contamination fallback uses cached neighbor context when
available or the official SPOC `CROWDSAP` field as an explicitly labeled aggregate aperture screen.
It is never described as centroid or pixel localization.

## Tool-result contract

Every scientific tool result contains, as applicable:

```yaml
tool_name: odd_even
status: SUCCESS | NO_EVIDENCE | INDETERMINATE | PRECONDITION_FAILED | FAILED
run_id: <id>
action_id: <id>
target_id: TARGET-X17
measurements:
  # typed values with explicit units
uncertainty:
  # where the method supports it
diagnostics:
  # method-specific compact fields
warnings: []
method: <algorithm/library/version>
parameters: {}
provenance:
  input_artifact_refs: []
  code_version: <git sha if available>
  source_data_ref: <cached artifact>
suggested_alternatives: []
```

Never return a bare number when units/method/provenance matter.

## Failure semantics

Prefer scientifically useful typed failures. Example:

```yaml
status: PRECONDITION_FAILED
reason: odd_even requires at least 4 usable transits; found 3
suggested_alternatives:
  - secondary_eclipse
  - harmonic_test
```

A domain-level negative finding is evidence, not an infrastructure error.

## Required tool families

### Data and preprocessing

- load cached TESS light curve,
- reject the spatial diagnostic explicitly when no cached Target Pixel File is available,
- apply quality flags,
- normalize,
- detrend using one of the declared allowed configurations,
- record all material preprocessing parameters.

### Candidate search and measurement

- Box Least Squares,
- phase folding,
- candidate period,
- transit epoch,
- depth,
- duration,
- SNR,
- number of usable transits,
- approximate radius ratio only when method/assumptions support it.

### Vetting

- odd/even transit comparison,
- secondary-eclipse significance/evidence,
- P/2, P, 2P harmonic/alias analysis,
- basic contamination/neighbor context,
- explicit unavailable status for pixel/centroid localization without cached target-pixel data.

## Mandatory baseline

A viable candidate must not skip:

1. minimum signal-quality checks,
2. odd/even comparison,
3. secondary-eclipse test,
4. basic contamination screening.

Adaptive experiments are additional and evidence-driven.

## Numerical precision

BLS decimal output is not presented as physical certainty. The system distinguishes statistical
uncertainties supplied by an implemented method from grid/cadence or evaluation tolerances. It does
not imply uncertainty propagation for depth, duration, or radius ratio where none was calculated.

## Hypothesis updates

Tool measurements and higher-level interpretation are separate.

If weighted hypothesis updates are used, weights must come from declared deterministic/heuristic rules. Unless calibrated by a defined statistical model, numeric weights are not displayed as calibrated planet probabilities.

## Provenance guardrail

Any scientific number appearing in agent-generated UI prose must match a value already present in the Evidence Ledger or another deterministic artifact. Unsupported numeric claims should be rejected before display.

## Scientific claims

Passing these tests means only that the planetary interpretation survives the implemented vetting. It is not equivalent to professional confirmation.
