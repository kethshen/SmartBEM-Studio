# EKF System Reference — SmartBEM FYP

> This document is the **single source of truth** for the Extended Kalman Filter (EKF) portion of the SmartBEM FYP.
> It follows the notation style used in the practice demos (`_prev`, `_est`, `_pred` suffixes on $X$, $P$, etc.).

---

## Notation Convention (from practice demos)

| Symbol | Meaning |
|---|---|
| $X_{\text{prev}}$ | State vector from previous timestep (after last update) |
| $X_{\text{pred}}$ | State vector after prediction step (before measurement correction) |
| $X_{\text{est}}$ | State vector after update step (corrected estimate) |
| $P_{\text{prev}}$ | Error covariance from previous timestep |
| $P_{\text{pred}}$ | Error covariance after prediction |
| $P_{\text{est}}$ | Error covariance after update |
| $K$ | Kalman Gain matrix |
| $F$ | State-transition Jacobian (10×10) |
| $H$ | Measurement matrix (3×10) |
| $Q$ | Process noise covariance (10×10) |
| $R$ | Measurement noise covariance (3×3) |
| $Z$ | Measurement vector [$T_{z,meas}$, $\omega_{z,meas}$, $c_{z,meas}$] |
| $y$ | Innovation (residual) = $Z − H @ X_{\text{pred}}$ |

---

## Augmented State Vector (10 states)

$$
X = \begin{bmatrix}
\alpha_o & \alpha_s & \alpha_e &
\beta_o & \beta_s & \beta_e &
\gamma_e &
T_z & \omega_z & c_z
\end{bmatrix}^T
$$

| Index | Symbol | What it is (practical meaning) | Units | Type |
|---|---|---|---|---|
| 0 | $\alpha_o$ | Heat-leak + infiltration rate | 1/s | Estimated parameter |
| 1 | $\alpha_s$ | Airflow effect on temperature | 1/(kg·s) effectively | Estimated parameter |
| 2 | $\alpha_e$ | Internal heat gains per capacitance | °C/s | Estimated parameter |
| 3 | $\beta_o$ | Infiltration moisture/CO₂ leak rate | 1/s | Estimated parameter |
| 4 | $\beta_s$ | Inverse of dry-air mass (moisture/CO₂ capacity) | 1/kg | Estimated parameter |
| 5 | $\beta_e$ | Internal moisture source per capacity | (kg_w/kg_da)/s | Estimated parameter |
| 6 | $\gamma_e$ | CO₂ generation rate per person per capacity | (kg_CO₂/kg_da)/(s·person) | Estimated parameter |
| 7 | $T_z$ | Zone temperature | °C | Measured state |
| 8 | $\omega_z$ | Zone humidity ratio | kg_w / kg_da | Measured state |
| 9 | $c_z$ | Zone CO₂ concentration | ppm (or kg_CO₂/kg_da) | Measured state |

> [!IMPORTANT]
> Indices 0–6 are **unknown parameters** the EKF learns over time.
> Indices 7–9 are **physical states** that we also measure with sensors.

---

## Section 1 — Zone Temperature (Sensible Energy)

### 1.1 Original Equation (from advisor)

$$
C_s \dot{T}_z =
- UA\,T_z - c_{pa}(m_{inf}+m_{sa})T_z
+ UA\,T_o + c_{pa}\,m_{inf}\,T_o + c_{pa}\,m_{sa}\,T_{sa}
+ Q_{bg} + f_c\,q^{occ}_{sens}\,N
$$

| Symbol | Meaning | Units |
|---|---|---|
| $C_s$ | Thermal capacitance of zone | J/K |
| $UA$ | Overall heat transfer coefficient × area | W/K |
| $c_{pa}$ | Specific heat of air (≈ 1006) | J/(kg·K) |
| $m_{inf}$ | Infiltration mass flow rate | kg/s |
| $m_{sa}$ | Supply air mass flow rate | kg/s |
| $T_z$ | Zone temperature | °C |
| $T_o$ | Outdoor temperature | °C |
| $T_{sa}$ | Supply air temperature | °C |
| $Q_{bg}$ | Background heat gain (equipment) | W |
| $f_c$ | Convective fraction of occupant heat | — |
| $q^{occ}_{sens}$ | Sensible heat per occupant | W/person |
| $N$ | Number of occupants | persons |

### 1.2 Compact Form ($\alpha$ parameters)

Define:

