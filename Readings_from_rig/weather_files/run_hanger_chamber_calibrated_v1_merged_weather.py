import os
import sys
import shutil
import subprocess
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize

# 1. Paths & Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
RIG_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig")
CALIBRATED_V1_DIR = SCRIPT_DIR

MASTER_IDF_PATH = os.path.join(CALIBRATED_V1_DIR, "hanger_chamber_base_template.idf")
OFFICIAL_KANDY_EPW_PATH = os.path.join(CALIBRATED_V1_DIR, "LKA_CP_Kandy.434440_TMYx.2011-2025.epw")
MERGED_EPW_PATH = os.path.join(CALIBRATED_V1_DIR, "test_day_weather_merged_1min.epw")
CSV_CLEANED_PATH = os.path.join(CALIBRATED_V1_DIR, "Idel_test_2026_07_21_cleaned.csv")
OUT_DIR = os.path.join(CALIBRATED_V1_DIR, "sim_output_merged_weather")
FINAL_IDF_PATH = os.path.join(CALIBRATED_V1_DIR, "hanger_chamber_after_calibrated_v1_merged_weather.idf")
PLOT_PATH = os.path.join(CALIBRATED_V1_DIR, "hanger_chamber_after_calibrated_v1_merged_weather.png")

ENERGYPLUS_EXE = r"C:\EnergyPlusV25-2-0\energyplus.exe"
if not os.path.exists(ENERGYPLUS_EXE):
    ENERGYPLUS_EXE = shutil.which("energyplus")

os.makedirs(OUT_DIR, exist_ok=True)

# DTW distance function
def compute_dtw_distance(s1, s2):
    n, m = len(s1), len(s2)
    dtw_matrix = np.zeros((n + 1, m + 1))
    dtw_matrix[0, 1:] = np.inf
    dtw_matrix[1:, 0] = np.inf
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(s1[i - 1] - s2[j - 1])
            dtw_matrix[i, j] = cost + min(dtw_matrix[i - 1, j], dtw_matrix[i, j - 1], dtw_matrix[i - 1, j - 1])
    return dtw_matrix[n, m] / max(n, m)

# 2. 4-Stage Sensor Data Cleaning Function
def clean_sensor_signal_4stage(series, min_val=5.0, max_val=50.0, rolling_window=12, ema_alpha=0.10):
    s = series.copy().astype(float)
    s[(s < min_val) | (s > max_val)] = np.nan
    roll_mean = s.rolling(window=rolling_window, min_periods=1, center=True).mean()
    roll_std = s.rolling(window=rolling_window, min_periods=1, center=True).std().fillna(0)
    outliers = (np.abs(s - roll_mean) > 3.0 * roll_std) & (roll_std > 0.01)
    s[outliers] = np.nan
    s_interp = s.interpolate(method="linear").bfill().ffill()
    s_ema = s_interp.ewm(alpha=ema_alpha, adjust=False).mean()
    return s_ema.values

# 3. Load Sensor Data & Create Merged 1-Minute EPW Boundary File
df_cleaned = pd.read_csv(CSV_CLEANED_PATH)
Tz_raw = df_cleaned["Tz_weighted"].values
Tz_ema = pd.Series(Tz_raw).ewm(alpha=0.10, adjust=False).mean().values
N_sensor = len(Tz_ema)
mean_Tz = np.mean(Tz_ema)

# Perform 4-stage cleaning on outdoor sensor signals
T_outdoor_cleaned = clean_sensor_signal_4stage(df_cleaned["outside_t"])
RH_outdoor_cleaned = clean_sensor_signal_4stage(df_cleaned["humidity"], min_val=10.0, max_val=100.0) if "humidity" in df_cleaned.columns else np.full(N_sensor, 70.0)
P_outdoor_cleaned = clean_sensor_signal_4stage(df_cleaned["pressure"], min_val=90000.0, max_val=105000.0) if "pressure" in df_cleaned.columns else np.full(N_sensor, 99063.0)

# Merge measured sensor 1-min data with official Kandy Solar & Wind data from EPW
with open(OFFICIAL_KANDY_EPW_PATH, "r", encoding="utf-8") as f:
    epw_lines = f.readlines()

