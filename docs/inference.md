# Featherless Inference Layer

## Purpose

Featherless.ai is a named, visible integration rather than an incidental HTTP call. The inference
layer supplies bounded specialist briefings, Director ratification, Skeptic experiment selection,
and independent Critic review. Deterministic application code remains authoritative for routes,
tools, measurements, permissions, budgets, state transitions, result locking, and fallback
behavior.

The P0 provider/model plan is:

| Field | Value |
|---|---|
| Provider | Featherless.ai via an OpenAI-compatible client |
| Primary model | `deepseek-ai/DeepSeek-V4-Flash-0731` |
| Live roles | Observer, Signal, Transit Hunter, Director, Skeptic, and Critic |
| Model-visible data | compact evidence packet with opaque identity and evidence references |
| Raw light-curve samples sent to model | `0` |
| Additional providers / model routing | cut for the hackathon |

## Current implementation status

The live OpenAI-compatible Featherless adapter supports all six roles through a central prompt
registry. Prompts include distinct objectives, authority boundaries, bounded vocabularies, exact
identifier bindings, citations, examples, schema, version, example-set version, and locked SHA-256
template hashes. Each rendered request is separately hashed without persisting its body. The
controller performs strict schema and semantic validation, one repair attempt, bounded transient
retries, per-role limits, and an optional explicitly injected fallback. Optional specialist or
Director failure records `ROLE_SKIPPED_TO_SAFE_BASELINE`; Skeptic/Critic remain strict. Every attempt
emits a sanitized `inference.attempt` record; terminal runs derive and persist
`inference_summary.json`. A blank API key means unconfigured rather than attempting broken startup.

Thinking is configured per role as `off`, `on`, or `auto`; code defaults remain off until an exact
model is verified. DeepSeek V4 requests send `chat_template_kwargs={"thinking": false|true}` for
explicit modes and omit the template kwarg for `auto`. Requested and provider-preflight-confirmed
status are recorded separately. All calls request JSON mode with
`response_format={"type":"json_object"}`.

