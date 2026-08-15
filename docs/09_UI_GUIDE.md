# Mission-Control UI Guide

## Product feel

The interface should feel like autonomous scientific mission control, not a chatbot and not a generic card-heavy admin dashboard.

Scientific evidence should dominate the visual hierarchy; agent prose is concise and subordinate.

## Information hierarchy

Prioritize:

1. target and investigation status,
2. core scientific visualization,
3. current hypothesis and strongest alternative,
4. active agent/reviewer action,
5. scientific tool being executed,
6. evidence returned,
7. hypothesis/disposition update,
8. result-lock and catalog-reveal state.

## Central visualization

Use **one** React Three Fiber mission-control scene in the center. It may progressively represent the target star/candidate orbit as evidence accumulates.

Do not use R3F for scientific charts.

## Scientific visualization

Use Plotly for:

- raw light curve,
- cleaned light curve,
- BLS periodogram,
- phase-folded signal,
- odd/even diagnostic,
- secondary-eclipse diagnostic,
- centroid/pixel diagnostic,
- other scientific charts.

Static reproducible artifacts may be generated with Matplotlib by the backend.

## Main panels

### Target/status

Before reveal, show only an opaque identity, e.g.:

```text
UNKNOWN TARGET - TARGET-X17
```

Also show run ID, current phase, and lock state.

### Hypothesis board

Show:

- current leading hypothesis,
- strongest competing explanation,
- evidence supporting/weakening each,
- remaining uncertainty,
- current disposition.

Avoid fake probability percentages.

### Agent activity

Concise state only, for example:

```text
OBSERVER          complete
SIGNAL            complete
TRANSIT HUNTER    candidate detected
SKEPTIC           selecting discriminating experiment
CRITIC            reviewing proposal
DIRECTOR          waiting
```

Do not render long persona conversations or hidden chain-of-thought.

### Adaptive decision panel

This is a key differentiator. Display:

- strongest unresolved alternative,
- available adaptive experiments,
- Skeptic-selected experiment,
- concise reason,
- expected discriminating outcome,
- Critic verdict (APPROVE/REVISE/VETO),
- final executed tool.

### Evidence Ledger

Render compact evidence such as:

```text
+ periodicity detected                 P = <ledger value>
+ odd/even depths consistent           difference = <ledger significance>
+ no significant secondary event       <ledger result>
! nearby source in contamination area  <ledger context>
+ centroid consistent with target       offset = <ledger value>
? low-SNR secondary unconstrained       <explicit indeterminate state>
```

Every displayed number must have a backend evidence reference.

### Lock/reveal

The UI must visibly distinguish:

- `GROUND TRUTH LOCKED`
- `RESULT LOCKED`
- `NASA REVEAL AVAILABLE`
- `CATALOG REVEALED`

No frontend shortcut may bypass the backend gate.

## Loading/failure states

Display real states for:

- data unavailable,
- scientific-tool failure,
- model timeout,
- malformed agent decision/fallback,
- ambiguous evidence,
- rejected signal,
- insufficient evidence,
- budget exhausted.

Do not use fake progress or fabricated terminal output.

## Demo narrative target

The primary flow should be visually understandable without narration:

1. opaque target + locked ground truth,
2. deterministic search and measured transit-like signal,
3. competing hypotheses,
4. Skeptic adaptive decision,
5. Critic review,
6. deterministic diagnostic and ledger update,
7. negative-control target follows a different branch,
8. blindness proof,
9. result lock/hash,
10. NASA reveal,
11. evaluation/ablation proof,
12. deterministic forward prediction if implemented.