header_lines = epw_lines[:8]
data_lines = epw_lines[8:]
merged_data_lines = []

for line in data_lines:
    parts = line.strip().split(",")
    if len(parts) > 20:
        hour = int(parts[3])
        # For afternoon test window (13:00 to 16:00), inject measured rig sensor values
        if 13 <= hour <= 16:
            idx = int(round((hour - 13) * (N_sensor / 4.0)))
            idx = min(idx, N_sensor - 1)
            parts[6] = f"{T_outdoor_cleaned[idx]:.2f}"      # Drybulb Temperature (C)
            parts[8] = f"{RH_outdoor_cleaned[idx]:.1f}"     # Relative Humidity (%)
            parts[9] = f"{P_outdoor_cleaned[idx]:.0f}"      # Atmospheric Pressure (Pa)
            # Solar Radiation (fields 13 & 14) and Wind Speed (field 21) are retained from official Kandy EPW
        merged_data_lines.append(",".join(parts) + "\n")

with open(MERGED_EPW_PATH, "w", encoding="utf-8") as f:
    f.writelines(header_lines + merged_data_lines)

print(f"Created Merged EPW File with Official Kandy Solar/Wind + 1-Min Rig Sensors: {MERGED_EPW_PATH}")

# 4. Read Base IDF Content & Ensure Timestep, 60;
with open(MASTER_IDF_PATH, "r", encoding="utf-8") as f:
    master_idf_content = f.read()

# Force Timestep, 60; (1-minute resolution)
if "Timestep,\n  6;" in master_idf_content:
    master_idf_content = master_idf_content.replace("Timestep,\n  6;", "Timestep,\n  60;")

iteration_counter = 0
best_loss = float("inf")
best_cv_rmse = float("inf")
best_nmbe = float("inf")
best_params = None
best_Tsim = None

print("=" * 95)
print("  LAUNCHING MERGED 1-MIN KANDY EPW + SENSOR BOUNDARY CALIBRATION LOOP  ")
print("=" * 95)
print(f"{'Iter':<5} | {'k_foam':<8} | {'cp_foam':<7} | {'rho_foam':<8} | {'ACH':<6} | {'Qcool(W)':<8} | {'CV(RMSE)%':<10} | {'NMBE%':<8} | {'Loss':<8}")
print("-" * 95)

