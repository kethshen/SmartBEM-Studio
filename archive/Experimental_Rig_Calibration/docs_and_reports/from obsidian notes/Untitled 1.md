# Implementation Plan — Sensor Data Cleaning and Parameter Calibration Target Extraction

This plan details the technical steps to clean the fragmented 4-part Day 1 dataset, apply the advisor's thermodynamic energy equations, and extract the target overall heat transfer conductance ($UA_{\text{effective}}$) and sensible thermal capacitance ($C_s$) of the experimental cool room chamber. 

These extracted targets will ground the EnergyPlus model in physical reality before EKF validation begins.

---

## User Review Required

Please review and confirm the following key parameter assumptions that will be coded into the analysis script:

> [!IMPORTANT]
> 1. **Sensor Weighting for $T_z$:** We will compute the spatial chamber temperature using $T_z = 0.6 \cdot T_{\text{S1}} + 0.4 \cdot T_{\text{S2}} + 0.0 \cdot T_{\text{S3}}$, assigning a weight of 0 to Sensor 3 because it experienced severe connection issues and was fully offline during Part 6.
> 2. **Negligible Background Heat ($Q_{bg}$):** We assume $Q_{bg} = 1.0\text{ W}$ since only an ESP32 micro-controller resides inside the chamber (no large internal heat loads, lights, or occupants).
> 3. **Duct Dimensions:** We will use a standard supply duct diameter of $15\text{ cm}$ (giving cross-sectional area $A_{\text{duct}} \approx 0.0177\text{ m}^2$) for the air mass flow rate calculations, unless you specify a different duct size.

---

## Proposed Changes

We will create a self-contained, clean data analysis pipeline inside the `Readings_from_rig/` folder.

### Data Processing Component

#### [NEW] [clean_and_calculate.py](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/clean_and_calculate.py)
A Python script utilizing `pandas` and `numpy` to run the following sequence:

1. **Data Ingestion:** Load the 4 CSV files (`Full Day 1 part 1`, `part 2`, `part 5`, `part 6`).
2. **Outlier Filtering:**
   * Clip any temperature values $> 60^{\circ}\text{C}$ or $< -30^{\circ}\text{C}$ to remove ADC glitches.
   * Remove the severe return temperature spike (86°C) in Part 6 using a rolling window median/IQR filter.
3. **Sensor Merging:**
   * Calculate the spatial average temperature $T_z = 0.6 \cdot T_{\text{room\_1}} + 0.4 \cdot T_{\text{room\_2}}$.
4. **EMA Smoothing:** Apply an Exponential Moving Average with a span of 30 seconds (6 timesteps) to all variables to filter out sensor jitter.
5. **AC Power Calculation:**
   * Read the `fan` % column.
   * Convert `fan` % to velocity $v$ (m/s) using the lookup mapping in `fan_value_and_anemometer.csv`.
   * Compute mass flow rate: $\dot{m}_{\text{air}} = 1.2 \cdot v \cdot 0.0177$.
   * Compute $Q_{\text{AC}} = \dot{m}_{\text{air}} \cdot 1006 \cdot (T_z - T_{\text{supply}})$.
6. **Steady-State Calculation (Step 3 Target):**
   * Identify steady-state regions: the tail of Part 2 and the tail of Part 6 (where $T_z$ change is $< 0.1^{\circ}\text{C}$ over 15 minutes).
   * Calculate $UA_{\text{effective}} = (Q_{\text{AC}} - Q_{bg}) / (T_o - T_z)$.
7. **Dynamic Pulldown Calculation (Step 4 Target):**
   * Identify pulldown regions: the start of Part 1 and Part 5.
   * Calculate $Q_{\text{net}, i} = UA_{\text{effective}} \cdot (T_{o, i} - T_{z, i}) + Q_{bg} - Q_{\text{AC}, i}$.
   * Integrate over the window: $E_{\text{total}} = \sum (Q_{\text{net}, i} \cdot 5.0\text{ seconds})$.
   * Calculate $C_s = E_{\text{total}} / (T_{z,\text{end}} - T_{z,\text{start}})$.
8. **Reporting:** Print the computed values for each segment and their final averages.

---

## Verification Plan

### Automated Verification
* Run `clean_and_calculate.py` and verify:
  - The script runs to completion without NaN or division-by-zero errors.
  - Calculated $UA_{\text{effective}}$ values for Part 2 and Part 6 are positive and agree within $\pm 20\%$.
  - Calculated $C_s$ values for Part 1 and Part 5 are positive and agree within $\pm 20\%$.

### Manual Review
* Check the generated console outputs against expected physics scales:
  - $UA_{\text{effective}}$ should be in the range of $5$ to $40\text{ W/K}$ for a $2\text{m} \times 2\text{m} \times 2\text{m}$ insulated box.
  - $C_s$ should be in the range of $10^5$ to $5 \times 10^5\text{ J/K}$ (accounting for air thermal capacitance + PU foam wall thermal mass + rig framing).
