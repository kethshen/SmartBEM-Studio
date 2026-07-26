import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLOTS_DIR = os.path.join(BASE_DIR, "plots", "cleaning_validation")
os.makedirs(PLOTS_DIR, exist_ok=True)

# List of files to process
FILE_SPECS = [
    {"part": "Part 1", "filename": "Full Day 1 part 1_2026-07-23.csv"},
    {"part": "Part 2", "filename": "Full day 1 part 2_2026-07-23.csv"},
    {"part": "Part 5", "filename": "Full Day 1 part 5_2026-07-23.csv"},
    {"part": "Part 6", "filename": "Full Day 1 part 6_2026-07-23.csv"},
]

TEMP_COLS = ["outside_t", "room_1_t", "room_2_t", "room_3_t", "supply_t", "return_t"]

def clean_series(series, min_val=5.0, max_val=50.0, iqr_window=15, iqr_multiplier=3.0):
    """
    Cleans a temperature series:
    1. Replaces values outside [min_val, max_val] with NaN (handles ADC glitches & zeros).
    2. Uses rolling median & IQR to detect and remove sharp spikes.
    3. Interpolates short NaN gaps (up to 5 timesteps = 25s).
    """
    s_raw = series.copy()
    
    # 1. Range clipping
    s_clipped = s_raw.apply(lambda v: v if (min_val <= v <= max_val) else np.nan)
    
    # 2. Rolling IQR spike detection
    rolling_med = s_clipped.rolling(window=iqr_window, center=True, min_periods=3).median()
    rolling_std = s_clipped.rolling(window=iqr_window, center=True, min_periods=3).std()
    
    # Identify outliers where deviation from rolling median > iqr_multiplier * rolling_std
    diff = (s_clipped - rolling_med).abs()
    outlier_mask = diff > (iqr_multiplier * rolling_std.fillna(1.0))
    
    s_filtered = s_clipped.copy()
    s_filtered[outlier_mask] = np.nan
    
    # 3. Small gap interpolation (limit 5 points)
    s_interp = s_filtered.interpolate(method='linear', limit=5)
    
    return s_interp

