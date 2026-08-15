# Temporary Plan: A Flashier, Result-Safe ExoSwarm Agent System

> Status: planning artifact only. No implementation is authorized by this document.
>
> Created from the repository snapshot reviewed on 2026-08-15. The working tree is dirty, so all
> retained baseline reports must be rerun from a clean release commit before they are used as
> promotion gates.

## Why this plan exists

The current ExoSwarm agentic system mostly does the scientific job it was built to do, and the
assessment found that its harness, deterministic safeguards, tracing, context isolation, and
evaluation setup are already strong. The problem is presentation and perceived ambition: only the
Skeptic and Critic currently make live LLM calls, their bounded task is fairly small, the Director
is entirely deterministic, and the Observer, Signal, and Transit Hunter roles exist only as
placeholder modules. As a result, the implemented system can look shallower and less agentic than
the underlying engineering deserves—especially in a hackathon where visible technical ambition and
an exciting three-minute story matter.

The project owner has therefore made an intentional hackathon product decision: prioritize a more
advanced, visibly multi-agent system even when that means additional model calls, prompts, latency,
and cost. This is not an accidental architecture drift or a request to minimize LLM usage. The
requested direction is to:

- add more real AI-agent roles, preferably reviving Observer, Signal, and Transit Hunter;
- turn the Scientific Director into an LLM-backed agent rather than leaving the visible role purely
  deterministic;
- strengthen prompt engineering with richer role definitions, structured outputs, grounding,
  examples, and evaluation;
- enable and evaluate the provider's thinking/reasoning mode, which is currently explicitly off;
- make agents perform and expose more understandable work so the investigation feels like a
  coordinated scientific swarm rather than two isolated JSON calls;
- preserve and extend the existing LLMOps, tracing, validation, recovery, and evaluation machinery;
- implement the remaining improvements identified in `AGENT_HARNESS_ASSESSMENT.md`, including
  prompt hashing, controlled prompt comparisons, grounded rationales, and broader real branching.

The governing quality rule is equally explicit: an added LLM role or prompt change is kept when the
scientific results remain the same or improve, even if the improvement is small. If it makes the
results worse, it must be adjusted and reevaluated; if the regression cannot be removed, that agent
or influence point is taken back out. Result-neutral agents are acceptable when they add honest,
traceable orchestration and demo value. For the Director specifically, it is acceptable to supply
the deterministic route as a binding, let the model reason about and explain it, and still execute
the deterministic answer so that the existing result cannot degrade.

This document was created to turn that decision into a concrete insertion and rollout strategy
before implementation. It identifies where the additional agents, prompts, thinking mode,
telemetry, evaluations, and mission-control presentation can be added without surrendering
deterministic scientific authority, blinding, bounded execution, or the current validated results.

## Executive decision

Build the original six-role ExoSwarm constellation—Scientific Director, Observer, Signal Analyst,
Transit Hunter, Skeptic, and Critic—but keep the existing deterministic controller as a
non-bypassable safety kernel.

The safe architecture is not “replace the controller with an unconstrained LLM.” It is:

```text
deterministic policy computes the authorized scientific route
                              |
                              v
LLM Director ratifies the route, synthesizes specialist briefs, and delegates focus
                              |
                              v
Observer + Signal Analyst -> Transit Hunter -> Skeptic -> independent Critic
                              |
                              v
controller validates every output and authorizes deterministic tools
                              |
                              v
evidence/state/trace persist -> deterministic stopping/disposition -> lock -> reveal
```

This gives the demo a real multi-agent system with seven normal model calls on the full path (two
Director calls plus five specialist/reviewer calls), while making every new call result-neutral by
default. A role may influence scientific action selection only after a locked comparison shows
baseline-or-better results. If any new role times out, emits invalid output, disagrees with a hard
route, or fails its eval gate, the current deterministic path continues unchanged and the UI labels
the fallback honestly.

