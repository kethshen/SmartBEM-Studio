import os
import sys
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ======================================================================
# PATH DEFINITIONS (calibrated_v2)
# ======================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CALIBRATED_V2_DIR = SCRIPT_DIR

MASTER_IDF_PATH = os.path.join(CALIBRATED_V2_DIR, "hanger_chamber_base_template_v2.idf")
CALIBRATED_IDF_PATH = os.path.join(CALIBRATED_V2_DIR, "hanger_chamber_after_calibrated_v2.idf")
EPW_PATH = os.path.join(CALIBRATED_V2_DIR, "test_day_weather_merged_1min.epw")
CSV_CLEANED_PATH = os.path.join(CALIBRATED_V2_DIR, "Idel_test_2026_07_21_cleaned.csv")
ANEMOMETER_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "experimental_data", "fan_value_and_anemometer.csv")
SENSOR_FLOW_CSV_PATH = os.path.join(CALIBRATED_V2_DIR, "fan_flow_rate_sensor_v2.csv")

OUT_DIR = os.path.join(CALIBRATED_V2_DIR, "sim_output")
PLOT_OUTDOOR_TEMP_PATH = os.path.join(CALIBRATED_V2_DIR, "calibrated_v2_outdoor_temp_verification.png")
PLOT_FLOW_RATE_PATH = os.path.join(CALIBRATED_V2_DIR, "calibrated_v2_flow_rate_verification.png")

ENERGYPLUS_EXE = r"C:\EnergyPlusV25-2-0\energyplus.exe"

# ======================================================================
# 1. FAN ANEMOMETER & MIXER FLOW RATE CONVERSION
# ======================================================================
def calculate_sensor_flow_rates():
    if os.path.exists(ANEMOMETER_PATH):
        df_anem = pd.read_csv(ANEMOMETER_PATH)
        fan_grid = df_anem.iloc[:, 0].values
        v_off_grid = df_anem.iloc[:, 1].values
        v_on_grid = df_anem.iloc[:, 2].values
    else:
        fan_grid = np.array([0, 10, 20, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100])
        v_off_grid = np.array([0, 0, 0, 0, 1.2, 2.2, 3.5, 4.8, 7.0, 7.9, 8.5, 8.8, 9.0, 9.1, 9.2, 9.2, 9.2, 9.2])
        v_on_grid = np.array([0, 0, 0, 0.4, 1.7, 2.6, 3.9, 5.4, 7.1, 8.8, 9.4, 9.7, 9.8, 9.9, 10, 10, 10, 10])

    df_rig = pd.read_csv(CSV_CLEANED_PATH)
    fan_pct = df_rig["fan"].values if "fan" in df_rig.columns else np.zeros(len(df_rig))
    mixer_pct = df_rig["mixer"].values if "mixer" in df_rig.columns else np.zeros(len(df_rig))

    v_off = np.interp(fan_pct, fan_grid, v_off_grid)
    v_on = np.interp(fan_pct, fan_grid, v_on_grid)
    v_air = v_off + (mixer_pct / 100.0) * (v_on - v_off)

    A_duct = np.pi * (0.055 ** 2)  # 11 cm diameter duct -> 0.0095033 m2
    rho_air = 1.20  # kg/m3

    Q_vol = v_air * A_duct  # m3/s
    m_dot = rho_air * Q_vol  # kg/s
    mixer_area_cm2 = mixer_pct  # 100% = 100 cm2 (10cm x 10cm square opening)
    mixer_area_m2 = (mixer_pct / 100.0) * 0.010

    df_out = pd.DataFrame({
        "timestamp": df_rig["timestamp"],
        "outside_t": df_rig["outside_t"] if "outside_t" in df_rig.columns else np.nan,
        "fan_pct": fan_pct,
        "mixer_pct": mixer_pct,
        "mixer_area_cm2": mixer_area_cm2,
        "mixer_area_m2": mixer_area_m2,
        "air_velocity_m_s": v_air,
        "volumetric_flow_m3_s": Q_vol,
        "mass_flow_kg_s": m_dot
    })

    df_out.to_csv(SENSOR_FLOW_CSV_PATH, index=False)
    print(f"[OK] Saved sensor flow rate data to: {SENSOR_FLOW_CSV_PATH}")
    return df_out

# ======================================================================
# 2. RUN ENERGYPLUS SIMULATION
# ======================================================================
def run_energyplus():
    target_idf = CALIBRATED_IDF_PATH if os.path.exists(CALIBRATED_IDF_PATH) else MASTER_IDF_PATH
    os.makedirs(OUT_DIR, exist_ok=True)
    
    cmd = [ENERGYPLUS_EXE, "-d", OUT_DIR, "-w", EPW_PATH, "-r", target_idf]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("[ERROR] EnergyPlus simulation failed:")
        print(res.stderr)
        sys.exit(1)
    
    csv_out = os.path.join(OUT_DIR, "eplusout.csv")
    if not os.path.exists(csv_out):
        print(f"[ERROR] eplusout.csv not found in {OUT_DIR}")
        sys.exit(1)
    
    df_sim = pd.read_csv(csv_out)
    return df_sim

