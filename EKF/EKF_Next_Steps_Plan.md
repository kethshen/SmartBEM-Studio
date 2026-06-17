# EKF — Next Steps Plan

This document maps the concrete next steps for the EKF development,
structured around three available data sources and four implementation phases.

---

## 0. Data Sources Available — A Comparison

| Property | Kaggle (current) | ROBOD (new) | Your Lab AHU (own data) |
| :--- | :--- | :--- | :--- |
| **Columns** | Temp × 4, CO₂ × 1, Light, Sound, PIR, Occupancy count | Temp, CO₂, Humidity, Supply Air Temp, FCU Fan Speed, Supply Air Pressure, Outdoor Temp, Outdoor CO₂, Outdoor Humidity, Occupancy count | Temp, CO₂, Humidity (zone + supply + outdoor + return), Flow (supply) |
| **Humidity** | ❌ Not available | ✅ `indoor_relative_humidity [%]` | ✅ Full |
| **Supply air temp** | ❌ (was hardcoded to 16°C) | ✅ `supply_air_temperature [Celsius]` | ✅ Real sensor |
| **Outdoor conditions** | Only T_o from EPW | ✅ `dry_bulb_temp`, `outdoor_co2`, `outdoor_relative_humidity` | ✅ Real sensors |
| **Mass flow proxy** | ❌ (was hardcoded M_SA=0.3) | ⚠️ `fcu_fan_speed [Hz]` + `supply_air_pressure [Pa]` (can derive) | ✅ Direct flow sensor |
| **Occupancy ground truth** | ✅ Count (0–3) | ✅ Count (0–38 in lecture rooms) | ❌ Manual counting only |
| **Rows / duration** | ~10,000 rows (~3 months) | 8,352 rows per room / 5-min interval / ~29 days each | Short (30-min sessions) |
| **AHU control** | Unknown generic room | FCU-controlled (tropical Singapore) | Your lab AHU — directly controllable |
| **Best use for EKF** | Proof of concept (done) | Full 10-state EKF validation on real AHU data | Real-time streaming + own ground-truth dataset creation |

---

## Phase 1 — Restore the Full 10-State EKF Using ROBOD

**Goal:** Replace the 8-state proof-of-concept with the proper 10-state system
the advisor designed, using ROBOD as validation data since it has all the columns.

### 1.1 What ROBOD gives us that Kaggle did not

| EKF Input / State | ROBOD Column | Notes |
| :--- | :--- | :--- |
| $T_z$ | `air_temperature [Celsius]` | Zone temperature ✅ |
| $\omega_z$ | `indoor_relative_humidity [%]` | Convert RH → humidity ratio using $\omega = 0.622 \cdot \frac{RH \cdot P_{sat}}{P - RH \cdot P_{sat}}$ |
| $c_z$ | `indoor_co2 [ppm]` | Zone CO₂ ✅ |
| $T_o$ | `dry_bulb_temp [Celsius]` | Real outdoor — no EPW hack needed ✅ |
| $c_o$ | `outdoor_co2 [ppm]` | Real outdoor CO₂ — no more hardcoded 420 ✅ |
| $\omega_o$ | `outdoor_relative_humidity [%]` | Convert to humidity ratio |
| $T_{sa}$ | `supply_air_temperature [Celsius]` | Real supply air ✅ |
| $m_{sa}$ proxy | `fcu_fan_speed [Hz]` + `supply_air_pressure [Pa]` | Derive: $\dot{m}_{sa} \approx k \cdot \text{fan\_speed}$ (calibrate k from pressure and duct area) |
| Occupancy ground truth | `occupant_count [number]` | Compare vs EKF-estimated N |

> Note: Supply air humidity $\omega_{sa}$ and outdoor humidity need conversion.
> Supply air CO₂ $c_{sa}$ can be approximated as outdoor CO₂ when fresh-air mode
> is on (reasonable for a well-ventilated FCU system in Singapore).

### 1.2 Code changes required in `Real_EKF.py`

- [ ] Add humidity ratio state $\omega_z$ (index 8) back to state vector → N_STATES = 10
- [ ] Add $\beta_e$ parameter (index 5) back
- [ ] Write `load_robod()` data loader function
- [ ] Write RH → humidity ratio converter
- [ ] Derive $m_{sa}$ from FCU fan speed column
- [ ] Update `predict_state()` to include humidity ODE
- [ ] Update `jacobian_F()` to include rows 8 (humidity) — add $\beta_o$, $\beta_s$, $\beta_e$ partials
- [ ] Update measurement vector $Z$ to 3×1: $[T_z, \omega_z, c_z]$
- [ ] Update $H$ matrix to 3×10
- [ ] Update $R$ matrix to 3×3
- [ ] Re-tune $Q$ and $P_0$ for the 10-state system

---

## Phase 2 — Real-Time EKF on Lab AHU Data

**Goal:** Connect the EKF to live sensor data streaming from your lab SCADA system
via MQTT, so the EKF runs in real time as the AHU operates.

### 2.1 What your lab setup provides (from the SCADA diagram)

From the SCADA panel you showed, the sensors cover:

