# SmartBEM EKF — Deep Diagnosis & Prioritized Fix Plan
**Deadline: Tomorrow night. All three workspaces: `robod_ekf`, `test_rig_ekf`, `ep_testdata_ekf`.**

---

## Part I — What Is Actually Wrong: Root Cause Analysis

I've examined every plot, every line of code, and cross-referenced the academic literature. The problems are **not random noise** and they are **not EKF bugs**. They are four deep, interconnected fundamental issues. Understanding this is crucial before touching a single line of code.

---

### Root Cause 1: Structural Non-Identifiability of the 10-State Augmented System

**This is the biggest issue. It explains nearly everything you are seeing.**

The model you have is:

```
dTz/dt = α_o·(To - Tz)  +  α_s·m_sa·(Tsa - Tz)  +  α_e
dcz/dt = β_o·(co - cz)  +  β_s·m_sa·(csa - cz)  +  γ_e
```

The problem: **You have too many parameters chasing too few observations.**

- You have 7 unknown parameters: `α_o, α_s, α_e, β_o, β_s, β_e, γ_e`
- You have only 3 measurements: `Tz, wz, cz`
- But critically: **`α_o` and `β_o` cannot be simultaneously identified from the same output channel.** The term `α_o·(To - Tz)` and `α_s·m_sa·(Tsa - Tz)` contribute to the same derivative `dTz/dt`. When `To ≈ Tsa` (supply air near ambient, common in mixed-mode), those two terms become **linearly dependent**. The EKF's Fisher Information Matrix becomes singular → parameters cannot converge.

**Observable evidence in your plots:**
- `α_o` (purple panel): bouncing between +0.004 and -0.0004 at high frequency → **sign-flipping between two equally valid optima** (identifiability degeneracy)
- `Cs` plot: starts in band at t=0, then immediately escapes to ~3600 kJ/K and **never returns** → initial conditions lie in band but parameters drift to an unidentifiable manifold
- `UA` plot: catastrophic spiky oscillation between 0 and 600+ W/K throughout all 700 hours → **total non-convergence**. The optimizer (EKF) keeps trying random walk exploration across the entire feasible set.

**Mathematical proof:** The identifiability matrix (empirical observability Gramian):
```
W_o = ∫ [∂h/∂θ]ᵀ [∂h/∂θ] dt
```
is rank-deficient when `(To - Tz)` and `m_sa·(Tsa - Tz)` are correlated. This is almost always true for a well-functioning HVAC system (because the AHU tries to maintain setpoint, so both drive temperatures toward the same target).

---

### Root Cause 2: The Euler Forward Integration is Numerically Unstable at DT=300s

**Your integration scheme:**
```python
X_pred = X + f(X, U) * DT    # Euler forward, DT = 300 seconds
F_k = I + J_F * DT            # First-order state transition matrix
```

**Why this explodes for ROBOD:** The dominant time constant for a building thermal circuit is approximately:
```
τ = Cs / (UA + m_sa·c_pa) ≈ 1,500,000 / (250 + 0.01×1006×1) ≈ 5,780 seconds ≈ 96 minutes
```

The Euler stability condition requires:
```
DT < 2 × τ_min
```

For the **humidity and CO2 subsystems**, the time constant can be as small as:
```
τ_c = M / (m_sa·β_s_true) ≈ 495 / (0.01/495) ≈ very small
```

Actually the real problem is the **product terms**: `α_s × m_sa × DT` must be < 1 for stability. At DT=300 and α_s ≈ 0.0003 [1/(kg·s)], m_sa ≈ 0.1 kg/s:
```
α_s × m_sa × DT = 0.0003 × 0.1 × 300 = 0.009   ← This is fine
```

