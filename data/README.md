# Data acquisition and provenance

External field-measurement data are **not redistributed** in this repository.

Original public dataset associated with Barry et al., Zenodo DOI **10.5281/zenodo.3958820**:
https://doi.org/10.5281/zenodo.3958820

Download the original one-minute measurements identified by the source archive:

```text
PV_temperature_model_data_2019_System_2B_1min.dat
PV_temperature_model_data_2018_System_1_1min.dat
PV_temperature_model_data_2018_System_2A_1min.dat
```

The 2019 System 2B record was used for development; 2018 System 1 and 2A were used for the reported external evaluation, **39 eligible days each** after applicable filtering. Both 2018 systems were inspected during broader development; describe this as an external cross-system retrospective evaluation, **not completely untouched prospective validation**.

The revised frozen causal supervisory rule uses **only the preceding 30 minutes of irradiance**, threshold 0.12. Earlier historical analysis using a retrospectively calculated **completed-day** NRI threshold of 0.090 is distinct from that rule. See the top-level README.

Cite the original data creators and source. The repository MIT license does not transfer rights in externally owned data.
