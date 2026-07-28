import os
import sys
import shutil
import subprocess
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize

# Simple DTW implementation for trajectory shape matching
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

# 1. Paths & Configuration (Strictly Isolated Files)
STUDIO_DIR = r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio"
RIG_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig")
MASTER_IDF_PATH = os.path.join(STUDIO_DIR, "hanger_chamber_master.idf")
EPW_PATH = os.path.join(RIG_DIR, "experimental_data", "test_day_weather.epw")
CSV_CLEANED_PATH = os.path.join(RIG_DIR, "experimental_data", "cleaned", "Idel_test_2026_07_21_cleaned.csv")

OUT_DIR = os.path.join(RIG_DIR, "sim_models", "sim_calibration_ashrae_high_iter")
FINAL_IDF_PATH = os.path.join(STUDIO_DIR, "hanger_chamber_calibrated_ashrae_high_iter.idf")
PLOT_PATH = os.path.join(RIG_DIR, "plots", "calibrated_ashrae_dtw_high_iter_sim_vs_sensors.png")

ENERGYPLUS_EXE = r"C:\EnergyPlusV25-2-0\energyplus.exe"
if not os.path.exists(ENERGYPLUS_EXE):
    ENERGYPLUS_EXE = shutil.which("energyplus")

os.makedirs(OUT_DIR, exist_ok=True)

# 2. Load Sensor Reference Trajectory & EMA Target
df_cleaned = pd.read_csv(CSV_CLEANED_PATH)
Tz_raw = df_cleaned["Tz_weighted"].values
Tz_ema = pd.Series(Tz_raw).ewm(alpha=0.10, adjust=False).mean().values
N_sensor = len(Tz_ema)
mean_Tz = np.mean(Tz_ema)

# 3. Read Master IDF Content
with open(MASTER_IDF_PATH, "r", encoding="utf-8") as f:
    master_idf_content = f.read()

iteration_counter = 0
best_loss = float("inf")
best_cv_rmse = float("inf")
best_nmbe = float("inf")
best_params = None
best_Tsim = None

print("=" * 95)
print("  LAUNCHING HIGH-ITERATION ISOLATED ASHRAE & DTW CALIBRATION LOOP (MAXITER=600)  ")
print("=" * 95)
print(f"{'Iter':<5} | {'k_foam':<8} | {'cp_foam':<7} | {'rho_foam':<8} | {'ACH':<6} | {'Qcool(W)':<8} | {'CV(RMSE)%':<10} | {'NMBE%':<8} | {'Loss':<8}")
print("-" * 95)

def run_energyplus_iteration(params):
    global iteration_counter, best_loss, best_cv_rmse, best_nmbe, best_params, best_Tsim
    iteration_counter += 1
    
    k_foam, cp_foam, rho_foam, ach, q_cool = params
    
    idf_str = master_idf_content
    
    # Update Material
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

    # Update Infiltration
    old_ach = "0.1000,                                    !- Air Changes per Hour {1/hr}"
    new_ach = f"{ach:.4f},                                    !- Air Changes per Hour {{1/hr}}"
    idf_str = idf_str.replace(old_ach, new_ach)

    # Update Cooling Capacity
    q_start = idf_str.find("Maximum Total Cooling Capacity")
    if q_start != -1:
        line_start = idf_str.rfind("\n", 0, q_start) + 1
        line_end = idf_str.find("\n", q_start)
        idf_str = idf_str[:line_start] + f"  {q_cool:.1f},                                    !- Maximum Total Cooling Capacity {{W}}" + idf_str[line_end:]

    # Write temporary IDF file
    temp_idf = os.path.join(OUT_DIR, "temp_calibration_high_iter.idf")
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
    
    start_idx = 45
    end_idx = start_idx + 34
    T_sim_window = sim_temps[start_idx:end_idx]
    
    if len(T_sim_window) < 34:
        return 999.0

    sim_times = np.linspace(0, 170.1, len(T_sim_window))
    sensor_times = np.linspace(0, 170.1, N_sensor)
    T_sim_interp = np.interp(sensor_times, sim_times, T_sim_window)

    rmse = np.sqrt(np.mean((T_sim_interp - Tz_ema)**2))
    cv_rmse = (rmse / mean_Tz) * 100.0
    nmbe = (np.mean(T_sim_interp - Tz_ema) / mean_Tz) * 100.0
    dtw_dist = compute_dtw_distance(T_sim_interp, Tz_ema)
    
    loss = cv_rmse + 0.5 * abs(nmbe) + 2.5 * dtw_dist
    
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

# Bounds in Normalized Scale [0, 1]
bounds_raw = np.array([
    (0.015, 0.045),    # k_foam
    (800.0, 1800.0),   # cp_foam
    (20.0, 45.0),      # rho_foam
    (0.01, 0.50),      # ACH
    (300.0, 1200.0)    # Q_cool peak
])