BUT for the **UA plot oscillations**: The EKF prediction step computes `F_k = I + J × DT`. When the state has slow convergence and `J[Tz, Tz] = -(α_o + α_s·m_sa)`, the eigenvalues of F_k need to be < 1. If parameter estimates overshoot:
```
F_k[Tz, Tz] = 1 - (α_o_est + α_s_est · m_sa) × DT
```
At α_o_est = 0.004 (seen in plots), m_sa = 0.1, DT = 300:
```
F_k[Tz, Tz] = 1 - (0.004 + 0.0003×0.1) × 300 = 1 - 1.209 = -0.209
```
**This is negative eigenvalue territory → oscillatory instability → that is exactly the UA spiking you see.**

---

### Root Cause 3: Incorrect Mass Flow Rate Scaling (`FCU_FLOW_SCALE = 0.01`)

**The `FCU_FLOW_SCALE = 0.01 [kg/s per Hz]` is a completely uncalibrated guess.**

Looking at the ROBOD data: fan speeds are between 0 and 50+ Hz. With scale=0.01, that's 0 to 0.5 kg/s supply air mass flow. For a 413 m³ room:
```
Air changes per hour = (0.5 kg/s × 3600) / (413.2 m³ × 1.2 kg/m³) ≈ 3.6 ACH
```
That's reasonable. But the filter is simultaneously trying to estimate `α_s = c_pa/Cs` and the actual mass flow is `m_sa_true = fan_hz × FCU_FLOW_SCALE_true`. If `FCU_FLOW_SCALE_true ≠ 0.01`, then:
```
α_s_estimated = c_pa / (Cs_true × FCU_FLOW_SCALE_true / FCU_FLOW_SCALE_assumed)
```
**The estimated α_s absorbs the flow calibration error.** This causes Cs to be wrong by the same factor as the flow scale error. The EKF can't simultaneously identify both — they are **perfectly coupled** (cannot be separated from each other without ground-truth flow measurements).

---

### Root Cause 4: Measurement Equation for CO2 is Wrong

**The CO2 dynamics equation you're using:**
```python
dcz = β_o × (co - cz) + β_s × m_sa × (csa - cz) + γ_e
```

There's a critical modelling error here: **`β_o` and `β_s` are coupled to the CO2 equation but they appear in the humidity equation too, with the same coefficient.** The physical reality:
```
β_o = ṁ_inf / M          [outdoor air infiltration rate / zone air mass]
β_s = 1 / M              [1 / zone air mass]  (for the supply term)
```

But `ṁ_inf / M` for humidity and CO2 should use **the same** `ṁ_inf` and `M`. They are NOT separate parameters. Your model treats `β_o_temp`, `β_o_CO2` as the same variable — which is fine. But you have `β_s` also scaling as `1/M` — **which means `β_s = 1/M` should be fixed to the KNOWN room air mass, not estimated.**

Further, `csa ≈ co` (outdoor CO2 = supply CO2) is your assumption. But the ROBOD AHU has **heat recovery and CO2 control** — the actual supply CO2 concentration is reduced by recirculation and filtration. Using `csa = co` systematically misrepresents the supply CO2, which biases `γ_e` to compensate for the model error → `γ_e` is not an occupancy signal, it is **model error absorption**.

---

## Part II — What Good Results Should Look Like

Before coding, let's define success criteria:

| Metric | Bad (current) | Good (target) |
|--------|--------------|---------------|
| Tz tracking RMSE | >0.5°C | <0.15°C |
| CO2 tracking RMSE | >50 ppm | <20 ppm |
| UA convergence | Oscillating 0–600 W/K | Steady ±10% of 250 W/K |
| Cs convergence | Fixed at wrong value | Within [1000–2250] kJ/K band |
| α_o | Oscillating ±0.004 | Settled <0.001 |

---

## Part III — Prioritized Fixes (Ranked by Impact/Effort Ratio)

Ordered by how much improvement you get for how little coding effort. **Do these in order.**

---

### FIX 1 (HIGHEST PRIORITY — Do This First) — Fix Structural Non-Identifiability: Fix Known Parameters, Estimate Only Identifiable Ones

**Core idea:** Stop estimating parameters that are physically knowable. Only estimate what is **genuinely unknown and observable**.

**What to fix vs. estimate:**

