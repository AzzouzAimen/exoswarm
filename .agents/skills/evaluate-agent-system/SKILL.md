---
name: evaluate-agent-system
description: Build or improve evaluations for an agentic system using traces, scenario suites, deterministic checks, trajectory metrics, qualitative judges, cost and latency measures, and regression gates. Use when validating agent necessity, tool selection, branching, model routing, context changes, harness changes, or release readiness. Success means important agent behaviors can be reproduced and compared against locked criteria rather than judged from a few successful demos.
---

# Evaluate Agent System

Evaluate the complete agent-plus-harness behavior, not only the underlying model.

## Define outcomes and trajectory requirements

Separate:

- final-task success,
- process or trajectory quality,
- safety and policy compliance,
- cost and latency,
- reliability.

A correct final answer can still hide a broken loop that used the wrong data, repeated tools, bypassed a guardrail, or leaked ground truth.

## Build a scenario suite

Include representative categories such as:

- straightforward success,
- ambiguous evidence,
- conflicting evidence,
- negative or reject case,
- missing data,
- tool failure,
- model timeout,
- malformed model output,
- approval-required action,
- stale state,
- context pressure,
- recovery after restart.

For an adaptive agent, include scenarios expected to take different branches.

## Prefer deterministic assertions first

Use deterministic checks for facts that code can verify:

- correct tool selected from a bounded set,
- invalid tool rejected,
- required action executed,
- forbidden action not executed,
- ground truth stayed locked,
- maximum step count respected,
- unit or schema correct,
- state transition valid,
- output field present,
- exact or tolerant numerical range.

Use model-based judges only for genuinely qualitative dimensions.

## Capture traces

Store enough trace information to reconstruct:

- context or state version,
- model identity,
- model output,
- selected action,
- tool call,
- tool result status,
- branch,
- retry,
- escalation,
- terminal reason.

Avoid depending on hidden chain-of-thought.

## Measure trajectory health

Track metrics such as:

- task success rate,
- valid-action rate,
- unnecessary tool calls,
- repeated action rate,
- average steps,
- retry rate,
- escalation rate,
- tool failure recovery,
- unsupported-claim rate,
- context tokens,
- latency,
- cost.

For multi-agent systems also track handoff failures and coordination overhead.

## Compare against a simpler baseline

Evaluate:

- fixed deterministic workflow,
- single agent with tools,
- proposed multi-agent or escalated architecture.

Keep extra agency only if it improves a dimension that matters enough to justify added cost and failure surface.

## Lock evaluation criteria during optimization

When changing prompts, tools, routing, or harness behavior:

- version the eval set,
- prevent the same optimization run from silently weakening acceptance criteria,
- record failures as well as wins,
- compare per-dimension results.

Do not accept a change solely because an aggregate score improved if a critical dimension regressed.

## Use qualitative judges carefully

When a model judge is necessary:

- define a concrete rubric,
- prefer evidence-backed scoring,
- separate dimensions,
- calibrate against human examples,
- use pairwise comparison when it is more reliable than absolute scoring,
- inspect disagreement cases.

Do not use the same loose prompt both to generate behavior and to certify it.

## Turn traces into harness improvements

Use an improvement loop:

1. collect representative traces,
2. label failure modes,
3. convert recurring failures into stable eval cases,
4. propose one harness, tool, or context change,
5. rerun the same eval set,
6. keep or revert based on evidence.

Prefer fixing tools, state, validation, or context when failures are structural rather than adding longer prompts.

## Add release gates

Define minimum acceptable behavior for critical scenarios.

For a hackathon demo, include a small locked suite that must pass before presentation.

Require repeated successful runs for the exact demo path.

## Evaluation output

Produce:

- scenario list,
- expected outcomes,
- deterministic assertions,
- qualitative rubric if needed,
- trace schema,
- baseline comparison,
- metric summary,
- known failures,
- release threshold.
