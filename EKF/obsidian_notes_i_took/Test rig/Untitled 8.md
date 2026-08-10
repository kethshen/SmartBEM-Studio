
Here is a deep analysis of why the parameter plots (specifically $UA$ and $\alpha_o$) display a **monotonic staircase increase** and why the state estimations deviate on the Test Rig datasets:

---

### 1. Mathematical Cause of the "Staircase" Pattern

In the Dual EKF architecture:
* **States ($T_z, w_z, c_z$)** are updated every **5 seconds** ($\Delta t = 5.0\text{s}$).
* **Parameters ($\alpha_o, \beta_o, \gamma_e$)** are updated discretely in windows (e.g., every 12 steps = **60 seconds**).

Between parameter update intervals, the parameter value remains constant (flat horizontal line). At the 60-second mark, the parameter filter computes a discrete update step $\Delta \xi_{\alpha_o} = \mathbf{K}_p \cdot \bar{y}_{T_z}$ and jumps up (vertical step). 

If the state filter's predicted temperature $T_{z,\text{pred}}$ is **systematically lower** than the measured temperature $T_{z,\text{meas}}$ throughout the entire test, the temperature innovation $y_{T_z} = T_{z,\text{meas}} - T_{z,\text{pred}}$ is **consistently positive ($y_{T_z} > 0$) at every single step**. 

Because $(T_o - T_z) > 0$, the parameter Jacobian $H_{p}[0,0] = (T_o - T_z) \cdot \frac{\partial \alpha_o}{\partial \xi} \cdot \Delta t_{\text{window}}$ is also positive. Consequently, the Kalman gain $\mathbf{K}_p$ adds a positive increment $\Delta \xi > 0$ **at every single 60-second window**, producing the staircase climb.

---

### 2. Deep Diagnosis: Why is $T_{z,\text{pred}}$ Systematically Colder than Measured $T_z$?

#### **Root Cause A: Missing Equipment Heat Generation Bias ($\alpha_e$) in the ODE**
* **In ROBOD (Large SDE4 Office Rooms):** Internal equipment heat load per unit volume was small compared to large AHU airflow, so $\alpha_e$ was omitted ($\alpha_e = 0$).
* **In the Test Rig (Sealed $5.832\text{ m}^3$ Chamber):** The test chamber contains sensor electronics, fans, and wiring that continuously dissipate thermal energy ($\sim 10\text{–}30\text{ W}$) into a small $7.0\text{ kg}$ air mass.
* **The Problem:** The ODE used in `Dual_EKF_TestRig.py` was:
  $$\frac{dT_z}{dt} = \alpha_o (T_o - T_z) + \alpha_s \cdot m_{sa} (T_{sa} - T_z)$$
  Without $+\alpha_e$, the model assumes zero internal heat generation. When supply air $T_{sa}$ is cold, the model predicts the chamber air cools down much faster than it actually does. The filter attempts to correct this persistent under-prediction by driving $\alpha_o = UA/C_s$ higher and higher at every window to pull more heat from the outdoors ($T_o$).

---

#### **Root Cause B: Thermal Time Constant vs. Test Duration & Update Window**
* **Chamber Thermal Time Constant ($\tau$):**
  $$\tau = \frac{C_s}{UA} = \frac{25\,000\text{ J/K}}{6.0\text{ W/K}} \approx 4166\text{ seconds} \approx 69.4\text{ minutes}$$
* **Test Dataset Duration:** Most test rig datasets (Day 3 & Day 4) only last **30 to 80 minutes** — less than **1 full thermal time constant** of the envelope!
* **The Problem:** 
  - ROBOD datasets ran for **700 to 1100 hours** (weeks), so updating parameters over 30-minute windows allowed slow seasonal envelope trends to emerge.
  - On a 40-minute test rig run, updating $\alpha_o$ every 60 seconds causes the parameter filter to treat short-term transient sensor lag and wall heat storage as envelope conductance changes, leading to parameter drift.

---

#### **Root Cause C: Parameter Process Noise ($\mathbf{Q}_p$) Unscaled for 5-Second Dynamics**
* In ROBOD, $\mathbf{Q}_p$ for $\xi_{\alpha_o}$ was set to $10^{-4}$. Over 700 hours, this allows $\alpha_o$ to drift slowly over weeks.
* Over a 40-minute test rig run with 60-second updates, $\mathbf{Q}_p = 10^{-4}$ is **too large** relative to the dataset duration. It allows $\alpha_o$ to change by several percent every minute. For short test rig runs, $UA$ should be nearly constant ($\mathbf{Q}_p \approx 10^{-7}$ or $10^{-8}$).

