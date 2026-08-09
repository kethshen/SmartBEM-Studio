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

# 1. Paths & Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
RIG_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig")
CALIBRATED_V1_DIR = SCRIPT_DIR

MASTER_IDF_PATH = os.path.join(CALIBRATED_V1_DIR, "hanger_chamber_base_template.idf")
EPW_PATH = os.path.join(CALIBRATED_V1_DIR, "test_day_weather_merged_1min.epw")
CSV_CLEANED_PATH = os.path.join(CALIBRATED_V1_DIR, "day_1_p_1.csv")
OUT_DIR = os.path.join(CALIBRATED_V1_DIR, "sim_output")
FINAL_IDF_PATH = os.path.join(CALIBRATED_V1_DIR, "hanger_chamber_after_calibrated_v1.idf")
PLOT_PATH = os.path.join(CALIBRATED_V1_DIR, "hanger_chamber_after_calibrated_v1.png")

ENERGYPLUS_EXE = r"C:\EnergyPlusV25-2-0\energyplus.exe"
if not os.path.exists(ENERGYPLUS_EXE):
    ENERGYPLUS_EXE = shutil.which("energyplus")

os.makedirs(OUT_DIR, exist_ok=True)

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

# 3. Load Sensor Reference Trajectory (170.1 min test window) & Clean Signals
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

# History Tracking Lists for Diagnostic Plots
history_iters = []
history_loss = []
history_cv_rmse = []
history_nmbe = []
history_rmse = []
history_mae = []
history_r2 = []

history_k = []
history_cp = []
history_rho = []
history_ach = []
history_q = []

print("=" * 95)
print("  LAUNCHING STAGE 2 ASHRAE GUIDELINE 14 & DTW SHAPE-MATCHING CALIBRATION LOOP  ")
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

    # 3. Update Cooling Capacity Q_cool (Robust replacement)
    q_start = idf_str.find("Maximum Total Cooling Capacity")
    if q_start != -1:
        line_start = idf_str.rfind("\n", 0, q_start) + 1
        line_end = idf_str.find("\n", q_start)
        idf_str = idf_str[:line_start] + f"  {q_cool:.1f},                                    !- Maximum Total Cooling Capacity {{W}}" + idf_str[line_end:]

    # Write temporary IDF file
    temp_idf = os.path.join(OUT_DIR, "temp_calibration_ashrae.idf")
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
    
    # Rig test window at 1-min resolution (13:26 PM to 16:16 PM = Minute 806 to 976)
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
    cv_rmse = (rmse / mean_Tz) * 100.0  # CV(RMSE) %
    nmbe = (np.mean(T_sim_interp - Tz_ema) / mean_Tz) * 100.0  # NMBE %
    dtw_dist = compute_dtw_distance(T_sim_interp, Tz_ema)  # DTW Distance
    
    # Additional Metrics
    mae = np.mean(np.abs(T_sim_interp - Tz_ema))
    ss_tot = np.sum((Tz_ema - mean_Tz)**2)
    r2 = 1.0 - (np.sum((Tz_ema - T_sim_interp)**2) / ss_tot) if ss_tot > 0 else 0.0

    # Composite ASHRAE + DTW Loss Function
    loss = cv_rmse + 0.5 * abs(nmbe) + 2.0 * dtw_dist
    
    # Store History
    history_iters.append(iteration_counter)
    history_loss.append(loss)
    history_cv_rmse.append(cv_rmse)
    history_nmbe.append(nmbe)
    history_rmse.append(rmse)
    history_mae.append(mae)
    history_r2.append(r2)

    history_k.append(k_foam)
    history_cp.append(cp_foam)
    history_rho.append(rho_foam)
    history_ach.append(ach)
    history_q.append(q_cool)

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

# 4. Initial Guesses & Bounds in Normalized Scale [0, 1]
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

x0_norm = [0.33, 0.60, 0.48, 0.18, 0.33]  # Normalized initial guess

# Execute Nelder-Mead Optimization on normalized parameters
res = minimize(
    objective_normalized,
    x0_norm,
    method="Nelder-Mead",
    options={"maxiter": 300, "disp": True, "xatol": 1e-3, "fatol": 1e-2}
)

print("\n" + "=" * 95)
print("              STAGE 2 ASHRAE & DTW CALIBRATION COMPLETED SUCCESSFULLY!             ")
print("=" * 95)
print(f"Optimal Composite Loss: {best_loss:.3f}")
print(f"Optimal ASHRAE CV(RMSE): {best_cv_rmse:.2f}% (Target <= 5.0%)")
print(f"Optimal ASHRAE NMBE:     {best_nmbe:.2f}% (Target <= 2.0%)")

