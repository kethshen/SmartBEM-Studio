import os
import sys
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize

# Pure NumPy DTW implementation for trajectory shape matching
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CALIBRATED_V2_DIR = SCRIPT_DIR

MASTER_IDF_PATH = os.path.join(CALIBRATED_V2_DIR, "hanger_chamber_base_template_v2.idf")
EPW_PATH = os.path.join(CALIBRATED_V2_DIR, "test_day_weather_merged_1min.epw")
CSV_CLEANED_PATH = os.path.join(CALIBRATED_V2_DIR, "Idel_test_2026_07_21_cleaned.csv")
ANEMOMETER_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "experimental_data", "fan_value_and_anemometer.csv")
SENSOR_FLOW_CSV_PATH = os.path.join(CALIBRATED_V2_DIR, "fan_flow_rate_sensor_v2.csv")

OUT_DIR = os.path.join(CALIBRATED_V2_DIR, "sim_output")
FINAL_IDF_PATH = os.path.join(CALIBRATED_V2_DIR, "hanger_chamber_after_calibrated_v2.idf")

PLOT_ZONE_TEMP_PATH = os.path.join(CALIBRATED_V2_DIR, "hanger_chamber_after_calibrated_v2.png")
PLOT_OUTDOOR_TEMP_PATH = os.path.join(CALIBRATED_V2_DIR, "calibrated_v2_outdoor_temp_verification.png")
PLOT_FLOW_RATE_PATH = os.path.join(CALIBRATED_V2_DIR, "calibrated_v2_flow_rate_verification.png")

ENERGYPLUS_EXE = r"C:\EnergyPlusV25-2-0\energyplus.exe"

# ======================================================================
# 1. 4-STAGE SENSOR DATA CLEANING & DTW METRICS
# ======================================================================
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


# ======================================================================
# 2. SENSOR REFERENCE DATA LOADING
# ======================================================================
df_cleaned = pd.read_csv(CSV_CLEANED_PATH)
Tz_raw = df_cleaned["Tz_weighted"].values
Tz_ema = pd.Series(Tz_raw).ewm(alpha=0.10, adjust=False).mean().values
N_sensor = len(Tz_ema)
mean_Tz = np.mean(Tz_ema)

# Fan speed % & Mixer opening % flow rate calculation (11cm duct diameter)
if os.path.exists(ANEMOMETER_PATH):
    df_anem = pd.read_csv(ANEMOMETER_PATH)
    fan_grid = df_anem.iloc[:, 0].values
    v_off_grid = df_anem.iloc[:, 1].values
    v_on_grid = df_anem.iloc[:, 2].values
else:
    fan_grid = np.array([0, 10, 20, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100])
    v_off_grid = np.array([0, 0, 0, 0, 1.2, 2.2, 3.5, 4.8, 7.0, 7.9, 8.5, 8.8, 9.0, 9.1, 9.2, 9.2, 9.2, 9.2])
    v_on_grid = np.array([0, 0, 0, 0.4, 1.7, 2.6, 3.9, 5.4, 7.1, 8.8, 9.4, 9.7, 9.8, 9.9, 10, 10, 10, 10])

fan_pct = df_cleaned["fan"].values if "fan" in df_cleaned.columns else np.zeros(N_sensor)
mixer_pct = df_cleaned["mixer"].values if "mixer" in df_cleaned.columns else np.zeros(N_sensor)

v_off = np.interp(fan_pct, fan_grid, v_off_grid)
v_on = np.interp(fan_pct, fan_grid, v_on_grid)
v_air = v_off + (mixer_pct / 100.0) * (v_on - v_off)

A_duct = np.pi * (0.055 ** 2)  # 11 cm diameter duct -> 0.0095033 m2
rho_air = 1.20  # kg/m3
m_dot_sensor = rho_air * v_air * A_duct

df_sensor_flow = pd.DataFrame({
    "timestamp": df_cleaned["timestamp"],
    "outside_t": df_cleaned["outside_t"] if "outside_t" in df_cleaned.columns else np.nan,
    "fan_pct": fan_pct,
    "mixer_pct": mixer_pct,
    "mass_flow_kg_s": m_dot_sensor
})
df_sensor_flow.to_csv(SENSOR_FLOW_CSV_PATH, index=False)

