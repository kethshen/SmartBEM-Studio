Here are the **exact equations** used for the 7 estimated parameters ($\alpha_o$ through $\gamma_e$) in [`Real_EKF_TestRig.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_ekf/Real_EKF_TestRig.py), updated with notation $C_s$ and the exact 5-step derived parameter calculation sequence:

---

### 1. Parameter State-Transition Model (Random Walk)
In the EKF prediction step $f(X, U)$, all 7 parameters follow a continuous random-walk model ($\dot{\theta} = 0$), meaning their values are updated online via measurement innovation corrections:

$$\begin{aligned}
\dot{\alpha}_o &= 0 \quad \Rightarrow \quad \alpha_{o, k|k-1} = \alpha_{o, k-1} \\
\dot{\alpha}_s &= 0 \quad \Rightarrow \quad \alpha_{s, k|k-1} = \alpha_{s, k-1} \\
\dot{\alpha}_e &= 0 \quad \Rightarrow \quad \alpha_{e, k|k-1} = \alpha_{e, k-1} \\
\dot{\beta}_o &= 0 \quad \Rightarrow \quad \beta_{o, k|k-1} = \beta_{o, k-1} \\
\dot{\beta}_s &= 0 \quad \Rightarrow \quad \beta_{s, k|k-1} = \beta_{s, k-1} \\
\dot{\beta}_e &= 0 \quad \Rightarrow \quad \beta_{e, k|k-1} = \beta_{e, k-1} \\
\dot{\gamma}_e &= 0 \quad \Rightarrow \quad \gamma_{e, k|k-1} = \gamma_{e, k-1}
\end{aligned}$$

---

### 2. How the 7 Parameters Drive Zone Physics in EKF ($f(X, U)$)

The 7 parameters enter the continuous-time physical state ODEs as follows:

#### A. Thermal Parameters ($\alpha_o, \alpha_s, \alpha_e$)
$$\frac{dT_z}{dt} = \mathbf{\alpha_o} (T_o - T_z) + \mathbf{\alpha_s} \cdot \dot{m}_{sa} (T_{sa} - T_z) + \mathbf{\alpha_e}$$
* $\mathbf{\alpha_o}$ $[1/\text{s}]$: Outdoor envelope & infiltration heat exchange rate coefficient ($\alpha_o = \frac{UA + c_{pa} \cdot \dot{m}_{\text{inf}}}{C_s}$).
* $\mathbf{\alpha_s}$ $[1/(\text{kg}\cdot\text{s})]$: Supply air thermal coupling coefficient ($\alpha_s = \frac{c_{pa}}{C_s}$).
* $\mathbf{\alpha_e}$ $[^\circ\text{C}/\text{s}]$: Internal sensible thermal load / equipment bias ($\alpha_e = \frac{Q_{\text{int}}}{C_s}$).

#### B. Moisture & Ventilation Parameters ($\beta_o, \beta_s, \beta_e$)
$$\frac{d\omega_z}{dt} = \mathbf{\beta_o} (\omega_o - \omega_z) + \mathbf{\beta_s} \cdot \dot{m}_{sa} (\omega_{sa} - \omega_z) + \mathbf{\beta_e}$$
* $\mathbf{\beta_o}$ $[1/\text{s}]$: Outdoor air infiltration / envelope moisture exchange coefficient ($\beta_o = \frac{\dot{m}_{\text{inf}}}{M_{\text{room}}}$).
* $\mathbf{\beta_s}$ $[1/(\text{kg}\cdot\text{s})]$: Supply air mass flow mixing fraction ($\beta_s = \frac{1}{M_{\text{room}}}$).
* $\mathbf{\beta_e}$ $[\text{kg}_w/(\text{kg}_a\cdot\text{s})]$: Internal moisture generation bias ($\beta_e = \frac{G_{\text{int}}}{M_{\text{room}}}$).

#### C. Occupancy $\text{CO}_2$ Generation Parameter ($\gamma_e$)
$$\frac{dc_z}{dt} = \mathbf{\beta_o} (c_o - c_z) + \mathbf{\beta_s} \cdot \dot{m}_{sa} (c_{sa} - c_z) + \mathbf{\gamma_e}$$
* $\mathbf{\gamma_e}$ $[\text{ppm}/\text{s}]$: Total volumetric $\text{CO}_2$ concentration generation rate in the chamber.

---

### 3. Sequential 5-Step Order of Derived Physical Parameter Calculations

First, the EKF filter updates the 10 state variables $[\alpha_o, \alpha_s, \alpha_e, \beta_o, \beta_s, \beta_e, \gamma_e, T_z, \omega_z, c_z]^T$ at each step $k$.

Then, the hidden physical building parameters are extracted sequentially in the exact **5-step order** below:

```
[EKF State Estimates] ---> (1) C_s ---> (2) M_room ---> (3) m_inf ---> (4) UA ---> (5) Occupancy N
```

1. **Step 1: Sensible Thermal Capacitance ($C_s$)**  
   Extracted from supply thermal parameter $\alpha_s$ and specific heat of air $c_{pa}$:
   $$C_s = \frac{c_{pa}}{\alpha_s} \quad [\text{J}/^\circ\text{C}]$$

2. **Step 2: Zone Air Mass ($M_{\text{room}}$)**  
   Extracted from supply mixing fraction parameter $\beta_s$ (or known physical air mass):
   $$M_{\text{room}} = \frac{1}{\beta_s} \quad [\text{kg}]$$

3. **Step 3: Outdoor Air Infiltration Mass Flow Rate ($\dot{m}_{\text{inf}}$)**  
   Extracted from infiltration coefficient $\beta_o$ and zone air mass $M_{\text{room}}$:
   $$\dot{m}_{\text{inf}} = \beta_o \cdot M_{\text{room}} \quad [\text{kg/s}]$$

4. **Step 4: Envelope Overall Thermal Conductance ($UA$)**  
   Extracted from $\alpha_o$, thermal capacity $C_s$, $c_{pa}$, and infiltration rate $\dot{m}_{\text{inf}}$:
   $$UA = \alpha_o \cdot C_s - c_{pa} \cdot \dot{m}_{\text{inf}} \quad [\text{W}/^\circ\text{C}]$$

5. **Step 5: Occupant Count ($\hat{N}$)**  
   Extracted from $\text{CO}_2$ generation rate $\gamma_e$, air mass $M_{\text{room}}$, and per-person emission constant $g_{\text{CO2\_occ}}$:
   $$\hat{N} = \frac{\gamma_e \cdot M_{\text{room}}}{g_{\text{CO2\_occ}}} = \frac{\gamma_e}{g_{\text{CO2\_occ\_per\_person}}} \quad [\text{person}]$$

Viewed Summary.md:1-100
Viewed Summary.md:101-215

Based on your chamber geometry ($1.8\text{m} \times 1.8\text{m} \times 1.8\text{m}$ inside air volume) and the calibrated parameters from [`Summary.md`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/docs_and_reports/from%20obsidian%20notes/Summary.md) ($k_{\text{foam}} = 0.0265\text{ W/m}\cdot\text{K}$, $10\text{ cm}$ PU foam), here are the **expected physical benchmark values** for $M_{\text{room}}$, $C_s$, and $UA$:

---

### 1. Zone Air Mass ($M_{\text{room}}$)
* **Geometry:** Inside net air volume $V_{\text{inside}} = 1.8\text{m} \times 1.8\text{m} \times 1.8\text{m} = \mathbf{5.832\text{ m}^3}$.
* **Air Density:** $\rho_{\text{air}} \approx 1.15 \text{ to } 1.20\text{ kg/m}^3$ (depending on barometric pressure and temperature).
* **Expected Value:**
  $$M_{\text{room}} = 5.832\text{ m}^3 \times 1.20\text{ kg/m}^3 = \mathbf{7.00\text{ kg}} \quad (\text{Benchmark Range: } 6.7 \text{ to } 7.1\text{ kg})$$

---

### 2. Sensible Thermal Capacitance ($C_s$)
$C_s$ represents the combined heat capacity of the room air **plus** the active inner wall surface layer of PU foam and internal test equipment.

* **Pure Air Heat Capacity:**
  $$C_{\text{air}} = M_{\text{room}} \cdot c_{pa} = 7.00\text{ kg} \times 1006.0\text{ J/(kg}\cdot\text{K)} = \mathbf{7.04\text{ kJ/}^\circ\text{C}}$$
* **Active Inner Foam Wall Layer ($\sim 1.5\text{ cm}$ active penetration depth):**
  $$C_{\text{foam, active}} = (A_{\text{inner}} \cdot d_{\text{active}}) \cdot \rho_{\text{foam}} \cdot c_{p,\text{foam}} = (19.44\text{ m}^2 \times 0.015\text{ m}) \cdot 45.0 \cdot 916.0 \approx \mathbf{12.02\text{ kJ/}^\circ\text{C}}$$
* **Expected Total Value:**
  $$C_s = C_{\text{air}} + C_{\text{foam, active}} + C_{\text{equipment}} \approx \mathbf{20.0 \text{ to } 30.0\text{ kJ/}^\circ\text{C}} = \mathbf{20,000 \text{ to } 30,000\text{ J/}^\circ\text{C}}$$

---

### 3. Overall Envelope Thermal Conductance ($UA$)
$UA$ measures total heat loss rate per degree of temperature difference between the chamber interior and exterior.

* **Wall Conductive Transfer ($UA_{\text{cond}}$):**
  - Mean wall surface area $A_{\text{mean}} \approx 6 \times (1.9\text{ m} \times 1.9\text{ m}) = 21.66\text{ m}^2$.
  - Wall thickness $d = 0.10\text{ m}$ ($10\text{ cm}$).
  - Calibrated foam conductivity: $k_{\text{foam}} = 0.02650\text{ W/(m}\cdot\text{K)}$.
  $$UA_{\text{cond}} = \frac{k_{\text{foam}} \cdot A_{\text{mean}}}{d} = \frac{0.02650 \times 21.66}{0.10} = \mathbf{5.74\text{ W/}^\circ\text{C}}$$
* **Infiltration Heat Transfer ($UA_{\text{inf}}$):**
  - Calibrated infiltration: $\text{ACH} = 0.0110\text{ hr}^{-1} \Rightarrow UA_{\text{inf}} \approx \mathbf{0.02\text{ W/}^\circ\text{C}}$.
* **Expected Total Value:**
  $$UA = UA_{\text{cond}} + UA_{\text{inf}} \approx \mathbf{5.76\text{ W/}^\circ\text{C}} \quad (\text{Benchmark Range: } 5.5 \text{ to } 6.5\text{ W/}^\circ\text{C})$$

---

### Physical Benchmark Summary Table

| Property              | Physical Meaning                     |                            Expected Physical Benchmark Value                             |
| :-------------------- | :----------------------------------- | :--------------------------------------------------------------------------------------: |
| **$M_{\text{room}}$** | Net Air Mass in Chamber              |                    **$7.00\text{ kg}$** ($6.7\text{–}7.1\text{ kg}$)                     |
| **$C_s$**             | Sensible Thermal Capacitance         | **$20.0 \text{ to } 30.0\text{ kJ/}^\circ\text{C}$** ($20,000\text{–}30,000\text{ J/K}$) |
| **$UA$**              | Envelope Overall Thermal Conductance |             **$5.76\text{ W/}^\circ\text{C}$** ($5.5\text{–}6.5\text{ W/K}$)             |