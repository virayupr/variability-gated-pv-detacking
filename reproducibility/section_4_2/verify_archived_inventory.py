"""Validate an archived Section 4.2 segment inventory, not a raw-data rerun."""
import argparse
from pathlib import Path
import pandas as pd

EXPECTED = {
    "1": (45, 55858, 1.046593, 2.522601),
    "2A": (47, 57020, -1.273133, 2.488273),
}
COLUMNS = {"sid", "start", "end", "n", "bias", "rmse", "system", "selection_rule"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    data = pd.read_csv(args.inventory, dtype={"system": str})
    missing = COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"Missing inventory columns: {sorted(missing)}")
    if set(data["system"]) != set(EXPECTED):
        raise AssertionError("Unexpected system identifiers")
    if data[["start", "end", "n", "bias", "rmse"]].isna().any().any():
        raise AssertionError("Missing segment values")
    if (data["n"] <= 0).any():
        raise AssertionError("Nonpositive segment length")
    for system, (count, samples, bias, rmse) in EXPECTED.items():
        group = data.loc[data["system"] == system]
        observed = (len(group), int(group["n"].sum()),
                    float(group["bias"].mean()), float(group["rmse"].mean()))
        assert observed[:2] == (count, samples), (system, observed)
        assert abs(observed[2] - bias) < 0.000002, (system, observed)
        assert abs(observed[3] - rmse) < 0.000002, (system, observed)
        print(f"System {system}: segments={observed[0]}, samples={observed[1]}, "
              f"mean bias={observed[2]:+.6f} C, mean RMSE={observed[3]:.6f} C")
    print("PASS: archived inventory matches the revised descriptive summary.")
    print("NOT VERIFIED: original raw-data eligibility or horizon RMSE reproduction.")

if __name__ == "__main__":
    main()
