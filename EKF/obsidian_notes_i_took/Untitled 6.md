# Proposed Outline for EKF Progress Summary Report to Advisor

This updated outline structures the report primarily around **Single 10-State EKF** and **Multi-Rate Decoupled Dual EKF**, evaluating each model on both **Experimental Test Rig** data and **EnergyPlus BEM Benchmark** data.

> [!NOTE]
> All ROBOD references are **100% excluded**.

---

## 📋 Proposed Report Structure

### **1. Executive Overview & Signal Processing Foundation**
* **Project Scope:** Multi-occupant headcount estimation and physical building parameter identification ($C_s, UA, m_{\text{inf}}$).
* **Empirical Measurement Noise ($R$):** Calibrated from steady-state empty-chamber experiments ($R_{TT} = 0.01$, $R_{ww} = 4\times 10^{-8}$, $R_{cc} = 6.25$).
* **Dynamic Airflow Process Noise ($Q_k$):** Scaled via fan mass flow rate: $Q_k = Q_{\text{base}} + Q_{\text{flow}} \cdot \tanh(m_{sa} / 0.010)$.
* **Hysteresis Deadband Thresholding (Schmitt Trigger):** Upper trigger ($\tau_{\text{high}} = 0.35$) and lower deadband trigger ($\tau_{\text{low}} = 0.25$) to eliminate boundary chatter.
* **Physical Boundary Bounds:** Enforced identically across both models ($C_s \in [20, 30]\text{ kJ/K}$, $UA \in [5.0, 6.5]\text{ W/K}$, $m_{\text{inf}} \in [0.0, 0.10]\text{ g/s}$). 

---

### **2. Single 10-State Joint EKF (Formulation & Performance)**
* **Mathematical Formulation:** 10-D unified state-parameter vector $X = [\alpha_o, \alpha_s, \alpha_e, \beta_o, \beta_s, \beta_e, \gamma_e, T_z, w_z, c_z]^T$ running at 5-second sampling steps ($DT = 5\text{s}$).
* **2.1 Experimental Test Rig Results (Days 3 & 4):**
  * Occupancy Metrics (Continuous MAE, RMSE, Peak Error, Hysteresis Exact Accuracy %, $\pm 1$-Person Accuracy %, F1-Score).
  * Parameter Identification Metrics ($\text{MAPE}_{C_s} \%$, $\text{MAPE}_{UA} \%$, $\text{PBAR} \%$, $\text{CV} \%$).
* **2.2 EnergyPlus BEM 1-Min Benchmark Results:**
  * Occupancy Metrics & Parameter Identification Metrics on 1-min resampled digital twin datasets.

---

### **3. Multi-Rate Decoupled Dual EKF (Formulation & Performance)**
* **Mathematical Formulation:** Interleaved dual filters—3-State Fast State EKF ($T_z, w_z, c_z$ at $DT=5\text{s}$ via RK4) + 5-State Slow Parameter EKF ($\xi$ at 1-min windows) with Sigmoidal Boundary Mapping.
* **3.1 Experimental Test Rig Results (Days 3 & 4):**
  * Occupancy Metrics (Continuous MAE, RMSE, Peak Error, Hysteresis Exact Accuracy %, $\pm 1$-Person Accuracy %, F1-Score).
  * Parameter Identification Metrics ($\text{MAPE}_{C_s} \%$, $\text{MAPE}_{UA} \%$, $\text{PBAR} \%$, $\text{CV} \%$).
* **3.2 EnergyPlus BEM 1-Min Benchmark Results:**
  * Occupancy Metrics & Parameter Identification Metrics on 1-min resampled digital twin datasets.

---

### **4. Comparative Analysis & Key Scientific Findings**
* **Head-to-Head Comparison Table:** Single EKF vs Dual EKF across both Test Rig and EnergyPlus environments.
* **Key Finding 1 (Occupancy):** Single EKF fast short-term step response ($75.33\%$ exact count accuracy, $\text{F1} = 0.8188$).
* **Key Finding 2 (Building Physics):** Dual EKF multi-rate timescale separation filters out sensor noise, achieving **5x higher parameter precision** ($\text{MAPE}_{C_s} = 3.05\%$, $\text{MAPE}_{UA} = 2.97\%$) and **ultra-low parameter jitter** ($\text{CV} = 1.45\%$).
* **Conclusion for Advisor:** Dual EKF established as the indispensable framework for real-time HVAC Model Predictive Control (MPC) and EnergyPlus IDF digital twin calibration.
