"""
SmartBEM Studio — ROBOD EKF Bayesian Optimization Hyperparameter Auto-Tuner
=============================================================================
Implements Bayesian Optimization using Gaussian Process Regression (scikit-learn)
and Expected Improvement (EI) acquisition function to auto-tune EKF process noise Q
and measurement noise R matrices across all 5 ROBOD room datasets.

Search Space:
  Θ = [log10(Q_ao), log10(Q_as), log10(Q_bo), log10(Q_bs), log10(Q_ge), log10(R_Tz), log10(R_cz)]

Objective Function:
  J(Θ) = RMSE(Tz) + 0.002 * RMSE(cz) + 0.0001 * Mean(Innovation_sq)
"""

import numpy as np
import pandas as pd
import os
import sys
from scipy.stats import norm
from scipy.optimize import minimize as scipy_minimize
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel

# Add paths to robod_single_ekf and robod_dual_ekf
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SINGLE_EKF_DIR = os.path.join(SCRIPT_DIR, "robod_single_ekf")
DUAL_EKF_DIR   = os.path.join(SCRIPT_DIR, "robod_dual_ekf")

sys.path.append(SINGLE_EKF_DIR)
import robod_single_ekf as single

ROBOD_DIR = r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\EKF\Datasets for EKF\ROBOD, Room level Occupancy and Building Operation Dataset"

