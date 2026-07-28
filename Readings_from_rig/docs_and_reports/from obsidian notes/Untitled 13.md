
## 1. Experimental Dataset & Test Rig Procedure

* **Test Date & Local Time:** Recorded on `2026-07-21` from **1:14 PM to 4:04 PM Local Time** (about 3 hours total runtime).
* **Sampling Rate:** Data was logged every **5 seconds** from the physical sensors.
* **Test Procedure:** We closed the $8\text{ m}^3$ chamber tightly and turned ON the AC unit to cool it down. We kept internal mixer fans running at a constant speed to mix the air evenly inside the chamber. The outer ME hangar acted as an unconditioned buffer space around the chamber.

### Sensor
To get one true room temperature reading $T_z$ for the whole chamber, we combined three sensors with different weights based on where they are placed and how accurate they are:

$$T_z(t) = 0.50 \cdot S_1 + 0.30 \cdot S_2 + 0.20 \cdot S_3$$

| Sensor    | Type & Location                           | Weight  | Reason for Weight                                    |
| :-------- | :---------------------------------------- | :-----: | :--------------------------------------------------- |
| **$S_1$** | Bosch BME280 / BMP280 (Center of Chamber) | **50%** | Main core sensor with highest accuracy and low noise |
| **$S_2$** | DHT22 #1 (Upper Air Layer)                | **30%** | Measures warm air accumulating at the top            |
| **$S_3$** | DHT22 #2 (Lower Floor Layer)              | **20%** | Measures cooler air near the floor                   |

*(Note: DHT22 #3 was broken and showing crazy spikes, so we removed it completely).*

### Data Cleaning Steps
Before feeding the raw data to EnergyPlus, we cleaned it in 3 simple steps:
1. **Spike Filtering:** Removed impossible hardware glitch readings (like $+100^{\circ}\text{C}$ or $-15^{\circ}\text{C}$).
2. **Outlier Filtering ($3\sigma$ Z-score):** Removed sudden random jump errors and replaced them with smooth values.
3. **EMA Smoothing:** Applied Exponential Moving Average smoothing so the line stays smooth without losing the real cooling trend.

#### Figure 1: Raw Sensor Data vs. Cleaned Data
![Raw vs Cleaned Sensors](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/data_cleaning/01_idle_before_vs_after.png)

#### Figure 2: Individual Cleaned Sensors vs. Combined Target Room Temperature $T_z(t)$
![Weighted Zone Temp Tz vs Individual Sensors](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/data_cleaning/01_idle_weighted_tz.png)

---

## 2. EnergyPlus Model & Custom Setup

* **Chamber & Hangar Size:** The test chamber is $2\text{ m} \times 2\text{ m} \times 2\text{ m} = 8\text{ m}^3$ inside an outer hangar zone.
* **Thermal Mass & Room Contents:** We added internal thermal mass objects inside EnergyPlus to account for heat absorbed by internal equipment and walls.
* **Custom Materials:** We created custom 100 mm Polyurethane (PU) Rigid Foam insulation wall layers.
* **Custom Weather EPW File:** We built our own EPW weather file using real outdoor temperature readings measured on site ($32.0^{\circ}\text{C}$ to $33.0^{\circ}\text{C}$).
* **Simulation Setup:** Ran with 1-minute calculation steps. Before the AC turned on at $t=0$, we added a small $320\text{ W}$ heat soak to warm up the chamber to **$29.9^{\circ}\text{C}$**, matching the exact starting room temperature when the test began.

---

## 3. Calibration Method (ASHRAE Guideline 14 & DTW)

To make EnergyPlus follow the real cooling curve, we used an automated optimizer loop:
* **Optimizer:** Bounded Nelder-Mead algorithm running on normalized $[0, 1]$ parameters so all settings optimize equally.
* **ASHRAE Standard Metrics:** Evaluated $\text{CV(RMSE)}$ (Target $\le 5\%$) and $\text{NMBE}$ (Target $\le 2\%$).
* **Dynamic Time Warping (DTW):** Used DTW shape distance in our loss score to force EnergyPlus to bend smoothly along the real $29.9^{\circ}\text{C} \rightarrow 20.4^{\circ}\text{C}$ pulldown curve.

---

## 4. Calibration Parameters & Final Results

#### Table 1: Starting Parameters vs. Final Calibrated Parameters
| Parameter | Starting Value | **Final Calibrated Value** | Search Range | Physical Role |
| :--- | :---: | :---: | :---: | :--- |
| **PU Foam Conductivity ($k$)** | $0.0220\text{ W/(m}\cdot\text{K)}$ | **$0.0260\text{ W/(m}\cdot\text{K)}$** | $[0.0150, 0.0450]$ | How well foam stops heat flow |
| **PU Foam Specific Heat ($c_p$)** | $1500.0\text{ J/(kg}\cdot\text{K)}$ | **$1449.2\text{ J/(kg}\cdot\text{K)}$** | $[800.0, 1800.0]$ | How much heat walls hold |
| **PU Foam Density ($\rho$)** | $32.0\text{ kg/m}^3$ | **$32.2\text{ kg/m}^3$** | $[20.0, 45.0]$ | Mass density of foam |
| **Chamber Infiltration ($\text{ACH}$)** | $0.10\text{ hr}^{-1}$ | **$0.115\text{ hr}^{-1}$** | $[0.01, 0.50]$ | Air leakiness of chamber |
| **AC Cooling Power ($Q_{\text{cool}}$)** | $600.0\text{ W}$ | **$461.0\text{ W}$** | $[300.0, 1200.0]$ | Actual cooling delivered |

---

## 5. Visual Comparison & Final Model Accuracy

#### Figure 3: Before Calibration (Uncalibrated Baseline — Flat Setpoint Line)
![Uncalibrated Baseline Plot](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/sim_vs_sensors_exact_rig_match.png)

#### Figure 4: After Calibration (Final Calibrated Model — Exact Curvature Match)
![Final Calibrated ASHRAE DTW Model Plot](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/plots/calibrated_ashrae_dtw_sim_vs_sensors.png)

#### Table 2: Final Accuracy Progress Summary
| Accuracy Metric | Uncalibrated Baseline | **Final Calibrated Model** | ASHRAE Standard Target | Result |
| :--- | :---: | :---: | :---: | :---: |
| **ASHRAE CV(RMSE)** | $17.45\%$ | **$3.90\%$** | $\le 5.0\%$ | **PASS (Exceeds Target)** |
| **ASHRAE NMBE** | $-12.48\%$ | **$-0.00\%$** | $|\text{NMBE}| \le 2.0\%$ | **PASS (Zero Bias)** |
| **RMSE Error** | $22.55^{\circ}\text{C}$ | **$0.89^{\circ}\text{C}$** | — | **$96.1\%$ Error Drop** |
| **MAE Error** | $19.24^{\circ}\text{C}$ | **$0.59^{\circ}\text{C}$** | — | **$96.9\%$ Error Drop** |
| **$R^2$ Score** | $-145.58$ | **$+0.8980$** | $> 0.80$ | **High Curve Match** |
