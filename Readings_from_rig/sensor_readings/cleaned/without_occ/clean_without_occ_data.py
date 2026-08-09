"""
Data Cleaning Script — Without Occupancy Datasets (Appendix A)
=============================================================
Applies the 4-stage data cleaning pipeline (Appendix A) across ALL numerical sensor channels:
  1. A.1 Hard Range Masking (Temp: [5, 50]°C, RH: [0, 100]%, CO2: [300, 850] ppm)
  2. A.2 Rolling 3-sigma Gaussian Outlier Filter (2-min centered window = 24 samples)
  3. A.3 Linear NaN Interpolation
  4. A.4 Exponential Moving Average (EMA) Noise Suppression (alpha = 0.10)
"""

import os
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLEANED_WITHOUT_DIR = SCRIPT_DIR
RAW_WITHOUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "raw", "without_occ"))

RANGE_LIMITS = {
    "_t": (5.0, 50.0),      # Temperature (°C)
    "_h": (0.0, 100.0),     # Relative Humidity (%)
    "_c": (300.0, 850.0)    # CO2 Concentration (ppm)
}

def clean_series(series, min_val, max_val, window=24, sigma_mult=3.0, ema_alpha=0.10):
    s_raw = series.copy()

    # ── Stage 1: Hard Range Masking ──────────────────────────────────────────
    s_masked = s_raw.apply(lambda v: v if (pd.notnull(v) and min_val <= v <= max_val) else np.nan)

    # ── Stage 2: Rolling 3-Sigma Gaussian Outlier Filter ─────────────────────
    r_mean = s_masked.rolling(window=window, center=True, min_periods=3).mean()
    r_std  = s_masked.rolling(window=window, center=True, min_periods=3).std()
    r_std  = r_std.fillna(1.0).replace(0.0, 1e-6)

    diff = (s_masked - r_mean).abs()
    outlier_mask = diff > (sigma_mult * r_std)

    s_filtered = s_masked.copy()
    s_filtered[outlier_mask] = np.nan

    # ── Stage 3: Linear NaN Interpolation ─────────────────────────────────────
    s_interp = s_filtered.interpolate(method='linear', limit_direction='both')

    # ── Stage 4: Exponential Moving Average (EMA) Smoothing ──────────────────
    s_ema = s_interp.ewm(alpha=ema_alpha, adjust=False).mean()

    return s_ema

def process_raw_dataset(raw_filename):
    base_name = raw_filename.replace("_raw.csv", "")
    target_clean_name = f"{base_name}.csv"

    raw_path = os.path.join(RAW_WITHOUT_DIR, raw_filename)
    clean_path = os.path.join(CLEANED_WITHOUT_DIR, target_clean_name)

    print(f"Cleaning dataset: {raw_filename} -> {target_clean_name}...")
    df_raw = pd.read_csv(raw_path)
    df_clean = df_raw.copy()

    # Apply 4-stage cleaning to all sensor channels
    for col in df_raw.columns:
        if col == "timestamp":
            continue

        # Determine variable category from column suffix
        min_val, max_val = None, None
        for suffix, limits in RANGE_LIMITS.items():
            if col.endswith(suffix):
                min_val, max_val = limits
                break

        if min_val is not None and max_val is not None:
            if pd.api.types.is_numeric_dtype(df_raw[col]):
                df_clean[col] = clean_series(df_raw[col], min_val, max_val).round(2)

    # Calculate spatial weighted zone target columns
    if "room_1_t" in df_clean.columns and "room_2_t" in df_clean.columns and "room_3_t" in df_clean.columns:
        df_clean["Tz_weighted"] = (0.50 * df_clean["room_1_t"] + 0.30 * df_clean["room_2_t"] + 0.20 * df_clean["room_3_t"]).round(2)

    if "room_1_h" in df_clean.columns and "room_2_h" in df_clean.columns and "room_3_h" in df_clean.columns:
        df_clean["RHz_weighted"] = (0.50 * df_clean["room_1_h"] + 0.30 * df_clean["room_2_h"] + 0.20 * df_clean["room_3_h"]).round(2)

    if "room_2_c" in df_clean.columns and "room_3_c" in df_clean.columns:
        df_clean["CO2z_weighted"] = (0.60 * df_clean["room_2_c"] + 0.40 * df_clean["room_3_c"]).round(2)

    # Save cleaned dataset
    df_clean.to_csv(clean_path, index=False)
    print(f"  Successfully saved cleaned dataset: {clean_path}")

if __name__ == "__main__":
    raw_files = sorted([f for f in os.listdir(RAW_WITHOUT_DIR) if f.endswith("_raw.csv")])
    print(f"Found {len(raw_files)} raw without_occ datasets to clean.")
    for f in raw_files:
        process_raw_dataset(f)
    print("ALL WITHOUT_OCC DATASETS CLEANED SUCCESSFULLY.")
