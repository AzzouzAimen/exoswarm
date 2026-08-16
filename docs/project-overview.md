# Project Brief

## Product

ExoSwarm is **AI mission control for a falsifiable, auditable exoplanet investigation**.

It analyzes real TESS observations using established deterministic astronomy algorithms, tracks competing explanations for transit-like signals, and uses bounded AI agents to decide which scientific experiment should happen next. The system deliberately tries to falsify the planetary interpretation rather than simply narrating a positive detection.

## One-line claim

> ExoSwarm is an AI-orchestrated TESS investigation system that uses deterministic astronomy tools to test and falsify competing explanations for transit-like signals, adaptively chooses which scientific evidence to seek next, and automatically compares its independent result with an official viewer-only reference.

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

## Viewer-visible, agent-blind evaluation

The runtime agent sees an opaque ID such as `TARGET-X17`. The backend privately maps that ID to the
real TESS/TIC/TOI identity needed for deterministic data loading. A separate viewer endpoint may
show the human the official identity, parameters, and catalog status immediately. Those values stay
unavailable to agents for the entire run.

At completion:

1. preserve the independent disposition and deterministic measurements,
2. compare them with the already-visible viewer reference,
3. show a plain verdict: match, partial match, mismatch, or insufficient evidence,
4. keep evidence and technical audit detail expandable rather than blocking the result.

The catalog is an evaluator, not an input to the investigation.

## Users and transferable value

ExoSwarm is built for engineers, researchers, and technical reviewers evaluating whether an AI-led
workflow is bounded, observable, reproducible, and useful. It is a research prototype for
photometric vetting, not a substitute for professional exoplanet confirmation.

The architecture demonstrates a reusable pattern for evidence-heavy domains: a model selects a
bounded deterministic analysis under budget; typed tools perform it; append-only evidence and trace
records make the trajectory auditable; and reference answers remain isolated from decision-making.

## What the prototype demonstrates

- five cached public TESS cases spanning clean, weak, rejected, and inconclusive outcomes,
- different valid paths when the deterministic evidence differs,
- visible Skeptic experiment selection and independent Critic review,
- an official viewer reference that remains absent from every agent context,
- automatic result comparison tied to the locked result hash,
- CI coverage of the blind protocol, persistence, recovery, API, science, and frontend,
- a complete offline reproduction path without model credentials or astronomy-network access,
- Featherless telemetry derived from recorded provider metadata rather than estimates.
