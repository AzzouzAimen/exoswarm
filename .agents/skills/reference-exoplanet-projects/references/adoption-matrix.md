# Adoption Matrix

## Contents

- [Decision summary](#decision-summary)
- [Capability matrix](#capability-matrix)
- [Adoption levels](#adoption-levels)
- [Cross-project workflow](#cross-project-workflow)
- [Update policy](#update-policy)

## Decision summary

Choose by the kind of uncertainty:

- Choose **SHERLOCK/WATSON** when the uncertainty is *how deterministic transit-search or vetting code is conventionally organized*.
- Choose **ASTER** when the uncertainty is *how an LLM-facing scientific tool is described, executed, observed, or recovered*.
- Choose **Stargazer** when the uncertainty is *how to prove that an agent loop works across locked, repeatable scenarios*.
- Use official astronomy package documentation and literature as numerical authority even when SHERLOCK/WATSON supplies the starting implementation idea.

## Capability matrix

| Capability | SHERLOCK / WATSON | ASTER | Stargazer | ExoSwarm decision |
|---|---:|---:|---:|---|
| TESS light-curve preparation | High | None | None | Study SHERLOCK; implement a smaller typed function |
| BLS/TLS transit search | High | None | None | Start with BLS; independently validate formulas and units |
| Candidate ranking and harmonics | High | None | Low | Borrow bounded strategies, not the full configurable selector system |
| Odd/even and secondary checks | High through WATSON | None | None | Extract deterministic measurements from report-oriented code |
| Centroid/difference-image vetting | High through WATSON | None | None | Use cached TPF fixtures; preserve provenance and units |
| Agent/tool architecture | Low | High | Medium | Prefer ExoSwarm harness contracts; borrow ASTER ergonomics only |
| Scientific agent loop | Low | High | High | Keep ExoSwarm's explicit bounded loop and action registry |
| Hidden-truth benchmark | None | Low | High | Adapt Stargazer's task-bank separation; evaluate post-lock only |
| Baselines and trajectory traces | Low | Medium | High | Use deterministic baselines plus trace-level metrics |
| Hard timeout and batch resilience | Low | Medium | High | Adopt watchdog/terminal-reason concepts, not code wholesale |
| Licensing confidence at indexed snapshot | MIT | No repository code license located | MIT code; CC BY 4.0 benchmark data | Do not copy ASTER code unless licensing is clarified |

## Adoption levels

Use one of these levels explicitly:

1. **Concept only** — learn a boundary or workflow, then design it against ExoSwarm contracts. Default for ASTER.
2. **Algorithm reference** — inspect equations and data flow, then independently implement and test. Default for SHERLOCK/WATSON science.
3. **Test-pattern reference** — reproduce the shape of fixtures, cases, and graders with ExoSwarm-owned data. Default for Stargazer.
4. **Direct dependency** — requires a concrete justification covering maintenance, transitive cost, API stability, license, and why a thin local implementation is worse. This is never the default.

Copying a function is not an adoption level. If licensed code is copied or modified, preserve notices and record provenance according to the license; otherwise reimplement the idea independently.

## Cross-project workflow

For a feature such as `odd_even_test()`:

1. Read `sherlock-watson.md` for the scientific measurement and fixture locations.
2. Read ASTER only if the function is becoming an agent-facing tool and its schema/error contract needs study.
3. Read Stargazer only when adding scenario coverage, a baseline, or trajectory grading.
4. Apply the corresponding ExoSwarm skills in order: numerical implementation, science validation, tool design, then agent evaluation.

For a harness-only feature such as retries or trace persistence, do not load SHERLOCK/WATSON. Use ASTER for lifecycle ideas and Stargazer for failure/evaluation patterns.

## Update policy

This index was researched on 2026-08-15 against:

| Project | Repository | Indexed commit |
|---|---|---|
| SHERLOCK | `franpoz/SHERLOCK` | `a42e2025c521572b79f0add0a6f135b2df84aabc` |
| WATSON companion | `PlanetHunters/watson` | `c8332b9a77fcae2b56942def18ca3a0573b0a772` |
| ASTER | `emipanek/aster` | `9eadc08ec5cf7b0065e0f63e8fbb949b7e68adfe` |
| Stargazer | `AIPS-UofT/Stargazer` | `3f617667472061e253288c7b26f0e70f186f2dff` |

When updating, preserve the old commit in git history, inspect upstream license changes, retest any adopted behavior, and update paths/symbols here only after verifying them at the new commit.
