# 10-State Extended Kalman Filter (`Real_EKF_TestRig.py`) — Code Breakdown & Advisor Formula Alignment Guide

This document provides a segment-by-segment walkthrough of [`Real_EKF_TestRig.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_ekf/Real_EKF_TestRig.py), updated with responses to user comments regarding elevation, live barometric sensor pressure, dynamic air density, and exact alignment with the advisor's `EMS_Cookbook from advisor.ipynb` formulas.

---

## Segment 1: Imports & Physical Constants

```python
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import sys

# ── Physical & Chamber Constants ───────────────────────────────────────────────
M_ROOM = 7.00             # Net air mass of test chamber [kg] (1.8m x 1.8m x 1.8m)
c_pa   = 1006.0           # Specific heat of dry air [J/(kg*K)]
g_CO2_occ = 7.00          # Chamber CO2 generation rate scaling factor
DT = 5.0                  # Sampling time step [seconds]
```

### Response to Comments & Parameter Analysis:

#### 1. Specific Heat of Air ($c_{pa} = 1006.0\text{ J/(kg}\cdot\text{K)}$)
* **User Comment:** *"Does this change with elevation and atmospheric pressure?"*
* **Physics & Engineering Explanation:**  
  For dry air, $c_{pa}$ is virtually independent of pressure and elevation (varies by less than $0.1\%$ across normal atmospheric ranges from 0 to 3000m altitude). However, **moist air specific heat** ($c_{p,\text{moist}}$) varies slightly with humidity ratio $\omega$:
  $$c_{p,\text{moist}} = c_{pa} + \omega \cdot c_{pv} = 1006.0 + \omega \cdot 1860.0 \quad [\text{J/(kg}\cdot\text{K)}]$$
  For standard HVAC modeling, holding $c_{pa} = 1006.0\text{ J/(kg}\cdot\text{K)}$ is standard practice.

#### 2. Air Density ($\rho_{\text{air}}$) & Elevation Adjustment
* **User Comment:** *"Do we have to adjust standard air density $\rho_{\text{air}} = 1.20\text{ kg/m}^3$ with elevation from sea level and atmospheric pressure?"*
* **Physics & Engineering Explanation:**  
  **YES!** Unlike $c_{pa}$, air density $\rho_{\text{air}}$ is sensitive to elevation and local barometric pressure. Using the ideal gas law:
  $$\rho_{\text{air}}(P, T) = \frac{P_{\text{baro}}}{R_{\text{specific}} \cdot (T + 273.15)}$$
  where $R_{\text{specific}} = 287.058\text{ J/(kg}\cdot\text{K)}$ for dry air, $P_{\text{baro}}$ is local pressure in $\text{Pa}$, and $T$ is temperature in $^\circ\text{C}$.  
  At higher elevations or under local weather fluctuations, $P_{\text{baro}}$ drops (e.g., at 500m elevation, $P \approx 95,400\text{ Pa} \Rightarrow \rho_{\text{air}} \approx 1.11\text{ kg/m}^3$).  
  **Action:** Rather than assuming static $\rho_{\text{air}} = 1.20$, we can dynamically compute $\rho_{\text{air}}$ from your sensor's live barometric pressure readings!

#### 3. Chamber Volume & Air Mass ($M_{\text{ROOM}} = 7.00\text{ kg}$)
* Internal dimensions: $1.8\text{m} \times 1.8\text{m} \times 1.8\text{m} = 5.832\text{ m}^3$.
* Net Air Mass: $M_{\text{ROOM}} = V_{\text{chamber}} \cdot \rho_{\text{air}} = 5.832\text{ m}^3 \times 1.20\text{ kg/m}^3 \approx 7.00\text{ kg}$.

---

## Segment 2: Live Sensor Barometric Pressure vs Hardcoded $P_{\text{atm}}$

```python
def rh_to_humidity_ratio(rh_pct, T_C, P_atm=101325.0):
    rh = np.clip(rh_pct / 100.0, 0.0, 1.0)
    P_sat = 610.78 * np.exp(17.269 * T_C / (T_C + 237.3))
    omega = 0.622 * (rh * P_sat) / (P_atm - rh * P_sat)
    return np.clip(omega, 0.0, 0.05)
```

### Response to Comment:
* **User Comment:** *"Is $P_{\text{atm}} = 101325.0$ correct? I think sensor data had something else."*
* **Physics & Engineering Explanation:**  
  **Spot on!** Hardcoding sea-level pressure ($101,325\text{ Pa}$) introduces systematic error if your laboratory test rig is at an elevation or experiencing weather pressure changes.
* **Sensor Telemetry Reality:** Your test rig CSV datasets contain live barometric pressure channels (`outside_p`, `room_1_p`, `room_2_p`, `room_3_p`, `supply_p`, `return_p`) recorded in hectopascals ($\text{hPa}$).
* **Action:** Convert live sensor barometric pressure to Pascals ($P_{\text{live}} = P_{\text{sensor\_hPa}} \times 100.0\text{ Pa}$) and pass $P_{\text{live}}$ into the psychrometric function `rh_to_humidity_ratio(rh, T, P_live)`!

---

## Segment 3: Alignment with Advisor's `EMS_Cookbook` $\text{CO}_2$ Formula

```python
# In Real_EKF_TestRig.py:
dcz = bo * (co - cz) + bs * msa * (csa - cz) + (ge / M_ROOM)
```

### Response to Comment & Mathematical Derivation:
* **User Comment:** *"Why divide $\gamma_e$ by $M_{\text{room}}$? That is not in the Zone $\text{CO}_2$ Concentration formula in `EMS_Cookbook from advisor.ipynb`."*

Let's examine the **exact ODE formula** from lines 106–115 of your advisor's `EMS_Cookbook from advisor.ipynb`:

### Advisor's Original Equations (`EMS_Cookbook`):

1. **Zone Thermal Dynamics:**
   $$\dot{T}_z = \frac{1}{C_{T,z}} \left( U_z (T_o - T_z) + \dot{m}_{sa,z} c_p (T_{sa} - T_z) + Q_{T,z}^{\text{int}} \right)$$

2. **Zone Moisture Dynamics:**
   $$\dot{\omega}_z = \frac{1}{C_{\omega,z}} \left( k_z (\omega_o - \omega_z) + \dot{m}_{sa,z} (\omega_{sa} - \omega_z) + G_{\omega,z}^{\text{int}} \right)$$

3. **Zone $\text{CO}_2$ Dynamics (Line 114):**
   $$\dot{c}_z = \frac{1}{V_z} \left( \dot{m}_{sa,z} (c_{sa} - c_z) + \dot{m}_z^{\text{inf}} (c_o - c_z) + q_z^{\text{occ}} \right)$$

Where:
* $V_z$: Net Zone Air Volume $[m^3]$ ($5.832\text{ m}^3$ for your chamber).
* $q_z^{\text{occ}}$: Total occupant $\text{CO}_2$ volumetric generation rate $[\text{m}^3/\text{s}]$ or $[\text{ppm} \cdot \text{m}^3 / \text{s}]$.
* $\dot{m}_{sa,z}, \dot{m}_z^{\text{inf}}$: Air mass flow rates $[\text{kg/s}]$.

### Why Dividing by $M_{\text{room}}$ in `Real_EKF_TestRig.py` was Wrong:
In `Real_EKF_TestRig.py`, the parameters $\beta_o, \beta_s$ were absorbed such that $\beta_s = \frac{1}{M_{\text{room}}}$ or $\frac{1}{V_z}$.  
When $\gamma_e$ was defined as a state and divided by $M_{\text{room}}$ again (`ge / M_ROOM`), it resulted in a **double division by volume/mass**, which artificially diluted the estimated $\text{CO}_2$ rate and caused the occupancy recovery signal to blow up to 8 people!

### Unified Advisor-Aligned $\text{CO}_2$ ODE:
By aligning directly with the advisor's `EMS_Cookbook` equation:
$$\dot{c}_z = \beta_{\text{inf}} (c_o - c_z) + \beta_{sa} \cdot m_{sa} (c_{sa} - c_z) + \frac{q^{\text{occ}}}{V_{\text{chamber}}}$$
Where:
* $q^{\text{occ}} = G_{\text{person}} \cdot N_{\text{occ}}$
* $G_{\text{person}} \approx 0.0045\text{ L/s} = 4.5 \times 10^{-6}\text{ m}^3/\text{s}$ (ASHRAE 62.1 standard $\text{CO}_2$ generation per person).
* $V_{\text{chamber}} = 5.832\text{ m}^3$.

Dividing $q^{\text{occ}}$ by $V_{\text{chamber}}$ yields the exact physical rate of rise in $[\text{ppm}/\text{s}]$ without requiring any arbitrary scaling constants!

---

## Segment 4: Summary Table of Clarifications & Proposed Updates

| Parameter / Code | User Query | Clarification & Proposed Fix |
| :--- | :--- | :--- |
| `c_pa = 1006.0` | Elevation/pressure effect? | Dry air $c_{pa}$ is constant ($1006\text{ J/kg}\cdot\text{K}$). Can add moisture correction $c_p = 1006 + 1860\omega$ if needed. |
| $\rho_{\text{air}} = 1.20$ | Elevation/pressure effect? | **Yes.** Calculate dynamically: $\rho_{\text{air}} = \frac{P_{\text{sensor\_hPa}} \times 100}{287.058 \cdot (T_z + 273.15)}$. |
| `P_atm = 101325.0` | Sensor data has live pressure? | **Correct.** Pass live measured pressure $P_{\text{sensor\_hPa}} \times 100$ into `rh_to_humidity_ratio()`. |
| `g_CO2_occ` | What is this? | Previous arbitrary scale factor. Replaced by physical ASHRAE occupant emission rate $G_{\text{person}} = 0.0045\text{ L/s}$. |
| `ge / M_ROOM` | Why divide by $M_{\text{room}}$? | **Correct catch.** Advisor's `EMS_Cookbook` ODE uses $\frac{q^{\text{occ}}}{V_z}$. Remove double division. |
