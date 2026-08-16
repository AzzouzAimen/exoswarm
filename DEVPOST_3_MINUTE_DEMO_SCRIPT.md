# ExoSwarm — Repo-Aware Devpost 3-Minute Demo Package

Prepared from the repository snapshot on 2026-08-16. Claims are labeled by the strongest evidence available:

- **CONFIRMED — rerun now:** exercised during this audit.
- **CONFIRMED — provider gate:** exercised against Featherless.ai during this audit and persisted as a report.
- **IMPLEMENTED — not visually verified:** present in code/tests, but the browser UI was not exercised because repository instructions prohibit browser verification unless explicitly requested.
- **PLANNED / UNAVAILABLE:** documented or registered but not safe to present as working.

## PART A — Repository Findings

### Project

ExoSwarm is an auditable AI-assisted investigation system for candidate exoplanet signals in cached NASA TESS light curves. It performs photometric vetting: deterministic Python measures a signal and tests common false-positive explanations, while bounded AI roles decide which permitted follow-up is most informative. The human viewer sees the official reference immediately; the agents receive only an opaque target ID, and the finished independent result is compared automatically.

### Target User

The primary product user is a computational researcher who needs agents to investigate observational data with a reviewable workflow. Exoplanet analysis is the concrete demonstration, but the product story is broader: ExoSwarm is research software for teams that want agentic speed, deterministic compute, reproducible evidence, and human control. A second audience is the AI/platform engineer building reliable agent systems.

### Problem

Computational research is often fragmented across scripts, plots, model outputs, and manual review. Adding an LLM introduces another layer of decisions to trace: why a test ran, where a number came from, and whether the known answer influenced the result. ExoSwarm demonstrates this general research-software problem with one easy-to-understand question: can a team of agents investigate an anonymous NASA observation and leave a reproducible record before the catalog comparison?

### Core Solution

The user chooses a cached observation and can see its official identity and catalog class. The agents receive only its opaque ID. Deterministic tools search for a transit-like period and run mandatory odd/even, secondary-eclipse, and contamination checks. Six model roles receive compact evidence packets and propose or review only allowlisted actions. A controller validates outputs, permissions, preconditions, duplication, and budgets. At completion, the UI immediately shows whether the independent interpretation matched the official viewer reference.

### Main Features

- Mission Control UI backed by FastAPI REST and ordered Server-Sent Events, with a separate recorded-scenario mode for offline presentation.
- Cached TESS FITS inputs with acquisition metadata and checksums.
- Deterministic BLS candidate search, odd/even comparison, secondary-event search, contamination screening, and adaptive harmonic testing.
- Six bounded roles: Observer, Signal, Transit Hunter, Director, Skeptic, and Critic. The normal adaptive flow makes seven calls because Director participates at briefing and finalization.
- Strict Pydantic schemas, prompt version/hash locks, one bounded repair attempt, explicit fallback policy, role/tool budgets, timeouts, and terminal reasons.
- Agent-safe context using opaque target IDs, evidence references, approved actions, and budgets—without raw samples, local paths, catalog truth, or hidden chain-of-thought.
- Durable `state.json`, append-only trace/evidence/decision ledgers, inference telemetry, artifacts, and restart recovery.
- Mission-control plot projections for raw, BLS, phase-folded, odd/even, secondary, and harmonic views.
- Separate viewer-only catalog API, enforced agent-context isolation, and automatic end-state comparison; exact-byte result hashing remains available for reproducibility.
- Five cached TESS evaluation cases covering planet-like, weak, eclipsing-binary, and insufficient-evidence outcomes.

### Tech Stack

| Layer | Important implementation |
|---|---|
| Web | Next.js 16, React 19, TypeScript, Tailwind CSS, Plotly.js, React Three Fiber |
| API/events | FastAPI, Pydantic v2, Uvicorn, REST, SSE |
| Agent runtime | LangGraph routing envelope plus an explicit durable controller loop |
| Inference | OpenAI-compatible Python client to Featherless.ai; `deepseek-ai/DeepSeek-V4-Flash-0731` |
| Science | Lightkurve, Astropy BoxLeastSquares, NumPy, SciPy, Pandas, Matplotlib |
| Persistence | Local JSON/JSONL, atomic state snapshots, append-only ledgers |
| Verification | pytest, Ruff, Vitest, ESLint, TypeScript, Next.js build, GitHub Actions, Docker |

### External Services / APIs

- **Featherless.ai:** structured inference for all six roles through an OpenAI-compatible client.
- **MAST TESS archive:** provenance source for the committed light-curve files. Normal demo runs use local cached FITS files and make no MAST request.
- **NASA Exoplanet Archive / MAST TESS-EB catalog:** viewer-only reference shown from the start and excluded from agent packets. Normal runs use a versioned local catalog cache.
- No database, authentication provider, queue, vector store, or second model provider is implemented.

### AI / Model Usage

The AI does not read raw light-curve arrays and does not calculate period, depth, duration, or signal-to-noise. Each role receives a role-specific, compact, typed packet containing opaque identity, evidence IDs, summaries, allowed actions, and remaining budgets. Featherless returns strict structured JSON. The controller validates identity bindings, schema, citations, semantics, permissions, costs, and current context before accepting an output. The Skeptic proposes one experiment; the Critic returns `APPROVE`, `REVISE`, or `VETO`; the controller remains the execution and final-disposition authority. Attempts, latency, tokens, validation, repairs, and fallbacks are persisted as telemetry, while hidden chain-of-thought and raw provider bodies are excluded.

