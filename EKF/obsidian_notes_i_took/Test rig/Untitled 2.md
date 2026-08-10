Here are the **exact equations** used for the 7 estimated parameters ($\alpha_o$ through $\gamma_e$) in [`Real_EKF_TestRig.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/test_rig_ekf/Real_EKF_TestRig.py):

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
* $\mathbf{\alpha_o}$ $[1/\text{s}]$: Outdoor wall/envelope heat exchange rate coefficient ($\alpha_o = \frac{UA}{C_{T}}$).
* $\mathbf{\alpha_s}$ $[1/(\text{kg}\cdot\text{s})]$: Supply air thermal coupling coefficient ($\alpha_s = \frac{c_{pa}}{C_{T}}$).
* $\mathbf{\alpha_e}$ $[^\circ\text{C}/\text{s}]$: Internal sensible thermal load / equipment bias ($\alpha_e = \frac{Q_{\text{int}}}{C_{T}}$).

#### B. Moisture & Ventilation Parameters ($\beta_o, \beta_s, \beta_e$)
$$\frac{d\omega_z}{dt} = \mathbf{\beta_o} (\omega_o - \omega_z) + \mathbf{\beta_s} \cdot \dot{m}_{sa} (\omega_{sa} - \omega_z) + \mathbf{\beta_e}$$
* $\mathbf{\beta_o}$ $[1/\text{s}]$: Outdoor air infiltration / envelope moisture exchange coefficient ($\beta_o = \frac{\dot{m}_{\text{inf}}}{M_{\text{room}}}$).
* $\mathbf{\beta_s}$ $[1/(\text{kg}\cdot\text{s})]$: Supply air mass flow mixing fraction ($\beta_s = \frac{1}{M_{\text{room}}}$).
* $\mathbf{\beta_e}$ $[\text{kg}_w/(\text{kg}_a\cdot\text{s})]$: Internal moisture generation bias ($\beta_e = \frac{G_{\text{int}}}{M_{\text{room}}}$).

#### C. Occupancy $\text{CO}_2$ Generation Parameter ($\gamma_e$)
$$\frac{dc_z}{dt} = \mathbf{\beta_o} (c_o - c_z) + \mathbf{\beta_s} \cdot \dot{m}_{sa} (c_{sa} - c_z) + \mathbf{\gamma_e}$$
* $\mathbf{\gamma_e}$ $[\text{ppm}/\text{s}]$: Total volumetric $\text{CO}_2$ concentration generation rate in the chamber.

---

### 3. Occupant Count Recovery Equation from $\gamma_e$

To convert the estimated state $\gamma_e$ $[\text{ppm}/\text{s}]$ into the estimated number of occupants $\hat{N}$:

$$\hat{N}_{\text{occupants}} = \frac{\gamma_e}{g_{\text{CO2\_occ\_per\_person}}}$$

Where:
$$g_{\text{CO2\_occ\_per\_person}} = \frac{G_{\text{person}}}{V_{\text{chamber}}} = \frac{4.5 \times 10^{-6} \text{ m}^3/\text{s} \times 10^6}{5.832 \text{ m}^3} = 0.7716 \text{ ppm/s per person}$$

*(Based on ASHRAE 62.1 standard emission $G_{\text{person}} = 0.0045 \text{ L/s} = 4.5 \text{ cm}^3/\text{s}$ per person).*


Here are the exact physical definitions:

### 1. In $\alpha_s = \frac{c_{pa}}{C_T}$, what is $C_T$?
* **$C_T$** is the **Effective Sensible Thermal Capacitance of the Zone** $[\text{J}/^\circ\text{C}]$ or $[\text{J/K}]$.
* It represents the total thermal mass (air + internal wall surface layers) inside the chamber that absorbs or releases thermal energy when temperature changes.
* **Derivation from Advisor's Thermal ODE (Line 106):**
  $$\frac{dT_z}{dt} = \frac{1}{\mathbf{C_T}} \left[ U (T_o - T_z) + \dot{m}_{sa} c_{pa} (T_{sa} - T_z) + Q_{\text{int}} \right]$$
  Expanding the supply air term gives:
  $$\alpha_s = \frac{c_{pa}}{\mathbf{C_T}}$$
  *(where $c_{pa} = 1006.0\text{ J/(kg}\cdot\text{K)}$ is the specific heat of air).*

---

### 2. In $\beta_s = \frac{1}{M_{\text{room}}}$, what is $M_{\text{room}}$?
* **$M_{\text{room}}$** is the **Total Net Air Mass inside the Zone/Chamber** $[\text{kg}]$.
* It represents the total mass of dry air enclosed within the $1.8\text{m} \times 1.8\text{m} \times 1.8\text{m}$ volume.
* **Derivation from Advisor's Mass Balance ODE (Lines 110 & 114):**
  $$\frac{d\omega_z}{dt} = \frac{1}{\mathbf{M_{\text{room}}}} \left[ \dot{m}_{\text{inf}} (\omega_o - \omega_z) + \dot{m}_{sa} (\omega_{sa} - \omega_z) + G_{\text{int}} \right]$$
  Expanding the supply air term gives:
  $$\beta_s = \frac{1}{\mathbf{M_{\text{room}}}}$$
  *(where $M_{\text{room}} = V_{\text{chamber}} \cdot \rho_{\text{air}} = 5.832\text{ m}^3 \times 1.20\text{ kg/m}^3 = \mathbf{7.00\text{ kg}}$).*

**Yes, absolutely!**

$1.20\text{ kg/m}^3$ is only the standard reference value at sea level ($101,325\text{ Pa}$, $20^\circ\text{C}$).

In our code, **$\rho_{\text{air}}$ is dynamically calculated in real time** per timestamp from your sensor's live barometric pressure and temperature:

$$\rho_{\text{air}}(t) = \frac{P_{\text{live}}(t)}{287.058 \cdot (T_z(t) + 273.15)} \quad [\text{kg/m}^3]$$

Where:
* $P_{\text{live}}(t)$: Live sensor barometric pressure in Pascals ($P_{\text{sensor\_hPa}} \times 100$).
* $T_z(t)$: Live zone temperature in $^\circ\text{C}$.

Therefore, the exact physical chamber air mass $M_{\text{room}}(t)$ dynamically adjusts as:

$$M_{\text{room}}(t) = V_{\text{chamber}} \cdot \rho_{\text{air}}(t) = 5.832\text{ m}^3 \cdot \left(\frac{P_{\text{live}}(t)}{287.058 \cdot (T_z(t) + 273.15)}\right) \quad [\text{kg}]$$

It is a **unit conversion** from hectopascals ($\text{hPa}$) to standard Pascals ($\text{Pa}$):

$$\mathbf{1\text{ hPa} = 100\text{ Pa}}$$

### Why we do this:
1. **Sensor Logged Unit:** Your pressure sensors (`outside_p`, `room_1_p`, etc.) output telemetry readings in **hectopascals ($\text{hPa}$)** (for example, $1013.25\text{ hPa}$ or $1008.50\text{ hPa}$).
2. **SI Engineering Unit Required:** Physical equations like the Ideal Gas Law ($\rho_{\text{air}} = \frac{P}{R \cdot T}$) and Psychrometric Vapor Equations require pressure in **standard SI units of Pascals ($\text{Pa}$)**.

Multiplying by $100$ converts the sensor reading to Pascals:
$$1013.25\text{ hPa} \times 100 = \mathbf{101,325\text{ Pa}}$$



We can deduce this directly from the numerical range logged in your dataset:

Looking at the raw sensor column `room_1_p` in your cleaned CSV file ([`Day 3 test 1 Take 1_2026-07-31_cleaned.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/experimental_data/with_occ/Day_3/cleaned_day_3/Day%203%20test%201%20Take%201_2026-07-31_cleaned.csv)):

```csv
room_1_p
954.9
954.9
954.8
954.8
```

### Physical Proof:
1. **$954.9\text{ hPa}$ (Hectopascals):** Standard sea-level pressure is $1013.25\text{ hPa}$. A reading of **$954.9\text{ hPa}$** is the exact expected barometric pressure for a laboratory location elevated slightly above sea level ($\sim 500\text{ m}$ elevation).
2. **If it were Pascals ($\text{Pa}$):** $954.9\text{ Pa} = 0.0094\text{ atm}$ (near vacuum — human collapse).
3. **If it were Kilopascals ($\text{kPa}$):** $954.9\text{ kPa} = 9.42\text{ atm}$ (extreme industrial pressure — chamber explosion).

Hence, **$954.9$** is mathematically and physically in **hectopascals ($\text{hPa}$)**!