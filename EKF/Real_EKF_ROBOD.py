"""
SmartBEM FYP — 10-State EKF with ROBOD Dataset  (Phase 1)
===========================================================
Full advisor design restored:

  State vector X (10 states):
    [α_o, α_s, α_e,       ← temperature parameters   (idx 0,1,2)
     β_o, β_s, β_e,       ← humidity/CO₂ parameters  (idx 3,4,5)
     γ_e,                 ← CO₂ source rate            (idx 6)
     T_z, ω_z, c_z]       ← measured physical states   (idx 7,8,9)

  Measurement vector Z (3):
    [T_z_meas, ω_z_meas, c_z_meas]

  Real inputs from ROBOD columns (no more hardcoded constants):
    T_o   ← dry_bulb_temp [Celsius]
    c_o   ← outdoor_co2 [ppm]
    ω_o   ← outdoor_relative_humidity [%]  (converted to humidity ratio)
    T_sa  ← supply_air_temperature [Celsius]
    c_sa  ← approximated as outdoor_co2 (fresh-air FCU assumption)
    ω_sa  ← approximated as outdoor ω_o (FCU with no humidifier)
    m_sa  ← derived from fcu_fan_speed [Hz] via linear scaling

  Dataset: ROBOD combined_Room3.csv  (office space — closest to lab setup)
           29 days, 5-min intervals, 8352 rows.

Naming convention: _prev, _pred, _est  (consistent with EKF_System_Reference.md)

Run modes:
  python Real_EKF_ROBOD.py            → interactive plot window
  python Real_EKF_ROBOD.py --save     → save 14 PNG plots to EKF/results_robod/
  python Real_EKF_ROBOD.py --room 4   → use combined_Room4.csv instead
"""

import numpy as np
import pandas as pd
import sys
import os

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ROBOD_DIR   = os.path.join(SCRIPT_DIR, "Datasets for EKF",
                           "ROBOD, Room level Occupancy and Building Operation Dataset")

# ── Physical constants ─────────────────────────────────────────────────────────
c_pa       = 1006.0   # specific heat of air              [J/(kg*K)]

# Room air mass — estimated from geometry (not from beta_s which diverges)
# Room 3 SDE4 NUS: office space, typical ~200 m3 -> M = 200*1.2 = 240 kg
# Diagnostic showed CO2 delta only ~23 ppm with ~4 people mean.
# This value is used ONLY for N recovery post-processing, not in the EKF ODEs.
M_ROOM = 240.0         # air mass of room [kg]  (tune from room dimensions)

# CO2 generation rate per person [ppm*kg/(s*person)]
# Calibrated from ROBOD Room 3 steady-state CO2 balance:
#   At steady state dc/dt=0: gamma_e = (m_sa/M)*(c_z - c_o)
#   gamma_e = g_CO2_occ * N / M  =>  g_CO2_occ = m_sa * (c_z - c_o) / N
#   m_sa=0.3 kg/s, delta_CO2=23 ppm, N=4 (median) -> g = 0.3*23/4 = 1.725
g_CO2_occ  = 1.725     # calibrated [ppm*kg/(s*person)]

# m_sa scaling: fcu_fan_speed [Hz] → mass flow [kg/s]
# Typical FCU: 50 Hz → ≈ 0.5 kg/s  →  k = 0.01  (tune after calibration)
FCU_FLOW_SCALE = 0.01

# ── State indices (10-state) ──────────────────────────────────────────────────
I_ao, I_as, I_ae = 0, 1, 2    # α parameters
I_bo, I_bs, I_be = 3, 4, 5    # β parameters   ← β_e RESTORED
I_ge             = 6           # γ_e
I_Tz, I_wz, I_cz = 7, 8, 9   # physical states ← ω_z RESTORED
N_STATES = 10


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def rh_to_humidity_ratio(rh_pct, T_C, P_atm=101325.0):
    """
    Convert Relative Humidity [%] and Temperature [°C] to
    Humidity Ratio ω [kg_water / kg_dry_air].

    Uses the Antoine equation for saturation pressure.
    """
    rh = np.clip(rh_pct / 100.0, 0.0, 1.0)
    # Magnus approximation for P_sat [Pa]
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    omega = 0.622 * (rh * P_sat) / (P_atm - rh * P_sat)
    return np.clip(omega, 0.0, 0.05)   # clip to physical range


