# Analysis of Dual EKF Occupancy Estimation Issues

## Problem Statement
In the `robod_dual_ekf.py` implementation, the estimated occupancy ($N_{occ}$) is frequently zero or significantly underestimated compared to the ground truth in the ROBOD dataset.

## Deep Analysis & Findings

### 1. Mathematical & Physical Issues

#### A. Questionable Supply Air CO2 Assumption
In lines 193 and 238:
```python
csa = 0.5 * cz_m + 0.5 * co
# and inside the loop
csa_k = 0.5 * S[2] + 0.5 * co[k]
```
The model assumes that the supply air CO2 concentration ($c_{sa}$) is the arithmetic mean of the indoor CO2 ($S[2]$) and outdoor CO2 ($co$). 
- **Issue:** This is a strong and likely inaccurate assumption for the ROBOD dataset. If the actual HVAC system provides air with a different mixing ratio (e.g., more outdoor air), the model will miscalculate the CO2 removal rate.
- **Impact:** If the model overestimates the "cleaning" effect of the supply air, it will incorrectly attribute the measured CO2 levels to a lower generation rate ($g_e$), leading to underestimated occupancy.

#### B. Non-Standard Innovation for $g_e$
In lines 262 and 269:
```python
cz_signmax = cz_vals[np.argmax(np.abs(cz_vals))]
# ...
innov_batch = np.array([..., cz_signmax])
```
The filter uses the value with the maximum absolute error within the update window rather than the mean innovation or the most recent error.
- **Issue:** This is not a standard EKF approach. Picking the "most extreme" error can introduce significant bias and instability, especially if there are outliers in the CO2 sensor data.
- **Impact:** Erratic updates to $g_e$ that may push the parameter toward the lower bound (0).

#### C. Parameter "Locking" via Sigmoid Gradient
The parameters are mapped using a sigmoid function: $\theta = lo + (hi - lo) \cdot \text{sigmoid}(\xi)$.
- **Issue:** The update for $\xi$ is proportional to the Jacobian $H_p$, which includes the sigmoid derivative $\text{sig\_jac}(\xi)$. As $\xi$ becomes very negative (mapping $\theta$ towards the lower bound $lo$), $\text{sig\_jac}(\xi) \to 0$.
- **Impact:** If the filter pushes $g_e$ toward 0, the gradient vanishes. Once the parameter "hits" the lower bound, the filter becomes unresponsive, "locking" the occupancy at zero even if the actual occupancy increases.

#### D. Parameter Identifiability (Tied Innovations)
In line 256:
```python
innov_5 = np.array([y_3[0], y_3[0], y_3[0], y_3[1], cz_err])
```
The parameters $a_o$ (envelope loss), $a_s$ (supply capacity), and $a_e$ (thermal bias) are all updated using the exact same innovation signal (`y_3[0]`, the temperature error).
- **Issue:** This leads to poor identifiability. The filter may struggle to distinguish between the effects of these three parameters, potentially leading to unstable convergence of $a_o$ and $a_s$, which in turn affects the overall state estimation.

### 2. Suggested Fixes

#### Fix 1: Improve Supply Air Modeling
Instead of assuming $c_{sa} = 0.5(c_z + c_o)$, try:
- Using a fixed mixing ratio (e.g., $c_{sa} = \alpha \cdot c_o + (1-\alpha) \cdot c_z$ where $\alpha$ is a known or estimated fresh air fraction).
- Treating $c_{sa}$ as a measured input if the dataset provides it.
- Adding the mixing ratio $\alpha$ as a parameter to be estimated by the Dual EKF.

#### Fix 2: Standardize Innovation Calculation
Replace `cz_signmax` with the mean innovation over the window:
```python
# Suggested change
cz_mean_innov = innov_arr[:, 4].mean()
innov_batch[4] = cz_mean_innov
```

#### Fix 3: Prevent Gradient Vanishing
To avoid parameter locking:
- **Soft Bounds:** Use a linear mapping for parameters that need to be more responsive.
- **Gradient Clipping/Floor:** Implement a minimum floor for the sigmoid derivative in `sig_jac` to ensure the filter can always move away from the bounds.
- **Reset Logic:** Implement a mechanism to "kick" the parameter back into the active gradient region if the innovation remains consistently high while the parameter is at the bound.

#### Fix 4: Diversify Innovation Sources
If possible, use different sensor signals or time-lagged innovations to separate the effects of $a_o, a_s,$ and $a_e$. Alternatively, fix one or two of these parameters to nominal values based on the `ROOM_SPECS` to improve the stability of the remaining estimated parameters.

#### Fix 5: Verify CO2 Generation Constant
Double-check the value $4.5 / v_{room}$. While $5 \text{ ppm/s}$ per person is a common rule of thumb for standard rooms, the actual generation rate can vary by occupant activity level. Ensure this constant aligns with the specific metadata of the ROBOD dataset.