### Technical Highlights

1. **Judgment/authority separation:** agent roles can interpret and propose; code authorizes; deterministic tools measure.
2. **Viewer/agent separation:** the answer key is visible to the audience from the start but absent from all agent contexts, tools, state, and events.
3. **Advanced inference-and-compute pipeline:** six role-specific prompts, schema validation, bounded repair/fallback, Skeptic-to-Critic review, allowlisted subprocess science tools, evidence updates, and deterministic finalization.
4. **Durable, resumable harness:** atomic snapshots and append-only ledgers allow state reload and prepared-action recovery without treating model conversation as the source of truth.
5. **Traceable UI projection:** scientific numbers and plot readouts resolve back to evidence references; public events are ordered and UI-safe.

### Current Limitations and Risks

- The repository has no deployed demo URL yet; the README still contains a placeholder.
- Browser behavior was not verified in this audit, by repository instruction. UI claims are supported by code, component tests, API tests, and a production build.
- Frontend tests are currently **38/38 passing**, with TypeScript and ESLint also green after the automatic comparison redesign.
- The current full six-role Featherless path passed **three consecutive fresh C11 gates** in 64.9–71.9 seconds. Each used seven calls, had zero provider errors/timeouts, achieved 100% first-attempt schema validity, selected an approved harmonic test, sent zero raw samples, and verified the reveal hash. Routine waiting can be removed in edit while preserving the visible event sequence.
- A fresh B42 gate also passed in 29.5 seconds with a different `decisive_baseline` route: one model call, no adaptive action or Critic call, a rejected planetary interpretation, zero raw samples, and a verified reveal hash. This proves evidence-dependent branching rather than a canned role procession.
- An older standalone Featherless canary file records a failed acceptance threshold (80% first-attempt validity versus 90% required). Newer full-backend gate files pass, but the stale failing artifact can confuse judges unless clearly superseded or regenerated.
- Cached reproduction emits Astropy FITS checksum warnings even though repository acquisition SHA-256 checks and the reproduction result pass. Explain or clean this warning before recording terminal footage.
- Pixel/centroid localization is explicitly registered as unavailable and must not be shown or claimed.
- Contamination is aggregate aperture context (`CROWDSAP` fallback), not spatial source localization.
- The system is fixed-target, cached, single-sector, local/single-process, and has no authentication or distributed scaling layer.
- Provider-backed inference depends on network availability. Recorded-scenario mode is an explicit offline option and never activates automatically.
- The architecture PNGs exist and are accurate, but they are extremely wide and dense for a 20-second video insert. Use a deliberate crop/zoom or a simplified five-node overlay.

## PART B — Demo Evidence Table

| Claim / Feature | Repository Evidence | Runtime Verified? | Demo Worthy? | Reason |
|---|---|---:|---:|---|
| Uses cached NASA TESS observations | `data/cached/lightcurves/*.fits`, `data/ground_truth/*-acquisition.json`, `apps/api/src/exoswarm/services/target_registry.py` | Yes—reproduction and cached-TESS tests | Yes | Provides stable inputs without a network dependency during the run. |
| Deterministic tools own scientific measurements | `apps/api/src/exoswarm/science/`, `investigation/tool_registry.py`, `science/contracts.py` | Yes—221-test backend suite | Yes | Central trust and architecture differentiator. |
| Mandatory false-positive baseline | `investigation/mandatory.py`, controller mandatory path | Yes—reproduction ran all four checks | Yes | Turns “found a dip” into actual vetting. |
| Featherless powers six specialist roles | `agents/inference_provider.py`, `agents/prompt_registry.py`, `docs/inference.md` | Yes—three fresh C11 provider gates | Yes | Directly addresses API & Compute Integration. |
| Skeptic proposal receives independent Critic review | `agents/skeptic.py`, `agents/critic.py`, controller decision path | Yes in tests; recorded provider gate | Yes | Shows the proposal, review, and execution boundaries in one sequence. |
| Model actions are allowlisted, typed, permissioned, and budgeted | `investigation/tool_registry.py`, `science/contracts.py`, `investigation/stopping.py`, `domain/models.py` | Yes—unit/adversarial tests | Yes | Makes agent control concrete and defensible. |
| Agent context excludes raw samples and identity | `agents/context.py`, `agents/role_context.py`, `security/blinding.py` | Yes—privacy tests and cached eval report | Yes, briefly | Shows how the application scopes model context. |
| State/evidence/decisions are durable and inspectable | `services/artifacts.py`, `investigation/persistence.py`, `runs/` contract | Yes—persistence and recovery tests | Yes | Shows production-minded engineering. |
| UI consumes API state and ordered events | `web/.../use-live-investigation.ts`, `lib/events.ts`, API SSE route | Implemented; API/tests/build verified, no browser run | Yes | Makes processing visible instead of narrating it abstractly. |
| Scientific plots are downsampled backend projections with evidence refs | `science/plot_projection.py`, `services/mission_control.py`, `ScientificPlotPanel.tsx` | Yes—mission-control tests | Yes | Connects each displayed measurement to its evidence record. |
| Viewer sees catalog reference while agents receive an opaque ID | viewer catalog API, context guards, `ResultComparisonPanel.tsx` | Yes—API/privacy/context tests | Essential | Makes the context boundary visible throughout the run. |
| Five cached TESS cases produce distinct trajectories | `evals/real_tess/v1/cases.json`, `evals/cached_real_tess_report.json` | Yes—committed report; backend test rerun | Secondary | Useful evaluation coverage, but too much for one three-minute story. |
| Centroid localization works | Tool spec says `implemented=False`; README says unavailable | No | No | Must not be implied or demonstrated. |

