"""
Diagnostic: find correct g_CO2_occ for Room 3 by doing a steady-state CO2 balance.
Also runs the full EKF and prints what beta_s and gamma_e actually converge to,
so we can back-calculate the right g_CO2_occ.
"""
import numpy as np
import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(SCRIPT_DIR,
    "Datasets for EKF",
    "ROBOD, Room level Occupancy and Building Operation Dataset",
    "combined_Room3.csv")

# ── helpers ───────────────────────────────────────────────────────────────────
def rh_to_hr(rh_pct, T_C, P=101325.0):
    rh = np.clip(rh_pct / 100.0, 0.0, 1.0)
    Psat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    return np.clip(0.622 * rh * Psat / (P - rh * Psat), 0.0, 0.05)

# ── load ──────────────────────────────────────────────────────────────────────
df = pd.read_csv(CSV)
df['datetime']  = pd.to_datetime(df['timestamp'], utc=True)
df = df.sort_values('datetime').reset_index(drop=True)
df['elapsed_s'] = (df['datetime'] - df['datetime'].iloc[0]).dt.total_seconds()
df['dt']        = df['elapsed_s'].diff().fillna(300.0)

df['T_z'] = df['air_temperature [Celsius]']
df['c_z']  = df['indoor_co2 [ppm]']
df['w_z']  = rh_to_hr(df['indoor_relative_humidity [%]'].values,
                       df['air_temperature [Celsius]'].values)
df['T_o'] = df['dry_bulb_temp [Celsius]']
df['c_o']  = df['outdoor_co2 [ppm]']
df['T_sa'] = df['supply_air_temperature [Celsius]']
df['c_sa'] = df['outdoor_co2 [ppm]']
df['m_sa'] = (df['supply_air_flow [CMH]'].values / 3600.0 * 1.2).clip(min=0.001)
df['N_true'] = df['occupant_count [number]'].astype(float)

cols = ['T_z','c_z','w_z','T_o','c_o','T_sa','c_sa','m_sa','N_true','elapsed_s','dt']
df = df[cols].dropna().reset_index(drop=True)

print(f"Rows: {len(df)}")
print(f"N_true  max={df['N_true'].max():.0f}  mean(occ)={df.loc[df['N_true']>0,'N_true'].mean():.1f}")
print(f"CO2:    max={df['c_z'].max():.0f}  mean(occ)={df.loc[df['N_true']>0,'c_z'].mean():.1f}  mean(empty)={df.loc[df['N_true']==0,'c_z'].mean():.1f}")
print()

# ── Steady-state CO2 balance approach ────────────────────────────────────────
# At steady state (dc_z/dt = 0):
#   0 = -(beta_o + m_sa*beta_s)*c_z + beta_o*c_o + m_sa*beta_s*c_sa + gamma_e
# Assume beta_o << m_sa*beta_s (infiltration small vs supply), c_sa = c_o:
#   gamma_e ≈ m_sa * beta_s * (c_z - c_o)
# And gamma_e = g_CO2_occ * N * beta_s
# → g_CO2_occ = m_sa * (c_z - c_o) / N

# Use median of occupied periods (more robust than mean)
occ = df[df['N_true'] > 0].copy()
occ['delta_co2'] = occ['c_z'] - occ['c_o']
occ['g_implied']  = occ['m_sa'] * occ['delta_co2'] / occ['N_true']

print("Steady-state back-calculation of g_CO2_occ:")
print(f"  delta_CO2 median (occ)   = {occ['delta_co2'].median():.1f} ppm")
print(f"  m_sa median (occ)        = {occ['m_sa'].median():.4f} kg/s")
print(f"  N_true median (occ)      = {occ['N_true'].median():.1f}")
print(f"  g_CO2_occ implied median = {occ['g_implied'].median():.4f} ppm*kg/(s*person)")
print(f"  g_CO2_occ implied mean   = {occ['g_implied'].mean():.4f} ppm*kg/(s*person)")
print()

# Check by N bucket
for n in sorted(occ['N_true'].unique()):
    sub = occ[occ['N_true'] == n]
    if len(sub) < 5:
        continue
    g = (sub['m_sa'] * sub['delta_co2'] / n).median()
    print(f"  N={n:2.0f}  count={len(sub):4d}  g_implied={g:.4f}")

print()
# ── Now run EKF and check beta_s and gamma_e convergence ─────────────────────
print("Running EKF to check beta_s / gamma_e convergence...")

I_ao,I_as,I_ae = 0,1,2
I_bo,I_bs,I_be = 3,4,5
I_ge            = 6
I_Tz,I_wz,I_cz = 7,8,9
N_STATES = 10

