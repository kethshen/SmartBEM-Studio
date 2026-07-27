import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. Directory Setup
STUDIO_DIR = r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio"
RAW_DATA_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig", "experimental_data")
CLEANED_DATA_DIR = os.path.join(RAW_DATA_DIR, "cleaned")
PLOTS_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig", "plots", "data_cleaning")

os.makedirs(CLEANED_DATA_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)

# 2. List of 5 CSV Datasets
DATASETS = [
    {"raw": "Idel_test_2026_07_21.csv", "out": "Idel_test_2026_07_21_cleaned.csv", "name": "Idle Test (2026-07-21)", "prefix": "01_idle"},
    {"raw": "Full Day 1 part 1_2026-07-23.csv", "out": "Full_Day_1_part_1_cleaned.csv", "name": "Full Day 1 Part 1", "prefix": "02_part1"},
    {"raw": "Full day 1 part 2_2026-07-23.csv", "out": "Full_Day_1_part_2_cleaned.csv", "name": "Full Day 1 Part 2", "prefix": "03_part2"},
    {"raw": "Full Day 1 part 5_2026-07-23.csv", "out": "Full_Day_1_part_5_cleaned.csv", "name": "Full Day 1 Part 5", "prefix": "04_part5"},
    {"raw": "Full Day 1 part 6_2026-07-23.csv", "out": "Full_Day_1_part_6_cleaned.csv", "name": "Full Day 1 Part 6", "prefix": "05_part6"},
]

TEMP_COLS = ["room_1_t", "room_2_t", "room_3_t", "supply_t", "return_t", "outside_t"]

def clean_series(series, window=24):
    """
    1. Range masking: Keep 5.0 <= x <= 50.0
    2. Rolling 3-Sigma filter: Flag |x - mean| > 3*std
    3. Linear interpolation for NaNs
    """
    s_raw = series.copy()
    
    # Step 1: Range Masking
    s_masked = s_raw.apply(lambda x: x if 5.0 <= x <= 50.0 else np.nan)
    
    # Step 2: Rolling 3-Sigma Filter
    r_mean = s_masked.rolling(window=window, min_periods=3, center=True).mean()
    r_std = s_masked.rolling(window=window, min_periods=3, center=True).std()
    
    is_outlier = (np.abs(s_masked - r_mean) > 3.0 * r_std)
    s_masked[is_outlier] = np.nan
    
    # Step 3: Linear Interpolation
    s_clean = s_masked.interpolate(method="linear").ffill().bfill()
    return s_clean

# 3. Process Each Dataset
for item in DATASETS:
    raw_path = os.path.join(RAW_DATA_DIR, item["raw"])
    out_path = os.path.join(CLEANED_DATA_DIR, item["out"])
    
    if not os.path.exists(raw_path):
        print(f"File not found: {raw_path}, skipping...")
        continue

    print(f"\nProcessing {item['name']}...")
    df_raw = pd.read_csv(raw_path)
    df_raw.columns = [c.strip() for c in df_raw.columns]
    
    df_cleaned = df_raw.copy()
    
    # Task 1: Clean Temperature Variables
    for col in TEMP_COLS:
        if col in df_raw.columns:
            df_cleaned[col] = clean_series(df_raw[col])
            
    # Task 2: Compute Weighted Zone Temperature (0.50 S1 + 0.30 S2 + 0.20 S3)
    s1 = df_cleaned["room_1_t"] if "room_1_t" in df_cleaned else 0
    s2 = df_cleaned["room_2_t"] if "room_2_t" in df_cleaned else 0
    s3 = df_cleaned["room_3_t"] if "room_3_t" in df_cleaned else 0
    
    df_cleaned["Tz_weighted"] = 0.50 * s1 + 0.30 * s2 + 0.20 * s3
    
    # Save Cleaned CSV File
    df_cleaned.to_csv(out_path, index=False)
    print(f"Saved cleaned CSV: {out_path}")
    
    # Elapsed Time Vector in Minutes
    time_min = np.linspace(0, len(df_raw) * 5 / 60.0, len(df_raw))
    
    # Plot 1: Before-Clean vs After-Clean Comparison (Chamber Sensors)
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, dpi=300)
    fig.suptitle(f"Task 1: Before vs. After Data Cleaning — {item['name']}", fontsize=14, fontweight="bold")
    
    sensor_info = [("room_1_t", "Sensor 1 (Bosch)", "#1f77b4"),
                   ("room_2_t", "Sensor 2 (DHT22)", "#ff7f0e"),
                   ("room_3_t", "Sensor 3 (DHT22)", "#d62728")]
    
    for idx, (col, label, color) in enumerate(sensor_info):
        if col in df_raw.columns:
            axes[idx].plot(time_min, df_raw[col], label=f"Raw Noisy {label}", color="#999999", alpha=0.6, linewidth=1.2)
            axes[idx].plot(time_min, df_cleaned[col], label=f"Cleaned {label}", color=color, linewidth=2.0)
            axes[idx].set_ylabel("Temp (°C)", fontsize=11)
            axes[idx].grid(True, linestyle=":", alpha=0.6)
            axes[idx].legend(loc="upper right", fontsize=10)
            
    axes[2].set_xlabel("Elapsed Time (Minutes)", fontsize=12)
    plt.tight_layout()
    plot_before_after_path = os.path.join(PLOTS_DIR, f"{item['prefix']}_before_vs_after.png")
    plt.savefig(plot_before_after_path)
    plt.close()
    print(f"Saved Before vs After Plot: {plot_before_after_path}")

    # Plot 2: Task 2 Weighted Average Tz vs Individual Cleaned Sensors
    plt.figure(figsize=(12, 6), dpi=300)
    plt.plot(time_min, df_cleaned["room_1_t"], label="Cleaned Sensor 1 (Bosch, Weight 50%)", color="#1f77b4", linewidth=1.5, alpha=0.7)
    plt.plot(time_min, df_cleaned["room_2_t"], label="Cleaned Sensor 2 (DHT22, Weight 30%)", color="#ff7f0e", linewidth=1.5, alpha=0.7)
    plt.plot(time_min, df_cleaned["room_3_t"], label="Cleaned Sensor 3 (DHT22, Weight 20%)", color="#d62728", linewidth=1.5, alpha=0.7)
    plt.plot(time_min, df_cleaned["Tz_weighted"], label="Weighted Zone Temp $T_z$ (0.50 S1 + 0.30 S2 + 0.20 S3)", color="#2ca02c", linewidth=2.8)
    
    # Task 3: Optional EMA Smoothing Overlay for Visual Comparison
    tz_ema = df_cleaned["Tz_weighted"].ewm(span=6).mean()
    plt.plot(time_min, tz_ema, label="EMA Smooth $T_z$ (Span=30s)", color="#9467bd", linewidth=1.8, linestyle="--")

    plt.title(f"Task 2 & 3: Weighted Zone Temp $T_z$ vs. Individual Cleaned Sensors — {item['name']}", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Elapsed Time (Minutes)", fontsize=12)
    plt.ylabel("Chamber Zone Air Temperature (°C)", fontsize=12)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(fontsize=10, loc="upper right")
    plt.tight_layout()
    
    plot_weighted_tz_path = os.path.join(PLOTS_DIR, f"{item['prefix']}_weighted_tz.png")
    plt.savefig(plot_weighted_tz_path)
    plt.close()
    print(f"Saved Weighted Tz Plot: {plot_weighted_tz_path}")

print("\nTasks 1, 2, and 3 execution completed successfully for all 5 CSV datasets!")
