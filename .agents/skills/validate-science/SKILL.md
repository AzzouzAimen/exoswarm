---
name: validate-science
description: Validate ExoSwarm numerical astronomy behavior against controlled fixtures, cached real TESS observations, expected ranges, units, and regression tolerances. Use after adding or changing scientific computation or when checking whether a scientific result is trustworthy. Success means positive, negative, unit/convention, and relevant real-data cases are reproducible without live-network dependence. Do not use for ordinary UI tests or non-scientific application logic.
---

# Validate Science

## State the scientific claim

- Write the exact behavior to validate.
- Prefer measurable claims such as:
  - recover an injected period within tolerance,
  - recover transit depth within tolerance,
  - detect an injected odd-even mismatch,
  - return low secondary-eclipse significance for a clean control,
  - detect an injected centroid shift.
- Avoid assertions such as "looks reasonable."

## Build a validation ladder

- Use a controlled synthetic or deterministic fixture when possible.
- Use a cached real TESS target when the feature is intended for real observations.
- Add an integration regression when unit or schema corruption could occur across layers.
- Avoid requiring live APIs for the regression suite.

## Set tolerances before evaluating the new result

- Record the expected value or range.
- Record the tolerance.
- Record why the tolerance is technically or scientifically reasonable.
- Change a tolerance only when the method or requirement genuinely changes.
- Do not relax a tolerance merely to make a failing implementation pass.

## Test negative and indeterminate cases

- Include relevant cases such as:
  - no signal,
  - insufficient transits,
  - low SNR,
  - missing sector,
  - NaN or corrupted samples,
  - secondary eclipse below threshold,
  - centroid shift below significance,
  - tool failure.
- Require the tool to preserve "no evidence" or "cannot determine" rather than converting absence into positive evidence.

## Verify units and conventions

- Test fragile conversions and conventions explicitly, including as applicable:
  - days versus hours,
  - fraction versus percent versus ppm,
  - time-system offsets,
  - epoch definitions,
  - radius ratio versus transit depth,
  - sign and sigma conventions.
- Fail loudly on unit ambiguity.

## Check preprocessing sensitivity when relevant

- Compare recovery under at least one reasonable alternative preprocessing configuration when preprocessing changed.
- Flag a signal that disappears under a small reasonable preprocessing change instead of treating it as robust.

## Protect blinded evaluation

- Keep expected catalog truth available only to validation code or fixtures.
- Prevent production or demo investigation code from reading hidden parameters before result lock.
- Test that early ground-truth access is denied.

## Record regressions

- Store stable expected values or ranges for important demo targets.
- Prefer tolerant range assertions over brittle exact floating-point equality.
- Include enough diagnostic output to identify why a regression failed.

## Report validation

- State the fixture or target used.
- State the expected result and tolerance.
- State the observed result.
- State which positive, negative, and unit checks passed.
- State any scientifically unresolved limitation.