### Verification Run During This Audit

| Check | Result |
|---|---|
| Cached reproduction (`scripts/reproduce.py`) | PASS in 19.8s; 4 mandatory checks, 2 scripted model-boundary calls, 4 tool calls, 8 artifacts, matching lock/reveal hash |
| Full backend suite | 221 passed, 1 skipped, 4 warnings |
| Focused backend/API/privacy/lock suite | 24 passed |
| Ruff | PASS |
| ESLint | PASS |
| TypeScript | PASS |
| Next.js production build | PASS |
| Frontend tests | **38 passed** |
| Featherless thinking-mode preflight | PASS; exact model template found, on/off formatting differs, no secret persisted |
| Fresh C11 API/Featherless gates | **3/3 PASS**; 64.9–71.9s, 7 calls each, harmonic test + Critic APPROVE, 100% first-attempt schema validity, 0 provider errors, 0 raw samples, verified hashes |
| Fresh B42 contrasting provider gate | PASS in 29.5s; decisive baseline, 1 model call, no adaptive/Critic path, rejected interpretation, verified hash |

### Demo Readiness Result

Overall: **READY TO RECORD; NOT YET READY TO SUBMIT.** The core product path is repeatable, but the final browser capture/export and the lone frontend regression still need closure.

| Gate | Verdict | Evidence / Remaining Condition |
|---|---|---|
| Clean startup / service availability | **PASS** | Existing web `/` and API `/health` returned HTTP 200; an isolated API startup also reached application-ready state. A second Next dev process was intentionally not forced because the user's existing dev server owns its workspace lock. |
| Cached inputs | **PASS** | Cached FITS acquisition hashes are checked by the cached-backend suite; routine runs make no astronomy-network request. |
| Science pipeline | **PASS** | Reproduction passed and the full backend suite is 221 passed / 1 skipped. |
| Adaptive agent branch | **PASS** | C11 passed 3/3 with Skeptic harmonic proposal, Critic APPROVE, and deterministic execution. |
| Model routing | **PASS** | C11 used the seven-call six-role route; B42 used a one-call decisive route, proving conditional routing. |
| Viewer/agent isolation | **PASS** | The viewer catalog is available without a run while agent-safe API, SSE, and context tests reject catalog fields. |
| Reproduction audit | **PASS** | The retained offline lock/hash path still verifies exact result bytes. |
| Frontend build | **PASS** | TypeScript, ESLint, optimized Next.js build, and all 38 frontend tests pass. |
| Total edited demo runtime | **FAIL — pending artifact** | Script is exactly 3:00 and 328 words, with loading marked for removal, but the finished export has not yet been recorded and timed. |

## PART C — Recommended Demo Story

A computational researcher starts with a TESS observation and a question. They choose `TARGET-C11`; the viewer already sees that it is WASP-4 b, while the agents receive only the opaque ID. The harness runs the required baseline, streams results into an evidence ledger, and gives compact evidence packets to six Featherless-backed roles. The specialist agents interpret, challenge, and route the investigation; the Skeptic requests one targeted follow-up, and the Critic independently reviews that request before the harness spends compute. The system reaches an evidence-grounded result and immediately shows a plain `MATCH` verdict beside the official record. The visible contract is simple: **the viewer knows, agents stay blind, the harness controls, and tools measure.**

## PART D — The Wow Moment

1. **What it is:** The viewer watches a multi-agent harness turn evidence into action: the Skeptic requests a targeted test, the Critic approves it, deterministic compute executes it, and the independent result automatically lands beside the official reference with a plain verdict.
2. **Why it matters:** The agents select among bounded actions while measurement, compute budgets, and catalog access remain controller-owned. The audience can see the catalog answer throughout; the agent context contains only the opaque target ID and evidence packet.
3. **Why it is impressive:** It combines multi-stage agent orchestration, constrained tool use, numerical compute, event-stream observability, append-only evidence, and a blind evaluation protocol.
4. **Where it belongs:** Build toward the adaptive proposal at approximately **1:30**, then deliver the automatic comparison payoff at **1:58–2:15**.

## PART E — Official 60-Point Judging Alignment

