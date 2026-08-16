# Backend-only ground truth

Recognizable target mappings and catalog truth are backend authority. They are never imported by
`exoswarm.agents` or serialized into investigation state, agent context, agent-safe API payloads, or
SSE events. The separate `/api/viewer/targets` projection intentionally exposes catalog references
to humans without attaching them to the investigation.

The committed acquisition records document source URLs, checksums, release metadata, and expected
values recorded before evaluation for the five fixed cached TESS cases. `catalog_reveal.json`
supplies the read-only viewer projection and the separate audit comparison. The audit path may
create `reveal.json` only after the exact locked-result hash is reverified.
