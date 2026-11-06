# Section 4.2 — segment reconciliation and reproducibility status

**Status: partial archived-output reconstruction; NOT a raw-data end-to-end reproduction.**

This directory documents the segment-count discrepancy identified in Solar Energy Reviewer 1, Comment 4. The revised manuscript distinguishes four cohorts:

1. **Completeness-audit / archived all-segment reconstruction:** System 1: 45 segments, 55,858 samples; System 2A: 47 segments, 57,020 samples.
2. **Historical recursive evaluation:** System 1: 44 segments; System 2A: 45 segments. The original exclusion rule could not be recovered. Do not claim these historical horizon-specific RMSE estimates were regenerated using the all-segment rule.
3. **Matched three-model benchmark:** System 1: 32 runs; System 2A: 34 runs, requiring common data including Barry-model longwave inputs. Distinct selection requirements; not the historical 44/45 subset.
4. **Matched model sensitivity:** 28 and 29 nonzero-baseline-CSI² days, respectively; a distinct analysis.

## Archived inventory and numerical checks

The user-provided file `complete_segment_inventory(1).csv` contains 92 segment records with columns `sid,start,end,n,bias,rmse,bias_exfirst,rmse_exfirst,system,selection_rule`. Its aggregate statistics were checked against the revised Section 4.2 values:

| Statistic | System 1 | System 2A |
|---|---:|---:|
| Segments | 45 | 47 |
| Samples | 55,858 | 57,020 |
| Mean of segment-level bias (°C) | +1.046593 | -1.273133 |
| Mean of segment-level RMSE (°C) | 2.522601 | 2.488273 |

See `archived_all_segment_summary.csv`. These figures summarize archived reconstructed segment outputs; they do **not** establish independent reproduction from the original one-minute measurements. The source inventory CSV must still be committed to this directory and checked against original measurements.

## Controller policy

The final frozen causal policy uses a **past-only 30-minute NRI window and threshold 0.12**, a positive-ramp target of 400 W m^-2 min^-1, a simulated 45-degree angular cap, and a five-minute dwell. Historical examples using **0.09** refer to an earlier retrospective completed-day gate, not the final causal controller. The cosine irradiance attenuation is an idealized optical proxy, not a validated physical tracking model.

## Running the archived-inventory checks

With Python 3, pandas, and the uploaded inventory file in this directory:

```bash
python -m pip install pandas
python verify_archived_inventory.py complete_segment_inventory.csv
```

The script checks the expected counts and aggregates and exits nonzero if they differ. It does not regenerate the segment inventory or horizon-specific RMSE values.

## Remaining before claiming Comment 4 fully resolved

- Commit the **full 92-row segment inventory** as `complete_segment_inventory.csv`.
- Publish the exact raw-data eligibility, continuity, exclusion, initialization, and horizon-prefix rules in executable code.
- Recompute 30-, 60-, 120-minute and full-run RMSE from raw one-minute records using the declared 45/47 all-segment cohort; update the manuscript table and figure together.
- Supply source-file checksums, a portable run command, expected output manifests, and ideally an automated clean-environment test.
- Verify matched benchmark run inventory and sky-temperature alignment independently.
- Keep historical outputs explicitly marked historical, and ensure all notebooks/configurations distinguish the old 0.09 and frozen 0.12 settings.

No physical tracker operation, electrical-energy savings, or reliability improvement is established by these archived reconstructions.
