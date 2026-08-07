import os
import sys
import shutil
import subprocess
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize

# 1. Paths & Configuration
STUDIO_DIR = r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio"
RIG_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig")
MASTER_IDF_PATH = os.path.join(STUDIO_DIR, "hanger_chamber_master.idf")
EPW_PATH = os.path.join(RIG_DIR, "sensor_readings", "weather", "test_day_weather.epw")
CSV_CLEANED_PATH = os.path.join(RIG_DIR, "experimental_data", "cleaned", "Idel_test_2026_07_21_cleaned.csv")
OUT_DIR = os.path.join(RIG_DIR, "sim_models", "sim_calibration_temp")
FINAL_IDF_PATH = os.path.join(STUDIO_DIR, "hanger_chamber_calibrated.idf")
PLOT_PATH = os.path.join(RIG_DIR, "plots", "calibrated_sim_vs_sensors.png")

ENERGYPLUS_EXE = r"C:\EnergyPlusV25-2-0\energyplus.exe"
if not os.path.exists(ENERGYPLUS_EXE):
    ENERGYPLUS_EXE = shutil.which("energyplus")

os.makedirs(OUT_DIR, exist_ok=True)

# 2. Load Sensor Reference Trajectory (170.1 min test window) & Apply EMA Smoothing
df_cleaned = pd.read_csv(CSV_CLEANED_PATH)
Tz_raw = df_cleaned["Tz_weighted"].values
# Apply EMA smoothing (alpha=0.10) to remove raw quantization noise
Tz_ema = pd.Series(Tz_raw).ewm(alpha=0.10, adjust=False).mean().values
N_sensor = len(Tz_ema)

# 3. Read Master IDF Content
with open(MASTER_IDF_PATH, "r", encoding="utf-8") as f:
    master_idf_content = f.read()

iteration_counter = 0
best_loss = float("inf")
best_params = None
best_Tsim = None

def run_energyplus_iteration(params):
    global iteration_counter, best_loss, best_params, best_Tsim
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
    temp_idf = os.path.join(OUT_DIR, "temp_calibration.idf")
    with open(temp_idf, "w", encoding="utf-8") as f:
        f.writelines(idf_str)

    # Run EnergyPlus
    cmd = [ENERGYPLUS_EXE, "-d", OUT_DIR, "-w", EPW_PATH, temp_idf]
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
    
    # Rig test window: 07:44 AM UTC (Step 92 to Step 126, 34 timesteps)
    start_idx = 92
    end_idx = start_idx + 34
    T_sim_window = sim_temps[start_idx:end_idx]
    
    if len(T_sim_window) < 34:
        return 999.0

    # Interpolate time vectors to match sensor length
    sim_times = np.linspace(0, 170.1, len(T_sim_window))
    sensor_times = np.linspace(0, 170.1, N_sensor)
    T_sim_interp = np.interp(sensor_times, sim_times, T_sim_window)

    rmse = np.sqrt(np.mean((T_sim_interp - Tz_ema)**2))
    
    print(f"Iter {iteration_counter:02d} | k={k_foam:.4f}, cp={cp_foam:.0f}, rho={rho_foam:.1f}, ACH={ach:.3f}, Qcool={q_cool:.0f} W => RMSE: {rmse:.3f} °C")

    if rmse < best_loss:
        best_loss = rmse
        best_params = params
        best_Tsim = T_sim_interp
        with open(FINAL_IDF_PATH, "w", encoding="utf-8") as f:
            f.write(idf_str)

    return rmse

# 4. Initial Parameters & Bounds
# [k_foam (W/m-K), cp_foam (J/kg-K), rho_foam (kg/m3), ACH (1/hr), Q_cool (W)]
x0 = [0.025, 1400.0, 32.0, 0.10, 120.0]
bounds = [
    (0.015, 0.045),    # k_foam
    (800.0, 1800.0),   # cp_foam
    (20.0, 45.0),      # rho_foam
    (0.01, 0.50),      # ACH
    (50.0, 300.0)      # Q_cool
]

