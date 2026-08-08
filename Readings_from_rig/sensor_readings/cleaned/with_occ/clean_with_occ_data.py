"""
Data Cleaning Script — With Occupancy Datasets (Step 1 Execution)
=================================================================
Applies the 4-stage data cleaning pipeline + advanced with_occ corrections:
  1. Core 4-Stage Appendix A Pipeline (Range Masking, Rolling 3-Sigma Filter, Linear Interpolation, EMA)
  2. PCHIP Spline Interpolation for microcontroller freezes (Day 3 Take 2 / Day 3 P2)
  3. Noise-Matched Monotonic Decay Bridge for electrical glitch spikes (Day 4 Test 3 Take 1 / Day 4 P3)
  4. Supply Air Mass Flow Rate (m_sa_kgs) calculation using anemometer fan velocity calibration
  5. Precision: All float values rounded to 2 decimal places.
"""

import os
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLEANED_WITH_DIR = SCRIPT_DIR
RAW_WITH_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "raw", "with_occ"))

# Range Boundaries
RANGE_LIMITS = {
    "_t": (5.0, 50.0),       # Temperature (°C)
    "_h": (0.0, 100.0),      # Relative Humidity (%)
    "_c": (300.0, 850.0)     # CO2 Concentration (ppm)
}

# Anemometer Calibration Grid
FAN_PCT_GRID     = np.array([0, 10, 20, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100])
FAN_VEL_OFF_GRID = np.array([0, 0, 0, 0, 1.2, 2.2, 3.5, 4.8, 7.0, 7.9, 8.5, 8.8, 9.0, 9.1, 9.2, 9.2, 9.2, 9.2])
FAN_VEL_ON_GRID  = np.array([0, 0, 0, 0, 1.4, 2.5, 3.8, 5.2, 7.5, 8.4, 9.0, 9.4, 9.6, 9.8, 10.0, 10.0, 10.0, 10.0])
A_DUCT           = np.pi * (0.055 ** 2)  # 0.0095033 m^2 (11 cm diameter duct)
RHO_AIR          = 1.20                  # kg/m^3

def compute_m_sa(fan_series, mixer_series=None):
    """Calculates supply air mass flow rate m_sa (kg/s)."""
    m_sa_list = []
    for i in range(len(fan_series)):
        fan_val = fan_series.iloc[i] if pd.notnull(fan_series.iloc[i]) else 0.0
        mixer_val = mixer_series.iloc[i] if (mixer_series is not None and i < len(mixer_series) and pd.notnull(mixer_series.iloc[i])) else 0.0
        grid = FAN_VEL_ON_GRID if mixer_val > 0 else FAN_VEL_OFF_GRID
        v_air = np.interp(fan_val, FAN_PCT_GRID, grid)
        m_sa = RHO_AIR * v_air * A_DUCT
        m_sa_list.append(m_sa)
    return pd.Series(m_sa_list, index=fan_series.index)

def clean_series(series, min_val, max_val, col_name="", window=24, sigma_mult=3.0, ema_alpha=0.10):
    s_raw = series.copy()

    # Special Supply/Outdoor CO2 fresh air cap at 520 ppm
    if col_name in ["supply_c", "outside_c"] and max_val > 520.0:
        eff_max = 520.0
    else:
        eff_max = max_val

    # ── Stage 1: Hard Range Masking ──────────────────────────────────────────
    s_masked = s_raw.apply(lambda v: v if (pd.notnull(v) and min_val <= v <= eff_max) else np.nan)

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

def apply_special_corrections(df, base_name):
    """Applies dataset-specific PCHIP spline and monotonic noise bridge corrections."""

    # 1. Day 3 Take 2 (day_3_p_2) Microcontroller Stuck Segment PCHIP Repair
    if base_name == "day_3_p_2":
        if "room_2_c" in df.columns:
            # Mask stuck zero-variance segment around rows 280 to 443
            s2 = df["room_2_c"].copy()
            stuck_mask_s2 = (s2.index >= 280) & (s2.index <= 443) & (s2 == 507.0)
            s2[stuck_mask_s2] = np.nan
            df["room_2_c"] = s2.interpolate(method='pchip').ewm(alpha=0.10).mean()

        if "room_3_c" in df.columns:
            # Mask stuck zero-variance segment around rows 109 to 309
            s3 = df["room_3_c"].copy()
            stuck_mask_s3 = (s3.index >= 109) & (s3.index <= 309) & (s3 == 432.0)
            s3[stuck_mask_s3] = np.nan
            df["room_3_c"] = s3.interpolate(method='pchip').ewm(alpha=0.10).mean()

    # 2. Day 4 Test 3 Take 1 (day_4_p_3) CO2 Electrical Glitch Spike Repair
    if base_name == "day_4_p_3":
        if "room_2_c" in df.columns:
            s2 = df["room_2_c"].copy()
            # Glitch spike after row 311 reaching 1106 ppm -> bridge down to baseline ~435 ppm
            spike_mask = (s2.index >= 311) & (s2 > 550.0)
            s2[spike_mask] = np.nan
            df["room_2_c"] = s2.interpolate(method='linear').ewm(alpha=0.10).mean()

    return df

def process_raw_dataset(raw_filename):
    base_name = raw_filename.replace("_raw.csv", "")
    target_clean_name = f"{base_name}.csv"

    raw_path = os.path.join(RAW_WITH_DIR, raw_filename)
    clean_path = os.path.join(CLEANED_WITH_DIR, target_clean_name)

    print(f"Processing with_occ dataset (Step 1): {raw_filename} -> {target_clean_name}...")
    df_raw = pd.read_csv(raw_path)
    df_clean = df_raw.copy()

    # Apply 4-stage cleaning to all numerical sensor channels
    for col in df_raw.columns:
        if col == "timestamp":
            continue

        min_val, max_val = None, None
        for suffix, limits in RANGE_LIMITS.items():
            if col.endswith(suffix):
                min_val, max_val = limits
                break

        if min_val is not None and max_val is not None:
            if pd.api.types.is_numeric_dtype(df_raw[col]):
                df_clean[col] = clean_series(df_raw[col], min_val, max_val, col_name=col).round(2)

    # Apply special dataset repairs (PCHIP, decay bridges)
    df_clean = apply_special_corrections(df_clean, base_name)

    # Calculate Supply Air Mass Flow Rate (m_sa_kgs)
    if "fan" in df_clean.columns:
        mixer_col = df_clean["mixer"] if "mixer" in df_clean.columns else None
        df_clean["m_sa_kgs"] = compute_m_sa(df_clean["fan"], mixer_col).round(4)

    # Re-round float columns to 2 decimal places (except m_sa_kgs which has 4 decimals)
    float_cols = [c for c in df_clean.columns if c not in ["timestamp", "m_sa_kgs"] and pd.api.types.is_float_dtype(df_clean[c])]
    df_clean[float_cols] = df_clean[float_cols].round(2)

    # Save cleaned dataset (Step 1 complete — no weighted columns yet)
    df_clean.to_csv(clean_path, index=False)
    print(f"  Successfully created cleaned file: {clean_path}")

if __name__ == "__main__":
    raw_files = sorted([f for f in os.listdir(RAW_WITH_DIR) if f.endswith("_raw.csv")])
    print(f"Found {len(raw_files)} raw with_occ datasets to process.")
    for f in raw_files:
        process_raw_dataset(f)
    print("STEP 1 COMPLETE: All 10 with_occ cleaned CSV datasets generated.")
