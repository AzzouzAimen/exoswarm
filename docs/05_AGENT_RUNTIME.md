# Agent Runtime Contract

## State, not conversation

The runtime is a state machine around the model. Important truth lives in `InvestigationState`, the Evidence Ledger, artifacts, and explicit transition records. The chat transcript is not the database.

## Core state

`InvestigationState` should contain, as applicable:

- `run_id`
- `opaque_target_id`
- backend-only target reference outside agent-visible serialization
- current phase/status
- observation/data-quality summary
- preprocessing runs
- candidate signals
- active hypotheses
- strongest unresolved alternative
- evidence references
- completed tests
- available tests
- unresolved questions
- step count
- model-call/tool-call counts
- experiment budget units remaining
- per-experiment cost for available adaptive actions
- inference/cost budget if tracked
- lock state
- terminal reason
- provenance/context version

## Runtime statuses

Recommended explicit states:

- `INITIALIZED`
- `PREPARING`
- `SEARCHING`
- `VETTING_MANDATORY`
- `SELECTING_ADAPTIVE_EXPERIMENT`
- `WAITING_FOR_CRITIC`
- `RUNNING_TOOL`
- `UPDATING_EVIDENCE`
- `READY_TO_LOCK`
- `RESULT_LOCKED`
- `REVEALED`
- `INSUFFICIENT_EVIDENCE`
- `REJECTED`
- `FAILED`
- `BUDGET_EXHAUSTED`

The exact names are a scaffold convention, but every terminal state must include a terminal reason.

## Specialist objectives

### Scientific Director / investigation controller

Owns control flow as deterministic application code. "Scientific Director" is a UI/product label,
not a distinct P0 inference role. The controller routes bounded model decisions, enforces mandatory
diagnostics and budgets, and owns terminal transitions and the catalog gate.

### Observer Agent

Receives compact observation/data-quality diagnostics. It may classify issues or select from allowed preparation choices. It never receives raw FITS arrays in prompt context.

### Signal Agent

Chooses among a small allowed set of preprocessing strategies when the data state justifies a choice. Deterministic Python performs the transformation and records the parameters.

### Transit Hunter

Requests deterministic candidate-search and candidate-measurement tools. It consumes structured candidate results; it does not estimate measurements by visual inspection.

### Skeptic Agent

Objective: identify the strongest plausible non-planetary explanation still compatible with evidence and select the available experiment expected to best discriminate it from the planetary hypothesis.

A `SkepticDecision` should contain fields like:

```yaml
hypothesis_under_test: background_contamination
requested_experiment: centroid_localization
parameters:
  candidate_period_ref: evidence://candidate/period
reason_code: NEARBY_SOURCE_IN_APERTURE
expected_discriminating_result: >-
  Determine whether transit-associated centroid motion is consistent with the target position.
predicted_outcomes:
  TARGET_CONSISTENT: planetary interpretation remains viable
  OFFSET_DETECTED: contamination explanation strengthened
expected_information_value: medium
stop_if: spatial evidence resolves the dominant remaining alternative
priority: high
budget_units_remaining: 4
cost_of_selected_experiment: 2
why_cost_is_justified: >-
  The spatial test directly targets the strongest unresolved contamination explanation.
concise_reason: Nearby-source evidence makes spatial localization the most discriminating unused test.
```

The three cost fields are required by the runtime schema and are validated against durable state
and the deterministic registry. The controller is authoritative for the actual remaining budget
and action cost; stale or mismatched model values are rejected before a decision can prepare an
action.

`expected_information_value` is a decision-quality signal, not a calibrated planet probability.

### Critic Agent

Objective: determine whether the proposed adaptive experiment is genuinely discriminating given the evidence already collected.

Output:

- `APPROVE`
- `REVISE` with at most one alternative/revision
- `VETO` with at most one alternative

Allow at most one revision round before deterministic runtime policy resolves the next action.

## Loop limits

Bound at least:

- total steps,
- model calls,
- tool calls,
- adaptive experiments,
- repeated identical actions,
- retries by failure class,
- wall-clock time where practical,
- escalation count if escalation is later enabled.

The model does not decide whether its own budget exists.

For the shippable path, use a default adaptive budget of four units. Suggested initial registry
costs are: alternate detrending `1`, harmonic test `1`, secondary deep search `1`, alternate
aperture `1`, centroid localization `2`, and stop `0`. Only registered actions may appear; do not
add placeholder actions solely to fill this list.

## Validation before execution

Before executing a model-selected action:

1. parse structured output,
2. validate schema,
3. verify action exists in the registry,
4. validate parameters/ranges,
5. check permission level,
6. check current-state preconditions,
7. check duplicate/idempotency rules,
8. check lock/ground-truth restrictions.

Reject invalid actions deterministically.

## Context packet

Do not send raw observation arrays. A useful packet contains:

```text
TARGET
TARGET-X17

CURRENT CANDIDATE
period = <value + unit + uncertainty/tolerance from ledger>
epoch = <...>
depth = <...>
duration = <...>
SNR = <...>
n_transits = <...>

COMPLETED TESTS
<test statuses and evidence refs>

NEW EVIDENCE
<compact result summaries with provenance refs>

OPEN HYPOTHESES
<ranked/active alternatives without fake probability>

AVAILABLE EXPERIMENTS
<validated allowed actions>
```

Each specialist receives only its objective, permitted actions, relevant compact state, a few canonical examples, and strict output schema.

## Trace

Persist enough to debug without hidden chain-of-thought:

- run/step IDs,
- context version/size,
- model identity,
- structured model output,
- action chosen,
- Critic verdict,
- tool invocation/result status,
- evidence references,
- state transition,
- retry/escalation/fallback,
- token/cost metadata if available,
- terminal reason.

Run completion must aggregate the recorded inference metadata into the summary defined in
`docs/inference.md` and make it available to the API/UI. Missing provider usage remains explicitly
`not_measured`; it must never be replaced by a guessed token count.
