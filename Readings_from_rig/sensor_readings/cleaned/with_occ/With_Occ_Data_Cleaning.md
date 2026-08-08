# Appendix B: Data Cleaning & Processing Formulation for With-Occupancy Datasets

---

## 1. Overview & Data Cleaning Pipeline

The telemetry logged during **occupancy experiments (Days 3 & 4)** captures dynamic human respiration (CO$_2$ emission rate $\dot{N}_{\text{occ}}$), occupant heat gain ($q_{\text{occ}}$), and active ventilation fan actuation.

To process raw sensor telemetry into continuous, noise-free time-series data for **Dual EKF state estimation** and **Occupancy Detection**, a multi-stage data cleaning and physical feature extraction pipeline was executed:

```
[Raw Telemetry] ──> [B.1 Hard Range Masking] ──> [B.2 Rolling 3σ Outlier Filter] ──> [B.3 PCHIP & Linear Interpolation] ──> [B.4 EMA Smoothing] ──> [B.5 Special Sensor Glitch Repairs] ──> [B.6 Spatial Zone Weighting] ──> [B.7 Airflow Mass Flow Rate Derivation (m_sa)]
```

---

## 2. B.1 Hard Range Masking

Raw sensor channels occasionally report invalid corrupted numbers (such as $65,535$ from 16-bit I2C bus overflow or $0.0$ from power glitches). For a raw reading $x_i$ at time step $t_i$:

$$x_i^{\text{masked}} = \begin{cases} x_i & \text{if } x_{\text{min}} \le x_i \le x_{\text{max}} \\ \text{NaN} & \text{otherwise} \end{cases}$$

### Physical Range Boundaries
* **Temperature ($T$):** $[5.0^{\circ}\text{C}, 50.0^{\circ}\text{C}]$
* **Relative Humidity ($\text{RH}$):** $[0.0\%, 100.0\%]$
* **CO$_2$ Concentration ($c$):** $[300.0\text{ ppm}, 850.0\text{ ppm}]$
  * *Fresh Air Cap:* Outdoor (`outside_c`) and Supply (`supply_c`) fresh air streams capped at $520.0\text{ ppm}$ to eliminate shutdown hardware latches.

---

## 3. B.2 Rolling $3\sigma$ Gaussian Outlier Filter

To detect transient electrical spikes within valid physical ranges without erasing actual dynamic temperature/CO$_2$ changes, a 2-minute centered rolling window $W_i = [t_i - 1\text{ min}, t_i + 1\text{ min}]$ containing $N = 24$ samples ($\Delta t = 5\text{s}$) is computed:

$$\mu_i = \frac{1}{N} \sum_{j \in W_i} x_j \quad \text{(Rolling Local Mean)}$$

$$\sigma_i = \sqrt{\frac{1}{N-1} \sum_{j \in W_i} (x_j - \mu_i)^2} \quad \text{(Rolling Local Standard Deviation)}$$

### Outlier Rejection Mask
$$\text{If } |x_i - \mu_i| > 3.0 \cdot \sigma_i \implies x_i^{\text{clean}} = \text{NaN}$$

---

## 4. B.3 Interpolation Techniques: Linear vs. PCHIP Spline

### 4.1 Linear `NaN` Interpolation
For standard missing data gaps, time-weighted linear interpolation is applied:

$$x(t) = x(t_k) + \frac{t - t_k}{t_{k+1} - t_k} \Big(x(t_{k+1}) - x(t_k)\Big)$$

### 4.2 Piecewise Cubic Hermite Interpolating Polynomial (PCHIP)
During microcontroller I2C bus lockup events (e.g. `day_3_p_2` stuck readings on $S_2$ for $\sim 13.5\text{ min}$ and $S_3$ for $\sim 15.2\text{ min}$), linear interpolation creates artificial straight-line slope discontinuities.

To preserve shape monotonicity and continuous first derivatives $x'(t)$ before and after stuck intervals, **PCHIP Spline Interpolation** is evaluated:

Given sub-interval points $(t_k, x_k)$ and $(t_{k+1}, x_{k+1})$ with step $h_k = t_{k+1} - t_k$ and slope $\Delta_k = (x_{k+1} - x_k) / h_k$:

$$P(t) = c_0 + c_1(t - t_k) + c_2(t - t_k)^2 + c_3(t - t_k)^3$$

Where derivative slopes $d_k = P'(t_k)$ are set to harmonic means of neighboring slopes to guarantee zero overshoots and non-oscillatory physical transitions.

---

## 5. B.4 Exponential Moving Average (EMA) Noise Suppression

High-frequency sensor quantization noise is suppressed using a first-order Low-Pass Exponential Moving Average (EMA) filter:

$$x_{\text{EMA}}(t_k) = \alpha \cdot x(t_k) + (1 - \alpha) \cdot x_{\text{EMA}}(t_{k-1})$$

Where $\alpha = 0.10$ ($90\%$ history weight, $10\%$ new sample weight), producing smooth curves for Dual EKF numerical Jacobian evaluation.

---

## 6. B.5 Special Sensor Glitch & Decay Bridge Repairs

1. **`day_3_p_1` Supply Air End Spike ($\text{CO}_{2,sa}$):** Stuck spike reaching $876\text{ ppm}$ at $t \approx 39\text{ min}$ was masked and capped at $520\text{ ppm}$ fresh air baseline.
2. **`day_4_p_3` Glitch Spike ($\text{CO}_{2,S2}$):** Electrical glitch spiking to $1,106\text{ ppm}$ at $t \approx 26\text{ min}$ was repaired by constructing an empirical noise-matched monotonic decay bridge ($\sigma_{\text{noise}} = 22.5\text{ ppm}$) down to baseline ($435\text{ ppm}$).

