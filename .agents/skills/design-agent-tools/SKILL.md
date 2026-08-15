---
name: design-agent-tools
description: Design, implement, or review tools intended for use by AI agents, including function calls, MCP tools, scientific actions, search or retrieval tools, and state-changing operations. Use when tool choice, names, schemas, return payloads, errors, permissions, or token efficiency affect agent reliability. Success means tools expose clear task-oriented capabilities, return compact actionable context, fail explicitly, and make unsafe or ambiguous use difficult.
---

# Design Agent Tools

Design tools for a non-deterministic caller.

A normal API can assume a developer understands its contract. An agent tool must make the intended action, valid parameters, failure modes, and returned evidence obvious from the schema and description.

## Choose the right tool boundary

Create a tool when it gives the agent a useful, repeatable capability.

Prefer task-oriented operations over exposing every low-level API primitive.

Avoid both extremes:

- one giant tool with many unrelated modes,
- dozens of near-duplicate micro-tools the model cannot distinguish.

Separate actions when they have meaningfully different:

- permissions,
- side effects,
- inputs,
- failure modes,
- semantic intent.

## Name tools for discrimination

Use names that describe the operation precisely.

Namespace related tools when useful.

Avoid ambiguous pairs whose descriptions differ only subtly.

A model should be able to choose the right tool from the name and short description without memorizing implementation details.

## Make schemas strict and ergonomic

Use:

- explicit required fields,
- narrow enums,
- bounded numeric ranges,
- descriptive parameter names,
- identifiers instead of free-form names when possible,
- separate fields instead of overloaded strings.

Validate again at the tool boundary even when structured output is enabled.

## Separate reads from writes

Do not hide a write behind a tool that sounds observational.

For state-changing or destructive operations:

- make the side effect explicit,
- return a preview or dry-run when useful,
- require approval or a commit step when risk warrants it,
- support idempotency keys when possible.

## Return decision-useful context

A tool result should help the agent choose the next action.

Return:

- status,
- key values,
- units,
- identifiers,
- warnings,
- relevant metadata,
- provenance,
- recovery information after failure.

Avoid returning huge raw payloads when a compact structured result plus an artifact reference is sufficient.

## Fail explicitly

Distinguish errors such as:

- invalid input,
- not found,
- permission denied,
- transient upstream failure,
- domain-level negative result,
- partial result,
- timeout.

Do not return `"success": false` with no explanation.

Do not turn a domain-level negative finding into an infrastructure error.

## Preserve determinism where the domain requires it

For scientific, financial, or other quantitative tools:

- compute numbers in deterministic code,
- include units and method,
- preserve provenance,
- return uncertainties or significance when available.

Do not ask the model to reconstruct measurements from raw arrays when code can compute them.

## Control tool-result size

Measure or inspect returned payloads.

Provide concise summaries plus references to full data when needed.

Use pagination, filtering, ranges, or field selection for large resources.

Do not flood the model context with information unrelated to the next decision.

## Add permission metadata to the runtime

The harness should know whether a tool is:

- read-only,
- state-changing,
- destructive,
- externally visible,
- credential-sensitive.

Tool prose alone is not a permission system.

## Evaluate tools with the agent

Test representative prompts and inspect whether the model:

- chooses the correct tool,
- supplies valid arguments,
- recovers from errors,
- avoids unnecessary calls,
- uses returned evidence correctly,
- distinguishes similar tools.

If repeated failures occur, redesign the tool contract before adding more prompt text.

## Tool completion criteria

A tool is ready when:

- its purpose is obvious,
- its schema rejects ambiguous calls,
- errors are typed and recoverable,
- side effects are explicit,
- outputs are compact and decision-useful,
- the harness can enforce permissions,
- agent-level evals show reliable selection and use.