$$
\alpha_o = \frac{UA + c_{pa}\,m_{inf}}{C_s}, \quad
\alpha_s = \frac{c_{pa}}{C_s}, \quad
\alpha_e = \frac{Q_{bg} + f_c\,q^{occ}_{sens}\,N}{C_s}
$$

Then the ODE becomes:

$$
\dot{T}_z = -(\alpha_o + m_{sa}\,\alpha_s)\,T_z
+ \alpha_o\,T_o
+ m_{sa}\,\alpha_s\,T_{sa}
+ \alpha_e
$$

**Discrete-time (Forward Euler):**

$$
T_{z,k+1} = T_{z,k} + \Delta t \cdot \Big[
-(\alpha_o + m_{sa}\,\alpha_s)\,T_{z,k}
+ \alpha_o\,T_{o,k}
+ m_{sa,k}\,\alpha_s\,T_{sa,k}
+ \alpha_e
\Big]
$$

### 1.3 Temperature — What We Measure / Estimate / Input

| Category | Variables | Source |
|---|---|---|
| **Measured state** (sensor) | $T_z$ | Zone temperature sensor |
| **Estimated parameters** (EKF learns) | $\alpha_o, \alpha_s, \alpha_e$ | Hidden — recovered by EKF |
| **Known inputs** (measured separately) | $T_o, T_{sa}, m_{sa}$ | Weather sensor, AHU sensor, flow sensor |

### 1.4 Temperature — Jacobian Entries (row 7 of $F$)

$$
F[7,0] = \Delta t \cdot (-T_z + T_o) \quad \leftarrow \frac{\partial f_T}{\partial \alpha_o}
$$

$$
F[7,1] = \Delta t \cdot m_{sa}(-T_z + T_{sa}) \quad \leftarrow \frac{\partial f_T}{\partial \alpha_s}
$$

$$
F[7,2] = \Delta t \quad \leftarrow \frac{\partial f_T}{\partial \alpha_e}
$$

$$
F[7,7] = 1 + \Delta t \cdot (-\alpha_o - m_{sa}\,\alpha_s) \quad \leftarrow \frac{\partial f_T}{\partial T_z}
$$

All other entries in row 7 are **0**.

---

## Section 2 — Zone Humidity Ratio (Moisture)

### 2.1 Original Equation

$$
M\,\dot{\omega}_z =
-(m_{inf}+m_{sa})\,\omega_z
+ m_{inf}\,\omega_o + m_{sa}\,\omega_{sa}
+ G_{bg} + g^{occ}_\omega\,N
$$

| Symbol | Meaning | Units |
|---|---|---|
| $M$ | Dry air mass in zone | kg_da |
| $\omega_z$ | Zone humidity ratio | kg_w/kg_da |
| $\omega_o$ | Outdoor humidity ratio | kg_w/kg_da |
| $\omega_{sa}$ | Supply air humidity ratio | kg_w/kg_da |
| $G_{bg}$ | Background moisture source | kg_w/s |
| $g^{occ}_\omega$ | Moisture generation per occupant | (kg_w/s)/person |

### 2.2 Compact Form ($\beta$ parameters)

Define:

$$
\beta_o = \frac{m_{inf}}{M}, \quad
\beta_s = \frac{1}{M}, \quad
\beta_e = \frac{G_{bg} + g^{occ}_\omega\,N}{M}
$$

Then:

$$
\dot{\omega}_z = -(\beta_o + m_{sa}\,\beta_s)\,\omega_z
+ \beta_o\,\omega_o
+ m_{sa}\,\beta_s\,\omega_{sa}
+ \beta_e
$$

**Discrete-time:**

$$
\omega_{z,k+1} = \omega_{z,k} + \Delta t \cdot \Big[
-(\beta_o + m_{sa}\,\beta_s)\,\omega_{z,k}
+ \beta_o\,\omega_{o,k}
+ m_{sa,k}\,\beta_s\,\omega_{sa,k}
+ \beta_e
\Big]
$$

### 2.3 Humidity — What We Measure / Estimate / Input

| Category | Variables | Source |
|---|---|---|
| **Measured state** (sensor) | $\omega_z$ | Zone humidity sensor |
| **Estimated parameters** (EKF learns) | $\beta_o, \beta_s, \beta_e$ | Hidden — recovered by EKF |
| **Known inputs** (measured separately) | $\omega_o, \omega_{sa}, m_{sa}$ | Weather sensor, AHU sensor, flow sensor |

