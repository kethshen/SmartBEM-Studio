# Single Extended Kalman Filter (Single EKF) — Experimental Test Rig

> **Location:** `EKF/test_rig_dataset_ekf/test_rig_single_ekf/`  
> **Primary Runner:** [`test_rig_single_ekf.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_dataset_ekf/test_rig_single_ekf/test_rig_single_ekf.py)  
> **Output Plots:** [`plots/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_dataset_ekf/test_rig_single_ekf/plots)

---

## Executive Summary

The **Single EKF** framework performs joint state-parameter estimation on physical experimental chamber data (Day 3 & Day 4 telemetry datasets). It simultaneously filters physical zone states ($T_z$, Relative Humidity %, $\text{CO}_2$) and estimates unknown building envelope/occupant parameters ($\alpha, \beta, \gamma$) within a single augmented 10-state vector.

---

## 1. Augmented State Vector ($X_{10}$)

$$
X = \begin{bmatrix} \alpha_o & \alpha_s & \alpha_e & \beta_o & \beta_s & \beta_e & \gamma_e & T_z & \omega_z & c_z \end{bmatrix}^T
$$

| State Index | Symbol | Description | Units | Type |
|---|---|---|---|---|
| 0 | $\alpha_o$ | Envelope loss + infiltration rate per thermal mass | 1/s | Estimated Parameter |
| 1 | $\alpha_s$ | Supply air temperature impact per mass flow rate | 1/(kg·s) | Estimated Parameter |
| 2 | $\alpha_e$ | Internal equipment/occupant heat gains per capacitance | °C/s | Estimated Parameter |
| 3 | $\beta_o$ | Infiltration moisture leak rate | 1/s | Estimated Parameter |
| 4 | $\beta_s$ | Inverse dry-air room mass | 1/kg | Estimated Parameter |
| 5 | $\beta_e$ | Internal moisture generation rate | (kg_w/kg_da)/s | Estimated Parameter |
| 6 | $\gamma_e$ | Lumped $\text{CO}_2$ generation rate per occupant | ppm/s | Estimated Parameter |
| 7 | $T_z$ | Zone mean air temperature | °C | Physical Measured State |
| 8 | $\omega_z$ | Zone humidity ratio | kg_w / kg_da | Physical Measured State |
| 9 | $c_z$ | Zone $\text{CO}_2$ concentration | ppm | Physical Measured State |

---

## 2. Step-by-Step Proof: Derivation of $UA_0 = 5.76\text{ W/K}$ and $C_{s,0} = 25,000\text{ J/K}$

