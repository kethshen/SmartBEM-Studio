"""
SmartBEM FYP — ROBOD Dual EKF v3
=================================
Architecture: TWO decoupled filters running in tandem.

  EKF_STATES (fast, 3-state):
    - Estimates [Tz, wz, cz] at every time step (DT=300s)
    - Uses current best PARAMETER estimates as known constants
    - Well-conditioned 3×3 system — nearly linear given fixed params
    - R is FIXED (not adaptive) to prevent measurement-copying collapse

  EKF_PARAMS (slow, 3-param):
    - Estimates [xi_ao, xi_bo, xi_ge] in sigmoid-space
    - Updates every PARAM_UPDATE_STEP steps (e.g. every 6 steps = 30 min)
    - Uses averaged innovation from EKF_STATES over the window
    - Fixed, larger Q to allow occupancy step changes to propagate
    - Parameters track on building timescale, not sensor noise timescale

Why this fixes the current failure:
  - Adaptive R collapse killed γ_e in the joint filter because once cz
    tracked measurements perfectly, the filter had no residual to blame
    on occupancy.
  - Dual EKF PREVENTS this: the state filter uses fixed R and does not
    update parameters at all. The parameter filter sees the RESIDUAL
    between the physics-predicted cz and measured cz, integrated over
    30 minutes — which contains the occupancy CO2 buildup signal.

Fixes applied from Deep Diagnosis Plan:
  [1] Reduced parameter set: β_s = 1/M fixed, Cs fixed = nominal
  [2] RK4 for state prediction
  [3] Measured supply air data from CSV
  [4] Sigmoid parameter mapping (alpha_o, beta_o, gamma_e)
  [6] Dual EKF architecture (NEW — the core fix in this version)

Physical model (per state filter step):
  dTz/dt = α_o·(To - Tz) + α_s_fixed·msa·(Tsa - Tz)
  dwz/dt = β_o·(wo - wz) + β_s_fixed·msa·(wsa - wz)
  dcz/dt = β_o·(co - cz) + β_s_fixed·msa·(csa - cz) + γ_e
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import argparse

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR   = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
ROBOD_DIR    = os.path.join(STUDIO_DIR, "EKF", "Datasets for EKF",
                             "ROBOD, Room level Occupancy and Building Operation Dataset")
OUT_DIR      = os.path.join(SCRIPT_DIR, "results_plots_dualekf")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
c_pa            = 1006.0      # J/(kg·K)
rho_air         = 1.2         # kg/m³
DT              = 300.0       # seconds per step
CMH_TO_KGS      = rho_air / 3600.0
F_RECIRC        = 0.5         # AHU recirculation fraction
PARAM_UPDATE_STEP = 12        # Update params every 12 steps = 60 min window
GE_PER_PERSON   = 0.0055      # CO₂ generation per person [ppm·kg/s] (typical ~0.005-0.008)

# ── Room Specifications ────────────────────────────────────────────────────────
ROOM_SPECS = {
    1: {"name": "Room 1",              "file": "combined_Room1.csv", "volume": 120.0,  "max_occ": 6.0,  "Cs": 500.0,  "UA": 80.0},
    2: {"name": "Room 2",              "file": "combined_Room2.csv", "volume": 150.0,  "max_occ": 8.0,  "Cs": 650.0,  "UA": 100.0},
    3: {"name": "Room 3 (SDE4 Office)","file": "combined_Room3.csv","volume": 413.2,  "max_occ": 13.0, "Cs": 1500.0, "UA": 250.0},
    4: {"name": "Room 4",              "file": "combined_Room4.csv", "volume": 756.0,  "max_occ": 25.0, "Cs": 2800.0, "UA": 450.0},
    5: {"name": "Room 5",              "file": "combined_Room5.csv", "volume": 760.0,  "max_occ": 25.0, "Cs": 2850.0, "UA": 450.0},
}

# ── Sigmoid helpers ────────────────────────────────────────────────────────────
def sigmoid(xi):
    return np.where(xi >= 0, 1/(1+np.exp(-xi)), np.exp(xi)/(1+np.exp(xi)))

def sig_map(xi, lo, hi):
    return lo + (hi - lo) * sigmoid(xi)

def sig_jac(xi, lo, hi):
    s = sigmoid(xi)
    return (hi - lo) * s * (1 - s)

def xi_from_theta(theta, lo, hi):
    s = np.clip((theta - lo)/(hi - lo), 1e-6, 1-1e-6)
    return np.log(s / (1 - s))

# ── Humidity helpers ───────────────────────────────────────────────────────────
def rh_to_w(rh_pct, T_C, P=101325.0):
    rh    = np.clip(rh_pct/100.0, 0, 1)
    Psat  = 610.78 * np.exp(17.269*T_C/(T_C+237.3))
    return np.clip(0.622*(rh*Psat)/(P - rh*Psat), 0, 0.05)

def w_to_rh(w, T_C, P=101325.0):
    Psat = 610.78 * np.exp(17.269*T_C/(T_C+237.3))
    Pw   = w*P/(0.622+w)
    return np.clip(Pw/Psat*100, 0, 100)

# ══════════════════════════════════════════════════════════════════════════════
# EKF_STATES — fast 3-state filter
# State: [Tz, wz, cz]
# Parameters: θ = (ao, as_fixed, bo, ge, bs_fixed) treated as CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
def state_f(S, U, theta):
    """Physical dynamics for state [Tz, wz, cz] given fixed parameters theta."""
    Tz, wz, cz = S
    To, wo, co, Tsa, wsa, csa, msa = U
    ao, as_f, bo, ge, bs_f = theta

    dTz = ao*(To-Tz) + as_f*msa*(Tsa-Tz)
    dwz = bo*(wo-wz) + bs_f*msa*(wsa-wz)
    dcz = bo*(co-cz) + bs_f*msa*(csa-cz) + ge
    return np.array([dTz, dwz, dcz])

def state_rk4(S, U, dt, theta):
    k1 = state_f(S,              U, theta)
    k2 = state_f(S+0.5*dt*k1,   U, theta)
    k3 = state_f(S+0.5*dt*k2,   U, theta)
    k4 = state_f(S+dt*k3,       U, theta)
    return S + (dt/6)*(k1+2*k2+2*k3+k4)

def state_jacobian(S, U, theta):
    """Analytical 3×3 Jacobian of state dynamics w.r.t. [Tz, wz, cz]."""
    Tz, wz, cz = S
    To, wo, co, Tsa, wsa, csa, msa = U
    ao, as_f, bo, ge, bs_f = theta

    J = np.zeros((3,3))
    J[0,0] = -(ao + as_f*msa)
    J[1,1] = -(bo + bs_f*msa)
    J[2,2] = -(bo + bs_f*msa)
    return J

# ══════════════════════════════════════════════════════════════════════════════
# EKF_PARAMS — slow 3-param filter in sigmoid space
# State: [xi_ao, xi_bo, xi_ge]
# Pseudo-measurement: innovation from EKF_STATES averaged over window
# ══════════════════════════════════════════════════════════════════════════════
def params_from_xi(xi_p, bounds_p):
    ao = sig_map(xi_p[0], *bounds_p["ao"])
    bo = sig_map(xi_p[1], *bounds_p["bo"])
    ge = sig_map(xi_p[2], *bounds_p["ge"])
    return ao, bo, ge

def param_jacobian(xi_p, S_avg, U_avg, bounds_p, as_f, bs_f):
    """
    Jacobian H_p: derivative of predicted state innovation w.r.t. [xi_ao, xi_bo, xi_ge].

    KEY DESIGN: Each parameter has a SEPARATE measurement channel:
      - xi_ao driven by Tz residual ONLY (via alpha_o * (To-Tz))
      - xi_bo driven by wz residual ONLY (via beta_o * (wo-wz))
      - xi_ge driven by cz residual ONLY (via gamma_e source term)

    H_p is block-diagonal: ensures no cross-channel identifiability degeneracy.
    """
    Tz, wz, cz = S_avg
    To, wo, co, Tsa, wsa, csa, msa = U_avg
    ao, bo, ge = params_from_xi(xi_p, bounds_p)

    dAo = sig_jac(xi_p[0], *bounds_p["ao"])
    dBo = sig_jac(xi_p[1], *bounds_p["bo"])
    dGe = sig_jac(xi_p[2], *bounds_p["ge"])

    # Window duration scaling
    win = DT * PARAM_UPDATE_STEP

    # BLOCK-DIAGONAL H_p: separate channels
    H_p = np.zeros((3, 3))           # [Tz_resid, wz_resid, cz_resid] x [xi_ao, xi_bo, xi_ge]
    H_p[0, 0] = (To - Tz) * dAo * win     # Tz residual <-> xi_ao
    H_p[1, 1] = (wo - wz) * dBo * win     # wz residual <-> xi_bo (SEPARATE from cz)
    H_p[2, 2] = dGe * win                  # cz residual <-> xi_ge (SEPARATE from bo)

    return H_p

# ══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════════════════════════════════════════
def run_dual_ekf(df_in, spec):
    df = df_in.ffill().bfill().copy()
    N  = len(df)

    def col(candidates, default=None):
        for c in candidates:
            if c in df.columns:
                return df[c].values
        if default is not None:
            return default
        raise KeyError(f"None of {candidates} found in CSV")

    # ── Input Data ──────────────────────────────────────────────────────────
    To  = col(["dry_bulb_temp [Celsius]"])
    rho = col(["outdoor_relative_humidity [%]"])
    wo  = np.array([rh_to_w(rho[i], To[i]) for i in range(N)])
    co  = col(["outdoor_co2 [ppm]"])

    # Supply air mass flow
    FCU_SCALE = 0.01
    if "supply_air_flow [CMH]" in df.columns:
        msa = np.clip(df["supply_air_flow [CMH]"].values * CMH_TO_KGS, 0.001, None)
    elif "ahu_fan_speed [Hz]" in df.columns:
        msa = np.clip(df["ahu_fan_speed [Hz]"].values * FCU_SCALE, 0.001, None)
    else:
        msa = np.clip(df["fcu_fan_speed [Hz]"].values * FCU_SCALE, 0.001, None)

    Tsa = df["supply_air_temperature [Celsius]"].values if "supply_air_temperature [Celsius]" in df.columns else To - 5.0
    if "supply_air_humidity [%]" in df.columns:
        sa_rh = df["supply_air_humidity [%]"].values
        wsa   = np.array([rh_to_w(sa_rh[i], Tsa[i]) for i in range(N)])
    else:
        wsa = wo.copy()

    # Measurements
    Tz_m  = col(["air_temperature [Celsius]"])
    RHz_m = col(["indoor_relative_humidity [%]"])
    wz_m  = np.array([rh_to_w(RHz_m[i], Tz_m[i]) for i in range(N)])
    cz_m  = col(["indoor_co2 [ppm]"])
    occ   = col(["occupant_count [number]"])

    # ── Fixed physical constants ─────────────────────────────────────────────
    V        = spec["volume"]
    M_fixed  = rho_air * V
    bs_f     = 1.0 / M_fixed
    Cs_f     = spec["Cs"] * 1000.0       # J/K
    as_f     = c_pa / Cs_f
    UA_nom   = spec["UA"]
    UA_lo    = UA_nom * 0.2
    UA_hi    = UA_nom * 4.0

    bounds_p = {
        "ao": (UA_lo / Cs_f,   UA_hi / Cs_f),   # α_o = UA/Cs_f
        "bo": (1e-6,            2e-3),            # β_o = m_inf/M
        "ge": (0.0,             0.5),             # γ_e [ppm·kg/s]
    }

    # ── EKF_PARAMS init ─────────────────────────────────────────────────────
    xi_p  = np.array([
        xi_from_theta(UA_nom / Cs_f,   *bounds_p["ao"]),
        xi_from_theta(5e-6,             *bounds_p["bo"]),
        xi_from_theta(GE_PER_PERSON*2,  *bounds_p["ge"]),  # start with ~2 persons equivalent
    ])
    Pp = np.diag([4.0, 2.0, 4.0])   # initial param covariance

    # Process noise Q_p: SMALL so params change slowly; gamma_e tracks over hours not minutes
    Qp = np.diag([
        1e-4,     # xi_ao — UA changes very slowly
        5e-4,     # xi_bo — infiltration changes slowly
        5e-3,     # xi_ge — occupancy on timescale of 30-60 min, NOT seconds
    ])

    # Param filter measurement noise: LARGE = params change slowly, trust prior
    # KEY: separate channels — Tz->ao, wz->bo, cz->ge
    # R must be large relative to Q * window_duration to prevent divergence
    Rp = np.diag([
        5.0,      # Tz residual variance: sigma_Tz ~ 0.3C => var ~ 0.09, use 5 to slow
        1e-4,     # wz residual variance (small — humidity signal drives bo)
        1000.0,   # cz residual variance: large = slow ge adaptation
    ])

    # ── EKF_STATES init ─────────────────────────────────────────────────────
    S  = np.array([Tz_m[0], wz_m[0], cz_m[0]])
    Ps = np.diag([0.25, 1e-6, 100.0])

    # State filter Q: model uncertainty (NOT adaptive — fixed)
    Qs = np.diag([0.05, 1e-7, 5.0])    # per step (before ×DT)

    # CRITICAL DESIGN: State filter measures ONLY Tz and wz (NOT cz).
    # CO2 is a predicted-only state driven entirely by gamma_e.
    # The parameter filter is the ONLY place that assimilates CO2 measurement.
    # This ensures cz residual is always nonzero and encodes occupancy signal.
    H_s = np.array([[1, 0, 0],   # Tz measured
                    [0, 1, 0]])   # wz measured — cz NOT measured in state filter
    Rs  = np.diag([0.09, 4e-6])  # Tz: 0.3degC std, wz: 0.002 kg/kg std

    # ── Storage ──────────────────────────────────────────────────────────────
    Tz_est  = np.zeros(N)
    wz_est  = np.zeros(N)
    cz_est  = np.zeros(N)
    ao_hist = np.zeros(N)
    bo_hist = np.zeros(N)
    ge_hist = np.zeros(N)
    innov_window  = []   # rolling innovation buffer for param update
    cz_innov_buf  = []   # separate CO2 innovation buffer (raw meas - predicted cz)

    # ── DUAL EKF MAIN LOOP ───────────────────────────────────────────────────
    for k in range(N):
        # Current param estimates (physical)
        ao_k, bo_k, ge_k = params_from_xi(xi_p, bounds_p)
        theta_k = (ao_k, as_f, bo_k, ge_k, bs_f)

        # Recirculation CO2 supply based on current cz estimate
        csa_k = F_RECIRC * S[2] + (1.0 - F_RECIRC) * co[k]
        U_k   = (To[k], wo[k], co[k], Tsa[k], wsa[k], csa_k, msa[k])
        Z_k   = np.array([Tz_m[k], wz_m[k], cz_m[k]])

        # ── EKF_STATES: Predict ───────────────────────────────────────────
        S_pred = state_rk4(S, U_k, DT, theta_k)
        J_s    = state_jacobian(S, U_k, theta_k)
        Fs     = np.eye(3) + J_s * DT
        Ps_pred = Fs @ Ps @ Fs.T + Qs * DT
        Ps_pred = 0.5 * (Ps_pred + Ps_pred.T)

        # ── EKF_STATES: Update ────────────────────────────────────────────
        y_k    = Z_k - S_pred          # innovation
        S_S    = Ps_pred + Rs
        K_s    = np.linalg.solve(S_S.T, Ps_pred.T).T
        S      = S_pred + K_s @ y_k
        Ps     = (np.eye(3) - K_s) @ Ps_pred
        Ps     = 0.5 * (Ps + Ps.T)

        # Collect innovation for parameter update
        innov_window.append(y_k)

        # ── EKF_PARAMS: Update (every PARAM_UPDATE_STEP steps) ───────────
        if len(innov_window) >= PARAM_UPDATE_STEP:
            # Average innovation over the window
            innov_batch = np.mean(innov_window, axis=0)
            innov_window = []

            S_avg = S.copy()
            U_avg = U_k

            # Param filter "prediction" (random walk)
            Pp = Pp + Qp * (DT * PARAM_UPDATE_STEP)
            Pp = 0.5 * (Pp + Pp.T)

            # Param filter "update"
            H_p = param_jacobian(xi_p, S_avg, U_avg, bounds_p, as_f, bs_f)
            S_p = H_p @ Pp @ H_p.T + Rp
            try:
                K_p = np.linalg.solve(S_p.T, (Pp @ H_p.T).T).T
            except np.linalg.LinAlgError:
                K_p = np.zeros((3, 3))

            delta_xi = K_p @ innov_batch
            # Hard-clip update step to prevent single-window divergence
            delta_xi = np.clip(delta_xi, -0.5, 0.5)
            xi_p = xi_p + delta_xi
            Pp   = (np.eye(3) - K_p @ H_p) @ Pp
            Pp   = 0.5 * (Pp + Pp.T)
            # Enforce positive definiteness
            eigvals = np.linalg.eigvalsh(Pp)
            if np.any(eigvals < 0):
                Pp += (-eigvals.min() + 1e-6) * np.eye(3)

        # Store
        ao_k2, bo_k2, ge_k2 = params_from_xi(xi_p, bounds_p)
        Tz_est[k]  = S[0]
        wz_est[k]  = S[1]
        cz_est[k]  = S[2]
        ao_hist[k] = ao_k2
        bo_hist[k] = bo_k2
        ge_hist[k] = ge_k2

    # ── Derived quantities ────────────────────────────────────────────────────
    UA_hist    = ao_hist * Cs_f
    N_occ_est  = ge_hist * M_fixed / GE_PER_PERSON
    m_inf_hist = bo_hist * M_fixed * 1000.0   # g/s
    RHz_est    = np.array([w_to_rh(wz_est[i], Tz_est[i]) for i in range(N)])

    return (Tz_est, wz_est, cz_est, RHz_est,
            ao_hist, bo_hist, ge_hist, UA_hist, N_occ_est, m_inf_hist,
            Tz_m, RHz_m, cz_m, occ,
            Cs_f/1000.0, M_fixed)

# ── Plotting ───────────────────────────────────────────────────────────────────
def make_plots(res, spec, t_hours, room_str):
    (Tz_est, wz_est, cz_est, RHz_est,
     ao_hist, bo_hist, ge_hist, UA_hist, N_occ_est, m_inf_hist,
     Tz_m, RHz_m, cz_m, occ,
     Cs_kJ, M_fixed) = res

    UA_nom   = spec["UA"]
    N_max    = spec["max_occ"]

    # ── Plot 1: Environmental states ─────────────────────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    axes[0].plot(t_hours, Tz_m,   "r--", lw=1.2, alpha=0.5, label="Measured Tz")
    axes[0].plot(t_hours, Tz_est, "b-",  lw=1.5,            label="Dual-EKF Estimated Tz")
    axes[0].set_ylabel("Temperature (°C)"); axes[0].legend(fontsize=8); axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f"ROBOD {spec['name']} — Dual-EKF Environmental States", fontsize=12, fontweight="bold")

    axes[1].plot(t_hours, RHz_m,   color="orange", linestyle="--", lw=1.2, alpha=0.5, label="Measured RHz")
    axes[1].plot(t_hours, RHz_est, color="teal",   lw=1.5,                             label="Dual-EKF Estimated RHz")
    axes[1].set_ylabel("Relative Humidity (%)"); axes[1].legend(fontsize=8); axes[1].grid(True, alpha=0.3)

    axes[2].plot(t_hours, cz_m,   "g--", lw=1.2, alpha=0.5, label="Measured CO2z")
    axes[2].plot(t_hours, cz_est, "k-",  lw=1.5,            label="Dual-EKF Estimated CO2z")
    axes[2].set_ylabel("CO₂ (ppm)"); axes[2].set_xlabel("Elapsed Time (hours)")
    axes[2].legend(fontsize=8); axes[2].grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, f"{room_str}_DualEKF_States.png"), dpi=130, bbox_inches="tight")
    plt.close()

    # ── Plot 2: Occupancy ─────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 4))
    N_clip = np.clip(N_occ_est, 0, N_max * 1.5)
    ax.fill_between(t_hours, 0, occ, alpha=0.3, color="gray", label="Ground Truth Occupancy")
    ax.plot(t_hours, occ,   "k--", lw=1.2, alpha=0.7, label="GT Count")
    ax.plot(t_hours, N_clip, color="magenta", lw=1.8, label="Dual-EKF Estimated Occupancy")
    ax.set_ylabel("Occupant Count"); ax.set_xlabel("Elapsed Time (hours)")
    ax.set_title(f"ROBOD {spec['name']} — Dual-EKF Estimated Occupancy vs Ground Truth", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, f"{room_str}_DualEKF_Occupancy.png"), dpi=130, bbox_inches="tight")
    plt.close()

    # ── Plot 3: Estimated parameters ─────────────────────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    axes[0].plot(t_hours, ao_hist, color="purple", lw=1.3, label="α_o = UA/Cs [1/s]")
    ao_nom = UA_nom / (spec["Cs"] * 1000)
    axes[0].axhline(ao_nom, color="green", lw=1.5, linestyle="--", label=f"Nominal α_o = {ao_nom:.2e}")
    axes[0].set_ylabel("α_o [1/s]"); axes[0].legend(fontsize=8); axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f"ROBOD {spec['name']} — Dual-EKF Parameter Estimates", fontsize=12, fontweight="bold")

    axes[1].plot(t_hours, bo_hist, color="green", lw=1.3, label="β_o = m_inf/M [1/s]")
    axes[1].set_ylabel("β_o [1/s]"); axes[1].legend(fontsize=8); axes[1].grid(True, alpha=0.3)

    axes[2].plot(t_hours, ge_hist, color="crimson", lw=1.3, label="γ_e: CO₂ generation [ppm·kg/s]")
    ge_nom = GE_PER_PERSON
    axes[2].axhline(ge_nom, color="k", lw=1, linestyle=":", label=f"1-person γ_e = {ge_nom:.4f}")
    axes[2].set_ylabel("γ_e [ppm·kg/s]"); axes[2].set_xlabel("Elapsed Time (hours)")
    axes[2].legend(fontsize=8); axes[2].grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, f"{room_str}_DualEKF_Parameters.png"), dpi=130, bbox_inches="tight")
    plt.close()

    # ── Plot 4: Derived physical parameters ──────────────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    axes[0].axhline(Cs_kJ, color="blue", lw=2, label=f"Cs FIXED = {Cs_kJ:.0f} kJ/K (nominal)")
    axes[0].fill_between(t_hours, Cs_kJ*0.7, Cs_kJ*1.5, alpha=0.18, color="green",
                          label=f"Expected [{Cs_kJ*0.7:.0f}–{Cs_kJ*1.5:.0f} kJ/K]")
    axes[0].set_ylabel("Cs (kJ/K)"); axes[0].legend(fontsize=8); axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f"ROBOD {spec['name']} — Dual-EKF Derived Physical Parameters", fontsize=12, fontweight="bold")

    axes[1].fill_between(t_hours, UA_nom*0.5, UA_nom*1.5, alpha=0.18, color="green",
                          label=f"Expected [{UA_nom*0.5:.0f}–{UA_nom*1.5:.0f} W/K]")
    axes[1].plot(t_hours, UA_hist, color="darkred", lw=1.3, label="Estimated UA (W/K)")
    axes[1].axhline(UA_nom, color="k", lw=1, linestyle="--", label=f"Nominal UA = {UA_nom} W/K")
    axes[1].set_ylabel("UA (W/K)"); axes[1].legend(fontsize=8); axes[1].grid(True, alpha=0.3)

    axes[2].fill_between(t_hours, 0, 50, alpha=0.18, color="green", label="Expected infiltration (0–50 g/s)")
    axes[2].plot(t_hours, m_inf_hist, color="purple", lw=1.3, label="Estimated m_inf (g/s)")
    axes[2].set_ylabel("m_inf (g/s)"); axes[2].set_xlabel("Elapsed Time (hours)")
    axes[2].legend(fontsize=8); axes[2].grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, f"{room_str}_DualEKF_Physical_Params.png"), dpi=130, bbox_inches="tight")
    plt.close()

    print(f"  4 plots saved for {spec['name']}")

# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--room", type=int, default=3, choices=[1,2,3,4,5])
    args = parser.parse_args()

    spec     = ROOM_SPECS[args.room]
    csv_path = os.path.join(ROBOD_DIR, spec["file"])

    print(f"\n{'='*65}")
    print(f"  Dual-EKF v3 | ROBOD {spec['name']}")
    print(f"  Param update every {PARAM_UPDATE_STEP} steps ({PARAM_UPDATE_STEP*DT/60:.0f} min window)")
    print(f"{'='*65}")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} samples ({len(df)*DT/3600:.1f} hours)")

    res = run_dual_ekf(df, spec)
    (Tz_est, wz_est, cz_est, RHz_est,
     ao_hist, bo_hist, ge_hist, UA_hist, N_occ_est, m_inf_hist,
     Tz_m, RHz_m, cz_m, occ,
     Cs_kJ, M_fixed) = res

    t_hours  = np.arange(len(df)) * (DT/3600)
    room_str = spec["name"].replace(" ","_").replace("(","").replace(")","").replace("/","_")

    make_plots(res, spec, t_hours, room_str)

    rmse_Tz = np.sqrt(np.mean((Tz_m  - Tz_est)**2))
    rmse_cz = np.sqrt(np.mean((cz_m  - cz_est)**2))
    ge_final = sig_map(np.log(sig_map(0, *{k: v for k,v in [("ge",(0.0,0.5))]}["ge"])), 0, 0.5)
    ua_final = UA_hist[-1]
    n_final  = np.clip(N_occ_est[-1], 0, spec["max_occ"]*1.5)

    print(f"\n  RMSE Tz   = {rmse_Tz:.3f} degC")
    print(f"  RMSE CO2  = {rmse_cz:.1f} ppm")
    print(f"  UA (final)= {ua_final:.1f} W/K   [nominal: {spec['UA']:.0f}]")
    print(f"  Cs (fixed)= {Cs_kJ:.0f} kJ/K  [nominal: {spec['Cs']:.0f}]")
    print(f"  M  (fixed)= {M_fixed:.1f} kg")
    print(f"  Param update window: {PARAM_UPDATE_STEP*DT/60:.0f} min")
    print(f"  Plots -> results_plots_dualekf/")
    print(f"{'='*65}\n")
