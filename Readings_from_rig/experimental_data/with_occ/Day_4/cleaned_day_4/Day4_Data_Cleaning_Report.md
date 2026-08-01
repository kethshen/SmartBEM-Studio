# Day 4 Experimental Dataset Cleaning & Processing Summary

This document provides a comprehensive technical reference for the data cleaning, sensor re-weighting, gap interpolation, empirical noise synthesis, and plot adjustments applied to the **Day 4 Occupancy Experimental Datasets** in `cleaned_day_4/`.

---

## 1. General Data Cleaning Pipeline (Appendix A Standard)

All raw 5-second sensor telemetry streams were processed through a 4-stage sequential data cleaning pipeline:

1. **Hard Range Masking (Physical Bounds Filtering):**
   - **Temperature ($T$):** $[5.0^\circ\text{C}, 50.0^\circ\text{C}]$
   - **Relative Humidity ($RH$):** $[20.0\%, 120.0\%]$
   - **$\text{CO}_2$ Concentration:** $[300.0\text{ ppm}, 700.0\text{ ppm}]$ (Supply/Outdoor fresh air capped at $520.0\text{ ppm}$)
   - *Purpose:* Removes hardware dropouts, $0\text{ V}$ sensor offline states, and ADC transmission overflow glitches ($65,535\text{ ppm}$).

2. **Rolling $3\sigma$ Gaussian Outlier Filter:**
   - Window size: $N = 24$ samples ($2\text{ minutes}$ at $5\text{s}$ sampling rate).
   - Rejects any sample where $|x - \mu_{\text{rolling}}| > 3.0 \cdot \sigma_{\text{rolling}}$.
   - *Purpose:* Eliminates transient electrical noise spikes and electromagnetic interference.

3. **Linear Gap Interpolation:**
   - Fills masked `NaN` entries via linear interpolation (`interpolate(method='linear')`).

4. **Exponential Moving Average (EMA) Noise Smoothing:**
   - Smoothing factor: $\alpha = 0.10$.
   - *Purpose:* Attenuates high-frequency sensor noise while preserving physical thermal and mass dynamics.

---

## 2. Dataset-Specific & Sensor-Specific Adjustments

### A. Spatial Weighting Equations ($T_z$, $RH_z$, $\text{CO}_{2,z}$)

#### Temperature ($T_z$) & Humidity ($RH_z$)
- **Sensor 3 ($S_3$) Offline Status:** Across Day 4 Tests 1, 2, 3 (Take 1 & 2), 4, and 5, Sensor 3 ($S_3$) was offline ($0^\circ\text{C}$ / $0\%$ RH) or corrupted. Including $0^\circ\text{C}$ drops $T_z$ artificially. Weights were re-normalized between active sensors $S_1$ and $S_2$:
  $$T_z = 0.60 \cdot S_1 + 0.40 \cdot S_2$$
  $$RH_z = 0.60 \cdot S_1 + 0.40 \cdot S_2$$
- **Day 4 Test 4 & Test 5 $S_3$ Removal:** $S_3$ had noisy glitch points in Test 4 and overflow points in Test 5—$S_3$ was completely removed/neglected from all $T, RH, \text{CO}_2$ plots and CSVs for these tests.

#### $\text{CO}_2$ Concentration ($\text{CO}_{2,z}$)
- **Sensor Hardware Note:** Sensor 1 ($S_1$) and Sensor 3 ($S_3$) have no physical $\text{CO}_2$ measurements ($S_1 = 0\text{ ppm}, S_3 = 0\text{ ppm}$).
- **Zone $\text{CO}_2$ Formula (All Day 4 Datasets):**
  $$\text{CO}_{2,z} = S_2 \quad (\text{Wall 2 alone treated as zone }\text{CO}_2)$$
- **Plot Styling:**
  - In Plot 3.3 (`[Dataset]_co2_wall_sensors_plus_weighted_CO2z.png`), **Wall 2 ($S_2$)** is rendered in **ORANGE (`#ff7f0e`)**.
  - In Plot 3.4 (`[Dataset]_co2_weighted_CO2z_plus_supply_outdoor.png`), **Zone $\text{CO}_2$ ($S_2$)** is rendered in **BOLD BLACK (`#000000`)**.

---

### B. Special Sensor Freeze, Spike & Disconnection Corrections

#### 1. Day 4 Test 3 Take 1 Hardware Glitch Spike ($\text{CO}_{2,S2}$)
- **Issue:** Sensor $S_2$ experienced an electrical glitch at $t \approx 26.0\text{ min}$ (Row 311+), spiking up to $1106\text{ ppm}$.
- **Fix:** Masked Row 311 to end as `NaN`. Measured empirical raw noise std ($\sigma_{\text{measured}} = 22.50\text{ ppm}$) from uncorrupted window ($t \in [8, 23\text{ min}]$), constructed a noise-matched monotonic decay bridge down to baseline ($435\text{ ppm}$), and passed it through EMA ($\alpha = 0.10$).
- **Impacted Files:** 
  - `Day 4 Test 3 Take 1_2026-07-31_co2_wall_sensors_before_vs_after.png`
  - `Day 4 Test 3 Take 1_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`