T_z_meas = df['T_z'].values
c_z_meas = df['c_z'].values
w_z_meas = df['w_z'].values
N_true   = df['N_true'].values
dt_arr   = df['dt'].values
T_o_arr  = df['T_o'].values
c_o_arr  = df['c_o'].values
T_sa_arr = df['T_sa'].values
c_sa_arr = df['c_sa'].values
m_sa_arr = df['m_sa'].values
w_sa_arr = np.zeros_like(T_sa_arr)  # simplified for diag

X = np.array([1e-4, 5e-4, 1e-3, 1e-4, 5.56e-3, 1e-6, 2e-3,
              T_z_meas[0], w_z_meas[0], c_z_meas[0]])
P = np.diag([1e-4,1e-4,1e-4, 1e-4,1e-5,1e-8, 1e-4, 1.0,1e-5,500.0])
Q = np.diag([1e-10,1e-10,1e-8, 1e-10,1e-8,1e-14, 1e-7, 0.01,1e-7,1.0])
R = np.diag([0.25, 1e-6, 400.0])
H = np.zeros((3,N_STATES)); H[0,I_Tz]=1; H[1,I_wz]=1; H[2,I_cz]=1
Im = np.eye(N_STATES)

bs_arr = np.zeros(len(df))
ge_arr = np.zeros(len(df))

for k in range(len(df)):
    dt = dt_arr[k]
    T_o,c_o,T_sa,c_sa,m_sa = T_o_arr[k],c_o_arr[k],T_sa_arr[k],c_sa_arr[k],m_sa_arr[k]
    ao,a_s,ae = X[I_ao],X[I_as],X[I_ae]
    bo,bs,be  = X[I_bo],X[I_bs],X[I_be]
    ge        = X[I_ge]
    Tz,wz,cz  = X[I_Tz],X[I_wz],X[I_cz]

    # predict
    Xp = X.copy()
    Xp[I_Tz] = Tz + dt*(-(ao+m_sa*a_s)*Tz + ao*T_o + m_sa*a_s*T_sa + ae)
    Xp[I_wz] = wz + dt*(-(bo+m_sa*bs)*wz + bo*0.015 + m_sa*bs*0.015 + be)
    Xp[I_cz] = cz + dt*(-(bo+m_sa*bs)*cz + bo*c_o  + m_sa*bs*c_sa  + ge)

    F = np.eye(N_STATES)
    F[I_Tz,I_ao]=dt*(-Tz+T_o); F[I_Tz,I_as]=dt*m_sa*(-Tz+T_sa)
    F[I_Tz,I_ae]=dt; F[I_Tz,I_Tz]=1+dt*(-(ao+m_sa*a_s))
    F[I_wz,I_bo]=dt*(-wz+0.015); F[I_wz,I_bs]=dt*m_sa*(-wz+0.015)
    F[I_wz,I_be]=dt; F[I_wz,I_wz]=1+dt*(-(bo+m_sa*bs))
    F[I_cz,I_bo]=dt*(-cz+c_o); F[I_cz,I_bs]=dt*m_sa*(-cz+c_sa)
    F[I_cz,I_ge]=dt; F[I_cz,I_cz]=1+dt*(-(bo+m_sa*bs))
    Pp = F@P@F.T + Q*dt

    # update
    Z = np.array([T_z_meas[k], w_z_meas[k], c_z_meas[k]])
    y = Z - H@Xp
    S = H@Pp@H.T + R
    K = Pp@H.T@np.linalg.inv(S)
    X  = Xp + K@y
    P  = (Im - K@H)@Pp

    bs_arr[k] = X[I_bs]
    ge_arr[k] = X[I_ge]

# After warmup: what are beta_s and gamma_e at occupied times?
WARMUP = 200
occ_mask = (N_true > 0) & (np.arange(len(df)) >= WARMUP)
bs_occ = bs_arr[occ_mask]
ge_occ = ge_arr[occ_mask]
N_occ  = N_true[occ_mask]

print(f"  beta_s  converged median = {np.median(bs_occ):.6f} (M={1/np.median(bs_occ):.0f} kg)")
print(f"  gamma_e converged median = {np.median(ge_occ):.6f} ppm/s")
print()

# What g_CO2_occ do we need?
# N_est = gamma_e / (g_CO2_occ * beta_s) should equal N_true
# g_CO2_occ = gamma_e / (N_true * beta_s)
g_needed = ge_occ / (N_occ * bs_occ)
print(f"  g_CO2_occ needed (median) = {np.nanmedian(g_needed):.4f}")
print(f"  g_CO2_occ needed (mean)   = {np.nanmean(g_needed[np.isfinite(g_needed)]):.4f}")
print()
print(f"  With g_CO2_occ={np.nanmedian(g_needed):.3f}: N_est for median beta_s/gamma_e =",
      np.median(ge_occ) / (np.nanmedian(g_needed) * np.median(bs_occ)))