The user's current direction intentionally supersedes older repository prioritization that says not
to add a separate LLM Director or ceremonial roles. It does **not** supersede deterministic numeric
authority, mandatory diagnostics, context safety, result blinding, evidence provenance, bounded
budgets, explicit stopping, or the single-provider constraint.

## What the audit found

| Surface | Current reality | Consequence for the plan |
|---|---|---|
| Live model roles | Only Skeptic and Critic call Featherless | Revive the three placeholder roles and add a bounded Director inference adapter |
| Director | `director.py` maps durable state to a typed route deterministically | Preserve this function as the route oracle; put the LLM around it as a ratifier/focus director |
| Adaptive breadth | Production usually offers `harmonic_test` or `stop`; centroid is disabled | More personas alone will not create meaningful tool branching; specialist briefs should improve the later Skeptic decision, and a second real action remains separately valuable |
| Thinking mode | Explicitly sent as `thinking: false` | Add a role-specific `off/on/auto` policy and promote `on` only after a controlled provider A/B |
| Prompts | Strong zero-shot schemas, but no few-shot set, prompt hashes, evidence-reference requirements, or bounded reason-code registry | Build a prompt registry, canonical examples, grounded rationale fields, and prompt/request fingerprints |
| Context | Strong 16 KB, opaque-ID, evidence-linked, fail-closed `agent-context-v3` packet | Reuse the sanitizer and create smaller role-specific projections; do not give every agent the whole packet |
| Harness | Typed validation, repair, fallback, budgets, recovery, persistence, subprocess tools, and blinding are strong | Generalize the harness instead of creating a second orchestration system |
| Current UI | Agent, adaptive-decision, evidence, hypothesis, plot, lock, and 3D panels are mostly static placeholders; one panel incorrectly says Skeptic/Critic are not implemented | Wiring real SSE/state into the mission-control surface is a P0 part of “flashiness,” not optional polish |
| Current eval evidence | Harness 24/24, cached-real 5/5, canary 20/20 schema/semantic/quality with four branches | Treat these as the behavior floor; all reports currently marked dirty must be rerun cleanly |

Current canary reference values to preserve in a clean rerun:

- first-attempt schema validity: 20/20;
- first-attempt semantic validity: 20/20;
- decision-quality checks: 20/20;
- resolved branches: 4;
- repairs, provider errors, and timeouts: 0;
- median/max latency: 3,669.5 ms / 11,630 ms;
- measured input/output tokens: 27,778 / 3,516;
- raw light-curve samples sent to the model: 0.

Because that canary is saturated, it cannot prove that thinking or richer prompts improve decision
quality. Keep it as a non-regression suite and add a separate locked set of genuinely ambiguous
cases for improvement measurement.

## Non-negotiable design rules

1. Deterministic Python remains the only source of measurements, units, diagnostics, scientific
   evidence, disposition rules, and result bytes.
2. The LLM Director never authorizes a tool or invents a route. It receives the controller's
   authorized route as an exact binding and must echo it.
3. Mandatory diagnostics remain code-enforced even if a model recommends a different order or says
   to stop.
4. New specialist outputs begin in shadow mode: persist and display them, but do not inject them
   into downstream decision prompts or durable scientific state.
5. Promotion is role-by-role. Result-neutral roles may ship on exact scientific parity; any role
   allowed to change a scientific branch must demonstrate an improvement on at least one locked
   difficult case with zero critical regressions.
6. The Critic remains independent: it receives deterministic evidence plus the Skeptic proposal,
   not the Director's conclusion or a synthetic agent conversation.
7. Hidden reasoning is neither persisted nor shown. The UI may show `reasoning requested`, time,
   token usage, schema status, and concise structured rationale—never chain-of-thought.
8. Ground truth, recognizable identity, local paths, raw arrays, and reveal authority remain absent
   from every role context before lock.
9. All added calls are bounded by total and per-role budgets, durable idempotency keys, timeouts,
   one repair, and explicit fallback behavior.
