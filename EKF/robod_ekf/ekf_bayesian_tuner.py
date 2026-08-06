"""
SmartBEM FYP — Autotuned Adaptive EKF via Bayesian Optimization (robod_ekf)
=============================================================================
Implements Bayesian Optimization using Gaussian Process Regression (scikit-learn)
and Expected Improvement (EI) acquisition function to auto-tune 10-State EKF 
process noise Q and measurement noise R matrices.

Theoretical basis:
  - Hyperparameter Search Space: Θ = [log10(Q_ao), log10(Q_as), log10(Q_bo), log10(Q_bs), log10(Q_ge), log10(R_T), log10(R_c)]
  - Objective Function: J(Θ) = RMSE(Tz) + λ_c * RMSE(cz) + Innovation Likelihood + Physics Penalty
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import sys
from scipy.stats import norm
from scipy.optimize import minimize as scipy_minimize
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel

# Import EKF functions from Real_EKF_ROBOD
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
from Real_EKF_ROBOD import (
    ROOM_SPECS, ROBOD_DIR, I_ao, I_as, I_ae, I_bo, I_bs, I_be, I_ge,
    I_Tz, I_wz, I_cz, N_STATES, c_pa, DT, FCU_FLOW_SCALE,
    rh_to_humidity_ratio, f_dynamics, get_jacobian_F
)

def evaluate_ekf_cost(log_params, df, room_spec):
    """
    Evaluates EKF tracking cost J(Θ) for a given log10 hyperparameter vector Θ.
    log_params: [log10(Q_ao), log10(Q_as), log10(Q_bo), log10(Q_bs), log10(Q_ge), log10(R_T), log10(R_c)]
    """
    N = len(df)
    
    # Helper to get column regardless of unit suffix
    def get_col(candidates):
        for c in candidates:
            if c in df.columns:
                return df[c].values
        raise KeyError(f"None of {candidates} found in CSV columns: {list(df.columns)}")
        
    To  = get_col(["dry_bulb_temp [Celsius]", "dry_bulb_temp"])
    rho = get_col(["outdoor_relative_humidity [%]", "outdoor_relative_humidity"])
    wo  = np.array([rh_to_humidity_ratio(rho[i], To[i]) for i in range(N)])
    co  = get_col(["outdoor_co2 [ppm]", "outdoor_co2"])
    
    Tsa = get_col(["supply_air_temperature [Celsius]", "supply_air_temperature"])
    wsa = wo.copy()
    csa = co.copy()
    
    fan_hz = get_col(["ahu_fan_speed [Hz]", "fcu_fan_speed [Hz]", "fcu_fan_speed", "ahu_fan_speed"])
    msa = np.clip(fan_hz * FCU_FLOW_SCALE, 0.001, None)
    
    Tz_meas = get_col(["indoor_temperature [Celsius]", "indoor_temperature", "air_temperature [Celsius]"])
    RHz_meas = get_col(["indoor_relative_humidity [%]", "indoor_relative_humidity"])
    wz_meas = np.array([rh_to_humidity_ratio(RHz_meas[i], Tz_meas[i]) for i in range(N)])
    cz_meas = get_col(["indoor_co2 [ppm]", "indoor_co2"])
    
    M_expected = room_spec["mass"]
    Cs_expected = room_spec["Cs"] * 1000.0
    UA_expected = room_spec["UA"]
    
    Cs_min = room_spec["Cs"] * 0.5 * 1000.0
    Cs_max = room_spec["Cs"] * 2.5 * 1000.0
    alpha_s_min = c_pa / Cs_max
    alpha_s_max = c_pa / Cs_min
    
    # Unpack log-space hyperparameters
    q_ao, q_as, q_bo, q_bs, q_ge, r_T, r_c = 10.0**log_params
    
    X = np.zeros(N_STATES)
    X[I_ao] = UA_expected / Cs_expected
    X[I_as] = c_pa / Cs_expected
    X[I_ae] = 0.0000
    X[I_bo] = 2.78e-5
    X[I_bs] = 1.0 / M_expected
    X[I_be] = 0.0000
    X[I_ge] = 0.0000
    X[I_Tz] = Tz_meas[0]
    X[I_wz] = wz_meas[0]
    X[I_cz] = cz_meas[0]
    
    P = np.eye(N_STATES) * 0.1
    P[I_ge, I_ge] = 1.0
    
    Q_base = np.diag([q_ao, q_as, 1e-8, q_bo, q_bs, 1e-14, q_ge, 0.01, 1e-7, 1.0])
    R = np.diag([r_T, 1e-6, r_c])
    
    H = np.zeros((3, N_STATES))
    H[0, I_Tz] = 1.0
    H[1, I_wz] = 1.0
    H[2, I_cz] = 1.0
    
    X_hist = np.zeros((N, N_STATES))
    innov_sq_sum = 0.0
    
    for k in range(N):
        U_k = [To[k], wo[k], co[k], Tsa[k], wsa[k], csa[k], msa[k]]
        Z_k = np.array([Tz_meas[k], wz_meas[k], cz_meas[k]])
        
        dX = f_dynamics(X, U_k)
        X_pred = X + dX * DT
        
        J_F = get_jacobian_F(X, U_k)
        F_k = np.eye(N_STATES) + J_F * DT
        
        excitation_factor = np.tanh(msa[k] / 0.05)
        Q_k = Q_base.copy()
        Q_k[I_as, I_as] = 1e-12 + q_as * excitation_factor
        Q_k[I_bs, I_bs] = 1e-10 + q_bs * excitation_factor
        
        P_pred = F_k @ P @ F_k.T + Q_k * DT
        
        Z_pred = np.array([X_pred[I_Tz], X_pred[I_wz], X_pred[I_cz]])
        y_k = Z_k - Z_pred
        
        S_k = H @ P_pred @ H.T + R
        K_k = P_pred @ H.T @ np.linalg.inv(S_k)
        
        X = X_pred + K_k @ y_k
        P = (np.eye(N_STATES) - K_k @ H) @ P_pred
        
        X[I_as] = np.clip(X[I_as], alpha_s_min, alpha_s_max)
        X[I_ge] = np.clip(X[I_ge], 0.0, None)
        X[I_cz] = np.clip(X[I_cz], 300.0, 2000.0)
        
        X_hist[k] = X
        innov_sq_sum += (y_k[0]**2 + 0.001 * y_k[2]**2)
        
    rmse_Tz = np.sqrt(np.mean((Tz_meas - X_hist[:, I_Tz])**2))
    rmse_cz = np.sqrt(np.mean((cz_meas - X_hist[:, I_cz])**2))
    
    cost = rmse_Tz + 0.002 * rmse_cz + 0.0001 * (innov_sq_sum / N)
    return cost if not np.isnan(cost) else 1e6

# ── Expected Improvement (EI) Acquisition Function ────────────────────────────
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

# ── Main Bayesian Optimization Tuner ───────────────────────────────────────────
def run_bayesian_tuning(room_id=3, n_iters=30):
    spec = ROOM_SPECS[room_id]
    csv_file = os.path.join(ROBOD_DIR, spec["file"])
    print(f"--- STARTING BAYESIAN OPTIMIZATION EKF AUTO-TUNER FOR ROBOD {spec['name']} ---")
    df = pd.read_csv(csv_file).ffill().bfill()
    
    # 7 Hyperparameters in log-10 scale
    bounds = np.array([
        [-12.0, -6.0],  # log10(Q_ao)
        [-12.0, -6.0],  # log10(Q_as)
        [-12.0, -6.0],  # log10(Q_bo)
        [-12.0, -6.0],  # log10(Q_bs)
        [-8.0,  -3.0],  # log10(Q_ge)
        [-3.0,   1.0],  # log10(R_T)
        [ 0.0,   4.0],  # log10(R_c)
    ])
    
    # Initial random sampling (5 initial points)
    np.random.seed(42)
    n_init = 5
    X_sample = np.random.uniform(bounds[:, 0], bounds[:, 1], size=(n_init, bounds.shape[0]))
    Y_sample = np.zeros(n_init)
    
    print(f"Evaluating {n_init} initial random hyperparameter samples...")
    for i in range(n_init):
        Y_sample[i] = evaluate_ekf_cost(X_sample[i], df, spec)
        print(f"  Init Sample {i+1}/{n_init} -> Cost J(Theta) = {Y_sample[i]:.4f}")
        
    kernel = Matern(nu=2.5) + WhiteKernel(noise_level=1e-5)
    gpr = GaussianProcessRegressor(kernel=kernel, alpha=1e-6, normalize_y=True, n_restarts_optimizer=5)
    
    print(f"\nRunning {n_iters} Bayesian Optimization iterations...")
    for i in range(n_iters):
        gpr.fit(X_sample, Y_sample)
        x_next = propose_location(expected_improvement, X_sample, Y_sample, gpr, bounds)
        y_next = evaluate_ekf_cost(x_next, df, spec)
        
        X_sample = np.vstack((X_sample, x_next))
        Y_sample = np.append(Y_sample, y_next)
        
        best_idx = np.argmin(Y_sample)
        best_cost = Y_sample[best_idx]
        print(f"  Iter {i+1:02d}/{n_iters} | Candidate Cost = {y_next:.4f} | Current Best J* = {best_cost:.4f}")
        
    best_idx = np.argmin(Y_sample)
    best_params = X_sample[best_idx]
    best_cost = Y_sample[best_idx]
    
    print("\n" + "="*70)
    print("BAYESIAN OPTIMIZATION COMPLETE — OPTIMAL EKF HYPERPARAMETERS FOUND:")
    print("="*70)
    param_names = ["Q_ao", "Q_as", "Q_bo", "Q_bs", "Q_ge", "R_T", "R_c"]
    for name, val in zip(param_names, best_params):
        print(f"  Optimal {name:5s} = 10^({val:6.3f}) = {10**val:.3e}")
    print(f"  Minimum Total Cost J(Theta*) = {best_cost:.4f}")
    print("="*70)
    
    return best_params

if __name__ == "__main__":
    run_bayesian_tuning(room_id=3, n_iters=25)
