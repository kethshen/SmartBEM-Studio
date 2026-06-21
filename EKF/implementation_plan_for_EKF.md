# Real EKF Implementation — Fixes + Real Data Integration

## Goal

Fix the bugs in `Real_EKF.py` and restructure it to work with the **Kaggle Room Occupancy Estimation** dataset + **EPW weather file**, using pseudo-functions for missing inputs.

---

## Bug Fixes in Current `Real_EKF.py`

### Bug 1: $\gamma_e \times N$ double-counting (lines 63, 139, 158)

The true simulation (line 63) and EKF prediction (line 139) both use `+ γe*N`, but $\gamma_e$ already absorbs $N$.
The Jacobian (line 158) uses `F[9,6] = dt*N` instead of `F[9,6] = dt`.

**Fix:** Change prediction to `+ γe` and Jacobian to `F[9,6] = dt`.

### Bug 2: Missing F[9,3] and F[9,4] in Jacobian

CO₂ shares $\beta_o, \beta_s$ with humidity, but the current code omits the CO₂ row's sensitivity to these parameters.

**Fix:** Add:
```python
F[9,3] = dt*(-c + c_o)       # ∂f_c/∂β_o
F[9,4] = dt*m_sa*(-c + c_sa)  # ∂f_c/∂β_s
```

### Bug 3: Naming inconsistency

Current code uses `X_est` and `P` without `_prev`/`_pred`/`_est` suffixes consistently. Should follow the notation from practice demos.

---

## Data Availability Analysis

### Kaggle Occupancy Dataset

- **10,129 rows** + header
- Timestep: ~30 seconds (irregular, e.g., 10:49:41 → 10:50:12 = 31s)
- Date range: 2017/12/22 → 2018/01/11

| EKF Variable | Dataset Column | Available? | Notes |
|---|---|---|---|
| $T_z$ (zone temp) | `S1_Temp` – `S4_Temp` | ✅ **REAL** | Average of 4 sensors |
| $\omega_z$ (zone humidity) | — | ❌ **MISSING** | Not in dataset |
| $c_z$ (zone CO₂) | `S5_CO2` | ✅ **REAL** | ppm |
| $N$ (occupancy) | `Room_Occupancy_Count` | ✅ **REAL** | For **validation only** |

### EPW Weather File (Chicago O'Hare TMY3)

| EKF Variable | EPW Column | Available? | Notes |
|---|---|---|---|
| $T_o$ (outdoor temp) | Column 7: Dry Bulb Temp | ✅ **REAL** | °C, hourly resolution |
| $\omega_o$ (outdoor humidity ratio) | — | ⚠️ **COMPUTABLE** | From dew point (col 8) + pressure (col 10) using psychrometric formula |
| $c_o$ (outdoor CO₂) | — | ❌ **MISSING** | Use constant ~420 ppm |

> [!IMPORTANT]
> **Location mismatch:** The Kaggle dataset is from an office/lab (unknown location). The EPW is from Chicago. Since the EPW data provides outdoor conditions for our HVAC model context, this is acceptable for **algorithm testing** — not for real building validation.

### Supply Air (AHU) Data — Entirely Missing

| EKF Variable | Available? | Pseudo Strategy |
|---|---|---|
| $T_{sa}$ (supply air temp) | ❌ | Constant setpoint: 16°C (typical cooling supply) |
| $\omega_{sa}$ (supply air humidity) | ❌ | Constant: 0.008 kg_w/kg_da (typical dehumidified AHU output) |
| $c_{sa}$ (supply air CO₂) | ❌ | Same as outdoor: 420 ppm (AHU draws mostly outdoor air) |
| $m_{sa}$ (supply mass flow) | ❌ | Constant: 0.3 kg/s (typical small office AHU) |

---

## Key Design Decision: Handle Missing $\omega_z$

The dataset has **no humidity sensor**. We have three options:

### Option A: Drop humidity from EKF (Recommended for now)
- Reduce to **8-state EKF**: $[\alpha_o, \alpha_s, \alpha_e, \beta_o, \beta_s, \gamma_e, T_z, c_z]$
- Remove $\beta_e$ (humidity-specific parameter)
- $H$ becomes 2×8, $Z$ = $[T_z, c_z]$
- Simpler, works with real data you have

### Option B: Keep 10-state but use pseudo humidity
- Generate synthetic $\omega_z$ using a simple model
- Keeps full system but validation is weaker for humidity

### Option C: Keep 10-state, set humidity measurement noise very high
- Keep $\omega_z$ in state but set $R_{\omega}$ extremely large
- EKF basically ignores humidity measurements
- Still estimates $\beta_e$ but with no data to correct it

> [!WARNING]
> **Recommendation:** Go with **Option A** for the real-data version. You can keep the 10-state version as a separate simulation-only script. For your FYP, showing that the EKF works on real T and CO₂ data with occupancy validation is strong enough.

