# Variability-Gated Predictive Detacking for Reliability-Aware Photovoltaic Tracking

This repository accompanies the manuscript **“Variability-Gated Predictive Detacking for Reliability-Aware Photovoltaic Tracking: A Field-Data-Driven Demonstration of Thermal-Cycle Mitigation”** submitted to *Solar Energy*.

## Scope

The study evaluates a reliability-aware supervisory tracking strategy in which temporary PV detacking is used to moderate rapid irradiance forcing and associated module-temperature cycling. The workflow combines:

- one-minute PV field measurements;
- data-quality screening and short-gap treatment;
- compact short-horizon module-temperature prediction;
- rainflow thermal-cycle counting and the squared cycle-severity index (CSI2);
- a normalized ramp index (NRI) for daily irradiance variability;
- slew-rate-limited detacking;
- supervisory NRI gating; and
- evaluation of CSI2 response, incident-irradiance penalty, and actuator burden.

The controller is a **conceptual, field-data-driven supervisory demonstration**. The term *predictive* refers to the use of short-horizon thermal forecasts; the detacking law itself is rule-based and is not model predictive control (MPC).

## Main reported results

For the System 2B development dataset, the compact thermal model achieved a one-minute MAE of **0.167 °C** and RMSE of **0.250 °C**; the 15-min recursive forecast retained an MAE of **1.167 °C** and R² of **0.970**.

On the selected high-variability day, the frozen controller setting of **400 W m⁻² min⁻¹** maximum positive irradiance slew and **45°** maximum detacking reduced simulated peak module temperature by **1.351 °C** and CSI2 by **9.354%**, at a **1.865% incident-irradiance penalty**.

On the 21-day complete-wind subset, the demonstration-specific **NRI ≥ 0.090** gate reduced mean incident-irradiance penalty, intervention time, and angle changes by approximately **45%**, while increasing mean CSI2 reduction from **0.139%** to **0.441%** relative to always-available adaptive control.

The same frozen NRI threshold was also evaluated without threshold re-optimization on two independent 2018 systems. These checks support selective supervisory activation, not a universal threshold claim.

## Repository structure

```text
.
├── README.md
├── CITATION.cff
├── LICENSE
├── requirements.txt
├── .gitignore
├── notebooks/
│   └── variability_gated_pv_detacking.ipynb
├── data/
│   └── README.md
└── results/
    └── README.md
```

## Data

The manuscript uses public one-minute PV module-temperature and meteorological data released with the work of Barry et al. The raw data are **not redistributed in this repository**. Please obtain the original files from the source repository cited in the manuscript and place them locally as described in [`data/README.md`](data/README.md).

The principal files used in the study are:

- `PV_temperature_model_data_2019_System_2B_1min.dat`
- `PV_temperature_model_data_2018_System_1_1min.dat`
- `PV_temperature_model_data_2018_System_2A_1min.dat`

## Reproducibility

1. Clone this repository.
2. Create a Python environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Download the public data files described in `data/README.md`.
5. Open and run:

```text
notebooks/variability_gated_pv_detacking.ipynb
```

The notebook contains the computational analysis used for the manuscript submission. Because the notebook originated from an interactive research workflow, users should verify local file paths before execution.

## Interpretation limits

The incident-irradiance penalty is a proxy for potential energy-yield loss; PV electrical conversion is not explicitly modeled. The simplified detacking relation does not resolve diffuse irradiance, bifacial contribution, row-to-row shading, backtracking, terrain geometry, or deployment-grade tracker constraints. CSI2 is a comparative cycle-severity metric and is not a calibrated lifetime-damage law.

## Authors

- **Vivekanandan N** — Department of Mechanical Engineering, Pimpri Chinchwad College of Engineering, Pune, India
- **Rajeswari K** — Department of Computer Engineering, Pimpri Chinchwad College of Engineering, Pune, India
- **Sanjay Salve** — Department of Mechanical Engineering, Pimpri Chinchwad College of Engineering, Pune, India

Corresponding author: **Vivekanandan N**  
Email: `n.vivekanandan@pccoepune.org`

## Citation

If you use this repository, please cite the associated manuscript. A machine-readable citation file is provided in [`CITATION.cff`](CITATION.cff).

## License

Code and repository-authored documentation are released under the MIT License. The external dataset remains subject to the terms of its original source and is not covered by this repository license.
