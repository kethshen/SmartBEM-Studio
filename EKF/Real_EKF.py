"""
SmartHVAC FYP — 8-State EKF with Real Data
===========================================
States:  X = [α_o, α_s, α_e, β_o, β_s, γ_e, T_z, c_z]
Measurements:  Z = [T_z, c_z]  (Kaggle dataset)
Inputs:  T_o (EPW), T_sa / c_sa / m_sa (pseudo constants)

Naming convention:  _prev, _pred, _est  (from practice demos)
"""

import numpy as np
import pandas as pd
import sys

SAVE_MODE = '--save' in sys.argv
if SAVE_MODE:
    import matplotlib
    matplotlib.use('Agg')

import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

# ========================= CONFIGURATION =========================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KAGGLE_CSV = os.path.join(SCRIPT_DIR,
    "Datasets for EKF", "Room Occupancy Estimation Keggle",
    "Occupancy_Estimation.csv")
EPW_FILE = os.path.join(os.path.dirname(SCRIPT_DIR),
    "colab", "weather",
    "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")

# physical constant
c_pa = 1006.0                    # specific heat of air [J/(kg·K)]

# CO₂ generation rate per person [ppm·kg/(s·person)]
# ~0.004 L/s CO₂ per person × air density 1.2 kg/m³ → ≈ 4.8
g_CO2_occ = 5.0

# pseudo supply-air constants (typical small office AHU)
T_SA  = 16.0     # supply air temperature   [°C]
C_SA  = 420.0    # supply air CO₂           [ppm]
C_O   = 420.0    # outdoor CO₂ (constant)   [ppm]
M_SA  = 0.3      # supply air mass flow      [kg/s]

# state indices (8-state)
I_ao, I_as, I_ae = 0, 1, 2       # α parameters
I_bo, I_bs       = 3, 4          # β parameters
I_ge             = 5             # γ_e
I_Tz, I_cz       = 6, 7          # physical states
N_STATES = 8


# ========================= DATA LOADING =========================
def load_kaggle(path):
    """Load Kaggle Room Occupancy CSV → DataFrame with T_z, c_z, N_true."""
    df = pd.read_csv(path)
    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
    df['T_z']    = df[['S1_Temp','S2_Temp','S3_Temp','S4_Temp']].mean(axis=1)
    df['c_z']    = df['S5_CO2'].astype(float)
    df['N_true'] = df['Room_Occupancy_Count'].astype(float)
    df['elapsed_s'] = (df['datetime'] - df['datetime'].iloc[0]).dt.total_seconds()
    df['dt'] = df['elapsed_s'].diff().fillna(30.0)
    return df


def load_epw_To(path):
    """Extract hourly dry-bulb T_o from EPW (column 7, 0-indexed col 6)."""
    rows = []
    with open(path, 'r') as f:
        for i, line in enumerate(f):
            if i < 8:
                continue
            flds = line.strip().split(',')
            yr, mo, dy, hr = int(flds[0]), int(flds[1]), int(flds[2]), int(flds[3])
            T_db = float(flds[6])
            dt_obj = datetime(yr, mo, dy) + timedelta(hours=hr - 1)
            rows.append((dt_obj, mo, dy, hr, T_db))
    epw = pd.DataFrame(rows, columns=['datetime','month','day','hour','T_o'])
    return epw


