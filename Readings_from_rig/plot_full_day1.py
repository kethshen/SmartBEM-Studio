"""
Full Day 1 multi-part plots
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

OVERFLOW = 60000
OUT_DIR = r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\plots\full_day1"
os.makedirs(OUT_DIR, exist_ok=True)

files = {
    "Part 1": r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Full Day 1 part 1_2026-07-23.csv",
    "Part 2": r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Full day 1 part 2_2026-07-23.csv",
    "Part 5": r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Full Day 1 part 5_2026-07-23.csv",
    "Part 6": r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Full Day 1 part 6_2026-07-23.csv",
}

TEMP_COLS   = ["outside_t", "room_1_t", "room_2_t", "room_3_t", "supply_t", "return_t"]
LABELS      = ["Outside",   "Sensor 1 (Bosch)", "Sensor 2", "Sensor 3", "Supply",   "Return"]
COLORS      = ["#e74c3c",   "#3498db",  "#2ecc71",  "#f39c12", "#9b59b6", "#1abc9c"]
LINESTYLES  = ["--",        "-",        "-",        "-",       "-.",      "-."]

dfs = {}
for part, path in files.items():
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    numeric = df.select_dtypes(include="number").columns
    df[numeric] = df[numeric].where(df[numeric] < OVERFLOW, np.nan)
    # clip obvious negative outliers
    for c in TEMP_COLS:
        if c in df.columns:
            df[c] = df[c].where(df[c] > -30, np.nan).where(df[c] < 60, np.nan)
    df["elapsed_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60
    dfs[part] = df

# --- 1. Individual part plots ---
for part, df in dfs.items():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    for col, label, color, ls in zip(TEMP_COLS, LABELS, COLORS, LINESTYLES):
        if col in df.columns:
            ax1.plot(df["elapsed_min"], df[col], label=label,
                     color=color, linewidth=0.9, linestyle=ls, alpha=0.85)
    ax1.set_ylabel("Temperature (C)")
    ax1.set_title(f"Full Day 1 {part} — Temperature channels")
    ax1.legend(fontsize=8, ncol=3)
    ax1.grid(True, linestyle="--", alpha=0.4)
    ax1.set_ylim(-5, 40)

    if "room_1_h" in df.columns:
        ax2.plot(df["elapsed_min"], df["room_1_h"], label="Sensor 1 RH", color="#3498db", linewidth=0.8)
    if "room_2_h" in df.columns:
        ax2.plot(df["elapsed_min"], df["room_2_h"], label="Sensor 2 RH", color="#2ecc71", linewidth=0.8)
    if "outside_h" in df.columns:
        ax2.plot(df["elapsed_min"], df["outside_h"], label="Outside RH", color="#e74c3c",
                 linewidth=0.8, linestyle="--")
    ax2.set_ylabel("Relative Humidity (%)")
    ax2.set_xlabel("Elapsed time (min)")
    ax2.legend(fontsize=8)
    ax2.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout()
    safe = part.replace(" ", "_").lower()
    fname = os.path.join(OUT_DIR, f"full_day1_{safe}_temp_hum.png")
    plt.savefig(fname, dpi=150)
    print(f"[saved] {os.path.basename(fname)}")
    plt.close()

# --- 2. Combined timeline (all parts stitched by wall-clock time) ---
all_dfs = []
for part, df in dfs.items():
    df = df.copy()
    df["part"] = part
    all_dfs.append(df)
combined = pd.concat(all_dfs).sort_values("timestamp").reset_index(drop=True)
combined["wall_min"] = (combined["timestamp"] - combined["timestamp"].iloc[0]).dt.total_seconds() / 60

fig, ax = plt.subplots(figsize=(16, 5))
for col, label, color, ls in zip(TEMP_COLS, LABELS, COLORS, LINESTYLES):
    if col in combined.columns:
        ax.plot(combined["wall_min"], combined[col], label=label,
                color=color, linewidth=0.8, linestyle=ls, alpha=0.85)

# shade gaps between parts
part_ends = {}
for part, df in dfs.items():
    t0 = (df["timestamp"].iloc[0] - combined["timestamp"].iloc[0]).total_seconds() / 60
    t1 = (df["timestamp"].iloc[-1] - combined["timestamp"].iloc[0]).total_seconds() / 60
    part_ends[part] = (t0, t1)

prev_end = None
for part, (t0, t1) in part_ends.items():
    ax.axvspan(t0, t1, alpha=0.04, color="blue")
    ax.axvline(t0, color="gray", linewidth=0.7, linestyle=":")
    ax.text(t0 + 0.5, 37, part, fontsize=7, color="gray")
    if prev_end is not None and t0 > prev_end:
        ax.axvspan(prev_end, t0, alpha=0.12, color="red", label="_gap" if prev_end == list(part_ends.values())[1][1] else "")
    prev_end = t1

ax.set_xlabel("Elapsed time from first recording (min)")
ax.set_ylabel("Temperature (C)")
ax.set_title("Full Day 1 — All parts on shared wall-clock timeline (red = gap / missing parts)")
ax.legend(fontsize=8, ncol=3)
ax.grid(True, linestyle="--", alpha=0.4)
ax.set_ylim(-5, 40)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "full_day1_combined_timeline.png"), dpi=150)
print("[saved] full_day1_combined_timeline.png")
plt.close()

print("Done.")
