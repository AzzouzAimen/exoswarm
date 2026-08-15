---
name: engineer-agent-loop
description: Implement or review the runtime loop that repeatedly assembles context, calls a model, validates its decision, executes tools, persists results, updates state, and decides whether to continue, stop, retry, compact, or escalate. Use for loop control, branching, retries, budgets, termination, idempotency, resumability, and recovery. Success means the loop is explicit, bounded, inspectable, replayable enough to debug, and cannot silently spin or execute invalid actions.
---

# Engineer Agent Loop

Treat the agent loop as a state machine, not as an unbounded `while true` around an LLM call.

## Define the loop contract

Implement an explicit cycle:

1. load durable run state,
2. assemble task-relevant context,
3. call the selected model,
4. validate the model output,
5. classify the output as terminal, tool action, handoff, approval request, or invalid,
6. authorize the action,
7. execute the tool or transition,
8. normalize the result,
9. persist state and trace data,
10. decide whether to continue, retry, compact, escalate, pause, or stop.

Keep each transition observable.

## Use explicit states and terminal reasons

Model runtime states such as:

- initialized,
- deciding,
- waiting_for_tool,
- waiting_for_approval,
- recovering,
- escalating,
- completed,
- rejected,
- insufficient_evidence,
- failed,
- budget_exhausted.

Record a terminal reason, not only a boolean `done`.

## Bound every dimension

Configure limits for:

- total steps,
- wall-clock time,
- model calls,
- tool calls,
- repeated identical actions,
- retries per failure class,
- token or cost budget,
- escalation count.

Stop with a clear status when a budget is exhausted.

Never rely on the model to notice that it is looping.

## Validate before execution

Before executing a model-selected action:

- parse structured output,
- validate schema,
- check the action exists,
- validate parameters,
- check permissions,
- check current-state preconditions,
- check duplication or idempotency requirements.

Reject invalid actions deterministically.

## Distinguish retry classes

Do not use one generic retry policy.

Separate:

- transient infrastructure failure,
- model-format failure,
- tool-domain failure,
- invalid action,
- ambiguous result,
- authorization denial.

Use bounded exponential backoff only for genuinely transient infrastructure errors.

A deterministic domain failure should become evidence or a terminal state, not an endless retry.

## Make writes idempotent where possible

For actions with side effects:

- attach run and action identifiers,
- use idempotency keys when supported,
- persist intended action before execution when needed,
- detect repeated execution after restart,
- separate prepare and commit phases for high-impact operations.

A resumed loop must not accidentally repeat an irreversible action.

## Keep continuation logic explicit

Do not hide all stopping logic inside the system prompt.

Use deterministic checks for conditions such as:

- required baseline checks completed,
- maximum steps reached,
- result already locked,
- tool unavailable,
- approval denied,
- evidence threshold structurally satisfied,
- no valid next actions remain.

Let the model decide only the parts that genuinely require judgment.

## Support evidence-dependent branching

The next action should depend on current structured state.

For an investigative agent, different evidence should be able to produce different branches.

Add scenario tests that prove branch diversity.

If every branch is predetermined, implement a workflow instead of an agent loop.

## Engineer escalation

Escalate model capability based on explicit signals.

Examples:

- two competing actions remain close,
- evidence conflicts,
- the routine model emits repeated invalid decisions,
- final high-impact adjudication is required.

Pass the stronger model a compact structured case rather than the entire raw trajectory.

## Manage context on every iteration

Treat context assembly as part of the loop.

Prefer:

- durable state,
- recent relevant actions,
- compact evidence,
- just-in-time retrieval,
- summarized older results.

Avoid replaying every raw tool result indefinitely.

Invoke context compaction before quality degrades, not only after an API limit is hit.

## Persist before the next inference

After a tool result or state transition:

- normalize it,
- persist it,
- emit trace data,
- then construct the next model context.

This order makes crash recovery and replay much safer.

## Add recovery checkpoints

Make it possible to resume from a persisted state after:

- process restart,
- model timeout,
- frontend disconnect,
- external API failure.

A recovery path should know which actions completed and which remain pending.

## Test the loop adversarially

Include tests for:

- normal completion,
- invalid model output,
- unknown action,
- repeated identical action,
- model timeout,
- tool timeout,
- deterministic tool failure,
- approval pause and resume,
- process restart,
- maximum-step exit,
- budget exhaustion,
- stronger-model escalation,
- stale or mismatched run state.

## Completion criteria

The loop is ready when:

- transitions are explicit,
- budgets are enforced outside the model,
- invalid actions cannot execute,
- retries are bounded and typed,
- side effects are protected against duplication,
- state survives restart,
- traces explain branch decisions,
- terminal reasons are explicit.
