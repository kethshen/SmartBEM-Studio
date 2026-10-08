Viewed Day%203%20test%201%20Take%201_2026-07-31_EKF_States_3Subplots.png

Here is the exact control-theoretic explanation for why these high-frequency oscillations and wild deviations (spiking to $10^9$) occurred after applying the changes:

---

### 1. The Discontinuity Defect of Hard Clipping (`np.clip`) on Covariance $P$

In Kalman filtering math, the state estimate $X_k$ and the error covariance matrix $P_k$ are **tightly coupled** through the update equations:

$$X_k = X_{\text{pred}} + K_k \cdot y_k$$
$$P_k = (I - K_k H) P_{\text{pred}}$$

* **What happened:**  
  When `np.clip()` abruptly forces a parameter state (e.g. $\alpha_s$ or $\beta_s$) back onto a hard threshold bound, the state vector $X_k$ is manually altered, but **the error covariance matrix $P_k$ is NOT aware of this truncation**.
* **The Resulting Limit Cycle (Chattering):**  
  At the next step $k+1$, the filter calculates a prediction based on the clipped $X_k$, but uses the unclipped, blown-up uncertainty $P_k$. This creates a massive mismatch between $X$ and $P$, resulting in an enormously large Kalman gain $K_{k+1}$. The filter over-corrects violently past the bound, gets clipped again, and enters a **numerical limit cycle / high-frequency chatter ($10^9$ oscillations)**.

---

### 2. Covariance Windup from Hard Kalman Gain Zeroing ($K_k = 0$)

In Step 3, we set $K_{k}[I_{as}, :] = 0.0$ whenever $\dot{m}_{sa} < 0.005\text{ kg/s}$.

* **What happened:**  
  Zeroing out rows of the Kalman gain $K_k$ freezes the state update for $\alpha_s$. However, during these frozen steps, the covariance propagation equation $P_{\text{pred}} = F_k P_{k-1} F_k^T + Q$ keeps adding process noise $Q$ at every single 5-second sample step.
* **The Resulting Covariance Explosion:**  
  Because $P$ keeps growing while updates are frozen, the parameter uncertainty $P[\alpha_s, \alpha_s]$ explodes (covariance windup). As soon as supply air flow exceeds $0.005\text{ kg/s}$ and gating turns off, the blown-up $P$ matrix produces a huge spike in Kalman gain, driving the filter into violent instability!

---

### Summary of Why This Occurred:

| Action Implemented | Intended Goal | Why It Failed (Control Theory Mechanism) |
| :--- | :--- | :--- |
| **`np.clip()` inside loop** | Keep parameters physical | State $X$ is truncated, but Covariance $P$ is not $\Rightarrow$ **Kalman Gain Explosion & Chattering** |
| **Hard $K_k = 0$ gating** | Stop parameter drift | Process noise $Q$ accumulates continuously $\Rightarrow$ **Covariance Windup & Massive Spikes** |

Here are the **3 control-theoretically sound solutions** to fix the oscillations and ensure smooth, accurate EKF convergence:

---

### Solution 1: Replace Hard Clipping with Smooth Sigmoid Parameter Mapping (Recommended)

* **How it works:**  
  Instead of estimating $\alpha_s$ directly and forcing it with `np.clip()`, the EKF estimates an unconstrained internal variable $\xi_{\alpha_s} \in (-\infty, +\infty)$.  
  The physical parameter $\alpha_s$ is then mapped smoothly using a logistic sigmoid function bounded strictly between physical limits $[\alpha_{s,\min}, \alpha_{s,\max}]$:
  $$\alpha_s(\xi) = \alpha_{s,\min} + \frac{\alpha_{s,\max} - \alpha_{s,\min}}{1 + e^{-\xi_{\alpha_s}}}$$
* **Why it eliminates oscillations:**  
  Because the sigmoid function is infinitely differentiable, the Jacobian derivative $\frac{\partial \alpha_s}{\partial \xi}$ remains smooth. The state space vector $\xi$ operates in unconstrained continuous space ($\mathbb{R}$), **preserving 100% covariance matrix $P$ consistency** and completely eliminating high-frequency chattering!

---

### Solution 2: Replace Hard Gating ($K_k = 0$) with Adaptive Process Noise Scaling $Q(\dot{m}_{sa})$

* **How it works:**  
  Instead of hard-zeroing rows of the Kalman gain $K_k$ (which caused covariance windup), we scale the process noise variance $Q_{\alpha_s}$ smoothly as a function of supply air mass flow $\dot{m}_{sa}$:
  $$Q_{\alpha_s}(\dot{m}_{sa}) = Q_{\text{base}} \cdot \tanh\left(\frac{\dot{m}_{sa}}{\dot{m}_{\text{threshold}}}\right)$$
* **Why it eliminates oscillations:**  
  When supply air flow is off ($\dot{m}_{sa} \to 0$), $Q_{\alpha_s} \to 0$. The filter naturally knows that no uncertainty is being added to $\alpha_s$, preventing covariance $P$ from growing during unexcited periods. When supply air turns back on, there is no covariance spike or sudden jump in Kalman gain.

---

### Solution 3: Keep Step 1 ($X_0$ Initialization) & Remove Discontinuous In-Loop Clips

* **How it works:**  
  Retain **Step 1** (initializing $X_0$ anchored at physical realities: $C_{s,0} = 25\text{ kJ/K}$, $M_0 = 7.00\text{ kg}$, $UA_0 = 5.76\text{ W/K}$), but **remove the abrupt in-loop hard clips and gain zeroing** that introduced numerical step discontinuities.
* **Why it eliminates oscillations:**  
  Starting the filter right inside the physical region at $t=0$ eliminates large initial transient errors. Without artificial step discontinuities, standard continuous EKF update equations operate smoothly without triggering numerical instability.


### Why 20–30 Minute Datasets Are Too Short for Parameter Convergence:

1. **Building Thermal Time Constant ($\tau$):**  
   The chamber's thermal time constant is:
   $$\tau = \frac{C_s}{UA} = \frac{25,000\text{ J/K}}{5.76\text{ W/K}} \approx 4,340\text{ seconds} \approx \mathbf{72\text{ minutes}}\text{ (1.2 hours)}$$
2. **Identification Limitation:**  
   In system identification theory, estimating long-term envelope parameters ($UA, C_s$) requires at least **$2\text{–}3$ time constants ($4\text{ to }24\text{ hours}$)** of data under varying outdoor temperature swings. A 20–30 minute test only captures $\sim 0.3 \tau$, which is too short for the EKF to decouple envelope heat loss ($UA$) from HVAC air flow ($\alpha_s$).

---

### Recommended Next Paths:

* **Path A: Run EKF on the ROBOD Dataset (29 Days of Data)**  
  ROBOD provides 8,352 samples over 29 days with full diurnal temperature swings and multi-person occupancy transitions, allowing the EKF ample time to fully converge.
* **Path B: Run EKF on EnergyPlus Calibrated Simulation (24-Hour Synthetic Rig Data)**  
  Generates a 24-hour noise-free simulation of your test rig chamber where $C_s = 25\text{ kJ/K}$ and $UA = 5.76\text{ W/K}$ are known ground-truth constants.

Which path would you like to take next?