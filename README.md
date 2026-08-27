# Variability-Gated Predictive Detacking for Reliability-Aware Photovoltaic Tracking

Reproducibility repository accompanying the manuscript **“Variability-Gated Predictive Detacking for Reliability-Aware Photovoltaic Tracking: A Field-Data-Driven Demonstration of Thermal-Cycle Mitigation”**, submitted to *Solar Energy*.

## Scope

This study evaluates a reliability-aware supervisory tracking strategy in which temporary PV detacking moderates rapid irradiance forcing and associated module-temperature cycling. The workflow combines one-minute PV field measurements, data-quality screening, compact short-horizon module-temperature prediction, rainflow thermal-cycle counting, the squared cycle-severity index (CSI2), a normalized ramp index (NRI), slew-rate-limited detacking, supervisory NRI gating, and evaluation of incident-irradiance penalty and actuator burden.

> **Controller status:** this is a conceptual, field-data-driven supervisory demonstration. “Predictive” refers to short-horizon thermal forecasts informing the decision logic; the detacking law is rule-based and is **not model predictive control (MPC)**.

## Main reported results

For the System 2B development dataset, the compact thermal model achieved a one-minute MAE of **0.167 °C** and RMSE of **0.250 °C**; the 15-min recursive forecast retained an MAE of **1.167 °C** and R² of **0.970**. On the selected high-variability day, the frozen setting of **400 W m⁻² min⁻¹** maximum positive irradiance slew and **45°** maximum detacking reduced simulated peak module temperature by **1.351 °C** and CSI2 by **9.354%**, at a **1.865% incident-irradiance penalty**.

On the 21-day complete-wind subset, the demonstration-specific **NRI ≥ 0.090** gate reduced mean incident-irradiance penalty, intervention time, and angle changes by approximately **45%**, while increasing mean CSI2 reduction from **0.139%** to **0.441%** relative to always-available adaptive control. The same frozen threshold was checked without re-optimization on independent 2018 System 1 and System 2A data; these tests support selective supervisory activation, not a universal threshold claim.

## Repository structure

```text
.
├── README.md
├── CITATION.cff
├── LICENSE
├── requirements.txt
├── .gitignore
├── notebooks/
│   └── README.md
├── data/
│   └── README.md
└── results/
    ├── README.md
    └── independent_validation_results.csv
```

## Data

The field-measurement dataset is publicly available from Zenodo under **DOI 10.5281/zenodo.3958820**. Raw third-party data are not redistributed here. See [`data/README.md`](data/README.md) for the three one-minute files used for development and independent validation.

## Reproducibility

Install the environment with:

```bash
pip install -r requirements.txt
```

Then obtain the original data as described in `data/README.md`. The corrected final submission notebook is `analysis_notebook_final.ipynb`; see [`notebooks/README.md`](notebooks/README.md) for its intended repository location and frozen analysis settings.

The independent-system summary exported from the audited submission analysis is provided in [`results/independent_validation_results.csv`](results/independent_validation_results.csv).

## Interpretation limits

The incident-irradiance penalty is a proxy for potential energy-yield loss; PV electrical conversion is not explicitly modeled. The simplified detacking relation does not resolve diffuse irradiance, bifacial contribution, row-to-row shading, backtracking, terrain geometry, or deployment-grade tracker constraints. CSI2 is a comparative cycle-severity metric and is not a calibrated lifetime-damage law.

## Authors

**Vivekanandan N** — Department of Mechanical Engineering, Pimpri Chinchwad College of Engineering, Pune, Maharashtra 411044, India  
**Rajeswari K** — Department of Computer Engineering, Pimpri Chinchwad College of Engineering, Pune, Maharashtra 411044, India  
**Sanjay Salve** — Department of Mechanical Engineering, Pimpri Chinchwad College of Engineering, Pune, Maharashtra 411044, India

Corresponding author: **Vivekanandan N** — `n.vivekanandan@pccoepune.org`

## Citation

Please cite the associated manuscript when using this repository. Machine-readable metadata are provided in [`CITATION.cff`](CITATION.cff). Publication DOI/details should be added after acceptance.

## License

Repository-authored code and documentation are released under the MIT License. External data remain subject to the terms of the original dataset source.