def fan_speed_to_mass_flow(fan_hz):
    """
    Linear mapping: FCU fan speed [Hz] → supply air mass flow [kg/s].
    FCU_FLOW_SCALE is a proportionality constant (tune from duct measurements).
    """
    return np.clip(fan_hz * FCU_FLOW_SCALE, 0.001, None)   # min 0.001 to avoid /0


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA LOADER
# ═══════════════════════════════════════════════════════════════════════════════

def load_robod(path):
    """
    Load ROBOD CSV and extract all EKF inputs / measured states.

    Handles column naming differences between rooms:
      Room 1/2 — fcu_fan_speed [Hz]         (FCU units, no direct flow)
      Room 3/4  — supply_air_flow [CMH]      (AHU units, direct flow measurement)
                  supply_air_humidity [%]     (direct supply humidity)
                  ahu_fan_speed [Hz]

    Returns a DataFrame with standardised column names:
      T_z, w_z, c_z               ← zone states  (measured)
      T_o, w_o, c_o               ← outdoor inputs
      T_sa, w_sa, c_sa, m_sa      ← supply air inputs
      N_true                      ← ground-truth occupancy
      elapsed_s, dt               ← timing
    """
    print(f"    Loading: {path}")
    df = pd.read_csv(path)
    cols = list(df.columns)

    # ── Parse timestamps ──────────────────────────────────────────────────────
    df['datetime'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('datetime').reset_index(drop=True)
    df['elapsed_s'] = (df['datetime'] - df['datetime'].iloc[0]).dt.total_seconds()
    df['dt'] = df['elapsed_s'].diff().fillna(300.0)   # 5-min intervals = 300 s

    # ── Zone measured states ──────────────────────────────────────────────────
    df['T_z'] = df['air_temperature [Celsius]']
    df['c_z'] = df['indoor_co2 [ppm]']
    df['w_z'] = rh_to_humidity_ratio(
        df['indoor_relative_humidity [%]'].values,
        df['air_temperature [Celsius]'].values
    )

    # ── Outdoor inputs ────────────────────────────────────────────────────────
    df['T_o'] = df['dry_bulb_temp [Celsius]']
    df['c_o'] = df['outdoor_co2 [ppm]']
    df['w_o'] = rh_to_humidity_ratio(
        df['outdoor_relative_humidity [%]'].values,
        df['dry_bulb_temp [Celsius]'].values
    )

    # ── Supply air inputs ─────────────────────────────────────────────────────
    df['T_sa'] = df['supply_air_temperature [Celsius]']
    df['c_sa'] = df['outdoor_co2 [ppm]']   # fresh-air assumption

    if 'supply_air_humidity [%]' in cols:
        df['w_sa'] = rh_to_humidity_ratio(
            df['supply_air_humidity [%]'].values,
            df['supply_air_temperature [Celsius]'].values)
    else:
        df['w_sa'] = df['w_o']

    if 'supply_air_flow [CMH]' in cols:
        df['m_sa'] = (df['supply_air_flow [CMH]'].values / 3600.0 * 1.2).clip(min=0.001)
    elif 'fcu_fan_speed [Hz]' in cols:
        df['m_sa'] = fan_speed_to_mass_flow(df['fcu_fan_speed [Hz]'].values)
    elif 'ahu_fan_speed [Hz]' in cols:
        df['m_sa'] = fan_speed_to_mass_flow(df['ahu_fan_speed [Hz]'].values)
    else:
        print("    WARNING: No flow column — using constant m_sa = 0.3 kg/s")
        df['m_sa'] = 0.3

    # ── Ground truth occupancy ────────────────────────────────────────────────
    df['N_true'] = df['occupant_count [number]'].astype(float)

    # ── Drop NaN rows (some sensors may have gaps) ────────────────────────────
    cols_needed = ['T_z','w_z','c_z','T_o','w_o','c_o',
                   'T_sa','w_sa','c_sa','m_sa','N_true','elapsed_s','dt']
    df = df[cols_needed].dropna().reset_index(drop=True)

    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  EKF CORE  — 10-state
# ═══════════════════════════════════════════════════════════════════════════════

def predict_state(X_prev, inputs, dt):
    """
    f(X): Euler integration of the three zone ODEs.

    inputs = (T_o, w_o, c_o, T_sa, w_sa, c_sa, m_sa)

    Parameters (indices 0-6) follow a random walk → unchanged in prediction.
    Physical states (indices 7-9) are integrated one step forward.
    """
    T_o, w_o, c_o, T_sa, w_sa, c_sa, m_sa = inputs

    ao, a_s, ae = X_prev[I_ao], X_prev[I_as], X_prev[I_ae]
    bo, bs, be  = X_prev[I_bo], X_prev[I_bs], X_prev[I_be]
    ge          = X_prev[I_ge]
    Tz, wz, cz  = X_prev[I_Tz], X_prev[I_wz], X_prev[I_cz]

    # Temperature ODE  (Eq 1 compact form)
    Tz_pred = Tz + dt * (
        -(ao + m_sa * a_s) * Tz
        + ao * T_o
        + m_sa * a_s * T_sa
        + ae
    )

    # Humidity ODE  (Eq 2 compact form)  ← RESTORED
    wz_pred = wz + dt * (
        -(bo + m_sa * bs) * wz
        + bo * w_o
        + m_sa * bs * w_sa
        + be
    )

    # CO₂ ODE  (Eq 3 compact form)
    cz_pred = cz + dt * (
        -(bo + m_sa * bs) * cz
        + bo * c_o
        + m_sa * bs * c_sa
        + ge
    )

    X_pred = X_prev.copy()
    X_pred[I_Tz] = Tz_pred
    X_pred[I_wz] = wz_pred
    X_pred[I_cz] = cz_pred
    return X_pred


def jacobian_F(X_prev, inputs, dt):
    """
    10×10 Jacobian  F = I + dt·(∂f/∂X).

    Only the bottom 3 rows have off-diagonal entries.
    Top 7×7 block = Identity (random walk for parameters).

    Row layout:
      Row 7 (T_z): ∂f_T/∂[α_o, α_s, α_e, T_z]
      Row 8 (ω_z): ∂f_ω/∂[β_o, β_s, β_e, ω_z]        ← RESTORED
      Row 9 (c_z): ∂f_c/∂[β_o, β_s, γ_e, c_z]
    """
    T_o, w_o, c_o, T_sa, w_sa, c_sa, m_sa = inputs

    ao, a_s = X_prev[I_ao], X_prev[I_as]
    bo, bs  = X_prev[I_bo], X_prev[I_bs]
    Tz, wz, cz = X_prev[I_Tz], X_prev[I_wz], X_prev[I_cz]

    F = np.eye(N_STATES)

    # ── Row 7: Temperature ────────────────────────────────────────────────────
    F[I_Tz, I_ao] = dt * (-Tz + T_o)
    F[I_Tz, I_as] = dt * m_sa * (-Tz + T_sa)
    F[I_Tz, I_ae] = dt
    F[I_Tz, I_Tz] = 1.0 + dt * (-(ao + m_sa * a_s))

    # ── Row 8: Humidity  (RESTORED) ──────────────────────────────────────────
    F[I_wz, I_bo] = dt * (-wz + w_o)
    F[I_wz, I_bs] = dt * m_sa * (-wz + w_sa)
    F[I_wz, I_be] = dt
    F[I_wz, I_wz] = 1.0 + dt * (-(bo + m_sa * bs))

    # ── Row 9: CO₂ ───────────────────────────────────────────────────────────
    F[I_cz, I_bo] = dt * (-cz + c_o)
    F[I_cz, I_bs] = dt * m_sa * (-cz + c_sa)
    F[I_cz, I_ge] = dt                            # ∂f_c/∂γ_e = 1 (γ_e absorbs N)
    F[I_cz, I_cz] = 1.0 + dt * (-(bo + m_sa * bs))

    return F


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main(room_num=3, save_mode=False, results_dir=None, dataset_path=None):
    if save_mode:
        import matplotlib
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    if results_dir is None:
        results_dir = os.path.join(SCRIPT_DIR, f"results_robod_room{room_num}")
    robod_csv = dataset_path if dataset_path else os.path.join(ROBOD_DIR, f"combined_Room{room_num}.csv")

    print("=" * 60)
    print(f"  SmartBEM — 10-State EKF  (ROBOD Room {room_num})")
    print("=" * 60)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("\n[1] Loading ROBOD CSV ...")
    df = load_robod(robod_csv)
    steps = len(df)
    print(f"    {steps} rows | "
          f"T_z {df['T_z'].min():.1f}-{df['T_z'].max():.1f} C | "
          f"CO2 {df['c_z'].min():.0f}-{df['c_z'].max():.0f} ppm | "
          f"w_z {df['w_z'].min()*1000:.1f}-{df['w_z'].max()*1000:.1f} g/kg | "
          f"Occ 0-{df['N_true'].max():.0f}")

    # ── Extract arrays ────────────────────────────────────────────────────────
    T_z_meas = df['T_z'].values
    w_z_meas = df['w_z'].values
    c_z_meas = df['c_z'].values
    N_true   = df['N_true'].values
    elapsed  = df['elapsed_s'].values
    dt_arr   = df['dt'].values

    T_o_arr  = df['T_o'].values
    w_o_arr  = df['w_o'].values
    c_o_arr  = df['c_o'].values
    T_sa_arr = df['T_sa'].values
    w_sa_arr = df['w_sa'].values
    c_sa_arr = df['c_sa'].values
    m_sa_arr = df['m_sa'].values

    # ── EKF initialisation ────────────────────────────────────────────────────
    print("[2] EKF init ...")
    X_prev = np.array([
        1e-4,             # α_o  — heat leak + infiltration  [1/s]
        5e-4,             # α_s  — airflow/temp coupling      [1/(kg·s)]
        1e-3,             # α_e  — internal heat gains        [°C/s]
        1e-4,             # β_o  — infiltration moisture      [1/s]
        5.56e-3,          # β_s  — 1/M: room ~150m3, M=180kg, 1/180=0.00556 [1/kg]
        1e-6,             # β_e  — moisture internal source   [(kg_w/kg_a)/s]
        2e-3,             # γ_e  — CO2 source rate (~1 person in 150m3 room)  [ppm/s]
        T_z_meas[0],      # T_z  — from first measurement     [°C]
        w_z_meas[0],      # ω_z  — from first measurement     [kg_w/kg_a]
        c_z_meas[0],      # c_z  — from first measurement     [ppm]
    ])

    P_prev = np.diag([
        1e-4, 1e-4, 1e-4,    # α uncertainties
        1e-4, 1e-5, 1e-8,    # β_o | β_s tighter (we have a good physical init) | β_e
        1e-4,                 # γ_e
        1.0,                  # T_z [°C²]
        1e-5,                 # ω_z [(kg/kg)²]
        500.0,                # c_z [ppm²]
    ])

    # Process noise Q
    # gamma_e: use 1e-5 (compromise -- fast enough to track occupancy changes
    # over 5-15 min, but not so fast that individual CO2 fluctuations cause noise)
    Q = np.diag([
        1e-10, 1e-10, 1e-8,   # alpha -- change slowly (building physics, hours)
        1e-10, 1e-8,  1e-14,  # beta_o slow | beta_s medium | beta_e tiny
        1e-5,                  # gamma_e -- moderate speed for occupancy tracking
        0.01,                  # T_z
        1e-7,                  # w_z
        1.0,                   # c_z
    ])

    # Measurement noise R
    # CO2 R = 200 (+-14 ppm): trusts sensor more than default 400 to drive
    # gamma_e updates, but less aggressive than 100 to avoid amplifying noise.
    R = np.diag([
        0.25,    # T_z: +-0.5 deg C
        1e-6,    # w_z: +-0.001 kg/kg
        200.0,   # c_z: +-14 ppm
    ])

    # Measurement matrix H (3×10): picks T_z, ω_z, c_z from state vector
    H = np.zeros((3, N_STATES))
    H[0, I_Tz] = 1.0
    H[1, I_wz] = 1.0
    H[2, I_cz] = 1.0

    I_mat = np.eye(N_STATES)

    # ── Storage ───────────────────────────────────────────────────────────────
    est_arr   = np.zeros((steps, N_STATES))
    N_est_arr = np.zeros(steps)

    # N_WARMUP: skip first N steps for occupancy output.
    # 24 rows = 2 hours -- enough for c_z state to settle from init.
    # gamma_e now has high Q so it tracks quickly from the start.
    N_WARMUP = 24
    N_MAX    = 14.0    # Room 3 actual max = 13; allow 1 margin

    # ── EKF loop ──────────────────────────────────────────────────────────────
    print("[3] Running EKF ...")
    for k in range(steps):
        dt = dt_arr[k]

        inputs = (
            T_o_arr[k], w_o_arr[k], c_o_arr[k],
            T_sa_arr[k], w_sa_arr[k], c_sa_arr[k],
            m_sa_arr[k]
        )

        # === PREDICT ===
        X_pred = predict_state(X_prev, inputs, dt)
        F      = jacobian_F(X_prev, inputs, dt)
        P_pred = F @ P_prev @ F.T + Q * dt     # scale Q by dt

        # === UPDATE ===
        Z = np.array([T_z_meas[k], w_z_meas[k], c_z_meas[k]])
        y = Z - H @ X_pred
        S = H @ P_pred @ H.T + R
        K = P_pred @ H.T @ np.linalg.inv(S)

        X_est = X_pred + K @ y
        P_est = (I_mat - K @ H) @ P_pred

        # === STORE ===
        est_arr[k] = X_est

        # Recover occupancy from gamma_e using FIXED room air mass M_ROOM.
        # We do NOT use beta_s for this recovery because beta_s diverges in
        # this dataset (CO2 signal too weak to identify 1/M independently).
        # M_ROOM is set from known room geometry — it is a measurable constant.
        # N_est = gamma_e * M_ROOM / g_CO2_occ
        ge_est = X_est[I_ge]
        if k < N_WARMUP:
            N_est_arr[k] = 0.0
        else:
            raw = (ge_est * M_ROOM) / g_CO2_occ
            N_est_arr[k] = np.clip(raw, 0.0, N_MAX)

        # === CARRY FORWARD ===
        X_prev = X_est
        P_prev = P_est

    print("    Done.\n")

    # ── Post-process: smooth N_est with a rolling median (window=3 = 15 min) ──
    # Removes single-step CO2 noise spikes while preserving real step-transitions.
    from scipy.signal import medfilt
    N_est_arr = medfilt(N_est_arr, kernel_size=3)
    N_est_arr = np.clip(N_est_arr, 0.0, N_MAX)   # re-apply clip after filter

    # ── Derived physical parameters ───────────────────────────────────────────
    Cs_arr    = c_pa / np.where(np.abs(est_arr[:, I_as]) > 1e-12,
                                est_arr[:, I_as], np.nan)
    M_arr     = 1.0 / np.where(np.abs(est_arr[:, I_bs]) > 1e-12,
                                est_arr[:, I_bs], np.nan)
    m_inf_arr = est_arr[:, I_bo] * M_arr
    UA_arr    = est_arr[:, I_ao] * Cs_arr - c_pa * m_inf_arr

    # ── Time axis ─────────────────────────────────────────────────────────────
    t_hrs = elapsed / 3600.0


    # ── Limit to first 14 days (336 h) to avoid long-run drift issues ─────────
    T_MAX_HRS = 336
    mask   = t_hrs <= T_MAX_HRS
    t_plot = t_hrs[mask]

    def s(arr):
        """Slice array to plot window."""
        return arr[mask]

    # ── Plot definitions ──────────────────────────────────────────────────────
    if save_mode:
        os.makedirs(results_dir, exist_ok=True)

    MEAS  = {'style': '.', 'color': '#2ca02c', 'alpha': 0.6, 'lw': 0,   'ms': 1.5}
    EKF   = {'style': '--','color': '#ff7f0e', 'alpha': 0.8, 'lw': 1.2}
    PARAM = {'style': '--','color': '#1f77b4', 'alpha': 0.8, 'lw': 1.2}

    plot_defs = [
        # ── Tracked states ──────────────────────────────────────────────────
        ('01_zone_temp.png', 'Zone Temperature', '°C', [
            {**MEAS, 'y': s(T_z_meas),          'label': 'Measured'},
            {**EKF,  'y': s(est_arr[:, I_Tz]),  'label': 'EKF'}]),
        ('02_zone_humidity.png', 'Zone Humidity Ratio', 'kg_w/kg_a', [
            {**MEAS, 'y': s(w_z_meas),           'label': 'Measured'},
            {**EKF,  'y': s(est_arr[:, I_wz]),   'label': 'EKF'}]),
        ('03_zone_co2.png', 'Zone CO₂', 'ppm', [
            {**MEAS, 'y': s(c_z_meas),            'label': 'Measured'},
            {**EKF,  'y': s(est_arr[:, I_cz]),    'label': 'EKF'}]),
        # ── Occupancy ───────────────────────────────────────────────────────
        ('04_occupancy.png', 'Occupancy (recovered vs truth)', 'persons', [
            {**MEAS, 'y': s(N_true),              'label': 'True N'},
            {**EKF,  'y': s(N_est_arr),           'label': 'EKF N'}]),
        # ── Outdoor inputs ──────────────────────────────────────────────────
        ('05_outdoor_temp.png', 'Outdoor Temperature (real)', '°C', [
            {**PARAM,'y': s(T_o_arr),             'label': 'T_o (ROBOD)'}]),
        # ── α parameters ───────────────────────────────────────────────────
        ('06_alpha_o.png', 'α_o (heat leak + infiltration)', '1/s', [
            {**PARAM,'y': s(est_arr[:, I_ao]),    'label': 'α_o'}]),
        ('07_alpha_s.png', 'α_s (airflow / temp coupling)', '1/(kg·s)', [
            {**PARAM,'y': s(est_arr[:, I_as]),    'label': 'α_s'}]),
        ('08_alpha_e.png', 'α_e (internal heat gains)', '°C/s', [
            {**PARAM,'y': s(est_arr[:, I_ae]),    'label': 'α_e'}]),
        # ── β parameters ───────────────────────────────────────────────────
        ('09_beta_o.png', 'β_o (infiltration moisture/CO₂)', '1/s', [
            {**PARAM,'y': s(est_arr[:, I_bo]),    'label': 'β_o'}]),
        ('10_beta_s.png', 'β_s (1/air mass)', '1/kg', [
            {**PARAM,'y': s(est_arr[:, I_bs]),    'label': 'β_s'}]),
        ('11_beta_e.png', 'β_e (moisture internal source)', '(kg/kg)/s', [
            {**PARAM,'y': s(est_arr[:, I_be]),    'label': 'β_e'}]),
        ('12_gamma_e.png', 'γ_e (CO₂ source rate)', 'ppm/s', [
            {**PARAM,'y': s(est_arr[:, I_ge]),    'label': 'γ_e'}]),
        # ── Derived physical quantities ─────────────────────────────────────
        ('13_thermal_cap.png', 'C_s (thermal capacitance)', 'J/K', [
            {**PARAM,'y': s(Cs_arr),              'label': 'C_s'}]),
        ('14_UA.png', 'UA (heat transfer coefficient)', 'W/K', [
            {**PARAM,'y': s(UA_arr),              'label': 'UA'}]),
    ]

    for fname, title, ylabel, traces in plot_defs:
        fig, ax = plt.subplots(figsize=(9, 4))
        for tr in traces:
            kw = dict(alpha=tr.get('alpha', 1),
                      lw=tr.get('lw', 1),
                      label=tr.get('label', ''),
                      color=tr['color'])
            if 'ms' in tr:
                kw['markersize'] = tr['ms']
            ax.plot(t_plot, tr['y'], tr['style'], **kw)
        ax.set_title(f"{title}  [ROBOD Room {room_num}]")
        ax.set_xlabel('Time [hours]')
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_mode:
            fig.savefig(os.path.join(results_dir, fname), dpi=150, bbox_inches='tight')
            plt.close(fig)

    if save_mode:
        try:
            res_df = pd.DataFrame({
                'time_hrs': t_plot,
                'T_z_measured': s(T_z_meas),
                'T_z_ekf': s(est_arr[:, I_Tz]),
                'w_z_measured': s(w_z_meas),
                'w_z_ekf': s(est_arr[:, I_wz]),
                'c_z_measured': s(c_z_meas),
                'c_z_ekf': s(est_arr[:, I_cz]),
                'N_true': s(N_true),
                'N_ekf': s(N_est_arr),
                'T_o': s(T_o_arr),
                'alpha_o': s(est_arr[:, I_ao]),
                'alpha_s': s(est_arr[:, I_as]),
                'alpha_e': s(est_arr[:, I_ae]),
                'beta_o': s(est_arr[:, I_bo]),
                'beta_s': s(est_arr[:, I_bs]),
                'beta_e': s(est_arr[:, I_be]),
                'gamma_e': s(est_arr[:, I_ge]),
                'C_s': s(Cs_arr),
                'UA': s(UA_arr)
            })
            csv_out_path = os.path.join(results_dir, "ekf_results.csv")
            res_df.to_csv(csv_out_path, index=False)
            print(f"    Saved EKF results CSV -> {csv_out_path}")
        except Exception as e:
            print(f"    Failed to save EKF results CSV: {e}")
            
        print(f"    Saved 14 plots -> {results_dir}")
    else:
        plt.show()


if __name__ == "__main__":
    import sys
    cli_save_mode = '--save' in sys.argv
    cli_room_num = 3
    for i, arg in enumerate(sys.argv):
        if arg == '--room' and i + 1 < len(sys.argv):
            cli_room_num = int(sys.argv[i + 1])
    main(room_num=cli_room_num, save_mode=cli_save_mode)
