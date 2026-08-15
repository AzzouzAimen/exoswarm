# Project Brief

## Product

ExoSwarm is **AI mission control for a falsifiable, auditable exoplanet investigation**.

It analyzes real TESS observations using established deterministic astronomy algorithms, tracks competing explanations for transit-like signals, and uses bounded AI agents to decide which scientific experiment should happen next. The system deliberately tries to falsify the planetary interpretation rather than simply narrating a positive detection.

## One-line claim

> ExoSwarm is an AI-orchestrated TESS investigation system that uses deterministic astronomy tools to test and falsify competing explanations for transit-like signals, adaptively chooses which scientific evidence to seek next, and locks its measurements before comparing them with NASA ground truth.

## Key distinction

```text
Agents decide what scientific operation should happen next.
Deterministic scientific software performs the operation.
```

The agent may interpret structured evidence and select among valid experiments. It may not manufacture periods, depths, durations, centroids, significances, or other numerical measurements.

## Why the agent layer is legitimate

The project is not a fixed Python pipeline with an LLM narrator. Evidence must be able to change the next experiment. Examples:

- suspicious odd/even difference -> test a possible half-period alias / 2P interpretation,
- nearby source in the aperture -> prioritize spatial localization/centroid evidence,
- low-SNR candidate with strong variability -> test an allowed alternative preprocessing strategy,
- significant secondary-like event -> strengthen eclipsing-binary alternatives and inspect primary/secondary/harmonic evidence,
- strong clean evidence with mandatory tests complete -> stop instead of running every tool.

If every target runs the same fixed sequence, the adaptive agent layer has failed its purpose.

## Competing hypotheses

At minimum, represent explicit alternatives such as:

- planetary transit,
- eclipsing binary,
- background/contaminating eclipsing source,
- stellar variability,
- instrumental/systematic artifact,
- period/harmonic alias.

The final disposition is an evidence-based state, not a model confidence score.

## Suitable disposition language

Use states such as:

- `NO_CREDIBLE_PERIODIC_SIGNAL`
- `TRANSIT_LIKE_SIGNAL`
- `PLANETARY_INTERPRETATION_WEAK`
- `PLANETARY_INTERPRETATION_PLAUSIBLE`
- `PLANETARY_INTERPRETATION_SURVIVES_IMPLEMENTED_VETTING`
- `PLANETARY_INTERPRETATION_REJECTED`
- `INCONCLUSIVE_ADDITIONAL_DATA_REQUIRED`

The exact enum may be refined, but the UI and reports must never imply that ExoSwarm photometric vetting itself confirms a planet.

## Blind evaluation idea

The runtime agent sees an opaque ID such as `TARGET-X17`. The backend privately maps that ID to the real TESS/TIC/TOI identity needed for deterministic data loading. Known catalog parameters and confirmation status stay unavailable to the agent until the result is locked.

After lock:

1. write `result.json`,
2. compute and persist `result.json.sha256`,
3. unlock the ground-truth service,
4. create `reveal.json`,
5. compare the locked measurement with the external catalog.

The catalog is an evaluator, not an input to the investigation.

## Target user and transferable value

The immediate users are hackathon judges and engineers evaluating whether an agentic workflow is
bounded, observable, reproducible, and useful—not professional astronomers validating every edge
case. ExoSwarm demonstrates a reusable software pattern for any evidence-heavy domain: the model
selects a bounded deterministic analysis under budget; typed tools perform it; an append-only ledger
and trace make the trajectory auditable; and hidden reference answers remain gated until commitment.

This framing does not relax scientific honesty. It explains why architecture legibility, failure
handling, context isolation, measured inference behavior, and blind-lock integrity are the product's
primary value.

## Minimum proof for the hackathon

A credible P0 demonstration must show:

- one planet-like/confirmed-planet holdout case,
- one false-positive/eclipsing-binary case,
- visibly different evidence-driven agent paths,
- a visible adaptive experiment decision,
- result lock before reveal,
- CI/test evidence that the blind protocol cannot be bypassed,
- reproducible run artifacts,
- a visible Featherless inference summary based on recorded—not estimated—metrics,
- a clean setup/reproduction path and honest limitations.
