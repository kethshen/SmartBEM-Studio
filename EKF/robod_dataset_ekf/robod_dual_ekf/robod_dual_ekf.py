"""
SmartBEM FYP — Dual EKF for ROBOD Dataset (Rooms 1 - 5)
========================================================
Direct adaptation of test_rig_dual_ekf.py tailored for the 5 ROBOD Room Datasets:
  - Fast 3-State Filter (Tz, wz, cz) at 300s sampling
  - Multi-Rate 5-Parameter Filter (ao, as, ae, bo, ge)
  - Uses live sensor barometric pressure (P_live in Pa)
  - Generates exactly 4 PNG plots per room dataset in plots/[room_name]/:
      1. dual_ekf_states.png
      2. dual_ekf_occupancy_estimation.png
      3. dual_ekf_estimated_parameters.png
      4. dual_ekf_derived_physical_properties.png
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
PARAM_UPDATE_STEP = 1      # Update parameter filter at EVERY single timestep (5 minutes)

# ── Room Specifications (official NUS ROBOD room_descriptions) ─────────────────
ROOM_SPECS = {
    1: {"name": "combined_Room1", "file": "combined_Room1.csv", "volume": 120.0, "max_occ": 6.0,  "Cs": 500000.0,  "UA": 80.0},
    2: {"name": "combined_Room2", "file": "combined_Room2.csv", "volume": 150.0, "max_occ": 8.0,  "Cs": 650000.0,  "UA": 100.0},
    3: {"name": "combined_Room3", "file": "combined_Room3.csv", "volume": 413.2, "max_occ": 13.0, "Cs": 1500000.0, "UA": 250.0},
    4: {"name": "combined_Room4", "file": "combined_Room4.csv", "volume": 756.0, "max_occ": 25.0, "Cs": 2800000.0, "UA": 450.0},
    5: {"name": "combined_Room5", "file": "combined_Room5.csv", "volume": 760.0, "max_occ": 25.0, "Cs": 2850000.0, "UA": 450.0},
}

def rh_to_w(rh_pct, T_C, P_pa):
    """Converts RH [%] and T [°C] to Humidity Ratio [kg_w/kg_a] using live pressure P_pa."""
    rh = np.clip(rh_pct / 100.0, 0.0, 1.0)
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    omega = 0.622 * (rh * P_sat) / (P_pa - rh * P_sat)
    return np.clip(omega, 0.0, 0.05)

def w_to_rh(omega, T_C, P_pa):
    """Converts Humidity Ratio [kg_w/kg_a] and T [°C] to RH [%] using live pressure P_pa."""
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    P_w = (omega * P_pa) / (0.622 + omega)
    rh = (P_w / P_sat) * 100.0
    return np.clip(rh, 0.0, 100.0)

def sigmoid(xi):
    return np.where(xi >= 0, 1.0 / (1.0 + np.exp(-xi)), np.exp(xi) / (1.0 + np.exp(xi)))

def sig_map(xi, lo, hi):
    return lo + (hi - lo) * sigmoid(xi)

def sig_jac(xi, lo, hi):
    s = sigmoid(xi)
    # Enforce minimum derivative floor (0.05) to prevent sigmoid gradient vanishing trap
    return (hi - lo) * np.maximum(s * (1.0 - s), 0.05)

def xi_from_theta(theta, lo, hi):
    s = np.clip((theta - lo) / (hi - lo), 1e-6, 1.0 - 1e-6)
    return np.log(s / (1.0 - s))

# ── Fast 3-State Filter Dynamics (RK4) ─────────────────────────────────────────
def state_f(S, U, theta, Cs_nom, v_room):
    Tz, wz, cz = S
    To, wo, co, Tsa, wsa, csa, msa = U
    ao, as_, ae, bo, ge, bs_f = theta

    g_CO2_per_person = 4.5 / v_room  # Exact room-specific CO2 generation rate per person
    n_occ_est = ge / g_CO2_per_person
    q_occ_sensible = n_occ_est * 70.0  # [W]
    a_occ_heat = q_occ_sensible / Cs_nom # [°C/s]

    dTz = ao * (To - Tz) + as_ * msa * (Tsa - Tz) + ae + a_occ_heat
    dwz = bo * (wo - wz) + bs_f * msa * (wsa - wz)
    dcz = bo * (co - cz) + bs_f * msa * (csa - cz) + ge
    return np.array([dTz, dwz, dcz])

def state_rk4(S, U, dt, theta, Cs_nom, v_room):
    k1 = state_f(S,               U, theta, Cs_nom, v_room)
    k2 = state_f(S + 0.5*dt*k1,  U, theta, Cs_nom, v_room)
    k3 = state_f(S + 0.5*dt*k2,  U, theta, Cs_nom, v_room)
    k4 = state_f(S + dt*k3,      U, theta, Cs_nom, v_room)
    return S + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)

def state_jacobian(S, U, theta):
    ao, as_, ae, bo, ge, bs_f = theta
    To, wo, co, Tsa, wsa, csa, msa = U

    J = np.zeros((3, 3))
    J[0, 0] = -(ao + as_ * msa)
    J[1, 1] = -(bo + bs_f * msa)
    J[2, 2] = -(bo + bs_f * msa)
    return J

def params_from_xi(xi_p, bounds_p):
    ao  = sig_map(xi_p[0], *bounds_p["ao"])
    as_ = sig_map(xi_p[1], *bounds_p["as"])
    ae  = sig_map(xi_p[2], *bounds_p["ae"])
    bo  = sig_map(xi_p[3], *bounds_p["bo"])
    ge  = sig_map(xi_p[4], *bounds_p["ge"])
    return ao, as_, ae, bo, ge

def param_jacobian(xi_p, S_avg, U_avg, bounds_p):
    Tz, wz, cz = S_avg
    To, wo, co, Tsa, wsa, csa, msa = U_avg

    dAo = sig_jac(xi_p[0], *bounds_p["ao"])
    dAs = sig_jac(xi_p[1], *bounds_p["as"])
    dAe = sig_jac(xi_p[2], *bounds_p["ae"])
    dBo = sig_jac(xi_p[3], *bounds_p["bo"])
    dGe = sig_jac(xi_p[4], *bounds_p["ge"])

    win = DT * PARAM_UPDATE_STEP

    H_p = np.zeros((5, 5))
    H_p[0, 0] = (To - Tz) * dAo * win
    H_p[1, 1] = msa * (Tsa - Tz) * dAs * win
    H_p[2, 2] = 1.0 * dAe * win
    H_p[3, 3] = (wo - wz) * dBo * win
    H_p[4, 4] = dGe * win
    return H_p

def run_dual_ekf_robod(df, room_spec):
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
    g_CO2_per_person = 4.5 / v_room
    max_occ = room_spec["max_occ"] * 1.5  # Room capacity headroom

    if "baromatic_pressure [hPa]" in df.columns:
        P_live_arr = df["baromatic_pressure [hPa]"].fillna(1013.25).values * 100.0
    else:
        P_live_arr = np.full(N, 101325.0)

    To = df["dry_bulb_temp [Celsius]"].fillna(28.0).values
    RHo = df["outdoor_relative_humidity [%]"].fillna(75.0).values
    wo = np.array([rh_to_w(RHo[i], To[i], P_live_arr[i]) for i in range(N)])
    co = df["outdoor_co2 [ppm]"].fillna(400.0).values

    Tsa = df["supply_air_temperature [Celsius]"].fillna(18.0).values
    if "supply_air_humidity [%]" in df.columns:
        RHsa = df["supply_air_humidity [%]"].fillna(85.0).values
    else:
        RHsa = RHo.copy()
    wsa = np.array([rh_to_w(RHsa[i], Tsa[i], P_live_arr[i]) for i in range(N)])

    if "supply_air_flow [CMH]" in df.columns:
        msa = df["supply_air_flow [CMH]"].fillna(0.0).values * (rho_air / 3600.0)
    elif "fcu_fan_speed [Hz]" in df.columns:
        msa = (df["fcu_fan_speed [Hz]"].fillna(0.0).values / 50.0) * 0.15
    else:
        msa = np.full(N, 0.05)

    Tz_m = df["air_temperature [Celsius]"].values
    RHz_m = df["indoor_relative_humidity [%]"].values
    cz_m = df["indoor_co2 [ppm]"].values
    wz_m = np.array([rh_to_w(RHz_m[i], Tz_m[i], P_live_arr[i]) for i in range(N)])

    # Supply air CO2: Central VAV fresh outdoor air supply (co)
    csa = co.copy()
    bs_f = 1.0 / M_room

    ge_max = max_occ * g_CO2_per_person
    ge_init = 0.20 * ge_max  # Start in active gradient region

    bounds_p = {
        "ao": (0.2 * UA_nom / Cs_nom, 2.0 * UA_nom / Cs_nom),
        "as": (c_pa / (2.0 * Cs_nom), c_pa / (0.5 * Cs_nom)),
        "ae": (-0.001, 0.002),
        "bo": (1e-7, 1e-3),
        "ge": (0.0, ge_max),
    }

    xi_p = np.array([
        xi_from_theta(UA_nom / Cs_nom, *bounds_p["ao"]),
        xi_from_theta(c_pa / Cs_nom,   *bounds_p["as"]),
        xi_from_theta(0.0,             *bounds_p["ae"]),
        xi_from_theta(3e-6,            *bounds_p["bo"]),
        xi_from_theta(ge_init,         *bounds_p["ge"]),
    ])

    Pp = np.diag([2.0, 2.0, 1.0, 2.0, 4.0])
    Qp = np.diag([1e-9, 1e-8, 1e-7, 1e-5, 5e-1])
    Rp = np.diag([0.5, 0.5, 0.5, 1e-5, 0.01])

    S  = np.array([Tz_m[0], wz_m[0], cz_m[0]])
    Ps = np.diag([0.01**2, 0.0002**2, 2.5**2])
    Qs = np.diag([1e-2, 1e-9, 1.0])
    H_s = np.eye(3)
    Rs = np.diag([0.0001, 4e-8, 6.25])

    Tz_est  = np.zeros(N)
    wz_est  = np.zeros(N)
    cz_est  = np.zeros(N)
    ao_hist = np.zeros(N)
    as_hist = np.zeros(N)
    ae_hist = np.zeros(N)
    bo_hist = np.zeros(N)
    ge_hist = np.zeros(N)
    innov_window = []

    for k in range(N):
        ao_k, as_k, ae_k, bo_k, ge_k = params_from_xi(xi_p, bounds_p)
        theta_k = (ao_k, as_k, ae_k, bo_k, ge_k, bs_f)
        csa_k = co[k]
        U_k = (To[k], wo[k], co[k], Tsa[k], wsa[k], csa_k, msa[k])

        S_pred  = state_rk4(S, U_k, DT, theta_k, Cs_nom, v_room)
        J_s     = state_jacobian(S, U_k, theta_k)
        Fs      = np.eye(3) + J_s * DT
        Ps_pred = Fs @ Ps @ Fs.T + Qs * DT
        Ps_pred = 0.5 * (Ps_pred + Ps_pred.T)

        Z_3    = np.array([Tz_m[k], wz_m[k], cz_m[k]])
        cz_err = Z_3[2] - S_pred[2]
        y_3    = Z_3 - H_s @ S_pred
        S_inn  = H_s @ Ps_pred @ H_s.T + Rs
        K_s    = np.linalg.solve(S_inn.T, (Ps_pred @ H_s.T).T).T
        S      = S_pred + K_s @ y_3
        Ps     = (np.eye(3) - K_s @ H_s) @ Ps_pred
        Ps     = 0.5 * (Ps + Ps.T)

        innov_5 = np.array([y_3[0], y_3[0], y_3[0], y_3[1], cz_err])
        innov_window.append(innov_5)

        if len(innov_window) >= PARAM_UPDATE_STEP:
            innov_arr  = np.array(innov_window)

            innov_batch = np.array([
                innov_arr[:, 0].mean(),
                innov_arr[:, 1].mean(),
                innov_arr[:, 2].mean(),
                innov_arr[:, 3].mean(),
                innov_arr[:, 4].mean()
            ])
            innov_window = []

            S_avg = S.copy()
            U_avg = U_k

            Pp = Pp + Qp * (DT * PARAM_UPDATE_STEP)
            Pp = 0.5 * (Pp + Pp.T)

            H_p = param_jacobian(xi_p, S_avg, U_avg, bounds_p)
            S_p = H_p @ Pp @ H_p.T + Rp
            try:
                K_p = np.linalg.solve(S_p.T, (Pp @ H_p.T).T).T
            except np.linalg.LinAlgError:
                K_p = np.zeros((5, 5))

            delta_xi = K_p @ innov_batch
            delta_xi = np.clip(delta_xi, -0.5, 0.5)

            if Pp[3, 3] < 0.01:
                delta_xi[3] = 0.0

            xi_p = xi_p + delta_xi
            Pp = (np.eye(5) - K_p @ H_p) @ Pp
            Pp = 0.5 * (Pp + Pp.T)

        ao_k2, as_k2, ae_k2, bo_k2, ge_k2 = params_from_xi(xi_p, bounds_p)
        Tz_est[k]  = S[0]
        wz_est[k]  = S[1]
        cz_est[k]  = S[2]
        ao_hist[k] = ao_k2
        as_hist[k] = as_k2
        ae_hist[k] = ae_k2
        bo_hist[k] = bo_k2
        ge_hist[k] = ge_k2

    Cs_hist    = c_pa / np.where(np.abs(as_hist) > 1e-12, as_hist, 1e-12)
    N_occ_est  = ge_hist / g_CO2_per_person
    m_inf_kgs  = bo_hist * M_room
    m_inf_hist = m_inf_kgs * 1000.0
    UA_hist    = ao_hist * Cs_hist - c_pa * m_inf_kgs
    RHz_est    = np.array([w_to_rh(wz_est[i], Tz_est[i], P_live_arr[i]) for i in range(N)])

    return (Tz_est, wz_est, cz_est, RHz_est,
            ao_hist, as_hist, ae_hist, bo_hist, ge_hist, Cs_hist, UA_hist, N_occ_est, m_inf_hist,
            Tz_m, RHz_m, cz_m, P_live_arr)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN PLOTTING AND EXECUTION LOOP
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 65)
    print("  Dual EKF v3 — ROBOD Dataset (Rooms 1 - 5)")
    print("  Running on 5 room datasets...")
    print("=" * 65 + "\n")

    for room_id, spec in ROOM_SPECS.items():
        base_name = spec["name"]
        csv_file  = spec["file"]
        csv_path  = os.path.join(ROBOD_DIR, csv_file)

        if not os.path.exists(csv_path):
            print(f"[WARNING] Skipping missing file: {csv_path}")
            continue

        print(f"Running Dual EKF for ROBOD {base_name}...")
        dataset_plot_dir = os.path.join(PLOTS_DIR, base_name)
        os.makedirs(dataset_plot_dir, exist_ok=True)
        print(f"• Output folder: {dataset_plot_dir}")

        df = pd.read_csv(csv_path)

        res = run_dual_ekf_robod(df, spec)
        (Tz_est, wz_est, cz_est, RHz_est,
         ao_hist, as_hist, ae_hist, bo_hist, ge_hist, Cs_hist, UA_hist, N_occ_est, m_inf_hist,
         Tz_m, RHz_m, cz_m, P_live) = res

        N = len(df)
        t_min = np.arange(N) * DT / 60.0
        N_occ_gt = df["occupant_count [number]"].fillna(0.0).values

        # ── PLOT 1: STATES (Tz, RHz, CO2) ────────────────────────────────────
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

        ax1.plot(t_min, Tz_m, color=COLOR_CYAN, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured Tz (°C)")
        ax1.plot(t_min, Tz_est, color=COLOR_RED, linestyle="-", linewidth=2.2, label="Dual-EKF Estimated Tz (°C)")
        ax1.set_ylabel("Temperature (°C)", fontsize=10)
        ax1.set_title(f"ROBOD {base_name} — Dual-EKF Physical State Estimation", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        ax2.plot(t_min, RHz_m, color=COLOR_ORANGE, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured RH (%)")
        ax2.plot(t_min, RHz_est, color=COLOR_BLUE, linestyle="-", linewidth=2.2, label="Dual-EKF Estimated RH (%)")
        ax2.set_ylabel("Relative Humidity (%)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        ax3.plot(t_min, cz_m, color=COLOR_CRIMSON, linestyle="--", alpha=0.8, linewidth=2.0, label="Measured CO2 (ppm)")
        ax3.plot(t_min, cz_est, color=COLOR_TEAL, linestyle="-", linewidth=2.2, label="Dual-EKF Estimated CO2 (ppm)")
        ax3.set_ylabel("CO2 Concentration (ppm)", fontsize=10)
        ax3.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax3.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax3.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot1_path = os.path.join(dataset_plot_dir, "dual_ekf_states.png")
        plt.savefig(plot1_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 1: {plot1_path}")

        # ── PLOT 2: OCCUPANCY ESTIMATION VS GROUND TRUTH ─────────────────────
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(t_min, N_occ_est, color=COLOR_PURPLE, linestyle="-", linewidth=2.0, label="Continuous Dual-EKF Estimated Occupants (N)")
        ax.step(t_min, N_occ_gt, color=COLOR_TEAL, where="post", linewidth=2.0, linestyle="--", alpha=0.8, label="Ground Truth Occupancy")

        ax.set_ylabel("Occupant Count (persons)", fontsize=11)
        ax.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax.set_title(f"ROBOD {base_name} — Dual-EKF Occupancy Estimation vs Ground Truth", fontsize=12, fontweight="bold", pad=12)
        ax.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white")
        ax.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot2_path = os.path.join(dataset_plot_dir, "dual_ekf_occupancy_estimation.png")
        plt.savefig(plot2_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 2: {plot2_path}")

        # ── PLOT 3: ESTIMATED PARAMETERS (ao, as, ae, bo, ge) ───────────────
        fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(11, 13), sharex=True)

        ax1.plot(t_min, ao_hist, color=COLOR_PURPLE, linewidth=1.8, label=r"$\alpha_o$ Envelope Loss [1/s]")
        ax1.set_ylabel(r"$\alpha_o$ [1/s]", fontsize=10)
        ax1.set_title(f"ROBOD {base_name} — Dual-EKF Estimated Parameters", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        ax2.plot(t_min, as_hist, color=COLOR_BLUE, linewidth=1.8, label=r"$\alpha_s$ Supply Air Capacity [1/(kg·s)]")
        ax2.set_ylabel(r"$\alpha_s$ [1/(kg·s)]", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        ax3.plot(t_min, ae_hist, color=COLOR_TEAL, linewidth=1.8, label=r"$\alpha_e$ Thermal Bias Gain [°C/s]")
        ax3.set_ylabel(r"$\alpha_e$ [°C/s]", fontsize=10)
        ax3.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax3.grid(True, linestyle=":", alpha=0.6)

        ax4.plot(t_min, bo_hist, color=COLOR_CYAN, linewidth=1.8, label=r"$\beta_o$ Infiltration Rate [1/s]")
        ax4.set_ylabel(r"$\beta_o$ [1/s]", fontsize=10)
        ax4.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax4.grid(True, linestyle=":", alpha=0.6)

        ax5.plot(t_min, ge_hist, color=COLOR_CRIMSON, linewidth=1.8, label=r"$\gamma_e$ CO2 Generation Rate [ppm/s]")
        ax5.set_ylabel(r"$\gamma_e$ [ppm/s]", fontsize=10)
        ax5.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax5.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax5.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot3_path = os.path.join(dataset_plot_dir, "dual_ekf_estimated_parameters.png")
        plt.savefig(plot3_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 3: {plot3_path}")

        # ── PLOT 4: DERIVED PHYSICAL PARAMETERS (Cs, M, m_inf, UA) ───────────
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

        ax1.plot(t_min, Cs_hist / 1000.0, color=COLOR_BLUE, linewidth=2.0, label="Estimated Thermal Capacitance Cs (kJ/°C)")
        ax1.axhline(spec["Cs"] / 1000.0, color=COLOR_TEAL, linestyle="--", label=f"Nominal Cs = {spec['Cs']/1000.0:.1f} kJ/°C")
        ax1.set_ylabel("Cs (kJ/°C)", fontsize=10)
        ax1.set_title(f"ROBOD {base_name} — Dual-EKF Derived Physical Building Parameters (Cs, M, m_inf, UA)", fontsize=12, fontweight="bold", pad=12)
        ax1.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax1.grid(True, linestyle=":", alpha=0.6)

        ax2.axhline(spec["volume"] * rho_air, color=COLOR_TEAL, linewidth=2.0, label=f"Zone Air Mass M FIXED = {spec['volume']*rho_air:.1f} kg")
        ax2.set_ylabel("Air Mass M (kg)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax2.grid(True, linestyle=":", alpha=0.6)

        ax3.plot(t_min, m_inf_hist, color=COLOR_PURPLE, linewidth=2.0, label="Estimated Infiltration Rate m_inf (g/s)")
        ax3.set_ylabel("m_inf (g/s)", fontsize=10)
        ax3.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax3.grid(True, linestyle=":", alpha=0.6)

        ax4.plot(t_min, UA_hist, color=COLOR_CRIMSON, linewidth=2.0, label="Estimated Envelope Conductance UA (W/°C)")
        ax4.axhline(spec["UA"], color=COLOR_TEAL, linestyle="--", label=f"Nominal UA = {spec['UA']:.1f} W/°C")
        ax4.set_ylabel("UA (W/°C)", fontsize=10)
        ax4.set_xlabel("Elapsed Time (minutes)", fontsize=11)
        ax4.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white")
        ax4.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        plot4_path = os.path.join(dataset_plot_dir, "dual_ekf_derived_physical_properties.png")
        plt.savefig(plot4_path, dpi=150)
        plt.close()
        print(f"  • Saved Plot 4: {plot4_path}")

        print(f"[SUCCESS] Saved 4 Dual-EKF plots for: {base_name}\n")

    print("\nALL DUAL EKF RUNS FOR ROBOD COMPLETED SUCCESSFULLY.")
