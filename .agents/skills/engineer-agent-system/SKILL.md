---
name: engineer-agent-system
description: 'Design or redesign an agentic application architecture: decide where models are actually needed, choose single-agent versus multi-agent structure, separate deterministic logic from model judgment, define state, routing, approvals, observability, and failure boundaries. Use for system-level agent architecture before or during implementation. Success means the agentic parts have explicit responsibilities and the surrounding deterministic system can validate, constrain, observe, and recover them. Use narrower loop, harness, context, tool, or evaluation skills for those details.'
---

# Engineer Agent System

Design the system around the model rather than treating the model as the system.

## Map the decision surface

For every major operation, classify it as one of:

- deterministic computation,
- deterministic policy,
- data retrieval,
- model judgment,
- human approval.

Keep deterministic behavior out of prompts when ordinary code can express it more reliably.

Use model judgment where the task genuinely benefits from interpretation, hypothesis formation, prioritization, planning, or choosing among valid actions under uncertainty.

## Start with the simplest topology

Prefer, in order:

1. deterministic workflow,
2. one tool-using agent,
3. one agent plus a reviewer or escalation step,
4. multiple specialized agents,
5. hierarchical or peer-to-peer multi-agent systems.

Add another agent only when it creates a concrete benefit such as:

- context isolation,
- distinct tool permissions,
- distinct policies or objectives,
- parallel work with independent inputs,
- independent adversarial review,
- model specialization.

Do not create multiple agents merely to assign personalities to sequential steps.

## Separate control, state, and execution

Design explicit boundaries:

- the model proposes or selects an action,
- the harness validates and authorizes it,
- deterministic tools execute it,
- structured state records the result,
- the next model call sees only the context required for the next decision.

Do not use conversation text as the sole source of application state.

Keep business state, scientific state, tool results, and agent messages distinguishable.

## Define durable structured state

Represent important state explicitly, including as applicable:

- run or investigation identifier,
- objective,
- current phase,
- hypotheses or candidate actions,
- evidence,
- completed actions,
- unresolved issues,
- budgets,
- permissions,
- model routing state,
- terminal status.

Persist enough state to resume, replay, or debug a run without reconstructing truth from prose.

## Define typed model contracts

Prefer structured model outputs for decisions that drive code.

Include only the fields the runtime needs.

Validate:

- action names,
- parameters,
- enums,
- identifiers,
- controller confidence when useful,
- required explanations or evidence references.

Reject malformed outputs instead of guessing what the model intended.

## Design model routing deliberately

Keep model and provider selection configurable.

Use a cheaper or faster model for routine bounded decisions.

Escalate to a stronger model only when an inspectable condition is met, such as:

- conflicting evidence,
- repeated invalid outputs,
- low controller confidence,
- high-impact final review,
- tool results outside the routine operating envelope.

Do not route by hidden demo flags.

## Put irreversible effects behind explicit authority

Classify tools and actions by risk.

For high-impact writes, destructive actions, credential use, external communication, or irreversible state changes:

- require deterministic policy checks,
- require human approval when appropriate,
- separate proposal from execution,
- log the authorization decision.

The model must not grant itself additional authority.

## Design failure as a first-class state

Specify behavior for:

- model timeout,
- model refusal,
- malformed structured output,
- tool timeout,
- tool failure,
- partial result,
- stale state,
- repeated action,
- exhausted budget,
- ambiguous evidence.

Do not collapse all failures into another model retry.

## Make the system observable

Trace at least:

- model call,
- model identity,
- context version or run identifier,
- selected action,
- tool invocation,
- tool result status,
- state transition,
- retry or escalation,
- terminal reason.

Prefer traces that let a developer answer "why did the system take this branch?" without reading hidden chain-of-thought.

## Test the architecture, not only components

Create scenario tests where the same runtime receives meaningfully different evidence and takes different valid paths.

Compare the agentic design against a simpler baseline.

If a fixed workflow achieves the same behavior with less cost and equal quality, remove unnecessary agency.

## Architecture output

Before implementation is considered ready, produce or update a concise architecture record containing:

- deterministic versus model responsibilities,
- topology,
- state schema,
- available actions,
- model routing,
- approvals,
- terminal states,
- trace points,
- major failure paths,
- evaluation plan.
