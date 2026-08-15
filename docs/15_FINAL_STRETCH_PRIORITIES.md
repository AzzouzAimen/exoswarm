# Final-Stretch Hackathon Priorities

This document is the delivery override for the remaining hackathon work. Roughly 70% of the event
time remains, so it ranks work by scoring value and dependency order rather than assuming an
emergency cut-down. Preserve high-value differentiators once the reliable core gates are green.
Coding agents should consult it before selecting their next task.

## Optimization target

Optimize for a working and legible software system: bounded inference, deterministic tools,
structured failures, durable traces, blind result locking, cached reproducibility, clear setup, and
a concise demonstration. Do not optimize for scientific breadth that is invisible in the judged
path.

The target audience is software, cloud, data, and security engineers. Explain the transferable
pattern: an LLM allocates a limited budget among bounded deterministic analyses; machine-enforced
contracts constrain it; an append-only ledger and trace make the result auditable; and a blind lock
prevents hidden answers from influencing the committed result.

## Scoring lens

The supplied review describes six equally weighted 10-point areas. Use them as a work-allocation
check, not as permission to fake or weaken the science:

| Area | Final-stretch response |
|---|---|
| Code structure and quality | preserve typed boundaries, explicit state, failures, tests, and recovery |
| Featherless API/compute integration | make live calls, validation, repair/fallback, and measured usage visible |
| Innovation and approach | lead with evidence-dependent actions, cost allocation, Critic review, and blind lock |
| Functional execution | complete two visibly different target paths and one inconclusive eval case |
| Three-minute video | show the real path, architecture, inference summary, blind proof, lock/reveal, and reproduction |
| Documentation and setup | exercise clean setup and document architecture, errors, inference, claims, limitations, and citations |

Do not let optional scientific breadth consume the work needed to make any entire scoring area
unjudgeable. Conversely, once all areas have credible evidence, use remaining time on the ranked P1
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

1. a real cached-TPF pixel/centroid diagnostic with a deterministic acceptance case and a strong UI
   visualization,
2. polished mission-control storytelling for evidence-driven branch differences, Critic review,
   cost allocation, failures, inference statistics, and blind lock/reveal,
3. one additional Observer or Signal model role only when its isolated context and bounded output
   cause a real, testable decision difference,
4. a fourth contamination/spatial end-to-end case when it validates the accepted centroid path,
5. deterministic forward-transit prediction if the underlying period/epoch contract is already
   stable and the result is clearly labeled.

These are gated, not discarded. A team member may start one in parallel as soon as its local
dependency is stable—for example, the science owner may pursue centroid after the cached vertical
slice passes—provided it does not block the primary planet-like/EB paths, live Featherless handling,
blinding, or reproducibility.

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

Centroid localization is not a P0 blocker, but it is one of the best remaining P1 opportunities.
Once the end-to-end core is stable, give it a focused, time-boxed implementation/acceptance window
using a real cached TPF. Keep it if the deterministic acceptance test passes. Otherwise:

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
- setup, architecture, inference, error handling, reproduction, claims, limitations, and citations
  are documented,
- the video and repository links are public and verified.

A broken optional feature is a cut, not a reason to delay the shippable path. A high-value P1
feature that passes its gate should remain in scope while time remains.