k_opt, cp_opt, rho_opt, ach_opt, q_opt = best_params
print(f"\nCalibrated Physical Parameters:")
print(f"• Foam Conductivity k:   {k_opt:.5f} W/(m·K)")
print(f"• Foam Specific Heat cp: {cp_opt:.1f} J/(kg·K)")
print(f"• Foam Density rho:      {rho_opt:.1f} kg/m³")
print(f"• Chamber Infiltration:  {ach_opt:.3f} ACH")
print(f"• Peak AC Cooling Q:     {q_opt:.1f} W")
print(f"Saved Calibrated IDF to: {FINAL_IDF_PATH}")

# 5. Final Evaluation Metrics & High-Resolution Plot
rmse_final = np.sqrt(np.mean((best_Tsim - Tz_ema)**2))
mae_final = np.mean(np.abs(best_Tsim - Tz_ema))
r2_final = 1.0 - (np.sum((Tz_ema - best_Tsim)**2) / np.sum((Tz_ema - np.mean(Tz_ema))**2))

plt.figure(figsize=(12, 6), dpi=300)
sensor_times_min = np.linspace(0, 170.1, N_sensor)
plt.plot(sensor_times_min, Tz_ema, label="Weighted Tz", color="#2A9D8F", linewidth=2.5)
plt.plot(sensor_times_min, best_Tsim, label="Calibrated Tz", color="#FF6B6B", linewidth=2.2, linestyle="--")

plt.title("calibrated_v1_initial_envelope_baseline", fontsize=14, fontweight="bold", pad=15)
plt.xlabel("Elapsed Time (Minutes)", fontsize=12)
plt.ylabel("Chamber Zone Air Temperature (°C)", fontsize=12)
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(fontsize=11, loc="upper right", frameon=True, facecolor="white", edgecolor="none")