#### 2. Day 4 Test 4 Microcontroller Disconnection Drop ($\text{CO}_{2,S2}$)
- **Issue:** Sensor $S_2$ disconnected/reset at $t \approx 43.0\text{ min}$ (Row 516+), dropping suddenly to the factory default floor ($400\text{ ppm}$).
- **Fix:** Masked Row 516 to end as `NaN`. Measured empirical raw noise std ($\sigma_{\text{measured}} = 19.04\text{ ppm}$) from uncorrupted window ($t \in [15, 38\text{ min}]$), applied a noise-matched monotonic decay bridge down to baseline ($425\text{ ppm}$) eliminating the artificial upward hump, and passed it through EMA ($\alpha = 0.10$).
- **Impacted Files:**
  - `Day 4 Test 4_2026-07-31_co2_wall_sensors_before_vs_after.png`
  - `Day 4 Test 4_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`

#### 3. Day 4 Test 5 Supply Air End Freeze ($\text{CO}_{2,sa}$)
- **Issue:** Supply air $\text{CO}_2$ froze flat at $432\text{ ppm}$ at $t \ge 42.75\text{ min}$ (Row 510+).
- **Fix:** Masked Row 510 to end as `NaN`. Measured empirical noise std ($\sigma_{\text{measured}} = 0.855\text{ ppm}$) from uncorrupted supply window, constructed a noise-matched monotonic decay bridge down to baseline ($420\text{ ppm}$), and smoothed via EMA ($\alpha = 0.10$).
- **Impacted File:** `Day 4 Test 5_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`

---

## 3. Controls & Actuation Conversion ($m_{sa}$)

- **Plot Layout:** Left Y-axis locked to $[20\%, 120\%]$ for Fan Speed (%) and Mixer Damper (%).
- **Mass Flow Rate Conversion:** Fan Speed (%) converted to Supply Airflow Mass Flow Rate $m_{sa}$ ($\text{kg/s}$) using `fan_value_and_anemometer.csv` calibration data on right Y-axis.
- **Duct Specifications:**
  - Duct Diameter: $d = 11\text{ cm} = 0.11\text{ m}$
  - Cross-sectional Area: $A_{\text{duct}} = \pi \cdot (0.055)^2 = 0.0095033\text{ m}^2$
  - Air Density: $\rho_{\text{air}} = 1.20\text{ kg/m}^3$
  - Formula: $m_{sa} = \rho_{\text{air}} \cdot v_{\text{air}} \cdot A_{\text{duct}} \quad (\text{kg/s})$
- **Saved Column:** `m_sa_kgs` added to all cleaned CSVs.

---

## 4. Summary of Output Files & Plot References

### Cleaned CSV Datasets
- `Day 4 Test 1_2026-07-31_cleaned.csv`
- `Day 4 Test 2_2026-07-31_cleaned.csv`
- `Day 4 Test 3 Take 1_2026-07-31_cleaned.csv`
- `Day 4 Test 3 Take 2_2026-07-31_cleaned.csv`
- `Day 4 Test 4_2026-07-31_cleaned.csv`
- `Day 4 Test 5_2026-07-31_cleaned.csv`

---

### Plot File References per Subfolder

#### A. Temperature Subfolder (`temp/`)
- `Day 4 Test 1_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 4 Test 1_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 1_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 4 Test 1_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`
- `Day 4 Test 2_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 4 Test 2_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 2_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 4 Test 2_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`
- `Day 4 Test 3 Take 1_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 4 Test 3 Take 1_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 3 Take 1_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 4 Test 3 Take 1_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`
- `Day 4 Test 3 Take 2_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 4 Test 3 Take 2_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 3 Take 2_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 4 Test 3 Take 2_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`
- `Day 4 Test 4_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 4 Test 4_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 4_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 4 Test 4_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`
- `Day 4 Test 5_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 4 Test 5_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 5_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 4 Test 5_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`

#### B. Humidity Subfolder (`humidity/`)
- `Day 4 Test 1_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 4 Test 1_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 1_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 4 Test 1_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`
- `Day 4 Test 2_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 4 Test 2_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 2_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 4 Test 2_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`
- `Day 4 Test 3 Take 1_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 4 Test 3 Take 1_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 3 Take 1_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 4 Test 3 Take 1_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`
- `Day 4 Test 3 Take 2_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 4 Test 3 Take 2_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 3 Take 2_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 4 Test 3 Take 2_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`
- `Day 4 Test 4_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 4 Test 4_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 4_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 4 Test 4_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`
- `Day 4 Test 5_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 4 Test 5_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 5_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 4 Test 5_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`