The promoted local demo profile enables thinking for the non-authoritative Director only. Thinking calls may
use up to 20,000 output tokens and 120 seconds because measured low-cap runs proved that reasoning
and final JSON compete for the completion allowance. Chat-mode role caps remain 500-1,200 tokens
with a 30-second role deadline. Runtime configuration records a 32,000-token input ceiling; live
telemetry has remained below 5,000 input tokens per call because contexts stay compact and
role-specific. The outer run remains bounded at 32 model calls, four transient retries, and 600
seconds. A provider `finish_reason=length` is classified as `OUTPUT_TRUNCATED`, not generic invalid
output.

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
role: observer | signal | transit_hunter | director | skeptic | critic
provider: featherless
model_identity: DeepSeek-V4-Flash-0731
attempt_kind: primary | repair
context_version: "..."
context_fingerprint: <sha256>
prompt_version: <version>
prompt_template_sha256: <sha256>
rendered_request_sha256: <sha256>
example_set_version: <version>
thinking_mode: off | on | auto
thinking_requested: false
thinking_confirmed: false
input_tokens: <integer|null>
output_tokens: <integer|null>
latency_ms: <integer>
status: SUCCESS | INVALID | OUTPUT_TRUNCATED | TIMEOUT | PROVIDER_ERROR
schema_valid: true
validation_error_code: null
finish_reason: stop | length | null
error_type: <safe schema error type and field|null>
fallback_used: false
```

Token fields may be null when the provider does not return usage. Null means `not_measured`, not
zero. A total or latency statistic is reported only when every included attempt supplied that
field; partial telemetry is not presented as a complete total. Do not store hidden chain-of-thought
or secrets.

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

Run the credential-gated canary against safe fixed contexts with:

```bash
uv run --project apps/api python scripts/run_featherless_canary.py --repeats 10 --output evals/featherless_canary.json
```

Before enabling thinking for the selected model, verify that its rendered format actually changes:

```bash
uv run --project apps/api python scripts/preflight_featherless_thinking.py
```

The preflight calls Featherless's model-specific debug chat-format endpoint for explicit off/on
modes and reports only hashes, token counts, template metadata, and a confirmation boolean. It does
not print the rendered prompts or persist the API key. Add a role to `thinking_confirmed_roles` only
after this exact-model check succeeds.

For a process-level rollback while a loaded `.env` enables roles, set those role keys explicitly to
`"off"`; an empty environment JSON object may be deep-merged with dotenv mappings by the settings
loader. Editing the `.env` values themselves back to `{}` and `[]` also disables the profile.

This produces 20 decisions across five evidence states. Accept the integration when:

- model identity and usage/latency metadata are captured where available,
- every response is validated before state mutation,
- invalid output follows the bounded repair/fallback policy,
- timeouts and provider errors become typed trace events,
- no secret, target identity, catalog truth, local path, or raw sample reaches the request,
- at least 80% of final decisions select the evidence-specific expected bounded action,
- the five states produce at least three distinct resolved action branches,
- a scripted/offline fallback keeps the failure path demonstrable without being mislabeled live.

Every generated report records its UTC timestamp, git commit, prompt versions, sanitized model and
runtime configuration (including context schema), worktree state, and configuration fingerprint.
The retained `agent-context-v4` chat control and Skeptic-thinking candidate each recorded 10/10
first-attempt schema- and semantic-valid decisions, 10/10 evidence-specific decision-quality
passes across four branches, zero repairs, and zero provider errors/timeouts. Thinking increased
latency without improving the saturated action metric, so Skeptic was not promoted. The canary
results are integration and bounded decision-policy evidence, not a scientific accuracy claim. The separate
`scripts/run_live_backend_gate.py` command exercises a cached scientific target through FastAPI,
SSE, live agents, locking, artifact listing, and hash-verified reveal. Live gates on TARGET-C11,
TARGET-P21, and the decisive-baseline TARGET-B42 all completed during the thinking rollout with
every branch-required role valid on its first attempt, no repairs/provider errors/fallbacks, and
zero raw light-curve samples in model context. The exact final Director-only profile completed C11,
P21, and B42 in 70.4, 62.9, and 31.2 seconds respectively. The P21 run also
exposed and regressed an over-broad context safety match: ordinary scientific prose such as "the
test may reveal a dip" remains allowed, while catalog/ground-truth reveal data stays blocked.
The frozen C11 demo path then passed three consecutive clean runs in 70.4, 71.5, and 64.6 seconds
with the same adaptive action and scientific disposition.

## Stabilized implementation decisions

- Thinking and final JSON share Featherless's `max_tokens` allowance. With the old 1,200/700 role
  caps, a current three-state reproduction yielded five length-truncated attempts and only 3/6
  first-attempt-valid decisions. A dedicated 20,000-token thinking cap removed truncation. Keep
  chat-mode caps small; do not lower the thinking cap without repeating this test.
- The context leak guard deliberately blocks catalog/ground-truth authority, recognizable target
  identity, local paths, and raw samples, but does not block the bare English verb `reveal`.
  Reintroducing that broad match crashes valid Skeptic-to-Critic handoff prose.
- Live reports distinguish `proposed_adaptive_actions`, `critic_verdicts`, and completed
  `adaptive_actions`. Do not derive executed actions from accepted model proposals: a proposal may
  be revised or vetoed before any tool runs.
- The six-role registry uses versioned v2 specialist/Director prompts, Skeptic v6, and Critic v5
  with locked hashes. The v2 contracts explicitly expose numeric-free advisory prose fields and
  the Director focus allowlist. Skeptic v6 adds explicit final-field length budgets after a
  reasoning run exceeded the existing schema maximum.
- The exact-model debug endpoint confirmed distinct on/off rendered prompts for
  `deepseek-ai/DeepSeek-V4-Flash-0731`. Promote thinking only for Director. Enabling it
  for both Skeptic and Critic produced 8/10 first-attempt-valid decisions, one repair, and one
  provider error. Skeptic-only thinking later passed 10/10 without repair but tied the chat-mode
  quality score at higher latency, so the branch-changing role stays off. Hidden reasoning content
  is neither requested in the schema nor persisted.
- The promoted advisory handoff is narrow: current validated Transit Hunter and Director briefing
  fields reach the Skeptic only. The Critic remains isolated. `agent.started` reports the visible
  advisory role names so this boundary is testable from the public event stream.
