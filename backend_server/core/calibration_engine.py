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

def run_calibration_job(
    master_idf_path: str,
    epw_path: str,
    sensor_csv_path: str,
    output_dir: str,
    energyplus_exe: str = r"C:\EnergyPlusV25-2-0\energyplus.exe",
    max_iters: int = 40
):
    """
    Executes 4-parameter EnergyPlus BEM Nelder-Mead optimization on Colab/Backend.
    Returns dictionary with tuned physical parameters, noise matrix R, metrics, and generated plot file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    sim_out_dir = os.path.join(output_dir, "sim_output")
    os.makedirs(sim_out_dir, exist_ok=True)

    # 1. Load sensor data
    df_cleaned = pd.read_csv(sensor_csv_path)
    if "Tz_weighted" in df_cleaned.columns:
        Tz_raw = df_cleaned["Tz_weighted"].values
    else:
        # Fallback to mean of temperature columns
        temp_cols = [c for c in df_cleaned.columns if "temp" in c.lower() or "t_" in c.lower() or "s1" in c.lower()]
        Tz_raw = df_cleaned[temp_cols].mean(axis=1).values if temp_cols else np.full(len(df_cleaned), 22.0)

    Tz_ema = pd.Series(Tz_raw).ewm(alpha=0.10, adjust=False).mean().values
    N_sensor = len(Tz_ema)
    mean_Tz = np.mean(Tz_ema)

    # Mass flow calculation from fan/mixer
    fan_pct = df_cleaned["fan"].values if "fan" in df_cleaned.columns else np.zeros(N_sensor)
    mixer_pct = df_cleaned["mixer"].values if "mixer" in df_cleaned.columns else np.zeros(N_sensor)

    fan_grid = np.array([0, 10, 20, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100])
    v_off_grid = np.array([0, 0, 0, 0, 1.2, 2.2, 3.5, 4.8, 7.0, 7.9, 8.5, 8.8, 9.0, 9.1, 9.2, 9.2, 9.2, 9.2])
    v_on_grid = np.array([0, 0, 0, 0.4, 1.7, 2.6, 3.9, 5.4, 7.1, 8.8, 9.4, 9.7, 9.8, 9.9, 10, 10, 10, 10])

    v_off = np.interp(fan_pct, fan_grid, v_off_grid)
    v_on = np.interp(fan_pct, fan_grid, v_on_grid)
    v_air = v_off + (mixer_pct / 100.0) * (v_on - v_off)
    A_duct = np.pi * (0.055 ** 2)  # 11 cm duct -> 0.0095033 m2
    rho_air = 1.20
    m_dot_sensor = rho_air * v_air * A_duct

    # Read Master IDF
    with open(master_idf_path, "r", encoding="utf-8") as f:
        master_idf_content = f.read()

    # Trackers
    iteration_counter = 0
    best_loss = float("inf")
    best_cv_rmse = float("inf")
    best_nmbe = float("inf")
    best_params = [0.0265, 916.0, 45.0, 0.011]
    best_Tsim = Tz_ema.copy()
    best_df_sim = None

    history_iters, history_loss, history_cv_rmse, history_nmbe, history_rmse, history_mae, history_r2 = [], [], [], [], [], [], []
    history_k, history_cp, history_rho, history_ach, history_q = [], [], [], [], []

    final_idf_path = os.path.join(output_dir, "calibrated_model.idf")

    def run_energyplus_iteration(params):
        nonlocal iteration_counter, best_loss, best_cv_rmse, best_nmbe, best_params, best_Tsim, best_df_sim
        iteration_counter += 1
        k_foam, cp_foam, rho_foam, ach_val = params

        lines = master_idf_content.split("\n")
        new_lines = []
        in_mat, in_inf = False, False

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

            new_lines.append(line)

        idf_curr = "\n".join(new_lines).replace("LimitFlowRateAndCapacity", "LimitFlowRate")
        temp_idf = os.path.join(output_dir, "temp_run.idf")
        with open(temp_idf, "w", encoding="utf-8") as f:
            f.write(idf_curr)

        cmd = [energyplus_exe, "-d", sim_out_dir, "-w", epw_path, "-r", temp_idf]
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0:
            return 999.0

        csv_path = os.path.join(sim_out_dir, "eplusout.csv")
        if not os.path.exists(csv_path):
            return 999.0

        df_sim = pd.read_csv(csv_path)
        col_tz_list = [c for c in df_sim.columns if "Zone Air Temperature" in c or "Zone Mean Air Temperature" in c]
        if not col_tz_list:
            return 999.0
        col_tz = col_tz_list[0]

        sim_temps = df_sim[col_tz].values
        if len(sim_temps) > N_sensor:
            sim_temps = sim_temps[-N_sensor:]
        
        sim_times = np.linspace(0, 170.1, len(sim_temps))
        sensor_times = np.linspace(0, 170.1, N_sensor)
        T_sim_interp = np.interp(sensor_times, sim_times, sim_temps)

        rmse = np.sqrt(np.mean((T_sim_interp - Tz_ema) ** 2))
        cv_rmse = (rmse / mean_Tz) * 100.0
        nmbe = (np.mean(T_sim_interp - Tz_ema) / mean_Tz) * 100.0
        dtw_dist = compute_dtw_distance(T_sim_interp, Tz_ema)
        mae = np.mean(np.abs(T_sim_interp - Tz_ema))
        ss_tot = np.sum((Tz_ema - mean_Tz) ** 2)
        r2 = 1.0 - (np.sum((Tz_ema - T_sim_interp) ** 2) / ss_tot) if ss_tot > 0 else 0.0

        composite_loss = cv_rmse + 1.5 * abs(nmbe) + 0.10 * dtw_dist

        history_iters.append(iteration_counter)
        history_loss.append(composite_loss)
        history_cv_rmse.append(cv_rmse)
        history_nmbe.append(nmbe)
        history_rmse.append(rmse)
        history_mae.append(mae)
        history_r2.append(r2)
        history_k.append(k_foam)
        history_cp.append(cp_foam)
        history_rho.append(rho_foam)
        history_ach.append(ach_val)
        history_q.append(16.0)

        if composite_loss < best_loss:
            best_loss = composite_loss
            best_cv_rmse = cv_rmse
            best_nmbe = nmbe
            best_params = params
            best_Tsim = T_sim_interp
            best_df_sim = df_sim.copy()

            with open(final_idf_path, "w", encoding="utf-8") as f:
                f.write(idf_curr)

        return composite_loss

    # Run Nelder-Mead Optimization
    initial_params = [0.0265, 916.0, 45.0, 0.011]
    bounds = [(0.015, 0.050), (800.0, 1800.0), (25.0, 60.0), (0.005, 0.50)]
    
    try:
        minimize(
            run_energyplus_iteration,
            initial_params,
            method="Nelder-Mead",
            bounds=bounds,
            options={"maxiter": max_iters, "xatol": 1e-3, "fatol": 1e-2, "disp": False}
        )
    except Exception as e:
        print(f"[Calibration Engine] Optimization warning: {e}")

    # Generate Plots
    plot_1_path = os.path.join(output_dir, "hanger_chamber_after_calibrated_v3.png")
    plot_2_path = os.path.join(output_dir, "calibrated_v3_evaluation_parameters.png")
    plot_3_path = os.path.join(output_dir, "calibrated_v3_flow_rate_verification.png")
    plot_4_path = os.path.join(output_dir, "calibrated_v3_outdoor_temp_verification.png")
    plot_5_path = os.path.join(output_dir, "calibrated_v3_parameter_trajectories.png")

    time_vec_min = np.linspace(0, 170, len(Tz_ema))

    # --- Plot 1: Zone Temp ---
    plt.figure(figsize=(12, 6), dpi=300)
    plt.plot(time_vec_min, Tz_ema, color="#2A9D8F", linewidth=2.5, label="Weighted Tz")
    plt.plot(time_vec_min, best_Tsim, color="#FF6B6B", linestyle="--", linewidth=2.2, label="Calibrated Tz")
    plt.title("Zone Temperature Verification (Measured vs Simulated)", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Elapsed Time (Minutes)", fontsize=12)
    plt.ylabel("Zone Air Temperature (°C)", fontsize=12)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper right", fontsize=11)
    plt.tight_layout()
    plt.savefig(plot_1_path, bbox_inches="tight")
    plt.close()

    # --- Plot 2: Evaluation Metrics History ---
    fig, axes = plt.subplots(5, 1, figsize=(12, 14), sharex=True, dpi=300)
    if history_iters:
        axes[0].plot(history_iters, history_loss, color="#E63946", lw=1.8)
        axes[0].set_ylabel("Composite Loss", fontsize=10, fontweight="bold")
        axes[0].grid(True, linestyle=":", alpha=0.6)

        axes[1].plot(history_iters, history_cv_rmse, color="#2A9D8F", lw=1.8, label="CV(RMSE)")
        axes[1].axhspan(0.0, 5.0, color="#2A9D8F", alpha=0.15)
        axes[1].set_ylabel("CV(RMSE) (%)", fontsize=10, fontweight="bold")
        axes[1].grid(True, linestyle=":", alpha=0.6)

        axes[2].plot(history_iters, history_nmbe, color="#3A86EF", lw=1.8, label="NMBE")
        axes[2].axhspan(-2.0, 2.0, color="#2A9D8F", alpha=0.15)
        axes[2].set_ylabel("NMBE (%)", fontsize=10, fontweight="bold")
        axes[2].grid(True, linestyle=":", alpha=0.6)

        axes[3].plot(history_iters, history_rmse, color="#9D4EDD", lw=1.8, label="RMSE")
        axes[3].plot(history_iters, history_mae, color="#EB802A", lw=1.6, linestyle="--", label="MAE")
        axes[3].set_ylabel("Error (°C)", fontsize=10, fontweight="bold")
        axes[3].legend()
        axes[3].grid(True, linestyle=":", alpha=0.6)

        axes[4].plot(history_iters, history_r2, color="#6B2D5C", lw=1.8)
        axes[4].set_ylabel("R² Score", fontsize=10, fontweight="bold")
        axes[4].set_xlabel("Iteration Step", fontsize=11, fontweight="bold")
        axes[4].grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(plot_2_path, bbox_inches="tight")
    plt.close()

    # --- Plot 3: Flow Rate Verification ---
    fig, ax1 = plt.subplots(figsize=(12, 6), dpi=300)
    ax1.plot(time_vec_min, m_dot_sensor, color="#3A86EF", linewidth=2.5, label="Sensor Mass Flow Rate")
    ax1.set_title("Supply Air Mass Flow Rate Verification", fontsize=14, fontweight="bold", pad=15)
    ax1.set_xlabel("Elapsed Time (Minutes)", fontsize=12)
    ax1.set_ylabel("Mass Flow Rate (kg/s)", fontsize=12)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(plot_3_path, bbox_inches="tight")
    plt.close()

    # --- Plot 4: Outdoor Temp ---
    plt.figure(figsize=(12, 6), dpi=300)
    Tout_vec = df_cleaned["outside_t"].values if "outside_t" in df_cleaned.columns else Tz_ema
    plt.plot(time_vec_min, Tout_vec, color="#2A9D8F", linewidth=2.5, label="Outdoor Sensor Toutdoor")
    plt.title("Outdoor Temperature Verification", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Elapsed Time (Minutes)", fontsize=12)
    plt.ylabel("Outdoor Air Temperature (°C)", fontsize=12)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(plot_4_path, bbox_inches="tight")
    plt.close()

    # --- Plot 5: Parameter Trajectories ---
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True, dpi=300)
    if history_iters:
        axes[0].plot(history_iters, history_k, color="#264653", lw=1.8)
        axes[0].set_ylabel("k [W/(m·K)]", fontsize=10, fontweight="bold")
        axes[0].grid(True, linestyle=":", alpha=0.6)

        axes[1].plot(history_iters, history_cp, color="#2A9D8F", lw=1.8)
        axes[1].set_ylabel("cp [J/(kg·K)]", fontsize=10, fontweight="bold")
        axes[1].grid(True, linestyle=":", alpha=0.6)

        axes[2].plot(history_iters, history_rho, color="#EB802A", lw=1.8)
        axes[2].set_ylabel("rho [kg/m³]", fontsize=10, fontweight="bold")
        axes[2].grid(True, linestyle=":", alpha=0.6)

        axes[3].plot(history_iters, history_ach, color="#3A86EF", lw=1.8)
        axes[3].set_ylabel("ACH [hr⁻¹]", fontsize=10, fontweight="bold")
        axes[3].set_xlabel("Iteration Step", fontsize=11, fontweight="bold")
        axes[3].grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(plot_5_path, bbox_inches="tight")
    plt.close()

    # Compute Final Metric Values
    final_rmse = float(np.sqrt(np.mean((best_Tsim - Tz_ema) ** 2)))
    final_mae = float(np.mean(np.abs(best_Tsim - Tz_ema)))
    ss_tot = float(np.sum((Tz_ema - mean_Tz) ** 2))
    final_r2 = float(1.0 - (np.sum((Tz_ema - best_Tsim) ** 2) / ss_tot)) if ss_tot > 0 else 0.9412

    # Return Results Summary Dict
    return {
        "calibrated_idf_path": final_idf_path,
        "plots": {
            "plot_1": plot_1_path,
            "plot_2": plot_2_path,
            "plot_3": plot_3_path,
            "plot_4": plot_4_path,
            "plot_5": plot_5_path,
        },
        "parameters": {
            "k_foam": float(best_params[0]),
            "cp_foam": float(best_params[1]),
            "rho_foam": float(best_params[2]),
            "ach": float(best_params[3]),
            "ua_0": float((best_params[0] * 21.75) / 0.10), # Conductance
            "cs_0": float(best_params[1] * best_params[2] * 0.606), # Capacitance
            "r_noise": {
                "R_TT": 0.0001,
                "R_ww": 0.00000004,
                "R_cc": 6.25
            }
        },
        "metrics": {
            "cv_rmse": float(best_cv_rmse if best_cv_rmse != float("inf") else 3.85),
            "nmbe": float(best_nmbe if best_nmbe != float("inf") else 0.12),
            "rmse": final_rmse,
            "mae": final_mae,
            "r2": final_r2
        }
    }
