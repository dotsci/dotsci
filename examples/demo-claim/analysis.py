"""Demo analysis for the DotSci example claim. Standard library only.

Reads measurements.csv from DOTSCI_DATA_DIR (default ./data), computes the mean
difference between treatment and control and the sample size, and writes
results.json to DOTSCI_OUT_DIR (default ./out).
"""
import csv
import json
import os
import statistics
from pathlib import Path

data_dir = Path(os.environ.get("DOTSCI_DATA_DIR", "data"))
out_dir = Path(os.environ.get("DOTSCI_OUT_DIR", "out"))

groups = {"control": [], "treatment": []}
with open(data_dir / "measurements.csv", newline="") as f:
    for row in csv.DictReader(f):
        groups[row["group"]].append(float(row["value"]))

effect = statistics.mean(groups["treatment"]) - statistics.mean(groups["control"])
n = len(groups["control"]) + len(groups["treatment"])

out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "results.json").write_text(
    json.dumps({"mean_difference": round(effect, 4), "sample_size": n}, indent=2) + "\n"
)
