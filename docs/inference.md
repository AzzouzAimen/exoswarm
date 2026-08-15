# Featherless Inference Layer

## Purpose

Featherless.ai is a named, visible integration rather than an incidental HTTP call. The inference
layer supplies bounded judgment for Skeptic experiment selection and Critic review. Deterministic
application code remains authoritative for tools, measurements, permissions, budgets, state
transitions, result locking, and fallback behavior.

The P0 provider/model plan is:

| Field | Value |
|---|---|
| Provider | Featherless.ai via an OpenAI-compatible client |
| Primary model | `DeepSeek-V4-Flash-0731` |
| Live roles | Skeptic and Critic |
| Model-visible data | compact evidence packet with opaque identity and evidence references |
| Raw light-curve samples sent to model | `0` |
| Additional providers / model routing | cut for the hackathon |

## Current implementation status

The repository currently has an `InferenceClient` boundary, a deterministic
`ScriptedInferenceClient`, strict decision schemas, bounded transient retry, and traceable decisions.
The live Featherless adapter, repair call, provider token/latency capture, deterministic fallback,
and run-level summary are not yet implemented. Until they exist, provider metrics are
`not_measured`; do not publish estimates or illustrative numbers as results.

## Call policy

The controller may call the model only with:

- an explicit role and objective,
- an agent-safe context packet assembled from durable state and Evidence Ledger entries,
- an allowlist of currently valid actions,
- authoritative remaining budget and per-action costs,
- a strict output schema,
- stable run, step, and call identifiers.

The model requests an action; it does not execute tools or authorize itself. No raw flux/time arrays,
FITS/TPF contents, local paths, recognizable target identity, catalog truth, or reveal capability may
enter the request.

## Structured-output failure policy

For each decision:

1. make one normal structured-output attempt,
2. validate JSON/schema plus role, identifiers, action, parameters, permissions, preconditions, and
   budget,
3. if the failure is repairable, make at most one repair attempt using the validation error and the
   same safe context,
4. if repair fails or the provider is unavailable, execute a declared deterministic fallback or
   terminate with an explicit typed failure,
5. append trace records for every attempt, repair, fallback, error, and state transition.

Never silently coerce an unknown or unauthorized action into a valid one. A fallback must be labeled
`AGENT_FALLBACK` in the trace and UI; it must not masquerade as model success.

## Per-call trace contract

Record, where supplied by the provider:

```yaml
call_id: call_...
run_id: run_...
step_id: step_...
role: skeptic | critic
provider: featherless
model_identity: DeepSeek-V4-Flash-0731
attempt_kind: primary | repair
context_version: "..."
input_tokens: <integer|null>
output_tokens: <integer|null>
latency_ms: <integer>
status: SUCCESS | INVALID | TIMEOUT | PROVIDER_ERROR
schema_valid: true
validation_error_code: null
fallback_used: false
```

Token fields may be null when the provider does not return usage. Null means `not_measured`, not
zero. Do not store hidden chain-of-thought or secrets.

## Run summary contract

At terminal state, derive a summary from the call trace and persist/expose it with the run:

```text
INFERENCE LAYER — Featherless.ai
Model:                       <recorded identity>
Agent calls:                 <count>
Input / output tokens:       <recorded totals or not_measured>
Median / max input tokens:   <recorded values or not_measured>
Median latency:              <recorded value or not_measured>
First-attempt schema-valid:  <count>/<count> (<rate>)
Repairs:                     <count>/<eligible calls> (<rate>)
Fallbacks:                   <count>/<decisions> (<rate>)
Provider errors/timeouts:    <count>
Raw light-curve samples sent to model: 0
```

Rates use explicit denominators and return `not_applicable` when the denominator is zero. The
summary must be computed from trace records, never copied from configuration or prose. Print one
concise summary at run completion and expose the same data to the API/UI so the video can show it.

## Provider canary and acceptance

Before enabling the provider in the judged path, run the real Skeptic schema repeatedly (target: 20
calls if time/provider budget allows) against safe fixed contexts. Accept the integration when:

- model identity and usage/latency metadata are captured where available,
- every response is validated before state mutation,
- invalid output follows the bounded repair/fallback policy,
- timeouts and provider errors become typed trace events,
- no secret, target identity, catalog truth, local path, or raw sample reaches the request,
- a scripted/offline fallback keeps the failure path demonstrable without being mislabeled live.

The canary results are integration evidence, not a scientific accuracy claim.
