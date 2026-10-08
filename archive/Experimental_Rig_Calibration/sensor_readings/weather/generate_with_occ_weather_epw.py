"""
Generate With-Occ Weather EPW Files for EnergyPlus Benchmark
=============================================================
Synthesizes EPW weather files for all cleaned with_occ datasets (Day 3 & Day 4)
in `Experimental_Rig_Calibration/sensor_readings/weather/`.
"""

import os
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEATHER_DIR = SCRIPT_DIR
WITH_OCC_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "cleaned", "with_occ"))
BASELINE_EPW = os.path.join(WEATHER_DIR, "LKA_CP_Kandy.434440_TMYx.2011-2025.epw")

def calculate_dew_point(temp, rh):
    a, b = 17.27, 237.7
    alpha = ((a * temp) / (b + temp)) + np.log(np.maximum(rh, 1.0) / 100.0)
    return (b * alpha) / (a - alpha)

def create_epw_for_dataset(csv_path, target_month, target_day, epw_out_path):
    if not os.path.exists(BASELINE_EPW):
        print(f"Error: Baseline EPW {BASELINE_EPW} not found.")
        return

    df_telemetry = pd.read_csv(csv_path)
    with open(BASELINE_EPW, "r") as f:
        epw_lines = f.readlines()

    header = epw_lines[:8]
    data_lines = epw_lines[8:]

    target_lines = []
    for line in data_lines:
        parts = line.strip().split(",")
        if len(parts) > 4:
            m, d = int(parts[1]), int(parts[2])
            if m == target_month and d == target_day:
                target_lines.append(parts)

    if not target_lines:
        target_lines = [l.strip().split(",") for l in data_lines[:24]]

    if "timestamp" in df_telemetry.columns:
        df_telemetry['timestamp'] = pd.to_datetime(df_telemetry['timestamp'])
        df_telemetry = df_telemetry.sort_values('timestamp').reset_index(drop=True)
        df_resampled = df_telemetry.set_index('timestamp').resample('1min').mean().interpolate(method='linear').ffill().bfill().reset_index()
    else:
        df_resampled = df_telemetry.ffill().bfill().copy()
        df_resampled['timestamp'] = pd.date_range(start='2026-07-28 08:00', periods=len(df_resampled), freq='1min')

    new_data_lines = []
    n_records = len(df_resampled)

    for i in range(n_records):
        row = df_resampled.iloc[i]
        base_parts = target_lines[i % len(target_lines)].copy()

        ts = row['timestamp']
        base_parts[0] = str(ts.year)
        base_parts[1] = str(ts.month)
        base_parts[2] = str(ts.day)
        base_parts[3] = str(ts.hour + 1)
        base_parts[4] = str(ts.minute)

        t_out = row.get('outside_t', 25.0)
        rh_out = row.get('outside_h', 70.0)

        p_val = row.get('outside_p', 0.0)
        if pd.isnull(p_val) or p_val < 500.0:
            p_val = row.get('room_1_p', 955.8)
        if p_val < 2000.0:
            p_val *= 100.0
        p_out = p_val

        tdew_out = calculate_dew_point(t_out, rh_out)
        v_out = row.get('outside_v', 1.0)
        if v_out > 15.0:
            v_out /= 100.0

        base_parts[6] = f"{t_out:.1f}"
        base_parts[7] = f"{tdew_out:.1f}"
        base_parts[8] = f"{rh_out:.1f}"
        base_parts[9] = f"{p_out:.0f}"
        base_parts[21] = f"{v_out:.1f}"

        new_data_lines.append(",".join(base_parts) + "\n")

    with open(epw_out_path, "w") as f:
        f.writelines(header)
        f.writelines(new_data_lines)

    print(f"Generated EPW: {epw_out_path}")

if __name__ == "__main__":
    csv_files = [f for f in os.listdir(WITH_OCC_DIR) if f.startswith("day_") and f.endswith(".csv")]
    for fname in csv_files:
        day_num = 4 if "day_4" in fname else 3
        target_day = 28 if day_num == 4 else 27
        csv_path = os.path.join(WITH_OCC_DIR, fname)
        out_epw_name = fname.replace(".csv", "_weather.epw")
        out_epw_path = os.path.join(WEATHER_DIR, out_epw_name)
        create_epw_for_dataset(csv_path, target_month=7, target_day=target_day, epw_out_path=out_epw_path)