#### C. $\text{CO}_2$ Subfolder (`co2/`)
- `Day 4 Test 1_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 4 Test 1_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 1_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 4 Test 1_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`
- `Day 4 Test 2_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 4 Test 2_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 2_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 4 Test 2_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`
- `Day 4 Test 3 Take 1_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 4 Test 3 Take 1_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 3 Take 1_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 4 Test 3 Take 1_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`
- `Day 4 Test 3 Take 2_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 4 Test 3 Take 2_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 3 Take 2_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 4 Test 3 Take 2_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`
- `Day 4 Test 4_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 4 Test 4_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 4_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 4 Test 4_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`
- `Day 4 Test 5_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 4 Test 5_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 4 Test 5_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 4 Test 5_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`

#### D. Controls Subfolder (`controls/`)
- `Day 4 Test 1_2026-07-31_controls.png`
- `Day 4 Test 2_2026-07-31_controls.png`
- `Day 4 Test 3 Take 1_2026-07-31_controls.png`
- `Day 4 Test 3 Take 2_2026-07-31_controls.png`
- `Day 4 Test 4_2026-07-31_controls.png`
- `Day 4 Test 5_2026-07-31_controls.png`

#### E. Occupancy Subfolder (`occupancy/`)
- `Day 4 Test 1_2026-07-31_occupancy.png`
- `Day 4 Test 2_2026-07-31_occupancy.png`
- `Day 4 Test 3 Take 1_2026-07-31_occupancy.png`
- `Day 4 Test 3 Take 2_2026-07-31_occupancy.png`
- `Day 4 Test 4_2026-07-31_occupancy.png`
- `Day 4 Test 5_2026-07-31_occupancy.png`


---

## Appendix A: Mathematical Deep Dive — Empirical Sensor Noise Extraction & Monotonic Decay Synthesis

When reconstructing corrupted or glitched telemetry segments (e.g., sensor disconnects or hardware spikes), simple mathematical curves can appear unnaturally smooth compared to real sensor signals. A 4-stage empirical noise synthesis and decay process is implemented to match the exact physical noise texture of the telemetry hardware.

### 1. Residual Sensor Noise Decomposition
Over an uncorrupted telemetry window $[k_{\text{start}}, k_{\text{end}}]$, the observed raw sensor stream $x_{\text{raw}}[k]$ is decomposed into a deterministic physical trend $x_{\text{smooth}}[k]$ and a zero-mean stochastic noise component $n[k]$:
$$x_{\text{raw}}[k] = x_{\text{smooth}}[k] + n[k]$$
$$n[k] = x_{\text{raw}}[k] - x_{\text{smooth}}[k]$$

### 2. Empirical Standard Deviation Estimation ($\sigma_{\text{empirical}}$)
The empirical noise variance $\sigma_{\text{empirical}}^2$ of the physical sensor module is calculated across $M$ uncorrupted samples:
$$\bar{n} = \frac{1}{M} \sum_{k=1}^M n[k]$$
$$\sigma_{\text{empirical}} = \sqrt{ \frac{1}{M-1} \sum_{k=1}^M \left( n[k] - \bar{n} \right)^2 }$$

For example, empirical measurement yielded:
- **Day 4 Test 3 Take 1 ($S_2$):** $\sigma_{\text{empirical}} = 22.501\text{ ppm}$
- **Day 4 Test 4 ($S_2$):** $\sigma_{\text{empirical}} = 19.037\text{ ppm}$
- **Day 4 Test 5 (Supply Air):** $\sigma_{\text{empirical}} = 0.855\text{ ppm}$

### 3. Monotonic Bridge Decay Function ($y_{\text{bridge}}[k]$)
Across a corrupted gap $[k_0, k_0 + N - 1]$, a linear/exponential decay trajectory is constructed connecting boundary value $y_{\text{start}}$ to ambient baseline $y_{\text{end}}$:
$$y_{\text{bridge}}[k] = y_{\text{start}} + \frac{k - k_0}{N - 1} \left( y_{	ext{end}} - y_{	ext{start}} \right), \quad k \in [k_0, k_0 + N - 1]$$

### 4. Stochastic Superposition & Exponential Moving Average (EMA) Filtering
Independent zero-mean Gaussian noise matching $\sigma_{\text{empirical}}$ is synthesized and superimposed onto the decay bridge to form a raw synthetic stream:
$$x_{\text{synth\_raw}}[k] = y_{\text{bridge}}[k] + e[k], \quad e[k] \sim \mathcal{N}(0, \sigma_{\text{empirical}}^2)$$

To ensure identical dynamic filtering across the entire dataset, the synthetic raw stream is passed through the same causal Exponential Moving Average (EMA) filter:
$$x_{\text{clean}}[k] = \alpha \cdot x_{\text{synth\_raw}}[k] + (1 - \alpha) \cdot x_{\text{clean}}[k-1], \quad \alpha = 0.10$$

This guarantees that the reconstructed segment maintains identical smooth ripple dynamics, frequency response, and statistical noise properties as the valid telemetry.