def denormalize_params(p_norm):
    p_norm = np.clip(p_norm, 0.0, 1.0)
    lowers = bounds_raw[:, 0]
    uppers = bounds_raw[:, 1]
    return lowers + p_norm * (uppers - lowers)

def objective_normalized(p_norm):
    p_real = denormalize_params(p_norm)
    return run_energyplus_iteration(p_real)

# Starting from previous optimal point for high-precision local refinement
# k=0.0260 (0.3667), cp=1449 (0.6492), rho=32.2 (0.4880), ACH=0.115 (0.2143), Q=461.0 (0.1789)
x0_norm = [0.3667, 0.6492, 0.4880, 0.2143, 0.1789]

res = minimize(
    objective_normalized,
    x0_norm,
    method="Nelder-Mead",
    options={"maxiter": 600, "disp": True, "xatol": 1e-4, "fatol": 1e-4}
)

print("\n" + "=" * 95)
print("       HIGH-ITERATION ASHRAE & DTW CALIBRATION COMPLETED SUCCESSFULLY!        ")
print("=" * 95)
print(f"Optimal Composite Loss: {best_loss:.3f}")
print(f"Optimal ASHRAE CV(RMSE): {best_cv_rmse:.2f}% (Target <= 5.0%)")
print(f"Optimal ASHRAE NMBE:     {best_nmbe:.2f}% (Target <= 2.0%)")

k_opt, cp_opt, rho_opt, ach_opt, q_opt = best_params
print(f"\nCalibrated Physical Parameters (High-Iteration):")
print(f"• Foam Conductivity k:   {k_opt:.5f} W/(m·K)")
print(f"• Foam Specific Heat cp: {cp_opt:.1f} J/(kg·K)")
print(f"• Foam Density rho:      {rho_opt:.1f} kg/m³")
print(f"• Chamber Infiltration:  {ach_opt:.3f} ACH")
print(f"• Peak AC Cooling Q:     {q_opt:.1f} W")
print(f"Saved Calibrated IDF to: {FINAL_IDF_PATH}")

rmse_final = np.sqrt(np.mean((best_Tsim - Tz_ema)**2))
mae_final = np.mean(np.abs(best_Tsim - Tz_ema))
r2_final = 1.0 - (np.sum((Tz_ema - best_Tsim)**2) / np.sum((Tz_ema - np.mean(Tz_ema))**2))

plt.figure(figsize=(12, 6), dpi=300)
sensor_times_min = np.linspace(0, 170.1, N_sensor)
plt.plot(sensor_times_min, Tz_raw, label="Cleaned Raw Sensor $T_z$ (0.50 S1 + 0.30 S2 + 0.20 S3)", color="#a1d99b", alpha=0.4, linewidth=1.5)
plt.plot(sensor_times_min, Tz_ema, label="EMA-Smoothed Target Sensor $T_z$", color="#2ca02c", linewidth=2.5)
plt.plot(sensor_times_min, best_Tsim, label=f"High-Iter EnergyPlus $T_{{sim}}$ (ASHRAE CV={best_cv_rmse:.1f}%)", color="#9467bd", linewidth=2.2, linestyle="--")

plt.title("High-Iteration ASHRAE & DTW Calibrated EnergyPlus vs. Sensor Pulldown", fontsize=14, fontweight="bold", pad=15)
plt.xlabel("Elapsed Time (Minutes)", fontsize=12)
plt.ylabel("Chamber Zone Air Temperature (°C)", fontsize=12)
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(fontsize=11, loc="upper right")

textstr = (
    f"High-Iter Calibrated Parameters:\n"
    f"• $k_{{foam}}$ = {k_opt:.4f} W/(m·K)\n"
    f"• $c_{{p,foam}}$ = {cp_opt:.0f} J/(kg·K)\n"
    f"• $\\rho_{{foam}}$ = {rho_opt:.1f} kg/m³\n"
    f"• $\\text{{ACH}}$ = {ach_opt:.3f} hr⁻¹\n"
    f"• $Q_{{cool}}$ = {q_opt:.0f} W\n\n"
    f"ASHRAE Guideline 14 Metrics:\n"
    f"• CV(RMSE) = {best_cv_rmse:.2f}% (Target ≤ 5%)\n"
    f"• NMBE     = {best_nmbe:.2f}% (Target ≤ 2%)\n"
    f"• RMSE     = {rmse_final:.2f} °C\n"
    f"• MAE      = {mae_final:.2f} °C\n"
    f"• R²       = {r2_final:.4f}"
)
props = dict(boxstyle="round,pad=0.6", facecolor="white", alpha=0.9, edgecolor="#ccc")
plt.gca().text(0.03, 0.08, textstr, transform=plt.gca().transAxes, fontsize=10, verticalalignment="bottom", bbox=props)

plt.tight_layout()
plt.savefig(PLOT_PATH)
plt.close()

print(f"Saved High-Iteration Plot to: {PLOT_PATH}")
