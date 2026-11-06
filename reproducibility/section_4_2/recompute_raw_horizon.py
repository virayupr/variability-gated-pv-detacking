"""Recompute A5 horizon-prefix RMSE from original 2018 PV measurements.

The 45/47 archived segment start/end boundaries are supplied by the inventory.
This independently recomputes temperatures and RMSE from raw observations, but
DOES NOT recover the original historical segment-selection rule.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

INTERCEPT = -0.0646758225962696
COEF = (0.001332444285928732, -0.03781738842017032, -0.0062791136383369)

def run(inventory, data_dir, output_dir):
    inv = pd.read_csv(inventory, dtype={"system": str}, parse_dates=["start", "end"])
    rows, checks = [], []
    for system in ("1", "2A"):
        files = sorted(data_dir.glob(f"PV_temperature_model_data_2018_System_{system}_1min*.dat"))
        if not files:
            raise FileNotFoundError(f"Missing raw System {system} data in {data_dir}")
        raw = pd.read_csv(files[0], sep=";", comment="#", parse_dates=["Timestamp_UTC"])
        raw = raw.set_index("Timestamp_UTC")
        if not raw.index.is_unique:
            raise ValueError("Duplicate timestamps")
        for seg in inv.loc[inv.system == system].itertuples():
            part = raw.loc[seg.start:seg.end]
            expected_index = pd.date_range(seg.start, seg.end, freq="min")
            if len(part) != seg.n or not part.index.equals(expected_index):
                raise AssertionError(f"Segment continuity mismatch: {system}, {seg.sid}")
            v = part[["T_module_C", "T_ambient_C", "Gtotpoa_Wm2", "v_wind_ms"]].to_numpy(float)
            if not np.isfinite(v).all():
                raise AssertionError(f"Nonfinite segment inputs: {system}, {seg.sid}")
            pred = np.empty(len(v))
            pred[0] = v[0, 0]
            for i in range(len(v) - 1):
                _, ambient, irradiance, wind = v[i]
                pred[i + 1] = (pred[i] + INTERCEPT + COEF[0] * irradiance
                    + (COEF[1] + COEF[2] * wind) * (pred[i] - ambient))
            error = pred - v[:, 0]
            full_rmse = float(np.sqrt(np.mean(error**2)))
            full_bias = float(np.mean(error))
            if abs(full_rmse - seg.rmse) > 1e-9 or abs(full_bias - seg.bias) > 1e-9:
                raise AssertionError(f"Archived mismatch: {system}, {seg.sid}")
            checks.append({"system": system, "sid": seg.sid,
                           "archived_rmse": seg.rmse, "raw_rmse": full_rmse,
                           "archived_bias": seg.bias, "raw_bias": full_bias})
            for horizon in (30, 60, 120, None):
                n = len(error) if horizon is None else min(horizon, len(error))
                rows.append({"system": system, "sid": seg.sid,
                             "horizon": "full" if horizon is None else str(horizon),
                             "n": n, "rmse": float(np.sqrt(np.mean(error[:n]**2))),
                             "bias": float(np.mean(error[:n]))})
    output_dir.mkdir(parents=True, exist_ok=True)
    checks = pd.DataFrame(checks)
    detail = pd.DataFrame(rows)
    summary = detail.groupby(["system", "horizon"], sort=False).agg(
        n_segments=("sid", "size"),
        mean_segment_rmse=("rmse", "mean"),
        mean_segment_bias=("bias", "mean")).reset_index()
    checks.to_csv(output_dir / "raw_vs_archived_segment_checks.csv", index=False)
    detail.to_csv(output_dir / "raw_horizon_by_segment.csv", index=False)
    summary.to_csv(output_dir / "raw_horizon_summary.csv", index=False)
    print(summary.to_string(index=False))
    print("Maximum archived RMSE discrepancy:",
          float(np.max(np.abs(checks.archived_rmse - checks.raw_rmse))))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path,
                        default=Path(__file__).with_name("complete_segment_inventory.csv"))
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("section_4_2_results"))
    args = parser.parse_args()
    run(args.inventory, args.data_dir, args.out_dir)