def interpolate_To(epw, kaggle_df):
    """Linearly interpolate hourly EPW T_o to Kaggle ~30 s timestamps.
    
    EPW uses TMY years (e.g. 1981/1986), Kaggle uses 2017/2018.
    We align by month/day/hour, ignoring year.
    """
    # filter EPW to Dec 22 - Jan 11
    mask = ((epw['month'] == 12) & (epw['day'] >= 22)) | \
           ((epw['month'] == 1)  & (epw['day'] <= 11))
    sub = epw[mask].copy().reset_index(drop=True)

    # build a synthetic elapsed-seconds axis using a common reference year
    # Dec 22 = day 0, Jan 11 = day 20  (spanning year boundary)
    def to_elapsed(mo, dy, hr):
        if mo == 12:
            day_offset = dy - 22
        else:  # January
            day_offset = (31 - 22) + dy   # 9 days of Dec + Jan days
        return day_offset * 86400 + (hr - 1) * 3600

    epw_elapsed = np.array([to_elapsed(r.month, r.day, r.hour) for _, r in sub.iterrows()])

    # same for Kaggle timestamps
    kaggle_dts = kaggle_df['datetime']
    def kaggle_to_elapsed(dt_obj):
        mo, dy = dt_obj.month, dt_obj.day
        if mo == 12:
            day_offset = dy - 22
        else:
            day_offset = (31 - 22) + dy
        seconds_in_day = dt_obj.hour * 3600 + dt_obj.minute * 60 + dt_obj.second
        return day_offset * 86400 + seconds_in_day

    kaggle_elapsed = np.array([kaggle_to_elapsed(dt) for dt in kaggle_dts])

    return np.interp(kaggle_elapsed, epw_elapsed, sub['T_o'].values)


# ========================= EKF CORE =========================
def predict_state(X_prev, T_o, m_sa, dt):
    """f(X): predict next state. Parameters unchanged (random walk)."""
    ao, a_s, ae = X_prev[I_ao], X_prev[I_as], X_prev[I_ae]
    bo, bs      = X_prev[I_bo], X_prev[I_bs]
    ge          = X_prev[I_ge]
    Tz, cz      = X_prev[I_Tz], X_prev[I_cz]

    Tz_pred = Tz + dt * (-(ao + m_sa*a_s)*Tz + ao*T_o + m_sa*a_s*T_SA + ae)
    cz_pred = cz + dt * (-(bo + m_sa*bs)*cz  + bo*C_O + m_sa*bs*C_SA  + ge)

    X_pred = X_prev.copy()
    X_pred[I_Tz] = Tz_pred
    X_pred[I_cz] = cz_pred
    return X_pred


def jacobian_F(X_prev, T_o, m_sa, dt):
    """8×8 Jacobian  F = I + dt·(∂f/∂X)."""
    ao, a_s = X_prev[I_ao], X_prev[I_as]
    bo, bs  = X_prev[I_bo], X_prev[I_bs]
    Tz, cz  = X_prev[I_Tz], X_prev[I_cz]

    F = np.eye(N_STATES)

    # row I_Tz  (temperature sensitivities)
    F[I_Tz, I_ao] = dt * (-Tz + T_o)
    F[I_Tz, I_as] = dt * m_sa * (-Tz + T_SA)
    F[I_Tz, I_ae] = dt
    F[I_Tz, I_Tz] = 1 + dt * (-(ao + m_sa*a_s))

    # row I_cz  (CO₂ sensitivities)  — includes β_o, β_s entries (Bug 2 fix)
    F[I_cz, I_bo] = dt * (-cz + C_O)
    F[I_cz, I_bs] = dt * m_sa * (-cz + C_SA)
    F[I_cz, I_ge] = dt                           # Bug 1 fix: dt, not dt*N
    F[I_cz, I_cz] = 1 + dt * (-(bo + m_sa*bs))

    return F