| Parameter              | Action                      | Reasoning                                                                                                                                  |
| ---------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `M` (zone air mass)    | **FIX** to `ρ_air × V_room` | Exactly calculable from room dimensions                                                                                                    |
| `β_s = 1/M`            | **FIX** (derived from M)    | Not independent — it's 1/M                                                                                                                 |
| `β_o = ṁ_inf/M`        | **ESTIMATE** (slow drift)   | This is the only genuinely unknown humidity/CO2 exchange                                                                                   |
| `c_pa` (specific heat) | **FIX** to 1006 J/(kg·K)    | Physical constant                                                                                                                          |
| `α_s = c_pa/Cs`        | **ESTIMATE**                | But ONLY via sigmoid mapping to keep within [α_s_min, α_s_max]                                                                             |
| `α_o = UA/Cs`          | **ESTIMATE**                | But tightly coupled with α_s — consider fixing ratio                                                                                       |
| `γ_e`                  | **ESTIMATE**                | CO2 generation from occupants — this is the main target                                                                                    |
| `α_e`                  | **CONSIDER REMOVING**       | This is a bias absorber — if model is correct, it should be zero. Keeping it allows the filter to "cheat" and not converge real parameters |
| `β_e`                  | **CONSIDER REMOVING**       | Same — humidity bias absorber                                                                                                              |

**Reduced state vector (7 states instead of 10):**
```
X = [α_o, α_s, β_o, γ_e, Tz, wz, cz]
```
This **eliminates the non-identifiable `α_e`, `β_e`, `β_s`** (fix β_s to 1/M), cutting the parameter space by 3. The filter now has a fighting chance.

**Code change required in `Real_EKF_ROBOD.py`:**
```python
# FIX these — do NOT estimate them
M_fixed = spec["mass"]                    # 495.8 kg for Room 3
bs_fixed = 1.0 / M_fixed                  # β_s is NOT a state anymore

# Modified dynamics:
dTz = ao*(To-Tz) + as_*msa*(Tsa-Tz)      # removed ae bias
dwz = bo*(wo-wz) + bs_fixed*msa*(wsa-wz) # bs_fixed, removed be bias
dcz = bo*(co-cz) + bs_fixed*msa*(csa-cz) + ge  # bs_fixed
```

---

### FIX 2 (HIGH PRIORITY) — Switch to 4th-Order Runge-Kutta Integration (RK4)

**Replace Euler forward with RK4.** This costs essentially nothing computationally and eliminates the numerical instability at large DT.

```python
def rk4_step(X, U, dt, dynamics_fn):
    k1 = dynamics_fn(X, U)
    k2 = dynamics_fn(X + 0.5*dt*k1, U)
    k3 = dynamics_fn(X + 0.5*dt*k2, U)
    k4 = dynamics_fn(X + dt*k3, U)
    return X + (dt/6.0) * (k1 + 2*k2 + 2*k3 + k4)
```

**Why this matters:** RK4 is stable for eigenvalues up to `|λ| × DT ≤ 2.79` vs Euler's limit of `2.0`. For DT=300s, this directly prevents the `F_k[Tz,Tz] < 0` condition we calculated above. The UA oscillations should dampen significantly from this change alone.

**Note:** The state transition matrix `F_k` used for covariance propagation must still be calculated analytically (the linearized Jacobian approach is fine for `P` propagation). Only replace `X_pred` update with RK4.

---

### FIX 3 (HIGH PRIORITY) — Correct the CO2 Supply Air Assumption

**Replace `csa = co` with a more physically realistic model.**

ROBOD data has AHU with partial recirculation. A reasonable first-order fix:
```python
# Instead of: csa = co  (wrong — implies 100% fresh air supply)
# Use recirculation blending model:
recirculation_fraction = 0.5  # 50% recirculated indoor air, 50% fresh
csa = recirculation_fraction * cz + (1.0 - recirculation_fraction) * co
```

This can be refined if ROBOD documentation specifies the AHU recirculation ratio. This directly affects `γ_e` accuracy.

