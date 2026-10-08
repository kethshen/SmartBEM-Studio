# EnergyPlus Pulldown Curvature & Calibrated Parameter Master Plan (ASHRAE Guideline 14 & 10-Min Terminal Execution Revision)

**Target Artifact Path:** [`calibration_curvature_and_bounds_plan.md`](file:///C:/Users/ASUS/.gemini/antigravity-ide/brain/30f9feb6-f7e5-40c7-a4be-f148a0753aa8/calibration_curvature_and_bounds_plan.md)  
**Cleaned Dataset Reference:** [`Idel_test_2026_07_21_cleaned.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/experimental_data/cleaned/Idel_test_2026_07_21_cleaned.csv)  
**Target Master IDF:** [`hanger_chamber_master.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_master.idf)

---

## 1. Standard Building Energy Model (BEM) Calibration Metrics

To adhere to industry-standard building calibration protocols (**ASHRAE Guideline 14** and **IPMVP**), we replace ad-hoc loss equations with standard statistical calibration metrics:

### 1. Coefficient of Variation of Root Mean Square Error ($\text{CV(RMSE)}$)
$$\text{CV(RMSE)} = \frac{1}{\bar{T}_z} \sqrt{\frac{\sum_{i=1}^N \Big(T_{\text{sim}}(t_i) - T_z(t_i)\Big)^2}{N - p}} \times 100\%$$

* **ASHRAE Guideline 14 Standard Target:** $\text{CV(RMSE)} \le 5.0\%$ for sub-hourly calibration.

### 2. Normalized Mean Bias Error ($\text{NMBE}$)
$$\text{NMBE} = \frac{1}{\bar{T}_z} \frac{\sum_{i=1}^N \Big(T_{\text{sim}}(t_i) - T_z(t_i)\Big)}{N - p} \times 100\%$$

* **ASHRAE Guideline 14 Standard Target:** $|\text{NMBE}| \le 2.0\%$.

### 3. Dynamic Time Warping Distance ($\text{DTW}$)
* Standard time-series trajectory shape similarity metric that measures structural curvature alignment without time-lag penalties.

---

## 2. 10-Minute Terminal Self-Run Execution Strategy

Since each EnergyPlus iteration takes $\approx 1.5\text{ seconds}$ on desktop, a **10-minute terminal run** permits **$300\text{ to }400\text{ iterations}$**, enabling comprehensive parameter space exploration.

### Optimizer Recommendations for 10-Minute Terminal Run
1. **Algorithm Choice:**
   * **Option A (Recommended):** `scipy.optimize.minimize` using **Powell** or **Nelder-Mead** with parameter bounds.
   * **Option B:** `skopt.gp_minimize` (Bayesian Optimization with Gaussian Processes) over 300 evaluations.
2. **Terminal Feedback & Real-Time Logging:**
   * Prints live iteration table: `Iter #`, $k_{\text{foam}}$, $c_{p, \text{foam}}$, $\rho_{\text{foam}}$, $\text{ACH}$, $Q_{\text{cool}}$, `CV(RMSE)%`, `NMBE%`, and `Loss`.
3. **Automatic Checkpointing & Deliverables:**
   * Saves the current best IDF copy (`hanger_chamber_calibrated.idf`) whenever a new best loss is discovered.
   * Generates the final high-resolution overlay plot ([`Readings_from_rig/plots/calibrated_sim_vs_sensors.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/calibrated_sim_vs_sensors.png)) automatically upon completion.

---

## 3. Simulation Setup & Initial Conditions

* **Calculation Timestep:** **1-Minute Timestep** (`Timestep: 60` extracted from `eplusout.eso`).
* **Test Duration:** $170.1\text{ minutes}$ (171 comparison points mapped 1-to-1 against cleaned EMA $T_z$).
* **Initial Start Temp ($t=0$):** **$29.9^{\circ}\text{C}$** (exact match to sensor reading at test start).
* **Thermostat Setpoint:** **$20.0^{\circ}\text{C}$**.
* **Outdoor Weather:** Real time-varying $T_{\text{outside}}(t)$ from `Idel_test_2026_07_21_cleaned.csv`.

---

## 4. Parameter Bounds & Initial Guesses (5 Parameters)

| Parameter | Symbol | Initial Guess | Lower Bound | Upper Bound | Unit | Physical Role |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **PU Foam Conductivity** | $k_{\text{foam}}$ | $0.0250$ | **$0.0150$** | **$0.0450$** | $\text{W/(m}\cdot\text{K)}$ | Thermal insulation envelope resistance |
| **PU Foam Specific Heat** | $c_{p, \text{foam}}$ | $1400.0$ | **$800.0$** | **$1800.0$** | $\text{J/(kg}\cdot\text{K)}$ | Wall heat storage capacity |
| **PU Foam Density** | $\rho_{\text{foam}}$ | $32.0$ | **$20.0$** | **$45.0$** | $\text{kg/m}^3$ | Structural wall mass density |
| **Chamber Infiltration** | $\text{ACH}$ | $0.10$ | **$0.01$** | **$0.50$** | $\text{hr}^{-1}$ | Air leakage rate |
| **Peak AC Pulldown Power** | $Q_{\text{cool}}$ | $600.0$ | **$300.0$** | **$1200.0$** | $\text{W}$ | Initial compressor cooling velocity |

---

## 5. Convergence & Stopping Criteria

The optimization run terminates when:
1. **ASHRAE Calibration Target Achieved:** $\text{CV(RMSE)} \le 5.0\%$ and $|\text{NMBE}| \le 2.0\%$.
2. **Iteration Cap Reached:** Max **300 iterations** (or 10 minutes terminal execution time).
