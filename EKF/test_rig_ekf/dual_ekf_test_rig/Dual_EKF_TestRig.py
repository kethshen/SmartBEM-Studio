"""
SmartBEM FYP — Dual EKF v3 for Experimental Test Rig (Day 3 & Day 4 Datasets)
=============================================================================
Architecture: Decoupled State and Parameter Filters running in tandem.

  EKF_STATES (Fast, 3-state, DT=5.0s):
    - States: [Tz, wz, cz]
    - RK4 numerical integration
    - Fixed Rs: Tz (tight), wz (tight), cz (weak, Rs=10000)
    - Prevents R-collapse (CO2 state filter does not force zero residual)

  EKF_PARAMS (Slow, 3-param, update every 60 steps = 5 min window):
    - Parameters: [xi_ao, xi_bo, xi_ge] in sigmoid-space
    - Block-diagonal Jacobian Hp (separate channels for ao, bo, ge)
    - Signed-max innovation for CO2 channel (preserves burst occupancy events)
    - Automatic beta_o freeze upon convergence to prevent channel competition

Generates 4 high-quality plots per dataset in results_plots_dualekf/
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_RIG_DIR = os.path.dirname(SCRIPT_DIR)
STUDIO_DIR = os.path.abspath(os.path.join(TEST_RIG_DIR, "..", ".."))

DAY3_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig", "experimental_data", "with_occ", "Day_3")
DAY4_DIR = os.path.join(STUDIO_DIR, "Readings_from_rig", "experimental_data", "with_occ", "Day_4")

DAY3_CLEAN_DIR = os.path.join(DAY3_DIR, "cleaned_day_3")
DAY4_CLEAN_DIR = os.path.join(DAY4_DIR, "cleaned_day_4")

OUT_DIR = os.path.join(SCRIPT_DIR, "results_plots_dualekf")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Chamber Physical Constants ────────────────────────────────────────────────
V_CHAMBER  = 5.832         # Net internal air volume [m³] (1.8m x 1.8m x 1.8m)
RHO_AIR    = 1.20          # Air density [kg/m³]
M_ROOM     = V_CHAMBER * RHO_AIR  # ~7.00 kg net air mass
c_pa       = 1006.0        # Specific heat of dry air [J/(kg·K)]
DT         = 5.0           # Step size [seconds]
PARAM_UPDATE_STEP = 12     # Update params every 12 steps = 60s (1 min window for short test runs)

# CO2 generation rate per person in test rig chamber
# 1 person adds 4.5e-6 m3/s into 5.832 m3 chamber -> 0.7716 ppm/s
G_CO2_PER_PERSON = 4.5e-6 * 1e6 / V_CHAMBER  # = 0.7716 ppm/s per person

# Nominal chamber parameters
Cs_nom = 25000.0           # Thermal capacitance [J/K] (25 kJ/K)
UA_nom = 6.0               # Envelope thermal conductance [W/K] (6.0 W/K)

# ── Sigmoid Helpers ────────────────────────────────────────────────────────────
def sigmoid(xi):
    return np.where(xi >= 0, 1.0 / (1.0 + np.exp(-xi)), np.exp(xi) / (1.0 + np.exp(xi)))

def sig_map(xi, lo, hi):
    return lo + (hi - lo) * sigmoid(xi)

def sig_jac(xi, lo, hi):
    s = sigmoid(xi)
    return (hi - lo) * s * (1.0 - s)

def xi_from_theta(theta, lo, hi):
    s = np.clip((theta - lo) / (hi - lo), 1e-6, 1.0 - 1e-6)
    return np.log(s / (1.0 - s))

# ── Humidity / Psychrometric Helpers ──────────────────────────────────────────
def rh_to_w(rh_pct, T_C, P_pa=101325.0):
    rh = np.clip(rh_pct / 100.0, 0.0, 1.0)
    Psat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    omega = 0.622 * (rh * Psat) / (P_pa - rh * Psat)
    return np.clip(omega, 0.0, 0.05)

def w_to_rh(omega, T_C, P_pa=101325.0):
    Psat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    Pw = (omega * P_pa) / (0.622 + omega)
    rh = (Pw / Psat) * 100.0
    return np.clip(rh, 0.0, 100.0)

# ── Ground Truth Schedule Readers ──────────────────────────────────────────────
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

# ══════════════════════════════════════════════════════════════════════════════
# EKF_STATES — Fast 3-State Filter Dynamics (RK4)
# ══════════════════════════════════════════════════════════════════════════════
def state_f(S, U, theta):
    """
    Physical ODEs for state [Tz, wz, cz] given fixed parameters theta.
    theta = (ao, as_fixed, bo, ge, bs_fixed)
    Inputs U = (To, wo, co, Tsa, wsa, csa, msa)
    """
    Tz, wz, cz = S
    To, wo, co, Tsa, wsa, csa, msa = U
    ao, as_f, bo, ge, bs_f = theta

    dTz = ao * (To - Tz) + as_f * msa * (Tsa - Tz)
    dwz = bo * (wo - wz) + bs_f * msa * (wsa - wz)
    dcz = bo * (co - cz) + bs_f * msa * (csa - cz) + ge
    return np.array([dTz, dwz, dcz])

def state_rk4(S, U, dt, theta):
    k1 = state_f(S,               U, theta)
    k2 = state_f(S + 0.5*dt*k1,  U, theta)
    k3 = state_f(S + 0.5*dt*k2,  U, theta)
    k4 = state_f(S + dt*k3,      U, theta)
    return S + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)

def state_jacobian(S, U, theta):
    """Analytical 3x3 Jacobian of state dynamics w.r.t. [Tz, wz, cz]."""
    ao, as_f, bo, ge, bs_f = theta
    To, wo, co, Tsa, wsa, csa, msa = U

    J = np.zeros((3, 3))
    J[0, 0] = -(ao + as_f * msa)
    J[1, 1] = -(bo + bs_f * msa)
    J[2, 2] = -(bo + bs_f * msa)
    return J

# ══════════════════════════════════════════════════════════════════════════════
# EKF_PARAMS — Slow 3-Parameter Filter Dynamics
# ══════════════════════════════════════════════════════════════════════════════
def params_from_xi(xi_p, bounds_p):
    ao = sig_map(xi_p[0], *bounds_p["ao"])
    bo = sig_map(xi_p[1], *bounds_p["bo"])
    ge = sig_map(xi_p[2], *bounds_p["ge"])
    return ao, bo, ge

def param_jacobian(xi_p, S_avg, U_avg, bounds_p, as_f, bs_f):
    """
    Block-diagonal parameter Jacobian Hp.
    Maps [xi_ao, xi_bo, xi_ge] -> [Tz_resid, wz_resid, cz_resid].
    Channel separation ensures no cross-parameter competition degeneracies.
    """
    Tz, wz, cz = S_avg
    To, wo, co, Tsa, wsa, csa, msa = U_avg

    dAo = sig_jac(xi_p[0], *bounds_p["ao"])
    dBo = sig_jac(xi_p[1], *bounds_p["bo"])
    dGe = sig_jac(xi_p[2], *bounds_p["ge"])

    win = DT * PARAM_UPDATE_STEP

    H_p = np.zeros((3, 3))
    H_p[0, 0] = (To - Tz) * dAo * win     # Tz residual <-> xi_ao
    H_p[1, 1] = (wo - wz) * dBo * win     # wz residual <-> xi_bo
    H_p[2, 2] = dGe * win                 # cz residual <-> xi_ge
    return H_p

# ══════════════════════════════════════════════════════════════════════════════
# MAIN DUAL EKF RUNNER FOR TEST RIG DATASET
# ══════════════════════════════════════════════════════════════════════════════
def run_dual_ekf_test_rig(df):
    N = len(df)

    # Sensor Barometric Pressure
    if "outside_p" in df.columns and df["outside_p"].dropna().mean() > 500:
        P_live_arr = df["outside_p"].fillna(1013.25).values * 100.0
    elif "room_1_p" in df.columns and df["room_1_p"].dropna().mean() > 500:
        P_live_arr = df["room_1_p"].fillna(1013.25).values * 100.0
    else:
        P_live_arr = np.full(N, 101325.0)

    To  = df["outside_t"].values
    wo  = np.array([rh_to_w(df["outside_h"].values[i], To[i], P_live_arr[i]) for i in range(N)])
    co  = df["outside_c"].values

    Tsa = df["supply_t"].values
    wsa = np.array([rh_to_w(df["supply_h"].values[i], Tsa[i], P_live_arr[i]) for i in range(N)])
    csa = df["supply_c"].values
    msa = df["m_sa_kgs"].values

    Tz_m  = df["T_z_weighted"].values
    RHz_m = df["RH_z_weighted"].values
    wz_m  = np.array([rh_to_w(RHz_m[i], Tz_m[i], P_live_arr[i]) for i in range(N)])
    cz_m  = df["CO2_z_weighted"].values

    # Fixed physical scaling coefficients
    Cs_f = Cs_nom                   # J/K
    as_f = c_pa / Cs_f              # 1/(kg·s)
    bs_f = 1.0 / M_ROOM             # 1/kg

    # Parameter sigmoid bounds
    UA_lo = UA_nom * 0.7            # ±30% range around nominal UA = 6.0 W/K
    UA_hi = UA_nom * 1.3

    bounds_p = {
        "ao": (UA_lo / Cs_f, UA_hi / Cs_f),      # alpha_o = UA/Cs
        "bo": (1e-7, 5e-4),                       # beta_o = m_inf/M
        "ge": (0.0, 5.0),                         # gamma_e [ppm/s], max ~6.5 persons
    }

    # Parameter filter initialization
    xi_p = np.array([
        xi_from_theta(UA_nom / Cs_f, *bounds_p["ao"]),
        xi_from_theta(3e-6, *bounds_p["bo"]),
        xi_from_theta(G_CO2_PER_PERSON * 0.5, *bounds_p["ge"]), # Start with 0.5 person equiv to avoid zero derivative
    ])
    Pp = np.diag([4.0, 2.0, 4.0])

    Qp = np.diag([
        1e-4,     # xi_ao process noise
        5e-4,     # xi_bo process noise
        1e-2,     # xi_ge process noise
    ])

    Rp = np.diag([
        0.5,      # Tz residual variance
        1e-5,     # wz residual variance
        50.0,     # cz residual variance
    ])

    # State filter initialization
    S  = np.array([Tz_m[0], wz_m[0], cz_m[0]])
    Ps = np.diag([0.05**2, 0.0002**2, 2.5**2])

    Qs = np.diag([1e-4, 1e-9, 1.0])       # Fixed state model process noise
    H_s = np.eye(3)
    Rs = np.diag([0.0025, 4e-8, 10000.0])  # Tz: tight, wz: tight, cz: very weak (Rs=10000)

    # Storage arrays
    Tz_est  = np.zeros(N)
    wz_est  = np.zeros(N)
    cz_est  = np.zeros(N)
    ao_hist = np.zeros(N)
    bo_hist = np.zeros(N)
    ge_hist = np.zeros(N)
    innov_window = []

    for k in range(N):
        ao_k, bo_k, ge_k = params_from_xi(xi_p, bounds_p)
        theta_k = (ao_k, as_f, bo_k, ge_k, bs_f)
        U_k = (To[k], wo[k], co[k], Tsa[k], wsa[k], csa[k], msa[k])

        # ── EKF_STATES: RK4 Prediction ───────────────────────────────────────
        S_pred  = state_rk4(S, U_k, DT, theta_k)
        J_s     = state_jacobian(S, U_k, theta_k)
        Fs      = np.eye(3) + J_s * DT
        Ps_pred = Fs @ Ps @ Fs.T + Qs * DT
        Ps_pred = 0.5 * (Ps_pred + Ps_pred.T)

        # ── EKF_STATES: Measurement Update ───────────────────────────────────
        Z_3    = np.array([Tz_m[k], wz_m[k], cz_m[k]])
        cz_err = Z_3[2] - S_pred[2]      # Raw CO2 prediction error BEFORE update
        y_3    = Z_3 - H_s @ S_pred
        S_inn  = H_s @ Ps_pred @ H_s.T + Rs
        K_s    = np.linalg.solve(S_inn.T, (Ps_pred @ H_s.T).T).T
        S      = S_pred + K_s @ y_3
        Ps     = (np.eye(3) - K_s @ H_s) @ Ps_pred
        Ps     = 0.5 * (Ps + Ps.T)

        innov_3 = np.array([y_3[0], y_3[1], cz_err])
        innov_window.append(innov_3)

        # ── EKF_PARAMS: Parameter Update (every PARAM_UPDATE_STEP = 5 min) ──
        if len(innov_window) >= PARAM_UPDATE_STEP:
            innov_arr = np.array(innov_window)
            cz_vals   = innov_arr[:, 2]
            cz_signmax = cz_vals[np.argmax(np.abs(cz_vals))]   # Signed max abs CO2 error

            innov_batch = np.array([
                innov_arr[:, 0].mean(),
                innov_arr[:, 1].mean(),
                cz_signmax
            ])
            innov_window = []

            S_avg = S.copy()
            U_avg = U_k

            Pp = Pp + Qp * (DT * PARAM_UPDATE_STEP)
            Pp = 0.5 * (Pp + Pp.T)

            H_p = param_jacobian(xi_p, S_avg, U_avg, bounds_p, as_f, bs_f)
            S_p = H_p @ Pp @ H_p.T + Rp
            try:
                K_p = np.linalg.solve(S_p.T, (Pp @ H_p.T).T).T
            except np.linalg.LinAlgError:
                K_p = np.zeros((3, 3))

            delta_xi = K_p @ innov_batch
            delta_xi = np.clip(delta_xi, -0.5, 0.5)

            # Freeze beta_o upon convergence
            BO_FREEZE_THRESH = 0.01
            if Pp[1, 1] < BO_FREEZE_THRESH:
                delta_xi[1] = 0.0
                Pp[1, :] = 0.0
                Pp[:, 1] = 0.0
                Pp[1, 1] = 1e-12

            xi_p = xi_p + delta_xi

            Pp = (np.eye(3) - K_p @ H_p) @ Pp
            Pp = 0.5 * (Pp + Pp.T)
            eigvals = np.linalg.eigvalsh(Pp)
            if np.any(eigvals < 0):
                Pp += (-eigvals.min() + 1e-6) * np.eye(3)

        ao_k2, bo_k2, ge_k2 = params_from_xi(xi_p, bounds_p)
        Tz_est[k]  = S[0]
        wz_est[k]  = S[1]
        cz_est[k]  = S[2]
        ao_hist[k] = ao_k2
        bo_hist[k] = bo_k2
        ge_hist[k] = ge_k2

    # Derived physical properties
    UA_hist    = ao_hist * Cs_f
    N_occ_est  = ge_hist / G_CO2_PER_PERSON
    m_inf_hist = bo_hist * M_ROOM * 1000.0   # [g/s]
    RHz_est    = np.array([w_to_rh(wz_est[i], Tz_est[i], P_live_arr[i]) for i in range(N)])

    return (Tz_est, wz_est, cz_est, RHz_est,
            ao_hist, bo_hist, ge_hist, UA_hist, N_occ_est, m_inf_hist,
            Tz_m, RHz_m, cz_m, P_live_arr)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN PLOTTING AND EXECUTION LOOP
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    df_sched4 = pd.read_csv(os.path.join(DAY4_DIR, "occ_schedule_day_4.csv"))
    df_sched4.columns = [c.strip() for c in df_sched4.columns]

    d3_files = [(3, f) for f in os.listdir(DAY3_CLEAN_DIR) if f.endswith("_cleaned.csv")]
    d4_files = [(4, f) for f in os.listdir(DAY4_CLEAN_DIR) if f.endswith("_cleaned.csv")]
    all_runs = d3_files + d4_files

    print(f"\n=================================================================")
    print(f"  Dual EKF v3 — Experimental Test Rig (Day 3 & Day 4)")
    print(f"  Running on {len(all_runs)} datasets...")
    print(f"=================================================================\n")

    for day, fname in all_runs:
        folder = DAY3_CLEAN_DIR if day == 3 else DAY4_CLEAN_DIR
        df = pd.read_csv(os.path.join(folder, fname))
        base_name = fname.replace("_cleaned.csv", "")
        raw_filename = f"{base_name}.csv"

        print(f"Running Dual EKF for Day {day}: {base_name}...")
        res = run_dual_ekf_test_rig(df)
        (Tz_est, wz_est, cz_est, RHz_est,
         ao_hist, bo_hist, ge_hist, UA_hist, N_occ_est, m_inf_hist,
         Tz_m, RHz_m, cz_m, P_live) = res

        ts = pd.to_datetime(df["timestamp"])
        t_min = (ts - ts.iloc[0]).dt.total_seconds() / 60.0

        # Ground Truth Occupancy
        if day == 4:
            n_gt = get_day4_occupancy_series(df, raw_filename, df_sched4)
        else:
            n_gt = get_day3_occupancy_series(df)

        n_disc = np.round(np.clip(N_occ_est, 0.0, None))

        # ── PLOT 1: 3-SUBPLOT ENVIRONMENTAL STATES ───────────────────────────
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

        ax1.plot(t_min, Tz_m, "r--", alpha=0.6, label="Measured Tz")
        ax1.plot(t_min, Tz_est, "b-", lw=1.8, label="Dual-EKF Estimated Tz")
        ax1.set_ylabel("Temperature (°C)", fontsize=10)
        ax1.set_title(f"{base_name} — Dual-EKF Environmental State Estimations", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right", fontsize=8)
        ax1.grid(True, alpha=0.3)

        ax2.plot(t_min, RHz_m, "orange", linestyle="--", alpha=0.6, label="Measured RHz")
        ax2.plot(t_min, RHz_est, "teal", linestyle="-", lw=1.8, label="Dual-EKF Estimated RHz")
        ax2.set_ylabel("Relative Humidity (%)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, alpha=0.3)

        ax3.plot(t_min, cz_m, "g--", alpha=0.6, label="Measured CO2z")
        ax3.plot(t_min, cz_est, "k-", lw=1.8, label="Dual-EKF Estimated CO2z")
        ax3.set_ylabel("CO2 Concentration (ppm)", fontsize=10)
        ax3.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax3.legend(loc="upper right", fontsize=8)
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(os.path.join(OUT_DIR, f"{base_name}_DualEKF_States_3Subplots.png"), dpi=150)
        plt.close()

        # ── PLOT 2: OCCUPANCY ESTIMATION VS GROUND TRUTH ─────────────────────
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(t_min, N_occ_est, "m-", lw=1.8, label="Continuous Dual-EKF Estimated Occupants (N)")
        ax.step(t_min, n_disc, "c-", where="post", lw=2.0, alpha=0.9, label="Thresholded Integer Occupants (Discretized)")
        ax.step(t_min, n_gt, "k--", where="post", alpha=0.8, lw=1.8, label="Ground Truth Occupancy Schedule")

        ax.set_ylim(-0.5, max(4.0, np.max(n_gt) + 1.5))
        ax.set_ylabel("Occupant Count (person)", fontsize=11)
        ax.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax.set_title(f"{base_name} — Dual-EKF Recovered Occupancy vs Ground Truth", fontsize=12, fontweight="bold")
        ax.legend(loc="upper right", fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(OUT_DIR, f"{base_name}_DualEKF_Occupancy_vs_GroundTruth.png"), dpi=150)
        plt.close()

        # ── PLOT 3: ESTIMATED PARAMETERS TRACKING (alpha_o, beta_o, gamma_e) ─
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 9), sharex=True)

        ax1.plot(t_min, ao_hist, color="purple", lw=1.5, label=r"$\alpha_o = UA/C_s$ [1/s]")
        ax1.axhline(UA_nom / Cs_nom, color="green", linestyle="--", label=f"Nominal α_o = {UA_nom/Cs_nom:.2e}")
        ax1.set_ylabel(r"$\alpha_o$ [1/s]", fontsize=10)
        ax1.set_title(f"{base_name} — Dual-EKF Parameter Estimates Tracking", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right", fontsize=8)
        ax1.grid(True, alpha=0.3)

        ax2.plot(t_min, bo_hist, color="darkgreen", lw=1.5, label=r"$\beta_o = m_{\text{inf}}/M$ [1/s]")
        ax2.set_ylabel(r"$\beta_o$ [1/s]", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, alpha=0.3)

        ax3.plot(t_min, ge_hist, color="crimson", lw=1.5, label=r"$\gamma_e$ CO2 Generation Rate [ppm/s]")
        ax3.axhline(G_CO2_PER_PERSON, color="k", linestyle=":", label=f"1-Person γ_e = {G_CO2_PER_PERSON:.4f} ppm/s")
        ax3.set_ylabel(r"$\gamma_e$ [ppm/s]", fontsize=10)
        ax3.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax3.legend(loc="upper right", fontsize=8)
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(os.path.join(OUT_DIR, f"{base_name}_DualEKF_Estimated_Parameters.png"), dpi=150)
        plt.close()

        # ── PLOT 4: DERIVED PHYSICAL PARAMETERS (Cs, M, m_inf, UA) ───────────
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

        ax1.axhline(Cs_nom / 1000.0, color="blue", lw=2, label=f"Cs FIXED = {Cs_nom/1000.0:.1f} kJ/°C (nominal)")
        ax1.axhspan(20.0, 30.0, color="lightgreen", alpha=0.35, label="Expected Physical Range (20.0 - 30.0 kJ/°C)")
        ax1.set_ylabel("Cs (kJ/°C)", fontsize=10)
        ax1.set_title(f"{base_name} — Dual-EKF Derived Physical Parameters", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right", fontsize=8)
        ax1.grid(True, alpha=0.3)

        ax2.axhline(M_ROOM, color="teal", lw=2, label=f"Zone Air Mass M FIXED = {M_ROOM:.2f} kg (nominal)")
        ax2.axhspan(6.70, 7.10, color="lightgreen", alpha=0.35, label="Expected Physical Range (6.70 - 7.10 kg)")
        ax2.set_ylabel("Air Mass M (kg)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, alpha=0.3)

        ax3.plot(t_min, m_inf_hist, "purple", lw=1.8, label="Estimated Infiltration Rate m_inf (g/s)")
        ax3.axhspan(0.00, 0.10, color="lightgreen", alpha=0.35, label="Expected Physical Range (0.00 - 0.10 g/s)")
        ax3.set_ylabel("m_inf (g/s)", fontsize=10)
        ax3.legend(loc="upper right", fontsize=8)
        ax3.grid(True, alpha=0.3)

        ax4.plot(t_min, UA_hist, "darkred", lw=1.8, label="Estimated Envelope Conductance UA (W/°C)")
        ax4.axhline(UA_nom, color="k", linestyle="--", label=f"Nominal UA = {UA_nom:.1f} W/°C")
        ax4.axhspan(5.50, 6.50, color="lightgreen", alpha=0.35, label="Expected Physical Range (5.50 - 6.50 W/°C)")
        ax4.set_ylabel("UA (W/°C)", fontsize=10)
        ax4.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax4.legend(loc="upper right", fontsize=8)
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(os.path.join(OUT_DIR, f"{base_name}_DualEKF_Derived_Physical_Parameters.png"), dpi=150)
        plt.close()

        rmse_Tz = np.sqrt(np.mean((Tz_m - Tz_est)**2))
        rmse_cz = np.sqrt(np.mean((cz_m - cz_est)**2))

        print(f"  RMSE Tz = {rmse_Tz:.3f} °C, RMSE CO2 = {rmse_cz:.1f} ppm | Saved 4 PNG plots for {base_name}")

    print("\nALL DUAL EKF RUNS FOR TEST RIG COMPLETED SUCCESSFULLY.")
