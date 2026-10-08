# EnergyPlus Simulation Benchmark & EKF Verification Plan (`ep_testdata_ekf`)

This document outlines the step-by-step implementation plan to run EnergyPlus simulations using our calibrated `v5` test rig IDF model on the experimental datasets (`with_occ` Day 3 & Day 4), generate synthetic ground-truth simulation outputs, and verify our 10-State EKF estimation accuracy in a controlled simulation environment.

---

## 1. Objectives

1. **Create `EKF/ep_testdata_ekf/` Workspace:** Establish a clean module structure for EnergyPlus simulation data generation and EKF benchmarking.
2. **EnergyPlus Simulation Generation:** Use the calibrated EnergyPlus IDF model ([`hanger_chamber_after_calibrated_v5_part_1.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/calibrated_v5/part_1/hanger_chamber_after_calibrated_v5_part_1.idf)) and [`EPlusUtil`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EnergyPlus%20utility/eplus_util.py) wrapper to simulate the 10 experimental datasets (`with_occ` Day 3 & Day 4).
3. **Synthetic Ground-Truth Data Generation:** Extract noise-free simulated outputs:
   * Zone Temperature $T_{z,\text{sim}}(t)$
   * Zone Relative Humidity $RH_{z,\text{sim}}(t)$ / Moisture $\omega_{z,\text{sim}}(t)$
   * Zone $\text{CO}_2$ Concentration $c_{z,\text{sim}}(t)$
4. **EKF Verification on Simulation Benchmark:** Run the 10-State EKF on the EnergyPlus simulated telemetry to verify:
   * Parameter convergence to known EnergyPlus IDF physics ($C_s = 25.0\text{ kJ/K}$, $UA = 5.76\text{ W/K}$, $M_{\text{room}} = 7.00\text{ kg}$).
   * Occupancy count $\hat{N}$ step tracking accuracy.

---

## 2. System Architecture & Workflow

```
[Calibrated IDF & EPW Weather]
             │
             ▼
   [EnergyPlus Simulation]  ──(EPlusUtil PyEnergyPlus API)──► [Synthetic Telemetry (Tz_sim, RH_sim, CO2_sim)]
                                                                                │
                                                                                ▼
[Exact Ground-Truth Physics (Cs, UA, M, N)] ◄───[Comparison & Plotting]◄─── [10-State EKF Engine]
```

---

## 3. Detailed Step-by-Step Action Plan

### **Step 1: Workspace Setup (`EKF/ep_testdata_ekf/`)**
Create directory structure:
* `SmartBEM-Studio/EKF/ep_testdata_ekf/`
* `SmartBEM-Studio/EKF/ep_testdata_ekf/ep_sim_outputs/` (stores generated synthetic CSVs)
* `SmartBEM-Studio/EKF/ep_testdata_ekf/ep_results_plots/` (stores 4-PNG plot suites)

### **Step 2: EnergyPlus Simulation Data Generator (`generate_ep_sim_data.py`)**
* Utilize [`EPlusUtil`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EnergyPlus%20utility/eplus_util.py) to load the calibrated IDF:
  `hanger_chamber_after_calibrated_v5_part_1.idf`
* Map outdoor boundary conditions ($T_o, RH_o, P_{\text{live}}, \dot{m}_{sa}, T_{sa}$) and occupancy schedules for each dataset in `Readings_from_rig/experimental_data/with_occ/`.
* Run EnergyPlus simulations at 5-second sampling intervals and export synthetic CSVs to `ep_sim_outputs/`.

### **Step 3: EnergyPlus Benchmark EKF Runner (`run_ep_ekf.py`)**
* Implement the 10-State EKF engine on synthetic EnergyPlus CSV outputs using:
  * Physically informed $X_0$ initialization ($C_{s,0} = 25\text{ kJ/K}, M_0 = 7\text{ kg}, UA_0 = 5.76\text{ W/K}$).
  * Adaptive excitation scaling $Q_k(\dot{m}_{sa})$.
* Calculate derived physical properties:
  $$C_{s,\text{est}} = \frac{c_{pa}}{\alpha_s}, \quad M_{\text{est}} = \frac{1}{\beta_s}, \quad UA_{\text{est}} = \alpha_o \cdot C_s - c_{pa} \cdot \dot{m}_{\text{inf}}$$

### **Step 4: 4-PNG Plot Suite Generation & Benchmark Comparison**
Generate 4 PNG plots per dataset comparing EKF estimates against EnergyPlus exact physics:
1. `[Dataset]_EP_EKF_States_3Subplots.png`: Simulated vs EKF Estimated $T_z, RH_z, c_z$.
2. `[Dataset]_EP_EKF_Occupancy_vs_GroundTruth.png`: EKF Occupancy vs EnergyPlus Occupancy Schedule.
3. `[Dataset]_EP_EKF_Estimated_Parameters.png`: 7 parameter trajectories ($\alpha_o \dots \gamma_e$).
4. `[Dataset]_EP_EKF_Derived_Physical_Parameters.png`: EKF Derived $C_s, M, \dot{m}_{\text{inf}}, UA$ vs EnergyPlus Exact Values ($C_s=25\text{ kJ/K}, M=7\text{ kg}, UA=5.76\text{ W/K}$).

---

## 4. Verification & Success Criteria

| Metric | Target Threshold | Validation Method |
| :--- | :---: | :--- |
| **Environmental State Fit** | $\text{RMSE}(T_z) \le 0.10^\circ\text{C}, \text{RMSE}(c_z) \le 5\text{ ppm}$ | Compare EKF output to EnergyPlus simulation output |
| **$C_s$ Parameter Convergence** | $25.0 \pm 5.0\text{ kJ/}^\circ\text{C}$ | Verify EKF $C_s$ settles inside EnergyPlus expectation band |
| **$M_{\text{room}}$ Air Mass Convergence** | $7.00 \pm 0.30\text{ kg}$ | Verify EKF $M$ settles inside EnergyPlus expectation band |
| **$UA$ Conductance Convergence** | $5.76 \pm 0.80\text{ W/}^\circ\text{C}$ | Verify EKF $UA$ settles inside EnergyPlus expectation band |