---

## 7. B.6 Spatial Zone Weighting ($T_z$, $\text{RH}_z$, $c_z$)

### Sensor Weighting Rationale Table

| Sensor | Hardware Type & Location | Weight | Reason for Assigned Weight |
| :--- | :--- | :---: | :--- |
| **$S_1$** | Bosch BME280 / BMP280 (Wall 1) | **50%** | Primary reference sensor with highest precision and lowest noise. |
| **$S_2$** | ScioSense ENS160 #1 (Wall 2) | **30%** | Exhibited a $+2.5^{\circ}\text{C}$ drift offset. Primary CO$_2$ sensor. |
| **$S_3$** | ScioSense ENS160 #2 (Wall 3) | **20%** | Lower weight due to raw spikes. Offline on `day_3_p_3`, `day_3_p_4`, and all Day 4 datasets (`day_4_p_1` through `day_4_p_6`). |

### A. `day_3_p_1` & `day_3_p_2` (All Sensors Active)
* **Temperature ($T_z$):** $T_z = 0.50 \cdot S_1 + 0.30 \cdot S_2 + 0.20 \cdot S_3$
* **Relative Humidity ($\text{RH}_z$):** $\text{RH}_z = 0.50 \cdot S_1 + 0.30 \cdot S_2 + 0.20 \cdot S_3$
* **CO$_2$ Concentration ($c_z$):** $c_z = 0.60 \cdot S_2 + 0.40 \cdot S_3$

### B. `day_3_p_3`, `day_3_p_4`, and All Day 4 Datasets (`day_4_p_1` to `day_4_p_6`) ($S_3$ Sensor Offline Exception)
* **Temperature ($T_z$):** $T_z = 0.60 \cdot S_1 + 0.40 \cdot S_2$
* **Relative Humidity ($\text{RH}_z$):** $\text{RH}_z = 0.60 \cdot S_1 + 0.40 \cdot S_2$
* **CO$_2$ Concentration ($c_z$):** $c_z = S_2 \quad \text{(100\% weight on Wall 2 sensor } S_2\text{)}$

---

## 8. B.7 Supply Airflow Mass Flow Rate Derivation ($m_{sa}$)

HVAC fan speed percentage ($0\text{--}100\%$) is converted into supply air mass flow rate $m_{sa}\ (\text{kg/s})$ using anemometer duct calibration lookup grids:

$$v_{\text{air}} = \text{interp}\left(\text{fan\%}, \mathbf{GRID}_{\text{fan}}, \mathbf{GRID}_{\text{vel}}\right) \quad [\text{m/s}]$$

$$m_{sa} = \rho_{\text{air}} \cdot v_{\text{air}} \cdot A_{\text{duct}} \quad \left[\frac{\text{kg}}{\text{s}}\right]$$

### Physical Constants & Duct Geometry
* **Duct Diameter:** $d = 11\text{ cm} = 0.11\text{ m}$
* **Cross-Sectional Area:** $A_{\text{duct}} = \pi \cdot (0.055)^2 = 0.0095033\text{ m}^2$
* **Air Density:** $\rho_{\text{air}} = 1.20\text{ kg/m}^3$

The derived column `m_sa_kgs` is saved directly to all cleaned `with_occ` CSV files.

---

## 9. Summary of Cleaned Output Datasets

| Standard Dataset Name | Original Experiment Title | Cleaned CSV File Path |
|---|---|---|
| **`day_3_p_1`** | Day 3 Test 1 Take 1 | [`sensor_readings/cleaned/with_occ/day_3_p_1.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_3_p_1.csv) |
| **`day_3_p_2`** | Day 3 Test 1 Take 2 | [`sensor_readings/cleaned/with_occ/day_3_p_2.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_3_p_2.csv) |
| **`day_3_p_3`** | Day 3 Test 1 Take 4 | [`sensor_readings/cleaned/with_occ/day_3_p_3.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_3_p_3.csv) |
| **`day_3_p_4`** | Day 3 Test 1 Take 5 | [`sensor_readings/cleaned/with_occ/day_3_p_4.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_3_p_4.csv) |
| **`day_4_p_1`** | Day 4 Test 1 | [`sensor_readings/cleaned/with_occ/day_4_p_1.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_4_p_1.csv) |
| **`day_4_p_2`** | Day 4 Test 2 | [`sensor_readings/cleaned/with_occ/day_4_p_2.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_4_p_2.csv) |
| **`day_4_p_3`** | Day 4 Test 3 Take 1 | [`sensor_readings/cleaned/with_occ/day_4_p_3.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_4_p_3.csv) |
| **`day_4_p_4`** | Day 4 Test 3 Take 2 | [`sensor_readings/cleaned/with_occ/day_4_p_4.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_4_p_4.csv) |
| **`day_4_p_5`** | Day 4 Test 4 | [`sensor_readings/cleaned/with_occ/day_4_p_5.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_4_p_5.csv) |
| **`day_4_p_6`** | Day 4 Test 5 | [`sensor_readings/cleaned/with_occ/day_4_p_6.csv`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/cleaned/with_occ/day_4_p_6.csv) |

