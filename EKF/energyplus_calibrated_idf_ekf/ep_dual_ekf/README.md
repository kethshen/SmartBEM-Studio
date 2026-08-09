# EnergyPlus Dual EKF Benchmark

This directory contains the 1-minute resampled EnergyPlus benchmark runner for the **Decoupled Dual Extended Kalman Filter (Dual EKF)**, ported directly from `test_rig_dual_ekf.py`.

---

## 🏛️ Architecture & Filter Formulations

Dual EKF operates two decoupled filters running in tandem:

1. **State Filter ($\mathbf{x} = [T_z, w_z, c_z]^T$):**
   * 4th-Order Runge-Kutta (RK4) ODE integration.
   * State measurement noise covariance $R_s = \text{diag}([0.0001, 4\times 10^{-8}, 6.25])$.

2. **Parameter Filter ($\boldsymbol{\xi}_p = [\xi_{\alpha_o}, \xi_{\alpha_s}, \xi_{\alpha_e}, \xi_{\beta_o}, \xi_{\gamma_e}]^T$):**
   * Unconstrained sigmoid mapping $\boldsymbol{\theta} = \text{lo} + (\text{hi} - \text{lo}) \sigma(\boldsymbol{\xi}_p)$.
   * Physical building parameters ($C_s, M, m_{\text{inf}}, UA$) derived online.

---

## 💻 Command to Run

```powershell
python "d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\EKF\energyplus_calibrated_idf_ekf\ep_dual_ekf\ep_dual_ekf.py"
```
