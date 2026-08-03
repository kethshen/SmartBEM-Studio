"""
SmartBEM FYP — 10-State EKF for Experimental Test Rig (Day 3 & Day 4)
======================================================================
Generates exactly 2 PNG plots per dataset:
  1. [Dataset]_EKF_States_3Subplots.png   (Temperature, Relative Humidity %, CO2)
  2. [Dataset]_EKF_Occupancy_vs_GroundTruth.png (EKF Estimated Occupants vs Exact Ground Truth Schedule)
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import sys

# ── Physical & Chamber Constants ───────────────────────────────────────────────
M_ROOM = 7.00             # Air mass of test chamber [kg] (1.8m x 1.8m x 1.8m)
c_pa   = 1006.0           # Specific heat of air [J/(kg*K)]
g_CO2_occ = 1.725         # CO2 generation rate per person [ppm*kg/(s*person)]
DT = 5.0                  # Sampling time step [seconds]

# ── State Indices ──────────────────────────────────────────────────────────────
I_ao, I_as, I_ae = 0, 1, 2
I_bo, I_bs, I_be = 3, 4, 5
I_ge             = 6
I_Tz, I_wz, I_cz = 7, 8, 9
N_STATES = 10

def rh_to_humidity_ratio(rh_pct, T_C, P_atm=101325.0):
    rh = np.clip(rh_pct / 100.0, 0.0, 1.0)
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    omega = 0.622 * (rh * P_sat) / (P_atm - rh * P_sat)
    return np.clip(omega, 0.0, 0.05)

def humidity_ratio_to_rh(omega, T_C, P_atm=101325.0):
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    P_w = (omega * P_atm) / (0.622 + omega)
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

# ── EKF State Dynamics f(X, U) ─────────────────────────────────────────────────
def f_dynamics(X, U):
    ao, as_, ae = X[I_ao], X[I_as], X[I_ae]
    bo, bs, be   = X[I_bo], X[I_bs], X[I_be]
    ge           = X[I_ge]
    Tz, wz, cz   = X[I_Tz], X[I_wz], X[I_cz]
    
    To, wo, co, Tsa, wsa, csa, msa = U
    
    dTz  = ao * (To - Tz) + as_ * msa * (Tsa - Tz) + ae
    dwz  = bo * (wo - wz) + bs  * msa * (wsa - wz)  + be
    dcz  = bo * (co - cz) + bs  * msa * (csa - cz)  + (ge / M_ROOM)
    
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
    J[I_cz, I_ge] = 1.0 / M_ROOM
    J[I_cz, I_cz] = -(bo + bs * msa)
    
    return J

def run_ekf_on_dataset(df):
    N = len(df)
    
    To = df["outside_t"].values
    wo = rh_to_humidity_ratio(df["outside_h"].values, To)
    co = df["outside_c"].values
    
    Tsa = df["supply_t"].values
    wsa = rh_to_humidity_ratio(df["supply_h"].values, Tsa)
    csa = df["supply_c"].values
    
    msa = df["m_sa_kgs"].values
    
    Tz_meas = df["T_z_weighted"].values
    RHz_meas = df["RH_z_weighted"].values
    wz_meas = rh_to_humidity_ratio(RHz_meas, Tz_meas)
    cz_meas = df["CO2_z_weighted"].values
    
    X = np.zeros(N_STATES)
    X[I_ao] = 0.001
    X[I_as] = 0.010
    X[I_ae] = 0.000
    X[I_bo] = 0.001
    X[I_bs] = 0.010
    X[I_be] = 0.000
    X[I_ge] = 0.000
    X[I_Tz] = Tz_meas[0]
    X[I_wz] = wz_meas[0]
    X[I_cz] = cz_meas[0]
    
    P = np.eye(N_STATES) * 0.1
    P[I_ge, I_ge] = 1.0
    
    Q = np.diag([1e-6, 1e-6, 1e-6, 1e-6, 1e-6, 1e-6, 1e-4, 1e-4, 1e-6, 1e-2])
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
        P_pred = F_k @ P @ F_k.T + Q
        
        Z_pred = np.array([X_pred[I_Tz], X_pred[I_wz], X_pred[I_cz]])
        y_k = Z_k - Z_pred
        
        S_k = H @ P_pred @ H.T + R
        K_k = P_pred @ H.T @ np.linalg.inv(S_k)
        
        X = X_pred + K_k @ y_k
        P = (np.eye(N_STATES) - K_k @ H) @ P_pred
        
        X[I_cz] = np.clip(X[I_cz], 300.0, 700.0)
        X[I_ge] = np.clip(X[I_ge], 0.0, None)
        
        X_hist[k] = X
        
    return X_hist, Tz_meas, RHz_meas, cz_meas

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    STUDIO_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

    DAY3_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig", "experimental_data", "with_occ", "Day_3")
    DAY4_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig", "experimental_data", "with_occ", "Day_4")

    DAY3_CLEAN_DIR = os.path.join(DAY3_DIR, "cleaned_day_3")
    DAY4_CLEAN_DIR = os.path.join(DAY4_DIR, "cleaned_day_4")
    
    OUT_PLOT_DIR = os.path.join(SCRIPT_DIR, "results_plots")
    os.makedirs(OUT_PLOT_DIR, exist_ok=True)
    
    # Load Day 4 Schedule CSV
    day4_sched_p = os.path.join(DAY4_DIR, "occ_schedule_day_4.csv")
    df_sched4 = pd.read_csv(day4_sched_p)
    df_sched4.columns = [c.strip() for c in df_sched4.columns]
    
    # Clean previous output plots
    for f in os.listdir(OUT_PLOT_DIR):
        if f.endswith(".png"):
            os.remove(os.path.join(OUT_PLOT_DIR, f))
            
    d3_files = [f for f in os.listdir(DAY3_CLEAN_DIR) if f.endswith("_cleaned.csv")]
    d4_files = [f for f in os.listdir(DAY4_CLEAN_DIR) if f.endswith("_cleaned.csv")]
    
    all_runs = [(3, f) for f in d3_files] + [(4, f) for f in d4_files]
    
    for day, fname in all_runs:
        folder = DAY3_CLEAN_DIR if day == 3 else DAY4_CLEAN_DIR
        df = pd.read_csv(os.path.join(folder, fname))
        base_name = fname.replace("_cleaned.csv", "")
        raw_filename = f"{base_name}.csv"
        
        print(f"Running 10-State EKF for Day {day}: {base_name}...")
        X_hist, Tz_m, RHz_m, cz_m = run_ekf_on_dataset(df)
        
        ts = pd.to_datetime(df["timestamp"])
        t_min = (ts - ts.iloc[0]).dt.total_seconds() / 60.0
        
        # Convert estimated humidity ratio omega_z back to RH %
        rh_est = humidity_ratio_to_rh(X_hist[:, I_wz], X_hist[:, I_Tz])
        
        # ── PLOT 1: 3-SUBPLOT ENVIRONMENTAL STATES ─────────────────────────────
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
        
        # Subplot 1: Temperature
        ax1.plot(t_min, Tz_m, "r--", alpha=0.6, label="Measured Tz")
        ax1.plot(t_min, X_hist[:, I_Tz], "b-", lw=1.8, label="EKF Estimated Tz")
        ax1.set_ylabel("Temperature (°C)", fontsize=10)
        ax1.set_title(f"{base_name} — 10-State EKF Environmental State Estimations", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right", fontsize=8)
        ax1.grid(True, alpha=0.3)
        
        # Subplot 2: Relative Humidity
        ax2.plot(t_min, RHz_m, "orange", linestyle="--", alpha=0.6, label="Measured RHz")
        ax2.plot(t_min, rh_est, "teal", linestyle="-", lw=1.8, label="EKF Estimated RHz")
        ax2.set_ylim(20.0, 120.0) # FIXED AT 20 - 120
        ax2.set_ylabel("Relative Humidity (%)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, alpha=0.3)
        
        # Subplot 3: CO2 Concentration
        ax3.plot(t_min, cz_m, "g--", alpha=0.6, label="Measured CO2z")
        ax3.plot(t_min, X_hist[:, I_cz], "k-", lw=1.8, label="EKF Estimated CO2z")
        ax3.set_ylim(300.0, 700.0) # FIXED AT 300 - 700 PPM
        ax3.set_ylabel("CO2 Concentration (ppm)", fontsize=10)
        ax3.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax3.legend(loc="upper right", fontsize=8)
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_PLOT_DIR, f"{base_name}_EKF_States_3Subplots.png"), dpi=150)
        plt.close()
        
        # ── PLOT 2: SEPARATE OCCUPANCY RECOVERY VS EXACT GROUND TRUTH ──────────
        n_est = (X_hist[:, I_ge] * M_ROOM) / g_CO2_occ
        
        if day == 4:
            n_gt = get_day4_occupancy_series(df, raw_filename, df_sched4)
        else:
            n_gt = get_day3_occupancy_series(df)
        
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(t_min, n_est, "m-", lw=2.0, label="EKF Estimated Occupants (N)")
        ax.step(t_min, n_gt, "k--", where="post", alpha=0.8, lw=1.8, label="Ground Truth Occupancy Schedule")
            
        ax.set_ylabel("Occupant Count (person)", fontsize=11)
        ax.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax.set_title(f"{base_name} — EKF Recovered Occupancy vs Ground Truth", fontsize=12, fontweight="bold")
        ax.legend(loc="upper right", fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_PLOT_DIR, f"{base_name}_EKF_Occupancy_vs_GroundTruth.png"), dpi=150)
        plt.close()
        
        print(f"  Saved 2 PNG plots for {base_name}")

    print("\nALL EKF RUNS & 2-PNG PLOTS GENERATED SUCCESSFULLY WITH EXACT GROUND TRUTH.")
