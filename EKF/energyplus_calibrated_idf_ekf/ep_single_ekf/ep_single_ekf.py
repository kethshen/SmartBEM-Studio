"""
SmartBEM FYP — 10-State Single EKF for EnergyPlus / Test Rig 1-Min Benchmark Datasets
========================================================================================
Ported directly from test_rig_single_ekf.py (without extra experimental modifications):
  - Uses live sensor barometric pressure (P_live in Pa)
  - Fully lumped CO2 dynamics (gamma_e enters ODE directly, no division)
  - Occupancy recovery: N = gamma_e / g_CO2_occ_per_person
  - 1-minute resampled dataset resolution for EnergyPlus alignment

Generates exactly 4 PNG plots per dataset:
  1. single_ekf_states.png (Tz, Relative Humidity %, CO2z)
  2. single_ekf_occupancy_estimation.png (Continuous EKF Occupants vs Ground Truth)
  3. single_ekf_estimated_parameters.png (7 Estimated Parameter Subplots)
  4. single_ekf_derived_physical_properties.png (Cs, M, m_inf, UA)
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

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EP_DIR = os.path.dirname(SCRIPT_DIR)
STUDIO_DIR = os.path.abspath(os.path.join(EP_DIR, "..", ".."))

DAY3_DIR = os.path.join(STUDIO_DIR, "Experimental_Rig_Calibration", "sensor_readings", "with_occ", "Day_3")
DAY4_DIR = os.path.join(STUDIO_DIR, "Experimental_Rig_Calibration", "sensor_readings", "with_occ", "Day_4")

DAY_WITH_OCC_CLEAN_DIR = os.path.join(STUDIO_DIR, "Experimental_Rig_Calibration", "sensor_readings", "cleaned", "with_occ")

PLOTS_ROOT_DIR = os.path.join(SCRIPT_DIR, "plots")
os.makedirs(PLOTS_ROOT_DIR, exist_ok=True)

# ── Physical & Chamber Constants ───────────────────────────────────────────────
V_CHAMBER  = 5.832         # Net internal air volume [m³] (1.8m x 1.8m x 1.8m)
RHO_AIR    = 1.20          # Air density [kg/m³]
M_ROOM     = V_CHAMBER * RHO_AIR  # ~7.00 kg net air mass
c_pa       = 1006.0        # Specific heat of dry air [J/(kg·K)]
DT         = 60.0          # 1-minute sampling interval [seconds] for EnergyPlus alignment

# CO2 generation rate per person — calibrated for chamber volume
g_CO2_occ_per_person = 4.5e-6 * 1e6 / V_CHAMBER  # = 0.7716 ppm/s per person

# Nominal Chamber Envelope Properties
Cs_nom = 25000.0           # Thermal capacitance [J/K] (25.0 kJ/K)
UA_nom = 5.76              # Nominal envelope conductance [W/K]

# ── State Indices ──────────────────────────────────────────────────────────────
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

# ── Ground Truth Schedule Parsers ──────────────────────────────────────────────
def get_day4_occupancy_series(df_data, dataset_filename, df_sched4):
    sched = df_sched4[df_sched4["Dataset name"].str.strip() == dataset_filename].copy()
    ts_local = pd.to_datetime(df_data["timestamp"], utc=True).dt.tz_convert("Asia/Colombo")
    occ_vec = np.zeros(len(df_data), dtype=float)
    
    for idx, row in sched.iterrows():
        t1_str = str(row["time 1"]).strip()
        t2_str = str(row["time 2"]).strip()
        cnt    = float(row["total occupancy inside chamber"])
        
        if t1_str and t2_str and t1_str != "nan" and t2_str != "nan":
            h1, m1 = map(int, t1_str.split(":"))
            h2, m2 = map(int, t2_str.split(":"))
            
            for i, t in enumerate(ts_local):
                t_m = t.hour * 60 + t.minute
                m_start = h1 * 60 + m1
                m_end   = h2 * 60 + m2
                if m_start <= t_m <= m_end:
                    occ_vec[i] = cnt
    return occ_vec

def get_day3_occupancy_series(df_data):
    if "timestamp" in df_data.columns:
        ts = pd.to_datetime(df_data["timestamp"])
        elapsed_min = (ts - ts.iloc[0]).dt.total_seconds() / 60.0
    else:
        elapsed_min = np.arange(len(df_data)) * 1.0
        
    occ_vec = np.zeros(len(df_data), dtype=float)
    for i, m in enumerate(elapsed_min):
        if 5.0 <= m <= 20.0:
            occ_vec[i] = 1.0
    return occ_vec

# ── EKF State Dynamics f(X, U) ─────────────────────────────────────────────────
def f_dynamics(X, U):
    ao, as_, ae = X[I_ao], X[I_as], X[I_ae]
    bo, bs, be   = X[I_bo], X[I_bs], X[I_be]
    ge           = X[I_ge]
    Tz, wz, cz   = X[I_Tz], X[I_wz], X[I_cz]
    
    To, wo, co, Tsa, wsa, csa, msa = U
    
    dTz  = ao * (To - Tz) + as_ * msa * (Tsa - Tz) + ae
    dwz  = bo * (wo - wz) + bs  * msa * (wsa - wz)  + be
    dcz  = bo * (co - cz) + bs  * msa * (csa - cz)  + ge
    
    dX = np.zeros(N_STATES)
    dX[I_Tz] = dTz
    dX[I_wz] = dwz
    dX[I_cz] = dcz
    return dX

def get_jacobian_F(X, U):
    ao, as_, ae = X[I_ao], X[I_as], X[I_ae]
    bo, bs, be   = X[I_bo], X[I_bs], X[I_be]
    ge           = X[I_ge]
    Tz, wz, cz   = X[I_Tz], X[I_wz], X[I_cz]
    To, wo, co, Tsa, wsa, csa, msa = U
    
    J = np.zeros((N_STATES, N_STATES))
    J[I_Tz, I_ao] = To - Tz
    J[I_Tz, I_as] = msa * (Tsa - Tz)
    J[I_Tz, I_ae] = 1.0
    J[I_Tz, I_Tz] = -(ao + as_ * msa)
    
    J[I_wz, I_bo] = wo - wz
    J[I_wz, I_bs] = msa * (wsa - wz)
    J[I_wz, I_be] = 1.0
    J[I_wz, I_wz] = -(bo + bs * msa)
    
    J[I_cz, I_bo] = co - cz
    J[I_cz, I_bs] = msa * (csa - cz)
    J[I_cz, I_ge] = 1.0
    J[I_cz, I_cz] = -(bo + bs * msa)
    return J

def run_single_ekf_ep(df):
    df_clean = df.copy()
    for col in df_clean.columns:
        if df_clean[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
            df_clean[col] = df_clean[col].ffill().bfill()

    N = len(df_clean)

    if "outside_p" in df_clean.columns and df_clean["outside_p"].dropna().mean() > 500:
        P_live_arr = df_clean["outside_p"].fillna(1013.25).values * 100.0
    elif "room_1_p" in df_clean.columns and df_clean["room_1_p"].dropna().mean() > 500:
        P_live_arr = df_clean["room_1_p"].fillna(1013.25).values * 100.0
    else:
        P_live_arr = np.full(N, 101325.0)

    To  = df_clean["outside_t"].values
    wo  = np.array([rh_to_humidity_ratio(df_clean["outside_h"].values[i], To[i], P_live_arr[i]) for i in range(N)])
    co  = df_clean["outside_c"].values

    Tsa = df_clean["supply_t"].values
    wsa = np.array([rh_to_humidity_ratio(df_clean["supply_h"].values[i], Tsa[i], P_live_arr[i]) for i in range(N)])
    csa = df_clean["supply_c"].values
    msa = df_clean["m_sa_kgs"].values

    Tz_meas  = df_clean["Tz_weighted"].values if "Tz_weighted" in df_clean.columns else df_clean["T_z_weighted"].values
    RHz_meas = df_clean["RHz_weighted"].values if "RHz_weighted" in df_clean.columns else df_clean["RH_z_weighted"].values
    wz_meas  = np.array([rh_to_humidity_ratio(RHz_meas[i], Tz_meas[i], P_live_arr[i]) for i in range(N)])
    cz_meas  = df_clean["CO2z_weighted"].values if "CO2z_weighted" in df_clean.columns else df_clean["CO2_z_weighted"].values

    X = np.zeros(N_STATES)
    X[I_ao] = (UA_nom + c_pa * (3e-6 * M_ROOM)) / Cs_nom
    X[I_as] = c_pa / Cs_nom
    X[I_ae] = 0.0000
    X[I_bo] = 3.06e-6
    X[I_bs] = 1.0 / M_ROOM
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

        Q_k = Q_base.copy()
        excitation_factor = np.tanh(msa[k] / 0.010)
        Q_k[I_as, I_as] += 1e-6 * excitation_factor
        Q_k[I_bs, I_bs] += 1e-6 * excitation_factor

        dX = f_dynamics(X, U_k)
        X_pred = X + dX * DT

        X_pred[I_ao] = np.clip(X_pred[I_ao], 1e-6, 0.01)
        X_pred[I_as] = np.clip(X_pred[I_as], 1e-6, 0.5)
        X_pred[I_bo] = np.clip(X_pred[I_bo], 1e-8, 1e-3)
        X_pred[I_bs] = np.clip(X_pred[I_bs], 1e-5, 1.0)
        X_pred[I_ge] = np.clip(X_pred[I_ge], 0.0, 5.0)
        X_pred[I_cz] = np.clip(X_pred[I_cz], 300.0, 3000.0)

        F_k = np.eye(N_STATES) + get_jacobian_F(X, U_k) * DT
        P_pred = F_k @ P @ F_k.T + Q_k * DT

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

    Cs_arr = c_pa / np.where(np.abs(X_hist[:, I_as]) > 1e-12, X_hist[:, I_as], 1e-12)
    M_est_arr = 1.0 / np.where(np.abs(X_hist[:, I_bs]) > 1e-12, X_hist[:, I_bs], 1e-12)
    m_inf_arr = X_hist[:, I_bo] * M_est_arr * 1000.0
    m_inf_kgs = X_hist[:, I_bo] * M_est_arr
    UA_arr    = X_hist[:, I_ao] * Cs_arr - c_pa * m_inf_kgs

    N_occ_est = X_hist[:, I_ge] / g_CO2_occ_per_person
    RHz_est = np.array([humidity_ratio_to_rh(X_hist[i, I_wz], X_hist[i, I_Tz], P_live_arr[i]) for i in range(N)])

    return (X_hist, Cs_arr, M_est_arr, m_inf_arr, UA_arr, N_occ_est, RHz_est,
            Tz_meas, RHz_meas, cz_meas, P_live_arr)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN PLOTTING AND EXECUTION LOOP
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    day4_sched_p = os.path.join(DAY_WITH_OCC_CLEAN_DIR, "occ_schedule_day_4.csv")
    if os.path.exists(day4_sched_p):
        df_sched4 = pd.read_csv(day4_sched_p)
        df_sched4.columns = [c.strip() for c in df_sched4.columns]
    else:
        df_sched4 = pd.DataFrame()

    all_csv_files = sorted([f for f in os.listdir(DAY_WITH_OCC_CLEAN_DIR) if f.startswith("day_") and f.endswith(".csv")])

    print(f"\n=================================================================")
    print(f"  10-State Single EKF — EnergyPlus / 1-Min Benchmark Datasets")
    print(f"  Running on {len(all_csv_files)} datasets...")
    print(f"=================================================================\n")

    for fname in all_csv_files:
        day = 4 if "day_4" in fname else 3
        df_raw = pd.read_csv(os.path.join(DAY_WITH_OCC_CLEAN_DIR, fname))
        base_name = fname.replace(".csv", "")
        raw_filename = f"{base_name}.csv"

        if "timestamp" in df_raw.columns:
            df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"])
            df = df_raw.resample("1min", on="timestamp").mean().reset_index()
        else:
            df = df_raw.iloc[::12].copy().reset_index(drop=True)

        dataset_plot_dir = os.path.join(PLOTS_ROOT_DIR, base_name)
        os.makedirs(dataset_plot_dir, exist_ok=True)

        print(f"Running 1-Min Single EKF for Day {day}: {base_name}...")
        print(f"• Output folder: {dataset_plot_dir}")

        (X_hist, Cs_arr, M_est_arr, m_inf_arr, UA_arr, N_occ_est, RHz_est,
         Tz_m, RHz_m, cz_m, P_live) = run_single_ekf_ep(df)

        ts = pd.to_datetime(df["timestamp"])
        t_min = (ts - ts.iloc[0]).dt.total_seconds() / 60.0

        if day == 4 and not df_sched4.empty:
            n_gt = get_day4_occupancy_series(df, raw_filename, df_sched4)
        else:
            n_gt = get_day3_occupancy_series(df)

        n_disc = np.where(N_occ_est >= 0.35, np.maximum(1.0, np.round(N_occ_est)), 0.0)

        # ── PLOT 1: 3-SUBPLOT ENVIRONMENTAL STATES ───────────────────────────
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

        ax1.plot(t_min, Tz_m, color=COLOR_CYAN, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured Tz (°C)")
        ax1.plot(t_min, X_hist[:, I_Tz], color=COLOR_RED, linestyle="-", linewidth=2.2, label="EKF Estimated Tz (°C)")
        ax1.set_ylabel("Temperature (°C)", fontsize=10)
        ax1.set_title(f"{base_name} — Single 10-State EKF Environmental State Estimation (1-Min)", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        ax2.plot(t_min, RHz_m, color=COLOR_ORANGE, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured RH (%)")
        ax2.plot(t_min, RHz_est, color=COLOR_BLUE, linestyle="-", linewidth=2.2, label="EKF Estimated RH (%)")
        ax2.set_ylabel("Relative Humidity (%)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        ax3.plot(t_min, cz_m, color=COLOR_CRIMSON, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured CO2 (ppm)")
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
        ax.plot(t_min, N_occ_est, color=COLOR_PURPLE, linestyle="-", linewidth=2.0, label="Continuous EKF Estimated Occupants (N)")
        ax.step(t_min, n_disc, color=COLOR_BLUE, where="post", linewidth=2.2, alpha=0.9, label="Thresholded Integer Occupants (≥0.35 Person Threshold)")
        ax.step(t_min, n_gt, color=COLOR_TEAL, where="post", linewidth=2.0, linestyle="--", alpha=0.8, label="Ground Truth Occupancy Schedule")

        ax.set_ylim(-0.5, 4.0)
        ax.set_ylabel("Occupant Count (persons)", fontsize=11)
        ax.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax.set_title(f"{base_name} — Single-EKF Occupancy Estimation vs Ground Truth", fontsize=12, fontweight="bold", pad=12)
        ax.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot2_path = os.path.join(dataset_plot_dir, "single_ekf_occupancy_estimation.png")
        plt.savefig(plot2_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 2: {plot2_path}")

        # ── PLOT 3: 7 ESTIMATED PARAMETERS SUBPLOTS ───────────────────────────
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

        axes[0].set_title(f"{base_name} — Single-EKF Estimated Parameters", fontsize=12, fontweight="bold", pad=12)

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
        ax1.axhline(Cs_nom / 1000.0, color=COLOR_TEAL, linestyle="--", label=f"Nominal Cs = {Cs_nom/1000.0:.1f} kJ/°C")
        ax1.set_ylabel("Cs (kJ/°C)", fontsize=10)
        ax1.set_title(f"{base_name} — Single-EKF Derived Physical Building Parameters (Cs, M, m_inf, UA)", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        ax2.plot(t_min, M_est_arr, color=COLOR_TEAL, linewidth=2.0, label="Estimated Zone Air Mass M (kg)")
        ax2.axhline(M_ROOM, color=COLOR_CYAN, linestyle="--", label=f"Nominal M = {M_ROOM:.2f} kg")
        ax2.set_ylabel("Air Mass M (kg)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        ax3.plot(t_min, m_inf_arr, color=COLOR_PURPLE, linewidth=2.0, label="Estimated Infiltration Rate m_inf (g/s)")
        ax3.set_ylabel("m_inf (g/s)", fontsize=10)
        ax3.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax3.grid(True, linestyle=":", alpha=0.6)

        ax4.plot(t_min, UA_arr, color=COLOR_CRIMSON, linewidth=2.0, label="Estimated Envelope Conductance UA (W/°C)")
        ax4.axhline(UA_nom, color=COLOR_TEAL, linestyle="--", label=f"Nominal UA = {UA_nom:.2f} W/°C")
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

    print("\nALL SINGLE EKF BENCHMARK RUNS COMPLETED SUCCESSFULLY.")
