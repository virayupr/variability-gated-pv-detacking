# Analysis notebook — provenance warning

The file `variability_gated_pv_detacking.ipynb` is retained from an earlier version of this study. Earlier descriptions refer to a **retrospective completed-day NRI threshold of 0.090**, while the revised manuscript primary analysis uses a **causal past-only 30-minute rolling-window threshold of 0.12**. These are different gating definitions and must not be conflated.

The revised frozen control settings are: causal rolling-window NRI threshold 0.12; positive irradiance slew target 400 W m⁻² min⁻¹; maximum angular offset 45°; five-minute dwell. The revised analysis uses 39 eligible days in each of 2018 Systems 1 and 2A.

**Reproducibility status: unverified for revised manuscript.** The existing notebook has not been independently rerun or audited here for the new causal gate, the 23-threshold sweep, moving-block bootstrap, thermal-model benchmark, or CSI² conventions. Do not describe it as the validated final submission notebook until those checks are completed.

Obtain the original data using `../data/README.md`. The repository requirements are in `../requirements.txt`. Preserve earlier source, parameters and outputs for historical provenance rather than silently changing their interpretation.
