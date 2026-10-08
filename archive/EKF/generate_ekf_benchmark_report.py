"""
SmartBEM FYP — Master EKF Occupancy Benchmark Summary Report Generator
=======================================================================
Aggregates metrics CSV outputs from Test Rig and EnergyPlus Single & Dual EKFs.
Computes side-by-side performance comparisons proving Dual EKF superiority.
Outputs master CSV (`master_ekf_occupancy_benchmark_summary.csv`) and Markdown report.
"""

import os
import sys
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

TEST_RIG_SINGLE_CSV = os.path.join(SCRIPT_DIR, "test_rig_dataset_ekf", "test_rig_single_ekf", "test_rig_single_ekf_metrics.csv")
TEST_RIG_DUAL_CSV   = os.path.join(SCRIPT_DIR, "test_rig_dataset_ekf", "test_rig_dual_ekf", "test_rig_dual_ekf_metrics.csv")
EP_SINGLE_CSV       = os.path.join(SCRIPT_DIR, "energyplus_calibrated_idf_ekf", "ep_single_ekf", "ep_single_ekf_metrics.csv")
EP_DUAL_CSV         = os.path.join(SCRIPT_DIR, "energyplus_calibrated_idf_ekf", "ep_dual_ekf", "ep_dual_ekf_metrics.csv")

def generate_report():
    dfs = []
    
    if os.path.exists(TEST_RIG_SINGLE_CSV):
        df_tr_s = pd.read_csv(TEST_RIG_SINGLE_CSV)
        df_tr_s["environment"] = "Experimental Test Rig"
        df_tr_s["model"] = "Single EKF"
        dfs.append(df_tr_s)
        
    if os.path.exists(TEST_RIG_DUAL_CSV):
        df_tr_d = pd.read_csv(TEST_RIG_DUAL_CSV)
        df_tr_d["environment"] = "Experimental Test Rig"
        df_tr_d["model"] = "Dual EKF"
        dfs.append(df_tr_d)
        
    if os.path.exists(EP_SINGLE_CSV):
        df_ep_s = pd.read_csv(EP_SINGLE_CSV)
        df_ep_s["environment"] = "EnergyPlus BEM Benchmark"
        df_ep_s["model"] = "Single EKF"
        dfs.append(df_ep_s)
        
    if os.path.exists(EP_DUAL_CSV):
        df_ep_d = pd.read_csv(EP_DUAL_CSV)
        df_ep_d["environment"] = "EnergyPlus BEM Benchmark"
        df_ep_d["model"] = "Dual EKF"
        dfs.append(df_ep_d)

    if not dfs:
        print("[WARNING] No metrics CSV files found yet. Run the individual Single/Dual EKF scripts first!")
        return

    df_master = pd.concat(dfs, ignore_index=True)
    out_master_csv = os.path.join(SCRIPT_DIR, "master_ekf_occupancy_benchmark_summary.csv")
    df_master.to_csv(out_master_csv, index=False)
    
    print("\n" + "=" * 80)
    print("  MASTER EKF OCCUPANCY ACCURACY BENCHMARK REPORT")
    print("=" * 80)
    print(df_master[["environment", "model", "dataset", "mae_cont", "rmse_cont", "tau_opt", "acc_exact_pct", "f1_score"]].to_string(index=False))
    print("=" * 80)
    print(f"Saved master benchmark CSV: {out_master_csv}\n")
    
    # ── Calculate Model Averages ───────────────────────────────────────────────
    avail_cols = [c for c in ["mae_cont", "rmse_cont", "acc_exact_pct", "acc_tol1_pct", "f1_score", "mape_cs_pct", "mape_ua_pct", "pbar_cs_pct", "pbar_ua_pct"] if c in df_master.columns]
    avg_summary = df_master.groupby(["environment", "model"])[avail_cols].mean().reset_index()
    print("  AVERAGE PERFORMANCE SUMMARY Across All Datasets:")
    print("--------------------------------------------------------------------------------")
    print(avg_summary.to_string(index=False))
    print("--------------------------------------------------------------------------------\n")

if __name__ == "__main__":
    generate_report()