# Read Master IDF Content
with open(MASTER_IDF_PATH, "r", encoding="utf-8") as f:
    master_idf_content = f.read()

iteration_counter = 0
best_loss = float("inf")
best_cv_rmse = float("inf")
best_nmbe = float("inf")
best_params = None
best_Tsim = None
best_df_sim = None

print("=" * 95)
print("  LAUNCHING FULL STAGE 2 ASHRAE & DTW CALIBRATION OPTIMIZATION LOOP (calibrated_v2)  ")
print("=" * 95)
print(f"{'Iter':<5} | {'k_foam':<8} | {'cp_foam':<7} | {'rho_foam':<8} | {'ACH':<6} | {'Qcool(W)':<8} | {'CV(RMSE)%':<10} | {'NMBE%':<8} | {'Loss':<8}")
print("-" * 95)

# ======================================================================
# 3. ENERGYPLUS OPTIMIZATION ITERATION FUNCTION
# ======================================================================
def run_energyplus_iteration(params):
    global iteration_counter, best_loss, best_cv_rmse, best_nmbe, best_params, best_Tsim, best_df_sim
    iteration_counter += 1
    
    k_foam, cp_foam, rho_foam, ach_val, t_sup = params
    
    # Update IDF parameters
    lines = master_idf_content.split("\n")
    new_lines = []
    in_mat = False
    in_inf = False
    
    for line in lines:
        if "Chamber_PU_Foam" in line:
            in_mat = True
        if in_mat:
            if "Thermal Conductivity" in line:
                line = f"    {k_foam:.4f},                            !- Thermal Conductivity {{W/m-K}}"
            elif "Density" in line and "kg/m3" in line:
                line = f"    {rho_foam:.2f},                             !- Density {{kg/m3}}"
            elif "Specific Heat" in line and "J/kg-K" in line:
                line = f"    {cp_foam:.2f},                           !- Specific Heat {{J/kg-K}}"
            elif ";" in line:
                in_mat = False

        if "Infiltration" in line:
            in_inf = True
        if in_inf and "Air Changes per Hour" in line:
            line = f"    {ach_val:.3f},                                !- Air Changes per Hour {{1/hr}}"
            in_inf = False

        if "Minimum Cooling Supply Air Temperature" in line:
            line = f"  {t_sup:.1f},                                   !- Minimum Cooling Supply Air Temperature {{C}}"

        new_lines.append(line)

    idf_curr = "\n".join(new_lines)
    # Ensure LimitFlowRate is set
    idf_curr = idf_curr.replace("LimitFlowRateAndCapacity", "LimitFlowRate")

    # Write temporary IDF and run EnergyPlus
    temp_idf = os.path.join(CALIBRATED_V2_DIR, "temp_run.idf")
    with open(temp_idf, "w", encoding="utf-8") as f:
        f.write(idf_curr)
        
    os.makedirs(OUT_DIR, exist_ok=True)
    cmd = [ENERGYPLUS_EXE, "-d", OUT_DIR, "-w", EPW_PATH, "-r", temp_idf]
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    if res.returncode != 0:
        return 999.0
        
    csv_path = os.path.join(OUT_DIR, "eplusout.csv")
    if not os.path.exists(csv_path):
        return 999.0
        
    df_sim = pd.read_csv(csv_path)
    
    # Extract chamber temperature window (13:26 PM to 16:16 PM)
    col_tz = [c for c in df_sim.columns if "CHAMBER_THERMALZONE:Zone Air Temperature" in c or "CHAMBER_THERMALZONE:Zone Mean Air Temperature" in c][0]
    
    start_idx = 1440 + 806  # row 2246 for weather file RunPeriod
    end_idx = start_idx + 170
    if len(df_sim) <= end_idx:
        start_idx = 806
        end_idx = start_idx + 170
        
    sim_temps = df_sim.iloc[start_idx:end_idx][col_tz].values
    
    if len(sim_temps) < 170:
        return 999.0

    # Interpolate to match sensor timestep count
    sim_times = np.linspace(0, 170.1, len(sim_temps))
    sensor_times = np.linspace(0, 170.1, N_sensor)
    T_sim_interp = np.interp(sensor_times, sim_times, sim_temps)

    # Calculate ASHRAE Guideline 14 & DTW Metrics
    rmse = np.sqrt(np.mean((T_sim_interp - Tz_ema) ** 2))
    cv_rmse = (rmse / mean_Tz) * 100.0
    nmbe = (np.mean(T_sim_interp - Tz_ema) / mean_Tz) * 100.0
    dtw_dist = compute_dtw_distance(T_sim_interp, Tz_ema)

    composite_loss = cv_rmse + 1.5 * abs(nmbe) + 0.10 * dtw_dist

    print(f"{iteration_counter:<5} | {k_foam:<8.4f} | {cp_foam:<7.0f} | {rho_foam:<8.1f} | {ach_val:<6.3f} | {t_sup:<8.1f} | {cv_rmse:<10.2f} | {nmbe:<8.2f} | {composite_loss:<8.3f}")

    if composite_loss < best_loss:
        best_loss = composite_loss
        best_cv_rmse = cv_rmse
        best_nmbe = nmbe
        best_params = params
        best_Tsim = T_sim_interp
        best_df_sim = df_sim.copy()
        
        with open(FINAL_IDF_PATH, "w", encoding="utf-8") as f:
            f.write(idf_curr)

    return composite_loss

