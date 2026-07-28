# Baseline EnergyPlus Simulation & Parameter Optimization Plan

**Target Master File:** [`hanger_chamber_master.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_master.idf)  
**Weather File:** [`test_day_weather.epw`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/experimental_data/test_day_weather.epw)  
**Sensor Data File:** [`Idel_test_2026_07_21.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/experimental_data/Idel_test_2026_07_21.csv)  
**Target Plot Output:** [`sim_vs_sensors_exact_rig_match.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/sim_vs_sensors_exact_rig_match.png)  
**Reference Analysis:** [`sensor_data_analysis.md`](file:///C:/Users/ASUS/.gemini/antigravity-ide/brain/30f9feb6-f7e5-40c7-a4be-f148a0753aa8/sensor_data_analysis.md)

---

## 1. Executive Summary & Goals

This plan synthesizes all physical equations, sensor weighting pipelines, target thermal metrics, and EKF convergence rules established in [`sensor_data_analysis.md`](file:///C:/Users/ASUS/.gemini/antigravity-ide/brain/30f9feb6-f7e5-40c7-a4be-f148a0753aa8/sensor_data_analysis.md).

Now that our master EnergyPlus building model ([`hanger_chamber_master.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_master.idf)) incorporates the exact 3D hanger geometry, 2-tier side wall window matrix (`CLEAR 6MM`), 45% mix damper, 17.0°C cooling setpoint, continuous fan operation (`Always On Discrete`), and 1-minute calculation timesteps (60 steps/hr), we execute a 3-stage validation process:

1. **Stage 1 (Immediate Baseline Simulation & Overlay Plotting):** Execute uncalibrated baseline EnergyPlus simulation and generate high-resolution overlay plot comparing simulated Chamber temperature $T_{\text{sim}}(t)$ against cleaned weighted sensor data $T_z(t)$.
2. **Stage 2 (Automated Parameter Optimization Loops):** Run ML-style optimization loops to fine-tune physical parameters ($k$, $\rho$, $c_p$, infiltration ACH) until the model hits target $UA_{\text{effective}}$ and $C_s$.
3. **Stage 3 (EKF Parameter Convergence Verification):** Validate that EKF estimated state parameters ($\alpha_o, \alpha_s$) converge within $\pm 20\%$ of the calibrated model.

---

## 2. Real Sensor Data Processing Pipeline

