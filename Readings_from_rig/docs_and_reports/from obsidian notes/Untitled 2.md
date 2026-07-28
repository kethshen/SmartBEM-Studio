# Implementation Plan — Phase 3: EnergyPlus Model Tuning & Phase 4: EKF Verification

This plan details the technical steps to ground the SmartBEM Studio EnergyPlus simulation model using our sensor-derived physical targets ($UA_{\text{effective}} = 52.83\text{ W/K}$ and $C_s = 3.80 \times 10^5\text{ J/K}$), and verify that the Extended Kalman Filter (EKF) parameter estimates converge to these physical baselines.

---

## User Review Required

Please review and confirm the calibration targets for the EnergyPlus model:

> [!IMPORTANT]
> 1. **Primary Conductance Target:** We will tune the EnergyPlus model envelope (PU foam conductivity `k` + infiltration ACH) to hit **$UA_{\text{effective}} = 52.83\text{ W/K}$** (derived from the long 83-minute Part 6 tail) as the steady-state baseline, while keeping $61.20\text{ W/K}$ as the overall multi-run upper bound.
> 2. **Primary Capacitance Target:** We will tune the model's total thermal mass (PU foam density $\rho$ + specific heat $c_p$) to hit **$C_s = 3.80 \times 10^5\text{ J/K}$** (proven with 0.1% repeatability).
> 3. **Nested Geometry Input:** You will provide the exact geometry dimensions and coordinate offsets for the Cool Room inside the Hanger when we begin setting up the model.

---

## Proposed Changes & Execution Workflow

### 1. EnergyPlus Model Calibration Pipeline (Phase 3)

#### [NEW] [tune_energyplus_model.py](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/tune_energyplus_model.py)
A Python calibration script to match the EnergyPlus model parameters to the sensor targets:

1. **Conductance Matching ($UA_{\text{effective}} = 52.83\text{ W/K}$):**
   * Adjust the wall PU foam thermal conductivity `k` and chamber `ZoneInfiltration:DesignFlowRate` ACH until the computed total envelope loss $UA_{\text{model}} = \sum (A_i \cdot U_i) + \dot{m}_{\text{inf}} c_p$ equals **$52.83\text{ W/K}$**.
2. **Thermal Capacitance Matching ($C_s = 3.80 \times 10^5\text{ J/K}$):**
   * Adjust PU foam density $\rho$ and specific heat $c_p$ until the model's total sensible heat capacitance $C_{\text{model}} = m_{\text{air}} c_{p,\text{air}} + \sum (m_i c_{p,i})$ equals **$3.80 \times 10^5\text{ J/K}$**.
3. **Simulation Execution & Comparison Plotting:**
   * Run EnergyPlus simulation using the cleaned outdoor temperature ($T_o$) and supply air temperature ($T_{sa}$) from Part 1 & Part 6 as boundary conditions.
   * Overlay simulated room temperature $T_{\text{sim}}$ on top of cleaned sensor $T_z$ logs.
   * Calculate RMSE (Root Mean Square Error) between simulated and real temperature profiles (target RMSE $< 0.5^{\circ}\text{C}$).

---

### 2. Extended Kalman Filter (EKF) Convergence Verification (Phase 4)

#### [MODIFY] [EKF_System_Reference.md](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/EKF_System_Reference.md) & EKF Validation Script
1. **State Vector Grounding:**
   * Set EKF physical parameter baseline:
     $$\alpha_o = \frac{UA_{\text{effective}}}{C_s} = \frac{52.83}{3.80 \times 10^5} \approx 1.39 \times 10^{-4}\text{ s}^{-1}$$
     $$\alpha_s = \frac{c_{pa} \dot{m}_{sa}}{C_s}$$
2. **EKF Running on Cleaned Sensor Data:**
   * Run EKF state estimation using cleaned $T_z$, $T_o$, $T_{sa}$ time-series data.
3. **Convergence Verification:**
   * Verify that the EKF parameter estimates $\hat{\alpha}_o(t)$ remain stable and converge within $\pm 20\%$ of $1.39 \times 10^{-4}\text{ s}^{-1}$.

---

## Verification Plan

### Automated Verification
* Run `tune_energyplus_model.py` and verify:
  - Computed $UA_{\text{model}}$ is within $\pm 2\%$ of $52.83\text{ W/K}$.
  - Computed $C_{\text{model}}$ is within $\pm 2\%$ of $3.80 \times 10^5\text{ J/K}$.
  - Simulation completes with 0 EnergyPlus errors.
  - Temperature profile RMSE between $T_{\text{sim}}$ and $T_z$ is $< 0.5^{\circ}\text{C}$.

### Manual Review
* Inspect the simulation overlay plot to confirm that the pulldown slope and steady-state offset match the real rig data visually.
