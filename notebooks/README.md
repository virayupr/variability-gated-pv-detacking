# Analysis notebook

The submission analysis is maintained as a Jupyter notebook. The final submission package uses `analysis_notebook_final.ipynb` (the corrected, audited analysis workflow).

For a fully self-contained GitHub reproducibility record, place that notebook in this directory as:

```text
notebooks/variability_gated_pv_detacking.ipynb
```

The notebook should be run with the original public data files described in `../data/README.md` and the environment listed in `../requirements.txt`.

Important frozen settings used by the submitted analysis include a 400 W m⁻² min⁻¹ slew-rate limit, 45° maximum detacking angle, NRI gate 0.090, 15-min thermal forecast horizon, and no threshold re-tuning on the independent 2018 systems.
