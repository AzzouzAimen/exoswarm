# SHERLOCK and WATSON Index

## Contents

- [Snapshot and role](#snapshot-and-role)
- [SHERLOCK code map](#sherlock-code-map)
- [WATSON code map](#watson-code-map)
- [Scientific cautions](#scientific-cautions)
- [Suggested ExoSwarm mapping](#suggested-exoswarm-mapping)
- [Tests and fixtures](#tests-and-fixtures)
- [Do not adopt](#do-not-adopt)

## Snapshot and role

- SHERLOCK repository: <https://github.com/franpoz/SHERLOCK>, MIT, indexed at `a42e2025c521572b79f0add0a6f135b2df84aabc`.
- SHERLOCK search documentation: <https://sherlockpipe.readthedocs.io/en/stable/search-proc.html>.
- WATSON repository: <https://github.com/PlanetHunters/watson>, MIT, indexed at `c8332b9a77fcae2b56942def18ca3a0573b0a772`.

SHERLOCK is the primary reference for deterministic light-curve preparation, transit search, candidate selection, and harmonic handling. WATSON is its focused vetting companion and is the better starting point for odd/even, secondary-event, centroid, difference-image, source-offset, and optical-ghost diagnostics.

Read these projects as mature pipeline case studies. ExoSwarm needs a small set of pure, typed measurements rather than their end-to-end workflow, plotting, reporting, catalogs, and broad configuration.

## SHERLOCK code map

All links below are pinned to the indexed commit.

| ExoSwarm concern | Upstream path and symbol | What to study | Caveat |
|---|---|---|---|
| Search interface | [`sherlockpipe/search/Searcher.py::Searcher.search`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/search/Searcher.py) | Common inputs and separation between search engines | Interface is pipeline-shaped and returns a mutable result carrier |
| BLS search | [`sherlockpipe/search/BlsSearcher.py::BlsSearcher.search`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/search/BlsSearcher.py) | Period grid, Lightkurve BLS invocation, candidate extraction, transit masks | Several metrics are placeholders or crude estimates; see cautions |
| TLS comparison | [`sherlockpipe/search/TlsSearcher.py::TlsSearcher.search`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/search/TlsSearcher.py) | How a second search backend fits the same orchestration | TLS is outside the first ExoSwarm surface unless explicitly required |
| Result vocabulary | [`sherlockpipe/search/transitresult.py::TransitResult`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/search/transitresult.py) | Candidate field names such as period, duration, depth, epoch, SNR, SDE | Untyped mutable attributes are discovery aids, not an ExoSwarm schema |
| Harmonic/alias check | [`sherlockpipe/search/Searcher.py::Searcher._is_harmonic`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/search/Searcher.py) | Ratios against prior signals, known objects, and detrending periods | Define ExoSwarm tolerances and evidence explicitly |
| End-to-end stage boundaries | [`sherlockpipe/search/sherlock.py::Sherlock.__prepare`, `__detrend`, `__identify_signals`, `__adjust_transit`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/search/sherlock.py) | Stage order, iterative signal masking, multiple detrends | This class mixes orchestration, files, plots, catalogs, and science; do not copy it |
| Search configuration vocabulary | [`sherlockpipe/search/sherlock_target.py::SherlockTarget`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/search/sherlock_target.py) | Bounds, cadences, detrend/search choices | ExoSwarm should expose only bounded registry parameters |
| Candidate scoring | [`sherlockpipe/scoring/`](https://github.com/franpoz/SHERLOCK/tree/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/scoring) | Basic SNR/SDE selectors, quorum across detrends, border correction | Pick one small deterministic policy first; avoid a plug-in selector ecosystem |
| Phase coverage | [`sherlockpipe/search/phase_coverage/phase_coverage.py::PhaseCoverage`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/search/phase_coverage/phase_coverage.py) | Detecting poorly sampled trial periods | Validate edge behavior with ExoSwarm time arrays |
| Vetting handoff | [`sherlockpipe/vetting/vetter.py::Vetter.run`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/vetting/vetter.py) | Adapter from search candidate to WATSON | Do not inherit report-directory coupling |

For preprocessing conventions, also consult SHERLOCK's search docs and the orchestration inside `Sherlock.__prepare`/`__detrend`. The documented pipeline uses Lightkurve products, Savitzky–Golay local noise reduction, RMS-based masking, periodic variability handling, and multiple detrending windows. At the indexed commit, acquisition and much preparation are delegated to the separate `lcbuilder` dependency (`LcBuilder.build`, `Flattener`, and `LcbuilderHelper`), so further searching inside SHERLOCK will not reveal all underlying algorithms. Treat each transformation as separately testable, prefer official Lightkurve/Astropy/Wotan contracts for the local implementation, and return explicit masks and provenance.

## WATSON code map

WATSON currently concentrates most scientific and plotting behavior in one large module. Navigate by symbol rather than reading `watson.py` from top to bottom.

| ExoSwarm concern | Upstream symbol | What to extract | Caveat |
|---|---|---|---|
| Vetting stage flow | [`Watson.vetting_with_data` and `Watson.__process`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | Inputs and order of folded, per-transit, TPF, centroid, and metric work | Split into pure measurements; exclude report/GPT paths |
| Phase-folded arrays | [`Watson.compute_phased_values`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | Phase convention, in/out-of-transit ranges, binning | Make epoch/time system and units explicit |
| Folded SNR | [`Watson.compute_snr`, `compute_snr_folded`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | OOT noise window and sample accounting | Verify against injections and degenerate windows |
| Transit-by-transit depths | [`Watson.plot_transits_statistics`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | Odd/even indexing and depth summary inputs | Plotting function is only an algorithm clue; return structured values instead |
| Odd/even diagnostic | [`Watson.plot_folded_curve`, `_extract_bayesian_odd_even_metrics`, `_plot_odd_even_comparison`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | Folded-curve correlation and fitted odd/even depth difference in sigma | Current fitted path depends on allesfitter; build the bounded ExoSwarm measurement first |
| Secondary event | [`Watson.plot_folded_curve`, `_extract_allesfitter_occultation_depth`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | Phase-0.5 window and secondary SNR/depth concepts | Search phase and multiple-testing policy must be explicit |
| Difference image | [`Watson.compute_tpf_diff_image`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | In-minus-out pixel image construction | Preserve aperture, cadence, WCS, sector, and mask provenance |
| Optical ghost | [`Watson.compute_optical_ghost_data`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | Core-versus-halo light-curve comparison | Validate apertures and failure on insufficient pixels |
| Centroid shifts | [`Watson.compute_centroids_for_tpf`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | OOT normalization, motion correction, RA/Dec shift series | Separate pixel and sky units and handle zero OOT variance |
| Source localization | [`Watson.light_centroid`, `plot_folded_tpf`, `plot_folded_tpfs`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/watson.py) | Flux/SNR centroid, WCS conversion, per-sector aggregation | Rendering is not evidence; persist coordinates and uncertainties |
| Neighbor/FOV analysis | [`watson/neighbours.py`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/neighbours.py) and `Watson.vetting_field_of_view` | Nearby-source light curves and 2-D Gaussian localization | Catalog identity must stay behind ExoSwarm's gate |

## Scientific cautions

Do not port `BlsSearcher.search` numerics unchanged. At the indexed commit it sets false-alarm probability and odd/even mismatch to zero, repeats one depth across all transits, uses zero depth errors, estimates SDE as peak power divided by median power, estimates period error from adjacent grid spacing, and contains a radius-ratio expression that requires independent review. These fields would look real in a typed result while carrying false certainty.

Use Astropy/Lightkurve public contracts and controlled injections to define ExoSwarm BLS behavior. Explicitly test:

- time, period, epoch, duration, and depth units;
- NaN, cadence, quality-mask, and normalization conventions;
- boundary periods, transit-count requirements, and period-grid resolution;
- uncertainty semantics rather than zeros;
- harmonic/half-period/double-period cases;
- positive injection, flat/noise-only negative, and cached real observation.

WATSON is report-oriented. Convert calculations into typed numeric evidence before generating any plot. Thresholds such as 3-sigma secondary or odd/even checks are useful hypotheses, not automatic ExoSwarm requirements; lock thresholds in ExoSwarm tests and docs.

## Suggested ExoSwarm mapping

| ExoSwarm function | First upstream stop | Expected local boundary |
|---|---|---|
| `load_tess_observation()` | SHERLOCK `__prepare` delegates to `lcbuilder`; use official Lightkurve docs | Cached observation, masks, cadence/sector metadata, provenance |
| `preprocess_lightcurve()` | SHERLOCK docs/orchestration plus the declared `lcbuilder` behavior | Clean arrays plus explicit removed-sample mask and reasons |
| `detrend_lightcurve()` | SHERLOCK `__detrend` | Deterministic trend and normalized flux with parameters |
| `search_bls()` | `BlsSearcher.search` | Periodogram and best candidate with units and non-placeholder metrics |
| `measure_candidate()` / `phase_fold()` | `TransitResult`; WATSON phased/SNR functions | Typed measurement and fold arrays, never plot-derived values |
| `harmonic_test()` | `Searcher._is_harmonic` | Tested relation, ratio, tolerance, referenced candidate IDs |
| `odd_even_test()` | WATSON transit statistics/folded curve | Odd/even depths, errors, difference, significance, sample counts |
| `secondary_eclipse_test()` | WATSON folded secondary path | searched phase/window, depth/error/SNR, trial policy |
| `centroid_localization()` | WATSON TPF difference/centroid paths | pixel and sky offsets, uncertainties, sector/aperture provenance |

## Tests and fixtures

Useful fixture patterns—not files to vendor blindly—are:

- SHERLOCK [`sherlockpipe/regression_tests/test_entrypoints.py`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/regression_tests/test_entrypoints.py) and [`search.yaml`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/regression_tests/search.yaml) for end-to-end regression shape.
- SHERLOCK [`sherlockpipe/tests/test_sherlock.py`](https://github.com/franpoz/SHERLOCK/blob/a42e2025c521572b79f0add0a6f135b2df84aabc/sherlockpipe/tests/test_sherlock.py) for orchestration tests.
- WATSON [`watson/tests/test_watson.py`](https://github.com/PlanetHunters/watson/blob/c8332b9a77fcae2b56942def18ca3a0573b0a772/watson/tests/test_watson.py) for vetting/report entry points.
- WATSON `watson/tests/vetting_test/` for the shape of cached TPF, light-curve, centroid, metric, source-offset, and optical-ghost artifacts.

Check data licensing and size before reusing any upstream fixture. Prefer ExoSwarm-owned synthetic fixtures and a deliberately cached real target with recorded acquisition provenance.

## Do not adopt

- Full SHERLOCK pipeline, OI/catalog refresh, arbitrary custom modules, or its broad YAML surface.
- Statistical validation, parameter fitting, follow-up planning, or TLS during the initial bounded science layer.
- WATSON PDF/report and GPT/IATSON interpretation paths as numerical authority.
- Ground-truth target names, neighbor catalogs, or recognizable identity in agent-visible context before lock.
- Mutable attribute bags, filesystem directories as API contracts, generated images as evidence, or silent fallback values.
