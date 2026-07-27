import os
import sys
import shutil
import subprocess
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. Setup Absolute Paths
STUDIO_DIR = r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio"
RIG_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig")
IDF_PATH = os.path.join(STUDIO_DIR, "hanger_chamber_master.idf")
EPW_PATH = os.path.join(RIG_DIR, "experimental_data", "test_day_weather.epw")
CSV_SENSOR_PATH = os.path.join(RIG_DIR, "experimental_data", "Idel_test_2026_07_21.csv")
OUT_DIR = os.path.join(RIG_DIR, "sim_models", "sim_output")
PLOT_PATH = os.path.join(RIG_DIR, "plots", "sim_vs_sensors_exact_rig_match.png")

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(PLOT_PATH), exist_ok=True)

# 2. Locate EnergyPlus V25 Executable
ENERGYPLUS_EXE = r"C:\EnergyPlusV25-2-0\energyplus.exe"
if not os.path.exists(ENERGYPLUS_EXE):
    ENERGYPLUS_EXE = shutil.which("energyplus")

print(f"Using EnergyPlus: {ENERGYPLUS_EXE}")
print(f"IDF Path: {IDF_PATH}")
print(f"EPW Path: {EPW_PATH}")

# 3. Run EnergyPlus Simulation
cmd = [
    ENERGYPLUS_EXE,
    "-d", OUT_DIR,
    "-w", EPW_PATH,
    IDF_PATH
]

print("Executing EnergyPlus baseline simulation run...")
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    print("EnergyPlus Run Error:")
    print(result.stderr)
    sys.exit(1)

print("EnergyPlus Simulation execution successful!")

# 4. Parse High-Resolution 1-Minute Timesteps directly from eplusout.eso
eso_path = os.path.join(OUT_DIR, "eplusout.eso")
target_id = None

with open(eso_path, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        if "End of Data Dictionary" in line:
            break
        parts = line.strip().split(",")
        if len(parts) >= 4 and "CHAMBER_THERMALZONE" in parts[2] and "Zone Mean Air Temperature" in parts[3]:
            target_id = parts[0]
            print(f"Extracted Target Variable ID: {target_id} -> {parts[3]}")

sim_temps = []
with open(eso_path, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        parts = line.strip().split(",")
        if len(parts) == 2 and parts[0] == target_id:
            sim_temps.append(float(parts[1]))

T_sim = np.array(sim_temps)
n_sim = len(T_sim)
print(f"Extracted {n_sim} 1-minute resolution simulated Chamber temperature steps!")

# 5. Load and Clean Real Sensor Data
df_sensor = pd.read_csv(CSV_SENSOR_PATH)
df_sensor.columns = [c.strip() for c in df_sensor.columns]

# Clean outliers (< 5°C or > 50°C)
s1 = df_sensor["room_1_t"].apply(lambda x: x if 5.0 <= x <= 50.0 else np.nan)
s2 = df_sensor["room_2_t"].apply(lambda x: x if 5.0 <= x <= 50.0 else np.nan)

# Weighted Zone Temperature (0.6 S1 Bosch + 0.4 S2)
df_sensor["Tz_weighted"] = 0.6 * s1 + 0.4 * s2

# Time alignment across 170.1 minutes
sim_times_min = np.linspace(0, 170.1, n_sim)
sensor_times_min = np.linspace(0, 170.1, len(df_sensor))

Tz_sensor_interp = np.interp(sim_times_min, sensor_times_min, df_sensor["Tz_weighted"].ffill().bfill())

# 6. Compute Statistical Metrics
rmse = np.sqrt(np.mean((T_sim - Tz_sensor_interp)**2))
mae = np.mean(np.abs(T_sim - Tz_sensor_interp))
r2 = 1.0 - (np.sum((Tz_sensor_interp - T_sim)**2) / np.sum((Tz_sensor_interp - np.mean(Tz_sensor_interp))**2))

print(f"Statistical Summary:")
print(f"• RMSE: {rmse:.2f} °C")
print(f"• MAE:  {mae:.2f} °C")
print(f"• R²:   {r2:.4f}")

# 7. Generate High-Resolution Overlay Comparison Plot
plt.figure(figsize=(12, 6), dpi=300)
plt.plot(sim_times_min, Tz_sensor_interp, label="Real Sensor Zone Temp $T_z$ (Weighted 0.6 S1 + 0.4 S2)", color="#2ca02c", linewidth=2.5)
plt.plot(sim_times_min, T_sim, label="EnergyPlus Baseline $T_{sim}$ (1-Min Timesteps)", color="#d62728", linewidth=2.2, linestyle="--")

plt.title("Stage 1 Baseline Simulation vs. Real Rig Sensor Data (1-Minute Timesteps)", fontsize=14, fontweight="bold", pad=15)
plt.xlabel("Elapsed Time (Minutes)", fontsize=12)
plt.ylabel("Chamber Zone Air Temperature (°C)", fontsize=12)
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(fontsize=11, loc="upper right")

# Annotate Statistics Box
textstr = f"Statistical Comparison:\n• RMSE = {rmse:.2f} °C\n• MAE  = {mae:.2f} °C\n• R²   = {r2:.4f}"
props = dict(boxstyle="round,pad=0.6", facecolor="white", alpha=0.9, edgecolor="#ccc")
plt.gca().text(0.03, 0.15, textstr, transform=plt.gca().transAxes, fontsize=11, verticalalignment="bottom", bbox=props)

plt.tight_layout()
plt.savefig(PLOT_PATH)
plt.close()

print(f"High-resolution baseline plot saved to: {PLOT_PATH}")
