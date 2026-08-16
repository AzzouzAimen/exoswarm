# Data boundary

`cached/` contains the versioned TESS light curves used by offline reproduction and evaluation;
`cached/tpf/` is reserved for Target Pixel Files. `targets/` contains agent-safe opaque manifests.
Identity mappings, acquisition provenance, and catalog references live under `ground_truth/` and
remain outside investigation state, agent context, and agent-safe events. A separate read-only
viewer projection may expose catalog references to humans. Scientific fixtures are reserved for
controlled test inputs and outcomes.