### 2.4 Humidity — Jacobian Entries (row 8 of $F$)

$$
F[8,3] = \Delta t \cdot (-\omega_z + \omega_o) \quad \leftarrow \frac{\partial f_\omega}{\partial \beta_o}
$$

$$
F[8,4] = \Delta t \cdot m_{sa}(-\omega_z + \omega_{sa}) \quad \leftarrow \frac{\partial f_\omega}{\partial \beta_s}
$$

$$
F[8,5] = \Delta t \quad \leftarrow \frac{\partial f_\omega}{\partial \beta_e}
$$

$$
F[8,8] = 1 + \Delta t \cdot (-\beta_o - m_{sa}\,\beta_s) \quad \leftarrow \frac{\partial f_\omega}{\partial \omega_z}
$$

All other entries in row 8 are **0**.

---

## Section 3 — Zone CO₂ Concentration

### 3.1 Original Equation

$$
M\,\dot{c}_z =
-(m_{inf}+m_{sa})\,c_z
+ m_{inf}\,c_o + m_{sa}\,c_{sa}
+ g^{occ}_{CO_2}\,N
$$

| Symbol | Meaning | Units |
|---|---|---|
| $c_z$ | Zone CO₂ concentration | ppm or kg_CO₂/kg_da |
| $c_o$ | Outdoor CO₂ concentration | ppm |
| $c_{sa}$ | Supply air CO₂ concentration | ppm |
| $g^{occ}_{CO_2}$ | CO₂ generation per occupant | (kg_CO₂/s)/person |

### 3.2 Compact Form ($\beta$ and $\gamma$ parameters)

Reuse $\beta_o, \beta_s$ from humidity. Define:

$$
\gamma_e = \frac{g^{occ}_{CO_2}\,N}{M}
$$

Then:

$$
\dot{c}_z = -(\beta_o + m_{sa}\,\beta_s)\,c_z
+ \beta_o\,c_o
+ m_{sa}\,\beta_s\,c_{sa}
+ \gamma_e
$$

> [!NOTE]
> CO₂ and humidity share $\beta_o$ and $\beta_s$ because both depend on the same air mass $M$ and infiltration $m_{inf}$. This is physically correct — air carries both moisture and CO₂.

**Discrete-time:**

$$
c_{z,k+1} = c_{z,k} + \Delta t \cdot \Big[
-(\beta_o + m_{sa}\,\beta_s)\,c_{z,k}
+ \beta_o\,c_{o,k}
+ m_{sa,k}\,\beta_s\,c_{sa,k}
+ \gamma_e
\Big]
$$

### 3.3 CO₂ — What We Measure / Estimate / Input

| Category | Variables | Source |
|---|---|---|
| **Measured state** (sensor) | $c_z$ | Zone CO₂ sensor |
| **Estimated parameters** (EKF learns) | $\beta_o, \beta_s$ (shared with humidity), $\gamma_e$ | Hidden — recovered by EKF |
| **Known inputs** (measured separately) | $c_o, c_{sa}, m_{sa}$ | Outdoor sensor, AHU sensor, flow sensor |

### 3.4 CO₂ — Jacobian Entries (row 9 of $F$)

$$
F[9,3] = \Delta t \cdot (-c_z + c_o) \quad \leftarrow \frac{\partial f_c}{\partial \beta_o}
$$

$$
F[9,4] = \Delta t \cdot m_{sa}(-c_z + c_{sa}) \quad \leftarrow \frac{\partial f_c}{\partial \beta_s}
$$

$$
F[9,6] = \Delta t \quad \leftarrow \frac{\partial f_c}{\partial \gamma_e}
$$

$$
F[9,9] = 1 + \Delta t \cdot (-\beta_o - m_{sa}\,\beta_s) \quad \leftarrow \frac{\partial f_c}{\partial c_z}
$$

All other entries in row 9 are **0**.

> [!WARNING]
> In your `Real_EKF.py`, row 9 currently uses `F[9,6] = dt*N`. However, $\gamma_e$ already absorbs $N$ ($\gamma_e = g^{occ}_{CO_2} \times N / M$). So the Jacobian entry should be `F[9,6] = dt` (i.e., $\partial f/\partial \gamma_e = 1$), not `dt*N`. Similarly, the prediction step should use `+ γe` not `+ γe*N`. Check Section 5 for details.

---

## Section 4 — Complete Jacobian $F$ (10×10 structure)

