# Dual Extended Kalman Filter (Dual EKF) — Experimental Test Rig

> **Location:** `EKF/test_rig_dataset_ekf/test_rig_dual_ekf/`  
> **Primary Runner:** [`test_rig_dual_ekf.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_dataset_ekf/test_rig_dual_ekf/test_rig_dual_ekf.py)  
> **Output Plots:** [`plots/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_dataset_ekf/test_rig_dual_ekf/plots)

---

## Executive Summary

The **Dual EKF** framework separates state estimation and parameter identification into **two decoupled filters running in tandem**. Instead of augmenting states and parameters into a single large covariance matrix (as done in Single EKF), Dual EKF operates a **Fast 3-State Filter** at 5-second sampling ($\Delta t = 5\text{s}$) alongside a **Multi-Rate 5-Parameter Filter** updated every 60 seconds ($\Delta t_p = 60\text{s}$).

---

## 1. Decoupled Architecture

```
                  ┌─────────────────────────────────────────┐
                  │          Fast 3-State Filter            │
  Inputs (U_k)───>│   x_k = [ Tz ,  w_z ,  c_z ]^T (RK4)    │───> State Estimates (x_k)
                  └────────────────────┬────────────────────┘
                                       │ State Residuals
                                       ▼ (Multi-Rate Window 60s)
                  ┌─────────────────────────────────────────┐
                  │        Multi-Rate Parameter Filter      │
  Sigmoid Bounds─>│  theta = [ ao, as, ae, bo, ge ]^T (xi)  │───> Physical Parameters (theta_k)
                  └─────────────────────────────────────────┘
```

---

## 2. Filter Definitions

### A. State Vector ($\mathbf{x}_3$) — Fast 3-State Filter ($\Delta t = 5\text{s}$)

$$
\mathbf{x} = \begin{bmatrix} T_z & \omega_z & c_z \end{bmatrix}^T
$$

| Index | Symbol | Description | Units | Sensor Measurement |
|:---:|:---:|---|---|---|
| 0 | $T_z$ | Zone mean air temperature | °C | `Tz_weighted` |
| 1 | $\omega_z$ | Zone humidity ratio | kg_w / kg_da | Psychrometric conversion of `RHz_weighted` |
| 2 | $c_z$ | Zone $\text{CO}_2$ concentration | ppm | `CO2z_weighted` |

---

### B. Parameter Vector ($\mathbf{\theta}_5$) — Multi-Rate Parameter Filter ($\Delta t_p = 60\text{s}$)

$$
\mathbf{\theta} = \begin{bmatrix} \alpha_o & \alpha_s & \alpha_e & \beta_o & \gamma_e \end{bmatrix}^T
$$

| Index | Symbol | Physical Parameter | Physical Bounds ($\text{min}, \text{max}$) | Physical Derived Unit |
|:---:|:---:|---|:---:|:---:|
| 0 | $\alpha_o$ | Envelope loss coupling | $\left[\frac{5.0}{25000}, \frac{6.5}{25000}\right] = [0.00020, 0.00026]$ | $1/\text{s} \implies UA \in [5.0, 6.5]\text{ W/K}$ |
| 1 | $\alpha_s$ | Supply air thermal capacity coupling | $\left[\frac{1006}{30000}, \frac{1006}{20000}\right] = [0.0335, 0.0503]$ | $1/(\text{kg}\cdot\text{s}) \implies C_s \in [20.0, 30.0]\text{ kJ/K}$ |
| 2 | $\alpha_e$ | Internal thermal load bias | $[-0.002, 0.005]$ | $^\circ\text{C}/\text{s} \implies Q_e \in [-50, 125]\text{ W}$ |
| 3 | $\beta_o$ | Infiltration mass flow coupling | $[1.0 \times 10^{-7}, 5.0 \times 10^{-4}]$ | $1/\text{s} \implies \dot{m}_{\text{inf}} \in [0.0, 0.10]\text{ g/s}$ |
| 4 | $\gamma_e$ | Lumped $\text{CO}_2$ occupant generation rate | $[0.0, 5.0]$ | $\text{ppm}/\text{s} \implies N_{\text{occ}} = \frac{\gamma_e}{0.7716}$ |

---

## 3. Decoupling Rationale & Mathematical Advantages

1. **Elimination of Cross-Covariance Instabilities:**
   Single EKF estimates off-diagonal cross-covariances $P_{x\theta}$ between fast states ($T_z$) and slow parameters ($\alpha_o$). In noisy datasets, unmodeled sensor noise corrupts $P_{x\theta}$, causing parameter divergence. Decoupling forces $P_{x\theta} = 0$, guaranteeing filter stability.

2. **Multi-Rate Sampling (5s vs. 60s):**
   Physical building parameters ($UA, C_s$) change over hours, whereas zone air temperature changes in seconds. Running parameter updates every 60 seconds ($\Delta t_p = 12 \times \Delta t$) averages out high-frequency sensor noise.

