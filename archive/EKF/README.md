# Extended Kalman Filter (EKF) Module

This directory contains the **Extended Kalman Filter (EKF)** research module for parameter and state estimation in building zones. It implements nonlinear state-space models to estimate latent (unmeasured) physical parameters of a room from measured sensor data.

## Research Objective
The goal is to estimate key thermal characteristics of a building envelope:
- **Thermal Capacitance ($C_z$):** Energy storage capacity of the zone air and mass.
- **Heat Transmission Coefficients ($\alpha_o, \alpha_s, \alpha_e$):** Heat transfer through the envelope and partition walls.
- **Internal Heat Gains ($\gamma$):** Heat added by occupants, lighting, and equipment.
- **Infiltration Rates ($\beta_o, \beta_s$):** Heat losses due to air exchange.

---

## File Registry & Documentation

### 1. Core Code Modules
- **`Real_EKF_ROBOD.py`:** The main EKF implementation. It reads time-series measurement datasets, models the zone using a 10-state nonlinear state-space representation, computes the state transitions and Jacobians, and updates the covariance matrices.
- **`diag_occupancy.py`:** Diagnostic script used to infer zone occupancy status from CO₂ levels and temperature differentials.

### 2. Mathematical Reference Documents
- **[EKF_System_Reference.md](EKF_System_Reference.md):** The canonical mathematical guide. It outlines the continuous-time differential equations, the discretized state transitions ($f(\mathbf{x})$), measurement models ($h(\mathbf{x})$), Jacobian matrices ($F$ and $H$), and noise covarance structures ($Q$ and $R$).
- **[EKF_Progress_Revision.md](EKF_Progress_Revision.md):** Summarizes progress updates, equation checks, and experimental configurations.
- **[EKF_Next_Steps_Plan.md](EKF_Next_Steps_Plan.md):** Details future expansion plans for multi-zone and online filtering.
- **[implementation_plan_for_EKF.md](implementation_plan_for_EKF.md):** Internal design document for EKF execution and persistence.

### 3. Directories
- **`Datasets for EKF/`:** Contains time-series sensor measurements (CSV format) of zone air temperatures, envelope surface heat fluxes, and HVAC statuses collected from test sites.
- **`results/` & `results_robod_room3/`:** Holds output files from EKF runs, including estimated parameter trajectories, convergence logs, and comparative charts.
- **`Practise demos/` & `Exp setup/`:** Sandbox scripts, toy models, and setup configurations used for practice and testing.

---
*For instructions on how to execute these EKF scripts in a Google Colab GPU environment, refer to the [smartbem_delivery_guide.md](../docs/smartbem_delivery_guide.md).*
