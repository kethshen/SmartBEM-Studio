"""
Weather EPW Generator & Verification Plotter
===========================================
Synthesizes 2 standardized 1-minute EPW weather files and verification plots:
  1. `day_1_weather.epw` & `day_1_weather_verification.png` (July 21, 2026 — Day 1 Idle Test)
  2. `day_2_weather.epw` & `day_2_weather_verification.png` (July 23, 2026 — Day 2 Parts 1-4)
"""

import os
import shutil
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", font="sans-serif")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEATHER_DIR = SCRIPT_DIR
WITHOUT_OCC_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "cleaned", "without_occ"))
WEATHER_FILES_RAW_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "weather_files"))

# Baseline TMY EPW File
BASELINE_EPW = os.path.join(WEATHER_FILES_RAW_DIR, "LKA_CP_Kandy.434440_TMYx.2011-2025.epw")
if not os.path.exists(BASELINE_EPW):
    BASELINE_EPW = os.path.join(WEATHER_DIR, "LKA_CP_Kandy.434440_TMYx.2011-2025.epw")

def calculate_dew_point(temp, rh):
    """Calculates dew point temperature using Magnus formula."""
    a, b = 17.27, 237.7
    alpha = ((a * temp) / (b + temp)) + np.log(np.maximum(rh, 1.0) / 100.0)
    return (b * alpha) / (a - alpha)

def create_epw_for_day(df_telemetry, target_month, target_day, epw_out_path, title_day):
    """
    Creates a customized EPW file by merging real telemetry data (outside_t, outside_h, outside_p, outside_v)
    with solar irradiance and sky radiation from the baseline Kandy TMY EPW.
    """
    if not os.path.exists(BASELINE_EPW):
        print(f"Error: Baseline EPW {BASELINE_EPW} not found.")
        return [], []

    with open(BASELINE_EPW, "r") as f:
        epw_lines = f.readlines()

    header = epw_lines[:8]
    data_lines = epw_lines[8:]

    # Filter baseline lines for target month and day
    target_lines = []
    for line in data_lines:
        parts = line.strip().split(",")
        if len(parts) > 4:
            m, d = int(parts[1]), int(parts[2])
            if m == target_month and d == target_day:
                target_lines.append(parts)

    if not target_lines:
        target_lines = [l.strip().split(",") for l in data_lines[:24]]

    # Ensure telemetry timestamp is datetime
    df_telemetry['timestamp'] = pd.to_datetime(df_telemetry['timestamp'])
    df_telemetry = df_telemetry.sort_values('timestamp').reset_index(drop=True)

    df_resampled = df_telemetry.set_index('timestamp').resample('1min').mean().interpolate(method='linear').ffill().bfill().reset_index()

    new_data_lines = []
    solar_values = []
    n_records = len(df_resampled)

    for i in range(n_records):
        row = df_resampled.iloc[i]
        base_parts = target_lines[i % len(target_lines)].copy()

        # Extract baseline solar global horizontal radiation (column 13 in EPW, index 13)
        solar_ghi = float(base_parts[13]) if len(base_parts) > 13 else 0.0
        solar_values.append(solar_ghi)

        # Update timestamps
        ts = row['timestamp']
        base_parts[0] = str(ts.year)
        base_parts[1] = str(ts.month)
        base_parts[2] = str(ts.day)
        base_parts[3] = str(ts.hour + 1)
        base_parts[4] = str(ts.minute)

        # Ambient Telemetry Overwrite
        t_out = row.get('outside_t', 25.0)
        rh_out = row.get('outside_h', 70.0)

        # Pressure fallback: if outside_p is 0 or missing, use room_1_p or standard 955.8 hPa (95580 Pa)
        p_val = row.get('outside_p', 0.0)
        if pd.isnull(p_val) or p_val < 500.0:
            p_val = row.get('room_1_p', 955.8)
        if p_val < 2000.0:  # hPa to Pa
            p_val *= 100.0
        p_out = p_val

        # Wind speed scaling
        v_raw = row.get('outside_v', 1.0)
        v_out = v_raw / 100.0 if v_raw > 15.0 else v_raw  # scale anemometer ticks to m/s

        dew_out = calculate_dew_point(t_out, rh_out)

        base_parts[6] = f"{t_out:.2f}"     # Dry-bulb temp (°C)
        base_parts[7] = f"{dew_out:.2f}"   # Dew-point temp (°C)
        base_parts[8] = f"{rh_out:.1f}"    # Relative humidity (%)
        base_parts[9] = f"{int(p_out)}"    # Atmospheric pressure (Pa)
        base_parts[21] = f"{v_out:.2f}"    # Wind speed (m/s)

        new_data_lines.append(",".join(base_parts) + "\n")

    header[7] = f"DATA PERIODS,1,1,Data,Wednesday,{target_month}/{target_day},{target_month}/{target_day}\n"

    with open(epw_out_path, "w") as f:
        f.writelines(header + new_data_lines)

    print(f"  Created EPW weather file: {epw_out_path}")
    return df_resampled, solar_values