10. No second provider, database, message broker, microservice, RAG layer, or new orchestration
    framework is introduced.

## Proposed six-role constellation

### 1. Scientific Director — bounded ratifier and focus director

**Invocation points:** once after the mandatory evidence briefing and once immediately before final
lock/finalization. Do not call it every time `determine_route()` is reevaluated.

**Sees:** a small Director packet containing the exact deterministic `authorized_route`, active
hypothesis IDs, available role briefs, budgets, evidence references, and current lock state.

**Returns:** `DirectorDecision` with exact run/step/context bindings, echoed `authorized_route`, a
bounded `focus_hypothesis` selected from current hypotheses, requested specialist handoffs from an
allowlist, cited evidence IDs, conflict codes, and a short mission brief.

**Real work:** synthesize specialist disagreements, frame the next investigation objective, and
hand the Skeptic a focused unresolved question. At finalization it produces a concise evidence
summary for the UI while copying the deterministic disposition and route exactly.

**Authority:** no numeric fields, no tool parameters, no disposition changes, no direct graph
transition. A route mismatch is invalid output, is traced, and falls back immediately to the
deterministic route.

This is the user's proposed “give it the deterministic answer and let it think plus repeat it”
pattern, strengthened so the Director also performs useful synthesis without becoming an unsafe
router.

### 2. Observer — observation-quality specialist

**Invocation point:** after candidate/search evidence exists and before adaptive selection.

**Sees:** only observation quality, preprocessing metadata, relevant warnings, and evidence IDs.

**Returns:** `ObserverAssessment` containing bounded quality flags, observation limitations,
supported/unsupported preparation concerns, cited evidence IDs, and questions for later roles.

**Authority:** advisory in the first release. A later promotion may allow it to request one
registered preprocessing comparison such as alternate detrending, but only after that deterministic
tool exists and its eval shows a real benefit.

### 3. Signal Analyst — candidate-pattern interpreter

**Invocation point:** in parallel with Observer when the deterministic candidate summary exists.

**Sees:** candidate measurements already in the Evidence Ledger, completed-test codes, and a bounded
hypothesis vocabulary. It does not see raw samples or plots.

**Returns:** `SignalAssessment` with leading and alternative hypothesis IDs, ambiguity flags,
evidence citations, and non-numeric questions for vetting.

**Authority:** never computes period, depth, duration, SNR, or significance. Initially shadow-only;
after promotion, its assessment may be included as clearly labeled advisory context for Transit
Hunter and Skeptic.

### 4. Transit Hunter — candidate-vetting specialist

**Invocation point:** after Observer and Signal Analyst complete and mandatory diagnostic evidence
is available.

**Sees:** the deterministic candidate, mandatory diagnostic statuses, and validated specialist
briefs. It sees candidate IDs, not raw arrays.

**Returns:** `TransitHunterBrief` containing the selected `focus_candidate_id` from an allowlist,
viability/ambiguity codes, the strongest vetting question, cited evidence IDs, and ranked action
names drawn only from the currently available registry.

**Authority:** the first version does not execute or authorize an action. If multiple deterministic
candidates are supported later, candidate selection becomes a separate promotion gate rather than
being smuggled into this change.

### 5. Skeptic — stronger evidence-grounded experiment selector

Keep its existing action authority, but upgrade the output contract:

- require `supporting_evidence_refs` and `contradicting_evidence_refs` that must exist in the
  supplied packet;
- replace unconstrained reason strings with a bounded reason-code registry plus concise prose;
- add two or three canonical few-shot cases for `harmonic_test`, a second real adaptive action, and
  `stop`;
- optionally consume promoted specialist briefs and the Director focus question;
- retain exact budget/cost bindings and strict action validation.

### 6. Critic — independent adversarial reviewer

Keep `APPROVE / REVISE / VETO`, one revision maximum, and isolated context. Strengthen it with:

