# Solar Energy revision — computational reproducibility review

**Status: review candidate, NOT a certified end-to-end reproducibility release.**

This directory preserves 21 original Python analysis and benchmark scripts for the revised exploratory study, *Causal Irradiance-Ramp-Gated Detacking for Photovoltaic Thermal-Cycle Assessment* (SEJ-D-26-04126). Scripts were copied from the research uploads and renamed to canonical importable filenames; scientific claims and computations have not been silently rewritten.

## Frozen computational policy
- Past-only 30-minute rolling normalized ramp index (NRI), threshold 0.12.
- Positive irradiance-slew target 400 W m^-2 min^-1, not a guaranteed physical limit.
- Maximum simulated offset 45 degrees; minimum dwell 5 minutes.
- Idealized cosine optical proxy; **not measured electrical energy**.
- External evaluation: 2018 System 1 and System 2A, 39 eligible days each, previously inspected during development.

## Archived results — NOT independently rerun by this PR
| Estimand | 2018 System 1 | 2018 System 2A |
|---|---:|---:|
| Equal-day mean-daily closed-cycle CSI² reduction | -1.7698% | -0.4482% |
| Pooled closed-cycle CSI² reduction | +0.5576% | +0.2366% |
| Equal-day mean-daily closed-cycle 95% moving-block CI | [-5.3583%, +0.3840%] | [-1.2273%, +0.2474%] |

Both mean-daily confidence intervals span zero. Pooled and mean-daily results are different estimands. Including half cycles reverses the sign of the mean-daily point estimates. CSI² is an uncalibrated simulated cycle-severity proxy, not demonstrated physical fatigue, lifetime extension, or validated intervention benefit.

## Reproduction dependencies and limitations
- Python scientific stack: numpy, pandas, scipy, matplotlib, scikit-learn, pvlib where required; A15 requires **rainflow==3.2.0**.
- Scripts currently retain original `/mnt/data` path assumptions in some supplementary audits; they are archived as supplied, not yet portable.
- The 2019 System 2B training data and complete A5–A9 archives are required for a clean end-to-end rerun.
- Raw 2018 external datasets and large binary archives are **not committed** in this PR. Obtain original data from https://doi.org/10.5281/zenodo.3958820 and verify source hashes against the archived audit manifests.
- A14/A15 archived comparisons report 624 rows, no failures, tolerance 1e-8 and maximum difference ~4.55e-13. These are archived findings, not an independently executed CI test in this branch.
- The existing repository notebook and historical results CSV predate the revised causal threshold and must not be represented as the revised empirical findings.

## Manuscript visuals
The uploaded manuscript ZIP contains original LaTeX tables and PNG figures, but they are **not yet committed here**; this PR does not claim the figures were independently regenerated. Do not replace them with invented images.

## Before merge
1. Add source-data checksums, pinned environment, and portable execution commands.
2. Regenerate A5–A15 from raw data and compare archived numeric outputs.
3. Inspect all manuscript tables and figures for consistency.
4. Resolve journal/editor requirements, including accurate disclosure of generative-AI involvement in manuscript drafting.

**Do not merge this PR as a certified reproducibility release until the above are complete.**