def evaluate_single_ekf_cost(log_params, df, room_spec):
    """
    Evaluates Single-EKF cost J(Theta) for a candidate log10 hyperparameter vector.
    log_params: [log10(Q_ao), log10(Q_as), log10(Q_bo), log10(Q_bs), log10(Q_ge), log10(R_Tz), log10(R_cz)]
    """
    q_ao, q_as, q_bo, q_bs, q_ge, r_Tz, r_cz = 10.0**log_params

    # Run modified EKF pass with candidate noise matrices
    df_clean = df.copy()
    for col in df_clean.columns:
        if df_clean[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
            df_clean[col] = df_clean[col].ffill().bfill()

    N = len(df_clean)
    v_room = room_spec["volume"]
    M_room = v_room * single.rho_air
    Cs_nom = room_spec["Cs"]
    UA_nom = room_spec["UA"]

    if "baromatic_pressure [hPa]" in df_clean.columns:
        P_live_arr = df_clean["baromatic_pressure [hPa]"].fillna(1013.25).values * 100.0
    else:
        P_live_arr = np.full(N, 101325.0)

    To = df_clean["dry_bulb_temp [Celsius]"].fillna(28.0).values
    RHo = df_clean["outdoor_relative_humidity [%]"].fillna(75.0).values
    wo = np.array([single.rh_to_humidity_ratio(RHo[i], To[i], P_live_arr[i]) for i in range(N)])
    co = df_clean["outdoor_co2 [ppm]"].fillna(400.0).values

    Tsa = df_clean["supply_air_temperature [Celsius]"].fillna(18.0).values
    if "supply_air_humidity [%]" in df_clean.columns:
        RHsa = df_clean["supply_air_humidity [%]"].fillna(85.0).values
    else:
        RHsa = RHo.copy()
    wsa = np.array([single.rh_to_humidity_ratio(RHsa[i], Tsa[i], P_live_arr[i]) for i in range(N)])

    if "supply_air_flow [CMH]" in df_clean.columns:
        msa = df_clean["supply_air_flow [CMH]"].fillna(0.0).values * (single.rho_air / 3600.0)
    elif "fcu_fan_speed [Hz]" in df_clean.columns:
        msa = (df_clean["fcu_fan_speed [Hz]"].fillna(0.0).values / 50.0) * 0.15
    else:
        msa = np.full(N, 0.05)

    Tz_meas = df_clean["air_temperature [Celsius]"].values
    RHz_meas = df_clean["indoor_relative_humidity [%]"].values
    cz_meas = df_clean["indoor_co2 [ppm]"].values
    wz_meas = np.array([single.rh_to_humidity_ratio(RHz_meas[i], Tz_meas[i], P_live_arr[i]) for i in range(N)])

    X = np.zeros(single.N_STATES)
    X[single.I_ao] = (UA_nom + single.c_pa * (3e-6 * M_room)) / Cs_nom
    X[single.I_as] = single.c_pa / Cs_nom
    X[single.I_ae] = 0.0000
    X[single.I_bo] = 3.06e-6
    X[single.I_bs] = 1.0 / M_room
    X[single.I_be] = 0.0000
    X[single.I_ge] = 0.05
    X[single.I_Tz] = Tz_meas[0]
    X[single.I_wz] = wz_meas[0]
    X[single.I_cz] = cz_meas[0]

    P = np.eye(single.N_STATES) * 0.1
    P[single.I_ge, single.I_ge] = 1.0

    Q_base = np.diag([q_ao, q_as, 1e-7, q_bo, q_bs, 1e-7, q_ge, 1e-2, 1e-6, 1.0])
    R = np.diag([r_Tz, 0.0002**2, r_cz])

    H = np.zeros((3, single.N_STATES))
    H[0, single.I_Tz] = 1.0
    H[1, single.I_wz] = 1.0
    H[2, single.I_cz] = 1.0

    X_hist = np.zeros((N, single.N_STATES))
    innov_sq_sum = 0.0

    for k in range(N):
        csa_k = 0.5 * X[single.I_cz] + 0.5 * co[k]
        U_k = (To[k], wo[k], co[k], Tsa[k], wsa[k], csa_k, msa[k])

        Q_k = Q_base.copy()
        excitation_factor = np.tanh(msa[k] / 0.010)
        Q_k[single.I_as, single.I_as] += 1e-6 * excitation_factor
        Q_k[single.I_bs, single.I_bs] += 1e-6 * excitation_factor

        dX = single.f_dynamics(X, U_k)
        X_pred = X + dX * single.DT

        X_pred[single.I_ao] = np.clip(X_pred[single.I_ao], 1e-6, 0.01)
        X_pred[single.I_as] = np.clip(X_pred[single.I_as], 1e-6, 0.5)
        X_pred[single.I_bo] = np.clip(X_pred[single.I_bo], 1e-8, 1e-3)
        X_pred[single.I_bs] = np.clip(X_pred[single.I_bs], 1e-5, 1.0)
        X_pred[single.I_ge] = np.clip(X_pred[single.I_ge], 0.0, 5.0)
        X_pred[single.I_cz] = np.clip(X_pred[single.I_cz], 300.0, 3000.0)

        F_k = np.eye(single.N_STATES) + single.get_jacobian_F(X, U_k) * single.DT
        P_pred = F_k @ P @ F_k.T + Q_k * single.DT

        Z_k = np.array([Tz_meas[k], wz_meas[k], cz_meas[k]])
        if np.any(np.isnan(Z_k)):
            X = X_pred
            P = P_pred
        else:
            y_k = Z_k - H @ X_pred
            S_k = H @ P_pred @ H.T + R
            try:
                K_k = P_pred @ H.T @ np.linalg.inv(S_k)
                X = X_pred + K_k @ y_k
                P = (np.eye(single.N_STATES) - K_k @ H) @ P_pred
                innov_sq_sum += (y_k[0]**2 + 0.001 * y_k[2]**2)
            except np.linalg.LinAlgError:
                X = X_pred
                P = P_pred
        P = 0.5 * (P + P.T)
        X_hist[k, :] = X

    rmse_Tz = np.sqrt(np.mean((Tz_meas - X_hist[:, single.I_Tz])**2))
    rmse_cz = np.sqrt(np.mean((cz_meas - X_hist[:, single.I_cz])**2))

    cost = rmse_Tz + 0.002 * rmse_cz + 0.0001 * (innov_sq_sum / N)
    return cost if not np.isnan(cost) else 1e6

def expected_improvement(X, X_sample, Y_sample, gpr, xi=0.01):
    X = np.atleast_2d(X)
    mu, sigma = gpr.predict(X, return_std=True)
    sigma = np.maximum(sigma, 1e-9)
    mu_sample_opt = np.min(Y_sample)

    improvement = mu_sample_opt - mu - xi
    Z = improvement / sigma
    ei = improvement * norm.cdf(Z) + sigma * norm.pdf(Z)
    return ei.flatten()

def propose_location(acquisition, X_sample, Y_sample, gpr, bounds, n_restarts=10):
    dim = bounds.shape[0]
    min_val = 1e10
    min_x = None

    def min_obj(x):
        return -acquisition(x, X_sample, Y_sample, gpr)

    for x0 in np.random.uniform(bounds[:, 0], bounds[:, 1], size=(n_restarts, dim)):
        res = scipy_minimize(min_obj, x0=x0, bounds=bounds, method="L-BFGS-B")
        if res.fun < min_val:
            min_val = res.fun
            min_x = res.x

    return min_x

def run_bayesian_tuning(room_id=3, n_iters=15):
    spec = single.ROOM_SPECS[room_id]
    csv_file = os.path.join(ROBOD_DIR, spec["file"])
    print("=" * 70)
    print(f"  BAYESIAN OPTIMIZATION EKF AUTO-TUNER FOR ROBOD {spec['name']}")
    print("=" * 70)
    df = pd.read_csv(csv_file)

    bounds = np.array([
        [-10.0, -6.0],  # log10(Q_ao)
        [-10.0, -6.0],  # log10(Q_as)
        [-10.0, -6.0],  # log10(Q_bo)
        [-10.0, -6.0],  # log10(Q_bs)
        [-5.0,  -1.0],  # log10(Q_ge)
        [-4.0,   0.0],  # log10(R_Tz)
        [-1.0,   3.0],  # log10(R_cz)
    ])

    np.random.seed(42)
    n_init = 5
    X_sample = np.random.uniform(bounds[:, 0], bounds[:, 1], size=(n_init, bounds.shape[0]))
    Y_sample = np.zeros(n_init)

    print(f"Evaluating {n_init} initial random hyperparameter samples...")
    for i in range(n_init):
        Y_sample[i] = evaluate_single_ekf_cost(X_sample[i], df, spec)
        print(f"  Init Sample {i+1}/{n_init} -> Cost J(Theta) = {Y_sample[i]:.4f}")

    kernel = Matern(nu=2.5) + WhiteKernel(noise_level=1e-5)
    gpr = GaussianProcessRegressor(kernel=kernel, alpha=1e-6, normalize_y=True, n_restarts_optimizer=5)

    print(f"\nRunning {n_iters} Bayesian Optimization iterations...")
    for i in range(n_iters):
        gpr.fit(X_sample, Y_sample)
        x_next = propose_location(expected_improvement, X_sample, Y_sample, gpr, bounds)
        y_next = evaluate_single_ekf_cost(x_next, df, spec)

        X_sample = np.vstack((X_sample, x_next))
        Y_sample = np.append(Y_sample, y_next)

        best_idx = np.argmin(Y_sample)
        best_cost = Y_sample[best_idx]
        print(f"  Iter {i+1:02d}/{n_iters} | Candidate Cost = {y_next:.4f} | Current Best J* = {best_cost:.4f}")

    best_idx = np.argmin(Y_sample)
    best_params = X_sample[best_idx]
    best_cost = Y_sample[best_idx]

    print("\n" + "=" * 70)
    print("  BAYESIAN OPTIMIZATION COMPLETE — OPTIMAL HYPERPARAMETERS:")
    print("=" * 70)
    param_names = ["Q_ao", "Q_as", "Q_bo", "Q_bs", "Q_ge", "R_Tz", "R_cz"]
    for name, val in zip(param_names, best_params):
        print(f"  Optimal {name:5s} = 10^({val:6.3f}) = {10**val:.3e}")
    print(f"  Minimum Total Cost J(Theta*) = {best_cost:.4f}")
    print("=" * 70 + "\n")

    return best_params

if __name__ == "__main__":
    run_bayesian_tuning(room_id=3, n_iters=15)