def process_and_plot():
    processed_data = {}
    
    for spec in FILE_SPECS:
        part_name = spec["part"]
        filepath = os.path.join(BASE_DIR, spec["filename"])
        
        if not os.path.exists(filepath):
            print(f"Warning: File not found: {filepath}")
            continue
            
        df_raw = pd.read_csv(filepath)
        df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'])
        df_raw = df_raw.sort_values('timestamp').reset_index(drop=True)
        
        # Calculate time in minutes from start of part
        t_min = (df_raw['timestamp'] - df_raw['timestamp'].iloc[0]).dt.total_seconds() / 60.0
        df_raw['time_min'] = t_min
        
        df_clean = df_raw.copy()
        
        # Clean each temperature channel
        for col in TEMP_COLS:
            if col in df_raw.columns:
                df_clean[col] = clean_series(df_raw[col])
            else:
                df_clean[col] = np.nan
                
        # Calculate weighted zone temperature Tz = 0.6 * room_1_t + 0.4 * room_2_t
        # (Handling potential NaNs gracefully)
        r1 = df_clean['room_1_t']
        r2 = df_clean['room_2_t']
        df_clean['weighted_Tz'] = 0.6 * r1.fillna(r2) + 0.4 * r2.fillna(r1)
        
        # Apply 30s EMA (span=6 timesteps @ 5s intervals) for final smoothed channels
        df_ema = df_clean.copy()
        for col in TEMP_COLS + ['weighted_Tz']:
            df_ema[col + '_ema'] = df_clean[col].ewm(span=6, adjust=False).mean()
            
        processed_data[part_name] = {
            "raw": df_raw,
            "clean": df_clean,
            "ema": df_ema
        }
        
    print(f"Data processed for {len(processed_data)} parts.")

    # -------------------------------------------------------------
    # PLOT GENERATION (Before vs. After Cleaning for Each Variable)
    # -------------------------------------------------------------
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    
    variables_to_plot = [
        ("room_1_t", "Sensor 1 Temp (°C) — Bosch"),
        ("room_2_t", "Sensor 2 Temp (°C)"),
        ("room_3_t", "Sensor 3 Temp (°C)"),
        ("outside_t", "Outdoor Temp (°C)"),
        ("supply_t", "AHU Supply Temp (°C)"),
        ("return_t", "AHU Return Temp (°C)"),
        ("weighted_Tz", "Weighted Zone Temp Tz (°C) — 0.6*S1 + 0.4*S2")
    ]
    
    for col, label in variables_to_plot:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=False, sharey=False)
        fig.suptitle(f"Before vs. After Cleaning — {label}", fontsize=16, fontweight='bold', y=0.98)
        
        ax_list = axes.flatten()
        
        for idx, spec in enumerate(FILE_SPECS):
            part_name = spec["part"]
            ax = ax_list[idx]
            
            if part_name not in processed_data:
                ax.text(0.5, 0.5, "Data Unavailable", ha='center', va='center')
                continue
                
            pdata = processed_data[part_name]
            df_r = pdata["raw"]
            df_e = pdata["ema"]
            
            # Raw data
            if col in df_r.columns:
                ax.plot(df_r['time_min'], df_r[col], color='red', alpha=0.5, linewidth=1.2, label='Raw (Uncleaned)')
            
            # Cleaned & EMA smoothed data
            col_target = col + '_ema' if (col + '_ema') in df_e.columns else col
            if col_target in df_e.columns:
                ax.plot(df_e['time_min'], df_e[col_target], color='blue', linewidth=2.0, label='Cleaned + 30s EMA')
                
            ax.set_title(f"{part_name}", fontsize=12, fontweight='bold')
            ax.set_xlabel("Time (minutes)", fontsize=10)
            ax.set_ylabel("Temperature (°C)", fontsize=10)
            ax.legend(loc='upper right', frameon=True)
            ax.grid(True, linestyle='--', alpha=0.6)
            
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        out_filename = os.path.join(PLOTS_DIR, f"before_vs_after_{col}.png")
        plt.savefig(out_filename, dpi=150)
        plt.close()
        print(f"Saved plot: {out_filename}")

    # Additional Overview Plot per Part (All Cleaned Variables Overlaid)
    for spec in FILE_SPECS:
        part_name = spec["part"]
        if part_name not in processed_data:
            continue
            
        df_e = processed_data[part_name]["ema"]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_title(f"Cleaned Temperature Profiles Overview — {part_name}", fontsize=14, fontweight='bold')
        
        ax.plot(df_e['time_min'], df_e['outside_t_ema'], label='Outdoor (T_out)', color='orange', linewidth=2)
        ax.plot(df_e['time_min'], df_e['weighted_Tz_ema'], label='Weighted Zone (T_z)', color='darkblue', linewidth=2.5)
        ax.plot(df_e['time_min'], df_e['room_1_t_ema'], label='Sensor 1 (Bosch)', color='blue', linestyle='--', linewidth=1.5)
        ax.plot(df_e['time_min'], df_e['room_2_t_ema'], label='Sensor 2', color='cyan', linestyle='--', linewidth=1.5)
        ax.plot(df_e['time_min'], df_e['supply_t_ema'], label='Supply Air (T_sa)', color='green', linewidth=2)
        ax.plot(df_e['time_min'], df_e['return_t_ema'], label='Return Air (T_ret)', color='red', linewidth=1.8)
        
        ax.set_xlabel("Time (minutes)", fontsize=11)
        ax.set_ylabel("Temperature (°C)", fontsize=11)
        ax.legend(loc='best', frameon=True)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        out_filename = os.path.join(PLOTS_DIR, f"cleaned_overview_{part_name.replace(' ', '_').lower()}.png")
        plt.savefig(out_filename, dpi=150)
        plt.close()
        print(f"Saved overview plot: {out_filename}")

if __name__ == "__main__":
    process_and_plot()