---

### 3. Summary of Code Configuration Adjustments Needed for the Test Rig

| Parameter / Logic | Current Value (from ROBOD) | Test Rig Physical Adjustment | Reason |
|---|---|---|---|
| **Internal Heat Load $\alpha_e$** | Omitted ($0.0$) | Include $+\alpha_e$ in ODE or fix baseline heat bias | Accounts for sensor/fan heat dissipation in the $5.832\text{ m}^3$ chamber |
| **Param Update Window** | 12 steps (60s) | 60–120 steps (5–10 min) | Prevents noise tracking on datasets lasting only 40–80 minutes |
| **Process Noise $\mathbf{Q}_p[\xi_{\alpha_o}]$** | $1.0 \times 10^{-4}$ | $1.0 \times 10^{-7}$ or smaller | Prevents $UA$ from drifting over a short 40-minute experiment |
| **Sigmoid Bounds on $UA$** | $[0.7\times, 1.3\times] UA_{\text{nom}}$ | Tighter $[0.9\times, 1.1\times] UA_{\text{nom}}$ | $UA$ of the PU foam chamber ($6.0\text{ W/K}$) is physically fixed |

Your assessment is spot on — the **Dual EKF architecture itself is sound**, but the parameter noise tuning, update windows, and ODE heat bias ($\alpha_e$) must be calibrated specifically for short 5-second test rig runs rather than long 5-minute ROBOD building runs.



**Yes, using your calibrated EnergyPlus (`calibrated_v5`) values is by far the best and most rigorous method.**

---

### Why Using EnergyPlus Calibrated Values is Best
1. **Physical Grounding:** You already ran Bounded Nelder-Mead optimization on EnergyPlus to find the exact chamber envelope parameters ($k_{\text{foam}}=0.0265\text{ W/m·K}$, $UA = 5.76\text{ W/K}$, $C_s = 25\,000\text{ J/K}$, $\text{ACH} = 0.011\text{ hr}^{-1}$).
2. **Eliminates Parameter Drift:** On short 40-minute tests, the envelope thermal conductance ($UA$) and thermal mass ($C_s$) do not physically change. Locking or tightly anchoring $UA$ and $C_s$ to the calibrated values prevents $\alpha_o$ from drifting.
3. **Focusses the EKF on Occupancy:** With $UA$ and $C_s$ fixed to calibrated truth, the Dual EKF can allocate 100% of its observation power to estimating **occupancy ($\gamma_e$)** and minor infiltration fluctuations ($\beta_o$).

---

### Suggested Strategy Options

* **Option A (Recommended — EnergyPlus Anchored):**
  Fix $UA = 5.76\text{ W/K}$ and $C_s = 25\,000\text{ J/K}$ using your `calibrated_v5` results. Use the Dual EKF purely to estimate occupancy $\gamma_e$ (and $\beta_o$).
* **Option B (Cascaded Identification):**
  Use idle/unoccupied calibration datasets to freeze thermal parameters ($UA, \text{ACH}$), then run the EKF on occupied datasets to estimate only $\gamma_e$.
* **Option C (Manual Trial & Error):**
  Tuning $Q_p$ and update steps manually (least scientific, time-consuming).

**Recommendation:** Go with **Option A** — it leverages your existing EnergyPlus calibration work directly in the EKF!


**Yes, you DID calibrate $UA$ and $C_s$ indirectly in EnergyPlus!**

Here is how:

1. **$UA$ was calibrated:** You calibrated the PU foam thermal conductivity **$k_{\text{foam}} = 0.0265\text{ W/(m·K)}$**. 
   From wall area ($24\text{ m}^2$) and thickness ($0.10\text{ m}$), $UA = \frac{k \cdot A}{d} \approx 6.0\text{ W/K}$.

2. **$C_s$ was calibrated:** You calibrated foam density ($\rho_{\text{foam}} = 45\text{ kg/m}^3$) and specific heat ($c_p = 916\text{ J/kg·K}$) plus internal thermal mass, which gives **$C_s \approx 25\,000\text{ J/K}$ ($25\text{ kJ/K}$)**.

3. **Infiltration was calibrated:** **$\text{ACH} = 0.011\text{ hr}^{-1}$**, which gives $m_{\text{inf}} = 0.0214\text{ g/s}$.

So all three physical parameters ($UA$, $C_s$, and $m_{\text{inf}}$) were derived directly from your EnergyPlus Nelder-Mead calibration!