# Data acquisition

Raw field measurements are intentionally not redistributed here.

The study uses the public PV module-temperature dataset associated with Barry et al., available from **Zenodo, DOI 10.5281/zenodo.3958820**:

https://doi.org/10.5281/zenodo.3958820

Download the following one-minute files from the original repository and place them in this `data/` directory:

```text
PV_temperature_model_data_2019_System_2B_1min.dat
PV_temperature_model_data_2018_System_1_1min.dat
PV_temperature_model_data_2018_System_2A_1min.dat
```

## Role of each dataset

- **2019 System 2B** — primary development dataset used for model fitting, controller demonstration, daily NRI analysis, and sensitivity evaluation.
- **2018 System 1** — independent cross-system validation.
- **2018 System 2A** — independent cross-system validation.

The manuscript reports 69,185 one-minute records in the System 2B source file spanning 25 June–12 August 2019. Quality-control and daylight filters are applied in the analysis workflow.

## Licensing and provenance

Please cite the original dataset/publication when reusing these measurements. Dataset rights and licensing remain with the original data creators/source; the MIT license in this repository does not apply to these external files.