| Scoring Criterion | Max Points | Repository Evidence | Runtime/Demo Evidence | Current Strength | How We Maximize This Score |
|---|---:|---|---|---|---|
| Code Structure & Quality | 10 | Domain/science/investigation/agents/API/security boundaries; typed schemas; explicit errors, budgets, persistence, tests | 221 backend tests; lint/type/build green | Strong | Show one concise authority-boundary graphic and keep links to exact modules in submission text. |
| API & Compute Integration | 10 | Featherless provider, six prompt contracts, structured validation, repair/fallback, Skeptic/Critic pipeline, deterministic tool registry | Three fresh C11 gates plus a contrasting B42 gate; all passed with verified hashes | Strong | Show provider/model/schema telemetry and the Skeptic → Critic → targeted follow-up sequence in-frame. |
| Innovation & Approach | 10 | Opaque targets, evidence-budget allocation, independent review, deterministic authority, append-only audit, pre-reveal hash | Full workflow visibly connects these boundaries | Strong | Frame this as a reusable controlled-agent pattern, not merely “multi-agent astronomy.” |
| Functional Execution | 10 | Cached TESS path, distinct outcomes, UI/API integration, lock/reveal | Reproduction and tests pass; browser not checked in this audit | Strong with recording risk | Rehearse C11 three times and fix the lone frontend test before recording. |
| 3-Minute Video Demo | 10 | Mission-control UI and two architecture assets exist | Script below allocates 92s to product execution and 20s to architecture | Medium until recorded | Capture clean live footage, readable zooms, result lock/reveal, and a concise architecture crop. |
| Documentation & Setup | 10 | Detailed README, quick starts, diagrams, citations, limitation section, engineering docs | Commands largely rerun successfully | Strong, one visible gap | Replace the hosted-demo placeholder and ensure public repository/video links work. |
| **TOTAL** | **60** | | | **Strong foundation; not yet submission-ready** | Fix the red test, rehearse the browser capture, and publish links. |

### E1 — Code Structure & Quality — 10 Points

Concrete evidence includes:

- `domain/models.py`, `domain/enums.py`, and `domain/errors.py` define typed contracts independent of adapters.
- `science/` owns numerical algorithms; `investigation/` owns policy, state, persistence, budgets, stopping, and tool authorization; `agents/` owns role prompts/context/inference; `api/` projects durable state through REST/SSE; `security/` owns lock and reveal.
- `ScientificToolRegistry` rejects unknown tools, missing scopes, invalid strict parameters, and model/backend input overlap before invocation.
- `InvestigationController` enforces mandatory diagnostics, duplicate-action checks, budgets, terminal reasons, recovery, and numerical provenance.
- `FileSystemRunArtifactStore` separates atomic state snapshots from append-only evidence, trace, and decision ledgers.
- `prompt_registry.py` locks prompt template hashes and versions so prompt changes are reviewable.
- Error/failure behavior is tested across malformed output, repair failure, provider timeout, stale context, repeated actions, tool failure/timeout, restart recovery, and budget exhaustion. The adversarial harness report is 24/24 passing.

**What earns 10/10:** Judges should see the boundaries in the running workflow and the corresponding tests. Resolve the lone frontend test mismatch, link the architecture and harness diagrams prominently, and show the controller/allowlist/lock path for a strong 10/10 case.

### E2 — API & Compute Integration — 10 Points

**Actual data flow:**

`Cached TESS FITS → deterministic preprocessing/BLS/mandatory checks → compact evidence packet → role-specific Featherless prompt → strict JSON output → schema/semantic/permission/budget validation → Skeptic proposal → Critic verdict → allowlisted subprocess tool → append-only evidence → deterministic disposition → SHA-256 lock → gated catalog comparison`

Featherless.ai supplies judgment for six roles through `deepseek-ai/DeepSeek-V4-Flash-0731`. Before inference, the application constructs role-specific context and versioned prompts. After inference, it validates bindings, citations, actions, budgets, and output schema; it allows one bounded repair/fallback and records telemetry. The selected action is then executed by a numerical Python tool.

**Classification: Advanced Pipeline.** This is supported by role routing, multi-stage structured inference, independent proposal review, validation/repair/fallback, constrained tool execution, durable evidence updates, measured telemetry, and a lock/reveal security boundary. The clearest video sequence is Skeptic → Critic → targeted compute, followed by a quick Run Integrity/telemetry readout.

### E3 — Innovation & Approach — 10 Points

The distinctive unit is a **blind, budgeted evidence investigation**: role-isolated judgments allocate limited compute among registered tests, a separate Critic challenges the proposed spend, numerical tools produce every displayed measurement, durable ledgers preserve provenance, and the catalog comparison is gated until commitment. Astronomy makes this pattern easy to understand, and the same control model can apply wherever AI prioritizes evidence while application code retains measurement and authorization boundaries.

### Demo Language Rule for a Non-Scientific Panel

Do not teach BLS, transit geometry, odd/even depth analysis, secondary eclipses, or harmonic aliases in the video. Translate them into **required baseline checks**, **one unresolved question**, and **one targeted follow-up**. Let plots and evidence movement show the computation as it progresses. Use high-value software terms only when the screen supports them: **multi-agent research harness**, **bounded autonomy**, **agentic compute orchestration**, **deterministic authority**, **event-stream observability**, **evidence ledger**, **structured outputs**, and **cryptographic result lock**.

### E4 — Functional Execution — 10 Points

- **Target user:** computational researcher who wants agents to investigate observational data with clear control, provenance, and reproducibility.
- **Problem:** research workflows are fragmented, and a model opinion alone does not record why compute ran or where a result came from. Exoplanet vetting supplies a concrete test case.
- **Primary workflow:** select a viewer-known/agent-opaque target → run deterministic baseline → observe structured role handoffs → approve/execute one adaptive test → see the automatic independent/catalog verdict.
- **Useful result:** an evidence-grounded photometric-vetting disposition, audit trail, and independent/catalog comparison—not a claim of planet confirmation.
- **Practical benefit:** faster, more legible first-pass investigation and a reproducible record of what was measured, proposed, authorized, and concluded.

