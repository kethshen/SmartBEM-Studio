# Autotuned Adaptive EKF via Nelder-Mead Optimization (`ekf_nelder_mead_optimization`)

This document explores the control-theoretic feasibility, mathematical formulation, and implementation architecture for running **Nelder-Mead Optimization to self-tune the Extended Kalman Filter (Autotuned A-EKF)**.

---

## 1. Executive Summary & Feasibility

**Question:** *Can we run Nelder-Mead optimization inside or around the EKF to optimize its internal parameters automatically?*

**Answer:** **YES!** In estimation theory and control engineering, this methodology is known as **Maximum Likelihood EKF Auto-Tuning** or **Bi-Level Optimization for State-Parameter Estimation** (Åström & Wittenmark 1995, Ljung 1999, Simon 2006).

While the inner EKF estimates continuous states ($\hat{T}_z, \hat{\omega}_z, \hat{c}_z$) and parameters ($\hat{\alpha}_o \dots \hat{\gamma}_e$) online at every timestep $k$, an **outer Nelder-Mead optimization loop** automatically tunes the EKF noise covariance matrices ($Q, R$) and initial state guess ($X_0$) to minimize measurement innovation errors and ensure convergence to physical reality.

---

## 2. Bi-Level Optimization Architecture

```
                      ┌────────────────────────────────────────────────────────┐
                      │    Outer Loop: Nelder-Mead Optimizer (SciPy)           │
                      │                                                        │
                      │    Optimizes Hyperparameters Θ = [Q, R, X_0]           │
                      └───────────────────────────┬────────────────────────────┘
                                                  │
                           Passes tuned Q, R, X_0 │ Evaluates Cost J(Θ)
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │    Inner Loop: 10-State EKF Engine                     │
                      │                                                        │
                      │    Runs forward filtering over dataset:                │
                      │    • X_{k|k} = X_{pred} + K_k * y_k                    │
                      │    • Calculates Innovations y_k & Covariance S_k       │
                      └────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical Formulation

### **A. Decision Variables (Optimization Parameters $\Theta$)**
Nelder-Mead optimizes the EKF diagonal process noise $Q$ and measurement noise $R$ in log-space (to guarantee positivity $Q_i > 0$):

$$\Theta = \left[ \log_{10}(Q_{\alpha_o}), \log_{10}(Q_{\alpha_s}), \log_{10}(Q_{\gamma_e}), \dots, \log_{10}(R_{T}), \log_{10}(R_{c}) \right]$$

### **B. Objective Function $J(\Theta)$ (Negative Log-Likelihood & Physical Penalty)**
The objective function measures how well the EKF tracks sensor telemetry while enforcing physical parameter bounds ($C_s, UA, M$):

$$J(\Theta) = J_{\text{tracking}}(\Theta) + J_{\text{innovation}}(\Theta) + J_{\text{physics}}(\Theta)$$

1. **State Tracking Performance:**
   $$J_{\text{tracking}} = \sqrt{\frac{1}{N} \sum_{k=1}^N (T_{z,k} - \hat{T}_{z,k})^2} + \lambda_c \sqrt{\frac{1}{N} \sum_{k=1}^N (c_{z,k} - \hat{c}_{z,k})^2}$$

2. **Innovation Whiteness (Maximum Likelihood Estimation):**
   $$J_{\text{innovation}} = \sum_{k=1}^N \left( y_k^T S_k^{-1} y_k + \ln |S_k| \right)$$
   *(When $Q$ and $R$ are optimal, the innovation residual $y_k = Z_k - H X_{\text{pred}}$ becomes zero-mean white noise).*

3. **Physical Expectation Penalty:**
   $$J_{\text{physics}} = \text{Penalty}\left(\hat{C}_s \notin [C_{s,\min}, C_{s,\max}]\right) + \text{Penalty}\left(\hat{UA} \notin [UA_{\min}, UA_{\max}]\right)$$

---

## 4. Why Nelder-Mead is Ideal for EKF Auto-Tuning

* **Derivative-Free (Simplex Method):** The EKF update loop involves matrix inversions $S_k^{-1}$ and non-linear thresholding, making analytic gradients $\nabla_\Theta J$ difficult to compute. Nelder-Mead uses geometric simplex reflections and expansions, requiring **no gradients**.
* **Global Parameters $Q$ and $R$:** Process noise $Q$ and measurement noise $R$ are constants across the run, making the search space compact ($5\text{--}10$ dimensions).
* **Guaranteed Physical Parameter Tuning:** Eliminates manual trial-and-error guessing of $Q$ and $R$.

---

## 5. Implementation Roadmap for SmartBEM Studio

1. **Create Optimizer Module (`ekf_nelder_mead_tuner.py`):**  
   Wraps `scipy.optimize.minimize(method='Nelder-Mead')` around our existing 10-State EKF function.
2. **Define Log-Scale Bounds:**  
   Search range: $Q_i \in [10^{-12}, 10^{-2}]$, $R_j \in [10^{-4}, 10^2]$.
3. **Execute Auto-Tuning on Calibration Data:**  
   Run Nelder-Mead over test rig / ROBOD datasets to find the global optimal $Q^*$ and $R^*$ vectors.
4. **Deploy Self-Tuned EKF:**  
   Run EKF with optimal $Q^*$ and $R^*$ for perfect parameter convergence and state estimation fit.

### Is Nelder-Mead the Best Choice?

**Short Answer:** **Nelder-Mead is good, but NOT the absolute best.**

---

### Why:

1. **Strength of Nelder-Mead:**  
   It is derivative-free and works well for small tuning problems ($D \le 10$ parameters).

2. **The Limitation:**  
   Because the EKF error surface can be highly non-convex, Nelder-Mead can get **trapped in local minima** if the initial guess is far off.

---

### Superior Alternatives:

* **Powell's Method or L-BFGS-B (Bounded Optimization):**  
  Faster and respects strict physical bounds ($\log_{10}(Q) \in [-12, -2]$).
* **Bayesian Optimization / CMA-ES (Recommended):**  
  The best global optimizer for EKF tuning—finds optimal $Q$ and $R$ in far fewer iterations without getting stuck.
* **Expectation-Maximization (EM Algorithm):**  
  The control-theory gold standard that auto-tunes $Q$ and $R$ directly inside the EKF loop without any outer optimizer.



# Autotuned Adaptive EKF via Bayesian Optimization (`ekf_bayesian_optimization`)

This document presents the theoretical control-theoretic framework, mathematical formulation, and implementation architecture for running **Bayesian Optimization to self-tune the Extended Kalman Filter (Autotuned A-EKF)**.

---

## 1. Executive Summary & Why Bayesian Optimization Superiority

**Question:** *Why is Bayesian Optimization superior to Nelder-Mead for tuning EKF process noise $Q$ and measurement noise $R$?*

**Answer:**  
Tuning EKF hyperparameters ($Q, R, X_0$) is a **non-convex black-box optimization problem** with expensive function evaluations.
* **Nelder-Mead Limitations:** Local simplex searches easily get trapped in local minima and require hundreds of trial runs.
* **Bayesian Optimization Superiority:**  
  1. **Global Exploration:** Uses a Gaussian Process (GP) probabilistic surrogate model to map the entire hyperparameter space, finding the **true global optimum $Q^*$ and $R^*$** without getting stuck.
  2. **High Sample Efficiency:** Reaches optimal convergence in **only 30–50 evaluations** (10x faster than Nelder-Mead or Random Search).
  3. **Strict Bounded Constraints:** Respects log-scale search bounds ($\log_{10}(Q) \in [-12, -2]$) natively.

---

## 2. Bi-Level Optimization Architecture

```
                 ┌────────────────────────────────────────────────────────┐
                 │  Outer Loop: Bayesian Optimizer (GP Surrogate + EI)    │
                 │                                                        │
                 │  Optimizes Hyperparameters Θ = [log10(Q), log10(R)]    │
                 └───────────────────────────┬────────────────────────────┘
                                             │
                      Passes candidate Q, R  │ Evaluates Cost J(Θ)
                                             ▼
                 ┌────────────────────────────────────────────────────────┐
                 │  Inner Loop: 10-State EKF Engine                       │
                 │                                                        │
                 │  Runs forward filtering over dataset:                  │
                 │  • X_{k|k} = X_{pred} + K_k * y_k                      │
                 │  • Calculates Innovations y_k & Covariance S_k         │
                 └────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical Formulation

