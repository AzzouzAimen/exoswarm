# Mission Control UI

## Product feel

The interface is designed as autonomous scientific mission control rather than a chatbot or a
generic card-heavy admin dashboard.

Scientific evidence dominates the visual hierarchy; agent prose is concise and subordinate.

## Information hierarchy

Prioritize:

1. target and investigation status,
2. core scientific visualization,
3. current hypothesis and strongest alternative,
4. active agent/reviewer action,
5. scientific tool being executed,
6. evidence returned,
7. hypothesis/disposition update,
8. clear independent-result versus official-reference comparison.

## Central visualization

One React Three Fiber mission-control scene progressively represents the target star and candidate
orbit as evidence accumulates.

Do not use R3F for scientific charts.

## Scientific visualization

Plotly renders:

- raw light curve,
- cleaned light curve,
- BLS periodogram,
- phase-folded signal,
- odd/even diagnostic,
- secondary-eclipse diagnostic,
- other scientific charts.

Static reproducible artifacts may be generated with Matplotlib by the backend.

## Main panels

### Target/status

Show both identities with an explicit trust boundary:

```text
VIEWER: WASP-4 b · confirmed planet
AGENTS: TARGET-C11 only
```

Also show run ID and current phase. The viewer reference belongs in the top-right from selection
through completion; its tooltip must explain that agents receive only the opaque ID.

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
- final executed tool,
- selected experiment cost and remaining budget units.

### Inference summary

Show a compact Featherless card near the agent activity or final run summary with model identity,
call count, input/output tokens, schema-valid rate, repair count/rate, fallback count/rate, and
latency. It must be derived from trace metadata. During scripted or unconfigured runs, label the
provider and usage metrics as unavailable/scripted instead of showing illustrative values. Include
the invariant `raw light-curve samples sent to model: 0` only when the context guardrail remains
enforced.

### Evidence Ledger

Render compact evidence such as:

```text
+ periodicity detected                 P = <ledger value>
+ odd/even depths consistent           difference = <ledger significance>
+ no significant secondary event       <ledger result>
! nearby source in contamination area  <ledger context>
! aggregate contamination capacity      CROWDSAP = <ledger value>
? low-SNR secondary unconstrained       <explicit indeterminate state>
```

Every displayed number must have a backend evidence reference.

### Automatic result comparison

At completion, open the comparison directly. Lead with one verdict understandable without astronomy
knowledge:

- `MATCH`
- `PARTIAL MATCH`
- `DID NOT MATCH`
- `NOT ENOUGH EVIDENCE`

Place the agent interpretation and official catalog interpretation side by side. Put numerical rows,
completed checks, provenance, and audit metadata behind expandable details. Do not require Commit,
Reveal, or Compare clicks; those steps delay the demo's payoff without improving agent blindness.

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

## Representative demonstration flow

The primary flow should be visually understandable without narration:

1. viewer sees the official target while agents receive only an opaque ID,
2. deterministic search and measured transit-like signal,
3. competing hypotheses,
4. Skeptic adaptive decision,
5. Critic review,
6. deterministic diagnostic and ledger update,
7. negative-control target follows a different branch,
8. architecture + measured Featherless summary,
9. blindness proof,
10. automatic plain-language result/catalog comparison,
11. optional details and `make reproduce` audit proof.
