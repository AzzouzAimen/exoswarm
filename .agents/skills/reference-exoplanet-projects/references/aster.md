# ASTER Index

## Contents

- [Snapshot and role](#snapshot-and-role)
- [Code map](#code-map)
- [Patterns worth adapting](#patterns-worth-adapting)
- [ExoSwarm translation](#exoswarm-translation)
- [Do not adopt](#do-not-adopt)

## Snapshot and role

- Repository: <https://github.com/emipanek/aster>
- Paper: <https://arxiv.org/html/2603.26953>
- Indexed commit: `9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe`
- License status: no repository code license file was located at the indexed commit. The paper's license does not automatically license the repository code. Use concepts and citations only unless an explicit code license or permission is later established.

ASTER is an atmospheric-analysis agent, not a transit-search implementation. Use it to study the boundary around scientific tools: how tools are assembled, described to a model, executed outside the model, hooked, reported, and recovered. It is not a source for BLS, TESS preprocessing, or ExoSwarm's multi-role investigation rules.

## Code map

| Concern | Pinned path / symbol | What to study | ExoSwarm caveat |
|---|---|---|---|
| Runtime assembly | [`run_aster.py`](https://github.com/emipanek/aster/blob/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe/run_aster.py) | One place assembling tools, hooks, model configuration, workspace, and agent | Its tool set is intentionally much broader than ExoSwarm's |
| Agent instructions | [`aster_system_prompt.md`](https://github.com/emipanek/aster/blob/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe/aster_system_prompt.md) | Domain conventions, workflow hints, tool-selection guidance | Move units, permissions, and invariants into schemas/validators rather than prompt-only rules |
| NASA Archive queries | [`aster_toolkit/data_acquisition/exoarchive.py::GetExoplanetParameters`, `FindExoplanetsByCondition`, `DownloadDataset`](https://github.com/emipanek/aster/blob/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe/aster_toolkit/data_acquisition/exoarchive.py) | Focused action names, type/docstring-driven arguments, result/error messaging | ExoSwarm's catalog and target identity remain locked; live queries are outside the cached core path |
| Deterministic model wrapper | [`aster_toolkit/taurex/forward_model.py::RunTaurexTransmissionModelTool`](https://github.com/emipanek/aster/blob/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe/aster_toolkit/taurex/forward_model.py) | Thin agent-facing wrapper around deterministic computation | Return typed evidence rather than conversation-oriented strings |
| Long-running computation | [`aster_toolkit/taurex/retrieval.py::SimulateTaurexRetrieval`](https://github.com/emipanek/aster/blob/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe/aster_toolkit/taurex/retrieval.py) | Parameter validation, defaults, progress/error handling | ExoSwarm tools need explicit budgets, idempotency, and durable terminal records |
| Generated parameter files | [`aster_toolkit/taurex/parfile_tools.py::WriteTaurexParameterFile`](https://github.com/emipanek/aster/blob/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe/aster_toolkit/taurex/parfile_tools.py) | Separating configuration construction from execution | Prefer typed local configuration; do not make text files the authority |
| Tool organization | [`aster_toolkit/`](https://github.com/emipanek/aster/tree/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe/aster_toolkit) | Grouping tools by scientific capability | ExoSwarm additionally separates domain, science, investigation, agents, evidence, and security boundaries |
| Procedural guidance | [`workspace/skills/`](https://github.com/emipanek/aster/tree/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe/workspace/skills) | Just-in-time task guidance adjacent to tools | Skills guide reasoning; machine validators remain authoritative |

## Patterns worth adapting

The paper describes an explicit cycle: assemble context, call the model, validate tool arguments, run pre-hooks, execute outside the model, run post-hooks, append results, and continue. Useful ExoSwarm adaptations include:

- tool schemas derived from a single typed implementation contract;
- concise errors that say what failed, whether retry is safe, and what valid correction looks like;
- pre-execution permission and argument checks;
- post-execution normalization, provenance capture, and artifact registration;
- persistent context that keeps tool calls paired with results;
- token, cost, iteration, and wall-time accounting with hard ceilings;
- explicit approval hooks for consequential actions.

These overlap with ExoSwarm's `engineer-agent-harness`, `engineer-agent-loop`, `engineer-agent-context`, and `design-agent-tools` skills. Those local skills decide the design; ASTER supplies examples.

## ExoSwarm translation

| ASTER idea | Translate to ExoSwarm as |
|---|---|
| General scientific tools available to one agent | Role- and state-scoped actions from a bounded registry |
| Tool result added to conversation | Typed `EvidenceRecord` persisted before the next inference |
| Tool docstring carries domain rules | Schema plus deterministic validator; prompt contains only concise usage guidance |
| Safety hook around commands | Permission policy before every action and Critic approval where required |
| Persistent conversation/workspace | Reconstructible investigation state plus append-only audit events |
| Cost-aware model operation | Per-investigation budgets and terminal reasons |
| Retrieval of known planet parameters | Backend-only catalog access after result lock, never an investigative shortcut |

## Do not adopt

- `RunCommandTool`, arbitrary Python, broad filesystem editing, or general web search as agent actions.
- Multiple model providers in the 48-hour core.
- Conversation history or generated files as the authoritative state store.
- Prompt-only enforcement of units, safe paths, phase conventions, or allowed parameter ranges.
- Direct NASA Archive/catalog access before the result lock.
- Atmospheric retrieval and TauREx/FastChem functionality; it is outside ExoSwarm's initial transit scope.
- ASTER source code itself while its repository lacks an explicit code license.