Even better: **check if the ROBOD CSV has a `supply_co2` column** — if it does, use it directly. Check with:
```python
print([c for c in df.columns if 'co2' in c.lower()])
```

---

### FIX 4 (MEDIUM PRIORITY) — Innovation-Based Adaptive R (Sage-Husa Style, Simplified)

**Online adaptation of measurement noise covariance R using the actual innovation sequence.**

The idea (Mehra/Sage-Husa, simplified stable version with forgetting factor):
```python
# After computing innovation y_k and S_k:
alpha_forget = 0.98   # forgetting factor (0.95-0.99)
N_window = 50         # effective window = 1/(1-alpha_forget) = 50 steps

# Update R estimate online:
R_adaptive = alpha_forget * R_adaptive + (1 - alpha_forget) * (np.outer(y_k, y_k) - H @ P_pred @ H.T)
# Safety: ensure positive definiteness
R_adaptive = np.maximum(R_adaptive, np.diag([0.001, 1e-7, 0.1]))  # lower bounds
```

**Why this helps:** When your model has structural errors (which it does), the true innovation covariance changes with operating conditions. Fixed R forces the filter to either over-trust measurements (causing spikes when measurement jumps) or under-trust them (causing slow sluggish tracking). Adaptive R self-calibrates to the actual data statistics.

---

### FIX 5 (MEDIUM PRIORITY) — Sigmoid-Based Parameter Mapping for ALL Physical Parameters

**You applied this to `α_s` but not `α_o` or `β_o`.** Every physically bounded parameter should use sigmoid mapping:

```python
# Replace raw parameter states with unconstrained internal variables:
# X_raw = [xi_ao, xi_as, xi_bo, xi_ge, Tz, wz, cz]
# 
# Physical parameters recovered by sigmoid:
def sigmoid_map(xi, lo, hi):
    return lo + (hi - lo) / (1 + np.exp(-xi))

def sigmoid_jac(xi, lo, hi):
    s = sigmoid_map(xi, lo, hi)
    return (s - lo) * (hi - s) / (hi - lo)

# Bounds for ROBOD Room 3:
ao_bounds = (UA_expected*0.3/Cs_expected, UA_expected*3.0/Cs_expected)  # UA: 75-750 W/K range
as_bounds = (c_pa/Cs_max, c_pa/Cs_min)
bo_bounds = (1e-6, 1e-2)   # infiltration rate [1/s]
ge_bounds = (0.0, 0.5)     # CO2 generation [ppm·kg/(s)] clipped positive
```

**How this eliminates oscillations:** The Jacobian chain rule gives:
```
∂f/∂xi = (∂f/∂θ) × (∂θ/∂xi)
```
where `∂θ/∂xi = sigmoid_jac(xi) > 0` always. This means the EKF never sees a discontinuous state space — the covariance matrix P remains consistent at all times.

---

### FIX 6 (MEDIUM PRIORITY) — Dual EKF Architecture Instead of Joint Augmented EKF

**Instead of one 10-state EKF doing everything, use two separate smaller EKFs:**

**EKF_states:** Estimates `[Tz, wz, cz]` using current best parameter estimates → **3 states**, simple linear system, well-conditioned.

**EKF_params:** Estimates `[α_o, α_s, β_o, γ_e]` using current state estimates → **4 states**, slower timescale.

```
Time Step k:
  1. EKF_params uses X_states[k-1] to update θ_params[k]
  2. EKF_states uses θ_params[k] as known inputs to update X_states[k]
  3. Repeat
```

**Why this is better:**
- Each filter works in a much lower-dimensional space → better conditioned Jacobians
- Parameter filter can run at a slower update rate (e.g., every 5 steps) → prevents parameter tracking responding to state noise
- State filter is essentially linear given fixed parameters → nearly exact Kalman gain

**This is the architecture used in NASA technical literature and recommended by Wan & Merwe (2001).**

---

### FIX 7 (LOWER PRIORITY, but Important for Test Rig) — Upgrade EKF to UKF (Unscented Kalman Filter)