3. **Sigmoid Reparameterization ($\xi \to \theta$):**
   Unconstrained Kalman updates can produce non-physical values (e.g. negative thermal capacitance $C_s < 0$). Dual EKF maps unconstrained filter states $\xi_i \in \mathbb{R}$ to physical parameters $\theta_i \in [\theta_{\text{min}}, \theta_{\text{max}}]$ via a smooth logistic sigmoid:
   $$
   \theta_i = \theta_{\text{min}} + (\theta_{\text{max}} - \theta_{\text{min}}) \cdot \frac{1}{1 + e^{-\xi_i}}
   $$

---

## 4. Step-by-Step Proof: Derivation of $UA_0 = 5.76\text{ W/K}$ and $C_{s,0} = 25,000\text{ J/K}$

Initial physical parameter anchors are derived directly from the master `calibrated_v3` chamber geometry ([`hanger_chamber_after_calibrated_v3.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Experimental_Rig_Calibration/calibrated_v3_dynamic_supply_controls/hanger_chamber_after_calibrated_v3.png)).

### Step 1: Chamber Geometry & Material Properties
* **Outer Cube Dimensions:** $1.80\text{ m} \times 1.80\text{ m} \times 1.80\text{ m}$
* **Polyurethane Wall Thickness:** $d = 0.075\text{ m}$ (75 mm)
* **Inner Cube Dimensions:** $1.65\text{ m} \times 1.65\text{ m} \times 1.65\text{ m}$
* **Inner Surface Area ($A_{\text{inner}}$):** $6 \times (1.65\text{ m})^2 = 16.335\text{ m}^2$
* **Foam Thermal Conductivity ($k_{\text{foam}}$):** $0.0265\text{ W/(m·K)}$
* **Foam Mass Density ($\rho_{\text{foam}}$):** $45.0\text{ kg/m}^3$
* **Foam Specific Heat ($c_{p,\text{foam}}$):** $916.0\text{ J/(kg·K)}$

### Step 2: Envelope Conductance ($UA_0 = 5.76\text{ W/K}$)
$$
UA_0 = \frac{k_{\text{foam}} \cdot A_{\text{inner}}}{d} = \frac{0.0265 \times 16.335}{0.075} = \mathbf{5.772\text{ W/K} \approx 5.76\text{ W/K}}
$$

### Step 3: Zone Thermal Capacitance ($C_{s,0} = 25,000\text{ J/K}$)
1. **Room Air Mass ($M_{\text{room}}$):** $M_{\text{room}} = 1.20\text{ kg/m}^3 \times (1.80\text{ m})^3 \approx 7.00\text{ kg}$
2. **Foam Wall Mass ($M_{\text{foam}}$):** $M_{\text{foam}} = 45.0\text{ kg/m}^3 \times (16.335 \times 0.075)\text{ m}^3 = 55.13\text{ kg}$
3. **Wall Heat Capacity ($C_{\text{foam}}$):** $C_{\text{foam}} = 55.13 \times 916.0 = 50,499\text{ J/K}$
4. **Effective Transient Capacitance ($C_{s,0}$):**
   $$
   C_{s,0} \approx 0.36 \times C_{\text{foam}} + M_{\text{room}} \cdot c_{pa} = 18,179 + 7,042 = \mathbf{25,221\text{ J/K} \approx 25,000\text{ J/K}}
   $$

---

## 5. ⚙️ Special Custom Enhancements in `test_rig_dual_ekf.py`

### 1. Analytical 5x5 Block-Diagonal Parameter Jacobian ($H_p$)
Instead of costly numerical finite differencing, Dual EKF computes exact analytical derivatives of the residual vector $\mathbf{y}_p$ w.r.t. internal sigmoid states $\xi$:
$$
H_p = \begin{bmatrix}
(T_o - T_z) \cdot \frac{\partial \alpha_o}{\partial \xi_0} \cdot \Delta t_p & 0 & 0 & 0 & 0 \\
0 & m_{sa}(T_{sa} - T_z) \cdot \frac{\partial \alpha_s}{\partial \xi_1} \cdot \Delta t_p & 0 & 0 & 0 \\
0 & 0 & \frac{\partial \alpha_e}{\partial \xi_2} \cdot \Delta t_p & 0 & 0 \\
0 & 0 & 0 & (\omega_o - \omega_z) \cdot \frac{\partial \beta_o}{\partial \xi_3} \cdot \Delta t_p & 0 \\
0 & 0 & 0 & 0 & \frac{\partial \gamma_e}{\partial \xi_4} \cdot \Delta t_p
\end{bmatrix}
$$

### 2. 4th-Order Runge-Kutta (RK4) State Integration
State predictions between 5-second sensor updates use RK4 integration (`state_rk4`) for continuous non-linear thermal dynamics.

### 3. Live Psychrometric Humidity Conversion
Converts Relative Humidity (%) to absolute mass Humidity Ratio ($\omega_z = \text{kg}_w/\text{kg}_a$) using live barometric telemetry ($P_{\text{live}}$).

---

## 6. Output Structure (`plots/[dataset_name]/`)

When `test_rig_dual_ekf.py` executes, it creates a dedicated folder for each dataset inside `plots/`:

```
plots/
├── day_3_p_1/
│   ├── dual_ekf_states.png
│   ├── dual_ekf_occupancy_estimation.png
│   ├── dual_ekf_estimated_parameters.png
│   └── dual_ekf_derived_physical_properties.png
├── day_3_p_2/
└── ...
```