textstr = (
    f"Calibrated Parameters:\n"
    f"• $k_{{foam}}$ = {k_opt:.4f} W/(m·K)\n"
    f"• $c_{{p,foam}}$ = {cp_opt:.0f} J/(kg·K)\n"
    f"• $\\rho_{{foam}}$ = {rho_opt:.1f} kg/m³\n"
    f"• $\\text{{ACH}}$ = {ach_opt:.3f} hr⁻¹\n"
    f"• $Q_{{cool}}$ = {q_opt:.0f} W\n\n"
    f"Evaluation Metrics:\n"
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

print(f"Saved Calibrated Comparison Plot to: {PLOT_PATH}")

# 6. Diagnostic Figure 1: calibrated_v1_evaluation_parameters.png (5 Error Subplots)
EVAL_PLOT_PATH = os.path.join(CALIBRATED_V1_DIR, "calibrated_v1_evaluation_parameters.png")
fig, axes = plt.subplots(5, 1, figsize=(12, 14), sharex=True, dpi=300)

# 1. Composite Loss
max_loss_cushion = max(history_loss) * 1.15 if len(history_loss) > 0 else 30.0
axes[0].plot(history_iters, history_loss, color="#E63946", lw=1.8)
axes[0].set_ylabel("Composite Loss", fontsize=10, fontweight="bold")
axes[0].set_ylim(0, max_loss_cushion)
axes[0].set_title("calibrated_v1 — Optimization Convergence & Evaluation Metrics History", fontsize=13, fontweight="bold", pad=12)
axes[0].grid(True, linestyle=":", alpha=0.6)

# 2. CV(RMSE)
max_cv_cushion = max(history_cv_rmse) * 1.15 if len(history_cv_rmse) > 0 else 25.0
axes[1].plot(history_iters, history_cv_rmse, color="#2A9D8F", lw=1.8, label="CV(RMSE)")
axes[1].axhspan(0.0, 5.0, color="#2A9D8F", alpha=0.15, label="ASHRAE Target Band (0 - 5%)")
axes[1].axhline(5.0, color="#2A9D8F", linestyle="--", lw=1.2)
axes[1].set_ylabel("CV(RMSE) (%)", fontsize=10, fontweight="bold")
axes[1].set_ylim(0, max_cv_cushion)
axes[1].legend(loc="upper right", frameon=True, facecolor="white")
axes[1].grid(True, linestyle=":", alpha=0.6)

# 3. NMBE
max_nmbe_abs = max(abs(min(history_nmbe)), abs(max(history_nmbe))) * 1.25 if len(history_nmbe) > 0 else 15.0
axes[2].plot(history_iters, history_nmbe, color="#3A86EF", lw=1.8, label="NMBE")
axes[2].axhspan(-2.0, 2.0, color="#2A9D8F", alpha=0.15, label="ASHRAE Target Band (±2%)")
axes[2].axhline(0.0, color="#6B2D5C", linestyle=":", lw=1.0)
axes[2].set_ylabel("NMBE (%)", fontsize=10, fontweight="bold")
axes[2].set_ylim(-max_nmbe_abs, max_nmbe_abs)
axes[2].legend(loc="upper right", frameon=True, facecolor="white")
axes[2].grid(True, linestyle=":", alpha=0.6)

# 4. Error (RMSE & MAE)
max_rmse_cushion = max(history_rmse) * 1.15 if len(history_rmse) > 0 else 15.0
axes[3].plot(history_iters, history_rmse, color="#9D4EDD", lw=1.8, label="RMSE (°C)")
axes[3].plot(history_iters, history_mae, color="#EB802A", lw=1.6, linestyle="--", label="MAE (°C)")
axes[3].set_ylabel("Error (°C)", fontsize=10, fontweight="bold")
axes[3].set_ylim(0, max_rmse_cushion)
axes[3].legend(loc="upper right", frameon=True, facecolor="white")
axes[3].grid(True, linestyle=":", alpha=0.6)

# 5. R² Score
axes[4].plot(history_iters, history_r2, color="#6B2D5C", lw=1.8)
axes[4].set_ylabel("R² Score", fontsize=10, fontweight="bold")
axes[4].set_xlabel("Optimization Iteration Step", fontsize=11, fontweight="bold")
axes[4].set_ylim(0.0, 1.05)
axes[4].grid(True, linestyle=":", alpha=0.6)

plt.tight_layout()
plt.savefig(EVAL_PLOT_PATH)
plt.close()
print(f"Saved Evaluation Parameters Plot to: {EVAL_PLOT_PATH}")

# 7. Diagnostic Figure 2: calibrated_v1_parameter_trajectories.png (5 Parameter Subplots)
PARAM_PLOT_PATH = os.path.join(CALIBRATED_V1_DIR, "calibrated_v1_parameter_trajectories.png")
fig, axes = plt.subplots(5, 1, figsize=(12, 14), sharex=True, dpi=300)

axes[0].plot(history_iters, history_k, color="#264653", lw=1.8)
axes[0].set_ylabel("k [W/(m·K)]", fontsize=10, fontweight="bold")
axes[0].set_ylim(0.0200, 0.0300)
axes[0].set_title("calibrated_v1 — Physical Parameter Calibration Trajectories", fontsize=13, fontweight="bold", pad=12)
axes[0].grid(True, linestyle=":", alpha=0.6)

axes[1].plot(history_iters, history_cp, color="#2A9D8F", lw=1.8)
axes[1].set_ylabel("cp [J/(kg·K)]", fontsize=10, fontweight="bold")
axes[1].set_ylim(600, 1700)
axes[1].grid(True, linestyle=":", alpha=0.6)

axes[2].plot(history_iters, history_rho, color="#EB802A", lw=1.8)
axes[2].set_ylabel("rho [kg/m³]", fontsize=10, fontweight="bold")
axes[2].set_ylim(30, 50)
axes[2].grid(True, linestyle=":", alpha=0.6)

axes[3].plot(history_iters, history_ach, color="#3A86EF", lw=1.8)
axes[3].set_ylabel("ACH [hr⁻¹]", fontsize=10, fontweight="bold")
axes[3].set_ylim(0.0, 0.20)
axes[3].grid(True, linestyle=":", alpha=0.6)

axes[4].plot(history_iters, history_q, color="#FF6B6B", lw=1.8)
axes[4].set_ylabel("Q_cool [W]", fontsize=10, fontweight="bold")
axes[4].set_xlabel("Optimization Iteration Step", fontsize=11, fontweight="bold")
axes[4].set_ylim(300, 750)
axes[4].grid(True, linestyle=":", alpha=0.6)

plt.tight_layout()
plt.savefig(PARAM_PLOT_PATH)
plt.close()
print(f"Saved Parameter Trajectories Plot to: {PARAM_PLOT_PATH}")