| SCADA Location | Variables | EKF Role |
| :--- | :--- | :--- |
| Outside Air inlet | $T$, $\omega$, CO₂ | $T_o$, $\omega_o$, $c_o$ — disturbance inputs |
| Mix Sensor (after damper) | $T$, $\omega$, Pressure | Mix air conditions |
| Heater Sensor (before blower) | $T$, $\omega$, Pressure | Supply air conditions |
| NORTH ZONE (facility) | $T$, $\omega$, CO₂ | $T_z$, $\omega_z$, $c_z$ — measured states |
| Return Air | $T$, $\omega$, CO₂ | Validation / well-mixed check |
| Flow sensor (supply duct) | $m_{sa}$ [kg/s] | Primary control input |

### 2.2 MQTT data pipeline

```
Lab sensors (ESP32) → MQTT broker → Python MQTT client → EKF loop → Results
```

- Subscribe to MQTT topics for each sensor channel
- Buffer incoming readings at a fixed timestep (e.g., $\Delta t = 30$ s or 60 s)
- Feed buffered values as inputs to the EKF at each step
- Log all inputs + EKF outputs to a CSV file for later analysis

### 2.3 Key code to write

- [ ] `mqtt_listener.py` — subscribes to MQTT, buffers and synchronises multi-sensor readings
- [ ] Modify `Real_EKF.py` to accept a "streaming" data source (not just a pre-loaded DataFrame)
- [ ] CSV logger that writes every EKF step to disk (timestamp, inputs, X_est, P_diag)

---

## Phase 3 — Own Dataset Creation (Controlled Experiment)

**Goal:** Run controlled 30-minute sessions with known occupants to create a
dataset where you know the ground truth, and validate your EKF against it.

### 3.1 Experimental Protocol

| Session | Occupants | Duration | What it tests |
| :--- | :--- | :--- | :--- |
| **A** — Baseline (empty room) | 0 | 30 min | Estimate $\alpha_o, \beta_o$ (envelope + infiltration) with no internal load |
| **B** — Step change | 0 → 3 persons enter at 10 min | 30 min | EKF should detect rise in $\alpha_e, \gamma_e$ at the step change |
| **C** — Full occupancy | 3 persons throughout | 30 min | Steady-state parameter estimation |
| **D** — AHU setpoint change | 3 persons, change supply air temp mid-session | 30 min | Test $\alpha_s$, $\beta_s$ sensitivity |

### 3.2 What to record

At every timestep ($\Delta t$ = 30 s or 60 s), log:
- All SCADA channels (already in MQTT stream)
- Manual occupancy count (person entering/leaving logged by timestamp)
- AHU setpoint commands issued

### 3.3 Validation strategy

After each session, run the EKF offline on the logged data and check:
- Does $N_{est} = \gamma_e / (g_{CO_2} \cdot \beta_s)$ match your manual occupancy log?
- Does $T_z$ EKF track match $T_z$ measured?
- Do $\alpha_e, \gamma_e$ rise/fall in sync with known occupancy changes?

---

## Phase 4 — Analysis and Thesis Results

**Goal:** Produce the plots, metrics, and analysis needed for the final thesis.

### 4.1 Metrics to compute

| Metric | What it shows |
| :--- | :--- |
| RMSE of $T_z$ EKF vs measured | Tracking accuracy |
| RMSE of $c_z$ EKF vs measured | CO₂ tracking accuracy |
| RMSE of $N_{est}$ vs ground truth occupancy | Occupancy estimation accuracy |
| $\hat{UA}$ convergence time | How long EKF takes to stabilise the envelope estimate |
| Parameter steady-state values vs. physical estimates | Sanity check (e.g., $C_s = c_{pa}/\alpha_s$ should be in the expected range for the room volume) |

### 4.2 Plots to produce (extending current 12)

- [ ] Parameter convergence plot: all 7 parameters over time showing settlement
- [ ] Innovation sequence ($y_k = Z_k - H X_{pred,k}$) — should be white (no pattern) if EKF is tuned properly
- [ ] Occupancy recovery comparison: session B step-change clearly shown
- [ ] ROBOD vs Kaggle vs Lab AHU parameter estimate comparison (same EKF, three datasets)

---

## Recommended Order of Work

```
Week 1:  Phase 1 — 10-state EKF code + ROBOD loader
Week 2:  Phase 1 — Test and validate on ROBOD data, fix bugs
Week 3:  Phase 2 — MQTT listener + real-time EKF connection
Week 4:  Phase 3 — Run experimental sessions A, B, C, D in lab
Week 5:  Phase 4 — Analysis, metrics, thesis plots
```

---

## Dataset Decision Summary

| Dataset | Use it for |
| :--- | :--- |
| **Kaggle** | Keep as "Phase 0" baseline. Already done. Shows EKF works conceptually. |
| **ROBOD Room 3 or 4** (office space) | Primary validation for full 10-state EKF. Closest to your lab room type. Has all EKF inputs. |
| **Your lab AHU data** | Real-time streaming demo + your own controlled experiment. This is your thesis highlight — it is data no one else has. |