**The most convincing 30–90 seconds:** from the first deterministic plot/evidence event through the Skeptic proposal, Critic approval, targeted result, and READY_TO_LOCK state. It proves input → processing → adaptive decision → useful output without requiring judges to understand the underlying science.

### E5 — 3-Minute Video Demo — 10 Points

- **Where is the API run shown?** 0:43–2:15, beginning with `Start blind investigation` on `TARGET-C11`.
- **Where is architecture shown?** 2:15–2:35 using a cropped architecture/harness view.
- **Where is the inference/API pipeline explained?** 1:13–1:53 in the event trace, then summarized at 2:15–2:35.
- **Where does the judge see the result?** 1:53–2:15: an automatic match verdict, side-by-side interpretation, and optional period/detail comparison.

The script includes a short problem, clear solution, one end-to-end run, the adaptive wow moment, architecture, Featherless integration, impact, and a closing within 3:00. The application occupies the majority of the screen time.

### E6 — Documentation & Setup — 10 Points

| Requirement | Present? | Quality | Missing / Improvement Needed |
|---|---:|---|---|
| README | Yes | Strong | Replace `#demo` placeholder; ensure claims match the final clean commit and green checks. |
| Setup Instructions | Yes | Strong | Add an explicit “recording reset/rehearsal” command if one is created; otherwise current install/config/start/reproduce steps are clear. |
| Architecture Diagram | Yes—`assets/architecture.png`, `assets/harness.png` | Strong for README; medium for video | Create a readable 16:9 crop/overlay for the 20-second insert; current images are too wide/dense at normal video scale. |
| Citations | Yes | Strong | Preserve exact SHERLOCK/WATSON adaptation boundaries and NASA/MAST/Featherless/LangGraph links in the public submission. |

### PART E — Final Judging Strategy

#### Three Strongest Scoring Opportunities

1. **API & Compute Integration:** the six-role Featherless pipeline plus numerical science and review/authorization boundaries.
2. **Innovation & Approach:** viewer-visible truth with machine-enforced agent blindness and bounded evidence allocation make the project meaningfully different from a chat wrapper.
3. **Code Structure & Quality:** strong modular boundaries, typed contracts, explicit failure modes, durable state, and extensive tests.

#### Three Biggest Judging Risks

1. A provider/network failure could still disrupt a recording take, although three consecutive fresh C11 gates passed. Edit routine waiting out of the video and preserve one complete successful capture as the source take.
2. An older failed canary artifact may contradict newer passing gates if it is presented without context.
3. The hosted demo link is missing, and the architecture assets may be unreadable if inserted full-frame without cropping.

#### Highest-Priority Changes Before Recording

1. Keep the green frontend and focused viewer/privacy checks in the final verification record.
2. Preserve the three fresh C11 reports and contrasting B42 report as final-working-tree evidence; rerun only if configuration or inference code changes.
3. Rehearse the exact browser-visible C11 start → targeted agent review → automatic comparison sequence and mark clean edit points around routine loading.
4. Prepare a 16:9 crop or simplified overlay emphasizing viewer projection → UI/API → controller → Featherless roles / deterministic tools, with the catalog-to-agent isolation boundary visible.
5. Replace the README demo placeholder with the public demo/video URL and verify public access in a signed-out session.
6. Explain or suppress non-actionable FITS checksum warnings before using terminal footage; keep integrity failures visible.

## PART F — 3-Minute Script

