---
name: engineer-agent-harness
description: 'Build or strengthen the control system around an AI agent: instructions, tools, permissions, model routing, state persistence, context assembly, loop policy, structured output validation, tracing, recovery, evaluation gates, and human approval boundaries. Use when the agent can reason but the surrounding runtime is unreliable, opaque, hard to resume, or too permissive. Success means the model operates inside explicit machine-enforced constraints and failures feed back into durable harness improvements.'
---

# Engineer Agent Harness

Treat the harness as the full contract around the model.

The model is one component. The harness determines what the model can see, what it can do, how actions are executed, what is persisted, when the run stops, and how correctness is measured.

## Inventory the harness

Identify the current implementation for:

- instructions,
- tools,
- tool schemas,
- permissions,
- model routing,
- loop control,
- durable state,
- context assembly,
- compaction,
- output validation,
- retries,
- approvals,
- tracing,
- evaluation,
- recovery.

Make missing surfaces explicit.

## Enforce boundaries mechanically

Prefer machine-enforced invariants over prose-only instructions.

Examples:

- schema validation,
- allowlisted tools,
- dependency-direction checks,
- state-machine guards,
- unit tests,
- structural tests,
- typed boundaries,
- permission checks,
- result-lock checks.

Use instructions to explain intent; use code to enforce invariants.

## Classify surfaces by authority

When the agent may modify its environment or optimize itself, distinguish:

- locked surfaces: evaluation rules, critical policies, immutable ground truth,
- editable surfaces: prompts, implementation under test, draft artifacts,
- append-only surfaces: traces, experiment logs, rejected attempts,
- human-controlled surfaces: deploy, merge, secrets, destructive actions.

Do not let an optimizing agent modify the evaluator that approves the same run.

## Keep repository and runtime legible

Put important operational knowledge in versioned, discoverable artifacts.

Prefer:

- schemas,
- tests,
- typed interfaces,
- runbooks,
- architecture notes,
- executable checks,
- machine-readable state.

Do not rely on undocumented conventions that live only in chat or team memory.

## Externalize durable state

Persist enough state that a new process or model context can resume without guessing.

Store:

- objective,
- current phase,
- completed actions,
- evidence,
- failures,
- pending work,
- budgets,
- lock or approval state,
- run identifiers.

Keep durable truth separate from temporary prompt text.

## Define permissions as code

For every tool or action, specify:

- read or write,
- side-effect level,
- required scopes,
- approval requirement,
- timeout,
- retry behavior,
- audit fields.

The model may request an action; the harness decides whether the request is authorized.

## Make context assembly a harness responsibility

Construct context from durable state and just-in-time retrieval rather than blindly replaying the whole conversation.

Support:

- tool-result trimming,
- external notes or files,
- compaction,
- context invalidation,
- scoped subagent contexts.

Keep provenance on retrieved facts that can affect decisions.

## Add robust output validation

Validate model outputs before they can change state.

Use:

- strict schemas where practical,
- enum and identifier validation,
- semantic precondition checks,
- maximum lengths,
- bounded repair or fallback.

Do not silently coerce an unsafe or unknown action into a valid one.

## Trace the full control path

Capture traces across:

- model calls,
- context versions,
- routing or escalation,
- tool calls,
- approvals,
- guardrails,
- state transitions,
- retries,
- terminal reason.

Prefer stable run and step identifiers.

## Design recovery before autonomy

Specify what happens after:

- model timeout,
- tool crash,
- process restart,
- invalid output,
- partial write,
- context compaction,
- external outage.

Use checkpoints and idempotent actions so recovery does not corrupt state.

## Create a harness improvement flywheel

Use real traces and failures to improve the harness.

Follow:

1. capture traces,
2. label or review important failures,
3. convert recurring failures into reproducible eval cases,
4. change one harness surface,
5. rerun the locked evals,
6. keep the change only if behavior improves without critical regressions.

Promote recurring prose rules into code or tests when possible.

## Review autonomy boundaries

Before increasing autonomy, verify:

- the action space is bounded,
- side effects are recoverable or approved,
- failures are observable,
- state is durable,
- stop conditions are external to the model,
- evaluation catches known bad behavior.

## Harness output

Document or implement:

- harness boundary,
- authority classes,
- permission model,
- persistence model,
- loop and retry policy,
- context policy,
- tracing schema,
- recovery strategy,
- evaluation gates,
- human approval points.
