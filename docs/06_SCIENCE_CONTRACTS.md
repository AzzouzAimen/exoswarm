# Deterministic Science Contracts

## Rule

Scientific measurements come from deterministic Python, cached/catalog data, or an explicitly defined statistical method. The LLM never reconstructs measurements from a plot, prose, or raw sample array.

## Final-stretch P0 scientific pipeline

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

Pixel/centroid localization is a high-value P1 differentiator, not a P0 ship blocker. After the
vertical path is stable, implement or finish it against a real cached TPF and keep it when the
deterministic acceptance test passes. Otherwise prefer an honestly labeled alternate-aperture
comparison plus neighbor context. Never rename that fallback as centroid or pixel localization.

## Tool-result contract

Every scientific tool result should contain, as applicable:

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
- load cached Target Pixel File only for an accepted conditional spatial diagnostic,
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
- optional genuine pixel/centroid localization diagnostic after its go/no-go gate.

## Mandatory baseline

A viable candidate must not skip:

1. minimum signal-quality checks,
2. odd/even comparison,
3. secondary-eclipse test,
4. basic contamination screening.

Adaptive experiments are additional and evidence-driven.

## Numerical precision

Do not present BLS decimal output as if it were physical certainty. For the final stretch,
prioritize a defensible period uncertainty or declared comparison tolerance because period is used
in the catalog reveal. Preserve already verified deterministic uncertainty fields, but do not add
new depth, duration, radius-ratio, or general uncertainty propagation before the core path ships.

## Hypothesis updates

Tool measurements and higher-level interpretation are separate.

If weighted hypothesis updates are used, weights must come from declared deterministic/heuristic rules. Unless calibrated by a defined statistical model, numeric weights are not displayed as calibrated planet probabilities.

## Provenance guardrail

Any scientific number appearing in agent-generated UI prose must match a value already present in the Evidence Ledger or another deterministic artifact. Unsupported numeric claims should be rejected before display.

## Scientific claims

Passing these tests means only that the planetary interpretation survives the implemented vetting. It is not equivalent to professional confirmation.
