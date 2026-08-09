# Experimental Rig Datasets Revision & Cleaning Audit Document

**Data Folder:** [`Readings_from_rig/experimental_data/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/experimental_data/)  
**Target Cleaned Folder:** [`Readings_from_rig/experimental_data/cleaned/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/experimental_data/cleaned/)  
**Analysis Reference:** [`sensor_data_analysis.md`](file:///C:/Users/ASUS/.gemini/antigravity-ide/brain/30f9feb6-f7e5-40c7-a4be-f148a0753aa8/sensor_data_analysis.md)

---

## 1. Intent & Overview

This document presents the complete, scientifically sufficient 3-stage data cleaning methodology (**Range Masking + Rolling 3-Sigma / IQR Filter + Linear Interpolation**).

---

## 2. Why Range Masking + Rolling 3-Sigma / IQR is 100% Sufficient

For physical temperature time-series data, this simple 3-stage pipeline is **100% complete and statistically robust**:

1. **Stage 1 — Plausible Physical Range Masking:**
   * Mask values outside $[5.0^{\circ}\text{C}, 50.0^{\circ}\text{C}] \rightarrow \text{NaN}$.
   * *Why it works:* Instantly catches all electrical disconnection dropouts ($-14.5^{\circ}\text{C}, 0.0^{\circ}\text{C}, +98.5^{\circ}\text{C}, +86.7^{\circ}\text{C}$).

2. **Stage 2 — Rolling 3-Sigma ($\mu \pm 3\sigma$) / IQR Local Filter:**
   * Evaluate a 2-minute rolling window (~24 samples).
   * Flag and set to `NaN` any sample that deviates from the local rolling mean $\mu$ by more than 3 standard deviations ($|x_i - \mu| > 3\sigma$).
   * *Why it works:* Catches any remaining subtle electrical noise spikes without distorting the physical cooling curve.

3. **Stage 3 — Linear NaN Interpolation:**
   * Replace `NaN` values using `df.interpolate(method='linear')`.
   * *Why it works:* Smoothly connects gaps using the true physical trend line.

---

## 3. Exact 3-Task Execution Sequence

```
===================================================================================
TASK 1: CLEANING & EXPORTING 5 CLEANED CSVs + BEFORE VS AFTER PLOTS
-----------------------------------------------------------------------------------
• Take each of the 5 raw CSV files from experimental_data/
• Step 1.1: Range Masking (< 5.0°C or > 50.0°C set to NaN)
• Step 1.2: Rolling 3-Sigma / IQR Filter (2-minute window: flag if |x - mean| > 3*std)
• Step 1.3: Linear NaN Interpolation (df.interpolate(method='linear'))
• Save 5 new cleaned CSV files in experimental_data/cleaned/
• Generate Before-Clean vs After-Clean comparison plots for each dataset

===================================================================================
TASK 2: WEIGHTED AVERAGE CALCULATION & PLOTS
-----------------------------------------------------------------------------------
• Using the cleaned CSV files, compute:
  Tz(t) = 0.50 * Sensor_1(Bosch) + 0.30 * Sensor_2 + 0.20 * Sensor_3
• Append Tz(t) column into the cleaned CSV files
• Generate Weighted Average Tz vs Individual Cleaned Sensors plots for all 5 datasets

===================================================================================
TASK 3: EXPONENTIAL MOVING AVERAGE (EMA) SMOOTHING (IF NEEDED)
-----------------------------------------------------------------------------------
• Apply EMA smoothing filter during plotting if needed for visual comparison
===================================================================================
```

---

## 4. List of 5 CSV Datasets to Process

| Dataset # | Raw CSV Input Filename | Cleaned CSV Output Filename | Task 1 & 2 Plot Output Names |
|:---:|:---|:---|:---|
| **1** | `Idel_test_2026_07_21.csv` | `cleaned/Idel_test_2026_07_21_cleaned.csv` | `plots/01_idle_before_vs_after.png`<br>`plots/01_idle_weighted_tz.png` |
| **2** | `Full Day 1 part 1_2026-07-23.csv` | `cleaned/Full_Day_1_part_1_cleaned.csv` | `plots/02_part1_before_vs_after.png`<br>`plots/02_part1_weighted_tz.png` |
| **3** | `Full day 1 part 2_2026-07-23.csv` | `cleaned/Full_Day_1_part_2_cleaned.csv` | `plots/03_part2_before_vs_after.png`<br>`plots/03_part2_weighted_tz.png` |
| **4** | `Full Day 1 part 5_2026-07-23.csv` | `cleaned/Full_Day_1_part_5_cleaned.csv` | `plots/04_part5_before_vs_after.png`<br>`plots/04_part5_weighted_tz.png` |
| **5** | `Full Day 1 part 6_2026-07-23.csv` | `cleaned/Full_Day_1_part_6_cleaned.csv` | `plots/05_part6_before_vs_after.png`<br>`plots/05_part6_weighted_tz.png` |

---

## 5. Next Steps Workflow

1. **User Final Review:** Please review this updated sequence artifact.
2. **User Confirmation:** When you give the green light, we will execute Tasks 1, 2, and 3!


# Stage 2 — Automated Parameter Calibration Loop Implementation Plan

This plan details the technical execution of **Stage 2: Automated Parameter Calibration Loop**. We will launch an automated optimization script that updates [`hanger_chamber_master.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_master.idf), executes desktop EnergyPlus runs in parallel/series, and minimizes the temperature trajectory error between $T_{\text{sim}}(t)$ and the cleaned sensor data $T_z(t)$ from [`Idel_test_2026_07_21_cleaned.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/experimental_data/cleaned/Idel_test_2026_07_21_cleaned.csv).

---

## 1. Calibration Parameters & Search Space

We will calibrate 5 physical parameters within realistic, physical limits:

| Parameter | Description | Initial Guess | Search Bounds | Physical Role |
| :--- | :--- | :---: | :---: | :--- |
| $k_{\text{foam}}$ | Polyurethane Foam Thermal Conductivity | $0.030\text{ W/(m}\cdot\text{K)}$ | $[0.020, 0.050]\text{ W/(m}\cdot\text{K)}$ | Envelope conduction resistance ($UA_{\text{effective}}$) |
| $c_{p, \text{foam}}$ | PU Foam Specific Heat Capacity | $1400\text{ J/(kg}\cdot\text{K)}$ | $[1000, 2000]\text{ J/(kg}\cdot\text{K)}$ | Wall thermal capacitance ($C_s$) |
| $\rho_{\text{foam}}$ | PU Foam Density | $32.0\text{ kg/m}^3$ | $[20.0, 50.0]\text{ kg/m}^3$ | Wall mass density |
| $\text{ACH}_{\text{chamber}}$ | Air Infiltration Rate | $0.10\text{ hr}^{-1}$ | $[0.01, 1.00]\text{ hr}^{-1}$ | Infiltration heat loss/gain |
| $Q_{\text{cool, max}}$ | Effective Cooling Capacity | $350\text{ W}$ | $[150, 700]\text{ W}$ | Transient pulldown rate |

---

## 2. Objective Function & Optimization Algorithm

We formulate the calibration as a bounded numerical minimization problem:

$$\min_{\boldsymbol{\theta}} J(\boldsymbol{\theta}) = \sqrt{\frac{1}{N} \sum_{i=1}^N \Big(T_{\text{sim}}(t_i; \boldsymbol{\theta}) - T_z(t_i)\Big)^2}$$

* **Optimization Method:** `scipy.optimize.minimize` using **L-BFGS-B** (or **Nelder-Mead / Powell**) with parameter scaling.
* **Target Metric:** $\text{RMSE} < 0.5^{\circ}\text{C}$ and $R^2 > 0.95$.

---

## 3. Proposed File Changes

### [NEW] [`run_stage2_calibration.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/scripts/run_stage2_calibration.py)
A dedicated automated Python calibration runner that:
1. Accepts parameter vector $\boldsymbol{\theta} = [k, c_p, \rho, \text{ACH}, Q_{\text{cool}}]$.
2. Modifies standard IDF fields in a temporary working copy.
3. Executes `C:\EnergyPlusV25-2-0\energyplus.exe`.
4. Extracts $T_{\text{sim}}(t)$ from `eplusout.eso`.
5. Computes loss $J(\boldsymbol{\theta})$ against $T_z(t)$.
6. Plots the optimization trajectory and saves the calibrated IDF as [`hanger_chamber_calibrated.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_calibrated.idf).

---

## 4. Verification & Output Deliverables

1. **Calibrated IDF:** `hanger_chamber_calibrated.idf` with verified physical properties.
2. **Final Calibration Plot:** High-resolution comparison plot saved to [`Readings_from_rig/plots/calibrated_sim_vs_sensors.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/calibrated_sim_vs_sensors.png).
3. **Statistical Summary Report:** Table of optimal parameters, final RMSE, MAE, and $R^2$.


Here is how the automated optimization loop works in simple, step-by-step terms:

---

### Step 1: Start with Initial Guesses
The Python script loads initial estimates for your chamber's physical properties:
* Insulation quality ($k$-value of PU foam)
* Wall heat storage capacity (foam density & specific heat)
* Air leakage (infiltration rate)
* AC cooling strength

---

### Step 2: Run EnergyPlus Simulation
The computer automatically runs EnergyPlus in the background using those current settings to generate a simulated temperature curve over time.

---

### Step 3: Compare with Real Rig Sensors
The script compares the simulated temperature line against your cleaned 3-sensor rig temperature curve ($T_z$). It calculates the gap (error) between the two lines.

---

### Step 4: Adjust Settings Automatically (The "Tuner Knob")
An optimization algorithm acts like an automated tuner:
* If the simulation cools down **too slowly**, it slightly increases AC strength or reduces wall heat storage.
* If the simulation cools down **too quickly**, it adds more wall thermal mass or changes insulation resistance.

---

### Step 5: Repeat in a Fast Loop
Steps 2 to 4 repeat automatically in a loop. With every run, the algorithm fine-tunes the parameters to pull the red simulation line closer and closer onto your green real sensor line.

---

### Step 6: Save Calibrated Model
Once the gap (error) between the simulation curve and real sensor data is as small as physically possible, the loop stops. The script saves the final optimal parameters into a new calibrated model file ([`hanger_chamber_calibrated.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_calibrated.idf)) and plots the final overlay graph.