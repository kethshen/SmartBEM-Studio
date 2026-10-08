# EnergyPlus Calibration Engines Overview

This folder contains the core **Python calibration and optimization scripts** used to tune and validate the EnergyPlus Building Energy Model (BEM) against test rig experimental telemetry.

---

## 📋 Calibration Execution Sequence & Script Reference

The scripts are numbered sequentially according to their position in the calibration workflow:

```
[01_run_uncalibrated_baseline.py] ──> [02_setup_sri_lanka_material_baseline.py] ──> [03_run_rmse_scipy_optimizer.py] ──> [04_run_ashrae_dtw_optimizer.py] ──> [05_run_high_iter_global_optimizer.py] ──> [06_apply_calibrated_parameters_to_idf.py] ──> [07_verify_ekf_state_estimation.py]
```

---

### 1. [`01_run_uncalibrated_baseline.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/calibration_engines/01_run_uncalibrated_baseline.py)
* **Objective:** Runs the uncalibrated baseline EnergyPlus model once to establish uncalibrated performance metrics.
* **Code Implementation:**
  * Invokes `energyplus.exe` with `chamber_base_template.idf` and `test_day_weather.epw`.
  * Extracts target variable `Zone Mean Air Temperature` from the output `.eso` binary file.
  * Overlay-plots $T_{\text{sim}}(t)$ against uncalibrated sensor data and computes initial baseline error metrics (RMSE, NMBE).

### 2. [`02_setup_sri_lanka_material_baseline.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/calibration_engines/02_setup_sri_lanka_material_baseline.py)
* **Objective:** Constructs a Sri Lanka-specific physical material baseline model.
* **Code Implementation:**
  * Modifies the master template IDF by inserting Sri Lanka Standard (SLS 855) 220mm brick and 15mm cement plaster wall construction objects (`Hanger_Composite_Wall_250mm`).
  * Updates site coordinates to Colombo/Kandy, Sri Lanka ($6.90^{\circ}\text{N}, 79.86^{\circ}\text{E}$, UTC+6).
  * Synthesizes day-specific weather lines into the EPW file template.

### 3. [`03_run_rmse_scipy_optimizer.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/calibration_engines/03_run_rmse_scipy_optimizer.py)
* **Objective:** Performs automated parameter optimization by minimizing Root Mean Square Error (RMSE).
* **Code Implementation:**
  * Uses `scipy.optimize.minimize` (Nelder-Mead simplex algorithm) to iterate over 5 decision variables:
    $$\mathbf{x} = \left[ k_{\text{foam}}, c_{p,\text{foam}}, \rho_{\text{foam}}, \text{ACH}, q_{\text{cool}} \right]$$
  * Objective Function: $\min_{\mathbf{x}} \text{RMSE}(T_{\text{sim}}(\mathbf{x}), T_{z,\text{EMA}})$.
  * Dynamically overwrites material properties in `Chamber_PU_Foam` per iteration.

### 4. [`04_run_ashrae_dtw_optimizer.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/calibration_engines/04_run_ashrae_dtw_optimizer.py)
* **Objective:** Advanced multi-objective optimization enforcing **ASHRAE Guideline 14 compliance** and **Dynamic Time Warping (DTW)** shape matching.
* **Code Implementation:**
  * Implements custom matrix DTW distance function (`compute_dtw_distance(s1, s2)`) to align non-linear thermal time lag and peak timing.
  * Objective Function: Composite loss balancing CV(RMSE), NMBE, and DTW trajectory shape distance:
    $$\mathcal{L}(\mathbf{x}) = 0.50 \cdot \text{CV(RMSE)} + 0.30 \cdot |\text{NMBE}| + 0.20 \cdot \text{DTW\_dist}$$

### 5. [`05_run_high_iter_global_optimizer.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/calibration_engines/05_run_high_iter_global_optimizer.py)
* **Objective:** Deep multi-start global optimization to find globally optimal thermal parameters without getting trapped in local minima.
* **Code Implementation:**
  * Runs an extended optimization loop (`maxiter=600`) across wide parameter bounds.
  * Tracks global best parameter set ($\mathbf{x}^*$) across all iterations and logs real-time convergence trajectories.

### 6. [`06_apply_calibrated_parameters_to_idf.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/calibration_engines/06_apply_calibrated_parameters_to_idf.py)
* **Objective:** Applies converged optimal master parameters to the base IDF template and generates final validation reports.
* **Code Implementation:**
  * Injects converged master parameters ($k_{\text{foam}} = 0.02650\text{ W/m·K}$, $c_p = 916\text{ J/kg·K}$, $\rho = 45\text{ kg/m}^3$, $\text{ACH} = 0.0110\text{ hr}^{-1}$) into the final IDF.
  * Executes full validation runs and outputs high-resolution comparison plots.

### 7. [`07_verify_ekf_state_estimation.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/calibration_engines/07_verify_ekf_state_estimation.py)
* **Objective:** Verifies state vector convergence when passing simulation outputs into the Dual Extended Kalman Filter.
* **Code Implementation:**
  * Formulates a 2-state EKF model: $\mathbf{x}_k = [T_z(k), \alpha_o(k)]^T$ where $\alpha_o = UA / C_s$ is the overall thermal loss rate parameter.
  * Evaluates state covariance matrix $P_k$ and Kalman gain $K_k$ over time to verify parameter estimation stability ($UA = 52.83\text{ W/K}$, $C_s = 379,699\text{ J/K}$).