print("==========================================================================")
print("   LAUNCHING STAGE 2 RE-CALIBRATION WITH REAL OUTSIDE_T & EMA SENSOR TZ    ")
print("==========================================================================")
print(f"Initial Guess: k={x0[0]}, cp={x0[1]}, rho={x0[2]}, ACH={x0[3]}, Qcool={x0[4]} W\n")

# Execute Nelder-Mead Optimization
res = minimize(
    run_energyplus_iteration,
    x0,
    method="Nelder-Mead",
    options={"maxiter": 50, "disp": True, "xatol": 1e-3, "fatol": 1e-2}
)

print("\n==========================================================================")
print("                    STAGE 2 CALIBRATION COMPLETED!                        ")
print("==========================================================================")
print(f"Optimal RMSE: {best_loss:.3f} °C")
k_opt, cp_opt, rho_opt, ach_opt, q_opt = best_params
print(f"• Optimal Foam Conductivity k:   {k_opt:.5f} W/(m·K)")
print(f"• Optimal Foam Specific Heat cp: {cp_opt:.1f} J/(kg·K)")
print(f"• Optimal Foam Density rho:      {rho_opt:.1f} kg/m³")
print(f"• Optimal Chamber Infiltration:  {ach_opt:.3f} ACH")
print(f"• Optimal Cooling Capacity Q:    {q_opt:.1f} W")
print(f"Saved Calibrated IDF to: {FINAL_IDF_PATH}")

# 5. Final Evaluation Metrics & High-Resolution Plot
mae_final = np.mean(np.abs(best_Tsim - Tz_ema))
r2_final = 1.0 - (np.sum((Tz_ema - best_Tsim)**2) / np.sum((Tz_ema - np.mean(Tz_ema))**2))

print(f"\nFinal Calibrated Accuracy against EMA Sensor Tz:")
print(f"• RMSE = {best_loss:.2f} °C")
print(f"• MAE  = {mae_final:.2f} °C")
print(f"• R²   = {r2_final:.4f}")

plt.figure(figsize=(12, 6), dpi=300)
sensor_times_min = np.linspace(0, 170.1, N_sensor)
plt.plot(sensor_times_min, Tz_raw, label="Cleaned Raw Sensor $T_z$ (0.50 S1 + 0.30 S2 + 0.20 S3)", color="#a1d99b", alpha=0.5, linewidth=1.5)
plt.plot(sensor_times_min, Tz_ema, label="EMA-Smoothed Target Sensor $T_z$", color="#2ca02c", linewidth=2.5)
plt.plot(sensor_times_min, best_Tsim, label=f"Calibrated EnergyPlus $T_{{sim}}$ (RMSE = {best_loss:.2f} °C)", color="#d62728", linewidth=2.2, linestyle="--")

plt.title("Stage 2 Calibrated EnergyPlus Simulation vs. Cleaned Rig Sensor Data (Real EPW & Time Match)", fontsize=14, fontweight="bold", pad=15)
plt.xlabel("Elapsed Time (Minutes)", fontsize=12)
plt.ylabel("Chamber Zone Air Temperature (°C)", fontsize=12)
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(fontsize=11, loc="upper right")

textstr = (
    f"Calibrated Parameters:\n"
    f"• $k_{{foam}}$ = {k_opt:.4f} W/(m·K)\n"
    f"• $c_{{p,foam}}$ = {cp_opt:.0f} J/(kg·K)\n"
    f"• $\\rho_{{foam}}$ = {rho_opt:.1f} kg/m³\n"
    f"• $\\text{{ACH}}$ = {ach_opt:.3f} hr⁻¹\n"
    f"• $Q_{{cool}}$ = {q_opt:.0f} W\n\n"
    f"Accuracy Metrics:\n"
    f"• RMSE = {best_loss:.2f} °C\n"
    f"• MAE  = {mae_final:.2f} °C\n"
    f"• R²   = {r2_final:.4f}"
)
props = dict(boxstyle="round,pad=0.6", facecolor="white", alpha=0.9, edgecolor="#ccc")
plt.gca().text(0.03, 0.10, textstr, transform=plt.gca().transAxes, fontsize=10, verticalalignment="bottom", bbox=props)

plt.tight_layout()
plt.savefig(PLOT_PATH)
plt.close()

print(f"Saved Calibrated Comparison Plot to: {PLOT_PATH}")