| Time | Narration | Screen / Shot | User Action | Purpose |
|---|---|---|---|---|
| 0:00–0:10 | “What if AI agents could investigate a scientific dataset end to end, with every measurement linked to its source? This is ExoSwarm.” | **Slide 1 — Hook:** ExoSwarm title; one dataset/star icon feeding six small agent nodes. | Simple node pulse; no detailed text. | Create curiosity immediately. |
| 0:10–0:18 | “Computational research is fragmented across scripts, plots, and model outputs. Adding AI introduces another layer of decisions to trace.” | **Slide 2 — Problem:** three disconnected icons labeled `Scripts`, `Plots`, `Models` pointing into a decision trace. | One simple build animation. | Tell a broad, relatable research-software story. |
| 0:18–0:26 | “ExoSwarm is a multi-agent research harness: agents choose useful tests, deterministic code produces the facts, and every step remains auditable.” | **Slide 3 — Solution:** `Agents decide → Harness validates → Code measures → Evidence persists`. | Highlight the four steps from left to right. | Explain exactly what the project does. |
| 0:26–0:32 | “We built it with Next.js, FastAPI, Python science tools, and Featherless.ai powering six specialist agents.” | **Slide 4 — Stack:** four large icons/wordmarks only: Next.js, FastAPI, Python, Featherless.ai. | Quick fade between the four marks. | Answer the stack question without a dependency list. |
| 0:32–0:45 | “Now let’s run it. You can already see this is WASP-4 b and what the catalog says. The agents receive only TARGET-C11 and the current evidence packet.” | Cut into Mission Control on `TARGET-C11`, `WASP-4 b`, `API run`. | Click `Start blind investigation`. | Make the context boundary understandable immediately. |
| 0:45–1:05 | “ExoSwarm first searches the star’s brightness for a repeating dip, then checks whether something other than a planet could explain it. Each result is saved, so we can follow exactly how it reaches its conclusion.” | Agent/tool trace advances, plots change, and completed results appear. | Jump-cut routine loading while preserving event order. | Explain the analysis in plain language. |
| 1:05–1:23 | “Now the agent team takes over. Four specialist roles receive compact evidence packets keyed by the opaque target ID and return structured decisions through Featherless.ai.” | Observer, Signal, Transit Hunter, and Director handoffs; brief provider/model telemetry crop. | Expand one decision only if legible. | Make the sponsor integration and agent flow visible. |
| 1:23–1:48 | “Here’s the agentic moment. The Skeptic finds an unresolved question and requests one targeted follow-up. Before any compute runs, an independent Critic checks that it is useful, affordable, and not redundant. The harness approves it, then deterministic code executes it.” | Skeptic proposal → budget → Critic `APPROVE` → tool execution → new evidence. | Preserve event order; cut only waiting. | Deliver the main wow moment. |
| 1:48–2:15 | “The comparison now appears: the agents matched the catalog’s broad conclusion. The planet-like interpretation survives the implemented checks, and the measured period aligns with the official value. The detailed evidence is one click away.” | Automatic `MATCH` result → side-by-side interpretation and period → briefly expand details. | No commit/reveal clicks; hold the verdict, optionally open details. | Deliver the aha moment without interrupting momentum. |
| 2:15–2:32 | “Behind the UI, FastAPI keeps the viewer reference separate while coordinating six Featherless-powered roles, allowlisted compute tools, durable evidence, and bounded recovery.” | Simplified five-node architecture crop with viewer/agent isolation. | Animate one clean left-to-right flow. | Reinforce technical execution without repeating the stack slide. |
| 2:32–2:49 | “For computational research, this means agentic orchestration without surrendering control. Models decide where to look, tested code produces the facts, and researchers can inspect every step.” | Trace/evidence/receipt composite with `AGENTS DECIDE`, `CODE MEASURES`, `EVIDENCE PERSISTS`. | No action. | Connect the product to the chosen theme. |
| 2:49–3:00 | “ExoSwarm gives AI agents a bounded research workflow—built to investigate, challenge, and leave every decision open to review.” | Clean end card with product, repository, and demo URL. | Hold for readability. | Memorable close. |

## PART G — Narration-Only Script

What if AI agents could investigate a scientific dataset end to end, with every measurement linked to its source? This is ExoSwarm.

Computational research is fragmented across scripts, plots, and model outputs. Adding AI introduces another layer of decisions to trace.

ExoSwarm is a multi-agent research harness: agents choose useful tests, deterministic code produces the facts, and every step remains auditable.

We built it with Next.js, FastAPI, Python science tools, and Featherless.ai powering six specialist agents.

Now let’s run it. You can already see this is WASP-4 b and what the catalog says. The agents receive only TARGET-C11 and the current evidence packet.

ExoSwarm first searches the star’s brightness for a repeating dip, then checks whether something other than a planet could explain it. Each result is saved, so we can follow exactly how it reaches its conclusion.

Now the agent team takes over. Four specialist roles receive compact evidence packets keyed by the opaque target ID and return structured decisions through Featherless.ai.

Here’s the agentic moment. The Skeptic finds an unresolved question and requests one targeted follow-up. Before any compute runs, an independent Critic checks that it is useful, affordable, and not redundant. The harness approves it, then deterministic code executes it.

The comparison now appears: the agents matched the catalog’s broad conclusion. The planet-like interpretation survives the implemented checks, and the measured period aligns with the official value. The detailed evidence is one click away.

Behind the UI, FastAPI keeps the viewer reference separate while coordinating six Featherless-powered roles, allowlisted compute tools, durable evidence, and bounded recovery.

For computational research, this means agentic orchestration without surrendering control. Models decide where to look, tested code produces the facts, and researchers can inspect every step.

ExoSwarm gives AI agents a bounded research workflow—built to investigate, challenge, and leave every decision open to review.

## PART H — Recording Shot List

### Shot 1 — Hook

**Duration:** 0:00–0:12  
**Screen:** Mission Control launchpad, ExoSwarm branding, viewer-visible identities.  
**Action:** None; slow editorial zoom toward C11.  
**Narration:** First paragraph of Part G.  
**Preparation:** C11 selected, `API run` badge visible, no stale error banner.

### Shot 2 — Problem and Solution

**Duration:** 0:12–0:43  
**Screen:** Fast montage of plot, agent trace, Evidence Ledger, and `Agents receive TARGET-C11 only`, then full launchpad.  
**Action:** Use editorial punch-ins; keep cursor movement minimal.  
**Narration:** Paragraphs two and three.  
**Preparation:** Rehearse crop coordinates so text remains readable at 1080p.

### Shot 3 — Start API Investigation

**Duration:** 0:43–0:55  
**Screen:** C11 row and `Start blind investigation`.  
**Action:** Click once.  
**Narration:** Paragraph four.  
**Expected result:** Mission Control enters running state and begins receiving backend events.

### Shot 4 — Deterministic Baseline

