# Cached TESS Candidate Vertical Slice

## Contract

The `search_bls` scientific action accepts one local SPOC-like TESS light-curve FITS product and
caller-owned run artifact and Evidence Ledger paths. It never contacts MAST. The FITS contract
requires `TIME`, `PDCSAP_FLUX`, `PDCSAP_FLUX_ERR`, and `QUALITY`, explicit day/TDB/BTJD metadata,
sector, cadence, and a declared flux unit.

The action applies the Lightkurve TESS default quality-bitmask convention (175), finite/error
filtering, positive-impulse rejection, median detrending, Astropy unit-aware Box Least Squares,
and phase folding. It returns period in days, epoch in BTJD/TDB, duration in hours, depth as a
relative-flux fraction, and dimensionless depth SNR. BLS depth error is the only statistical
uncertainty currently reported; grid/cadence tolerances are labeled as tolerances rather than
uncertainties.

The content SHA-256 identifies the source in agent-visible evidence. Recognizable FITS target
headers and the local source path are deliberately excluded. Processing masks, arrays, periodogram,
configuration, versions, and phase fold are stored in a deterministic JSON artifact referenced by
the typed result and append-only Evidence Ledger record.

## Upstream reference note

Reference: [SHERLOCK](https://github.com/franpoz/SHERLOCK) (MIT) at
`a42e2025c521572b79f0add0a6f135b2df84aabc`,
`sherlockpipe/search/sherlock.py::Sherlock.__prepare/__detrend/__identify_signals` and
`sherlockpipe/search/BlsSearcher.py::BlsSearcher.search`.

Borrowed: pipeline stage ordering, explicit preprocessing choices, BLS candidate extraction, and
checking half/same/double-period trials.

Adapted: stages are pure deterministic Python behind ExoSwarm's strict result/provenance boundary;
cached content is addressed by hash and catalog identity remains outside evidence.

Verified: controlled injected, negative, harmonic-relation, preprocessing-sensitivity,
unit/convention, determinism, malformed-input, and append-only ledger tests use Astropy outputs and
declared tolerances as authority.

Not adopted: SHERLOCK orchestration, mutable result carriers, plots/reports/catalog coupling,
multiple detrenders/search engines, placeholder false-alarm/odd-even/depth-error metrics, and its
approximate radius-ratio calculation.

## Pending cached-real acceptance artifact

The repository currently has no real file under `data/cached/lightcurves/`. The remaining gate needs
one unmodified local SPOC TESS light-curve FITS product with the required columns/metadata/checksums
and documented acquisition provenance, plus `evals/fixtures/cached_real_tess_case.json`:

```json
{
  "opaque_target_id": "TARGET-...",
  "cached_path": "data/cached/lightcurves/<cached-product>.fits",
  "search": {},
  "expected": {
    "period_days_min": "<independently-set numeric lower bound>",
    "period_days_max": "<independently-set numeric upper bound>"
  }
}
```

The expected range must be set from independent documentation before this implementation's output
is evaluated. Recognizable identity and catalog truth stay backend-only.
