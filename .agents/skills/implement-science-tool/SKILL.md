---
name: implement-science-tool
description: Implement or modify deterministic ExoSwarm astronomy computation and scientific result contracts. Use for TESS retrieval/preprocessing, BLS, transit fitting, period/epoch/depth/duration/SNR, odd-even tests, secondary-eclipse tests, centroid or contamination analysis, and related numerical tools. Success means fixed inputs produce reproducible structured measurements with explicit units, failures, and provenance. Do not use for LLM policy, UI-only work, or validation-only tasks.
---

# Implement Science Tool

## Define the measurement

- Identify the scientific quantity or diagnostic to compute.
- Specify units, conventions, required inputs, assumptions, algorithm or library, and failure conditions.
- Preserve uncertainty, significance, or quality metrics when the method provides them.
- Surface ambiguous definitions instead of silently choosing one.

## Keep numerical authority deterministic

- Compute all scientific measurements in deterministic code, a catalog query, or an explicitly identified statistical model.
- Never ask an LLM to infer a numerical measurement from prose, plots, or raw samples.
- Reduce raw observations to structured evidence before passing results to an agent.
- Keep raw or canonical inputs available for reproducibility.

## Return structured results

- Use the repository's existing result schema when available.
- Include, as applicable:
  - tool name,
  - status,
  - measurements,
  - explicit units,
  - uncertainty or significance,
  - diagnostics,
  - warnings,
  - method,
  - parameters,
  - target or input identifier,
  - provenance.
- Return an explicit failure state with diagnostics when computation fails.
- Never substitute guessed values for missing or failed measurements.

## Preserve scientific boundaries

- Treat odd-even consistency, secondary-eclipse evidence, centroid stability, and contamination checks as evidence rather than proof of a planet.
- Separate measured results from higher-level interpretation.
- Avoid labeling a candidate as confirmed from basic TESS photometric vetting.
- Keep catalog ground truth inaccessible to the investigation path until the result-lock mechanism permits access.

## Handle preprocessing carefully

- Treat detrending, normalization, outlier rejection, masks, gaps, and sector selection as scientifically meaningful choices.
- Check whether a preprocessing change attenuates, reshapes, creates, or removes a transit signal.
- Record material preprocessing parameters in provenance.

## Add scientific tests

- Add or update tests that exercise the new numerical behavior.
- Use controlled synthetic data when the expected truth can be injected.
- Use a cached real TESS target when the method should work on real observations.
- Invoke the `validate-science` skill for dedicated regression and tolerance work.

## Verify completion

- Confirm deterministic behavior for fixed inputs and configuration.
- Confirm units and conventions are explicit.
- Confirm failures remain explicit.
- Confirm provenance is preserved.
- Confirm relevant scientific tests pass.
- Confirm no LLM path produces the measurement.