Per [`sensor_data_analysis.md`](file:///C:/Users/ASUS/.gemini/antigravity-ide/brain/30f9feb6-f7e5-40c7-a4be-f148a0753aa8/sensor_data_analysis.md), real sensor data is cleaned and processed as follows:

### 2.1 Outlier Filtering & Spike Removal
* **Spike Removal:** Filter out any reading where temperature $< 5.0^{\circ}\text{C}$ or $> 50.0^{\circ}\text{C}$ (clips ADC glitches on Sensor 3).
* **Sensor Weighting for Zone Temperature ($T_z$):**
  $$T_z(t) = 0.6 \cdot T_{\text{Sensor 1 (Bosch)}} + 0.4 \cdot T_{\text{Sensor 2}}$$
  *(Sensor 1 Bosch is primary accurate sensor; Sensor 3 weight $= 0$ due to outlier spikes/disconnections).*

### 2.2 Sensor-Derived Target Thermal Metrics
From the energy balance equation:
$$C_s \dot{T}_z = -UA\,T_z - c_{pa}(m_{inf}+m_{sa})T_z + UA\,T_o + c_{pa}\,m_{inf}\,T_o + c_{pa}\,m_{sa}\,T_{sa} + Q_{bg}$$

We extract two target physical calibration metrics from the sensor data:
* **Target Conductance ($UA_{\text{effective}}$):**
  $$UA_{\text{effective}} = UA + c_{pa}\,m_{inf} = \frac{Q_{AC} - Q_{bg}}{T_o - T_z} \approx \mathbf{52.83\text{ W/K}}$$
  *(Where $Q_{AC} = c_{pa}\,m_{sa}\,(T_z - T_{sa})$ and $Q_{bg} \approx 1.0\text{ W}$ for ESP32).*
* **Target Thermal Mass ($C_s$):**
  $$C_s = \frac{\int [UA_{\text{effective}} (T_o - T_z) + Q_{bg} - Q_{AC}] dt}{T_{z,\text{end}} - T_{z,\text{start}}} \approx \mathbf{3.80 \times 10^5\text{ J/K}}$$

---

## 3. Stage 1: Uncalibrated Baseline Simulation & High-Resolution Overlay Plotting

### Step 3.1 — EnergyPlus V25 Simulation Run
* **Command:** Execute desktop `energyplus.exe` on [`hanger_chamber_master.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_master.idf) with weather file `test_day_weather.epw`.
* **Output Extraction:** Process `eplusout.eso` using `ReadVarsESO.exe` to extract 1-minute resolution simulated zone temperatures:
  - $T_{\text{sim\_chamber}}(t)$: Chamber Zone Air Temperature (°C)
  - $T_{\text{sim\_hanger}}(t)$: Hanger Zone Air Temperature (°C)
  - $T_{\text{outdoor}}(t)$: Outdoor Dry-Bulb Temperature (°C)

### Step 3.2 — Overlay Plot Generation & Statistical Evaluation
* **Plot Output File:** [`sim_vs_sensors_exact_rig_match.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/sim_vs_sensors_exact_rig_match.png)
* **Visual Validation:** Compare $T_{\text{sim}}(t)$ against $T_z(t)$ (verifying that the 1-minute timesteps eliminate the flat "bathtub curve").
* **Metrics Calculated:**
  - Root Mean Square Error ($\text{RMSE} = \sqrt{\frac{1}{N}\sum (T_{\text{sim}} - T_z)^2}$)
  - Mean Absolute Error ($\text{MAE} = \frac{1}{N}\sum |T_{\text{sim}} - T_z|$)
  - Coefficient of Determination ($R^2$)

---

## 4. Stage 2: Automated Parameter Optimization Tuning Loops (Machine Learning Style)

Once the baseline plot is inspected:

1. **Parameter Tuning Bounds:**
   - Chamber PU Foam Conductivity ($k \in [0.015, 0.080]\text{ W/m·K}$)
   - Chamber Thermal Mass Density ($\rho \in [30.0, 150.0]\text{ kg/m}^3$)
   - Chamber Infiltration Rate ($\text{ACH} \in [0.10, 15.00]\text{ 1/hr}$)
   - Blower Air Flow Rate ($\dot{m} \in [0.010, 0.060]\text{ kg/s}$)

2. **Automated Optimizer Script:**
   - Runs iterative batch EnergyPlus simulations tuning parameters to hit target $UA_{\text{effective}} \approx 52.83\text{ W/K}$ and $C_s \approx 3.80 \times 10^5\text{ J/K}$ while minimizing RMSE.

---

## 5. Stage 3: Extended Kalman Filter (EKF) Convergence Verification

1. Feed cleaned sensor time-series into EKF algorithm.
2. Verify EKF estimated state parameters ($\alpha_o, \alpha_s$) converge within $\pm 20\%$ of calibrated model values.

---

## 6. Next Steps & Approval Workflow

1. **User Approval:** Please review this updated plan artifact.
2. **Execute Stage 1:** Upon your approval, we will launch the baseline simulation runner, extract 1-minute output data, and generate the overlay plot [`sim_vs_sensors_exact_rig_match.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/sim_vs_sensors_exact_rig_match.png).


Here is our exact step-by-step roadmap in simple terms (with EKF set aside):

---

### Step 1: Run Baseline & Plot
We run EnergyPlus on our updated **[`hanger_chamber_master.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_master.idf)** and plot the EnergyPlus simulated temperature curve alongside your real sensor data on a single comparison chart (`sim_vs_sensors_exact_rig_match.png`).

### Step 2: Inspect the Curve Match
We inspect the comparison plot together to check if our 1-minute timesteps and exact physical geometry eliminated the flat "bathtub curve" and captured the real temperature dynamics.

### Step 3: Run Automated Calibration Loop
We launch an automated optimization loop that repeatedly runs EnergyPlus, adjusting the chamber insulation ($k$), thermal mass ($\rho$), and air leakage ($\text{ACH}$) until the simulation curve matches your real sensor readings as closely as possible.