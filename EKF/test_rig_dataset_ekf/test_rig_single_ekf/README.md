# Single Extended Kalman Filter (Single EKF) — Experimental Test Rig

> **Location:** `EKF/test_rig_dataset_ekf/test_rig_single_ekf/`  
> **Primary Runner:** [`test_rig_single_ekf.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_dataset_ekf/test_rig_single_ekf/test_rig_single_ekf.py)  
> **Output Plots:** [`test_rig_single_ekf_plots/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_dataset_ekf/test_rig_single_ekf/test_rig_single_ekf_plots)

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

## 2. ⚙️ Special Custom Enhancements Beyond Typical EKF

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
```python
X[I_ao] = 0.00023  # UA / Cs = 5.76 W/K / 25000 J/K
X[I_as] = 0.0402   # cpa / Cs = 1006.0 J/(kg*K) / 25000 J/K
X[I_bo] = 3.06e-6  # minf / Mroom = 2.14e-5 kg/s / 7.00 kg
X[I_bs] = 0.1428   # 1 / Mroom = 1 / 7.00 kg
```
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

## 3. Data Inputs & Output Plots

### Input Datasets
* **Experimental Telemetry:** Cleaned CSVs from `Experimental_Rig_Calibration/sensor_readings/with_occ/` (Day 3 & Day 4 test runs).
* **Occupancy Ground Truth Schedule:** `day4_occupancy_schedule.csv` timetable logs.

### Output Visualizations (`test_rig_single_ekf_plots/`)
1. **`[Dataset]_EKF_States_3Subplots.png`**: 3-panel subplot comparing measured raw sensors vs. EKF-filtered estimates for Zone Temperature ($T_z$), Relative Humidity %, and $\text{CO}_2$ (ppm).
2. **`[Dataset]_EKF_Occupancy_vs_GroundTruth.png`**: Step plot comparing EKF estimated human occupants ($\hat{N}_{\text{occ}}$) against the ground-truth occupant log.

---

## 4. Covariance Autotuning Reference

For automated optimization of process noise matrix $Q$ and measurement noise matrix $R$ using Bayesian/Nelder-Mead optimization, see:
* **[`EKF/robod_dataset_ekf/ekf_bayesian_tuner.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/robod_dataset_ekf/ekf_bayesian_tuner.py)**
