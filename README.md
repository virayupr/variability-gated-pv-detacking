# Causal Irradiance-Ramp-Gated Detacking for Photovoltaic Thermal-Cycle Assessment

Supporting computational research repository for manuscript **SEJ-D-26-04126**, *Causal Irradiance-Ramp-Gated Detacking for Photovoltaic Thermal-Cycle Assessment*, submitted to *Solar Energy*. This repository accompanies a revision-stage computational study; it does **not** demonstrate an operational detacking controller or verified module reliability improvement.

## Research scope

The revised assessment combines one-minute public photovoltaic (PV) field measurements, a recursive module-temperature surrogate, a **causal** irradiance-ramp supervisory gate using only the preceding 30 minutes, hypothetical angular detacking commands, simulated incident-irradiance attenuation, rainflow cycle counting, and uncertainty analysis. Its main outcome is a comparative squared thermal-cycle-severity index (CSI²), **not** calibrated fatigue damage or lifetime.

**Frozen causal policy:** NRI activation threshold 0.12; preceding 30-minute window; positive irradiance slew-rate target 400 W m⁻² min⁻¹; maximum simulated angular offset 45°; minimum dwell time 5 min. Angular saturation and dwell restrictions mean that the target slew is not guaranteed. The angular intervention is a computational counterfactual, not measured tracker operation.

The previously published/used retrospective **completed-day** NRI threshold of 0.090 (historical bootstrap interval 0.015–0.125) is different from the causal rolling-window threshold 0.12. The historical interval is **not** a confidence interval for the causal threshold. Earlier historical controller demonstrations and summary outputs remain in the repository for provenance but must not be confused with the revised primary assessment.

## Principal revised evaluation results

Both 2018 evaluation systems had **39 eligible days**. For the prespecified five-point median-filtered, closed-cycle CSI² analysis, the equal-day-weighted **mean-daily** reductions were:

| Revised external evaluation | System 1 | System 2A |
|---|---:|---:|
| Mean-daily CSI² reduction | −1.7698% | −0.4482% |
| 95% five-day moving-block bootstrap interval | [−5.3583%, +0.3840%] | [−1.2273%, +0.2474%] |
| Pooled CSI² reduction (different weighting) | +0.5576% | +0.2366% |
| Mean simulated incident-irradiance penalty | 0.2215% | 0.1942% |
| Mean duration of nonzero simulated detacking, min/eligible day | 5.28 | 6.51 |

Confidence intervals for both primary mean-daily reductions include zero. Pooled reductions likewise have confidence intervals crossing zero. Thus **no robust beneficial reduction in thermal-cycle severity is established**. The mean-daily and pooled estimands use different aggregation weights and should not be interchanged.

Including rainflow residual half-cycles changes the mean-daily estimates to +0.2045% and +0.1132%, illustrating sensitivity to cycle-counting conventions. An exploratory sweep of **23** causal thresholds (0.015–0.125, increment 0.005) did not yield a positive mean-daily CSI² reduction on either external system.

The optical penalties are based on an **unvalidated cosine-based attenuation model**; they are not measured electrical-energy losses. Neither physical detacking, field reliability, fatigue damage, nor module lifetime was validated.

## Historical material retained for provenance

The 2019 System 2B development event previously illustrated a modelled 1.351 °C peak-temperature reduction, 9.354% closed-cycle CSI² reduction and 1.865% optical penalty. That single selected event is **not representative** of the revised 2018 external mean-daily findings.

**Important:** the existing `results/independent_validation_results.csv` records the **earlier historical NRI ≥ 0.090 evaluation**, not the revised NRI = 0.12 analysis. It is retained unchanged to prevent erasing the earlier output. Do not cite it as evidence for the revised primary table above.

## Repository structure and reproducibility status

- `notebooks/variability_gated_pv_detacking.ipynb`: existing notebook; **not yet independently verified against the revised policy or numerical results**.
- `notebooks/README.md`: explains the historical/revised-workflow distinction.
- `data/README.md`: provides public dataset acquisition instructions (third-party raw data are not distributed here).
- `results/independent_validation_results.csv`: **historical 0.090** summary; not updated or relabelled.
- `results/README.md`: explains which reported values are revised manuscript results.
- `CITATION.cff`: updated working manuscript citation.

Install requirements using `pip install -r requirements.txt` and obtain the datasets identified in `data/README.md`. **Do not treat the existence of the notebook as proof that all revised results can be rerun**: the revised analysis notebook, archived settings, outputs and environment require a separate reproducibility audit.

## Scientific limitations

The baseline and controlled-temperature trajectories depend on recursive thermal predictions. The original external full-segment RMSE values were 2.5261 °C (System 1) and 2.5525 °C (System 2A). In a matched-data comparison, surrogate complete-run RMSE values were 2.6278 °C and 2.7019 °C; the literature Barry model gave 1.5866 °C and 1.5135 °C but was calibrated on the evaluated systems, so this is **not an independent out-of-sample ranking**.

The analysis does not validate real electrical yield, physical motion, mechanical wear, field reliability, or module lifetime.

## Authors

1. **Vivekanandan N**, Department of Mechanical Engineering, Pimpri Chinchwad College of Engineering, Pune, India.
2. **Rajeswari K**, Department of Computer Engineering, Pimpri Chinchwad College of Engineering, Pune, India.
3. **Sanjay Salve**, Department of Mechanical Engineering, Pimpri Chinchwad College of Engineering, Pune, India.

Corresponding author: Vivekanandan N — `n.vivekanandan@pccoepune.org`. Original author order is unchanged.

## Citation and licensing

See [CITATION.cff](CITATION.cff). The manuscript is under editorial review; no article DOI or acceptance is claimed. The repository's MIT license applies to repository-authored material, not to the external measurement dataset.
