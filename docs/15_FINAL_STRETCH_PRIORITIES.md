# Final-Stretch Hackathon Priorities

> Current task override (2026-08-15): the backend-only six-role implementation authorized in
> `TEMP_MULTI_AGENT_FLASHINESS_PLAN.md` supersedes the older two-role/no-model-Director cut below.
> Deterministic numerical authority, blinding, bounded actions, and result-neutral rollout remain
> mandatory. Frontend work is still deferred for this task.

This document is the delivery override for the remaining hackathon work. Roughly 70% of the event
time remains, so it ranks work by scoring value and dependency order rather than assuming an
emergency cut-down. Preserve high-value differentiators once the reliable core gates are green.
Coding agents should consult it before selecting their next task.

## Optimization target

Optimize for a working and legible software system: bounded inference, deterministic tools,
structured failures, durable traces, blind result locking, cached reproducibility, clear setup, and
a concise demonstration. Do not optimize for specialist scientific breadth or edge-case precision
that is invisible in the judged path.

The target audience is software, cloud, data, and security engineers. Explain the transferable
pattern: an LLM allocates a limited budget among bounded deterministic analyses; machine-enforced
contracts constrain it; an append-only ledger and trace make the result auditable; and a blind lock
prevents hidden answers from influencing the committed result.

## Scoring lens

Use the published rubric as the work-allocation check. It is not permission to fake or weaken the
science; it is a reason to invest where this software-focused panel can directly evaluate the work:

| Category | Scored criterion | Evidence the project must make judgeable |
|---|---|---|
| Technical Execution & Code Architecture (20) | Code Structure & Quality (10) | modular domain/science/investigation/agent/API/security boundaries; typed state and outputs; original control logic; explicit errors, budgets, recovery, persistence, and tests |
| Technical Execution & Code Architecture (20) | API & Compute Integration (10) | real Featherless calls; structured-output validation; bounded repair/fallback; Skeptic-to-Critic pipeline; deterministic tool execution; measured model, token, latency, and error telemetry |
| Originality & Problem Solving (10) | Innovation & Approach (10) | budgeted evidence selection, independent Critic review, append-only evidence, opaque targets, and cryptographic blind lock as one coherent trustworthy-agent pattern |
| Utility, Functionality & Real-World Impact (10) | Functional Execution (10) | a working end-to-end prototype for researchers and engineers, with distinct real-data paths, explicit inconclusive outcomes, recovery, and reproducible cached operation |
| Pitch, Demo & Documentation (20) | 3-Minute Video Demo (10) | concise live execution plus a legible architecture explanation; show evidence changing the path, agent/tool boundaries, Critic verdict, telemetry, and lock/reveal payoff |
| Pitch, Demo & Documentation (20) | Documentation & Setup (10) | complete README quick start, architecture diagram, environment/provider setup, reproduction and eval commands, limitations, data attribution, upstream references, and citations |

Do not let optional scientific breadth consume the work needed to make an architecture or demo
claim unjudgeable. Once all four areas have credible evidence, use remaining time on the ranked P1
differentiators below.

## Keep without weakening

- opaque target identity and backend-only mapping,
- canonical result serialization, SHA-256 lock, and catalog gate,
- blind-protocol import/payload tests,
- append-only Evidence Ledger with typed provenance,
- deterministic authority for every scientific measurement,
- Skeptic structured selection and Critic `APPROVE` / `REVISE` / `VETO`, with one revision maximum,
- allowlisted tools, strict schemas, permissions, preconditions, budgets, retries, and terminal
  reasons,
- attempt -> schema validation -> bounded repair -> fallback, all traced,
- no raw light-curve samples in model context,
- no fake confidence percentages or unsupported scientific claims,
- two visibly different demo trajectories and a locked result before reveal.

## P0 delivery order

1. Finish the harness path already in progress: real cached source resolution, mandatory tools,
   durable recovery, and explicit failure states.
2. Add the single-provider Featherless path for Skeptic and Critic. Keep the Scientific Director as
   deterministic controller code.