The full $F$ matrix has the form $F = I + \Delta t \times (\partial f/\partial X)$:

```
         α_o   α_s   α_e   β_o   β_s   β_e   γ_e   T_z   ω_z   c_z
       ┌─────────────────────────────────────────────────────────────────┐
α_o    │  1     0     0     0     0     0     0     0     0     0      │
α_s    │  0     1     0     0     0     0     0     0     0     0      │
α_e    │  0     0     1     0     0     0     0     0     0     0      │
β_o    │  0     0     0     1     0     0     0     0     0     0      │
β_s    │  0     0     0     0     1     0     0     0     0     0      │
β_e    │  0     0     0     0     0     1     0     0     0     0      │
γ_e    │  0     0     0     0     0     0     1     0     0     0      │
       │                                                               │
T_z    │ [a]   [b]   [c]    0     0     0     0    [d]    0     0      │
ω_z    │  0     0     0    [e]   [f]   [g]    0     0    [h]    0      │
c_z    │  0     0     0    [i]   [j]    0    [k]    0     0    [l]     │
       └─────────────────────────────────────────────────────────────────┘
```

Where:

| Label | Entry | Formula |
|---|---|---|
| [a] | F[7,0] | $\Delta t \cdot (−T_z + T_o)$ |
| [b] | F[7,1] | $\Delta t \cdot m_{sa} \cdot (−T_z + T_{sa})$ |
| [c] | F[7,2] | $\Delta t$ |
| [d] | F[7,7] | $1 + \Delta t \cdot (−\alpha_o − m_{sa} \cdot \alpha_s)$ |
| [e] | F[8,3] | $\Delta t \cdot (−\omega_z + \omega_o)$ |
| [f] | F[8,4] | $\Delta t \cdot m_{sa} \cdot (−\omega_z + \omega_{sa})$ |
| [g] | F[8,5] | $\Delta t$ |
| [h] | F[8,8] | $1 + \Delta t \cdot (−\beta_o − m_{sa} \cdot \beta_s)$ |
| [i] | F[9,3] | $\Delta t \cdot (−c_z + c_o)$ |
| [j] | F[9,4] | $\Delta t \cdot m_{sa} \cdot (−c_z + c_{sa})$ |
| [k] | F[9,6] | $\Delta t$ |
| [l] | F[9,9] | $1 + \Delta t \cdot (−\beta_o − m_{sa} \cdot \beta_s)$ |

> [!TIP]
> Top-left 7×7 block = Identity (parameters follow random walk).
> Bottom-right 3×3 diagonal entries encode how each state decays.
> Off-diagonal entries in bottom 3 rows encode how parameters affect states.

---

## Section 5 — EKF Process Flow (Step by Step)

This is exactly what happens **every timestep** inside your EKF loop.

### Step 0 — Read Inputs

At timestep $k$, read the following from sensors / known sources:

```
T_o_k, ω_o_k, c_o_k       ← outdoor conditions
T_sa_k, ω_sa_k, c_sa_k     ← supply air conditions
m_sa_k                      ← supply air mass flow
```

### Step 1 — Extract Current Estimates

```python
α_o, α_s, α_e = X_prev[0], X_prev[1], X_prev[2]
β_o, β_s, β_e = X_prev[3], X_prev[4], X_prev[5]
γ_e            = X_prev[6]
T_z, ω_z, c_z = X_prev[7], X_prev[8], X_prev[9]
```

### Step 2 — Predict States ($f$ function)

```python
T_pred = T_z + dt * (-(α_o + m_sa*α_s)*T_z + α_o*T_o + m_sa*α_s*T_sa + α_e)
w_pred = ω_z + dt * (-(β_o + m_sa*β_s)*ω_z + β_o*ω_o + m_sa*β_s*ω_sa + β_e)
c_pred = c_z + dt * (-(β_o + m_sa*β_s)*c_z + β_o*c_o + m_sa*β_s*c_sa + γ_e)

X_pred = X_prev.copy()
X_pred[7], X_pred[8], X_pred[9] = T_pred, w_pred, c_pred
# parameters X_pred[0:7] stay the same (random walk → no change in prediction)
```

### Step 3 — Compute Jacobian $F$

Build the 10×10 $F$ matrix as described in Section 4.

### Step 4 — Predict Covariance

```python
P_pred = F @ P_prev @ F.T + Q
```

### Step 5 — Read Measurements

