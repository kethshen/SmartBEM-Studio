# EKF Estimation Diagnostics & Implementation Fix Plan

This document addresses the parameter estimation discrepancies observed in [`EKF/test_rig_ekf/results_plots/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_ekf/results_plots/), validates your advisor's EnergyPlus simulation baseline strategy, explains the physical root causes of parameter divergence, and outlines the exact steps to fix the estimation accuracy based on your comments.

---

## 1. Validation of Your Advisor's Simulation Strategy

> **User Question:** *"My advisor told me to run an EnergyPlus simulation with the `with_occ` datasets and get baseline parameter plots. Is it accurate what he told?"*

### **Answer: YES, 100% ACCURATE AND SCIENTIFICALLY ESSENTIAL.**

In systems identification and Kalman filter research (e.g. DTU grey-box building thermal modeling literature), validating an Extended Kalman Filter follows a mandatory 2-phase workflow:

```
Phase 1: Simulation Verification (EnergyPlus)  --->  Phase 2: Physical Test Rig Validation
[Exact Known Ground-Truth Parameters]                 [Real Noisy Physical Rig Telemetry]
```

### Why your advisor's strategy is correct:
1. **Known Ground Truth:** In real physical test rig data, parameters like internal thermal wall coupling ($C_s$) and infiltration ($\dot{m}_{\text{inf}}$) cannot be directly measured by standard sensors. In EnergyPlus, you set exact material properties ($k_{\text{foam}}, c_{p,\text{foam}}, \text{ACH}$), providing a **true numerical benchmark**.
2. **Isolation of Error Sources:** Running EKF on EnergyPlus simulation outputs tests whether the EKF algorithm structure works under perfect, noise-free physics. If EKF works in EnergyPlus simulation but struggles on rig data, the issue is sensor calibration/unmodeled duct dynamics. If EKF fails in EnergyPlus simulation, the issue is internal filter tuning ($Q, R, X_0$).

---

## 2. Why Are EKF Environmental States Good, but Physical Parameters & Occupancy Bad?

### **Observation Summary:**
* **`EKF_States_3Subplots.png` (EXCELLENT):** $T_z, RH_z, c_z$ track sensor telemetry almost perfectly.
* **`EKF_Occupancy_vs_GroundTruth.png` (BAD):** Occupancy step transitions are missed or lagged.
* **`EKF_Derived_Physical_Parameters.png` (BAD):** $C_s, M, UA$ spike to high values outside expected green bands.

---

### **Root Cause 1: Parameter Unidentifiability & Lack of System Excitation**
In Kalman filtering theory, parameters ($\alpha_s, \beta_s$) are **unmeasured latent states**. They can only be updated when the system is actively driven by external thermal/mass inputs (system excitation).

* **The Math:**
  $$\frac{dT_z}{dt} = \alpha_o (T_o - T_z) + \mathbf{\alpha_s} \cdot \dot{m}_{sa} (T_{sa} - T_z) + \alpha_e$$
* **The Problem:** When supply air flow $\dot{m}_{sa} \approx 0$ or supply air temperature matches room temperature ($T_{sa} \approx T_z$), the term $\mathbf{\alpha_s} \cdot \dot{m}_{sa} (T_{sa} - T_z) \rightarrow 0$.
* **Consequence:** $\alpha_s$ becomes mathematically **unobservable/unidentifiable**. Because $C_s = \frac{c_{pa}}{\alpha_s}$, dividing by a near-zero $\alpha_s$ causes estimated thermal capacitance $C_s$ to spike to millions ($140,000\text{ kJ/}^\circ\text{C}$).

---

### **Root Cause 2: Measurement Feedback vs Parameter Leakage**
* Physical states ($T_z, \omega_z, c_z$) receive **direct sensor feedback** ($Z_k = [T_{z,\text{meas}}, \omega_{z,\text{meas}}, c_{z,\text{meas}}]^T$). Because measurement noise $R$ is small, the EKF forces physical states to match sensor readings directly.
* However, parameter updates rely entirely on backpropagating state innovation errors through the Jacobian $J_F$. If process noise $Q$ for parameters is improperly balanced relative to state noise $Q$, the EKF assigns all measurement error to state noise rather than parameter adaptation.

---

### **Root Cause 3: Unphysical Initial State Vectors ($X_0$)**
Currently, $X_0$ initializes $\beta_s = 0.010 \text{ kg}^{-1} \cdot \text{s}^{-1}$.  
At $t=0$, $M = \frac{1}{\beta_s} = \frac{1}{0.010} = \mathbf{100\text{ kg}}$ (14 times larger than the real $7.00\text{ kg}$ chamber air mass!).  
Starting the filter 1400% away from physical reality forces the EKF to spend the entire run attempting to converge, causing parameter drift.

---

## 3. Action Plan to Fix EKF Parameter & Occupancy Estimation

---

### **Step 1: Physically Informed Initialization ($X_0$) for ALL 7 Parameters**

Initialize all 7 parameter states anchored directly at physical expected values at $t=0$:

| Parameter State | Physical Meaning | Formula / Basis | Exact Initial Value ($X_0$) |
| :--- | :--- | :--- | :---: |
| **$\alpha_{s,0}$** | Supply Air Thermal Coupling | $\frac{c_{pa}}{C_{s,0}} = \frac{1006.0}{25000.0\text{ J/K}}$ | **`0.0402`** $[1/(\text{kg}\cdot\text{s})]$ |
| **$\beta_{s,0}$** | Supply Air Mixing Fraction | $\frac{1}{M_{\text{room},0}} = \frac{1}{7.00\text{ kg}}$ | **`0.1428`** $[1/(\text{kg}\cdot\text{s})]$ |
| **$\alpha_{o,0}$** | Envelope Heat Coupling | $\frac{UA_0}{C_{s,0}} = \frac{5.76\text{ W/K}}{25000.0\text{ J/K}}$ | **`0.00023`** $[1/\text{s}]$ |
| **$\beta_{o,0}$** | Infiltration Coupling | $\frac{\dot{m}_{\text{inf},0}}{M_{\text{room},0}} = \frac{2.14 \times 10^{-5}}{7.00\text{ kg}}$ | **`3.06e-6`** $[1/\text{s}]$ |
| **$\alpha_{e,0}$** | Internal Heat Bias | Zero equipment heat at $t=0$ | **`0.0000`** $[^\circ\text{C}/\text{s}]$ |
| **$\beta_{e,0}$** | Internal Moisture Bias | Zero unmodeled moisture at $t=0$ | **`0.0000`** $[\text{kg}_w/(\text{kg}_a\cdot\text{s})]$ |
| **$\gamma_{e,0}$** | Occupancy $\text{CO}_2$ Generation | Zero occupants in chamber at $t=0$ | **`0.0000`** $[\text{ppm}/\text{s}]$ |

---

### **Step 2: Parameter Bounds & Hard Physical Clipping (In EKF Loop)**

> **User Question:** *"Do you mean this in plotting or in the EKF run itself?"*  
> **Answer:** **IN THE EKF RUN LOOP ITSELF!**

In Control Theory, this is known as **Constrained / Projected Kalman Filtering** (Simon 2010).  
Immediately after the EKF measurement correction update $X_{k|k} = X_{pred} + K_k \cdot y_k$, the updated state vector $X_{k|k}$ is projected onto its physical feasibility domain before proceeding to step $k+1$:

```python
# Executed inside the EKF loop right after X = X_pred + K @ y:
X[I_as] = np.clip(X[I_as], 1006.0 / 50000.0, 1006.0 / 10000.0) # Cs bounded to 10 - 50 kJ/K
X[I_bs] = np.clip(X[I_bs], 1.0 / 10.0, 1.0 / 5.0)              # M bounded to 5 - 10 kg
X[I_ao] = np.clip(X[I_ao], 2.0 / 50000.0, 15.0 / 10000.0)      # UA bounded to 2 - 15 W/K
X[I_ge] = np.clip(X[I_ge], 0.0, 4.0 * 0.7716)                 # N bounded to 0 - 4 persons
```

This prevents non-physical division-by-zero spikes and ensures state predictions remain stable.

---

### **Step 3: Excitation-Aware Parameter Updating (Gating)**

> **User Question:** *"Is this a valid scientific method?"*  
> **Answer:** **YES, IT IS A STANDARD SCIENTIFIC METHOD IN ADAPTIVE CONTROL & SYSTEM IDENTIFICATION KNOWN AS "PERSISTENT EXCITATION GATING" OR "CONDITIONAL UPDATING".**

#### Scientific Validation:
In system identification literature (Ljung 1999, *System Identification: Theory for the User*; Åström & Wittenmark 1995, *Adaptive Control*):
* **The Principle of Persistent Excitation:** A parameter $\theta$ can only be identified when its regression gradient vector $\phi_k = \frac{\partial f}{\partial \theta} \neq 0$.
* **What Happens Without Gating:** When supply air flow $\dot{m}_{sa} = 0$, the gradient $\frac{\partial f}{\partial \alpha_s} = 0$. If you update $\alpha_s$ when the gradient is zero, measurement noise in temperature $T_z$ leaks into $\alpha_s$, causing $\alpha_s$ to drift randomly (covariance windup).
* **The Gating Rule:**
  $$\text{If } |\dot{m}_{sa}| < \epsilon \quad \implies \quad K_{\alpha_s} = 0, \quad K_{\beta_s} = 0$$
  This temporarily freezes parameter updates during unexcited periods, preserving their true physical values until excitation returns!

---

### **Step 4: Execute EnergyPlus Baseline Simulation (Advisor's Task)**
1. Run EnergyPlus simulation for `Day_3` and `Day_4` datasets with the calibrated IDF file.
2. Feed EnergyPlus simulated $T_z, \omega_z, c_z$ outputs into `Real_EKF_TestRig.py`.
3. Compare EKF estimated $\alpha_o \dots \gamma_e$ against the EnergyPlus theoretical baseline.
