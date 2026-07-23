"""
Quick visualiser for cold-room idle test data
Usage:  python explore_sensor_data.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os

# ── 1. Load ──────────────────────────────────────────────────────────────────
CSV_PATH = r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\Idel_test_2026_07_21.csv"
OUT_DIR  = r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\plots"
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)

# Clip obviously erroneous sensor spikes (e.g. 65535 / 65402 raw overflow values)
OVERFLOW = 60000
numeric_cols = df.select_dtypes(include="number").columns
df[numeric_cols] = df[numeric_cols].where(df[numeric_cols] < OVERFLOW, np.nan)

# Derived: elapsed minutes from start
df["elapsed_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60

print("=" * 60)
print("DATASET OVERVIEW")
print("=" * 60)
print(f"  Rows            : {len(df):,}")
print(f"  Duration        : {df['elapsed_min'].max():.1f} min  "
      f"({df['elapsed_min'].max()/60:.2f} hrs)")
print(f"  Approx interval : {df['timestamp'].diff().dt.total_seconds().median():.1f} s")
print(f"  Columns         : {len(df.columns)}")

# Key sensors we care about
KEY_TEMP = {
    "Outside":  "outside_t",
    "Room 1":   "room_1_t",
    "Room 2":   "room_2_t",
    "Room 3":   "room_3_t",
    "Supply":   "supply_t",
    "Return":   "return_t",
    "Mixed":    "mixed_t",
    "Cooler":   "cooler_t",
    "Heated":   "heated_t",
}
KEY_HUM = {k: v.replace("_t", "_h") for k, v in KEY_TEMP.items()}

print("\n-- Temperature stats (C) --")
temp_df = df[[v for v in KEY_TEMP.values() if v in df.columns]].copy()
temp_df.columns = list(KEY_TEMP.keys())[:len(temp_df.columns)]
print(temp_df.describe().round(2).to_string())

print("\n-- Humidity stats (%) --")
hum_df = df[[v for v in KEY_HUM.values() if v in df.columns]].copy()
hum_df.columns = list(KEY_HUM.keys())[:len(hum_df.columns)]
print(hum_df.describe().round(2).to_string())

# ── 2. Cooler state timeline ──────────────────────────────────────────────────
print("\n-- Cooler state changes --")
cs = df[["elapsed_min", "coolerState"]].dropna()
cs["change"] = cs["coolerState"].diff().ne(0)
changes = cs[cs["change"]][["elapsed_min", "coolerState"]]
print(changes.to_string(index=False))

# ── 3. Plots ─────────────────────────────────────────────────────────────────
style = dict(linewidth=0.9, alpha=0.85)

PALETTE = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#34495e", "#95a5a6"
]

# ── Plot 1: All temperatures ─────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 5))
for i, (label, col) in enumerate(KEY_TEMP.items()):
    if col in df.columns:
        ax.plot(df["elapsed_min"], df[col], label=label,
                color=PALETTE[i % len(PALETTE)], **style)

# Shade cooler-ON periods
if "coolerState" in df.columns:
    on = df["coolerState"].fillna(0) > 0
    ax.fill_between(df["elapsed_min"], ax.get_ylim()[0], ax.get_ylim()[1],
                    where=on, alpha=0.08, color="#3498db", label="Cooler ON")

ax.set_xlabel("Elapsed time (min)")
ax.set_ylabel("Temperature (°C)")
ax.set_title("Cold-room idle test – All zone temperatures  (2026-07-21)")
ax.legend(loc="upper right", fontsize=8, ncol=2)
ax.grid(True, linestyle="--", alpha=0.4)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "01_all_temperatures.png"), dpi=150)
print("\n[saved] 01_all_temperatures.png")
plt.close()

# ── Plot 2: Room 1/2/3 temperatures (interior) vs Outside ───────────────────
fig, ax = plt.subplots(figsize=(14, 5))
interior = {"Outside": "outside_t", "Room 1": "room_1_t",
            "Room 2": "room_2_t",  "Room 3": "room_3_t"}
for i, (label, col) in enumerate(interior.items()):
    if col in df.columns:
        lw = 1.5 if label == "Outside" else 1.0
        ls = "--" if label == "Outside" else "-"
        ax.plot(df["elapsed_min"], df[col], label=label,
                color=PALETTE[i], linewidth=lw, linestyle=ls, alpha=0.9)

ax.set_xlabel("Elapsed time (min)")
ax.set_ylabel("Temperature (°C)")
ax.set_title("Interior zones vs Outdoor temperature")
ax.legend(fontsize=9)
ax.grid(True, linestyle="--", alpha=0.4)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "02_interior_vs_outdoor_temp.png"), dpi=150)
print("[saved] 02_interior_vs_outdoor_temp.png")
plt.close()

# ── Plot 3: Supply / Return / Cooler temperatures ────────────────────────────
fig, ax = plt.subplots(figsize=(14, 5))
hvac_temps = {"Supply": "supply_t", "Return": "return_t",
              "Cooler": "cooler_t", "Heated": "heated_t", "Mixed": "mixed_t"}
for i, (label, col) in enumerate(hvac_temps.items()):
    if col in df.columns:
        ax.plot(df["elapsed_min"], df[col], label=label,
                color=PALETTE[i], **style)

ax.set_xlabel("Elapsed time (min)")
ax.set_ylabel("Temperature (°C)")
ax.set_title("HVAC stream temperatures (supply / return / cooler)")
ax.legend(fontsize=9)
ax.grid(True, linestyle="--", alpha=0.4)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "03_hvac_stream_temps.png"), dpi=150)
print("[saved] 03_hvac_stream_temps.png")
plt.close()

# ── Plot 4: All humidity channels ────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 5))
for i, (label, col) in enumerate(KEY_HUM.items()):
    if col in df.columns:
        ax.plot(df["elapsed_min"], df[col], label=label,
                color=PALETTE[i % len(PALETTE)], **style)

ax.set_xlabel("Elapsed time (min)")
ax.set_ylabel("Relative Humidity (%)")
ax.set_title("All humidity channels")
ax.legend(loc="upper right", fontsize=8, ncol=2)
ax.grid(True, linestyle="--", alpha=0.4)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "04_all_humidity.png"), dpi=150)
print("[saved] 04_all_humidity.png")
plt.close()

# ── Plot 5: Cooler state + Room 1 temp overlay ───────────────────────────────
fig, ax1 = plt.subplots(figsize=(14, 4))
ax2 = ax1.twinx()

ax1.plot(df["elapsed_min"], df["room_1_t"], color="#e74c3c",
         linewidth=1.0, label="Room 1 Temp")
ax2.step(df["elapsed_min"], df["coolerState"].fillna(0),
         color="#3498db", linewidth=1.2, alpha=0.7, label="Cooler state")

ax1.set_xlabel("Elapsed time (min)")
ax1.set_ylabel("Room 1 Temperature (°C)", color="#e74c3c")
ax2.set_ylabel("Cooler state (0/1)", color="#3498db")
ax1.set_title("Room 1 temperature vs Cooler ON/OFF state")
lines1, lab1 = ax1.get_legend_handles_labels()
lines2, lab2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, lab1 + lab2, fontsize=9)
ax1.grid(True, linestyle="--", alpha=0.4)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "05_room1_vs_cooler_state.png"), dpi=150)
print("[saved] 05_room1_vs_cooler_state.png")
plt.close()

# ── Plot 6: Flow rate ─────────────────────────────────────────────────────────
if "flowrate" in df.columns:
    fig, ax = plt.subplots(figsize=(14, 3))
    fr = df["flowrate"].where(df["flowrate"] < OVERFLOW, np.nan)
    ax.plot(df["elapsed_min"], fr, color="#9b59b6", linewidth=0.8)
    ax.set_xlabel("Elapsed time (min)")
    ax.set_ylabel("Flow rate")
    ax.set_title("Flow rate over time")
    ax.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "06_flowrate.png"), dpi=150)
    print("[saved] 06_flowrate.png")
    plt.close()

print(f"\nAll plots saved to: {OUT_DIR}")
print("Done.")