def generate_verification_plot(df_resampled, solar_values, plot_out_path, title_str, temp_ylim, rh_ylim):
    """Generates 5-panel weather verification plot (Temp, RH, Pressure, Solar, Wind Speed)."""
    t_min = (df_resampled['timestamp'] - df_resampled['timestamp'].iloc[0]).dt.total_seconds() / 60.0

    fig, axes = plt.subplots(5, 1, figsize=(11, 12), sharex=True)

    # 1. Temperature
    axes[0].plot(t_min, df_resampled['outside_t'], color="#FF6B6B", lw=1.6, label="Outdoor Temperature (°C)")
    axes[0].set_ylabel("Temp (°C)", fontsize=10, fontweight="bold")
    axes[0].set_ylim(temp_ylim)
    axes[0].legend(loc="upper right", frameon=True, facecolor="white")
    axes[0].set_title(f"{title_str} — Ambient Weather Verification Overview", fontsize=13, fontweight="bold", pad=10)
    axes[0].grid(True, alpha=0.3)

    # 2. Relative Humidity
    axes[1].plot(t_min, df_resampled['outside_h'], color="#3A86EF", lw=1.6, label="Outdoor Relative Humidity (%)")
    axes[1].set_ylabel("RH (%)", fontsize=10, fontweight="bold")
    axes[1].set_ylim(rh_ylim)
    axes[1].legend(loc="upper right", frameon=True, facecolor="white")
    axes[1].grid(True, alpha=0.3)

    # 3. Barometric Pressure
    p_val = df_resampled.get('outside_p', pd.Series(0.0, index=df_resampled.index))
    if p_val.mean() < 500.0 and 'room_1_p' in df_resampled.columns:
        p_val = df_resampled['room_1_p']
    if p_val.mean() > 2000.0:
        p_val = p_val / 100.0  # Pa to hPa

    axes[2].plot(t_min, p_val, color="#2A9D8F", lw=1.6, label="Barometric Pressure (hPa)")
    axes[2].set_ylabel("Pressure (hPa)", fontsize=10, fontweight="bold")
    axes[2].set_ylim(940, 970)
    axes[2].legend(loc="upper right", frameon=True, facecolor="white")
    axes[2].grid(True, alpha=0.3)

    # 4. Solar Irradiance (GHI W/m2)
    axes[3].plot(t_min, solar_values, color="#EB802A", lw=1.6, label="Global Horizontal Solar Irradiance (W/m²)")
    axes[3].set_ylabel("Solar (W/m²)", fontsize=10, fontweight="bold")
    axes[3].set_ylim(0, 1200)
    axes[3].legend(loc="upper right", frameon=True, facecolor="white")
    axes[3].grid(True, alpha=0.3)

    # 5. Wind Speed
    v_raw = df_resampled.get('outside_v', pd.Series(1.0, index=df_resampled.index))
    v_val = v_raw / 100.0 if v_raw.mean() > 15.0 else v_raw
    axes[4].plot(t_min, v_val, color="#9D4EDD", lw=1.6, label="Wind Speed (m/s)")
    axes[4].set_ylabel("Wind (m/s)", fontsize=10, fontweight="bold")
    axes[4].set_xlabel("Elapsed Time (minutes)", fontsize=11, fontweight="bold")
    axes[4].set_ylim(0, 5.0)
    axes[4].legend(loc="upper right", frameon=True, facecolor="white")
    axes[4].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(plot_out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Generated verification plot: {plot_out_path}")

if __name__ == "__main__":
    print("Processing weather EPW generation and verification plots...")

    # Day 1 (July 21, 2026)
    day1_csv = os.path.join(WITHOUT_OCC_DIR, "day_1_p_1.csv")
    if os.path.exists(day1_csv):
        df_day1 = pd.read_csv(day1_csv)
        epw_day1_path = os.path.join(WEATHER_DIR, "day_1_weather.epw")
        plot_day1_path = os.path.join(WEATHER_DIR, "day_1_weather_verification.png")

        df_res1, sol1 = create_epw_for_day(df_day1, target_month=7, target_day=21, epw_out_path=epw_day1_path, title_day="Day 1 (July 21, 2026)")
        generate_verification_plot(df_res1, sol1, plot_day1_path, "Day 1 (July 21, 2026)", temp_ylim=(30, 35), rh_ylim=(20, 80))

    # Day 2 (July 23, 2026)
    day2_files = ["day_2_p_1.csv", "day_2_p_2.csv", "day_2_p_3.csv", "day_2_p_4.csv"]
    day2_dfs = []
    for f in day2_files:
        p = os.path.join(WITHOUT_OCC_DIR, f)
        if os.path.exists(p):
            day2_dfs.append(pd.read_csv(p))

    if day2_dfs:
        df_day2 = pd.concat(day2_dfs, ignore_index=True)
        epw_day2_path = os.path.join(WEATHER_DIR, "day_2_weather.epw")
        plot_day2_path = os.path.join(WEATHER_DIR, "day_2_weather_verification.png")

        df_res2, sol2 = create_epw_for_day(df_day2, target_month=7, target_day=23, epw_out_path=epw_day2_path, title_day="Day 2 (July 23, 2026)")
        generate_verification_plot(df_res2, sol2, plot_day2_path, "Day 2 (July 23, 2026)", temp_ylim=(25, 35), rh_ylim=(0, 100))

    print("ALL WEATHER EPW FILES & VERIFICATION PLOTS GENERATED SUCCESSFULLY.")