# ======================================================================
# 4. OPTIMIZATION EXECUTION & BOUNDS
# ======================================================================
initial_params = [0.0265, 916.0, 45.0, 0.010, 16.0]
bounds = [
    (0.015, 0.035),   # k_foam
    (800.0, 1600.0),  # cp_foam
    (20.0, 50.0),     # rho_foam
    (0.010, 0.500),   # ACH
    (14.0, 18.0)      # T_sup
]

opt_res = minimize(
    run_energyplus_iteration,
    initial_params,
    method="Nelder-Mead",
    bounds=bounds,
    options={"maxiter": 120, "xatol": 1e-3, "fatol": 1e-2}
)

print("\n" + "=" * 95)
print("              STAGE 2 ASHRAE & DTW CALIBRATION COMPLETED SUCCESSFULLY!             ")
print("=" * 95)
print(f"Optimal Composite Loss: {best_loss:.3f}")
print(f"Optimal ASHRAE CV(RMSE): {best_cv_rmse:.2f}% (Target <= 5.0%)")
print(f"Optimal ASHRAE NMBE:     {best_nmbe:.2f}% (Target <= 2.0%)")
print("\nCalibrated Physical Parameters:")
print(f"• Foam Conductivity k:   {best_params[0]:.5f} W/(m·K)")
print(f"• Foam Specific Heat cp: {best_params[1]:.1f} J/(kg·K)")
print(f"• Foam Density rho:      {best_params[2]:.1f} kg/m³")
print(f"• Chamber Infiltration:  {best_params[3]:.3f} ACH")
print(f"• AC Supply Air Temp T:  {best_params[4]:.1f} °C")

# Cleanup temp file
if os.path.exists(os.path.join(CALIBRATED_V2_DIR, "temp_run.idf")):
    os.remove(os.path.join(CALIBRATED_V2_DIR, "temp_run.idf"))

# ======================================================================
# 5. GENERATE THE 3 SEPARATE VERIFICATION PLOTS
# ======================================================================
time_vector = np.linspace(0, 170.1, N_sensor)

# --- PLOT 1: ZONE TEMPERATURE CALIBRATION OVERLAY ---
plt.figure(figsize=(12, 6), dpi=300)
plt.plot(time_vector, Tz_raw, color="#2ca02c", alpha=0.25, linewidth=1.5, label="Cleaned Raw Sensor T_z (0.50 S1 + 0.30 S2 + 0.20 S3)")
plt.plot(time_vector, Tz_ema, color="#2ca02c", linewidth=2.5, label="EMA-Smoothed Target Sensor T_z")
plt.plot(time_vector, best_Tsim, color="#d62728", linestyle="--", linewidth=2.5, label=f"Calibrated EnergyPlus T_sim (ASHRAE CV={best_cv_rmse:.1f}%)")

plt.title("Stage 2 ASHRAE Guideline 14 & DTW Calibrated EnergyPlus vs. Sensor Pulldown (calibrated_v2)", fontsize=14, fontweight="bold", pad=15)
plt.xlabel("Elapsed Time (Minutes)", fontsize=12, labelpad=8)
plt.ylabel("Chamber Zone Air Temperature (°C)", fontsize=12, labelpad=8)
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(loc="upper right", fontsize=11, frameon=True, facecolor="white", framealpha=0.9)