**Duration:** 0:55–1:13  
**Screen:** Scientific plots, tool events, and Evidence Ledger with a small `API RUN` callout.  
**Action:** Mostly hands-off; select one plot only if it does not obscure streaming.  
**Narration:** Paragraph five.  
**Expected result:** The repeating signal is found, the follow-up checks complete, and their results appear. Do not explain each scientific method.

### Shot 5 — Structured Role Briefing

**Duration:** 1:13–1:32  
**Screen:** Observer, Signal, Transit Hunter, and Director checkpoints plus a short Featherless/model telemetry crop.  
**Action:** Optionally expand one role decision.  
**Narration:** Paragraph six.  
**Expected result:** Role completion, evidence references, provider/model or validation metadata are visible.

### Shot 6 — Skeptic and Critic

**Duration:** 1:32–1:53  
**Screen:** Targeted follow-up proposal, one-unit cost, Critic verdict, tool start/completion.  
**Action:** None; preserve continuity.  
**Narration:** Paragraph seven.  
**Expected result:** `APPROVE` followed by new deterministic evidence. The audience only needs to understand that the agent found a useful unresolved question.

### Shot 7 — Automatic Comparison

**Duration:** 1:53–2:15  
**Screen:** Automatic `MATCH` verdict, agent/catalog interpretation, and period comparison.  
**Action:** Hold on the verdict; optionally expand `Why the agents reached this result`.  
**Narration:** Paragraph eight.  
**Expected result:** A non-scientist can immediately tell that the independent result agrees with WASP-4 b's catalog record.

### Shot 8 — Architecture

**Duration:** 2:15–2:35  
**Screen:** Cropped `assets/architecture.png` or `assets/harness.png`: viewer projection, UI/API, controller, Featherless roles, and deterministic tools.  
**Action:** Add four simple highlight pulses or pans during editing.  
**Narration:** Paragraph nine.  
**Preparation:** Export a readable 16:9 crop; do not show the full ultra-wide image scaled to fit.

### Shot 9 — Impact and Close

**Duration:** 2:35–3:00  
**Screen:** Comparison verdict and trace composite, then clean end card with public links.  
**Action:** None.  
**Narration:** Final two paragraphs.  
**Preparation:** Replace placeholder URLs before export and hold the end card for at least three seconds.

### Editing and Style Direction

- Open directly on the product—no team-introduction slide and no astronomy lecture.
- Use short, high-contrast callouts tied to visible state: `API RUN`, `OPAQUE TARGET`, `AGENT PROPOSAL`, `HARNESS VALIDATION`, `PYTHON TOOL`, `MATCH`.
- Treat the Skeptic → Critic → tool sequence like the hero moment: quick punch-ins, one restrained approval sound, then a visual pulse when new evidence lands.
- Cut all routine loading. Preserve chronological order and add a small `waiting removed` caption once to make the edit clear.
- Use the automatic verdict as the cinematic payoff: let the run finish, cut directly to `MATCH`, then briefly expose the side-by-side measurements.
- Keep the architecture insert to five ideas and 20 seconds. Animate the flow; do not display a dense static diagram and expect judges to read it.
- Favor concrete software language in captions: **multi-agent research harness**, **bounded autonomy**, **structured outputs**, **event stream**, **controller authority**, **evidence ledger**, **agent-context isolation**.
- Do not stack all keywords at once. Each term should appear only when the corresponding state is on screen.

## PART I — Pre-Recording Setup

1. Rerun backend tests, frontend tests, lint, typecheck, and build after any final code change.
2. From the repository root, verify the cached deterministic safety path with `uv run --project apps/api --extra science python scripts/reproduce.py`.
3. Confirm `.env` has a valid `FEATHERLESS_API_KEY`, the intended Featherless base URL/model, multi-agent enabled, and specialist advisory enabled. Never show the key on screen.
4. The current preflight and three C11 gates are green. Rerun them only if model, prompt, inference, controller, or environment configuration changes; preserve the reports under `evals/`.
5. Rehearse the exact judged path from a fresh UI selection and identify edit points after Start, mandatory evidence, role briefing, Critic verdict, tool completion, and READY_TO_LOCK. Capture a complete source take even though routine loading will be cut.
6. Start the backend in Terminal 1 with `uv run --project apps/api --extra science --extra agents uvicorn exoswarm.api.app:app --reload --port 8000`.
7. Start the frontend in Terminal 2 with `pnpm --dir apps/web dev`. Keep `NEXT_PUBLIC_EXOSWARM_DATA_MODE` unset or `live`; do not accidentally build/record fixture mode.
8. Verify `http://localhost:8000/health` and ensure the target list reports C11 available before opening the recording composition.
9. Use one API process for the configured runs directory. Start a new run rather than reusing a previous run.
10. Open Mission Control at the target-selection state with C11 selected, `WASP-4 b`, `confirmed planet`, `API run`, and no error banners.
11. Keep a cached reproduction terminal ready as a recovery path. If the provider fails, restart the take; label any recorded-scenario footage with its on-screen mode.
12. Prepare a readable 16:9 architecture crop and an end card with the final public repository, demo, and Devpost URLs.
13. Record at 1440p or clean 1080p, set browser zoom so trace text is readable, hide bookmarks/personal tabs, disable notifications, and close unrelated terminals.
14. Keep the cursor parked away from measurements during hands-off processing. The only required demo click is Start; details are optional.
15. Record narration separately. Cut routine loading freely, but retain chronological cause and effect and hold the proposal, verdict, and comparison long enough to read. A subtle jump cut or “waiting removed” caption keeps the edit transparent.