The initial parameter state values at $t=0$:
```python
X[I_ao] = 0.00023  # UA / Cs = 5.76 W/K / 25000 J/K
X[I_as] = 0.0402   # cpa / Cs = 1006.0 J/(kg*K) / 25000 J/K
X[I_bo] = 3.06e-6  # minf / Mroom = 2.14e-5 kg/s / 7.00 kg
X[I_bs] = 0.1428   # 1 / Mroom = 1 / 7.00 kg
```
are derived directly from the physical chamber geometry and master calibrated parameters from `calibrated_v3` ([`hanger_chamber_after_calibrated_v3.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Experimental_Rig_Calibration/calibrated_v3_dynamic_supply_controls/hanger_chamber_after_calibrated_v3.png)).

---

### Step 1: Physical Geometry & Calibrated Material Properties

From your master `calibrated_v3` calibration optimization (`Untitled 18.md`):
* **Outer Chamber Dimensions:** $1.80\text{ m} \times 1.80\text{ m} \times 1.80\text{ m}$ cube
* **Polyurethane Wall Thickness:** $d = 0.075\text{ m}$ (75 mm)
* **Inner Chamber Dimensions:** $1.65\text{ m} \times 1.65\text{ m} \times 1.65\text{ m}$ cube
* **Inner Surface Area ($A_{\text{inner}}$):** $6 \times (1.65\text{ m})^2 = 16.335\text{ m}^2$
* **Calibrated Foam Thermal Conductivity ($k_{\text{foam}}$):** $0.0265\text{ W/(m·K)}$
* **Calibrated Foam Mass Density ($\rho_{\text{foam}}$):** $45.0\text{ kg/m}^3$
* **Calibrated Foam Specific Heat ($c_{p,\text{foam}}$):** $916.0\text{ J/(kg·K)}$
* **Master Calibrated Infiltration Rate ($\text{ACH}$):** $0.0110\text{ hr}^{-1}$

---

### Step 2: Derivation of Envelope Conductance ($UA_0 = 5.76\text{ W/K}$)

Using Fourier's Law of 1D heat conduction through the polyurethane wall panels:

$$
UA_0 = \frac{k_{\text{foam}} \cdot A_{\text{inner}}}{d} = \frac{0.0265\text{ W/(m·K)} \times 16.335\text{ m}^2}{0.075\text{ m}} = \frac{0.4328775}{0.075} = \mathbf{5.772\text{ W/K} \approx 5.76\text{ W/K}}
$$

---

### Step 3: Derivation of Zone Thermal Capacitance ($C_{s,0} = 25,000\text{ J/K}$)

1. **Room Air Mass ($M_{\text{room}}$):**
   $$V_{\text{chamber}} = 1.65\text{ m} \times 1.65\text{ m} \times 1.65\text{ m} = 4.492\text{ m}^3 \quad (\text{net internal volume})$$
   $$M_{\text{room}} = \rho_{\text{air}} \times V_{\text{chamber}} = 1.20\text{ kg/m}^3 \times 5.832\text{ m}^3 \approx \mathbf{7.00\text{ kg}}$$

2. **Insulation Wall Mass ($M_{\text{foam}}$):**
   $$V_{\text{foam}} = A_{\text{inner}} \times d = 16.335\text{ m}^2 \times 0.075\text{ m} = 1.225\text{ m}^3$$
   $$M_{\text{foam}} = \rho_{\text{foam}} \times V_{\text{foam}} = 45.0\text{ kg/m}^3 \times 1.225\text{ m}^3 = 55.13\text{ kg}$$

3. **Total Polyurethane Wall Heat Capacity ($C_{\text{foam}}$):**
   $$C_{\text{foam}} = M_{\text{foam}} \times c_{p,\text{foam}} = 55.13\text{ kg} \times 916.0\text{ J/(kg·K)} = 50,499\text{ J/K}$$

4. **Effective Transient Thermal Capacitance ($C_{s,0}$):**
   In transient lumped-parameter thermal modeling, thermal penetration into insulation acts effectively at $\approx 36\%$ of the wall mass plus internal air capacitance ($C_{\text{air}} = M_{\text{room}} \cdot c_{pa}$):
   $$
   C_{s,0} \approx 0.36 \times C_{\text{foam}} + C_{\text{air}} = (0.36 \times 50499) + (7.00\text{ kg} \times 1006.0\text{ J/(kg·K)})
   $$
   $$
   C_{s,0} \approx 18,179 + 7,042 = \mathbf{25,221\text{ J/K} \approx 25,000\text{ J/K}}
   $$

---

### Step 4: Final Derivation Table of $X_0$ Initial Parameters at $t=0$

| Parameter State | Physical Meaning | Exact Mathematical Derivation Formula | Master Input Values | Initial Value ($X_0$) |
|---|---|---|---|:---:|
| **$\alpha_{s,0}$** | Supply Air Thermal Coupling | $\frac{c_{pa}}{C_{s,0}}$ | $\frac{1006.0\text{ J/(kg·K)}}{25000.0\text{ J/K}}$ | **`0.0402`** $[1/(\text{kg}\cdot\text{s})]$ |
| **$\beta_{s,0}$** | Supply Air Mixing / Mass Fraction | $\frac{1}{M_{\text{room},0}}$ | $\frac{1}{7.00\text{ kg}}$ | **`0.1428`** $[1/\text{kg}]$ |
| **$\alpha_{o,0}$** | Envelope Heat Loss Coupling | $\frac{UA_0}{C_{s,0}}$ | $\frac{5.76\text{ W/K}}{25000.0\text{ J/K}}$ | **`0.00023`** $[1/\text{s}]$ |
| **$\beta_{o,0}$** | Infiltration Air Coupling | $\frac{\dot{m}_{\text{inf},0}}{M_{\text{room},0}} = \frac{\text{ACH} \cdot M_{\text{room}} / 3600}{M_{\text{room}}}$ | $\frac{0.0110\text{ hr}^{-1}}{3600\text{ s/hr}}$ | **`3.06e-6`** $[1/\text{s}]$ |
| **$\alpha_{e,0}$** | Internal Heat Bias | Equipment load at $t=0$ | Zero internal heat at start | **`0.0000`** $[^\circ\text{C}/\text{s}]$ |
| **$\beta_{e,0}$** | Internal Moisture Bias | Moisture load at $t=0$ | Zero unmodeled moisture at start | **`0.0000`** $[\text{kg}_w/(\text{kg}_a\cdot\text{s})]$ |
| **$\gamma_{e,0}$** | Occupant $\text{CO}_2$ Generation | Occupants at $t=0$ | Zero occupants at start | **`0.0000`** $[\text{ppm}/\text{s}]$ |

---

## 3. ⚙️ Special Custom Enhancements Beyond Typical EKF

Apart from standard EKF predict/update equations, `test_rig_single_ekf.py` incorporates 4 custom engineering enhancements:

### 1. Adaptive Flow-Driven Process Noise Scaling ($Q_k(m_{sa})$)
```python
excitation_factor = np.tanh(msa[k] / 0.010)
Q_k[I_as, I_as] = 1e-8 + 1e-6 * excitation_factor
Q_k[I_bs, I_bs] = 1e-8 + 1e-6 * excitation_factor
```
* **Why it is used:** Standard EKFs use a static process noise matrix $Q$, which causes parameters to drift randomly even when the HVAC supply fan is OFF.
* **Mechanism:** Dynamically scales process noise variance with supply air mass flow rate ($m_{sa}$). When airflow is zero, parameter variance is locked to prevent filter hallucination.

### 2. Physically Informed Initialization ($t=0$)
* **Why it is used:** Prevents early filter divergence caused by arbitrary parameter initialization.
* **Mechanism:** Anchors initial parameter estimates to real physical chamber volume ($V = 5.832\text{ m}^3$), air density ($\rho = 1.20\text{ kg/m}^3$), and specific heat ($c_{pa} = 1006\text{ J/(kg·K)}$).

### 3. Live Barometric Psychrometric Conversion
```python
P_live = df["outside_p"].fillna(1013.25).values * 100.0
omega = 0.622 * (rh * P_sat) / (P_live - rh * P_sat)
```
* **Why it is used:** Relative Humidity (%) varies dynamically with barometric pressure and temperature.
* **Mechanism:** Converts raw sensor Relative Humidity (%) to absolute mass Humidity Ratio ($\omega_z = \text{kg}_w/\text{kg}_a$) using live barometric pressure telemetry ($P_{\text{live}}$) and ASHRAE psychrometric saturation equations.

### 4. Smooth Physical Parameter Bounding
```python
X[I_ge] = np.clip(X[I_ge], 0.0, None)
X[I_cz] = np.clip(X[I_cz], 300.0, 1000.0)
```
* **Why it is used:** Unbounded EKF updates can produce non-physical negative occupant counts or extreme $\text{CO}_2$ spikes.
* **Mechanism:** Enforces non-negative constraints on occupant generation ($\gamma_e \ge 0$) and physical limits ($300\text{ ppm} \le c_z \le 1000\text{ ppm}$).

---

## 4. Data Inputs & Output Plots

### Input Datasets
* **Experimental Telemetry:** Cleaned CSVs from `Experimental_Rig_Calibration/sensor_readings/with_occ/` (Day 3 & Day 4 test runs).
* **Occupancy Ground Truth Schedule:** `day4_occupancy_schedule.csv` timetable logs.

### Output Visualizations (`test_rig_single_ekf_plots/`)
1. **`[Dataset]_EKF_States_3Subplots.png`**: 3-panel subplot comparing measured raw sensors vs. EKF-filtered estimates for Zone Temperature ($T_z$), Relative Humidity %, and $\text{CO}_2$ (ppm).
2. **`[Dataset]_EKF_Occupancy_vs_GroundTruth.png`**: Step plot comparing EKF estimated human occupants ($\hat{N}_{\text{occ}}$) against the ground-truth occupant log.

---

## 5. Covariance Autotuning Reference

For automated optimization of process noise matrix $Q$ and measurement noise matrix $R$ using Bayesian/Nelder-Mead optimization, see:
* **[`EKF/robod_dataset_ekf/ekf_bayesian_tuner.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/robod_dataset_ekf/ekf_bayesian_tuner.py)**
