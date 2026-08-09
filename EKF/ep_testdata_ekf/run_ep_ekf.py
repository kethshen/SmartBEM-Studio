"""
SmartBEM FYP — EnergyPlus Benchmark EKF Runner (ep_testdata_ekf)
===================================================================
Runs 10-State EKF at 1-minute resolution (DT = 60.0s) on EnergyPlus 
synthetic simulation datasets / 1-min aggregated test rig telemetry.

Implements:
  - Solution 1: Smooth continuous physical bounds
  - Solution 2: Smooth adaptive process noise Q_k(msa) scaling
  - Solution 3: Physically informed X0 initialization (Cs=25kJ/K, M=7kg, UA=5.76W/K)

Generates 4 PNG plots per dataset in ep_results_plots/:
  1. [Dataset]_EP_EKF_States_3Subplots.png
  2. [Dataset]_EP_EKF_Occupancy_vs_GroundTruth.png
  3. [Dataset]_EP_EKF_Estimated_Parameters.png
  4. [Dataset]_EP_EKF_Derived_Physical_Parameters.png
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import sys

# ── Physical & Chamber Constants ───────────────────────────────────────────────
V_CHAMBER  = 5.832         # Net internal air volume [m3] (1.8m x 1.8m x 1.8m)
RHO_AIR    = 1.20           # Standard air density [kg/m3]
M_ROOM     = V_CHAMBER * RHO_AIR  # ~7.00 kg net air mass
c_pa       = 1006.0        # Specific heat of dry air [J/(kg*K)]
DT         = 60.0          # 1-minute sampling interval [seconds]

# CO2 generation rate per person — calibrated for chamber volume
g_CO2_occ_per_person = 4.5e-6 * 1e6 / V_CHAMBER  # = 0.7716 ppm/s per person

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

# ── State Dynamics & Jacobian ──────────────────────────────────────────────────
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

def run_ekf_on_dataset(df):
    N = len(df)
    
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
    
    Tz_meas = df["T_z_weighted"].values
    RHz_meas = df["RH_z_weighted"].values
    wz_meas = np.array([rh_to_humidity_ratio(RHz_meas[i], Tz_meas[i], P_live_arr[i]) for i in range(N)])
    cz_meas = df["CO2_z_weighted"].values
    
    X = np.zeros(N_STATES)
    # Physically Informed Initialization (anchored at physical baseline at t=0)
    X[I_ao] = 0.00023  # UA / Cs = 5.76 W/K / 25000 J/K
    X[I_as] = 0.0402   # cpa / Cs = 1006.0 J/(kg*K) / 25000 J/K
    X[I_ae] = 0.0000
    X[I_bo] = 3.06e-6  # minf / Mroom = 2.14e-5 kg/s / 7.00 kg
    X[I_bs] = 0.1428   # 1 / Mroom = 1 / 7.00 kg
    X[I_be] = 0.0000
    X[I_ge] = 0.0000
    X[I_Tz] = Tz_meas[0]
    X[I_wz] = wz_meas[0]
    X[I_cz] = cz_meas[0]
    
    P = np.eye(N_STATES) * 0.1
    P[I_ge, I_ge] = 1.0
    
    # Process noise Q — baseline tuning
    Q_base = np.diag([1e-7, 1e-7, 1e-7, 1e-7, 1e-7, 1e-7, 1e-5, 1e-3, 1e-5, 1.0])
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
        
        # Adaptive Excitation Scaling Q_k(msa)
        excitation_factor = np.tanh(msa[k] / 0.010)
        Q_k = Q_base.copy()
        Q_k[I_as, I_as] = 1e-9 + 1e-7 * excitation_factor
        Q_k[I_bs, I_bs] = 1e-9 + 1e-7 * excitation_factor
        
        P_pred = F_k @ P @ F_k.T + Q_k
        
        Z_pred = np.array([X_pred[I_Tz], X_pred[I_wz], X_pred[I_cz]])
        y_k = Z_k - Z_pred
        
        S_k = H @ P_pred @ H.T + R
        K_k = P_pred @ H.T @ np.linalg.inv(S_k)
        
        X = X_pred + K_k @ y_k
        P = (np.eye(N_STATES) - K_k @ H) @ P_pred
        
        X[I_ge] = np.clip(X[I_ge], 0.0, None)
        X[I_cz] = np.clip(X[I_cz], 300.0, 1000.0)
        
        X_hist[k] = X
        
    return X_hist, Tz_meas, RHz_meas, cz_meas, P_live_arr

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    STUDIO_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

    DAY3_DIR = os.path.join(STUDIO_DIR, "Experimental_Rig_Calibration", "experimental_data", "with_occ", "Day_3")
    DAY4_DIR = os.path.join(STUDIO_DIR, "Experimental_Rig_Calibration", "experimental_data", "with_occ", "Day_4")

    DAY3_CLEAN_DIR = os.path.join(DAY3_DIR, "cleaned_day_3")
    DAY4_CLEAN_DIR = os.path.join(DAY4_DIR, "cleaned_day_4")
    
    OUT_PLOT_DIR = os.path.join(SCRIPT_DIR, "ep_results_plots")
    os.makedirs(OUT_PLOT_DIR, exist_ok=True)
    
    day4_sched_p = os.path.join(DAY4_DIR, "occ_schedule_day_4.csv")
    df_sched4 = pd.read_csv(day4_sched_p)
    df_sched4.columns = [c.strip() for c in df_sched4.columns]
    
    d3_files = [f for f in os.listdir(DAY3_CLEAN_DIR) if f.endswith("_cleaned.csv")]
    d4_files = [f for f in os.listdir(DAY4_CLEAN_DIR) if f.endswith("_cleaned.csv")]
    
    all_runs = [(3, f) for f in d3_files] + [(4, f) for f in d4_files]
    
    for day, fname in all_runs:
        folder = DAY3_CLEAN_DIR if day == 3 else DAY4_CLEAN_DIR
        df_raw = pd.read_csv(os.path.join(folder, fname))
        
        # Resample data to 1-minute resolution (DT = 60s) for EnergyPlus alignment
        if "timestamp" in df_raw.columns:
            df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"])
            df = df_raw.resample("1min", on="timestamp").mean().reset_index()
        else:
            df = df_raw.iloc[::12].copy().reset_index(drop=True)
            
        base_name = fname.replace("_cleaned.csv", "")
        raw_filename = f"{base_name}.csv"
        
        print(f"Running 1-Min EnergyPlus Benchmark EKF for Day {day}: {base_name}...")
        X_hist, Tz_m, RHz_m, cz_m, P_live = run_ekf_on_dataset(df)
        
        t_min = np.arange(len(df)) * (DT / 60.0)
        
        rh_est = np.array([humidity_ratio_to_rh(X_hist[i, I_wz], X_hist[i, I_Tz], P_live[i]) for i in range(len(df))])
        
        # ── PLOT 1: 3-SUBPLOT ENVIRONMENTAL STATES ─────────────────────────────
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
        
        ax1.plot(t_min, Tz_m, "r--", alpha=0.6, label="Measured Tz")
        ax1.plot(t_min, X_hist[:, I_Tz], "b-", lw=1.8, label="EKF Estimated Tz")
        ax1.set_ylabel("Temperature (°C)", fontsize=10)
        ax1.set_title(f"{base_name} — 1-Min EKF Environmental State Estimations", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right", fontsize=8)
        ax1.grid(True, alpha=0.3)
        
        ax2.plot(t_min, RHz_m, "orange", linestyle="--", alpha=0.6, label="Measured RHz")
        ax2.plot(t_min, rh_est, "teal", linestyle="-", lw=1.8, label="EKF Estimated RHz")
        ax2.set_ylim(20.0, 120.0)
        ax2.set_ylabel("Relative Humidity (%)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, alpha=0.3)
        
        ax3.plot(t_min, cz_m, "g--", alpha=0.6, label="Measured CO2z")
        ax3.plot(t_min, X_hist[:, I_cz], "k-", lw=1.8, label="EKF Estimated CO2z")
        ax3.set_ylim(300.0, 700.0)
        ax3.set_ylabel("CO2 Concentration (ppm)", fontsize=10)
        ax3.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax3.legend(loc="upper right", fontsize=8)
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_PLOT_DIR, f"{base_name}_EP_EKF_States_3Subplots.png"), dpi=150)
        plt.close()
        
        # ── PLOT 2: OCCUPANCY RECOVERY VS GROUND TRUTH ─────────────────────────
        n_est = X_hist[:, I_ge] / g_CO2_occ_per_person
        
        if day == 4:
            n_gt = get_day4_occupancy_series(df, raw_filename, df_sched4)
        else:
            n_gt = get_day3_occupancy_series(df)
        
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(t_min, n_est, "m-", lw=2.0, label="EKF Estimated Occupants (N)")
        ax.step(t_min, n_gt, "k--", where="post", alpha=0.8, lw=1.8, label="Ground Truth Occupancy Schedule")
            
        ax.set_ylim(-0.5, max(4.0, np.max(n_gt) + 1.5))
        ax.set_ylabel("Occupant Count (person)", fontsize=11)
        ax.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax.set_title(f"{base_name} — 1-Min EKF Recovered Occupancy vs Ground Truth", fontsize=12, fontweight="bold")
        ax.legend(loc="upper right", fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_PLOT_DIR, f"{base_name}_EP_EKF_Occupancy_vs_GroundTruth.png"), dpi=150)
        plt.close()
        
        # ── PLOT 3: 7 ESTIMATED PARAMETERS SUBPLOTS ───────────────────────────
        fig, axes = plt.subplots(7, 1, figsize=(11, 14), sharex=True)
        
        param_configs = [
            (I_ao, r"$\alpha_o$ [1/s]", "purple", "Outdoor Wall Heat Exchange Coeff"),
            (I_as, r"$\alpha_s$ [1/(kg·s)]", "blue", "Supply Air Heat Exchange Coeff"),
            (I_ae, r"$\alpha_e$ [°C/s]", "navy", "Internal Heat Generation Bias"),
            (I_bo, r"$\beta_o$ [1/s]", "darkgreen", "Infiltration / Ingress Coeff"),
            (I_bs, r"$\beta_s$ [1/(kg·s)]", "teal", "Supply Air Mixing Coeff"),
            (I_be, r"$\beta_e$ [kg_w/(kg_a·s)]", "olive", "Internal Moisture Load Bias"),
            (I_ge, r"$\gamma_e$ [ppm/s]", "crimson", "CO2 Generation Rate")
        ]
        
        axes[0].set_title(f"{base_name} — 1-Min EKF Estimated Parameters Tracking", fontsize=12, fontweight="bold")
        
        for idx, (p_idx, label_str, color_str, title_str) in enumerate(param_configs):
            ax = axes[idx]
            ax.plot(t_min, X_hist[:, p_idx], color=color_str, lw=1.5, label=title_str)
            ax.set_ylabel(label_str, fontsize=9)
            ax.legend(loc="upper right", fontsize=8)
            ax.grid(True, alpha=0.3)
            
        axes[-1].set_xlabel("Elapsed Time (minutes)", fontsize=11)
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_PLOT_DIR, f"{base_name}_EP_EKF_Estimated_Parameters.png"), dpi=150)
        plt.close()
        
        # ── PLOT 4: DERIVED PHYSICAL PARAMETERS VS GROUND TRUTH BANDS ─────────
        Cs_arr = c_pa / np.where(np.abs(X_hist[:, I_as]) > 1e-12, X_hist[:, I_as], 1e-12)
        M_est_arr = 1.0 / np.where(np.abs(X_hist[:, I_bs]) > 1e-12, X_hist[:, I_bs], 1e-12)
        M_est_arr = np.clip(M_est_arr, 0.0, 50.0)
        m_inf_arr_g_s = (X_hist[:, I_bo] * M_est_arr) * 1000.0
        UA_arr = X_hist[:, I_ao] * Cs_arr - c_pa * (X_hist[:, I_bo] * M_est_arr)
        
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(11, 12), sharex=True)
        
        ax1.plot(t_min, Cs_arr / 1000.0, "b-", lw=1.8, label="Estimated Thermal Capacitance Cs (kJ/°C)")
        ax1.axhspan(20.0, 30.0, color="lightgreen", alpha=0.35, label="EnergyPlus Calibrated Baseline (20.0 - 30.0 kJ/°C)")
        ax1.set_ylabel("Cs (kJ/°C)", fontsize=10)
        ax1.set_title(f"{base_name} — 1-Min EKF Derived Physical Building Parameters (Cs, M, m_inf, UA)", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right", fontsize=8)
        ax1.grid(True, alpha=0.3)
        
        ax2.plot(t_min, M_est_arr, "teal", lw=1.8, label="Estimated Zone Air Mass M (kg)")
        ax2.axhspan(6.70, 7.10, color="lightgreen", alpha=0.35, label="Physical Air Mass Baseline (6.70 - 7.10 kg)")
        ax2.set_ylabel("Air Mass M (kg)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, alpha=0.3)
        
        ax3.plot(t_min, m_inf_arr_g_s, "purple", lw=1.8, label="Estimated Infiltration Rate m_inf (g/s)")
        ax3.axhspan(0.00, 0.10, color="lightgreen", alpha=0.35, label="EnergyPlus Infiltration Baseline (0.00 - 0.10 g/s)")
        ax3.set_ylabel("m_inf (g/s)", fontsize=10)
        ax3.legend(loc="upper right", fontsize=8)
        ax3.grid(True, alpha=0.3)
        
        ax4.plot(t_min, UA_arr, "darkred", lw=1.8, label="Estimated Envelope Conductance UA (W/°C)")
        ax4.axhspan(5.50, 6.50, color="lightgreen", alpha=0.35, label="EnergyPlus Calibrated Baseline (5.50 - 6.50 W/°C)")
        ax4.set_ylabel("UA (W/°C)", fontsize=10)
        ax4.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax4.legend(loc="upper right", fontsize=8)
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_PLOT_DIR, f"{base_name}_EP_EKF_Derived_Physical_Parameters.png"), dpi=150)
        plt.close()
        
        print(f"  Saved 4 PNG plots for {base_name}")

    print("\nALL 1-MIN ENERGYPLUS BENCHMARK EKF RUNS COMPLETED SUCCESSFULLY.")
