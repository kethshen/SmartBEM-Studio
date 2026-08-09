"""
SmartBEM FYP — ROBOD Dataset 7-State EKF Runner (robod_ekf)  v2.0
==================================================================
Implements the 5 structural fixes from the Deep Diagnosis Plan:

  FIX 1 — Reduced 7-state identifiable vector
           Removed alpha_e, beta_e (bias absorbers).
           Fixed beta_s = 1/M (known room air mass — NOT estimated).
           Estimated: [alpha_o, alpha_s, beta_o, gamma_e, Tz, wz, cz]

  FIX 2 — RK4 (4th-order Runge-Kutta) integration
           Replaces unstable Euler forward X_pred = X + f*DT.
           Prevents F_k eigenvalue going negative at large DT.

  FIX 3 — Correct supply air inputs
           Uses measured supply_air_flow [CMH] and supply_air_humidity [%]
           directly from ROBOD CSV (no assumptions).
           CO2 supply uses recirculation blending model:
             csa = f_recirc * cz + (1 - f_recirc) * co  [f_recirc = 0.5]

  FIX 4 — Sigmoid parameter mapping for ALL physical parameters
           Replaces np.clip() post-update with unconstrained xi states
           mapped to physical ranges via sigmoid.
           Eliminates covariance-state inconsistency that causes oscillations.

  FIX 5 — Innovation-based Adaptive R (simplified Sage-Husa)
           R is updated online using the innovation sequence with
           a forgetting factor (alpha = 0.98), ensuring the filter
           self-calibrates to actual data noise statistics.

Generates 4 PNG plots per room in robod_ekf/results_plots/.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import sys
import argparse

# ── Paths & Setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR   = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
ROBOD_DIR    = os.path.join(STUDIO_DIR, "EKF", "Datasets for EKF",
                             "ROBOD, Room level Occupancy and Building Operation Dataset")
OUT_PLOT_DIR = os.path.join(SCRIPT_DIR, "results_plots")
os.makedirs(OUT_PLOT_DIR, exist_ok=True)

# ── Physical Constants ─────────────────────────────────────────────────────────
c_pa          = 1006.0    # Specific heat of dry air [J/(kg·K)]
rho_air       = 1.2       # Dry air density [kg/m³]
DT            = 300.0     # 5-minute sampling interval [seconds]
CMH_TO_KGS    = rho_air / 3600.0  # [CMH] → [kg/s]: ρ × 1/3600
F_RECIRC      = 0.5       # AHU recirculation fraction (50% indoor / 50% fresh)

# ── Room Specifications (official NUS ROBOD room_descriptions) ─────────────────
ROOM_SPECS = {
    1: {"name": "Room 1",             "file": "combined_Room1.csv", "volume": 120.0,  "max_occ": 6.0,  "Cs": 500.0,  "UA": 80.0},
    2: {"name": "Room 2",             "file": "combined_Room2.csv", "volume": 150.0,  "max_occ": 8.0,  "Cs": 650.0,  "UA": 100.0},
    3: {"name": "Room 3 (SDE4 Office)","file": "combined_Room3.csv","volume": 413.2,  "max_occ": 13.0, "Cs": 1500.0, "UA": 250.0},
    4: {"name": "Room 4",             "file": "combined_Room4.csv", "volume": 756.0,  "max_occ": 25.0, "Cs": 2800.0, "UA": 450.0},
    5: {"name": "Room 5",             "file": "combined_Room5.csv", "volume": 760.0,  "max_occ": 25.0, "Cs": 2850.0, "UA": 450.0},
}

# ── FIX 1: 6-State Vector Indices (Cs fixed to nominal — only UA estimated) ───
# States: [xi_ao, xi_bo, xi_ge, Tz, wz, cz]
# xi_* are unconstrained sigmoid-space variables (FIX 4)
# alpha_s = c_pa / Cs_fixed is NOT estimated — Cs is fixed to nominal
I_xi_ao = 0   # unconstrained surrogate for alpha_o = UA/Cs_fixed
I_xi_bo = 1   # unconstrained surrogate for beta_o = m_inf/M
I_xi_ge = 2   # unconstrained surrogate for gamma_e (CO2 generation rate)
I_Tz    = 3   # Zone temperature [°C]
I_wz    = 4   # Zone humidity ratio [kg_w/kg_a]
I_cz    = 5   # Zone CO2 concentration [ppm]
N_STATES = 6

# ── FIX 4: Sigmoid Mapping Helpers ────────────────────────────────────────────
def sigmoid(xi):
    """Numerically stable sigmoid."""
    return np.where(xi >= 0,
                    1.0 / (1.0 + np.exp(-xi)),
                    np.exp(xi) / (1.0 + np.exp(xi)))

def sigmoid_map(xi, lo, hi):
    """Map unconstrained xi ∈ (-∞,+∞) → physical θ ∈ (lo, hi)."""
    return lo + (hi - lo) * sigmoid(xi)

def sigmoid_jac_scalar(xi, lo, hi):
    """Jacobian dθ/dxi for sigmoid mapping (scalar)."""
    s = sigmoid(xi)
    return (hi - lo) * s * (1.0 - s)

def get_physical_params(X, bounds, as_fixed):
    """Extract physical parameters from sigmoid-space state vector.
    as_fixed = c_pa/Cs_fixed is a constant (not estimated)."""
    ao  = sigmoid_map(X[I_xi_ao], *bounds["ao"])
    bo  = sigmoid_map(X[I_xi_bo], *bounds["bo"])
    ge  = sigmoid_map(X[I_xi_ge], *bounds["ge"])
    return ao, as_fixed, bo, ge

# ── Moisture / Humidity Utilities ─────────────────────────────────────────────
def rh_to_humidity_ratio(rh_pct, T_C, P_atm=101325.0):
    rh    = np.clip(rh_pct / 100.0, 0.0, 1.0)
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    omega = 0.622 * (rh * P_sat) / (P_atm - rh * P_sat)
    return np.clip(omega, 0.0, 0.05)

def humidity_ratio_to_rh(omega, T_C, P_atm=101325.0):
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    P_w   = (omega * P_atm) / (0.622 + omega)
    rh    = (P_w / P_sat) * 100.0
    return np.clip(rh, 0.0, 100.0)

# ── FIX 1+4: Dynamics in Sigmoid Space ────────────────────────────────────────
def f_dynamics(X, U, bs_fixed, bounds, as_fixed):
    """
    State derivatives in the 6-state sigmoid-space formulation.
    alpha_s = c_pa/Cs_fixed is FIXED (not estimated).
    bs_fixed = 1/M is FIXED (known room air mass).
    """
    ao, as_, bo, ge = get_physical_params(X, bounds, as_fixed)
    Tz, wz, cz      = X[I_Tz], X[I_wz], X[I_cz]

    To, wo, co, Tsa, wsa, csa, msa = U

    dTz = ao * (To - Tz) + as_ * msa * (Tsa - Tz)
    dwz = bo * (wo - wz) + bs_fixed * msa * (wsa - wz)
    dcz = bo * (co - cz) + bs_fixed * msa * (csa - cz) + ge

    dX         = np.zeros(N_STATES)
    dX[I_Tz]   = dTz
    dX[I_wz]   = dwz
    dX[I_cz]   = dcz
    return dX

# ── FIX 2: RK4 Integration Step ───────────────────────────────────────────────
def rk4_step(X, U, dt, bs_fixed, bounds, as_fixed):
    """4th-order Runge-Kutta integration of state X over interval dt."""
    k1 = f_dynamics(X,              U, bs_fixed, bounds, as_fixed)
    k2 = f_dynamics(X + 0.5*dt*k1, U, bs_fixed, bounds, as_fixed)
    k3 = f_dynamics(X + 0.5*dt*k2, U, bs_fixed, bounds, as_fixed)
    k4 = f_dynamics(X + dt*k3,     U, bs_fixed, bounds, as_fixed)
    return X + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)

# ── FIX 4: Analytical Jacobian in Sigmoid Space ───────────────────────────────
def get_jacobian_F(X, U, bs_fixed, bounds, as_fixed):
    """
    Linearized state transition Jacobian dF/dX (6-state version).
    alpha_s is fixed; only xi_ao, xi_bo, xi_ge are free parameters.
    """
    ao, as_, bo, ge = get_physical_params(X, bounds, as_fixed)
    Tz, wz, cz      = X[I_Tz], X[I_wz], X[I_cz]
    To, wo, co, Tsa, wsa, csa, msa = U

    # Sigmoid Jacobians dθ/dxi at current xi values
    d_ao = sigmoid_jac_scalar(X[I_xi_ao], *bounds["ao"])
    d_bo = sigmoid_jac_scalar(X[I_xi_bo], *bounds["bo"])
    d_ge = sigmoid_jac_scalar(X[I_xi_ge], *bounds["ge"])

    J = np.zeros((N_STATES, N_STATES))

    # ── dTz row ──────────────────────────────────────────────────────────
    J[I_Tz, I_xi_ao] = (To - Tz) * d_ao          # ∂(dTz)/∂xi_ao
    J[I_Tz, I_Tz]    = -(ao + as_ * msa)          # ∂(dTz)/∂Tz

    # ── dwz row ──────────────────────────────────────────────────────────
    J[I_wz, I_xi_bo] = (wo - wz) * d_bo           # ∂(dwz)/∂xi_bo
    J[I_wz, I_wz]    = -(bo + bs_fixed * msa)     # ∂(dwz)/∂wz

    # ── dcz row ──────────────────────────────────────────────────────────
    J[I_cz, I_xi_bo] = (co - cz) * d_bo           # ∂(dcz)/∂xi_bo
    J[I_cz, I_xi_ge] = d_ge                        # ∂(dcz)/∂xi_ge
    J[I_cz, I_cz]    = -(bo + bs_fixed * msa)     # ∂(dcz)/∂cz

    return J

# ── Main EKF Runner ────────────────────────────────────────────────────────────
def run_ekf_on_robod(df_in, room_spec):
    df = df_in.ffill().bfill().copy()
    N  = len(df)

    def get_col(candidates):
        for c in candidates:
            if c in df.columns:
                return df[c].values
        raise KeyError(f"None of {candidates} found. Available: {list(df.columns)}")

    # ── Outdoor conditions ────────────────────────────────────────────────
    To  = get_col(["dry_bulb_temp [Celsius]", "dry_bulb_temp"])
    rho = get_col(["outdoor_relative_humidity [%]", "outdoor_relative_humidity"])
    wo  = np.array([rh_to_humidity_ratio(rho[i], To[i]) for i in range(N)])
    co  = get_col(["outdoor_co2 [ppm]", "outdoor_co2"])

    # ── FIX 3: Use measured supply air data directly from ROBOD CSV ───────
    # Rooms 3-5 have AHU: supply_air_flow [CMH] measured directly
    # Rooms 1-2 have FCU: estimate flow from fcu_fan_speed [Hz] × scale
    FCU_FLOW_SCALE = 0.01  # [kg/s per Hz] for FCU-type rooms (1,2)
    if "supply_air_flow [CMH]" in df.columns:
        cmh  = df["supply_air_flow [CMH]"].values
        msa  = np.clip(cmh * CMH_TO_KGS, 0.001, None)
    elif "ahu_fan_speed [Hz]" in df.columns:
        hz   = df["ahu_fan_speed [Hz]"].values
        msa  = np.clip(hz * FCU_FLOW_SCALE, 0.001, None)
    elif "fcu_fan_speed [Hz]" in df.columns:
        hz   = df["fcu_fan_speed [Hz]"].values
        msa  = np.clip(hz * FCU_FLOW_SCALE, 0.001, None)
    else:
        msa  = np.full(N, 0.05)  # default 0.05 kg/s if no flow data

    if "supply_air_temperature [Celsius]" in df.columns:
        Tsa  = df["supply_air_temperature [Celsius]"].values
    else:
        Tsa  = To - 5.0  # fallback: 5°C below outdoor temp

    if "supply_air_humidity [%]" in df.columns:
        sa_rh = df["supply_air_humidity [%]"].values
        wsa   = np.array([rh_to_humidity_ratio(sa_rh[i], Tsa[i]) for i in range(N)])
    else:
        # fallback: same as outdoor humidity
        wsa   = wo.copy()

    # FIX 3: Recirculation CO2 blending (no supply CO2 sensor in ROBOD)
    # Initialise cz_prev for recirculation model; updated each step
    cz_prev = get_col(["indoor_co2 [ppm]", "indoor_co2"])  # use measured as first pass
    csa_arr = F_RECIRC * cz_prev + (1.0 - F_RECIRC) * co  # pre-compute approx

    # ── Indoor measurements ───────────────────────────────────────────────
    Tz_meas  = get_col(["air_temperature [Celsius]", "indoor_temperature [Celsius]", "indoor_temperature"])
    RHz_meas = get_col(["indoor_relative_humidity [%]", "indoor_relative_humidity"])
    wz_meas  = np.array([rh_to_humidity_ratio(RHz_meas[i], Tz_meas[i]) for i in range(N)])
    cz_meas  = get_col(["indoor_co2 [ppm]", "indoor_co2"])
    occ_gt   = get_col(["occupant_count [number]", "occupant_count"])

    # ── FIX 1: Fixed Cs and alpha_s (eliminates identifiability degeneracy) ─
    V        = room_spec["volume"]
    M_fixed  = rho_air * V                          # kg  — room air mass (FIXED)
    bs_fixed = 1.0 / M_fixed                        # β_s = 1/M (FIXED)
    Cs_fixed = room_spec["Cs"] * 1000.0             # J/K — FIXED to nominal
    as_fixed = c_pa / Cs_fixed                      # α_s = c_pa/Cs FIXED
    UA_nom   = room_spec["UA"]
    UA_lo    = room_spec["UA"] * 0.2
    UA_hi    = room_spec["UA"] * 4.0

    bounds = {
        "ao": (UA_lo / Cs_fixed,  UA_hi / Cs_fixed), # α_o = UA/Cs_fixed
        "bo": (1e-6,              2e-3),              # β_o = m_inf/M [1/s]
        "ge": (0.0,               0.5),               # γ_e [ppm·kg/s]
    }

    # ── FIX 4: Initial state in sigmoid space (anchored at nominal values) ──
    def xi_from_theta(theta, lo, hi):
        """Inverse sigmoid: recover xi from known physical θ."""
        s = (theta - lo) / (hi - lo)
        s = np.clip(s, 1e-6, 1.0 - 1e-6)
        return np.log(s / (1.0 - s))

    X = np.zeros(N_STATES)
    X[I_xi_ao] = xi_from_theta(UA_nom / Cs_fixed, *bounds["ao"])
    X[I_xi_bo] = xi_from_theta(2.78e-5,           *bounds["bo"])
    X[I_xi_ge] = xi_from_theta(0.01,              *bounds["ge"])
    X[I_Tz]    = Tz_meas[0]
    X[I_wz]    = wz_meas[0]
    X[I_cz]    = cz_meas[0]

    P = np.eye(N_STATES) * 0.1
    P[I_xi_ao, I_xi_ao] = 2.0
    P[I_xi_bo, I_xi_bo] = 1.0
    P[I_xi_ge, I_xi_ge] = 9.0

    # Process noise Q (6-state)
    Q = np.diag([
        2e-4,    # xi_ao  — UA estimation (slow drift)
        5e-4,    # xi_bo  — infiltration variation
        2e-2,    # xi_ge  — CO2 generation (must track occupancy steps)
        0.005,   # Tz     — model mismatch [°C²/s]
        1e-7,    # wz     — moisture noise
        2.0,     # cz     — CO2 noise [ppm²/s]
    ])

    # FIX 5: Initial measurement noise R — physically calibrated
    R_adaptive = np.diag([0.09, 1e-6, 100.0])  # Tz: 0.3°C std, CO2: 10ppm std
    alpha_forget = 0.98                         # Forgetting factor for Sage-Husa R update

    # Measurement matrix H (only environmental states are directly measured)
    H = np.zeros((3, N_STATES))
    H[0, I_Tz] = 1.0
    H[1, I_wz] = 1.0
    H[2, I_cz] = 1.0

    # Storage
    X_hist  = np.zeros((N, N_STATES))
    innov_h = np.zeros((N, 3))

    for k in range(N):
        # ── FIX 3: Update recirculation CO2 supply dynamically using last cz ─
        cz_est  = X[I_cz]
        csa_k   = F_RECIRC * cz_est + (1.0 - F_RECIRC) * co[k]

        U_k = [To[k], wo[k], co[k], Tsa[k], wsa[k], csa_k, msa[k]]
        Z_k = np.array([Tz_meas[k], wz_meas[k], cz_meas[k]])

        # ── FIX 2: RK4 Prediction ────────────────────────────────────────
        X_pred = rk4_step(X, U_k, DT, bs_fixed, bounds, as_fixed)

        # ── Covariance Prediction (linearised about current X)
        J_F = get_jacobian_F(X, U_k, bs_fixed, bounds, as_fixed)
        F_k = np.eye(N_STATES) + J_F * DT
        P_pred = F_k @ P @ F_k.T + Q * DT
        P_pred = 0.5 * (P_pred + P_pred.T)

        # ── Measurement Update ───────────────────────────────────────────
        Z_pred = np.array([X_pred[I_Tz], X_pred[I_wz], X_pred[I_cz]])
        y_k    = Z_k - Z_pred

        S_k    = H @ P_pred @ H.T + R_adaptive
        K_k    = P_pred @ H.T @ np.linalg.solve(S_k.T, np.eye(3)).T

        X = X_pred + K_k @ y_k
        P = (np.eye(N_STATES) - K_k @ H) @ P_pred
        P = 0.5 * (P + P.T)

        # ── FIX 5: Adaptive R update (simplified Sage-Husa) ─────────────
        innov_outer   = np.outer(y_k, y_k)
        R_innovation  = innov_outer + H @ P_pred @ H.T  # true innovation covariance estimate
        R_new         = alpha_forget * R_adaptive + (1.0 - alpha_forget) * R_innovation
        # Ensure positive definiteness with physical lower bounds
        R_adaptive    = np.maximum(R_new, np.diag([0.001, 1e-8, 0.5]))

        innov_h[k] = y_k
        X_hist[k]  = X

    return X_hist, Tz_meas, RHz_meas, cz_meas, occ_gt, msa, bounds, as_fixed, M_fixed, bs_fixed, innov_h

# ── Derived Physical Parameters from 7-State History ─────────────────────────
def derive_physical(X_hist, bounds, as_fixed, M_fixed):
    """Convert 6-state sigmoid-space history back to physical parameters."""
    N    = len(X_hist)
    ao   = np.array([sigmoid_map(X_hist[i, I_xi_ao], *bounds["ao"]) for i in range(N)])
    bo   = np.array([sigmoid_map(X_hist[i, I_xi_bo], *bounds["bo"]) for i in range(N)])
    ge   = np.array([sigmoid_map(X_hist[i, I_xi_ge], *bounds["ge"]) for i in range(N)])

    as_  = as_fixed                                # fixed constant
    Cs   = (c_pa / as_fixed) / 1000.0             # kJ/K (fixed from nominal)
    UA   = ao * Cs * 1000.0                        # W/K  = ao * Cs[J/K]
    m_inf = bo * M_fixed                           # kg/s
    N_est = ge * M_fixed / 0.008                  # Occupant count estimate

    return ao, as_, bo, ge, Cs, UA, m_inf, N_est

# ── Plotting ───────────────────────────────────────────────────────────────────
def make_all_plots(X_hist, Tz_m, RHz_m, cz_m, occ_gt, msa,
                   bounds, as_fixed, M_fixed, room_spec, t_hours, room_str):
    ao, as_, bo, ge, Cs, UA, m_inf, N_est = derive_physical(X_hist, bounds, as_fixed, M_fixed)

    rh_est = np.array([humidity_ratio_to_rh(X_hist[i, I_wz], X_hist[i, I_Tz])
                        for i in range(len(X_hist))])

    N_max = room_spec["max_occ"]

    # ── PLOT 1: Environmental States ──────────────────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    axes[0].plot(t_hours, Tz_m, "r--", alpha=0.5, lw=1.2, label="Measured Tz")
    axes[0].plot(t_hours, X_hist[:, I_Tz], "b-", lw=1.5, label="EKF Estimated Tz")
    axes[0].set_ylabel("Temperature (°C)", fontsize=10)
    axes[0].set_title(f"ROBOD {room_spec['name']} — 7-State EKF Environmental States (v2)", fontsize=12, fontweight="bold")
    axes[0].legend(loc="upper right", fontsize=8); axes[0].grid(True, alpha=0.3)

    axes[1].plot(t_hours, RHz_m, "orange", linestyle="--", alpha=0.5, lw=1.2, label="Measured RHz")
    axes[1].plot(t_hours, rh_est, color="teal", lw=1.5, label="EKF Estimated RHz")
    axes[1].set_ylabel("Relative Humidity (%)", fontsize=10)
    axes[1].legend(loc="upper right", fontsize=8); axes[1].grid(True, alpha=0.3)

    axes[2].plot(t_hours, cz_m, "g--", alpha=0.5, lw=1.2, label="Measured CO2z")
    axes[2].plot(t_hours, X_hist[:, I_cz], "k-", lw=1.5, label="EKF Estimated CO2z")
    axes[2].set_ylabel("CO₂ (ppm)", fontsize=10)
    axes[2].set_xlabel("Elapsed Time (hours)", fontsize=10)
    axes[2].legend(loc="upper right", fontsize=8); axes[2].grid(True, alpha=0.3)
    plt.tight_layout()
    path1 = os.path.join(OUT_PLOT_DIR, f"{room_str}_EKF_States_3Subplots.png")
    plt.savefig(path1, dpi=130, bbox_inches="tight"); plt.close()

    # ── PLOT 2: Occupancy vs Ground Truth ─────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 4))
    N_clipped = np.clip(N_est, 0.0, N_max * 1.2)
    ax.plot(t_hours, N_clipped, color="magenta", lw=1.5, label="EKF Estimated Occupants (N)")
    ax.plot(t_hours, occ_gt, "k--", lw=1.2, alpha=0.6, label="Ground Truth Occupancy Count")
    ax.set_ylabel("Occupant Count (person)", fontsize=10)
    ax.set_xlabel("Elapsed Time (hours)", fontsize=10)
    ax.set_title(f"ROBOD {room_spec['name']} — EKF Recovered Occupancy vs Ground Truth", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path2 = os.path.join(OUT_PLOT_DIR, f"{room_str}_EKF_Occupancy_vs_GroundTruth.png")
    plt.savefig(path2, dpi=130, bbox_inches="tight"); plt.close()

    # ── PLOT 3: Physical Parameters (alpha_o, beta_o, gamma_e only) ──────
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    axes[0].plot(t_hours, ao,  color="purple", lw=1.3, label=f"alpha_o = UA/Cs_fixed [1/s]")
    axes[0].set_ylabel("alpha_o [1/s]", fontsize=9); axes[0].legend(fontsize=8); axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f"ROBOD {room_spec['name']} — EKF Estimated Parameters (v2)", fontsize=12, fontweight="bold")

    axes[1].plot(t_hours, bo,  color="green", lw=1.3, label="beta_o = m_inf/M [1/s]")
    axes[1].set_ylabel("beta_o [1/s]", fontsize=9); axes[1].legend(fontsize=8); axes[1].grid(True, alpha=0.3)

    axes[2].plot(t_hours, ge,  color="crimson", lw=1.3, label="gamma_e: CO2 generation [ppm*kg/s]")
    axes[2].set_ylabel("gamma_e", fontsize=9); axes[2].set_xlabel("Elapsed Time (hours)", fontsize=10)
    axes[2].legend(fontsize=8); axes[2].grid(True, alpha=0.3)
    plt.tight_layout()
    path3 = os.path.join(OUT_PLOT_DIR, f"{room_str}_EKF_Estimated_Parameters.png")
    plt.savefig(path3, dpi=130, bbox_inches="tight"); plt.close()

    # ── PLOT 4: Derived Physical Building Parameters ──────────────────────
    Cs_fixed_kJ = Cs  # constant scalar (same for all time steps)
    UA_arr = UA        # W/K array over time
    m_inf_gs = m_inf * 1000.0
    Cs_nom_kJ = room_spec["Cs"]

    fig, axes = plt.subplots(4, 1, figsize=(14, 14), sharex=True)

    # Cs is FIXED — show as constant with benchmark band
    axes[0].fill_between(t_hours, Cs_nom_kJ*0.7, Cs_nom_kJ*1.5,
                          alpha=0.18, color="green", label=f"Benchmark [{Cs_nom_kJ*0.7:.0f}–{Cs_nom_kJ*1.5:.0f} kJ/K]")
    axes[0].axhline(Cs_fixed_kJ, color="blue", lw=2.0, label=f"Cs FIXED = {Cs_fixed_kJ:.0f} kJ/K (nominal)")
    axes[0].set_ylabel("Cs (kJ/K)"); axes[0].legend(fontsize=8); axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f"ROBOD {room_spec['name']} — Derived Physical Parameters (v2)", fontsize=12, fontweight="bold")

    axes[1].fill_between(t_hours, M_fixed * 0.9, M_fixed * 1.1,
                          alpha=0.18, color="green", label=f"Air Mass M = {M_fixed:.1f} kg (fixed)")
    axes[1].axhline(M_fixed, color="teal", lw=1.5, label=f"M_fixed = {M_fixed:.1f} kg")
    axes[1].set_ylabel("M (kg)"); axes[1].legend(fontsize=8); axes[1].grid(True, alpha=0.3)

    axes[2].fill_between(t_hours, 0.0, 50.0, alpha=0.18, color="green",
                          label="Expected infiltration (0–50 g/s)")
    axes[2].plot(t_hours, m_inf_gs, color="purple", lw=1.3, label="Estimated m_inf (g/s)")
    axes[2].set_ylabel("m_inf (g/s)"); axes[2].legend(fontsize=8); axes[2].grid(True, alpha=0.3)

    axes[3].fill_between(t_hours, room_spec["UA"] * 0.6, room_spec["UA"] * 1.4,
                          alpha=0.18, color="green",
                          label=f"Benchmark [{room_spec['UA']*0.6:.0f}–{room_spec['UA']*1.4:.0f} W/K]")
    axes[3].plot(t_hours, UA_arr, color="darkred", lw=1.3, label="Estimated UA (W/K)")
    axes[3].set_ylabel("UA (W/K)"); axes[3].set_xlabel("Elapsed Time (hours)")
    axes[3].legend(fontsize=8); axes[3].grid(True, alpha=0.3)
    plt.tight_layout()
    path4 = os.path.join(OUT_PLOT_DIR, f"{room_str}_EKF_Derived_Physical_Parameters.png")
    plt.savefig(path4, dpi=130, bbox_inches="tight"); plt.close()

    print(f"  ALL 4 PLOTS SAVED for {room_spec['name']}")
    return Cs_fixed_kJ, UA_arr, m_inf_gs, N_est

# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 7-State EKF v2 on ROBOD Dataset")
    parser.add_argument("--room", type=int, default=3, choices=[1, 2, 3, 4, 5])
    args = parser.parse_args()

    room_id = args.room
    spec    = ROOM_SPECS[room_id]
    csv_file = os.path.join(ROBOD_DIR, spec["file"])

    print(f"\n{'='*65}")
    print(f"  7-State EKF v2 | ROBOD {spec['name']}")
    print(f"  Fixes: [1] Reduced state  [2] RK4  [3] Supply air  [4] Sigmoid  [5] Adaptive R")
    print(f"{'='*65}")
    print(f"Loading {spec['file']}...")
    df = pd.read_csv(csv_file)
    print(f"Running EKF on {len(df)} samples ({len(df)*DT/3600:.1f} hours)...")

    X_hist, Tz_m, RHz_m, cz_m, occ_gt, msa, bounds, as_fixed, M_fixed, bs_fixed, innov_h = \
        run_ekf_on_robod(df, spec)

    t_hours  = np.arange(len(df)) * (DT / 3600.0)
    room_str = spec["name"].replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")

    Cs_kJ, UA, m_inf_gs, N_est = make_all_plots(
        X_hist, Tz_m, RHz_m, cz_m, occ_gt, msa,
        bounds, as_fixed, M_fixed, spec, t_hours, room_str
    )

    # ── Console Summary ───────────────────────────────────────────────────
    rmse_Tz = np.sqrt(np.mean((Tz_m - X_hist[:, I_Tz])**2))
    rmse_cz = np.sqrt(np.mean((cz_m - X_hist[:, I_cz])**2))
    print(f"\n  RMSE  Tz  = {rmse_Tz:.3f} degC")
    print(f"  RMSE  CO2 = {rmse_cz:.1f} ppm")
    print(f"  Cs (FIXED) = {Cs_kJ:.0f} kJ/K   [nominal: {spec['Cs']:.0f} kJ/K]")
    print(f"  UA (final) = {UA[-1]:.1f} W/K    [nominal: {spec['UA']:.0f} W/K]")
    print(f"  M  (fixed) = {M_fixed:.1f} kg     [rho*V = {rho_air}x{spec['volume']}]")
    print(f"  Plots saved to: results_plots/")
    print(f"{'='*65}\n")