- evidence citations for every verdict;
- bounded verdict/reason codes;
- few-shot examples covering approve, revise, veto, and apparently valid but irrelevant actions;
- explicit checks for unsupported specialist claims if any are later included;
- no access to the Director's preferred answer, preserving real independence.

## Runtime insertion plan

The existing LangGraph remains the sole topology and the file-backed state remains restart
authority. During implementation, load the mandatory LangGraph skill before touching graph code.

Recommended durable path:

```text
mandatory deterministic tools complete
        |
        v
specialist briefing checkpoint
  |-- Observer -----------|  (parallel provider calls, independent contexts)
  |-- Signal Analyst -----|
        |
        v
Transit Hunter brief
        |
        v
LLM Director ratification + focus decision
        |
        v
Skeptic proposal -> independent Critic review
        |
        v
deterministic authorization -> deterministic adaptive tool
        |
        v
deterministic evaluation/stopping
        |
        v
LLM Director final brief (non-blocking) -> lock eligibility unchanged
```

Implementation details that prevent loops and duplicate calls:

- add a durable role checkpoint keyed by `(run_id, role, phase, context_version)`;
- reload state before and after every provider call;
- persist each accepted role output before advancing;
- execute Observer and Signal concurrently, but commit their decisions in a stable role order;
- never repeat a completed role checkpoint on resume;
- rebuild downstream contexts only from durable accepted outputs;
- keep advisory failures non-terminal and emit a typed `ROLE_SKIPPED_TO_SAFE_BASELINE` fallback;
- keep Skeptic/Critic failure semantics as strict as they are today;
- cap normal full-path calls at seven, with explicit per-role maxima and a larger bounded total (for
  example 24) to leave room for one repair without permitting an unbounded swarm;
- do not count advisory calls as scientific experiment steps or cost units, but do count them in
  model-call, latency, and token budgets.

## Prompt-engineering plan

Create one versioned prompt registry rather than scattering role-specific conditionals through the
provider client. Each role registration should define:

- role name and objective;
- prompt version;
- output schema;
- context projection;
- model and thinking policy;
- maximum output tokens;
- few-shot example set/version;
- deterministic semantic validator;
- timeout, repair, fallback, and per-role call limit.

Every role prompt should use the same stable sections:

1. role and scientific objective;
2. authority boundary and forbidden behavior;
3. allowed vocabulary/actions;
4. evidence-grounding and citation rules;
5. exact output bindings;
6. concise rationale policy;
7. strict output schema;
8. small canonical examples;
9. dynamic role-specific context.

Provenance must include both:

- `prompt_template_sha256`: static instructions/schema/examples;
- `rendered_request_sha256`: the complete sanitized request without persisting its body.

Require a prompt version bump whenever the template hash changes. Record prompt hash, example-set
version, context fingerprint, model identity, and thinking policy on every inference attempt.

Do not ask models to print chain-of-thought. Provider-side thinking may be enabled, but the only
persisted explanation remains a short schema field with evidence references.

## Thinking-mode rollout

Featherless currently documents `thinking: true` for DeepSeek V3/V4-family templates and exposes a
debug chat-format endpoint. It also warns that unsupported template keys may have no effect. The
DeepSeek-V4-Flash catalog page describes non-think and higher-reasoning modes. Therefore:

1. Add a role-specific `thinking_mode = off | on | auto` setting; retain `off` as the rollback
   baseline until the comparison passes.
2. Preflight the exact configured model ID through Featherless model metadata and
   `/debug/chat-format`. Confirm that `thinking: true` changes the rendered template for the exact
   alias used in this repository.
3. Test `thinking=true` with JSON mode because the current parser reads only `message.content`.
   Explicitly test empty content, reasoning-only responses, reasoning tags leaking into content,
   and `finish_reason=length`.
4. Start with no assumed thinking budget. If the exact template proves that `thinking_budget` is
   supported, tune a small role-specific budget; do not infer support from the generic docs.