```python
Z = np.array([T_z_measured, ω_z_measured, c_z_measured])
```

### Step 6 — Compute Innovation

```python
y = Z - H @ X_pred    # H picks out indices 7, 8, 9
```

### Step 7 — Compute Kalman Gain

```python
S = H @ P_pred @ H.T + R
K = P_pred @ H.T @ np.linalg.inv(S)
```

### Step 8 — Update State

```python
X_est = X_pred + K @ y
```

### Step 9 — Update Covariance

```python
P_est = (I - K @ H) @ P_pred
```

### Step 10 — Carry Forward

```python
X_prev = X_est
P_prev = P_est
```

> [!IMPORTANT]
> The measurement matrix $H$ is constant:
> ```
> H = | 0 0 0 0 0 0 0 1 0 0 |
>     | 0 0 0 0 0 0 0 0 1 0 |
>     | 0 0 0 0 0 0 0 0 0 1 |
> ```
> It selects $T_z, \omega_z, c_z$ from the 10-element state vector.

---

## Section 6 — Recovering Hidden Physical Parameters

After the EKF converges, the estimated compact parameters ($\alpha, \beta, \gamma$) can be **mapped back** to physical quantities:

| Hidden Parameter | How to Recover | Formula | Units |
|---|---|---|---|
| **Thermal capacitance** $C_s$ | From $\alpha_s$ | $C_s = c_{pa} / \alpha_s$ | J/K |
| **Dry air mass** $M$ | From $\beta_s$ | $M = 1 / \beta_s$ | kg |
| **Infiltration flow** $m_{inf}$ | From $\beta_o$ and $M$ | $m_{inf} = \beta_o \times M = \beta_o / \beta_s$ | kg/s |
| **Overall heat transfer** $UA$ | From $\alpha_o, C_s, m_{inf}$ | $UA = \alpha_o \times C_s − c_{pa} \times m_{inf}$ | W/K |
| **Occupancy** $N$ | From $\gamma_e$ and $M$ | $N = (\gamma_e \times M) / g^{occ}_{CO_2} = \gamma_e / (\beta_s \times g^{occ}_{CO_2})$ | persons |
| **Internal heat** $Q_{\text{internal}}$ | From $\alpha_e$ and $C_s$ | $Q_{\text{int}} = \alpha_e \times C_s$ | W |
| **Internal moisture** $G_{\text{internal}}$ | From $\beta_e$ and $M$ | $G_{\text{int}} = \beta_e \times M = \beta_e / \beta_s$ | kg_w/s |

