---
name: reference-exoplanet-projects
description: Route ExoSwarm science-tool, investigation-harness, and agent-evaluation work to the relevant indexed parts of SHERLOCK/WATSON, ASTER, or Stargazer. Use before researching or borrowing upstream exoplanet code, algorithms, tool patterns, fixtures, blinding, task banks, traces, or evaluation ideas; use when a task mentions any of these projects or when an implementation would otherwise require searching their repositories.
---

# Reference Exoplanet Projects

Use these projects as advisory references, never as ExoSwarm requirements. Repository contracts remain authoritative in the order defined by `AGENTS.md`.

## Route the task

| ExoSwarm task | Primary reference | Read |
|---|---|---|
| TESS/Kepler acquisition, light-curve cleanup, detrending, BLS/TLS search, candidate selection, harmonic checks | SHERLOCK | `references/sherlock-watson.md` |
| Odd/even depths, secondary-event checks, centroid/source localization, difference images, contamination diagnostics | WATSON within the SHERLOCK ecosystem | `references/sherlock-watson.md` |
| Agent tool lifecycle, typed tool ergonomics, hooks, recovery messages, cost/context controls | ASTER | `references/aster.md` |
| Scenario banks, synthetic and cached-real evals, hidden truth, deterministic graders, baselines, traces, timeouts | Stargazer | `references/stargazer.md` |
| A cross-cutting design or uncertainty about what can be adopted | Compare all three | `references/adoption-matrix.md`, then only the relevant project file |

Use the narrow ExoSwarm implementation skill as well. This skill locates upstream ideas; it does not replace `implement-science-tool`, `validate-science`, `engineer-agent-harness`, or `evaluate-agent-system`.

## Apply a reference safely

1. Write the ExoSwarm contract first: inputs, outputs, units, errors, provenance, state changes, and acceptance checks.
2. Classify what is being borrowed as an algorithm, interface, architecture pattern, test fixture pattern, or evaluation pattern.
3. Open the indexed file and symbol at the pinned commit. Search upstream only if the index lacks the needed detail.
4. Check the upstream license and record the repository, commit, path, and idea in the implementation note or PR description.
5. Re-express the smallest useful idea behind ExoSwarm's typed boundary. Do not import a whole pipeline or add an upstream dependency by default.
6. Validate scientific behavior independently with controlled fixtures and official library/documentation conventions. Upstream output is comparison evidence, not ground truth.
7. Preserve ExoSwarm's lock boundary: no catalog identity or hidden answer enters agent-visible state before a result is locked.

If network access is available and exact behavior matters, compare the pinned commit with current upstream HEAD. If it changed, inspect the diff and update this index in the same change; do not silently mix versions.

## Non-negotiable filters

- Deterministic Python owns numerical measurements; never ask a model to reproduce an upstream numerical method from prose or plots.
- Mandatory diagnostics remain explicit code paths. An upstream agent's freedom does not expand ExoSwarm tool permissions.
- Do not copy placeholder or fabricated metrics. SHERLOCK's current BLS path contains explicit zero-valued placeholders; see its warnings.
- Do not adopt ASTER's broad shell, filesystem, Python, or web access.
- Do not expose Stargazer-style truth-derived feedback during an investigation. Run truth comparison only after ExoSwarm's result lock.
- Do not treat plots, report generators, mutable result carriers, prompts, or conversation history as scientific state.
- Never change scope merely to match an upstream project. ExoSwarm intentionally implements a smaller bounded surface.

## Produce a reference note

When a reference materially influences implementation, leave a concise note containing:

```text
Reference: <project>@<commit> <path>::<symbol>
Borrowed: <algorithm/interface/pattern>
Adapted: <how it fits ExoSwarm contracts and lock boundary>
Verified: <independent tests, fixtures, units, and tolerances>
Not adopted: <important upstream behavior intentionally excluded>
```

Do not paste large upstream excerpts into repository docs. Link to the pinned source and describe the idea.