5. Compare `off` and `on` with identical prompts, contexts, model ID, and temperature. Change one
   variable at a time.
6. Promote `on` for a role only if critical invariants stay perfect and that role is at least tied
   on its quality metric. Require a measurable improvement for any role whose output can alter a
   scientific branch.
7. Trace `thinking_requested` separately from `thinking_confirmed`. Only mark it confirmed when
   provider/template evidence supports that claim. Never show hidden reasoning content.
8. Raise the output ceiling only when measured truncation proves it necessary. Thinking and final
   JSON may compete for the current ceiling, so truncation rate and latency are first-class gates.

Primary provider references checked for this plan:

- [Featherless chat-template kwargs](https://featherless.ai/docs/chat-template-kwargs)
- [Featherless DeepSeek-V4-Flash model page](https://featherless.ai/models/deepseek-ai/DeepSeek-V4-Flash)
- [Featherless completion request/response contract](https://featherless.ai/docs/completions)

## Context and state changes

Do not widen one generic context packet until every role sees everything. Introduce a shared safe
envelope plus role-specific payloads:

| Role | Required context | Explicitly excluded beyond global exclusions |
|---|---|---|
| Observer | quality/preprocessing evidence | adaptive recommendations from other agents |
| Signal | candidate measurements and interpretation codes | Observer conclusions during shadow phase |
| Transit Hunter | candidate + mandatory results + promoted briefs | Critic verdict and ground truth |
| Director | deterministic route + compact accepted briefs + state budgets | raw tool payloads and hidden authority |
| Skeptic | current deterministic evidence + promoted briefs | Critic output |
| Critic | current deterministic evidence + exact Skeptic proposal | Director preference and specialist consensus |

Persist generic accepted decisions as append-only records with role, phase, schema version,
decision ID, evidence refs, context fingerprint, prompt hash, model identity, and concise output.
Keep only references/checkpoints in `state.json` so the snapshot does not become a growing chat log.

Add deterministic validation for:

- all cited evidence IDs exist and were in the role context;
- selected hypothesis/candidate/action IDs are allowlisted;
- no new numeric scientific claims appear in narrative fields;
- exact route, disposition, run, step, context, and budget bindings match;
- advisory outputs cannot mutate evidence, disposition, lock, or tool-execution records;
- context stays under its ceiling and passes the existing recursive safety scan.

## LLMOps and evaluation strategy

### Locked baselines

First create clean, immutable baselines for:

- the 24-case adversarial harness suite;
- the five-case cached-real TESS suite;
- the 20-decision live Skeptic/Critic canary;
- the three retained live backend targets;
- the exact three-minute demo path repeated three times.

Keep the existing v1 evaluator locked. Add new v2 cases; never edit v1 criteria to make a new role
look better.

### Outcome comparison

Create a deterministic semantic comparator that ignores generated IDs/timestamps but compares:

- terminal status and disposition;
- mandatory test completion;
- tool/action sequence and budgets;
- scientific measurement names, values, units, tolerances, and provenance;
- failure class and fallback label;
- lock/reveal invariants;
- raw-sample and hidden-authority counts.

Do not compare lock hashes across different run IDs as the sole parity signal; preserve the real
lock algorithm and compare a separate canonical scientific-outcome projection.

### Role-specific evals

| Role/change | Deterministic quality gate |
|---|---|
| Thinking mode | schema/semantic validity, truncation, latency, provider errors, task score |
| Observer | correct quality flags, evidence citations, no unsupported preparation claim |
| Signal | allowed hypothesis codes, correct evidence grounding, no invented measurements |
| Transit Hunter | valid candidate/action references and useful vetting focus |
| Director | exact authorized-route parity, allowed handoffs, grounded synthesis |
| Skeptic | correct evidence-dependent action, valid cost/budget, citations, branch diversity |
| Critic | correct approve/revise/veto outcome, relevance, independence, citations |

Use an LLM judge only for concise explanation clarity/groundedness after deterministic checks pass.
Use pairwise, order-swapped comparisons against the current prompt and calibrate a small sample by
human review. The LLM judge must never certify scientific numeric correctness or replace the locked
deterministic grader.

### Promotion matrix

| Tier | Can affect scientific result? | Required outcome |
|---|---:|---|
| Shadow | No; persist/trace/display only | All safety/schema checks pass; no baseline outcome change |
| Advisory | Indirectly; brief is visible to a later role | Baseline parity plus no decrease on difficult cases |
| Action-bearing | Yes; can change selected bounded action | At least one locked difficult-case improvement, no critical regression, no weaker blinding/validation |
| Removed | N/A | Any unfixable regression, unacceptable demo latency, or repeated invalid/fallback behavior |

Critical release thresholds:

- 100% v1 harness and cached-real cases;
- 100% ground-truth lock, context safety, mandatory-tool, and numeric-provenance assertions;
- 100% validity after the one-repair policy;
- at least 95% first-attempt schema/semantic validity for each new role, with a goal of 100%;
- zero unsupported scientific numbers;
- zero repeated role checkpoints or duplicate tool actions after restart;
- no worse scientific outcome on any existing case;
- action-bearing change improves at least one predeclared difficult case;
- full online demo comfortably under three minutes at p95, with cached/offline fallback retained;
- exact judged path passes three consecutive clean resets.

## Mission-control experience

The current frontend hides almost all of the backend's strongest work. Implement the visual layer
from real state and SSE events alongside the new roles.

The core visual should be a six-role constellation around the existing central target scene, backed
by a compact chronological handoff rail rather than a chatbot transcript or a Graphify-generated
diagram. Each role has real states: `queued`, `reasoning`, `validated`, `repairing`, `fallback`,
`complete`, or `skipped`.

For the active role, show only:

- role objective;
- evidence IDs/count received;
- bounded action or brief produced;
- concise rationale;
- model identity;
- thinking requested/confirmed status;
- latency and token usage when measured;
- schema/semantic validation and fallback status;
- prompt version/hash and context fingerprint in an expandable audit detail.

Animate real transitions only:

1. deterministic tool emits evidence;
2. Observer and Signal light up in parallel;
3. Transit Hunter receives their validated briefs;
4. Director publishes the mission focus;
5. Skeptic proposes an experiment;
6. Critic approves, revises, or vetoes;
7. deterministic tool executes and evidence updates;
8. Director publishes the final brief;
9. result locks and catalog truth reveals.

The scientific plot and measured evidence remain more prominent than agent prose. “Reasoning” is a
live status indicator, not a stream of hidden thoughts. The UI must clearly distinguish live model,
repair, deterministic fallback, and cached/offline replay modes.

Backend event additions should be generic and typed, for example:

- `agent.queued`;
- `agent.started` (already present, generalized to all roles);
- `agent.completed`;
- `agent.handoff`;
- `agent.skipped`;
- `agent.decision` (generic validated output summary);
- existing `inference.attempt`, `inference.fallback`, and `inference.summary` with per-role fields.

Update the frontend's static text immediately when implementation begins; it currently claims that
Skeptic and Critic are not implemented. Verification should use component/type/lint/build checks and
the backend event fixtures; do not introduce Playwright/browser verification unless separately
requested.

## File-level implementation map

| Area | Expected files | Planned change |
|---|---|---|
| Role types and decisions | `domain/enums.py`, `domain/models.py` | Generic role enum, specialist schemas, Director schema, generic decision/checkpoint records, reasoning telemetry |
| Role contexts | `agents/context.py` plus optional role-context modules | Shared safe envelope, strict role projections, citation validation, size limits |
| Prompts | `agents/observer.py`, `signal.py`, `transit_hunter.py`, `director.py`, `skeptic.py`, `critic.py` | Real adapters, few-shot sets, reason-code contracts, prompt hashes |
| Provider boundary | `agents/model_client.py`, `agents/inference_provider.py`, `agents/inference_telemetry.py`, `config.py` | Role registry, per-role thinking policy, generic output mapping, role metrics, total/per-role budgets |
| Orchestration | `investigation/controller.py`, `agents/graph.py` | Durable briefing checkpoints, parallel Observer/Signal calls, Director ratification nodes, restart-safe fallback |
| Persistence/events/API | `services/artifacts.py`, `domain/events.py`, `api/routes_investigations.py`, `docs/08_API_EVENTS.md` | Append-only agent decisions, typed handoffs, safe public summaries |
| Evaluation | `evals/provenance.py`, canary scripts, harness fixtures, new prompt/role eval fixtures | Prompt hashes, thinking A/B, role quality, outcome parity, failure/restart cases |
| UI | `apps/web/src/lib/*`, mission-control components | Real SSE reducer, six-role activity surface, handoffs, audit telemetry, lock/reveal continuity |
| Documentation | assessment/runtime/inference/testing/README docs after promotion | Exact behavior, limitations, eval results, demo narrative |

No scientific algorithm should be changed as part of the role-infrastructure phases. A second real
adaptive tool is a separate science task with its own deterministic validation gate.

## Staged implementation order and stop/go gates

### Stage 0 — freeze the truth baseline

- Finish or isolate current unrelated work.
- Rerun all existing suites from a clean commit.
- Save sanitized configs, prompt versions, hashes, model identity, and result reports.
- Add the semantic scientific-outcome comparator.

**Go only if:** all current gates pass cleanly. Otherwise diagnose the baseline first.

### Stage 1 — generalize prompt/inference/trace infrastructure with no behavior change

- Add the role/prompt registry, prompt hashes, rendered request hashes, per-role config, and generic
  telemetry.
- Keep only Skeptic/Critic registered and thinking off.
- Preserve exact existing outputs and event behavior.

**Go only if:** v1 outcomes are identical and the live canary remains at its current quality floor.

### Stage 2 — improve Skeptic/Critic prompts and A/B thinking

- Add evidence citations, bounded reason codes, and a small few-shot set.
- Run one-variable-at-a-time comparisons: baseline, prompt-only, thinking-only, then combined.
- Add ambiguous v2 cases before optimizing against them and lock their criteria.

**Keep:** the simplest variant that meets or beats the baseline. **Revert:** any variant that lowers
validity, groundedness, branch quality, or demo reliability.

### Stage 3 — revive Observer, Signal Analyst, and Transit Hunter in shadow mode

- Implement strict schemas, contexts, prompts, fallback outputs, checkpoints, and events.
- Persist/display outputs but do not expose them to Skeptic, Critic, disposition, or tools.
- Run them on all locked cases and inspect disagreements.

**Go only if:** scientific outcome parity is exact, citations are valid, and latency fits the demo.

### Stage 4 — add the LLM Director as a non-bypassable ratifier

- Keep `determine_director_route()` as the deterministic oracle.
- Add one Director briefing and one final Director synthesis call.
- Reject mismatched routes and continue on the deterministic route.
- Display ratification, focus, handoffs, and fallback status.

**Go only if:** route parity is 100%, restarts do not duplicate calls, and Director failure never
changes the scientific result.

### Stage 5 — controlled advisory influence

- Feed validated Observer/Signal briefs to Transit Hunter.
- Feed validated Transit Hunter and Director focus fields to Skeptic, one source at a time.
- Keep Critic isolated.
- Compare each addition against the locked baseline and the previous accepted variant.

**Promote:** only if parity or improvement is demonstrated. **Remove from downstream context:** any
brief that adds correlation, verbosity, or worse action choice.

### Stage 6 — mission-control choreography

- Replace all placeholder panels with a real SSE-driven reducer.
- Show the six roles, real handoffs, thinking status, validation, evidence, tool execution, budgets,
  telemetry, lock, and reveal.
- Keep scientific plots and deterministic evidence dominant.

**Go only if:** every displayed state can be traced to a backend event/artifact and failure/offline
modes are honestly labeled.

### Stage 7 — release and demo hardening

- Rerun v1, v2, cached-real, thinking canary, live backend, frontend build, reproduce, blinding,
  restart, timeout, repair, fallback, and lock/reveal checks.
- Run the exact full-agent demo three consecutive times from clean reset.
- Capture a cached/offline run of the same real trace for provider outage recovery.
- Freeze prompts/model/thinking configuration and document the result.

## Pre-mortem: how this plan could fail

### 1. Judges see ornamental agents — likelihood high, impact high

Five new personas produce paraphrases of the same evidence, the UI looks like role-play, and judges
notice no decision difference. Mitigation: distinct contexts/contracts, real persisted handoffs,
role-specific evals, and at least one promoted specialist contribution that improves or preserves a
hard case. Never show fabricated agent conversation.

### 2. Thinking mode breaks structured JSON — likelihood medium, impact high

Reasoning consumes the output budget or moves content outside `message.content`; repairs multiply,
latency grows, and a live run fails. Mitigation: exact-model template preflight, JSON-mode canary,
truncation tests, role-level rollout, explicit reasoning telemetry, and one-switch rollback to off.

### 3. Sequential calls miss the three-minute demo — likelihood medium, impact high

Seven calls at current worst-case latency consume most of the demo. Mitigation: parallelize only
Observer/Signal, cap each optional role at one attempt plus one repair, use hard deadlines,
non-blocking advisory fallbacks, measure p95 end-to-end time, and retain a clearly labeled cached
path.

### 4. Specialist consensus weakens the Critic — likelihood medium, impact high

All roles see each other's opinions, converge on the same framing, and the Critic stops being
independent. Mitigation: role-isolated contexts, deterministic evidence as shared truth, fixed merge
order, and a Critic packet that excludes Director/specialist conclusions.

### 5. Evals are changed until the new design passes — likelihood medium, impact critical

Prompt/agent changes silently weaken acceptance criteria and create a flashy but less trustworthy
system. Mitigation: preserve v1 locks, add rather than rewrite v2 cases, record all failed variants,
compare dimension-by-dimension, and make safety/science regressions absolute blockers rather than
tradeable aggregate points.

## Definition of done

The flashy multi-agent redesign is complete only when:

- all six named roles make real, traceable, schema-validated contributions on the full demo path;
- the deterministic route and scientific tools remain authoritative and non-bypassable;
- provider thinking is verifiably requested/active for promoted roles and can be disabled by config;
- no hidden reasoning is stored or displayed;
- specialist outputs cite model-visible evidence and contain no invented measurements;
- current scientific, blinding, budget, restart, lock, and reveal gates do not regress;
- at least one difficult case improves before any new role gains action-bearing influence;
- optional-role failures fall back to the current result instead of failing the investigation;
- the mission-control UI visibly and honestly shows agent handoffs, decisions, tools, evidence,
  validation, inference telemetry, and lock/reveal;
- the full online judged path passes three consecutive clean runs within the three-minute envelope;
- every accepted prompt/config is hash-versioned and tied to a clean evaluation report.

## Recommended first implementation slice

When implementation is authorized, start with Stage 0 and Stage 1 only. The smallest high-value
vertical slice is:

1. clean baseline reports;
2. generic role/prompt registry and prompt hashes with current behavior unchanged;
3. exact-model thinking-mode A/B for Skeptic/Critic;
4. a real SSE-driven six-role UI shell that can distinguish unavailable, shadow, live, repair, and
   fallback states;
5. then revive Observer in shadow mode as the first new specialist.

That sequence exposes the existing system immediately, creates the evaluation machinery needed for
safe iteration, and prevents the later agents from being added faster than they can be measured.
