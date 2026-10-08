# Web Application EKF & BEM Calibration User Journey Plan

---

## 1. User-Centric Design Philosophy

The **SmartBEM Studio Web Application** is designed as a general-purpose, interactive platform for building engineers, facility managers, and researchers.

Rather than presenting static research results, the web application follows an **interactive 4-step user workflow**:

```
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ STEP 1: ENERGYPLUS IDF MODEL CALIBRATION                                    │
 │ • Select pre-calibrated baseline OR upload custom .idf + calibration data.  │
 │ • Verify baseline physical parameters (UA_0 = 5.76 W/K, Cs_0 = 25,000 J/K). │
 └─────────────────────────────────────┬───────────────────────────────────────┘
                                       │
 ┌─────────────────────────────────────▼───────────────────────────────────────┐
 │ STEP 2: EKF TELEMETRY & FILTER CONFIGURATION                                │
 │ • Select data source: Physical Test Rig Telemetry vs EnergyPlus BEM.        │
 │ • Choose architecture: Single EKF (Joint) vs Dual EKF (Multi-Rate).        │
 │ • Adjust Schmitt Trigger Hysteresis threshold triggers (tau_high, tau_low). │
 └─────────────────────────────────────┬───────────────────────────────────────┘
                                       │
 ┌─────────────────────────────────────▼───────────────────────────────────────┐
 │ STEP 3: REAL-TIME TELEMETRY & PARAMETER IDENTIFICATION                      │
 │ • Live state tracking plots (Temperature, Humidity, CO2).                  │
 │ • Occupant headcount step curve with hysteresis deadband protection.         │
 │ • Dynamic building parameter convergence trajectories (Cs, UA, m_inf).      │
 └─────────────────────────────────────┬───────────────────────────────────────┘
                                       │
 ┌─────────────────────────────────────▼───────────────────────────────────────┐
 │ STEP 4: EXECUTIVE BENCHMARKING & PARAMETER EXPORT                           │
 │ • Side-by-side performance cards (Occupancy Accuracy vs Parameter Error).   │
 │ • Download calibrated IDF parameters & estimated occupancy logs (CSV).       │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Detailed UI Component Breakdown

### Step 1: EnergyPlus IDF Model Calibration Studio

Before executing filter estimation, the user is presented with the **BEM Model Calibration Panel**:

* **Option A — Pre-Calibrated Model Select:**
  * Select from benchmark models (e.g. `Hanger Environmental Chamber (Calibrated v3)`).
* **Option B — Custom IDF Model Upload & Calibration:**
  * Upload custom EnergyPlus `.idf` model file.
  * Upload baseline empty-chamber calibration dataset (`Experimental_Rig_Calibration` telemetry).
* **Calibration Diagnostics Cards:**
  * Displays baseline overall heat transfer conductance ($UA_0 = 5.76\text{ W/K}$).
  * Displays baseline effective sensible thermal capacitance ($C_{s,0} = 25,000\text{ J/K}$).
  * Displays steady-state sensor measurement noise matrix ($R_{TT}=0.01^{\circ}\text{C}, R_{cc}=2.5\text{ ppm}$).

---

### Step 2: EKF Telemetry & Filter Configuration

Once the building model is selected/calibrated, the user configures the EKF estimation engine:

1. **Telemetry Data Source:**
   * **Physical Test Rig Stream:** 5-second sampling telemetry recorded inside the test chamber.
   * **EnergyPlus Digital Twin Stream:** Synthetic 1-minute telemetry generated from the calibrated IDF model.
2. **Occupancy Test Dataset Selection:**
   * Dropdown selection across **10 benchmark dataset profiles** (`day_3_p_1` to `day_4_p_6`), specifying scheduled occupant entry/exit phases (20–30 mins each).
3. **Filter Architecture Selection:**
   * **Single EKF (10-State Joint Filter):** 3 room conditions + 7 parameters updated together every 5 seconds.
   * **Dual EKF (Decoupled Multi-Rate Filter):** Fast 3-state filter (5s steps with RK4) + Slow 5-parameter filter (1-min steps with sigmoidal bounds).
4. **Hysteresis Threshold Adjuster:**
   * Sliders to adjust upper trigger ($\tau_{\text{high}} = 0.35$) and lower trigger ($\tau_{\text{low}} = 0.25$) for deadband chatter prevention.

---

### Step 3: Real-Time Telemetry & Parameter Tracking Dashboard

The main dashboard presents 3 interactive tabbed plot cards:

* **Tab 1: Environmental State Tracking:**
  * Real-time zone air temperature ($T_z$), humidity ratio ($\omega_z$), and $\text{CO}_2$ concentration ($c_z$) comparing measured values vs EKF filtered estimates.
* **Tab 2: Occupant Headcount Estimation:**
  * Displays ground truth headcount $N_{\text{gt}}(t)$, continuous estimate $\hat{N}(t)$, discrete integer count $N_{\text{disc}}(t)$, and the shaded hysteresis deadband zone ($0.25\text{--}0.35$).
* **Tab 3: Derived Building Parameters:**
  * Real-time convergence curves for Thermal Capacitance ($C_s$), Conductance ($UA$), and Infiltration Rate ($m_{\text{inf}}$) reaching ground truth physical bounds.

---

### Step 4: Executive Performance Benchmarks & Export

1. **Grouped Metric Cards:**
   * **Zone Occupancy Metrics:** Continuous MAE/RMSE, Exact Count Accuracy ($75.33\%$), Tolerant Accuracy ($96.86\%$), and Presence F1-Score ($0.82$).
   * **Building Parameter Metrics:** Thermal Capacitance Error ($3.05\%$), Conductance Error ($2.97\%$), Parameter Stability ($1.45\%$), and Physical Bounds Adherence ($100\%$).
2. **Side-by-Side Master Comparison Table:**
   * Compares Single EKF vs Dual EKF across Test Rig and EnergyPlus environments.
3. **Data & Model Export Panel:**
   * **Export Calibrated IDF:** Download updated EnergyPlus IDF file populated with EKF-identified physical building parameters.
   * **Export Telemetry Logs:** Download estimated state, occupancy, and parameter trajectories in CSV format.

---

## 3. MathJax Formula & Methodology Drawer

An expandable accordion drawer allows users to inspect the mathematical foundations:

* **Appendix A:** Single EKF 10-State differential equations.
* **Appendix B:** Dual EKF RK4 integration & Sigmoidal parameter bounds.
* **Appendix C:** Sensor measurement noise matrix $R$ & Dynamic fan process noise $Q_k(m_{sa})$.
* **Appendix D:** Schmitt trigger hysteresis threshold equations & metric formulas.
* **Appendix E:** Analytical proof of baseline chamber parameters ($UA_0 = 5.76\text{ W/K}, C_{s,0} = 25,000\text{ J/K}$).
