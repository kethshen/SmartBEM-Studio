"""
SmartBEM FYP — 10-State Single EKF for ROBOD Dataset (Rooms 1 - 5)
===================================================================
Direct adaptation of test_rig_single_ekf.py tailored for the 5 ROBOD Room Datasets:
  - Uses live sensor barometric pressure (P_live in Pa)
  - Fully lumped CO2 dynamics (gamma_e enters ODE directly)
  - Occupancy recovery: N_occ = gamma_e / (4.5 / V_room)
  - Generates exactly 4 PNG plots per room dataset in plots/[room_name]/:
      1. single_ekf_states.png
      2. single_ekf_occupancy_estimation.png
      3. single_ekf_estimated_parameters.png
      4. single_ekf_derived_physical_properties.png
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys

# Apply Seaborn whitegrid style
sns.set_theme(style="whitegrid")

# Custom Color Palette
COLOR_BLUE    = "#3A86EF"  # Light Vibrant Blue
COLOR_CYAN    = "#2A9D8F"  # Emerald Cyan
COLOR_ORANGE  = "#EB802A"  # Rich Vibrant Orange
COLOR_RED     = "#FF6B6B"  # Light Coral Red
COLOR_PURPLE  = "#9D4EDD"  # Crisp Light Purple
COLOR_TEAL    = "#264653"  # Teal Slate
COLOR_CRIMSON = "#E63946"  # Crimson Red
COLOR_MAGENTA = "#6B2D5C"  # Dark Magenta

# ── Paths & Setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR   = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
ROBOD_DIR    = os.path.join(STUDIO_DIR, "EKF", "Datasets for EKF",
                             "ROBOD, Room level Occupancy and Building Operation Dataset")
PLOTS_DIR    = os.path.join(SCRIPT_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

# ── Physical Constants ─────────────────────────────────────────────────────────
c_pa          = 1006.0     # Specific heat of dry air [J/(kg·K)]
rho_air       = 1.20       # Standard dry air density [kg/m³]
DT            = 300.0      # 5-minute sampling interval [seconds]

# ── Room Specifications (official NUS ROBOD room_descriptions) ─────────────────
ROOM_SPECS = {
    1: {"name": "combined_Room1", "file": "combined_Room1.csv", "volume": 120.0, "max_occ": 6.0,  "Cs": 500000.0,  "UA": 80.0},
    2: {"name": "combined_Room2", "file": "combined_Room2.csv", "volume": 150.0, "max_occ": 8.0,  "Cs": 650000.0,  "UA": 100.0},
    3: {"name": "combined_Room3", "file": "combined_Room3.csv", "volume": 413.2, "max_occ": 13.0, "Cs": 1500000.0, "UA": 250.0},
    4: {"name": "combined_Room4", "file": "combined_Room4.csv", "volume": 756.0, "max_occ": 25.0, "Cs": 2800000.0, "UA": 450.0},
    5: {"name": "combined_Room5", "file": "combined_Room5.csv", "volume": 760.0, "max_occ": 25.0, "Cs": 2850000.0, "UA": 450.0},
}

# ── State Indices (10-State Vector) ────────────────────────────────────────────
I_ao, I_as, I_ae = 0, 1, 2
I_bo, I_bs, I_be = 3, 4, 5
I_ge             = 6
I_Tz, I_wz, I_cz = 7, 8, 9
N_STATES = 10

def rh_to_humidity_ratio(rh_pct, T_C, P_pa):
    """Converts RH [%] and T [°C] to Humidity Ratio [kg_w/kg_a] using live pressure P_pa."""
    rh = np.clip(rh_pct / 100.0, 0.0, 1.0)
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    omega = 0.622 * (rh * P_sat) / (P_pa - rh * P_sat)
    return np.clip(omega, 0.0, 0.05)

def humidity_ratio_to_rh(omega, T_C, P_pa):
    """Converts Humidity Ratio [kg_w/kg_a] and T [°C] to RH [%] using live pressure P_pa."""
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    P_w = (omega * P_pa) / (0.622 + omega)
    rh = (P_w / P_sat) * 100.0
    return np.clip(rh, 0.0, 100.0)

# ── EKF State Dynamics f(X, U) — Fully Lumped Formulation ─────────────────────
def f_dynamics(X, U):
    ao, as_, ae = X[I_ao], X[I_as], X[I_ae]
    bo, bs, be   = X[I_bo], X[I_bs], X[I_be]
    ge           = X[I_ge]
    Tz, wz, cz   = X[I_Tz], X[I_wz], X[I_cz]

    To, wo, co, Tsa, wsa, csa, msa = U

    dTz = ao * (To - Tz) + as_ * msa * (Tsa - Tz) + ae
    dwz = bo * (wo - wz) + bs  * msa * (wsa - wz)  + be
    dcz = bo * (co - cz) + bs  * msa * (csa - cz)  + ge

    dX = np.zeros(N_STATES)
    dX[I_Tz] = dTz
    dX[I_wz] = dwz
    dX[I_cz] = dcz
    return dX

def get_jacobian_F(X, U):
    ao, as_, ae = X[I_ao], X[I_as], X[I_ae]
    bo, bs, be   = X[I_bo], X[I_bs], X[I_be]
    Tz, wz, cz   = X[I_Tz], X[I_wz], X[I_cz]
    To, wo, co, Tsa, wsa, csa, msa = U

    J = np.zeros((N_STATES, N_STATES))

    # Thermal derivatives
    J[I_Tz, I_ao] = To - Tz
    J[I_Tz, I_as] = msa * (Tsa - Tz)
    J[I_Tz, I_ae] = 1.0
    J[I_Tz, I_Tz] = -(ao + as_ * msa)

    # Moisture derivatives
    J[I_wz, I_bo] = wo - wz
    J[I_wz, I_bs] = msa * (wsa - wz)
    J[I_wz, I_be] = 1.0
    J[I_wz, I_wz] = -(bo + bs * msa)

    # CO2 derivatives
    J[I_cz, I_bo] = co - cz
    J[I_cz, I_bs] = msa * (csa - cz)
    J[I_cz, I_ge] = 1.0
    J[I_cz, I_cz] = -(bo + bs * msa)

    return J

def run_single_ekf_robod(df, room_spec):
    # Clean raw sensor telemetry (forward fill then backward fill any missing NaN readings)
    df = df.copy()
    for col in df.columns:
        if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
            df[col] = df[col].ffill().bfill()

    N = len(df)
    v_room = room_spec["volume"]
    M_room = v_room * rho_air
    Cs_nom = room_spec["Cs"]
    UA_nom = room_spec["UA"]
    g_CO2_per_person = 4.5 / v_room  # [ppm/s per person]

    # Barometric pressure (convert hPa -> Pa)
    if "baromatic_pressure [hPa]" in df.columns:
        P_live_arr = df["baromatic_pressure [hPa]"].fillna(1013.25).values * 100.0
    else:
        P_live_arr = np.full(N, 101325.0)

    To = df["dry_bulb_temp [Celsius]"].fillna(28.0).values
    RHo = df["outdoor_relative_humidity [%]"].fillna(75.0).values
    wo = np.array([rh_to_humidity_ratio(RHo[i], To[i], P_live_arr[i]) for i in range(N)])
    co = df["outdoor_co2 [ppm]"].fillna(400.0).values

    Tsa = df["supply_air_temperature [Celsius]"].fillna(18.0).values
    if "supply_air_humidity [%]" in df.columns:
        RHsa = df["supply_air_humidity [%]"].fillna(85.0).values
    else:
        RHsa = RHo.copy()
    wsa = np.array([rh_to_humidity_ratio(RHsa[i], Tsa[i], P_live_arr[i]) for i in range(N)])

    # Supply airflow m_sa [kg/s]
    if "supply_air_flow [CMH]" in df.columns:
        msa = df["supply_air_flow [CMH]"].fillna(0.0).values * (rho_air / 3600.0)
    elif "fcu_fan_speed [Hz]" in df.columns:
        msa = (df["fcu_fan_speed [Hz]"].fillna(0.0).values / 50.0) * 0.15
    else:
        msa = np.full(N, 0.05)

    Tz_meas = df["air_temperature [Celsius]"].values
    RHz_meas = df["indoor_relative_humidity [%]"].values
    cz_meas = df["indoor_co2 [ppm]"].values
    wz_meas = np.array([rh_to_humidity_ratio(RHz_meas[i], Tz_meas[i], P_live_arr[i]) for i in range(N)])

    # Recirculated AHU supply CO2 model (50% outdoor / 50% indoor)
    csa = 0.5 * cz_meas + 0.5 * co

    X = np.zeros(N_STATES)
    # Physically Informed Initialization
    X[I_ao] = (UA_nom + c_pa * (3e-6 * M_room)) / Cs_nom
    X[I_as] = c_pa / Cs_nom
    X[I_ae] = 0.0000
    X[I_bo] = 3.06e-6
    X[I_bs] = 1.0 / M_room
    X[I_be] = 0.0000
    X[I_ge] = 0.05
    X[I_Tz] = Tz_meas[0]
    X[I_wz] = wz_meas[0]
    X[I_cz] = cz_meas[0]

    P = np.eye(N_STATES) * 0.1
    P[I_ge, I_ge] = 1.0

    Q_base = np.diag([1e-8, 1e-8, 1e-7, 1e-7, 1e-7, 1e-7, 1e-3, 1e-2, 1e-6, 1.0])
    R = np.diag([0.01**2, 0.0002**2, 2.5**2])

    H = np.zeros((3, N_STATES))
    H[0, I_Tz] = 1.0
    H[1, I_wz] = 1.0
    H[2, I_cz] = 1.0

    X_hist = np.zeros((N, N_STATES))

    for k in range(N):
        U_k = (To[k], wo[k], co[k], Tsa[k], wsa[k], csa[k], msa[k])

        # Flow-driven process noise scaling
        Q_k = Q_base.copy()
        excitation_factor = np.tanh(msa[k] / 0.010)
        Q_k[I_as, I_as] += 1e-6 * excitation_factor
        Q_k[I_bs, I_bs] += 1e-6 * excitation_factor

        # Prediction Step (Euler Integration)
        dX = f_dynamics(X, U_k)
        X_pred = X + dX * DT

        # Sigmoidal parameter bounding
        X_pred[I_ao] = np.clip(X_pred[I_ao], 1e-6, 0.01)
        X_pred[I_as] = np.clip(X_pred[I_as], 1e-6, 0.5)
        X_pred[I_bo] = np.clip(X_pred[I_bo], 1e-8, 1e-3)
        X_pred[I_bs] = np.clip(X_pred[I_bs], 1e-5, 1.0)
        X_pred[I_ge] = np.clip(X_pred[I_ge], 0.0, 5.0)
        X_pred[I_cz] = np.clip(X_pred[I_cz], 300.0, 3000.0)

        F_k = np.eye(N_STATES) + get_jacobian_F(X, U_k) * DT
        P_pred = F_k @ P @ F_k.T + Q_k * DT

        # Update Step (with NaN measurement guard)
        Z_k = np.array([Tz_meas[k], wz_meas[k], cz_meas[k]])
        if np.any(np.isnan(Z_k)):
            X = X_pred
            P = P_pred
        else:
            y_k = Z_k - H @ X_pred
            S_k = H @ P_pred @ H.T + R
            try:
                K_k = P_pred @ H.T @ np.linalg.inv(S_k)
                X = X_pred + K_k @ y_k
                P = (np.eye(N_STATES) - K_k @ H) @ P_pred
            except np.linalg.LinAlgError:
                X = X_pred
                P = P_pred
        P = 0.5 * (P + P.T)

        X_hist[k, :] = X

    # Extract Derived Physical Properties
    Cs_arr = c_pa / np.where(np.abs(X_hist[:, I_as]) > 1e-12, X_hist[:, I_as], 1e-12)
    M_est_arr = 1.0 / np.where(np.abs(X_hist[:, I_bs]) > 1e-12, X_hist[:, I_bs], 1e-12)
    m_inf_arr = X_hist[:, I_bo] * M_est_arr * 1000.0  # [g/s]
    m_inf_kgs = X_hist[:, I_bo] * M_est_arr
    UA_arr    = X_hist[:, I_ao] * Cs_arr - c_pa * m_inf_kgs

    N_occ_est = X_hist[:, I_ge] / g_CO2_per_person
    RHz_est = np.array([humidity_ratio_to_rh(X_hist[i, I_wz], X_hist[i, I_Tz], P_live_arr[i]) for i in range(N)])

    return (X_hist, Cs_arr, M_est_arr, m_inf_arr, UA_arr, N_occ_est, RHz_est,
            Tz_meas, RHz_meas, cz_meas, P_live_arr)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN PLOTTING AND EXECUTION LOOP
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 65)
    print("  Single EKF v3 — ROBOD Dataset (Rooms 1 - 5)")
    print("  Running on 5 room datasets...")
    print("=" * 65 + "\n")

    for room_id, spec in ROOM_SPECS.items():
        base_name = spec["name"]
        csv_file  = spec["file"]
        csv_path  = os.path.join(ROBOD_DIR, csv_file)

        if not os.path.exists(csv_path):
            print(f"[WARNING] Skipping missing file: {csv_path}")
            continue

        print(f"Running Single EKF for ROBOD {base_name}...")
        dataset_plot_dir = os.path.join(PLOTS_DIR, base_name)
        os.makedirs(dataset_plot_dir, exist_ok=True)
        print(f"• Output folder: {dataset_plot_dir}")

        df = pd.read_csv(csv_path)

        (X_hist, Cs_arr, M_est_arr, m_inf_arr, UA_arr, N_occ_est, RHz_est,
         Tz_meas, RHz_meas, cz_meas, P_live) = run_single_ekf_robod(df, spec)

        N = len(df)
        t_min = np.arange(N) * DT / 60.0

        # Ground Truth Occupancy from ROBOD CSV
        N_occ_gt = df["occupant_count [number]"].fillna(0.0).values

        # ── PLOT 1: 3-SUBPLOT ENVIRONMENTAL STATES ─────────────────────────────
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

        ax1.plot(t_min, Tz_meas, color=COLOR_CYAN, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured Tz (°C)")
        ax1.plot(t_min, X_hist[:, I_Tz], color=COLOR_RED, linestyle="-", linewidth=2.2, label="EKF Estimated Tz (°C)")
        ax1.set_ylabel("Temperature (°C)", fontsize=10)
        ax1.set_title(f"ROBOD {base_name} — Single 10-State EKF Environmental State Estimation", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        ax2.plot(t_min, RHz_meas, color=COLOR_ORANGE, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured RH (%)")
        ax2.plot(t_min, RHz_est, color=COLOR_BLUE, linestyle="-", linewidth=2.2, label="EKF Estimated RH (%)")
        ax2.set_ylabel("Relative Humidity (%)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        ax3.plot(t_min, cz_meas, color=COLOR_CRIMSON, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured CO2 (ppm)")
        ax3.plot(t_min, X_hist[:, I_cz], color=COLOR_TEAL, linestyle="-", linewidth=2.2, label="EKF Estimated CO2 (ppm)")
        ax3.set_ylabel("CO2 Concentration (ppm)", fontsize=10)
        ax3.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax3.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax3.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot1_path = os.path.join(dataset_plot_dir, "single_ekf_states.png")
        plt.savefig(plot1_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 1: {plot1_path}")

        # ── PLOT 2: OCCUPANCY ESTIMATION VS GROUND TRUTH ─────────────────────
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(t_min, N_occ_est, color=COLOR_PURPLE, linestyle="-", linewidth=2.0, label="Continuous EKF Estimated Occupants (N_occ)")
        ax.step(t_min, N_occ_gt, color=COLOR_TEAL, where="post", linewidth=2.0, linestyle="--", alpha=0.8, label="Ground Truth Occupancy")

        ax.set_ylabel("Occupants (persons)", fontsize=10)
        ax.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax.set_title(f"ROBOD {base_name} — Single-EKF Occupancy Estimation vs Ground Truth", fontsize=12, fontweight="bold", pad=12)
        ax.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot2_path = os.path.join(dataset_plot_dir, "single_ekf_occupancy_estimation.png")
        plt.savefig(plot2_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 2: {plot2_path}")

        # ── PLOT 3: 7 ESTIMATED PARAMETERS SUBPLOTS (alpha_o to gamma_e) ────────
        fig, axes = plt.subplots(7, 1, figsize=(11, 14), sharex=True)

        param_configs = [
            (I_ao, r"$\alpha_o$ [1/s]", COLOR_PURPLE, "Envelope Heat Loss Coeff"),
            (I_as, r"$\alpha_s$ [1/(kg·s)]", COLOR_BLUE, "Supply Air Thermal Impact"),
            (I_ae, r"$\alpha_e$ [°C/s]", COLOR_TEAL, "Internal Heat Generation Bias"),
            (I_bo, r"$\beta_o$ [1/s]", COLOR_CYAN, "Infiltration / Ingress Coeff"),
            (I_bs, r"$\beta_s$ [1/(kg·s)]", COLOR_ORANGE, "Supply Air Mixing Coeff"),
            (I_be, r"$\beta_e$ [kg_w/(kg_a·s)]", COLOR_MAGENTA, "Internal Moisture Load Bias"),
            (I_ge, r"$\gamma_e$ [ppm/s]", COLOR_CRIMSON, "CO2 Generation Rate")
        ]

        axes[0].set_title(f"ROBOD {base_name} — Single-EKF Estimated Parameters", fontsize=12, fontweight="bold", pad=12)

        for idx, (p_idx, label_str, color_str, title_str) in enumerate(param_configs):
            ax = axes[idx]
            ax.plot(t_min, X_hist[:, p_idx], color=color_str, linewidth=1.8, label=title_str)
            ax.set_ylabel(label_str, fontsize=9)
            ax.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
            ax.grid(True, linestyle=":", alpha=0.6)

        axes[-1].set_xlabel("Elapsed Time (minutes)", fontsize=11)
        plt.tight_layout()
        plot3_path = os.path.join(dataset_plot_dir, "single_ekf_estimated_parameters.png")
        plt.savefig(plot3_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 3: {plot3_path}")

        # ── PLOT 4: DERIVED PHYSICAL PARAMETERS (Cs, M, m_inf, UA) ───────────
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

        ax1.plot(t_min, Cs_arr / 1000.0, color=COLOR_BLUE, linewidth=2.0, label="Estimated Thermal Capacitance Cs (kJ/°C)")
        ax1.axhline(spec["Cs"] / 1000.0, color=COLOR_TEAL, linestyle="--", label=f"Nominal Cs = {spec['Cs']/1000.0:.1f} kJ/°C")
        ax1.set_ylabel("Cs (kJ/°C)", fontsize=10)
        ax1.set_title(f"ROBOD {base_name} — Single-EKF Derived Physical Building Parameters (Cs, M, m_inf, UA)", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        ax2.plot(t_min, M_est_arr, color=COLOR_TEAL, linewidth=2.0, label="Estimated Zone Air Mass M (kg)")
        ax2.axhline(spec["volume"] * rho_air, color=COLOR_CYAN, linestyle="--", label=f"Nominal M = {spec['volume']*rho_air:.1f} kg")
        ax2.set_ylabel("Air Mass M (kg)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        ax3.plot(t_min, m_inf_arr, color=COLOR_PURPLE, linewidth=2.0, label="Estimated Infiltration Rate m_inf (g/s)")
        ax3.set_ylabel("m_inf (g/s)", fontsize=10)
        ax3.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax3.grid(True, linestyle=":", alpha=0.6)

        ax4.plot(t_min, UA_arr, color=COLOR_CRIMSON, linewidth=2.0, label="Estimated Envelope Conductance UA (W/°C)")
        ax4.axhline(spec["UA"], color=COLOR_TEAL, linestyle="--", label=f"Nominal UA = {spec['UA']:.1f} W/°C")
        ax4.set_ylabel("UA (W/°C)", fontsize=10)
        ax4.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax4.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax4.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot4_path = os.path.join(dataset_plot_dir, "single_ekf_derived_physical_properties.png")
        plt.savefig(plot4_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 4: {plot4_path}")

        print(f"[SUCCESS] Saved 4 Single-EKF plots for: {base_name}\n")

    print("\nALL SINGLE EKF RUNS FOR ROBOD COMPLETED SUCCESSFULLY.")
