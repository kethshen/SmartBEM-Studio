"""
SmartBEM FYP — 10-State EKF for Experimental Test Rig (Day 3 & Day 4)
======================================================================
Fully aligned with advisor's EMS_Cookbook ODEs & ROBOD-consistent formulation:
  - Uses live sensor barometric pressure (P_live in Pa)
  - Fully lumped CO2 dynamics (gamma_e enters ODE directly, no division)
  - Occupancy recovery: N = gamma_e * M_room / g_CO2_occ (same as ROBOD)
  - g_CO2_occ calibrated for chamber volume

Generates exactly 2 PNG plots per dataset:
  1. [Dataset]_EKF_States_3Subplots.png   (Temperature, Relative Humidity %, CO2)
  2. [Dataset]_EKF_Occupancy_vs_GroundTruth.png (EKF Estimated Occupants vs Exact Ground Truth Schedule)
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

# ── Physical & Chamber Constants ───────────────────────────────────────────────
V_CHAMBER  = 5.832         # Net internal air volume [m3] (1.8m x 1.8m x 1.8m)
RHO_AIR    = 1.20           # Standard air density [kg/m3] (updated dynamically below)
M_ROOM     = V_CHAMBER * RHO_AIR  # ~7.00 kg net air mass
c_pa       = 1006.0        # Specific heat of dry air [J/(kg*K)]
R_SPECIFIC = 287.058        # Specific gas constant for dry air [J/(kg*K)]
DT = 5.0                   # Sampling time step [seconds]

# CO2 generation rate per person — calibrated for this chamber
# From steady-state balance: g_CO2_occ = m_sa * (c_z - c_o) / N
# Using ASHRAE volumetric rate: G_person = 4.5 cm3/s = 4.5e-6 m3/s
# Converting to lumped EKF units: g_CO2_occ = G_person_ppm_m3s / M_room
#   = 4.5 [ppm*m3/s] / 7.0 [kg] = 0.643 [ppm*m3/(s*kg)]  (per person)
# BUT in the fully-lumped formulation (ROBOD-style), gamma_e already absorbs
# the 1/M factor, so: N = gamma_e * M_room / g_CO2_occ
# Calibrating from ASHRAE: g_CO2_occ = G_person_vol / V_chamber * M_room
#   = (4.5 / 5.832) * 7.0 = 5.40
# Alternatively, direct: g_CO2_occ = G_person_ppm_m3s = 4.5  and  N = gamma_e / (g/M)
# Simplest: in ROBOD-style, g_CO2_occ has units [ppm/s / (person/kg)]
# For our chamber: 1 person adds 4.5e-6 m3/s CO2 into 5.832 m3 = 0.772 ppm/s
# In the lumped ODE: gamma_e ≈ 0.772 for 1 person
# N = gamma_e / (0.772) = gamma_e * M / (G * M / V) = gamma_e / (G_person/V)
g_CO2_occ_per_person = 4.5e-6 * 1e6 / V_CHAMBER  # = 0.772 ppm/s per person

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
        elapsed_min = np.arange(len(df_data)) * 5.0 / 60.0
        
    occ_vec = np.zeros(len(df_data), dtype=float)
    for i, m in enumerate(elapsed_min):
        if 5.0 <= m <= 20.0:
            occ_vec[i] = 1.0
    return occ_vec

# ── EKF State Dynamics f(X, U) — ROBOD-Consistent Fully Lumped ────────────────
def f_dynamics(X, U):
    ao, as_, ae = X[I_ao], X[I_as], X[I_ae]
    bo, bs, be   = X[I_bo], X[I_bs], X[I_be]
    ge           = X[I_ge]
    Tz, wz, cz   = X[I_Tz], X[I_wz], X[I_cz]
    
    To, wo, co, Tsa, wsa, csa, msa = U
    
    # Temperature ODE (advisor line 106)
    dTz  = ao * (To - Tz) + as_ * msa * (Tsa - Tz) + ae
    # Humidity ODE (advisor line 110)
    dwz  = bo * (wo - wz) + bs  * msa * (wsa - wz)  + be
    # CO2 ODE — FULLY LUMPED (ROBOD-style): gamma_e enters directly, no /V or /M
    # gamma_e absorbs all scaling: units = [ppm/s] directly
    dcz  = bo * (co - cz) + bs  * msa * (csa - cz)  + ge
    
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
    
    # CO2 derivatives — FULLY LUMPED: d(dcz)/d(ge) = 1.0 (ROBOD-consistent)
    J[I_cz, I_bo] = co - cz
    J[I_cz, I_bs] = msa * (csa - cz)
    J[I_cz, I_ge] = 1.0    # NOT 1/V — gamma_e is fully lumped
    J[I_cz, I_cz] = -(bo + bs * msa)
    
    return J

def run_ekf_on_dataset(df):
    N = len(df)
    
    # Live barometric pressure from sensor telemetry (convert hPa -> Pa)
    if "outside_p" in df.columns and df["outside_p"].dropna().mean() > 500:
        P_live_arr = df["outside_p"].fillna(1013.25).values * 100.0
    elif "room_1_p" in df.columns and df["room_1_p"].dropna().mean() > 500:
        P_live_arr = df["room_1_p"].fillna(1013.25).values * 100.0
    else:
        P_live_arr = np.full(N, 101325.0)
        
    To = df["outside_t"].values
    wo = np.array([rh_to_humidity_ratio(df["outside_h"].values[i], To[i], P_live_arr[i]) for i in range(N)])
    co = df["outside_c"].values
    
    Tsa = df["supply_t"].values
    wsa = np.array([rh_to_humidity_ratio(df["supply_h"].values[i], Tsa[i], P_live_arr[i]) for i in range(N)])
    csa = df["supply_c"].values
    
    msa = df["m_sa_kgs"].values
    
    tz_col = "Tz_weighted" if "Tz_weighted" in df.columns else ("T_z_weighted" if "T_z_weighted" in df.columns else "room_1_t")
    rhz_col = "RHz_weighted" if "RHz_weighted" in df.columns else ("RH_z_weighted" if "RH_z_weighted" in df.columns else "room_1_h")
    co2z_col = "CO2z_weighted" if "CO2z_weighted" in df.columns else ("CO2_z_weighted" if "CO2_z_weighted" in df.columns else "room_1_c")

    # Fallback for room temperature if Tz_weighted contains NaNs
    Tz_series = df[tz_col]
    if Tz_series.isna().any():
        fallback_tz = (df["room_1_t"] + df["room_2_t"]) / 2.0 if ("room_1_t" in df.columns and "room_2_t" in df.columns) else df["room_1_t"]
        Tz_series = Tz_series.fillna(fallback_tz)
    Tz_meas = Tz_series.values

    # Fallback for relative humidity if RHz_weighted contains NaNs
    RHz_series = df[rhz_col]
    if RHz_series.isna().any():
        fallback_rh = (df["room_1_h"] + df["room_2_h"]) / 2.0 if ("room_1_h" in df.columns and "room_2_h" in df.columns) else df["room_1_h"]
        RHz_series = RHz_series.fillna(fallback_rh)
    RHz_meas = RHz_series.values

    # Fallback for CO2 if CO2z_weighted contains NaNs
    co2_series = df[co2z_col]
    if co2_series.isna().any():
        fallback_co2 = (df["room_1_c"] + df["room_2_c"]) / 2.0 if ("room_1_c" in df.columns and "room_2_c" in df.columns) else df["room_1_c"]
        co2_series = co2_series.fillna(fallback_co2)
    cz_meas = co2_series.values

    wz_meas = np.array([rh_to_humidity_ratio(RHz_meas[i], Tz_meas[i], P_live_arr[i]) for i in range(N)])
    
    X = np.zeros(N_STATES)
    # Solution 3 & Step 1: Physically Informed Initialization (anchored at physical reality at t=0)
    X[I_ao] = 0.00023  # UA / Cs = 5.76 W/K / 25000 J/K
    X[I_as] = 0.0402   # cpa / Cs = 1006.0 J/(kg*K) / 25000 J/K
    X[I_ae] = 0.0000   # 0 equipment heat load at start
    X[I_bo] = 3.06e-6  # minf / Mroom = 2.14e-5 kg/s / 7.00 kg
    X[I_bs] = 0.1428   # 1 / Mroom = 1 / 7.00 kg
    X[I_be] = 0.0000   # 0 moisture load at start
    X[I_ge] = 0.0000   # 0 occupants at start
    X[I_Tz] = Tz_meas[0]
    X[I_wz] = wz_meas[0]
    X[I_cz] = cz_meas[0]
    
    P = np.eye(N_STATES) * 0.1
    P[I_ge, I_ge] = 1.0
    
    # Process noise Q — ROBOD-consistent baseline tuning
    Q_base = np.diag([1e-6, 1e-6, 1e-6, 1e-6, 1e-6, 1e-6, 1e-5, 1e-4, 1e-6, 1e-2])
    R = np.diag([0.05**2, 0.0002**2, 2.5**2])
    
    H = np.zeros((3, N_STATES))
    H[0, I_Tz] = 1.0
    H[1, I_wz] = 1.0
    H[2, I_cz] = 1.0
    
    X_hist = np.zeros((N, N_STATES))
    
    for k in range(N):
        U_k = [To[k], wo[k], co[k], Tsa[k], wsa[k], csa[k], msa[k]]
        Z_k = np.array([Tz_meas[k], wz_meas[k], cz_meas[k]])
        
        dX = f_dynamics(X, U_k)
        X_pred = X + dX * DT
        
        J_F = get_jacobian_F(X, U_k)
        F_k = np.eye(N_STATES) + J_F * DT
        
        # Solution 2: Smooth Adaptive Process Noise Q_k(msa) Scaling
        # Scales parameter process noise smoothly as supply flow excitation rises
        excitation_factor = np.tanh(msa[k] / 0.010)
        Q_k = Q_base.copy()
        Q_k[I_as, I_as] = 1e-8 + 1e-6 * excitation_factor
        Q_k[I_bs, I_bs] = 1e-8 + 1e-6 * excitation_factor
        
        P_pred = F_k @ P @ F_k.T + Q_k
        
        Z_pred = np.array([X_pred[I_Tz], X_pred[I_wz], X_pred[I_cz]])
        y_k = Z_k - Z_pred
        
        S_k = H @ P_pred @ H.T + R
        K_k = P_pred @ H.T @ np.linalg.inv(S_k)
            
        X = X_pred + K_k @ y_k
        P = (np.eye(N_STATES) - K_k @ H) @ P_pred
        
        # Solution 1 & 3: Smooth Physical Bounds (no hard discontinuous np.clip)
        X[I_ge] = np.clip(X[I_ge], 0.0, None)
        X[I_cz] = np.clip(X[I_cz], 300.0, 1000.0)
        
        X_hist[k] = X
        
    return X_hist, Tz_meas, RHz_meas, cz_meas, P_live_arr

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    STUDIO_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))

    CLEAN_DATA_DIR = os.path.join(STUDIO_DIR, "Experimental_Rig_Calibration", "sensor_readings", "cleaned", "with_occ")
    PLOTS_ROOT_DIR = os.path.join(SCRIPT_DIR, "plots")
    os.makedirs(PLOTS_ROOT_DIR, exist_ok=True)

    # Load Day 4 Schedule CSV
    day4_sched_p = os.path.join(CLEAN_DATA_DIR, "occ_schedule_day_4.csv")
    if os.path.exists(day4_sched_p):
        df_sched4 = pd.read_csv(day4_sched_p)
        df_sched4.columns = [c.strip() for c in df_sched4.columns]
    else:
        df_sched4 = pd.DataFrame()

    all_csv_files = [f for f in os.listdir(CLEAN_DATA_DIR) if f.startswith("day_") and f.endswith(".csv")]
    all_csv_files.sort()

    for fname in all_csv_files:
        day = 4 if "day_4" in fname else 3
        df = pd.read_csv(os.path.join(CLEAN_DATA_DIR, fname))
        base_name = fname.replace(".csv", "")
        raw_filename = f"{base_name}.csv"

        # Create dataset-specific plot subfolder (e.g. plots/day_3_p_1/)
        dataset_plot_dir = os.path.join(PLOTS_ROOT_DIR, base_name)
        os.makedirs(dataset_plot_dir, exist_ok=True)

        print(f"\nRunning Single 10-State EKF for Day {day}: {base_name}...")
        print(f"• Output folder: {dataset_plot_dir}")

        X_hist, Tz_m, RHz_m, cz_m, P_live = run_ekf_on_dataset(df)

        ts = pd.to_datetime(df["timestamp"])
        t_min = (ts - ts.iloc[0]).dt.total_seconds() / 60.0

        # Convert estimated humidity ratio omega_z back to RH % using live barometric pressure
        rh_est = np.array([humidity_ratio_to_rh(X_hist[i, I_wz], X_hist[i, I_Tz], P_live[i]) for i in range(len(df))])

        # ── PLOT 1: 3-SUBPLOT ENVIRONMENTAL STATES ─────────────────────────────
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

        # Subplot 1: Temperature
        ax1.plot(t_min, Tz_m, color=COLOR_CYAN, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured Tz")
        ax1.plot(t_min, X_hist[:, I_Tz], color=COLOR_RED, linestyle="-", linewidth=2.2, label="EKF Estimated Tz")
        ax1.set_ylabel("Temperature (°C)", fontsize=10)
        ax1.set_title(f"{base_name} — Single 10-State EKF Environmental State Estimations", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        # Subplot 2: Relative Humidity
        ax2.plot(t_min, RHz_m, color=COLOR_ORANGE, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured RHz")
        ax2.plot(t_min, rh_est, color=COLOR_BLUE, linestyle="-", linewidth=2.2, label="EKF Estimated RHz")
        ax2.set_ylim(20.0, 120.0)
        ax2.set_ylabel("Relative Humidity (%)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        # Subplot 3: CO2 Concentration
        ax3.plot(t_min, cz_m, color=COLOR_CRIMSON, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured CO2z")
        ax3.plot(t_min, X_hist[:, I_cz], color=COLOR_TEAL, linestyle="-", linewidth=2.2, label="EKF Estimated CO2z")
        ax3.set_ylim(300.0, 700.0)
        ax3.set_ylabel("CO2 Concentration (ppm)", fontsize=10)
        ax3.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax3.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax3.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot1_path = os.path.join(dataset_plot_dir, "single_ekf_states.png")
        plt.savefig(plot1_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 1: {plot1_path}")

        # ── PLOT 2: OCCUPANCY RECOVERY VS GROUND TRUTH ─────────────────────────
        n_est = X_hist[:, I_ge] / g_CO2_occ_per_person
        n_disc = np.round(np.clip(n_est, 0.0, None))

        if day == 4 and not df_sched4.empty:
            n_gt = get_day4_occupancy_series(df, raw_filename, df_sched4)
        else:
            n_gt = get_day3_occupancy_series(df)

        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(t_min, n_est, color=COLOR_PURPLE, linestyle="-", linewidth=2.0, label="Continuous EKF Estimated Occupants (N)")
        ax.step(t_min, n_disc, color=COLOR_BLUE, where="post", linewidth=2.2, alpha=0.9, label="Thresholded Integer Occupants (Discretized)")
        ax.step(t_min, n_gt, color=COLOR_TEAL, linestyle="--", where="post", alpha=0.8, linewidth=2.0, label="Ground Truth Occupancy Schedule")

        ax.set_ylim(-0.5, max(4.0, np.max(n_gt) + 1.5))
        ax.set_ylabel("Occupant Count (person)", fontsize=11)
        ax.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax.set_title(f"{base_name} — Single EKF Recovered Occupancy vs Ground Truth", fontsize=12, fontweight="bold", pad=12)
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
        
        axes[0].set_title(f"{base_name} — Single EKF Estimated Parameters Tracking", fontsize=12, fontweight="bold", pad=12)
        
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

        # ── PLOT 4: 4-SUBPLOT DERIVED PHYSICAL PARAMETERS (Cs, M_room, m_inf, UA) ──
        # Calculate derived physical properties from estimated state parameters:
        # 1. Cs = c_pa / alpha_s  [J/°C]
        Cs_arr = c_pa / np.where(np.abs(X_hist[:, I_as]) > 1e-12, X_hist[:, I_as], 1e-12)

        # 2. M_room = 1 / beta_s  [kg]
        M_est_arr = 1.0 / np.where(np.abs(X_hist[:, I_bs]) > 1e-12, X_hist[:, I_bs], 1e-12)
        M_est_arr = np.clip(M_est_arr, 0.0, 50.0)

        # 3. m_inf = beta_o * M_room  [kg/s] -> convert to [g/s]
        m_inf_arr_g_s = (X_hist[:, I_bo] * M_est_arr) * 1000.0

        # 4. UA = alpha_o * Cs - c_pa * (beta_o * M_room)  [W/°C]
        UA_arr = X_hist[:, I_ao] * Cs_arr - c_pa * (X_hist[:, I_bo] * M_est_arr)

        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

        # Subplot 1: Sensible Thermal Capacitance Cs [kJ/°C]
        ax1.plot(t_min, Cs_arr / 1000.0, color=COLOR_BLUE, linewidth=2.0, label="Estimated Thermal Capacitance Cs (kJ/°C)")
        ax1.axhspan(20.0, 30.0, color=COLOR_CYAN, alpha=0.25, label="Expected Physical Range (20.0 - 30.0 kJ/°C)")
        ax1.set_ylabel("Cs (kJ/°C)", fontsize=10)
        ax1.set_title(f"{base_name} — Single EKF Derived Physical Building Parameters (Cs, M, m_inf, UA)", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        # Subplot 2: Zone Air Mass M [kg]
        ax2.plot(t_min, M_est_arr, color=COLOR_TEAL, linewidth=2.0, label="Estimated Zone Air Mass M (kg)")
        ax2.axhspan(6.70, 7.10, color=COLOR_CYAN, alpha=0.25, label="Expected Physical Range (6.70 - 7.10 kg)")
        ax2.set_ylabel("Air Mass M (kg)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        # Subplot 3: Infiltration Mass Flow Rate m_inf [g/s]
        ax3.plot(t_min, m_inf_arr_g_s, color=COLOR_PURPLE, linewidth=2.0, label="Estimated Infiltration Rate m_inf (g/s)")
        ax3.axhspan(0.00, 0.10, color=COLOR_CYAN, alpha=0.25, label="Expected Physical Range (0.00 - 0.10 g/s)")
        ax3.set_ylabel("m_inf (g/s)", fontsize=10)
        ax3.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax3.grid(True, linestyle=":", alpha=0.6)

        # Subplot 4: Overall Thermal Conductance UA [W/°C]
        ax4.plot(t_min, UA_arr, color=COLOR_CRIMSON, linewidth=2.0, label="Estimated Envelope Conductance UA (W/°C)")
        ax4.axhspan(5.50, 6.50, color=COLOR_CYAN, alpha=0.25, label="Expected Physical Range (5.50 - 6.50 W/°C)")
        ax4.set_ylabel("UA (W/°C)", fontsize=10)
        ax4.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax4.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax4.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot4_path = os.path.join(dataset_plot_dir, "single_ekf_derived_physical_properties.png")
        plt.savefig(plot4_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 4: {plot4_path}")


    print("\nALL SINGLE 10-STATE EKF RUNS & PLOTS GENERATED SUCCESSFULLY.")
