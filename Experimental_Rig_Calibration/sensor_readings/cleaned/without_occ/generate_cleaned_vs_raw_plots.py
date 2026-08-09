"""
Seaborn Raw vs. Cleaned Comparison Plot Generator — Without Occupancy
====================================================================
Generates 3 separate multi-subplot figures (temperature.png, humidity.png, co2.png)
per dataset inside subdirectories under `plots/day_x_p_y/`.

Subplots per channel:
  - Raw: Dashed line (ls="--", alpha=0.7)
  - Cleaned: Solid line (ls="-", alpha=0.9, lw=1.6)
Both use the EXACT SAME color per channel from the 8-color palette!
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ── Master 8-Color Palette ───────────────────────────────────────────────────
PALETTE = {
    "S1":      "#3A86EF",  # Light Vibrant Blue
    "S2":      "#2A9D8F",  # Emerald Cyan
    "S3":      "#EB802A",  # Rich Vibrant Orange
    "Outdoor": "#FF6B6B",  # Light Coral Red
    "Supply":  "#9D4EDD",  # Crisp Light Purple
    "Return":  "#264653",  # Teal Slate
    "Aux1":    "#E63946",  # Crimson Red
    "Aux2":    "#6B2D5C"   # Dark Magenta
}

sns.set_theme(style="whitegrid", font="sans-serif")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLEANED_WITHOUT_DIR = SCRIPT_DIR
RAW_WITHOUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "raw", "without_occ"))
PLOTS_BASE_DIR = os.path.join(SCRIPT_DIR, "plots")
os.makedirs(PLOTS_BASE_DIR, exist_ok=True)

def generate_channel_subplots(df_raw, df_clean, channels, title_suffix, ylabel, out_filepath):
    """
    Creates a figure with N stacked subplots, one per channel in `channels`.
    `channels` format: [("S1", "room_1_t"), ("S2", "room_2_t"), ...]
    """
    n_ch = len(channels)
    fig, axes = plt.subplots(n_ch, 1, figsize=(12, 2.5 * n_ch), sharex=True)
    if n_ch == 1:
        axes = [axes]

    # Time axis in minutes
    if "timestamp" in df_clean.columns:
        ts = pd.to_datetime(df_clean["timestamp"])
        t_min_clean = (ts - ts.iloc[0]).dt.total_seconds() / 60.0
    else:
        t_min_clean = df_clean.index * 5.0 / 60.0

    if "timestamp" in df_raw.columns:
        ts_r = pd.to_datetime(df_raw["timestamp"])
        t_min_raw = (ts_r - ts_r.iloc[0]).dt.total_seconds() / 60.0
    else:
        t_min_raw = df_raw.index * 5.0 / 60.0

    for idx, (label, col) in enumerate(channels):
        ax = axes[idx]
        color = PALETTE.get(label, "#333333")

        if col in df_raw.columns:
            ax.plot(t_min_raw, df_raw[col], label=f"Raw {label}", color=color, ls="--", lw=1.2, alpha=0.7)
        if col in df_clean.columns:
            ax.plot(t_min_clean, df_clean[col], label=f"Cleaned {label}", color=color, ls="-", lw=1.6, alpha=0.9)

        ax.set_ylabel(ylabel, fontsize=10, fontweight="bold")
        ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_title(f"Channel: {label}", fontsize=11, fontweight="bold", loc="left", pad=4)

    axes[0].set_title(title_suffix, fontsize=13, fontweight="bold", pad=12)
    axes[-1].set_xlabel("Elapsed Time (minutes)", fontsize=11, fontweight="bold")

    plt.tight_layout()
    plt.savefig(out_filepath, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Generated plot: {out_filepath}")

def process_dataset(cleaned_filename):
    base_name = cleaned_filename.replace(".csv", "")
    raw_filename = f"{base_name}_raw.csv"

    cleaned_csv_path = os.path.join(CLEANED_WITHOUT_DIR, cleaned_filename)
    raw_csv_path = os.path.join(RAW_WITHOUT_DIR, raw_filename)

    if not os.path.exists(raw_csv_path):
        print(f"Warning: Raw file {raw_csv_path} not found. Skipping.")
        return

    df_clean = pd.read_csv(cleaned_csv_path)
    df_raw = pd.read_csv(raw_csv_path)

    # Dataset output folder: plots/day_x_p_y/
    dataset_plot_dir = os.path.join(PLOTS_BASE_DIR, base_name)
    os.makedirs(dataset_plot_dir, exist_ok=True)

    print(f"Processing dataset: {base_name}...")

    # 1. Temperature Subplots
    temp_channels = [
        ("S1", "room_1_t"),
        ("S2", "room_2_t"),
        ("S3", "room_3_t"),
        ("Outdoor", "outside_t"),
        ("Supply", "supply_t")
    ]
    generate_channel_subplots(
        df_raw, df_clean, temp_channels,
        f"{base_name} — Raw vs. Cleaned Temperature",
        "Temperature (°C)",
        os.path.join(dataset_plot_dir, "temperature.png")
    )

    # 2. Humidity Subplots
    rh_channels = [
        ("S1", "room_1_h"),
        ("S2", "room_2_h"),
        ("S3", "room_3_h"),
        ("Outdoor", "outside_h"),
        ("Supply", "supply_h")
    ]
    generate_channel_subplots(
        df_raw, df_clean, rh_channels,
        f"{base_name} — Raw vs. Cleaned Relative Humidity",
        "Relative Humidity (%)",
        os.path.join(dataset_plot_dir, "humidity.png")
    )

    # 3. CO2 Subplots
    co2_channels = [
        ("S2", "room_2_c"),
        ("S3", "room_3_c"),
        ("Outdoor", "outside_c"),
        ("Supply", "supply_c")
    ]
    generate_channel_subplots(
        df_raw, df_clean, co2_channels,
        f"{base_name} — Raw vs. Cleaned CO2 Concentration",
        "CO2 (ppm)",
        os.path.join(dataset_plot_dir, "co2.png")
    )

if __name__ == "__main__":
    clean_files = sorted([f for f in os.listdir(CLEANED_WITHOUT_DIR) if f.endswith(".csv")])
    print(f"Found {len(clean_files)} without_occ cleaned datasets.")
    for f in clean_files:
        process_dataset(f)
