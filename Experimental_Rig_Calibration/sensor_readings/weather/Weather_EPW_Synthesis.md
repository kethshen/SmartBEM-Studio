# Appendix C: EnergyPlus EPW Weather Synthesis & Boundary Condition Formulation

---

## 1. Overview & Objectives

Thermal calibration of the test rig EnergyPlus Building Energy Model (BEM) requires high-resolution, physically accurate ambient boundary conditions. Standard climate weather files (TMY) provide historical typical conditions, but lack the exact ambient variations experienced during experimental test days.

To bridge this gap, a hybrid **EPW Weather Synthesis Engine** was developed. It merges real-time high-resolution experimental telemetry logged by outdoor weather sensors with solar radiation and sky temperature models from the official Kandy TMY weather dataset (`LKA_CP_Kandy.434440_TMYx.2011-2025.epw`).

```
[Cleaned Rig Telemetry] ───┐
                           ├─> [EPW Synthesis Engine] ──> [1-Minute EPW Weather Files]
[Official Kandy TMY EPW] ──┘
```

---

## 2. Telemetry Ingestion & Resampling

Telemetry logged at $\Delta t = 5\text{s}$ interval from `sensor_readings/cleaned/without_occ/` is resampled onto a clean 1-minute grid ($N=60\text{ s}$) using time-weighted linear interpolation:

* **Dry-Bulb Temperature ($T_{\text{db}}$):** Logged outdoor temperature sensor (`outside_t`).
* **Relative Humidity ($\text{RH}$):** Logged outdoor relative humidity sensor (`outside_h`).
* **Atmospheric Pressure ($p_{\text{atm}}$):** Logged barometric pressure sensor (`outside_p`), with automatic fallback to Wall 1 reference sensor (`room_1_p` $\approx 955.8\text{ hPa}$) to account for elevation ($477\text{ m}$ above sea level in Kandy, Sri Lanka).
* **Wind Speed ($v_{\text{wind}}$):** Logged anemometer air velocity (`outside_v`).

---

## 3. Psychrometric & Solar Formulations

### 3.1 Dew-Point Temperature Calculation ($T_{\text{dp}}$)
Dew-point temperature $T_{\text{dp}}\ (^{\circ}\text{C})$ is derived using the Magnus-Tetens approximation formula:

$$\alpha(T_{\text{db}}, \text{RH}) = \frac{a \cdot T_{\text{db}}}{b + T_{\text{db}}} + \ln\left(\frac{\text{RH}}{100}\right)$$

$$T_{\text{dp}} = \frac{b \cdot \alpha(T_{\text{db}}, \text{RH})}{a - \alpha(T_{\text{db}}, \text{RH})}$$

Where $a = 17.27$ and $b = 237.7^{\circ}\text{C}$.

### 3.2 Solar Irradiance & Sky Radiation Blending
Global Horizontal Irradiance ($\text{GHI}$), Direct Normal Irradiance ($\text{DNI}$), Diffuse Horizontal Irradiance ($\text{DHI}$), and Infrared Sky Radiation ($I_{\text{sky}}$) are extracted directly from the official Kandy TMY EPW profile to ensure radiative heat transfer balance on chamber exterior surfaces.

---

## 4. Generated Standardized EPW Weather Files

Two standardized 1-minute EPW weather files were synthesized and saved in [`sensor_readings/weather/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/weather):

| EPW Weather File Name | Test Date | Source Telemetry Datasets | Verification Figure |
|---|---|---|---|
| **[`day_1_weather.epw`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/weather/day_1_weather.epw)** | July 21, 2026 | `day_1_p_1.csv` (Idle Envelope Calibration) | [`day_1_weather_verification.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/weather/day_1_weather_verification.png) |
| **[`day_2_weather.epw`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/weather/day_2_weather.epw)** | July 23, 2026 | `day_2_p_1.csv` through `day_2_p_4.csv` | [`day_2_weather_verification.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/sensor_readings/weather/day_2_weather_verification.png) |

---

## 5. Verification Plots Overview

Each verification figure contains 5 stacked subplots:

1. **Outdoor Temperature ($T_{\text{db}}$):** Fixed Y-axis limits ($30\text{--}35^{\circ}\text{C}$ for Day 1; $25\text{--}35^{\circ}\text{C}$ for Day 2).
2. **Relative Humidity ($\text{RH}$):** Fixed Y-axis limits ($20\text{--}80\%$ for Day 1; $0\text{--}100\%$ for Day 2).
3. **Barometric Pressure ($p_{\text{atm}}$):** Fixed Y-axis limits ($940\text{--}970\text{ hPa}$).
4. **Global Horizontal Solar Irradiance ($\text{GHI}$):** Fixed Y-axis limits ($0\text{--}1200\text{ W/m}^2$).
5. **Wind Speed ($v_{\text{wind}}$):** Fixed Y-axis limits ($0\text{--}5.0\text{ m/s}$).