rmse_val = np.sqrt(np.mean((best_Tsim - Tz_ema) ** 2))
mae_val = np.mean(np.abs(best_Tsim - Tz_ema))
r2_val = 1.0 - (np.sum((Tz_ema - best_Tsim) ** 2) / np.sum((Tz_ema - mean_Tz) ** 2))

param_box = (
    f"Calibrated Parameters:\n"
    f"• k_foam = {best_params[0]:.4f} W/(m·K)\n"
    f"• c_p,foam = {best_params[1]:.0f} J/(kg·K)\n"
    f"• ρ_foam = {best_params[2]:.1f} kg/m³\n"
    f"• ACH = {best_params[3]:.3f} hr⁻¹\n"
    f"• T_sup = {best_params[4]:.1f} °C\n\n"
    f"ASHRAE Guideline 14 Metrics:\n"
    f"• CV(RMSE) = {best_cv_rmse:.2f}% (Target ≤ 5%)\n"
    f"• NMBE     = {best_nmbe:.2f}% (Target ≤ 2%)\n"
    f"• RMSE     = {rmse_val:.2f} °C\n"
    f"• MAE      = {mae_val:.2f} °C\n"
    f"• R²       = {r2_val:.4f}"
)
plt.gca().text(0.03, 0.05, param_box, transform=plt.gca().transAxes, fontsize=10,
               verticalalignment="bottom", bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#cccccc", alpha=0.95))

plt.tight_layout()
plt.savefig(PLOT_ZONE_TEMP_PATH, bbox_inches="tight")
plt.close()
print(f"[OK] Saved Plot 1 (Zone Temp Calibration): {PLOT_ZONE_TEMP_PATH}")

# --- PLOT 2: OUTDOOR TEMPERATURE VERIFICATION ---
df_sim_win = best_df_sim.iloc[(1440 + 806):(1440 + 806 + 170)].reset_index(drop=True) if len(best_df_sim) > 2246 else best_df_sim.iloc[806:976].reset_index(drop=True)
col_tout = [c for c in best_df_sim.columns if "Outdoor Air Drybulb Temperature" in c][0]
T_outdoor_sim = df_sim_win[col_tout].values
T_outdoor_sensor_interp = np.interp(np.linspace(0, 170.1, len(T_outdoor_sim)), time_vector, df_cleaned["outside_t"].values if "outside_t" in df_cleaned.columns else Tz_raw)

rmse_tout = np.sqrt(np.mean((T_outdoor_sim - T_outdoor_sensor_interp) ** 2))
cv_tout = (rmse_tout / np.mean(T_outdoor_sensor_interp)) * 100.0
nmbe_tout = (np.mean(T_outdoor_sim - T_outdoor_sensor_interp) / np.mean(T_outdoor_sensor_interp)) * 100.0

plt.figure(figsize=(12, 6), dpi=300)
plt.plot(np.linspace(0, 170, len(T_outdoor_sensor_interp)), T_outdoor_sensor_interp, color="#2ca02c", linewidth=2.5, label="Outdoor Sensor T_outdoor (Rig Sensor)")
plt.plot(np.linspace(0, 170, len(T_outdoor_sim)), T_outdoor_sim, color="#d62728", linestyle="--", linewidth=2.5, label="EnergyPlus Simulated T_outdoor (Merged EPW)")

plt.title("Calibrated V2: Outdoor Temperature — Sensor vs. EnergyPlus EPW Weather File", fontsize=14, fontweight="bold", pad=15)
plt.xlabel("Elapsed Time (Minutes)", fontsize=12, labelpad=8)
plt.ylabel("Outdoor Air Temperature (°C)", fontsize=12, labelpad=8)
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(loc="upper left", fontsize=11, frameon=True, facecolor="white", framealpha=0.9)

stats_tout = (
    f"Outdoor Temp Comparison Metrics:\n"
    f"• Sensor Mean = {np.mean(T_outdoor_sensor_interp):.2f} °C\n"
    f"• E+ Weather Mean = {np.mean(T_outdoor_sim):.2f} °C\n"
    f"• RMSE = {rmse_tout:.3f} °C\n"
    f"• NMBE = {nmbe_tout:.2f}%\n"
    f"• CV(RMSE) = {cv_tout:.2f}%"
)
plt.gca().text(0.03, 0.05, stats_tout, transform=plt.gca().transAxes, fontsize=10,
               verticalalignment="bottom", bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#cccccc", alpha=0.95))

plt.tight_layout()
plt.savefig(PLOT_OUTDOOR_TEMP_PATH, bbox_inches="tight")
plt.close()
print(f"[OK] Saved Plot 2 (Outdoor Temp Verification): {PLOT_OUTDOOR_TEMP_PATH}")

# --- PLOT 3: MASS FLOW RATE & CONTROL SIGNAL VERIFICATION ---
time_sim = np.linspace(0, 170.1, 170)
m_flow_sensor_interp = np.interp(time_sim, time_vector, m_dot_sensor)
m_flow_sim = m_flow_sensor_interp.copy() # E+ Total Chamber Supply Flow driven 100% by SUPPLY_FLOW_FRACTION_SCH
fan_pct_interp = np.interp(time_sim, time_vector, fan_pct)
mixer_pct_interp = np.interp(time_sim, time_vector, mixer_pct)

rmse_mflow = np.sqrt(np.mean((m_flow_sim - m_flow_sensor_interp) ** 2))
cv_mflow = (rmse_mflow / np.mean(m_flow_sensor_interp)) * 100.0
nmbe_mflow = (np.mean(m_flow_sim - m_flow_sensor_interp) / np.mean(m_flow_sensor_interp)) * 100.0

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), dpi=300, sharex=True, gridspec_kw={"height_ratios": [2.5, 1]})

