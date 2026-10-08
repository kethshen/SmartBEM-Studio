"""
Generate occ_day_3_truth.csv for Day 3 Datasets
===============================================
Matches the exact schema of occ_day_4_truth.csv:
Dataset name,start_min,end_min,total occupancy inside chamber

Schedule for Day 3 (standard experiment protocol):
  - start_min = 0.0 to 5.0  -> 0 occupants
  - start_min = 5.0 to 20.0 -> 1 occupant
  - start_min = 20.0 to end -> 0 occupants
"""

import os
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WITH_OCC_DIR = SCRIPT_DIR

day3_files = sorted([f for f in os.listdir(WITH_OCC_DIR) if f.startswith("day_3_") and f.endswith(".csv") and "truth" not in f])

rows = []
for fname in day3_files:
    ds_name = fname.replace(".csv", "")
    df = pd.read_csv(os.path.join(WITH_OCC_DIR, fname))
    
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
        total_duration = round((ts.iloc[-1] - ts.iloc[0]).total_seconds() / 60.0, 2)
    else:
        total_duration = round(len(df) * 5.0 / 60.0, 2)
        
    # 0.0 to 5.0 -> 0 occupants
    rows.append({"Dataset name": ds_name, "start_min": 0.0, "end_min": 5.0, "total occupancy inside chamber": 0})
    # 5.0 to 20.0 -> 1 occupant
    rows.append({"Dataset name": ds_name, "start_min": 5.0, "end_min": 20.0, "total occupancy inside chamber": 1})
    # 20.0 to total_duration -> 0 occupants
    if total_duration > 20.0:
        rows.append({"Dataset name": ds_name, "start_min": 20.0, "end_min": total_duration, "total occupancy inside chamber": 0})

df_day3_truth = pd.DataFrame(rows)
out_csv = os.path.join(WITH_OCC_DIR, "occ_day_3_truth.csv")
df_day3_truth.to_csv(out_csv, index=False)

print(f"[SUCCESS] Saved Day 3 Ground Truth CSV to: {out_csv}")
print(df_day3_truth.to_string(index=False))
