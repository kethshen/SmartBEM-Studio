# Dual Extended Kalman Filter (Dual EKF) — ROBOD Dataset

> **Location:** `EKF/robod_dataset_ekf/robod_dual_ekf/`  
> **Primary Runner:** [`robod_dual_ekf.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/robod_dataset_ekf/robod_dual_ekf/robod_dual_ekf.py)  
> **Output Plots:** [`plots/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/robod_dataset_ekf/robod_dual_ekf/plots)

---

## Executive Summary

The **ROBOD Dual EKF** separates physical state estimation and parameter identification into **two decoupled filters running in tandem** across the 5 official NUS ROBOD building room datasets (`combined_Room1.csv` through `combined_Room5.csv`). It operates a **Fast 3-State Filter** at 300-second sampling ($\Delta t = 300\text{s}$) alongside a **Multi-Rate 5-Parameter Filter** updated every 2 sample steps ($\Delta t_p = 600\text{s}$).

---

## 1. Decoupled Architecture

```
                  ┌─────────────────────────────────────────┐
                  │          Fast 3-State Filter            │
  Inputs (U_k)───>│   x_k = [ Tz ,  w_z ,  c_z ]^T (RK4)    │───> State Estimates (x_k)
                  └────────────────────┬────────────────────┘
                                       │ State Residuals
                                       ▼ (Multi-Rate Window 10min)
                  ┌─────────────────────────────────────────┐
                  │        Multi-Rate Parameter Filter      │
  Sigmoid Bounds─>│  theta = [ ao, as, ae, bo, ge ]^T (xi)  │───> Physical Parameters (theta_k)
                  └────────────────────┴────────────────────┘
```

---

## 2. Filter Definitions

### A. State Vector ($\mathbf{x}_3$) — Fast 3-State Filter ($\Delta t = 300\text{s}$)

$$
\mathbf{x} = \begin{bmatrix} T_z & \omega_z & c_z \end{bmatrix}^T
$$

| Index | Symbol | Description | Units | Sensor Measurement |
|:---:|:---:|---|---|---|
| 0 | $T_z$ | Zone mean air temperature | °C | `air_temperature [Celsius]` |
| 1 | $\omega_z$ | Zone humidity ratio | kg_w / kg_da | Psychrometric conversion of `indoor_relative_humidity [%]` |
| 2 | $c_z$ | Zone $\text{CO}_2$ concentration | ppm | `indoor_co2 [ppm]` |

---

### B. Parameter Vector ($\mathbf{\theta}_5$) — Multi-Rate Parameter Filter ($\Delta t_p = 600\text{s}$)

$$
\mathbf{\theta} = \begin{bmatrix} \alpha_o & \alpha_s & \alpha_e & \beta_o & \gamma_e \end{bmatrix}^T
$$

| Index | Symbol | Physical Parameter | Description |
|:---:|:---:|---|---|
| 0 | $\alpha_o$ | Envelope loss coupling | $\alpha_o = \frac{UA + c_{pa} m_{\text{inf}}}{C_s}$ $[1/\text{s}]$ |
| 1 | $\alpha_s$ | Supply air thermal capacity coupling | $\alpha_s = \frac{c_{pa}}{C_s}$ $[1/(\text{kg}\cdot\text{s})]$ |
| 2 | $\alpha_e$ | Internal thermal heat bias | Equipment & occupant sensible heat gain rate $[^\circ\text{C}/\text{s}]$ |
| 3 | $\beta_o$ | Infiltration mass flow coupling | $\beta_o = \frac{m_{\text{inf}}}{M}$ $[1/\text{s}]$ |
| 4 | $\gamma_e$ | Lumped $\text{CO}_2$ occupant generation rate | Occupant emission rate $[\text{ppm}/\text{s}] \implies N_{\text{occ}} = \frac{\gamma_e}{g_{\text{CO}_2,\text{person}}}$ |

---

## 3. Output Structure (`plots/[room_name]/`)

Each dataset run creates a dedicated folder inside `plots/`:

```
plots/
├── combined_Room1/
│   ├── dual_ekf_states.png
│   ├── dual_ekf_occupancy_estimation.png
│   ├── dual_ekf_estimated_parameters.png
│   └── dual_ekf_derived_physical_properties.png
├── combined_Room2/
└── ...
```
