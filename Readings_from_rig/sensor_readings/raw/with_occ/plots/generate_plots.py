"""
Seaborn Plotting Script — Raw Datasets (With Occupancy)
======================================================
Generates modern, publication-ready multi-subplot figures for raw sensor data with occupancy.
Palette: Fixed 8-color modern theme.
Labels:
  - In-room sensors: S1 (room_1), S2 (room_2), S3 (room_3)
  - Other channels: Outdoor (outside), Supply (supply), Return (return)
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ── 8-Color Modern Palette (Refined) ─────────────────────────────────────────
PALETTE = {
    "S1":      "#3A86EF",  # Vibrant Light Blue
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
RAW_WITH_DIR = os.path.dirname(SCRIPT_DIR)
PLOTS_DIR = SCRIPT_DIR
os.makedirs(PLOTS_DIR, exist_ok=True)

def generate_seaborn_plot(csv_path):
    filename = os.path.basename(csv_path)
    dataset_title = filename.replace(".csv", "")
    df = pd.read_csv(csv_path)

    # Time axis in minutes
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
        t_min = (ts - ts.iloc[0]).dt.total_seconds() / 60.0
    else:
        t_min = df.index * 5.0 / 60.0

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # ── Subplot 1: Temperature ───────────────────────────────────────────────
    if "room_1_t" in df.columns: ax1.plot(t_min, df["room_1_t"], label="S1", color=PALETTE["S1"], lw=1.5)
    if "room_2_t" in df.columns: ax1.plot(t_min, df["room_2_t"], label="S2", color=PALETTE["S2"], lw=1.5)
    if "room_3_t" in df.columns: ax1.plot(t_min, df["room_3_t"], label="S3", color=PALETTE["S3"], lw=1.5)
    if "outside_t" in df.columns: ax1.plot(t_min, df["outside_t"], label="Outdoor", color=PALETTE["Outdoor"], lw=1.5)
    if "supply_t" in df.columns: ax1.plot(t_min, df["supply_t"], label="Supply", color=PALETTE["Supply"], lw=1.5)

    ax1.set_ylabel("Temperature (°C)", fontsize=11, fontweight="bold")
    ax1.set_title(f"{dataset_title} — Raw Sensor Data Overview", fontsize=13, fontweight="bold", pad=12)
    ax1.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # ── Subplot 2: Relative Humidity ─────────────────────────────────────────
    if "room_1_h" in df.columns: ax2.plot(t_min, df["room_1_h"], label="S1", color=PALETTE["S1"], lw=1.5)
    if "room_2_h" in df.columns: ax2.plot(t_min, df["room_2_h"], label="S2", color=PALETTE["S2"], lw=1.5)
    if "room_3_h" in df.columns: ax2.plot(t_min, df["room_3_h"], label="S3", color=PALETTE["S3"], lw=1.5)
    if "outside_h" in df.columns: ax2.plot(t_min, df["outside_h"], label="Outdoor", color=PALETTE["Outdoor"], lw=1.5)
    if "supply_h" in df.columns: ax2.plot(t_min, df["supply_h"], label="Supply", color=PALETTE["Supply"], lw=1.5)

    ax2.set_ylabel("Relative Humidity (%)", fontsize=11, fontweight="bold")
    ax2.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", fontsize=9)
    ax2.grid(True, alpha=0.3)

    # ── Subplot 3: CO2 Concentration ─────────────────────────────────────────
    if "room_2_c" in df.columns: ax3.plot(t_min, df["room_2_c"], label="S2", color=PALETTE["S2"], lw=1.5)
    if "room_3_c" in df.columns: ax3.plot(t_min, df["room_3_c"], label="S3", color=PALETTE["S3"], lw=1.5)
    if "outside_c" in df.columns: ax3.plot(t_min, df["outside_c"], label="Outdoor", color=PALETTE["Outdoor"], lw=1.5)
    if "supply_c" in df.columns: ax3.plot(t_min, df["supply_c"], label="Supply", color=PALETTE["Supply"], lw=1.5)

    ax3.set_ylabel("CO2 Concentration (ppm)", fontsize=11, fontweight="bold")
    ax3.set_xlabel("Elapsed Time (minutes)", fontsize=11, fontweight="bold")
    ax3.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", fontsize=9)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(PLOTS_DIR, f"{dataset_title}_plot.png")
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Generated plot: {out_path}")

if __name__ == "__main__":
    csv_files = [f for f in os.listdir(RAW_WITH_DIR) if f.endswith(".csv")]
    for f in sorted(csv_files):
        generate_seaborn_plot(os.path.join(RAW_WITH_DIR, f))
