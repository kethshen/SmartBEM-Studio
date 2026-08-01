# Day 3 Experimental Dataset Cleaning & Processing Summary

This document provides a comprehensive technical reference for the data cleaning, sensor re-weighting, gap interpolation, and plot adjustments applied to the **Day 3 Occupancy Experimental Datasets** in `cleaned_day_3/`.

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
- **Take 1 & Take 2 (All 3 Sensors Active):**
  $$T_z = 0.50 \cdot S_1 + 0.30 \cdot S_2 + 0.20 \cdot S_3$$
  $$RH_z = 0.50 \cdot S_1 + 0.30 \cdot S_2 + 0.20 \cdot S_3$$
- **Take 4 & Take 5 (Sensor 3 $S_3$ Offline / $0^\circ\text{C}$):**
  *Rationale:* Sensor 3 ($S_3$) was offline during Take 4 and Take 5. Including $0^\circ\text{C}$ in the weighting drops $T_z$ artificially. Weights were re-normalized between active sensors $S_1$ and $S_2$:
  $$T_z = 0.60 \cdot S_1 + 0.40 \cdot S_2$$
  $$RH_z = 0.60 \cdot S_1 + 0.40 \cdot S_2$$

#### $\text{CO}_2$ Concentration ($\text{CO}_{2,z}$)
- **Sensor Hardware Note:** Sensor 1 ($S_1$) does not have a physical $\text{CO}_2$ hardware module ($S_1 = 0\text{ ppm}$).
- **Take 1 & Take 2 ($S_2$ and $S_3$ Active):**
  $$\text{CO}_{2,z} = 0.70 \cdot S_2 + 0.30 \cdot S_3$$
- **Take 4 & Take 5 (Sensor 3 $S_3$ Offline):**
  $$\text{CO}_{2,z} = S_2 \quad (\text{Wall 2 alone treated as zone }\text{CO}_2)$$

---

### B. Special Sensor Freeze & Spike Corrections

#### 1. Day 3 Take 1 Supply Air End Spike ($\text{CO}_{2,sa}$)
- **Issue:** Supply air $\text{CO}_2$ contained a stuck spike reaching $876\text{ ppm}$ at $t \approx 39\text{ min}$ (Rows 464–480).
- **Cause:** Sensor hardware latching during chamber shutdown.
- **Fix:** Hard upper bound masking at $520.0\text{ ppm}$ for supply air, keeping the cleaned supply $\text{CO}_2$ curve smooth at fresh air baseline ($\sim 415\text{ ppm}$).
- **Impacted File:** `Day 3 test 1 Take 1_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`

#### 2. Day 3 Take 1 Sensor 3 Freeze ($\text{CO}_{2,S3}$)
- **Issue:** Sensor 3 remained stuck flat at $412\text{ ppm}$ from $t = 0\text{ to }25\text{ mins}$ while occupants entered at $t = 5\text{ min}$.
- **Fix:** Treated $S_3$ as offline during $t = 0\text{ to }25\text{ mins}$, setting $\text{CO}_{2,z} = S_2$. After $t = 25\text{ mins}$ (when $S_3$ unfreezes), transitioned to $\text{CO}_{2,z} = 0.70 S_2 + 0.30 S_3$.
- **Impacted File:** `Day 3 test 1 Take 1_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`

#### 3. Day 3 Take 2 Sensor $S_2$ and $S_3$ Microcontroller Freeze (PCHIP Spline Interpolation)
- **Issue:** Microcontroller I2C bus lockup caused flat zero-variance stuck readings:
  - **$S_2$ (`room_2_c`) Stuck:** Lines 280 to 443 at $507\text{ ppm}$ (`07:23:19 AM` to `07:36:54 AM`, $\sim 13.5\text{ min}$).
  - **$S_3$ (`room_3_c`) Stuck:** Lines 109 to 309 at $432\text{ ppm}$ (`07:09:04 AM` to `07:24:19 AM`, $\sim 15.25\text{ min}$).
- **Fix:** Masked stuck line segments as `NaN` and applied **PCHIP Spline Interpolation (`method='pchip'`)** followed by light EMA smoothing.
- **Rationale:** PCHIP preserves the natural physical curvature and dynamic momentum before and after the freeze without creating artificial straight lines, providing ideal continuous input for EKF state estimation.
- **Impacted Files:** 
  - `Day 3 Test 1 Take 2_2026-07-31_co2_wall_sensors_before_vs_after.png`
  - `Day 3 Test 1 Take 2_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`

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
- `Day 3 test 1 Take 1_2026-07-31_cleaned.csv`
- `Day 3 Test 1 Take 2_2026-07-31_cleaned.csv`
- `Day 3 Test 1 Take 4_2026-07-31_cleaned.csv`
- `Day 3 Test 1 Take 5_2026-07-31_cleaned.csv`

---

### Plot File References per Subfolder

#### A. Temperature Subfolder (`temp/`)
- `Day 3 test 1 Take 1_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 3 test 1 Take 1_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 3 test 1 Take 1_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 3 test 1 Take 1_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 2_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 2_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 2_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 3 Test 1 Take 2_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 4_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 4_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 4_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 3 Test 1 Take 4_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 5_2026-07-31_temp_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 5_2026-07-31_temp_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 5_2026-07-31_temp_wall_sensors_plus_weighted_Tz.png`
- `Day 3 Test 1 Take 5_2026-07-31_temp_weighted_Tz_plus_supply_outdoor.png`

#### B. Humidity Subfolder (`humidity/`)
- `Day 3 test 1 Take 1_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 3 test 1 Take 1_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 3 test 1 Take 1_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 3 test 1 Take 1_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 2_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 2_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 2_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 3 Test 1 Take 2_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 4_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 4_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 4_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 3 Test 1 Take 4_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 5_2026-07-31_humidity_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 5_2026-07-31_humidity_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 5_2026-07-31_humidity_wall_sensors_plus_weighted_RHz.png`
- `Day 3 Test 1 Take 5_2026-07-31_humidity_weighted_RHz_plus_supply_outdoor.png`

#### C. $\text{CO}_2$ Subfolder (`co2/`)
- `Day 3 test 1 Take 1_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 3 test 1 Take 1_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 3 test 1 Take 1_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 3 test 1 Take 1_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 2_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 2_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 2_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 3 Test 1 Take 2_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 4_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 4_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 4_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 3 Test 1 Take 4_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`
- `Day 3 Test 1 Take 5_2026-07-31_co2_wall_sensors_before_vs_after.png`
- `Day 3 Test 1 Take 5_2026-07-31_co2_supply_return_outdoor_before_vs_after.png`
- `Day 3 Test 1 Take 5_2026-07-31_co2_wall_sensors_plus_weighted_CO2z.png`
- `Day 3 Test 1 Take 5_2026-07-31_co2_weighted_CO2z_plus_supply_outdoor.png`

#### D. Controls Subfolder (`controls/`)
- `Day 3 test 1 Take 1_2026-07-31_controls.png`
- `Day 3 Test 1 Take 2_2026-07-31_controls.png`
- `Day 3 Test 1 Take 4_2026-07-31_controls.png`
- `Day 3 Test 1 Take 5_2026-07-31_controls.png`

#### E. Occupancy Subfolder (`occupancy/`)
- `Day 3 test 1 Take 1_2026-07-31_occupancy.png`
- `Day 3 Test 1 Take 2_2026-07-31_occupancy.png`
- `Day 3 Test 1 Take 4_2026-07-31_occupancy.png`
- `Day 3 Test 1 Take 5_2026-07-31_occupancy.png`