---

## Proposed Changes

### File Structure

#### [MODIFY] [Real_EKF.py](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/Real_EKF.py)

Keep this as the **10-state simulation-only** version. Apply the 3 bug fixes only.

#### [NEW] Real_EKF_Data.py

New script that:
1. Loads the Kaggle CSV
2. Loads the EPW file for $T_o$ (interpolated to ~30s timestep)
3. Uses pseudo-functions for supply air inputs
4. Runs an **8-state EKF** (no humidity)
5. Compares estimated $N$ from $\gamma_e$ recovery against `Room_Occupancy_Count`
6. Plots: $T_z$, $c_z$ tracking + parameter convergence + occupancy estimation vs truth

---

### 8-State EKF Design (for Real_EKF_Data.py)

**State vector:**
$$X = [\alpha_o, \alpha_s, \alpha_e, \beta_o, \beta_s, \gamma_e, T_z, c_z]^T$$

**Measurement vector:**
$$Z = [T_{z,meas}, c_{z,meas}]^T$$

**H matrix (2×8):**
```
H = | 0 0 0 0 0 0 1 0 |
    | 0 0 0 0 0 0 0 1 |
```

**F matrix (8×8):**
- Top-left 6×6 = Identity (parameter random walk)
- Row 6 (T_z): entries at columns 0,1,2 and diagonal at 6
- Row 7 (c_z): entries at columns 3,4,5 and diagonal at 7

**Dynamics:**
- Temperature: same as before
- CO₂: same as before but without humidity coupling
- Humidity equation: **dropped entirely**

> [!NOTE]
> Dropping humidity means $\beta_o$ and $\beta_s$ are now estimated purely from CO₂ data. This reduces observability slightly but CO₂ is the strongest signal for infiltration and occupancy anyway.

---

### Data Pipeline

```
┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  Kaggle CSV      │    │  EPW File       │    │  Pseudo Functions │
│                  │    │                 │    │                  │
│  T_z (avg S1-S4) │    │  T_o (dry bulb) │    │  T_sa = 16°C     │
│  c_z (S5_CO2)    │    │  ω_o (computed) │    │  c_sa = 420 ppm  │
│  N (validation)  │    │                 │    │  m_sa = 0.3 kg/s │
└────────┬─────────┘    └────────┬────────┘    └────────┬─────────┘
         │                       │                      │
         └───────────┬───────────┴──────────────────────┘
                     │
              ┌──────▼──────┐
              │  8-State    │
              │  EKF Loop   │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │  Recover N  │
              │  from γ_e   │
              │  Compare to │
              │  truth      │
              └─────────────┘
```

### EPW Time Alignment

- EPW data is **hourly** (8760 rows for a year)
- Kaggle data is **~30 second** intervals
- EPW covers a full TMY year; Kaggle covers Dec 22 → Jan 11
- **Strategy:** Extract the matching date range from EPW, then **linearly interpolate** hourly $T_o$ to the Kaggle timestamps

### Timestep ($\Delta t$)

- Kaggle data is irregular (~30s intervals)
- **Strategy:** Compute $\Delta t$ per row as the difference between consecutive timestamps
- Use variable $\Delta t$ in the forward-Euler step (this is valid for EKF)

---

## Verification Plan

### Automated Tests
1. Run the fixed `Real_EKF.py` (simulation) — all 10 parameters should converge to true values
2. Run `Real_EKF_Data.py` on Kaggle data — check:
   - $T_z$ estimated tracks measured temperature
   - $c_z$ estimated tracks measured CO₂
   - Recovered $N$ correlates with `Room_Occupancy_Count`
   - No NaN or divergence in parameters

### Visual Checks (plots)
- Parameter convergence over time (should stabilize)
- $T_z$ and $c_z$: EKF estimate vs measurement
- Recovered $N$ vs ground truth occupancy (overlay plot)

---

## Open Questions

> [!IMPORTANT]
> **Q1: Option A (8-state, drop humidity) vs Option B/C?**
> I recommend Option A since you have no humidity data. But if you want to show the full 10-state system for the FYP report, we can keep the simulation version as a separate demo.

> [!IMPORTANT]
> **Q2: The `g_CO2_occ = 0.17` value in your code — what units is your CO₂ in?**
> The Kaggle dataset uses ppm. The standard per-person CO₂ generation rate in ppm-based systems is roughly **~27–40 ppm·m³/min/person** depending on activity level. We need to reconcile this with your model's units (which assume kg_CO₂/kg_da). This affects whether $\gamma_e$ recovery gives meaningful occupancy numbers.

> [!IMPORTANT]
> **Q3: Do you want to keep `Real_EKF.py` as-is (simulation) and create a new file `Real_EKF_Data.py` for real data? Or merge everything into one file?**
> I recommend separate files — simulation for validating the algorithm, real-data for your FYP results.
