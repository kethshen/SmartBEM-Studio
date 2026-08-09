# EnergyPlus 10-State Single EKF Benchmark

This directory contains the 1-minute resampled EnergyPlus benchmark runner for the **10-State Extended Kalman Filter (Single EKF)**, ported directly from `test_rig_single_ekf.py`.

---

## 🏛️ Continuous Physical State Equations

$$\begin{aligned}
\frac{d T_z}{dt} &= \alpha_o (T_o - T_z) + \alpha_s m_{sa} (T_{sa} - T_z) + \alpha_e \\
\frac{d w_z}{dt} &= \beta_o (w_o - w_z) + \beta_s m_{sa} (w_{sa} - w_z) + \beta_e \\
\frac{d c_z}{dt} &= \beta_o (c_o - c_z) + \beta_s m_{sa} (c_{sa} - c_z) + \gamma_e
\end{aligned}$$

---

## 📊 Physical Parameter Definitions

$$\begin{aligned}
\alpha_o &= \frac{UA + c_{pa} m_{\text{inf}}}{C_s} & \quad \alpha_s &= \frac{c_{pa}}{C_s} & \quad \alpha_e &= \frac{Q_e}{C_s} \\
\beta_o &= \frac{m_{\text{inf}}}{M} & \quad \beta_s &= \frac{1}{M} & \quad \beta_e &= \frac{\dot{m}_{w,e}}{M} \\
\gamma_e &= \frac{\dot{m}_{\text{CO}_2,e}}{M}
\end{aligned}$$

---

## 💻 Command to Run

```powershell
python "d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\EKF\energyplus_calibrated_idf_ekf\ep_single_ekf\ep_single_ekf.py"
```