**For the test rig and EnergyPlus datasets** where the nonlinearity is most pronounced (small room, large parameter sensitivity), upgrading to UKF gives 2nd-order accuracy in nonlinear propagation vs EKF's 1st-order.

**UKF procedure replaces Jacobian with sigma points:**
```
1. Generate 2n+1 sigma points from (X, P) using Cholesky decomposition
2. Propagate EACH sigma point through the nonlinear f(x)
3. Recover predicted mean and covariance from propagated points
4. Same measurement update as EKF (no Jacobian needed)
```

**The key advantage for your system:** The product terms like `α_s × m_sa × (Tsa - Tz)` are 3rd-order in the state (product of 3 state-dependent quantities). EKF linearizes away the second and third order terms. UKF captures them correctly.

**Implementation complexity:** Moderate (~50 extra lines), but `filterpy` library implements it trivially:
```python
from filterpy.kalman import UnscentedKalmanFilter
```

---

### FIX 8 (LOWER PRIORITY) — Moving Horizon Estimation (MHE) for Parameter Identification

**If Dual EKF still doesn't converge:** Use a batch optimization over a sliding window of data instead of recursive filtering.

```
At each step k, solve:
min_{θ}  Σ_{t=k-N}^{k} ||y_t - h(x_t(θ))||²_R  +  ||θ - θ_prior||²_Λ
s.t.     θ_min ≤ θ ≤ θ_max
         model dynamics satisfied (implicit constraints)
```

This is the gold standard for parameter estimation because it:
- Uses the entire window of data, not just one step
- Can enforce physical constraints natively
- Handles measurement outliers robustly (use Huber loss instead of L2)

**Downside:** Computationally expensive. For an N=100 window with 10 states, this is a 1000-variable optimization problem. Use `scipy.optimize.minimize` with `method='SLSQP'` for constrained optimization. With 5-min data, N=100 = 8 hours of window. This is tractable.

---

## Part IV — For Each Dataset: Specific Immediate Actions

### For `robod_ekf` (ROBOD Room 3 — 700 hours)

**Immediate fix priorities (order of implementation):**

1. **FIX 1:** Reduce state vector from 10 to 7 (fix `β_s=1/M`, remove `α_e`, `β_e`)
2. **FIX 2:** Replace Euler with RK4
3. **FIX 3:** Check ROBOD CSV for actual `supply_co2` column; if absent, use recirculation model
4. **FIX 5:** Apply sigmoid mapping to `α_o` (currently unclipped, causing sign flips)
5. **FIX 4:** Add adaptive R using innovation sequence

**Expected improvement:** The UA oscillation should stop after Fixes 1+2+5. The CO2/occupancy estimation should improve with Fix 3. Overall: from completely non-converged to physically plausible within 50 hours of data.

---

### For `test_rig_ekf` (Test Chamber — ~168 hours, 5.832 m³)

The test rig has different dominant problems:

1. **`β_s` is less problematic** because you have a very small room where `M = 7 kg` is almost exactly known from `ρ × V`. **Fix `β_s = 1/7 kg`**.
2. **The main issue here is lack of parameter excitation**: in a sealed chamber, `m_sa = 0` almost always (no HVAC). This means `α_s × m_sa = 0` → `α_s` is completely **unobservable**. You cannot estimate `α_s` from test rig data without HVAC running.
3. **Fix for test rig:** Estimate only `α_o` (= UA/Cs) and `Cs` indirectly through temperature response. Use `α_s × m_sa` as known input (zero when no fan, small positive during test periods).
4. **RK4 is critical here** too — at the test rig's DT and small time constants, Euler instability bites hard.

---

### For `ep_testdata_ekf` (EnergyPlus Synthetic — 1-minute DT)

EnergyPlus gives you **synthetic ground truth**. This is your most valuable diagnostic tool.

