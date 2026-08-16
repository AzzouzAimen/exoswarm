# Cached TESS Candidate Vertical Slice

## Contract

The `search_bls` scientific action accepts one local SPOC-like TESS light-curve FITS product and
caller-owned run artifact and Evidence Ledger paths. It never contacts MAST. The FITS contract
requires `TIME`, `PDCSAP_FLUX`, `PDCSAP_FLUX_ERR`, and `QUALITY`, explicit day/TDB/BTJD metadata,
sector, cadence, and a declared flux unit.

Official SPOC products may encode the `TIME` column unit as `BJD - 2457000, days` (or the
documented `JD - 2457000, days`) while also declaring `TIMEUNIT=d`, `TIMESYS=TDB`, and the TESS
2457000.0 BJD reference. The loader normalizes those unambiguous official spellings to days.

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

## Cached-real acceptance artifact

The local acceptance case uses one unmodified public SPOC TESS light-curve FITS product with the
required columns, metadata, checksums, and documented acquisition provenance. The agent-safe
configuration is `evals/fixtures/cached_real_tess_case.json`:

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

The cached FITS and identity-bearing provenance remain ignored at `data/cached/lightcurves/` and
`data/ground_truth/`. `scripts/acquire_cached_tess.py` is the manually invoked, networked one-time
acquisition boundary; its exact invocation is stored only in the private provenance JSON. Normal
science execution and `make reproduce` read the opaque cached file and never contact MAST.

The selected official SPOC file is structurally valid but preserves extension-level `CHECKSUM`
values that Astropy reports as invalid through both tested official MAST delivery routes. The
acquisition record retains each embedded value and validity result plus a local SHA-256. Invalid
`DATASUM` values remain fatal; absent `DATASUM` keywords are recorded explicitly rather than
invented.

## Deterministic vetting pack

The accepted candidate artifact now feeds strict odd/even depth comparison, phase-window
secondary-eclipse search, fixed P/2-P-2P harmonic trials, and contamination screening. Each tool
returns measurements with units, method/provenance, warnings, typed negative/precondition outcomes,
and an `interpretation_code`; application code—not the model—maps those codes to disposition.

The odd/even diagnostic measures each transit event separately, combines event depths by parity,
and uses the larger of propagated reported-flux error and empirical event-depth standard error.
This prevents hundreds of correlated in-transit cadences from turning one anomalous event into a
decisive mismatch. Reference: WATSON@`c8332b9a77fcae2b56942def18ca3a0573b0a772`
`watson/watson.py::Watson.plot_transits_statistics` (MIT). Borrowed: the per-transit depth-series
pattern. Adapted: pure typed evidence with explicit units and no plotting/report dependency.
Verified: controlled mismatch, clean, single-event-outlier, and cached-real checks. Not adopted:
allesfitter coupling, plotting, report generation, or catalog-aware interpretation.

This is a stabilized regression fix, not unfinished statistical cleanup. Do not revert it to a
cadence-level comparison or formal flux-error-only uncertainty: those forms produced a false
odd/even rejection on the cached WASP-18 case because samples within one transit are correlated.
Change it only with a replacement controlled regression, cached-real evidence, explicit units, and
updated tolerances/provenance.

The controller derives the artifact path from committed same-run `search_bls` evidence and never
copies it into model parameters, decisions, state, or public events. Cached-neighbor contamination
is preferred when available. The current cached-real case falls back to official SPOC `CROWDSAP`
and labels that result as an aggregate aperture-contamination capacity check with no source or
centroid localization claim.