# ======================================================================
# 3. METRIC COMPUTATION
# ======================================================================
def compute_metrics(sim_vals, sensor_vals):
    rmse = np.sqrt(np.mean((sim_vals - sensor_vals) ** 2))
    mean_val = np.mean(sensor_vals)
    cv_rmse = (rmse / mean_val) * 100.0 if mean_val != 0 else 0.0
    nmbe = (np.mean(sim_vals - sensor_vals) / mean_val) * 100.0 if mean_val != 0 else 0.0
    mae = np.mean(np.abs(sim_vals - sensor_vals))
    
    ss_res = np.sum((sensor_vals - sim_vals) ** 2)
    ss_tot = np.sum((sensor_vals - mean_val) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    return {"rmse": rmse, "cv_rmse": cv_rmse, "nmbe": nmbe, "mae": mae, "r2": r2}

# ======================================================================
# MAIN EXECUTION & PLOTTING
# ======================================================================
def main():
    print("=" * 80)
    print("  CALIBRATED V2: OUTDOOR TEMP & FLOW RATE VERIFICATION RUN  ")
    print("=" * 80)

    # 1. Compute & save sensor flow rates
    df_sensor = calculate_sensor_flow_rates()

    # 2. Execute EnergyPlus simulation
    df_sim = run_energyplus()

    # 3. Extract 170-minute window (13:26 PM to 16:16 PM)
    # EnergyPlus RunPeriod starts at row 1440 in eplusout.csv
    N_win = 170
    start_idx = 1440 + 806  # row 2246
    end_idx = start_idx + N_win
    
    if len(df_sim) <= end_idx:
        start_idx = 806
        end_idx = start_idx + N_win
    
    df_sim_win = df_sim.iloc[start_idx:end_idx].reset_index(drop=True)

    # Outdoor drybulb temperature column
    col_tout = [c for c in df_sim.columns if "Outdoor Air Drybulb Temperature" in c][0]
    T_outdoor_sim = df_sim_win[col_tout].values

    # System node mass flow rate column (Chamber Outdoor Air / Ventilation Node)
    col_mflow_candidates = [
        c for c in df_sim.columns
        if "CHAMBER_IDEALLOADS OUTDOOR AIR INLET NODE" in c
        or "CHAMBER_THERMALZONE:Zone Mechanical Ventilation" in c
    ]
    if col_mflow_candidates:
        col_mflow = col_mflow_candidates[0]
    else:
        col_mflow = [c for c in df_sim.columns if "System Node Mass Flow Rate" in c][0]
    m_flow_sim = df_sim_win[col_mflow].values

    # Resample sensor data to 170 1-minute steps
    T_outdoor_sensor_raw = df_sensor["outside_t"].values
    m_flow_sensor_raw = df_sensor["mass_flow_kg_s"].values
    fan_pct_raw = df_sensor["fan_pct"].values
    mixer_pct_raw = df_sensor["mixer_pct"].values

    time_sim = np.linspace(0, N_win, len(T_outdoor_sim))
    time_sensor = np.linspace(0, N_win, len(T_outdoor_sensor_raw))

    T_outdoor_sensor_interp = np.interp(time_sim, time_sensor, T_outdoor_sensor_raw)
    m_flow_sensor_interp = np.interp(time_sim, time_sensor, m_flow_sensor_raw)
    fan_pct_interp = np.interp(time_sim, time_sensor, fan_pct_raw)
    mixer_pct_interp = np.interp(time_sim, time_sensor, mixer_pct_raw)

    # 4. Compute error metrics
    m_tout = compute_metrics(T_outdoor_sim, T_outdoor_sensor_interp)
    m_mflow = compute_metrics(m_flow_sim, m_flow_sensor_interp)

    print("\n--- OUTDOOR TEMPERATURE VERIFICATION METRICS ---")
    print(f"Sensor Outdoor Temp Mean: {np.mean(T_outdoor_sensor_interp):.2f} °C")
    print(f"EnergyPlus Outdoor Temp Mean: {np.mean(T_outdoor_sim):.2f} °C")
    print(f"RMSE: {m_tout['rmse']:.3f} °C | MAE: {m_tout['mae']:.3f} °C | NMBE: {m_tout['nmbe']:.2f}% | CV(RMSE): {m_tout['cv_rmse']:.2f}% | R2: {m_tout['r2']:.4f}")

    print("\n--- MASS FLOW RATE VERIFICATION METRICS ---")
    print(f"Sensor Mass Flow Rate Mean: {np.mean(m_flow_sensor_interp):.4f} kg/s")
    print(f"EnergyPlus Mass Flow Rate Mean: {np.mean(m_flow_sim):.4f} kg/s")
    print(f"RMSE: {m_mflow['rmse']:.4f} kg/s | MAE: {m_mflow['mae']:.4f} kg/s | NMBE: {m_mflow['nmbe']:.2f}% | CV(RMSE): {m_mflow['cv_rmse']:.2f}%")

    # ======================================================================
    # PLOT 1: OUTDOOR TEMPERATURE VERIFICATION
    # ======================================================================
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    ax.plot(time_sim, T_outdoor_sensor_interp, color="#2ca02c", linewidth=2.5, label="Outdoor Sensor T_outdoor (Rig Sensor)")
    ax.plot(time_sim, T_outdoor_sim, color="#d62728", linestyle="--", linewidth=2.5, label="EnergyPlus Simulated T_outdoor (Merged EPW)")

    ax.set_title("Calibrated V2: Outdoor Temperature — Sensor vs. EnergyPlus EPW Weather File", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Elapsed Time (Minutes)", fontsize=12, labelpad=8)
    ax.set_ylabel("Outdoor Air Temperature (°C)", fontsize=12, labelpad=8)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", fontsize=11, frameon=True, facecolor="white", framealpha=0.9)

    stats_text_tout = (
        f"Outdoor Temp Comparison Metrics:\n"
        f"• Sensor Mean = {np.mean(T_outdoor_sensor_interp):.2f} °C\n"
        f"• E+ Weather Mean = {np.mean(T_outdoor_sim):.2f} °C\n"
        f"• RMSE = {m_tout['rmse']:.3f} °C\n"
        f"• MAE = {m_tout['mae']:.3f} °C\n"
        f"• NMBE = {m_tout['nmbe']:.2f}%\n"
        f"• CV(RMSE) = {m_tout['cv_rmse']:.2f}%\n"
        f"• R² = {m_tout['r2']:.4f}"
    )
    ax.text(0.03, 0.05, stats_text_tout, transform=ax.transAxes, fontsize=10,
            verticalalignment="bottom", bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#cccccc", alpha=0.95))

    plt.tight_layout()
    plt.savefig(PLOT_OUTDOOR_TEMP_PATH, bbox_inches="tight")
    plt.close()
    print(f"\n[OK] Saved Outdoor Temperature Plot to: {PLOT_OUTDOOR_TEMP_PATH}")

    # ======================================================================
    # PLOT 2: FLOW RATE VERIFICATION & CONTROL SIGNALS
    # ======================================================================
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), dpi=300, sharex=True, gridspec_kw={"height_ratios": [2.5, 1]})

    # Upper Subplot: Mass Flow Rate (kg/s)
    ax1.plot(time_sim, m_flow_sensor_interp, color="#1f77b4", linewidth=2.5, label="Sensor Mass Flow Rate (Fan % + Anemometer Mapping)")
    ax1.plot(time_sim, m_flow_sim, color="#ff7f0e", linestyle="--", linewidth=2.5, label="EnergyPlus System Supply Mass Flow Rate (Node 6)")

    ax1.set_title("Calibrated V2: Supply Air Mass Flow Rate — Sensor Conversion vs. EnergyPlus Simulation", fontsize=14, fontweight="bold", pad=15)
    ax1.set_ylabel("Mass Flow Rate (kg/s)", fontsize=12, labelpad=8)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper left", fontsize=11, frameon=True, facecolor="white", framealpha=0.9)

    stats_text_mflow = (
        f"Mass Flow Rate Comparison Metrics:\n"
        f"• Sensor Mean Flow = {np.mean(m_flow_sensor_interp):.4f} kg/s\n"
        f"• E+ Sim Mean Flow = {np.mean(m_flow_sim):.4f} kg/s\n"
        f"• RMSE = {m_mflow['rmse']:.4f} kg/s\n"
        f"• MAE = {m_mflow['mae']:.4f} kg/s\n"
        f"• NMBE = {m_mflow['nmbe']:.2f}%\n"
        f"• CV(RMSE) = {m_mflow['cv_rmse']:.2f}%"
    )
    ax1.text(0.03, 0.05, stats_text_mflow, transform=ax1.transAxes, fontsize=10,
             verticalalignment="bottom", bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#cccccc", alpha=0.95))

    # Lower Subplot: Fan Speed % & Mixer Opening %
    ax2.plot(time_sim, fan_pct_interp, color="#9467bd", linewidth=2.0, label="Fan Speed Control (%)")
    ax2.plot(time_sim, mixer_pct_interp, color="#8c564b", linestyle="-.", linewidth=2.0, label="Mixer Opening (0-100% = 0-100 cm²)")

    ax2.set_xlabel("Elapsed Time (Minutes)", fontsize=12, labelpad=8)
    ax2.set_ylabel("Control State (%)", fontsize=12, labelpad=8)
    ax2.set_ylim(-5, 105)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper left", fontsize=10, frameon=True, facecolor="white", framealpha=0.9)

    plt.tight_layout()
    plt.savefig(PLOT_FLOW_RATE_PATH, bbox_inches="tight")
    plt.close()
    print(f"[OK] Saved Flow Rate Plot to: {PLOT_FLOW_RATE_PATH}")

    print("\n==========================================================================")
    print("  CALIBRATED V2 VERIFICATION COMPLETED SUCCESSFULLY!  ")
    print("==========================================================================")

if __name__ == "__main__":
    main()
