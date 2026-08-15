# Backend-only ground truth

Recognizable target mappings and catalog truth are locked backend authority. Do not import this
directory from `exoswarm.agents`, serialize it into agent context, or expose it through pre-lock API
and SSE payloads.

The committed acquisition records document source URLs, checksums, release metadata, and expected
values recorded before evaluation for the three fixed cached TESS cases. `catalog_reveal.json` is
read only by the backend reveal authority after the exact locked-result hash is reverified.
