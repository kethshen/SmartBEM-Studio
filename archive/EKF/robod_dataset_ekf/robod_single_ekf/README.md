# 10-State Single Extended Kalman Filter (Single EKF) — ROBOD Dataset

> **Location:** `EKF/robod_dataset_ekf/robod_single_ekf/`  
> **Primary Runner:** [`robod_single_ekf.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/robod_dataset_ekf/robod_single_ekf/robod_single_ekf.py)  
> **Output Plots:** [`plots/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/robod_dataset_ekf/robod_single_ekf/plots)

---

## Executive Summary

The **ROBOD 10-State Single EKF** estimates physical zone states ($T_z, \omega_z, c_z$) and structural parameters ($\alpha_o, \alpha_s, \alpha_e, \beta_o, \beta_s, \beta_e, \gamma_e$) simultaneously across the 5 official NUS ROBOD building room datasets (`combined_Room1.csv` through `combined_Room5.csv`).

---

## 1. 10-State Vector ($\mathbf{x}_{10}$) Formulation

$$
\mathbf{x} = \begin{bmatrix} 
\alpha_o & \alpha_s & \alpha_e & \beta_o & \beta_s & \beta_e & \gamma_e & T_z & \omega_z & c_z 
\end{bmatrix}^T
$$

| Index | Symbol | Physical Parameter | Description | Units |
|:---:|:---:|---|---|---|
| 0 | **$\alpha_o$** | Envelope Loss & Outdoor Heat Exchange | Lumped thermal conductance ($\frac{UA + c_{pa} m_{\text{inf}}}{C_s}$) | $1/\text{s}$ |
| 1 | **$\alpha_s$** | Supply Air Thermal Coupling | Thermal capacitance inverse ($\frac{c_{pa}}{C_s}$) | $1/(\text{kg}\cdot\text{s})$ |
| 2 | **$\alpha_e$** | Internal Thermal Heat Bias | Equipment & occupant sensible heat gain rate | $^\circ\text{C}/\text{s}$ |
| 3 | **$\beta_o$** | Outdoor Infiltration Mass Flow | Infiltration rate per dry-air mass ($\frac{m_{\text{inf}}}{M}$) | $1/\text{s}$ |
| 4 | **$\beta_s$** | Supply Air Mass Mixing Fraction | Dry-air room mass inverse ($\frac{1}{M}$) | $1/\text{kg}$ |
| 5 | **$\beta_e$** | Internal Moisture Generation | Moisture generation per dry-air mass | $(\text{kg}_w/\text{kg}_{da})/\text{s}$ |
| 6 | **$\gamma_e$** | Occupant $\text{CO}_2$ Generation | Lumped $\text{CO}_2$ emission rate | $\text{ppm}/\text{s}$ |
| 7 | **$T_z$** | Zone Air Temperature | Mean room temperature | $^\circ\text{C}$ |
| 8 | **$\omega_z$** | Zone Humidity Ratio | Absolute moisture content | $\text{kg}_w/\text{kg}_{da}$ |
| 9 | **$c_z$** | Zone $\text{CO}_2$ Concentration | Carbon dioxide concentration | $\text{ppm}$ |

---

## 2. Room Specifications & Initializations

| Room | Dataset File | Air Volume ($V$) | Air Mass ($M$) | Nominal $C_s$ | Nominal $UA$ | $\text{CO}_2$ Rate per Person ($\frac{4.5}{V}$) |
|---|---|---|---|---|---|---|
| **Room 1** | `combined_Room1.csv` | $120.0\text{ m}^3$ | $144.0\text{ kg}$ | $500.0\text{ kJ/K}$ | $80.0\text{ W/K}$ | $0.0375\text{ ppm/s}$ |
| **Room 2** | `combined_Room2.csv` | $150.0\text{ m}^3$ | $180.0\text{ kg}$ | $650.0\text{ kJ/K}$ | $100.0\text{ W/K}$ | $0.0300\text{ ppm/s}$ |
| **Room 3** | `combined_Room3.csv` | $413.2\text{ m}^3$ | $495.8\text{ kg}$ | $1500.0\text{ kJ/K}$ | $250.0\text{ W/K}$ | $0.0109\text{ ppm/s}$ |
| **Room 4** | `combined_Room4.csv` | $756.0\text{ m}^3$ | $907.2\text{ kg}$ | $2800.0\text{ kJ/K}$ | $450.0\text{ W/K}$ | $0.00595\text{ ppm/s}$ |
| **Room 5** | `combined_Room5.csv` | $760.0\text{ m}^3$ | $912.0\text{ kg}$ | $2850.0\text{ kJ/K}$ | $450.0\text{ W/K}$ | $0.00592\text{ ppm/s}$ |

---

## 3. Output Visualizations Structure (`plots/[room_name]/`)

Each dataset run creates a dedicated folder containing 4 plots:

1. **`single_ekf_states.png`**: Subplots of measured vs. EKF-filtered estimates for $T_z$, Relative Humidity %, and $\text{CO}_2$ (ppm).
2. **`single_ekf_occupancy_estimation.png`**: Step plot comparing EKF estimated occupants ($\hat{N}_{\text{occ}}$) against official ROBOD sensor ground truth (`occupant_count`).
3. **`single_ekf_estimated_parameters.png`**: Time series of estimated parameters ($\alpha_o, \alpha_s, \beta_o, \gamma_e$).
4. **`single_ekf_derived_physical_properties.png`**: Derived physical building properties ($C_s, M, m_{\text{inf}}, UA$).
