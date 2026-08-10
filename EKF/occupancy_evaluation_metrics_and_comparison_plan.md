# Occupancy Estimation Accuracy Metrics & Single vs Dual EKF Comparison Framework

This document outlines the **mathematical evaluation metrics**, **automated decision threshold optimization method**, and **comparative benchmark framework** for evaluating occupancy estimation accuracy across the Experimental Test Rig and EnergyPlus BEM datasets.

---

## 1. 📐 Mathematical Evaluation Metrics

To evaluate continuous and discretized occupant estimations against the Ground Truth schedule ($N_{\text{gt}}$), we use a multi-metric suite combining **continuous regression errors**, **discrete count precision**, and **occupancy presence classification**.

### A. Continuous Estimation Metrics ($\hat{N}_{\text{cont}}$ vs $N_{\text{gt}}$)

1. **Root Mean Square Error (RMSE):**
   Penalizes large transient estimation spikes or delayed responses.
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{k=1}^{N} \left(\hat{N}_{\text{cont},k} - N_{\text{gt},k}\right)^2} \quad [\text{persons}]$$

2. **Mean Absolute Error (MAE):**
   Measures average headcount discrepancy across all timesteps.
   $$\text{MAE} = \frac{1}{N} \sum_{k=1}^{N} \left|\hat{N}_{\text{cont},k} - N_{\text{gt},k}\right| \quad [\text{persons}]$$

3. **Peak Occupancy Recovery Error ($\Delta N_{\text{peak}}$):**
   Measures the filter's ability to capture maximum room capacity during peak hours.
   $$\Delta N_{\text{peak}} = \left| \max_k(\hat{N}_{\text{cont},k}) - \max_k(N_{\text{gt},k}) \right| \quad [\text{persons}]$$

---

### B. Discretized Integer Metrics ($N_{\text{disc}}$ vs $N_{\text{gt}}$)

1. **Exact Integer Count Accuracy ($A_{\text{exact}}$):**
   Percentage of timesteps where discretized count matches ground truth headcount exactly.
   $$A_{\text{exact}} = \frac{1}{N} \sum_{k=1}^{N} \mathbb{I}\left(N_{\text{disc},k} == N_{\text{gt},k}\right) \times 100\%$$

2. **Within-1-Person Tolerant Accuracy ($A_{\pm 1}$):**
   Percentage of timesteps within a $\pm 1$ person tolerance band.
   $$A_{\pm 1} = \frac{1}{N} \sum_{k=1}^{N} \mathbb{I}\left(\left|N_{\text{disc},k} - N_{\text{gt},k}\right| \le 1\right) \times 100\%$$

