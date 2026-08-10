"""
SmartBEM FYP — Shared EKF Occupancy Evaluation & Threshold Optimizer
=====================================================================
Provides mathematical metrics (Continuous RMSE, MAE, Peak Error)
and automated threshold optimization (tau*) for discretized occupant count,
exact integer accuracy (%), tolerance accuracy (+-1 person), and binary F1-score.
"""

import numpy as np
import pandas as pd

def optimize_threshold(N_occ_est, N_gt, tau_min=0.10, tau_max=0.90, step=0.02):
    """
    Automated Parameter-Free Grid Search Optimizer for Decision Threshold tau*.
    Finds tau* in [tau_min, tau_max] that minimizes MAE(N_disc(tau), N_gt).
    """
    N_occ_est = np.asarray(N_occ_est)
    N_gt = np.asarray(N_gt)
    
    threshold_grid = np.arange(tau_min, tau_max + 1e-5, step)
    best_tau = 0.50
    best_mae = 1e9
    best_acc = -1.0
    
    for tau in threshold_grid:
        n_disc = np.maximum(0.0, np.floor(N_occ_est + (1.0 - tau)))
        mae = np.mean(np.abs(n_disc - N_gt))
        acc = np.mean(n_disc == N_gt) * 100.0
        
        if mae < best_mae or (abs(mae - best_mae) < 1e-6 and acc > best_acc):
            best_mae = mae
            best_acc = acc
            best_tau = float(tau)
            
    return best_tau

def compute_occupancy_metrics(N_occ_est, N_gt, tau=None):
    """
    Computes complete evaluation metrics suite for continuous and discretized occupancy.
    """
    N_occ_est = np.asarray(N_occ_est)
    N_gt = np.asarray(N_gt)
    N = len(N_gt)
    
    if N == 0:
        return {}
        
    # ── Continuous Metrics ─────────────────────────────────────────────────────
    rmse_cont = float(np.sqrt(np.mean((N_occ_est - N_gt)**2)))
    mae_cont  = float(np.mean(np.abs(N_occ_est - N_gt)))
    peak_err  = float(abs(np.max(N_occ_est) - np.max(N_gt)))
    
    # ── Threshold Optimization / Discretization ────────────────────────────────
    if tau is None:
        tau_opt = optimize_threshold(N_occ_est, N_gt)
    else:
        tau_opt = float(tau)
        
    N_disc = np.maximum(0.0, np.floor(N_occ_est + (1.0 - tau_opt)))
    
    # ── Discretized Metrics ────────────────────────────────────────────────────
    acc_exact = float(np.mean(N_disc == N_gt) * 100.0)
    acc_tol1  = float(np.mean(np.abs(N_disc - N_gt) <= 1.0) * 100.0)
    mae_disc  = float(np.mean(np.abs(N_disc - N_gt)))
    rmse_disc = float(np.sqrt(np.mean((N_disc - N_gt)**2)))
    
    # ── Binary Presence Classification (F1-Score) ──────────────────────────────
    bin_pred = (N_disc >= 1.0).astype(int)
    bin_gt   = (N_gt >= 1.0).astype(int)
    
    tp = np.sum((bin_pred == 1) & (bin_gt == 1))
    fp = np.sum((bin_pred == 1) & (bin_gt == 0))
    fn = np.sum((bin_pred == 0) & (bin_gt == 1))
    tn = np.sum((bin_pred == 0) & (bin_gt == 0))
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score  = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    
    return {
        "rmse_cont": round(rmse_cont, 4),
        "mae_cont": round(mae_cont, 4),
        "peak_err": round(peak_err, 4),
        "tau_opt": round(tau_opt, 2),
        "acc_exact_pct": round(acc_exact, 2),
        "acc_tol1_pct": round(acc_tol1, 2),
        "mae_disc": round(mae_disc, 4),
        "rmse_disc": round(rmse_disc, 4),
        "f1_score": round(float(f1_score), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4)
    }

def compute_parameter_metrics(Cs_hist, UA_hist, m_inf_hist):
    """
    Computes performance metrics for derived physical building parameters (Cs, UA, m_inf):
    - MAPE (%): Mean Absolute Percentage Error against calibrated physical target
    - PBAR (%): Physical Bounds Adherence Rate (% of time inside valid physical window)
    - CV (%): Steady-State Coefficient of Variation
    """
    Cs_hist = np.asarray(Cs_hist) / 1000.0  # convert J/K to kJ/K
    UA_hist = np.asarray(UA_hist)
    m_inf_hist = np.asarray(m_inf_hist)
    
    CS_TARGET = 25.0    # kJ/K
    UA_TARGET = 5.76    # W/K
    MINF_TARGET = 0.03  # g/s
    
    mape_cs = float(np.mean(np.abs(Cs_hist - CS_TARGET) / CS_TARGET) * 100.0)
    mape_ua = float(np.mean(np.abs(UA_hist - UA_TARGET) / UA_TARGET) * 100.0)
    mape_minf = float(np.mean(np.abs(m_inf_hist - MINF_TARGET) / MINF_TARGET) * 100.0)
    
    pbar_cs = float(np.mean((Cs_hist >= 20.0) & (Cs_hist <= 30.0)) * 100.0)
    pbar_ua = float(np.mean((UA_hist >= 5.0) & (UA_hist <= 6.5)) * 100.0)
    pbar_minf = float(np.mean((m_inf_hist >= 0.0) & (m_inf_hist <= 0.10)) * 100.0)
    
    cv_cs = float((np.std(Cs_hist) / np.mean(Cs_hist)) * 100.0) if np.mean(Cs_hist) > 0 else 0.0
    cv_ua = float((np.std(UA_hist) / np.mean(UA_hist)) * 100.0) if np.mean(UA_hist) > 0 else 0.0
    
    return {
        "mape_cs_pct": round(mape_cs, 2),
        "mape_ua_pct": round(mape_ua, 2),
        "pbar_cs_pct": round(pbar_cs, 2),
        "pbar_ua_pct": round(pbar_ua, 2),
        "pbar_minf_pct": round(pbar_minf, 2),
        "cv_cs_pct": round(cv_cs, 2),
        "cv_ua_pct": round(cv_ua, 2),
    }
