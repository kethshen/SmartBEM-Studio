Viewed test_rig_dual_ekf.py:125-360
Edited debug_dual_ekf.py
Ran command: `python "C:\Users\ASUS\.gemini\antigravity-ide\brain\30f9feb6-f7e5-40c7-a4be-f148a0753aa8\scratch\debug_dual_ekf.py"`
Edited debug_dual_ekf.py
Ran command: `python "C:\Users\ASUS\.gemini\antigravity-ide\brain\30f9feb6-f7e5-40c7-a4be-f148a0753aa8\scratch\debug_dual_ekf.py"`
Edited test_dual_ekf_fix.py
Ran command: `python "C:\Users\ASUS\.gemini\antigravity-ide\brain\30f9feb6-f7e5-40c7-a4be-f148a0753aa8\scratch\test_dual_ekf_fix.py"`
Edited test_dual_ekf_fix.py
Ran command: `python "C:\Users\ASUS\.gemini\antigravity-ide\brain\30f9feb6-f7e5-40c7-a4be-f148a0753aa8\scratch\test_dual_ekf_fix.py"`
Viewed test_rig_dual_ekf.py:245-290
Edited test_rig_dual_ekf.py
Ran command: `python "d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\EKF\test_rig_dataset_ekf\test_rig_dual_ekf\test_rig_dual_ekf.py"`
Used tool: manage_task
Used tool: schedule

!

### 🛠️ Root Cause Analysis & Fixes for `test_rig_dual_ekf.py`

#### 1. Why Occupancy Estimation was Stuck at 0
* **Root Cause (Sigmoidal Vanishing Gradient):**  
  $\gamma_e$ is mapped from unbounded filter parameter $\xi_{\gamma_e}$ via a sigmoid function ($\theta \in [0.0, 5.0]$). Initializing $\gamma_e$ near $1 \times 10^{-4}$ set $\xi_{\gamma_e} \approx -10.8$, where the sigmoid derivative $\frac{\partial \theta}{\partial \xi} = (\text{hi}-\text{lo}) \cdot s(1-s) \approx 10^{-4}$. This caused the Kalman gain $K_{p, \gamma_e}$ to drop to $0.0009$, trapping the parameter at 0 regardless of how high $\text{CO}_2$ rose.
* **Fix Applied:**  
  Initialized $\gamma_{e,0}$ at $0.05\text{ ppm/s}$ (active gradient region of the sigmoid where derivative $dGe \approx 0.098$, 1,000× larger!) and tuned $R_{p, \gamma_e} = 2.0\text{ ppm}^2$. The filter now dynamically tracks occupancy jumps from 0 to 1+ occupants!

---

#### 2. Why Temperature Estimation ($T_z$) had a Downward Offset
* **Root Cause 1 (Thermal Bias Over-Adaptation):**  
  Process noise $Q_p[\xi_{\alpha_e}] = 1 \times 10^{-4}$ was too large, causing the thermal heat bias $\alpha_e$ to quickly adapt downward to $-0.002^\circ\text{C}/\text{s}$ ($-50\text{ W}$ fake heat loss), artificially pulling estimated $T_z$ lower than measured $T_z$.
* **Root Cause 2 (State Measurement Variance $R_s$):**  
  $R_{s, T_z} = 0.0025$ ($0.05^\circ\text{C}$ std) caused state filter prediction lag during cooling transients.
* **Fix Applied:**  
  - Controlled thermal bias adaptation $Q_p[\xi_{\alpha_e}] = 1 \times 10^{-7}$ and initialized $\alpha_e = 0.0\text{ W}$ at $t=0$.
  - Tightened state measurement noise $R_{s, T_z} = 0.0001$ ($0.01^\circ\text{C}$ std) and set process noise $Q_{s, T_z} = 1 \times 10^{-2}$.

---

### 📊 Verification Results (Dataset `day_4_p_5`)

| Metric | Before Fix | After Fix | Target |
|---|:---:|:---:|:---:|
| **Mean $T_z$ Offset ($T_{z,\text{est}} - T_{z,\text{meas}}$)** | $-0.098^\circ\text{C}$ | **`-0.00014 °C`** | **`~0.00 °C` (Zero Offset!)** |
| **Peak Occupancy Estimate ($\hat{N}_{\text{occ}}$)** | $0.0004$ occupants | **`1.18 occupants`** | **`~1 occupant`** |

---

### 💻 Command for You to Run in Your Terminal

```powershell
python "d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\EKF\test_rig_dataset_ekf\test_rig_dual_ekf\test_rig_dual_ekf.py"
```