# ========================= MAIN =========================
def main():
    print("=" * 60)
    print("  SmartHVAC — 8-State EKF  (Real Data)")
    print("=" * 60)

    # ---------- load data ----------
    print("\n[1] Loading Kaggle CSV ...")
    kdf = load_kaggle(KAGGLE_CSV)
    steps = len(kdf)
    print(f"    {steps} rows | T_z {kdf['T_z'].min():.1f}-{kdf['T_z'].max():.1f} C"
          f" | CO2 {kdf['c_z'].min():.0f}-{kdf['c_z'].max():.0f} ppm"
          f" | Occ 0-{kdf['N_true'].max():.0f}")

    print("[2] Loading EPW outdoor temp ...")
    epw = load_epw_To(EPW_FILE)
    T_o_arr = interpolate_To(epw, kdf)
    print(f"    T_o {T_o_arr.min():.1f}-{T_o_arr.max():.1f} C (interpolated)")

    # ---------- arrays ----------
    T_z_meas = kdf['T_z'].values
    c_z_meas = kdf['c_z'].values
    N_true   = kdf['N_true'].values
    dt_arr   = kdf['dt'].values
    elapsed  = kdf['elapsed_s'].values

    # ---------- EKF init ----------
    print("[3] EKF init ...")
    X_prev = np.array([
        0.01,              # α_o
        0.005,             # α_s
        0.01,              # α_e
        0.01,              # β_o
        0.01,              # β_s
        0.5,               # γ_e
        T_z_meas[0],       # T_z  (from first measurement)
        c_z_meas[0],       # c_z  (from first measurement)
    ])

    P_prev = np.diag([
        0.1, 0.1, 0.1,    # α uncertainties
        0.1, 0.1,          # β uncertainties
        1.0,               # γ_e (more uncertain)
        1.0,               # T_z
        100.0,             # c_z (ppm scale)
    ])

    Q = np.diag([
        1e-6, 1e-6, 1e-4,     # α (α_e drifts with occupancy)
        1e-6, 1e-6,            # β
        1e-3,                  # γ_e (changes with occupancy)
        0.01,                  # T_z
        1.0,                   # c_z
    ])

    R = np.diag([0.25, 400.0])   # T_z (±0.5°C), c_z (±20 ppm)

    H = np.zeros((2, N_STATES))
    H[0, I_Tz] = 1.0
    H[1, I_cz] = 1.0

    I_mat = np.eye(N_STATES)

    # ---------- storage ----------
    est_arr   = np.zeros((steps, N_STATES))
    N_est_arr = np.zeros(steps)

    # ---------- EKF loop ----------
    print("[4] Running EKF ...")
    for k in range(steps):
        dt = dt_arr[k]
        T_o_k  = T_o_arr[k]
        m_sa_k = M_SA

        # === PREDICT ===
        X_pred = predict_state(X_prev, T_o_k, m_sa_k, dt)
        F      = jacobian_F(X_prev, T_o_k, m_sa_k, dt)
        P_pred = F @ P_prev @ F.T + Q * dt     # scale Q by dt

        # === UPDATE ===
        Z = np.array([T_z_meas[k], c_z_meas[k]])
        y = Z - H @ X_pred
        S = H @ P_pred @ H.T + R
        K = P_pred @ H.T @ np.linalg.inv(S)

        X_est = X_pred + K @ y
        P_est = (I_mat - K @ H) @ P_pred

        # === STORE ===
        est_arr[k] = X_est
        bs_est = X_est[I_bs]
        ge_est = X_est[I_ge]
        if abs(bs_est) > 1e-10:
            M_est = 1.0 / bs_est
            N_est_arr[k] = max(0, (ge_est * M_est) / g_CO2_occ)
        else:
            N_est_arr[k] = 0.0

        # === CARRY FORWARD ===
        X_prev = X_est
        P_prev = P_est

    print("    Done.\n")

    # ---------- derived physical parameters ----------
    Cs_arr    = c_pa / est_arr[:, I_as]
    M_arr     = 1.0 / est_arr[:, I_bs]
    m_inf_arr = est_arr[:, I_bo] * M_arr
    UA_arr    = est_arr[:, I_ao] * Cs_arr - c_pa * m_inf_arr

    # ---------- time axis in hours ----------
    t_hrs = elapsed / 3600.0

    # ========================= PLOTS =========================
    RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
    if SAVE_MODE:
        os.makedirs(RESULTS_DIR, exist_ok=True)

    # ---- Limit time range to avoid late-time outliers ----
    T_MAX_HRS = 120
    mask = t_hrs <= T_MAX_HRS
    t_plot = t_hrs[mask]

    # Slice all plot data to the mask
    T_z_meas_p   = T_z_meas[mask]
    c_z_meas_p   = c_z_meas[mask]
    N_true_p     = N_true[mask]
    N_est_p      = N_est_arr[mask]
    T_o_p        = T_o_arr[mask]
    est_p        = est_arr[mask]
    Cs_p         = Cs_arr[mask]
    UA_p         = UA_arr[mask]

    # Define all 12 plots: (filename, title, ylabel, traces[])
    plot_defs = [
        ('01_zone_temp.png', 'Zone Temperature', 'deg C', [
            {'y': T_z_meas_p, 'style': '.', 'color': '#2ca02c', 'alpha': 0.7, 'lw': 0, 'ms': 1.5, 'label': 'Measured'},
            {'y': est_p[:, I_Tz], 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'EKF'}]),
        ('02_zone_co2.png', 'Zone CO2', 'ppm', [
            {'y': c_z_meas_p, 'style': '.', 'color': '#2ca02c', 'alpha': 0.7, 'lw': 0, 'ms': 1.5, 'label': 'Measured'},
            {'y': est_p[:, I_cz], 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'EKF'}]),
        ('03_occupancy.png', 'Occupancy N (recovered vs truth)', 'persons', [
            {'y': N_true_p, 'style': '.', 'color': '#2ca02c', 'alpha': 0.7, 'lw': 0, 'ms': 1.5, 'label': 'True N'},
            {'y': N_est_p, 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'EKF N'}]),
        ('04_outdoor_temp.png', 'Outdoor Temperature (input)', 'deg C', [
            {'y': T_o_p, 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'T_o (EPW)'}]),
        ('05_alpha_o.png', 'alpha_o (heat leak + infiltration)', '1/s', [
            {'y': est_p[:, I_ao], 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'alpha_o'}]),
        ('06_alpha_s.png', 'alpha_s (airflow effect on temp)', '1/(kg.s)', [
            {'y': est_p[:, I_as], 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'alpha_s'}]),
        ('07_alpha_e.png', 'alpha_e (internal heat gains)', 'deg C/s', [
            {'y': est_p[:, I_ae], 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'alpha_e'}]),
        ('08_beta_o.png', 'beta_o (infiltration CO2)', '1/s', [
            {'y': est_p[:, I_bo], 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'beta_o'}]),
        ('09_beta_s.png', 'beta_s (air capacity)', '1/kg', [
            {'y': est_p[:, I_bs], 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'beta_s'}]),
        ('10_gamma_e.png', 'gamma_e (CO2 source)', 'ppm/s', [
            {'y': est_p[:, I_ge], 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'gamma_e'}]),
        ('11_thermal_cap.png', 'C_s (thermal capacitance)', 'J/K', [
            {'y': Cs_p, 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'C_s'}]),
        ('12_UA.png', 'UA (heat transfer coeff)', 'W/K', [
            {'y': UA_p, 'style': '--', 'color': '#ff7f0e', 'alpha': 0.7, 'lw': 1.2, 'label': 'UA'}]),
    ]

    for fname, title, ylabel, traces in plot_defs:
        fig, ax = plt.subplots(figsize=(8, 4))
        for tr in traces:
            kwargs = dict(alpha=tr.get('alpha', 1), lw=tr.get('lw', 1),
                          label=tr.get('label', ''))
            if 'color' in tr:
                kwargs['color'] = tr['color']
            if 'ms' in tr:
                kwargs['markersize'] = tr['ms']
            ax.plot(t_plot, tr['y'], tr['style'], **kwargs)
        ax.set_title(title)
        ax.set_xlabel('Time [hours]')
        ax.set_ylabel(ylabel)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        if SAVE_MODE:
            fig.savefig(os.path.join(RESULTS_DIR, fname), dpi=150, bbox_inches='tight')
            plt.close(fig)

    if SAVE_MODE:
        print(f"    Saved 12 plots to {RESULTS_DIR}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
