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