### **A. Search Space & Hyperparameters $\Theta$**
Bayesian Optimization searches over process noise covariance $Q$ and measurement noise $R$ in log-10 scale:

$$\Theta = \left[ \log_{10}(Q_{\alpha_o}), \log_{10}(Q_{\alpha_s}), \log_{10}(Q_{\gamma_e}), \dots, \log_{10}(R_{T}), \log_{10}(R_{c}) \right]$$

Search bounds:
$$\log_{10}(Q_i) \in [-12, -2], \quad \log_{10}(R_j) \in [-4, 2]$$

### **B. Objective Function $J(\Theta)$ (Negative Log-Likelihood & Physical Penalty)**
The objective function balances state tracking fit, innovation whiteness, and physical parameter realistic bounds ($C_s, UA, M$):

$$J(\Theta) = J_{\text{tracking}}(\Theta) + J_{\text{innovation}}(\Theta) + J_{\text{physics}}(\Theta)$$

1. **State Tracking Fit:**
   $$J_{\text{tracking}} = \text{RMSE}(T_z) + \lambda_c \text{RMSE}(c_z)$$

2. **Innovation Whiteness (Maximum Likelihood Estimation):**
   $$J_{\text{innovation}} = \sum_{k=1}^N \left( y_k^T S_k^{-1} y_k + \ln |S_k| \right)$$

