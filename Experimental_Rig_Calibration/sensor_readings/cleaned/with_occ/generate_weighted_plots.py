"""
Spatial Zone Weighted Plot Generator — With Occupancy Datasets
==============================================================
Computes spatial zone averages (Tz, RHz, CO2z) and generates 3 single-axes comparison
plots (weighted_temperature.png, weighted_humidity.png, weighted_co2.png)
per dataset in `plots/day_x_p_y/`.

Weights Configuration:
  - Day 3 Take 1 & 2 (day_3_p_1, day_3_p_2):
      Tz   = 0.50*S1 + 0.30*S2 + 0.20*S3
      RHz  = 0.50*S1 + 0.30*S2 + 0.20*S3
      CO2z = 0.60*S2 + 0.40*S3
  - Day 3 Take 3 & 4 (day_3_p_3, day_3_p_4 — S3 Offline):
      Tz   = 0.60*S1 + 0.40*S2
      RHz  = 0.60*S1 + 0.40*S2
      CO2z = S2
  - All Day 4 Datasets (day_4_p_1 through day_4_p_6 — S3 Offline):
      Tz   = 0.60*S1 + 0.40*S2
      RHz  = 0.60*S1 + 0.40*S2
      CO2z = S2
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

PALETTE = {
    "S1":       "#3A86EF",  # Light Vibrant Blue
    "S2":       "#2A9D8F",  # Emerald Cyan
    "S3":       "#EB802A",  # Rich Vibrant Orange
    "Weighted": "#5E6370"   # Slate Gray
}

sns.set_theme(style="whitegrid", font="sans-serif")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLEANED_WITH_DIR = SCRIPT_DIR
PLOTS_BASE_DIR = os.path.join(SCRIPT_DIR, "plots")
os.makedirs(PLOTS_BASE_DIR, exist_ok=True)

def process_dataset_weighted(cleaned_filename):
    base_name = cleaned_filename.replace(".csv", "")
    cleaned_csv_path = os.path.join(CLEANED_WITH_DIR, cleaned_filename)

    if not os.path.exists(cleaned_csv_path):
        print(f"Warning: Cleaned file {cleaned_csv_path} not found. Skipping.")
        return

    df = pd.read_csv(cleaned_csv_path)

    # Time axis in minutes
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
        t_min = (ts - ts.iloc[0]).dt.total_seconds() / 60.0
    else:
        t_min = df.index * 5.0 / 60.0

    # Determine weighting rule based on dataset
    has_s3_active = (base_name in ["day_3_p_1", "day_3_p_2"])

    # ── Read Pre-Calculated Spatial Weighted Target Columns ──────────────────
    df["Tz"]   = df["Tz_weighted"] if "Tz_weighted" in df.columns else (0.50 * df["room_1_t"] + 0.30 * df["room_2_t"] + 0.20 * df["room_3_t"])
    df["RHz"]  = df["RHz_weighted"] if "RHz_weighted" in df.columns else (0.50 * df["room_1_h"] + 0.30 * df["room_2_h"] + 0.20 * df["room_3_h"])
    df["CO2z"] = df["CO2z_weighted"] if "CO2z_weighted" in df.columns else df["room_2_c"]

    dataset_plot_dir = os.path.join(PLOTS_BASE_DIR, base_name)
    os.makedirs(dataset_plot_dir, exist_ok=True)

    print(f"Generating weighted plots for with_occ dataset: {base_name}...")

    # ── 1. Weighted Temperature Plot ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    if "room_1_t" in df.columns:
        ax.plot(t_min, df["room_1_t"], label="S1", color=PALETTE["S1"], lw=1.4, alpha=0.7)
    if "room_2_t" in df.columns:
        ax.plot(t_min, df["room_2_t"], label="S2", color=PALETTE["S2"], lw=1.4, alpha=0.7)
    if "room_3_t" in df.columns and has_s3_active:
        ax.plot(t_min, df["room_3_t"], label="S3", color=PALETTE["S3"], lw=1.4, alpha=0.7)
    ax.plot(t_min, df["Tz"], label="Tz (Weighted)", color=PALETTE["Weighted"], lw=2.2, alpha=0.95)

    ax.set_title(f"{base_name} — Spatial Zone Weighted Temperature (Tz)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Temperature (°C)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Elapsed Time (minutes)", fontsize=11, fontweight="bold")
    ax.set_ylim(15, 35)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(dataset_plot_dir, "weighted_temperature.png"), dpi=200, bbox_inches="tight")
    plt.close()

    # ── 2. Weighted Humidity Plot ────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    if "room_1_h" in df.columns:
        ax.plot(t_min, df["room_1_h"], label="S1", color=PALETTE["S1"], lw=1.4, alpha=0.7)
    if "room_2_h" in df.columns:
        ax.plot(t_min, df["room_2_h"], label="S2", color=PALETTE["S2"], lw=1.4, alpha=0.7)
    if "room_3_h" in df.columns and has_s3_active:
        ax.plot(t_min, df["room_3_h"], label="S3", color=PALETTE["S3"], lw=1.4, alpha=0.7)
    ax.plot(t_min, df["RHz"], label="RHz (Weighted)", color=PALETTE["Weighted"], lw=2.2, alpha=0.95)

    ax.set_title(f"{base_name} — Spatial Zone Weighted Relative Humidity (RHz)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Relative Humidity (%)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Elapsed Time (minutes)", fontsize=11, fontweight="bold")
    ax.set_ylim(20, 100)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(dataset_plot_dir, "weighted_humidity.png"), dpi=200, bbox_inches="tight")
    plt.close()

    # ── 3. Weighted CO2 Plot ──────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    if "room_2_c" in df.columns:
        ax.plot(t_min, df["room_2_c"], label="S2", color=PALETTE["S2"], lw=1.4, alpha=0.7)
    if "room_3_c" in df.columns and has_s3_active:
        ax.plot(t_min, df["room_3_c"], label="S3", color=PALETTE["S3"], lw=1.4, alpha=0.7)
    ax.plot(t_min, df["CO2z"], label="CO2z (Weighted)", color=PALETTE["Weighted"], lw=2.2, alpha=0.95)

    ax.set_title(f"{base_name} — Spatial Zone Weighted CO2 Concentration (CO2z)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("CO2 Concentration (ppm)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Elapsed Time (minutes)", fontsize=11, fontweight="bold")
    ax.set_ylim(300, 850)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(dataset_plot_dir, "weighted_co2.png"), dpi=200, bbox_inches="tight")
    plt.close()

    print(f"  Generated 3 weighted plots in: {dataset_plot_dir}")

if __name__ == "__main__":
    clean_files = sorted([f for f in os.listdir(CLEANED_WITH_DIR) if f.endswith(".csv")])
    print(f"Found {len(clean_files)} cleaned with_occ datasets to process.")
    for f in clean_files:
        process_dataset_weighted(f)