### Fast Recovery Plan

- **Provider timeout before meaningful role activity:** stop the take, preserve the visible failure trace if useful, verify provider status/preflight, and start a fresh run.
- **Backend refresh/restart:** use the run resume path only if rehearsed; otherwise restart the take with a new run ID.
- **Frontend refresh:** the live hook should reload durable state; confirm this in rehearsal before relying on it during recording.
- **Provider or API becomes unstable:** use a complete successful source take captured during rehearsal. If recorded-scenario mode is shown, retain its on-screen mode label.

## PART J — Features We Should NOT Spend Demo Time On

- **Multiple target tours:** C11 alone carries the complete story. A second target dilutes the three-minute arc.
- **Recorded-scenario controls:** useful for fallback and regression, but unnecessary in the primary API-run footage.
- **Centroid localization:** explicitly unavailable; showing or implying it would be inaccurate.
- **Full API docs or raw JSON artifacts:** valuable repository evidence, poor primary video footage. Use only a one-second inset if needed.
- **Install steps, environment variables, Docker, or CI screens:** documentation criteria are better proved in the repository.
- **Every role output:** show the role flow, then focus on Skeptic and Critic. Reading six briefs becomes a feature inventory.
- **Every scientific plot mode:** show enough to establish deterministic evidence, then stay with the adaptive decision.
- **Download artifact metadata:** less direct than the on-screen ledger and automatic comparison.
- **3D orbit animation as a feature:** it can remain visual atmosphere, but it is not scientific evidence or the core differentiator.
- **Authentication, databases, scaling, or live NASA fetching:** these are not implemented and are intentionally outside scope.
- **Planet “confirmation” language:** ExoSwarm performs photometric vetting. The confirmed status belongs to the external viewer catalog, not the agents.
- **Scientific method names and transit theory:** do not explain BLS, odd/even checks, secondary eclipses, or harmonics. Call them baseline checks and a targeted follow-up; the demo is about research software and agent orchestration.
- **Benchmark inventory:** five cached TESS cases and 24 adversarial scenarios strengthen the write-up, but should not consume demo time.

## PART K — Missing Information

### Critical Missing Information

- Final public hosted-demo URL and whether it will be available to judges without local setup.
- Final public repository URL/branch/commit to use in the end card and Devpost submission.
- Whether hackathon rules require a particular Featherless logo, sponsor wording, or an explicit on-screen provider identifier beyond narration and telemetry.
- Three-run timing/reliability evidence for the exact browser-based C11 path; only backend provider-gate timings and non-browser verification were available here.
- Confirmation that the final recording environment shows provider/model/schema/latency telemetry legibly enough for judges.

### Optional Missing Information

- Presenter/team name and whether a very short spoken credit is desired; the current script intentionally skips introductions.
- Preferred pronunciation and conversational wording for `TESS`, `WASP-4 b`, `BLS`, and `SHA-256`.
- Desired final call to action: try the demo, inspect the repository, or discuss the reusable controlled-agent architecture.
- Music, captions, brand colors, and whether narration will be live or recorded separately.
- Whether the final video can use a brief edited zoom/crop of the existing architecture assets.

## Final Quality Test

| Category | Score | Reason |
|---|---:|---|
| Problem clarity | 9/10 | False positives and untrustworthy model-only judgment are explained in under 30 seconds. |
| Solution clarity | 9/10 | The judgment/authority split is stated before the demo and then shown. |
| Product visibility | 9/10 | More than half the video is one Mission Control workflow. |
| Demo coherence | 9/10 | One target connects action, processing, adaptive choice, result, and automatic comparison. |
| Technical credibility | 9/10 | Concrete provider, schemas, controller, tools, ledgers, and isolation tests are visible and evidence-backed. |
| Innovation visibility | 9/10 | Skeptic/Critic review and viewer/agent separation distinguish the product from a chat wrapper. |
| Real-world value | 8/10 | The researcher benefit is clear without overclaiming confirmation or accuracy. |
| Judging alignment | 9/10 | All six official criteria are mapped; the video prioritizes execution and integration. |
| Memorability | 9/10 | “You can see the answer; the agents cannot” provides a simple, visual payoff. |
| Timing discipline | 9/10 | Script ends at 3:00 and leaves the product 92 seconds; routine loading is explicitly removed in edit while evidence order remains intact. |

### Judge-Perspective Check

- **What did they build?** A blind, auditable AI-assisted TESS signal-vetting system.
- **What problem does it solve?** It tests planet-like dips against false-positive explanations without trusting model-generated measurements.
- **Who would use it?** Researchers/analysts vetting candidate signals; engineers can reuse the bounded-agent pattern.
- **Did I see it working?** The planned footage shows an API target run, streamed evidence, adaptive action, result, lock, and reveal.
- **What is technically interesting?** Six-role structured inference, independent review, deterministic tools, durable state, budgets, and a gated hash protocol.
- **Why is it different?** Models choose bounded evidence-gathering actions but cannot calculate science, authorize tools, or see the answer key.
- **Why does it matter?** The result is easier to inspect, reproduce, and trust.
- **How does it meet the criteria?** The official 60-point mapping in Part E ties repository and video evidence to every scored item.