3. **Binary Presence Classification (F1-Score):**
   Evaluates binary Occupied vs Unoccupied detection ($N \ge 1$ vs $N = 0$).
   $$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}, \quad \text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$$
   $$\text{F1-Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

---

## 2. 🎯 Automated Threshold Optimization Method ($\tau^*$)

### The Problem with Arbitrary Thresholds
Fixed thresholds (e.g. $0.5$ or $0.35$) are arbitrary and fail when sensor responsiveness varies across small vs large rooms.

### Solution: Grid Search Optimization
We formulate an automated, parameter-free optimization algorithm to extract the optimal decision threshold $\tau^*$ for any dataset.

$$\tau^* = \arg\min_{\tau \in [0.10, 0.90]} \text{MAE}\left( N_{\text{disc}}(\tau), N_{\text{gt}} \right)$$

where:
$$N_{\text{disc},k}(\tau) = \begin{cases} 
0, & \text{if } \hat{N}_{\text{cont},k} < \tau \\
\lfloor \hat{N}_{\text{cont},k} + (1 - \tau) \rfloor, & \text{if } \hat{N}_{\text{cont},k} \ge \tau 
\end{cases}$$

### Implementation Strategy:
1. Sweep $\tau$ from $0.10$ to $0.90$ in steps of $0.02$.
2. Compute $\text{MAE}(\tau)$ and Exact Count Accuracy $A_{\text{exact}}(\tau)$ at each point.
3. Select $\tau^*$ that minimizes MAE while maximizing $A_{\text{exact}}$.

---

## 3. 📊 Continuous vs Discretized Comparison Strategy

| Feature / Metric | Continuous Estimate ($\hat{N}_{\text{cont}}$) | Discretized Estimate ($N_{\text{disc}}(\tau^*)$) |
| :--- | :--- | :--- |
| **Primary Purpose** | Evaluates raw sensor filter dynamics, convergence speed, and decay rates. | Evaluates HVAC decision engine readiness (integer occupant headcount). |
| **Compared Against** | Ground Truth $N_{\text{gt}}$ (Continuous) | Ground Truth $N_{\text{gt}}$ (Integer) |
| **Primary Metric** | Continuous RMSE & MAE | Exact Count Accuracy (%) & F1-Score |
| **Key Advantage** | Unbiased by rounding artifacts; smooth parameter tracking. | Direct input for demand-controlled ventilation (DCV). |

---

## 4. ⚔️ Multi-Tier Comparative Benchmark Framework

To prove that **Dual EKF is strictly superior to Single EKF**, we execute a 4-comparison benchmark matrix:

```
                  ┌─────────────────────────────────────────┐
                  │          SINGLE EKF vs DUAL EKF         │
                  └────────────────────┬────────────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌───────────────────────┐                             ┌───────────────────────┐
│ 1. EXPERIMENTAL TEST  │                             │  2. ENERGYPLUS BEM    │
│    RIG DATASETS       │                             │     BENCHMARK         │
│ (Day 3 & Day 4 Real)  │                             │  (1-Min Synthetic)    │
└───────────┬───────────┘                             └───────────┬───────────┘
            │                                                     │
            └──────────────────────────┬──────────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │ 3 & 4. CROSS-ENVIRONMENTAL    │
                       │    PHYSICS CONSISTENCY        │
                       │ (Real Rig vs BEM Simulation)  │
                       └───────────────────────────────┘
```

---

### Comparison Matrix Breakdown

#### 1. Single EKF vs Dual EKF (Test Rig Datasets)
* **Objective:** Demonstrate that Dual EKF's decoupled state/parameter architecture overcomes Single EKF state-coupling lag on physical experimental data.
* **Key Metric:** MAE reduction & F1-score improvement in Day 3 and Day 4 runs.

#### 2. Single EKF vs Dual EKF (EnergyPlus Datasets)
* **Objective:** Confirm that Dual EKF maintains superior performance when tested against calibrated EnergyPlus thermal and airflow simulation physics.
* **Key Metric:** Continuous RMSE and peak occupancy recovery $\Delta N_{\text{peak}}$.

#### 3. Test Rig Single EKF vs EnergyPlus Single EKF
* **Objective:** Validate that the Single 10-State EKF behaves consistently between real chamber sensors and BEM simulated telemetry.

#### 4. Test Rig Dual EKF vs EnergyPlus Dual EKF (Final Demo Proof)
* **Objective:** Provide the final proof that **Dual EKF achieves robust, accurate occupancy tracking** across both physical hardware and digital twin BEM environments.

---

## 📋 Recommended Summary Table Structure for Demo Presentation

| Dataset | Model | Continuous RMSE | Continuous MAE | Optimal $\tau^*$ | Discretized Accuracy (%) | Binary F1-Score |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Test Rig Day 3** | Single EKF | -- | -- | -- | -- | -- |
| **Test Rig Day 3** | **Dual EKF** | **--** | **--** | **--** | **--** | **--** |
| **Test Rig Day 4** | Single EKF | -- | -- | -- | -- | -- |
| **Test Rig Day 4** | **Dual EKF** | **--** | **--** | **--** | **--** | **--** |
| **EnergyPlus Day 3**| Single EKF | -- | -- | -- | -- | -- |
| **EnergyPlus Day 3**| **Dual EKF** | **--** | **--** | **--** | **--** | **--** |
| **EnergyPlus Day 4**| Single EKF | -- | -- | -- | -- | -- |
| **EnergyPlus Day 4**| **Dual EKF** | **--** | **--** | **--** | **--** | **--** |