def run_energyplus_iteration(params):
    global iteration_counter, best_loss, best_cv_rmse, best_nmbe, best_params, best_Tsim
    iteration_counter += 1
    
    k_foam, cp_foam, rho_foam, ach, q_cool = params
    
    idf_str = master_idf_content
    
    # 1. Update Chamber_PU_Foam material (Conductivity, Density, Specific Heat)
    old_mat_block = (
        "  Material,\n"
        "    Chamber_PU_Foam,                   !- Name\n"
        "    Smooth,                            !- Roughness\n"
        "    0.1000,                            !- Thickness {m}\n"
        "    0.0220,                            !- Thermal Conductivity {W/m-K} (Raw Default)\n"
        "    32.00,                             !- Density {kg/m3} (Raw Default)\n"
        "    1500.00,                           !- Specific Heat {J/kg-K} (Raw Default)"
    )
    new_mat_block = (
        "  Material,\n"
        "    Chamber_PU_Foam,                   !- Name\n"
        "    Smooth,                            !- Roughness\n"
        "    0.1000,                            !- Thickness {m}\n"
        f"    {k_foam:.6f},                            !- Thermal Conductivity {{W/m-K}}\n"
        f"    {rho_foam:.2f},                             !- Density {{kg/m3}}\n"
        f"    {cp_foam:.2f},                           !- Specific Heat {{J/kg-K}}"
    )
    
    if old_mat_block in idf_str:
        idf_str = idf_str.replace(old_mat_block, new_mat_block)
    else:
        mat_start = idf_str.find("Chamber_PU_Foam")
        if mat_start != -1:
            mat_end = idf_str.find(";", mat_start)
            mat_snippet = idf_str[mat_start:mat_end]
            lines = mat_snippet.splitlines()
            if len(lines) >= 6:
                lines[2] = f"    0.1000,                            !- Thickness {{m}}"
                lines[3] = f"    {k_foam:.6f},                            !- Thermal Conductivity {{W/m-K}}"
                lines[4] = f"    {rho_foam:.2f},                             !- Density {{kg/m3}}"
                lines[5] = f"    {cp_foam:.2f},                           !- Specific Heat {{J/kg-K}}"
                idf_str = idf_str[:mat_start] + "\n".join(lines) + idf_str[mat_end:]

    # 2. Update Infiltration ACH
    old_ach = "0.1000,                                    !- Air Changes per Hour {1/hr}"
    new_ach = f"{ach:.4f},                                    !- Air Changes per Hour {{1/hr}}"
    idf_str = idf_str.replace(old_ach, new_ach)

    # 3. Update Cooling Capacity Q_cool
    q_start = idf_str.find("Maximum Total Cooling Capacity")
    if q_start != -1:
        line_start = idf_str.rfind("\n", 0, q_start) + 1
        line_end = idf_str.find("\n", q_start)
        idf_str = idf_str[:line_start] + f"  {q_cool:.1f},                                    !- Maximum Total Cooling Capacity {{W}}" + idf_str[line_end:]

    # Write temporary IDF file
    temp_idf = os.path.join(OUT_DIR, "temp_calibration_merged.idf")
    with open(temp_idf, "w", encoding="utf-8") as f:
        f.write(idf_str)

    # Run EnergyPlus
    cmd = [ENERGYPLUS_EXE, "-d", OUT_DIR, "-w", MERGED_EPW_PATH, temp_idf]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    
    if proc.returncode != 0:
        return 999.0

    # Parse simulation output
    eso_path = os.path.join(OUT_DIR, "eplusout.eso")
    target_id = None
    with open(eso_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "End of Data Dictionary" in line:
                break
            parts = line.strip().split(",")
            if len(parts) >= 4 and "CHAMBER_THERMALZONE" in parts[2] and "Zone Mean Air Temperature" in parts[3]:
                target_id = parts[0]

    if target_id is None:
        return 999.0

    sim_temps = []
    with open(eso_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) == 2 and parts[0] == target_id:
                sim_temps.append(float(parts[1]))

    sim_temps = np.array(sim_temps)
    
    # 1-min resolution test window (13:26 PM start = Minute 806 to 976, 170 timesteps)
    start_idx = 806
    end_idx = start_idx + 170
    if len(sim_temps) <= end_idx:
        start_idx = 450
        end_idx = start_idx + 170

    T_sim_window = sim_temps[start_idx:end_idx]
    
    if len(T_sim_window) < 170:
        return 999.0

    # Interpolate time vectors to match sensor length
    sim_times = np.linspace(0, 170.1, len(T_sim_window))
    sensor_times = np.linspace(0, 170.1, N_sensor)
    T_sim_interp = np.interp(sensor_times, sim_times, T_sim_window)

    # Calculate ASHRAE Guideline 14 Standard Metrics
    rmse = np.sqrt(np.mean((T_sim_interp - Tz_ema)**2))
    cv_rmse = (rmse / mean_Tz) * 100.0
    nmbe = (np.mean(T_sim_interp - Tz_ema) / mean_Tz) * 100.0
    dtw_dist = compute_dtw_distance(T_sim_interp, Tz_ema)
    
    loss = cv_rmse + 0.5 * abs(nmbe) + 2.0 * dtw_dist
    
    print(f"{iteration_counter:<5d} | {k_foam:<8.4f} | {cp_foam:<7.0f} | {rho_foam:<8.1f} | {ach:<6.3f} | {q_cool:<8.1f} | {cv_rmse:<10.2f} | {nmbe:<8.2f} | {loss:<8.3f}")

    if loss < best_loss:
        best_loss = loss
        best_cv_rmse = cv_rmse
        best_nmbe = nmbe
        best_params = params
        best_Tsim = T_sim_interp
        with open(FINAL_IDF_PATH, "w", encoding="utf-8") as f:
            f.write(idf_str)

    return loss

# Initial parameter guesses
init_params = [0.0249, 1400.0, 32.0, 0.098, 597.0]

bounds = [
    (0.0150, 0.0450),  # k_foam (W/mK)
    (800.0, 2000.0),   # cp_foam (J/kgK)
    (20.0, 60.0),      # rho_foam (kg/m3)
    (0.010, 0.500),    # ACH (1/hr)
    (300.0, 1200.0)    # Q_cool (W)
]

res = minimize(
    run_energyplus_iteration,
    init_params,
    method="Nelder-Mead",
    bounds=bounds,
    options={"maxiter": 80, "xatol": 1e-3, "fatol": 1e-2}
)

best_k, best_cp, best_rho, best_ach, best_q = best_params

print("=" * 95)
print("              STAGE 2 MERGED EPW + SENSOR CALIBRATION COMPLETED SUCCESSFULLY!             ")
print("=" * 95)
print(f"Optimal Composite Loss: {best_loss:.3f}")
print(f"Optimal ASHRAE CV(RMSE): {best_cv_rmse:.2f}% (Target <= 5.0%)")
print(f"Optimal ASHRAE NMBE:     {best_nmbe:.2f}% (Target <= 2.0%)")
print(f"\nCalibrated Physical Parameters:")
print(f"• Foam Conductivity k:   {best_k:.5f} W/(m·K)")
print(f"• Foam Specific Heat cp: {best_cp:.1f} J/(kg·K)")
print(f"• Foam Density rho:      {best_rho:.1f} kg/m³")
print(f"• Chamber Infiltration:  {best_ach:.3f} ACH")
print(f"• Peak AC Cooling Q:     {best_q:.1f} W")

# Plot Final Calibrated Trajectory vs Sensors
sensor_times = np.linspace(0, 170.1, N_sensor)

plt.figure(figsize=(12, 6), dpi=300)
plt.plot(sensor_times, Tz_raw, label="Cleaned Raw Sensor $T_z$ (0.50 S1 + 0.30 S2 + 0.20 S3)", color="#2ca02c", alpha=0.25, linewidth=1.5)
plt.plot(sensor_times, Tz_ema, label="EMA-Smoothed Target Sensor $T_z$", color="#2ca02c", linewidth=2.5)
plt.plot(sensor_times, best_Tsim, label=f"Calibrated EnergyPlus $T_{{sim}}$ (ASHRAE CV={best_cv_rmse:.1f}%)", color="#d62728", linestyle="--", linewidth=2.5)

plt.title("Stage 2 Merged Kandy EPW & 1-Min Sensor Calibrated EnergyPlus vs. Sensor Pulldown", fontsize=13, fontweight="bold", pad=12)
plt.xlabel("Elapsed Time (Minutes)", fontsize=11)
plt.ylabel("Chamber Zone Air Temperature (°C)", fontsize=11)
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(fontsize=10, loc="upper right")

textstr = (
    f"Calibrated Parameters:\n"
    f"• $k_{{foam}}$ = {best_k:.4f} W/(m·K)\n"
    f"• $c_{{p,foam}}$ = {best_cp:.0f} J/(kg·K)\n"
    f"• $\\rho_{{foam}}$ = {best_rho:.1f} kg/m³\n"
    f"• ACH = {best_ach:.3f} hr⁻¹\n"
    f"• $Q_{{cool}}$ = {best_q:.0f} W\n\n"
    f"ASHRAE Guideline 14 Metrics:\n"
    f"• CV(RMSE) = {best_cv_rmse:.2f}% (Target ≤ 5%)\n"
    f"• NMBE       = {best_nmbe:.2f}% (Target ≤ 2%)\n"
    f"• RMSE       = {np.sqrt(np.mean((best_Tsim - Tz_ema)**2)):.2f} °C\n"
    f"• MAE        = {np.mean(np.abs(best_Tsim - Tz_ema)):.2f} °C\n"
    f"• R²         = {1.0 - (np.sum((best_Tsim - Tz_ema)**2) / np.sum((Tz_ema - np.mean(Tz_ema))**2)):.4f}"
)
props = dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9, edgecolor="#ccc")
plt.gca().text(0.03, 0.15, textstr, transform=plt.gca().transAxes, fontsize=9, bbox=props)

plt.tight_layout()
plt.savefig(PLOT_PATH)
plt.close()

print(f"Saved Calibrated IDF to: {FINAL_IDF_PATH}")
print(f"Saved Calibrated Comparison Plot to: {PLOT_PATH}")
