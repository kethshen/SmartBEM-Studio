import pandas as pd
import numpy as np
import os

OVERFLOW = 60000

files = {
    "Part 1": r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Full Day 1 part 1_2026-07-23.csv",
    "Part 2": r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Full day 1 part 2_2026-07-23.csv",
    "Part 5": r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Full Day 1 part 5_2026-07-23.csv",
    "Part 6": r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Full Day 1 part 6_2026-07-23.csv",
}

TEMP_COLS = ["outside_t", "room_1_t", "room_2_t", "room_3_t", "supply_t", "return_t"]
LABELS    = ["Outside",   "Sensor 1", "Sensor 2", "Sensor 3", "Supply",   "Return"]

for part, path in files.items():
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    numeric = df.select_dtypes(include="number").columns
    df[numeric] = df[numeric].where(df[numeric] < OVERFLOW, np.nan)
    df["elapsed_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60

    dur = df["elapsed_min"].max()
    interval = df["timestamp"].diff().dt.total_seconds().median()

    print(f"=== {part} ===")
    print(f"  File     : {os.path.basename(path)}")
    print(f"  Rows     : {len(df)}")
    print(f"  Duration : {dur:.1f} min ({dur/60:.2f} hrs)")
    print(f"  Interval : {interval:.1f} s")
    print(f"  Start    : {df['timestamp'].iloc[0]}")
    print(f"  End      : {df['timestamp'].iloc[-1]}")

    temp_sub = df[[c for c in TEMP_COLS if c in df.columns]].copy()
    temp_sub.columns = [LABELS[TEMP_COLS.index(c)] for c in temp_sub.columns]
    print(temp_sub.describe().round(2).to_string())
    print()