3. Record and surface inference identity, calls, tokens, latency, schema-valid, repair, and fallback
   metrics as defined in `docs/inference.md`.
4. Complete one planet-like path and one eclipsing-binary-like path end to end through evidence,
   disposition, lock, hash, and reveal. Make the paths visibly different.
5. Lock a compact third inconclusive case for the minimum evaluation gate. Add a fourth spatial case
   only through the P1 rule below.
6. Wire the mission-control UI to real state and events, including adaptive action cost, remaining
   budget, Critic verdict, failures, inference summary, lock, and reveal.
7. Make cached `make reproduce` regenerate the complete locked result and verify its hash.
8. Exercise clean setup, harden the judged path, freeze features, then finish README, write-up,
   captions/video, limitations, citations, and public-link checks.

## High-value P1 after the core gates

Do not stop at a bare minimum while time remains. In this order, pursue:

1. polished mission-control storytelling for evidence-driven branch differences, Critic review,
   cost allocation, failures, inference statistics, and blind lock/reveal,
2. judge-legible architecture and documentation: concise diagrams, setup/reproduction, failure
   behavior, security boundaries, live inference telemetry, and honest limitations,
3. harden the exact online demo path, cached fallback, reset behavior, and provider-failure story,
4. one additional Observer or Signal model role only when its isolated context and bounded output
   cause a real, testable decision difference,
5. a time-boxed cached-TPF pixel/centroid diagnostic only if it materially improves the visible
   software/agent story and passes a deterministic acceptance case,
6. a fourth contamination/spatial end-to-end case when it validates an accepted centroid path,
7. deterministic forward-transit prediction if the underlying period/epoch contract is already
   stable and the result is clearly labeled.

These are gated, not discarded. Optional science work must not block the primary planet-like/EB
paths, live Featherless handling, agent observability, blinding, reproducibility, documentation, or
the judged demo.

## Explicit low-return cuts

Do not implement for the hackathon submission:

- agent-vs-fixed-policy ablation,
- `pass^3` or other repeated stochastic consistency scoring,
- an end-to-end eval suite larger than the three-case minimum plus one gated spatial case,
- a separate LLM Scientific Director,
- multi-model routing or another model provider,
- new trapezoid/transit fitting,
- new depth, duration, radius-ratio, or broad uncertainty propagation,
- broad target coverage, multi-sector stitching, or ceremonial extra agents,
- speculative scientific or UI features after the primary path works.

Existing deterministic values that are already implemented, tested, and truthfully labeled do not
need to be removed merely because further work in that area is cut.

## Centroid go/no-go

Centroid localization is not a P0 blocker and is lower priority than architecture clarity, agent
observability, documentation, and demo reliability. Attempt it only when those gates are already
strong and the feature adds something a software-focused judge can understand in the demo. Give it
a focused, time-boxed implementation/acceptance window using a real cached TPF. Keep it only if the
deterministic acceptance test passes. Otherwise:

- leave the unfinished capability out of the judged path,
- use an alternate-aperture comparison plus cached neighbor/contamination context if those can be
  implemented reliably,
- label the fallback exactly as implemented,
- do not show a centroid plot or claim spatial localization.

## Submission gates

The project is ready to freeze only when:

- the planet-like and eclipsing-binary-like cached paths finish with different valid trajectories,
- the inconclusive case stays inconclusive,
- every displayed scientific number resolves to deterministic evidence,
- invalid model output exercises validation, bounded repair, or explicit fallback,
- inference statistics come from trace records and raw-sample count is zero,
- ground truth is inaccessible before lock and reveal verifies the same locked hash,
- `make reproduce` works without live astronomy-data access,
- the primary demo completes from a clean reset three consecutive times,
- the README contains tested setup steps, an architecture diagram, inference/API integration,
  error handling, reproduction/eval commands, claims, limitations, data attribution, and citations,
- the three-minute video shows live execution and architecture rather than relying on slides or
  unexplained UI alone,
- the video and repository links are public and verified.

A broken optional feature is a cut, not a reason to delay the shippable path. A high-value P1
feature that passes its gate should remain in scope while time remains.