Where:
- $c_{pa} \approx 1006$ J/(kg·K)
- $g^{occ}_{CO_2} \approx 0.004–0.006$ kg_CO₂/s per person (check your advisor's value; your code uses 0.17 — verify units!)

> [!CAUTION]
> The value `g_CO2_occ = 0.17` in your `Real_EKF.py` may be in different units (e.g., L/min or ppm-related). Confirm with your advisor what units your CO₂ concentration $c_z$ uses (ppm vs kg/kg) and match $g^{occ}_{CO_2}$ accordingly.

---

## Section 7 — Grand Summary Table

| # | Symbol | Role | Equation(s) Used In | Measured? | Source |
|---|---|---|---|---|---|
| 0 | $\alpha_o$ | Estimated param | Temperature | No | EKF learns |
| 1 | $\alpha_s$ | Estimated param | Temperature | No | EKF learns |
| 2 | $\alpha_e$ | Estimated param | Temperature | No | EKF learns |
| 3 | $\beta_o$ | Estimated param | Humidity + CO₂ | No | EKF learns |
| 4 | $\beta_s$ | Estimated param | Humidity + CO₂ | No | EKF learns |
| 5 | $\beta_e$ | Estimated param | Humidity | No | EKF learns |
| 6 | $\gamma_e$ | Estimated param | CO₂ | No | EKF learns |
| 7 | $T_z$ | State | Temperature | **Yes** | Zone temp sensor |
| 8 | $\omega_z$ | State | Humidity | **Yes** | Zone humidity sensor |
| 9 | $c_z$ | State | CO₂ | **Yes** | Zone CO₂ sensor |
| — | $T_o$ | Known input | Temperature | **Yes** | Weather / outdoor sensor |
| — | $T_{sa}$ | Known input | Temperature | **Yes** | AHU supply sensor |
| — | $\omega_o$ | Known input | Humidity | **Yes** | Weather / outdoor sensor |
| — | $\omega_{sa}$ | Known input | Humidity | **Yes** | AHU supply sensor |
| — | $c_o$ | Known input | CO₂ | **Yes** | Outdoor CO₂ sensor |
| — | $c_{sa}$ | Known input | CO₂ | **Yes** | AHU supply sensor |
| — | $m_{sa}$ | Known input | All three | **Yes** | Flow sensor / actuator |

---

## Section 8 — Required CSV Data Columns

To fully test the Real EKF, you need **one CSV file** with time-series data containing these columns:

### 8.1 Required Columns

| # | Column Name | Description | Units | Category |
|---|---|---|---|---|
| 1 | `timestamp` | Time of reading | datetime or seconds | Index |
| 2 | $T_z$ | Zone temperature (measured) | °C | **Zone sensor** |
| 3 | $\omega_z$ | Zone humidity ratio (measured) | kg_w/kg_da | **Zone sensor** |
| 4 | $c_z$ | Zone CO₂ concentration (measured) | ppm | **Zone sensor** |
| 5 | $T_o$ | Outdoor temperature | °C | **Outdoor sensor** |
| 6 | $\omega_o$ | Outdoor humidity ratio | kg_w/kg_da | **Outdoor sensor** |
| 7 | $c_o$ | Outdoor CO₂ concentration | ppm | **Outdoor sensor** |
| 8 | $T_{sa}$ | Supply air temperature | °C | **AHU sensor** |
| 9 | $\omega_{sa}$ | Supply air humidity ratio | kg_w/kg_da | **AHU sensor** |
| 10 | $c_{sa}$ | Supply air CO₂ concentration | ppm | **AHU sensor** |
| 11 | $m_{sa}$ | Supply air mass flow rate | kg/s | **Flow sensor** |

### 8.2 Optional (for validation only)

| # | Column Name | Description | Units | Notes |
|---|---|---|---|---|
| 12 | $N$ | True occupancy count | persons | Ground truth for validating $\gamma_e$ recovery |
| 13 | $Q_{\text{internal}}$ | True internal heat gain | W | Ground truth for validating $\alpha_e$ recovery |
| 14 | $m_{inf}$ | True infiltration rate | kg/s | Ground truth for validating $\beta_o$ recovery |

> [!TIP]
> If you are using **EnergyPlus simulation** to generate this data, all 11 required columns are available as EMS output variables. The optional columns can also be extracted for validation.

### 8.3 Example CSV Structure

```csv
timestamp,T_z,W_z,C_z,T_o,W_o,C_o,T_sa,W_sa,C_sa,m_sa,N_occ
0,25.0,0.010,600,30.0,0.012,420,18.0,0.009,420,0.5,5
60,25.1,0.010,605,30.1,0.012,420,18.0,0.009,420,0.5,5
120,25.2,0.010,610,30.2,0.012,420,18.0,0.009,420,0.52,5
...
```

- Rows are sampled at a fixed interval ($\Delta t = 60s$ recommended to match EnergyPlus timestep).
- Each row provides **one EKF iteration** worth of data.

---

## Section 9 — Issues Found in `Real_EKF.py`

> [!WARNING]
> **Issue 1: $\gamma_e \times N$ double-counting**
> In your simulation (line 63) you write `+ γe*N`, but $\gamma_e$ is already defined as $g^{occ}_{CO_2} \times N / M$. So you are effectively using $g^{occ}_{CO_2} \times N^2 / M$. The compact form should just be `+ \gamma_e` ($N$ is baked in).
> Similarly, `F[9,6] = dt*N` should be `F[9,6] = dt`.
>
> **Resolution:** Either (a) redefine $\gamma_e = g^{occ}_{CO_2} / M$ (per-person rate, then multiply by $N$ in equations), or (b) keep $\gamma_e = g^{occ}_{CO_2} \times N / M$ (total, no extra $N$). Your advisor's cookbook uses option (b).

> [!NOTE]
> **Issue 2: CO₂ shares $\beta_o, \beta_s$ with humidity**
> Rows 8 and 9 of $F$ both have entries at columns 3 and 4 ($\beta_o, \beta_s$). This means CO₂ and humidity observations jointly help estimate $\beta_o$ and $\beta_s$ — which is correct and actually **improves observability**.
> Your `Real_EKF.py` currently omits $F[9,3]$ and $F[9,4]$. These should be added for correct EKF behavior.