1. **Check the Tz RMSE directly:** If EKF Tz tracking error is >0.05°C against EnergyPlus synthetic data, the model equations themselves are wrong — not the tuning.
2. **EnergyPlus provides exact supply air conditions** (temperature, humidity, flow rate) — **no assumptions needed**. This removes Root Cause 3 entirely. Use EnergyPlus outputs directly as inputs `Tsa, m_sa, csa`.
3. **At DT=60s**, the Euler stability issue is less severe (DT is 5x smaller than ROBOD). But RK4 should still be used for correctness.
4. **Use EnergyPlus synthetic data to validate your EKF formulation FIRST**, then apply to real data. If it doesn't work on synthetic data with known ground truth, the model structure itself needs fixing.

---

## Part V — Priority Decision Tree for Tomorrow

```
START HERE:
  └─► Does EKF track Tz within 0.2°C on EnergyPlus (synthetic) data?
        ├─ NO → Fix model structure (Root Causes 1, 3, 4)
        │         Implement Fix 1 + Fix 2 + Fix 3 on ep_testdata_ekf FIRST
        │         Validate Tz RMSE < 0.2°C
        │         Then carry validated structure to robod_ekf
        └─ YES → Problem is ROBOD-specific (noisy data, wrong flow scale, identifiability)
                  Go straight to Fix 5 + Fix 6 (sigmoid + dual EKF)
```

---

## Part VI — Implementation Timeline (Tomorrow)

| Time Block | Task | Expected Result |
|------------|------|-----------------|
| **Hour 1-2** | Implement Fix 1 (reduce states) + Fix 2 (RK4) in ONE file (`ep_testdata_ekf`) | Clean convergence on synthetic data |
| **Hour 3** | Validate ep_testdata_ekf plots — check Tz RMSE, UA convergence | Model structure confirmed correct |
| **Hour 4-5** | Port Fix 1 + Fix 2 to `robod_ekf`, add Fix 5 (sigmoid all params) | Eliminate UA oscillations, Cs drift |
| **Hour 6** | Check ROBOD CSV for `supply_co2`, implement Fix 3 if needed | CO2/occupancy accuracy improves |
| **Hour 7** | Add Fix 4 (adaptive R) to robod_ekf | RMSE further reduces |
| **Hour 8** | Apply all fixes to `test_rig_ekf` | Consistent across all 3 datasets |
| **Hour 9-10** | Generate all final plots, review visually | Final results for submission |
| **Buffer** | Fix 6 (Dual EKF) if any single dataset still diverges | Last resort |

---

## Part VII — Key Academic References

- **Structural Identifiability:** Ljung (1999), *System Identification: Theory for the User*, Ch.4 — identifiability conditions for RC networks
- **Dual EKF Architecture:** Wan & Merwe (2001), "The Unscented Kalman Filter," in *Kalman Filtering and Neural Networks*
- **Adaptive Noise Estimation:** Mehra (1972), *IEEE Trans. Autom. Control* — innovation-based covariance matching; Sage & Husa (1969) — recursive MAP noise estimation
- **Building Thermal Identification:** Ghiaus (2006), *Energy and Buildings* — RC network parameter identifiability for buildings; recommends fixing room air mass M
- **UKF vs EKF for buildings:** Bacher & Madsen (2011), *Energy and Buildings* — grey-box model identification using UKF shows 40-60% improvement over EKF for nonlinear building thermal models

---

> [!IMPORTANT]
> The single highest-impact change you can make: **Reduce the state vector from 10 to 7 states by fixing `β_s = 1/M` and removing `α_e`, `β_e`.** This alone will make the identifiability problem tractable and likely resolve most of the UA oscillations and Cs drift. Do this first.

> [!WARNING]
> Do NOT keep tweaking Q and R values as a primary fix. Bayesian optimization of Q/R cannot fix a **structurally non-identifiable model**. Tuning Q and R on a broken model is equivalent to adjusting the volume of a radio that isn't tuned to a station — no amount of adjustment will produce music.

> [!TIP]
> The EnergyPlus synthetic dataset is your secret weapon. Use it as a validation testbed for model structure changes BEFORE applying them to noisy real data. If the model can't track its own ground truth data, no amount of filtering will fix it on real sensor data.
