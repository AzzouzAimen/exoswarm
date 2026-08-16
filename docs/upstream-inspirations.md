# Upstream Inspirations and Attribution

ExoSwarm is an independent implementation. It does not import SHERLOCK, WATSON, ASTER, or
Stargazer at runtime. These projects were reviewed as advisory references at the pinned commits
below; ExoSwarm's repository contracts, deterministic tests, and lock boundary remained
authoritative.

## Reference and adoption record

| Project | Pinned reference | Influence on ExoSwarm | Adaptation and verification | Not adopted |
|---|---|---|---|---|
| SHERLOCK | [`franpoz/SHERLOCK@a42e202`](https://github.com/franpoz/SHERLOCK/tree/a42e2025c521572b79f0add0a6f135b2df84aabc), MIT; [Dévora-Pajares et al. (2024)](https://doi.org/10.1093/mnras/stae1740) | Algorithm reference for pipeline stage ordering, preprocessing choices, BLS candidate extraction, and half/same/double-period trials. | Re-expressed as deterministic typed Python with explicit units, provenance, content hashes, and controlled plus cached-real regression tests. See [scientific provenance](scientific-provenance.md). | Upstream orchestration, mutable result carriers, report/catalog coupling, multiple search engines, and placeholder metrics. |
| WATSON | [`PlanetHunters/watson@c8332b9`](https://github.com/planetHunters/watson/tree/c8332b9a77fcae2b56942def18ca3a0573b0a772), MIT | Algorithm reference for computing odd/even depths as a per-transit depth series rather than treating correlated in-transit cadences as independent. | Implemented as typed evidence with explicit units and tested against clean, mismatch, single-event-outlier, and cached-real cases. See [scientific provenance](scientific-provenance.md). | Plotting, report generation, allesfitter coupling, catalog-aware interpretation, and unsupported centroid claims. |
| ASTER | [`emipanek/aster@9eadc08`](https://github.com/emipanek/aster/tree/9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe); [Panek et al. (2026)](https://arxiv.org/abs/2603.26953). No repository code license was located at the reviewed commit. | Concept-level reference for scientific-tool lifecycle, typed tool descriptions, pre/post execution checks, recovery messages, and cost/context controls. | Translated into role- and state-scoped allowlists, strict schemas, persistent typed evidence, explicit retry policy, and hard budgets. Verified through tool-registry, authorization, recovery, context-isolation, and budget tests. | No source code was copied. ExoSwarm excludes arbitrary shell, filesystem, Python, and web tools; prompt-only enforcement; and agent access to catalogs. |
| Stargazer | [`AIPS-UofT/Stargazer@3f61766`](https://github.com/AIPS-UofT/Stargazer/tree/3f617667472061e253288c7b26f0e70f186f2dff), MIT code / CC BY 4.0 benchmark data; [Liu et al. (2026)](https://arxiv.org/abs/2604.15664) | Test-pattern reference for stable scenario banks, synthetic and cached-real cases, hidden truth, conjunctive graders, resource limits, durable traces, and explicit terminal failures. | Adapted to ExoSwarm-owned TESS fixtures and transit-specific criteria. Ground-truth comparison is a separate post-lock process, and tests enforce that the agent runtime cannot access it. See [testing and evaluation](testing-and-evaluation.md). | Radial-velocity numerical methods, upstream fixtures, arbitrary Python execution, scalar reward as scientific confidence, hidden chain-of-thought, and mid-investigation truth feedback. |

## Attribution policy

For scientific algorithms, upstream implementations are comparison evidence rather than numerical
authority. ExoSwarm validates behavior independently using controlled fixtures, cached public TESS
observations, official package conventions, explicit units, and declared tolerances.

For agent architecture and evaluation, ExoSwarm borrows patterns rather than code. Models remain
restricted to bounded proposals; application code authorizes execution; deterministic Python owns
measurements; and official catalog truth remains outside agent-visible state. These differences are
intentional, not omissions from the cited projects.

The references were indexed on 2026-08-15. Commit-pinned links make the reviewed source stable even
if an upstream default branch later changes.