3. **Physical Parameter Bounds Penalty:**
   $$J_{\text{physics}} = \text{Penalty}\left(\hat{C}_s \notin [C_{s,\min}, C_{s,\max}]\right) + \text{Penalty}\left(\hat{UA} \notin [UA_{\min}, UA_{\max}]\right)$$

### **C. Acquisition Function (Expected Improvement - EI)**
The outer optimizer chooses the next candidate $\Theta_{\text{next}}$ by maximizing the Expected Improvement over the current best score $f(\Theta^+)$:

$$\alpha_{\text{EI}}(\Theta) = \mathbb{E} \left[ \max(0, f(\Theta^+) - f(\Theta)) \right]$$

---

## 4. Comparison of Optimization Approaches

| Feature | Manual Trial-and-Error | Nelder-Mead Simplex | **Bayesian Optimization (Recommended)** |
| :--- | :--- | :--- | :--- |
| **Search Strategy** | Heuristic Guessing | Local Simplex Reflection | **Probabilistic Gaussian Process Surrogate** |
| **Global Convergence** | Low | Low (Gets stuck in local traps) | **High (Guaranteed Global Exploration)** |
| **Sample Efficiency** | Very Low | Low (100–300 runs) | **Ultra High (30–50 runs)** |
| **Log-Bounded Search** | Difficult | Hard penalty required | **Native Bounded Box Constraints** |
| **Automation Level** | 100% Manual | Semi-Automated | **100% Fully Automated Self-Tuning** |

---

## 5. Implementation Roadmap for SmartBEM Studio

1. **Create Tuner Module (`ekf_bayesian_tuner.py`):**  
   Integrates `scikit-optimize` (`gp_minimize`) or `optuna` with our existing 10-State EKF engine.
2. **Define Log-Scale Search Space:**  
   Specify bounds for $Q$ ($10^{-12} \dots 10^{-2}$) and $R$ ($10^{-4} \dots 10^2$).
3. **Execute Auto-Tuning Run:**  
   Run Bayesian Optimization over test rig / ROBOD calibration datasets to extract global optimal $Q^*$ and $R^*$.
4. **Deploy Self-Tuned EKF:**  
   Execute EKF with optimal $Q^*$ and $R^*$ for perfect state fit and physical parameter convergence.
