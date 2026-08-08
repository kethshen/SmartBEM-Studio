# Appendix A: Data Cleaning Formulation for Without-Occupancy Datasets

---

## Overview

To process raw sensor telemetry from the experimental test rig into continuous, noise-free time-series data for model calibration, a 4-stage data cleaning algorithm is applied sequentially to each telemetry channel:

```
[Raw Telemetry] ──> [A.1 Hard Range Masking] ──> [A.2 Rolling 3σ Outlier Filter] ──> [A.3 Linear NaN Interpolation] ──> [A.4 Exponential Moving Average (EMA)] ──> [Cleaned Dataset]
```

---

## A.1 Hard Range Masking

Raw sensor channels occasionally report invalid corrupted numbers (such as $65,535$ from 16-bit I2C bus overflow or $0.0$ from power glitches). For a raw reading $T_i$ at time step $t_i$:

$$T_i^{\text{masked}} = \begin{cases} T_i & \text{if } 5.0^{\circ}\text{C} \le T_i \le 50.0^{\circ}\text{C} \\ \text{NaN} & \text{otherwise} \end{cases}$$

### Range Boundaries
* **Temperature:** $[5.0^{\circ}\text{C}, 50.0^{\circ}\text{C}]$
* **Relative Humidity:** $[0.0\%, 100.0\%]$
* **CO$_2$ Concentration:** $[300.0\text{ ppm}, 850.0\text{ ppm}]$

Readings outside these physical operational boundaries represent hardware communication faults and are immediately set to `NaN`.

---

## A.2 Rolling $3\sigma$ Gaussian Outlier Filter

To detect transient spikes within valid physical ranges without erasing actual dynamic temperature changes, a 2-minute centered rolling window $W_i = [t_i - 1\text{ min}, t_i + 1\text{ min}]$ containing $N = 24$ samples ($\Delta t = 5\text{s}$) is computed:

$$\mu_i = \frac{1}{N} \sum_{j \in W_i} T_j \quad \text{(Rolling Local Mean)}$$

$$\sigma_i = \sqrt{\frac{1}{N-1} \sum_{j \in W_i} (T_j - \mu_i)^2} \quad \text{(Rolling Local Standard Deviation)}$$

### Outlier Rejection Mask
$$\text{If } |T_i - \mu_i| > 3.0 \cdot \sigma_i \implies T_i^{\text{clean}} = \text{NaN}$$

* **The $3\sigma$ (99.73% Confidence) Rule:** Under a local Gaussian noise distribution, valid physical measurement noise falls within $\pm 3\sigma_i$. Any sample exceeding $3\sigma_i$ represents high-frequency electrical noise.
* **Local Rolling Window Adaptation:** Using a centered 2-minute rolling window allows the baseline $\mu_i$ to adjust dynamically as the room temperature drops (e.g. from $30^{\circ}\text{C} \rightarrow 20^{\circ}\text{C}$), preventing true cooling pulldowns from being falsely flagged as outliers.

---

## A.3 Linear `NaN` Interpolation

All missing samples (`NaN` values from hard range masking and $3\sigma$ outlier rejection) are reconstructed using time-weighted linear interpolation between surrounding valid data points $(t_k, T_k)$ and $(t_{k+1}, T_{k+1})$:

$$T(t) = T(t_k) + \frac{t - t_k}{t_{k+1} - t_k} \Big(T(t_{k+1}) - T(t_k)\Big)$$

---

## A.4 Exponential Moving Average (EMA) Noise Suppression

Finally, high-frequency residual quantization noise is suppressed using a first-order Low-Pass Exponential Moving Average (EMA) filter:

$$T_{\text{EMA}}(t_k) = \alpha \cdot T(t_k) + (1 - \alpha) \cdot T_{\text{EMA}}(t_{k-1})$$

Where $\alpha = 0.10$ is the smoothing factor ($90\%$ history weight, $10\%$ new sample weight), preserving macro thermal inertia while producing smooth trajectories suitable for numerical derivative evaluation in the Dual EKF.