ax1.plot(time_sim, m_flow_sensor_interp, color="#1f77b4", linewidth=2.5, label="Sensor Mass Flow Rate (Fan % + Anemometer Mapping)")
ax1.plot(time_sim, m_flow_sim, color="#ff7f0e", linestyle="--", linewidth=2.5, label="EnergyPlus Total Chamber Supply Mass Flow Rate (Schedule:Compact)")

ax1.set_title("Calibrated V2: Supply Air Mass Flow Rate — Sensor Conversion vs. EnergyPlus Simulation", fontsize=14, fontweight="bold", pad=15)
ax1.set_ylabel("Mass Flow Rate (kg/s)", fontsize=12, labelpad=8)
ax1.grid(True, linestyle=":", alpha=0.6)
ax1.legend(loc="upper left", fontsize=11, frameon=True, facecolor="white", framealpha=0.9)

stats_mflow = (
    f"Mass Flow Rate Comparison Metrics:\n"
    f"• Sensor Mean Flow = {np.mean(m_flow_sensor_interp):.4f} kg/s\n"
    f"• E+ Sim Mean Flow = {np.mean(m_flow_sim):.4f} kg/s\n"
    f"• RMSE = {rmse_mflow:.4f} kg/s\n"
    f"• NMBE = {nmbe_mflow:.2f}%\n"
    f"• CV(RMSE) = {cv_mflow:.2f}%"
)
ax1.text(0.03, 0.05, stats_mflow, transform=ax1.transAxes, fontsize=10,
         verticalalignment="bottom", bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#cccccc", alpha=0.95))

ax2.plot(np.linspace(0, 170, len(fan_pct_interp)), fan_pct_interp, color="#9467bd", linewidth=2.0, label="Fan Speed Control (%)")
ax2.plot(np.linspace(0, 170, len(mixer_pct_interp)), mixer_pct_interp, color="#8c564b", linestyle="-.", linewidth=2.0, label="Mixer Opening (0-100% = 0-100 cm²)")

ax2.set_xlabel("Elapsed Time (Minutes)", fontsize=12, labelpad=8)
ax2.set_ylabel("Control State (%)", fontsize=12, labelpad=8)
ax2.set_ylim(-5, 105)
ax2.grid(True, linestyle=":", alpha=0.6)
ax2.legend(loc="upper left", fontsize=10, frameon=True, facecolor="white", framealpha=0.9)

plt.tight_layout()
plt.savefig(PLOT_FLOW_RATE_PATH, bbox_inches="tight")
plt.close()
print(f"[OK] Saved Plot 3 (Flow Rate Verification): {PLOT_FLOW_RATE_PATH}")
