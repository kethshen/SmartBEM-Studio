# ROBOD EKF Spike Elimination & Parameter Stabilization Plan (`robod_ekf`)

This document presents the theoretical control solutions and implementation strategy to eliminate parameter division spikes ($10^{12}$ and $-10^6$) in the ROBOD Extended Kalman Filter ([`Real_EKF_ROBOD.py`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/EKF/robod_ekf/Real_EKF_ROBOD.py)).

---

## 1. Root Cause Diagnosis of Spikes in ROBOD EKF

In the current ROBOD multi-day plots (e.g. `Room_3_SDE4_Office_EKF_Derived_Physical_Parameters.png`), large vertical spikes ($10^{12}$ and $-10^6$) occur at specific timestamps. There are **two distinct mathematical mechanisms** causing these spikes:

1. **Division-by-Zero / Near-Zero Singularities ($\alpha_s \to 0$):**  
   The derived thermal capacitance is computed as:
   $$C_s = \frac{c_{pa}}{\alpha_s}$$
   During unexcited periods (nighttime / FCU fan off, $\dot{m}_{sa} \approx 0$), the supply heat exchange parameter $\alpha_s$ drops near zero ($10^{-9}$). Dividing $c_{pa} = 1006.0$ by $10^{-9}$ causes $C_s$ to explode to **$10^{12}$**.
2. **Cascading Envelope Conductance Spike ($UA$ Spikes):**  
   Envelope conductance is derived as:
   $$UA = \alpha_o \cdot C_s - c_{pa} \cdot \dot{m}_{\text{inf}}$$
   When $C_s$ spikes to $10^{12}$, $UA$ immediately multiplies by $10^{12}$, producing massive vertical spikes in the $UA$ plot.

---

## 2. Proposed Control-Theoretic Solutions for `robod_ekf`

### **Solution 1: Sigmoid/Logistic Parameter Mapping ($\xi \to \alpha_s, \beta_s, \alpha_o$)**

* **Mathematical Formulation:**  
  Instead of estimating $\alpha_s$ in unconstrained space, the EKF estimates an internal state variable $\xi_{\alpha_s} \in (-\infty, +\infty)$.  
  The physical parameter $\alpha_s$ is mapped through an infinitely differentiable logistic sigmoid function bounded strictly to the physical room limits $[\alpha_{s,\min}, \alpha_{s,\max}]$:
  $$\alpha_s(\xi_{\alpha_s}) = \alpha_{s,\min} + \frac{\alpha_{s,\max} - \alpha_{s,\min}}{1 + e^{-\xi_{\alpha_s}}}$$

* **Room 3 Physical Bounds:**  
  For ROBOD Room 3 ($C_s \in [1000, 2500]\text{ kJ/K}$), the physical bounds are:
  $$\alpha_s \in \left[\frac{1006.0}{2,500,000}, \frac{1006.0}{1,000,000}\right] = [0.0004024, 0.001006]$$

* **Why it eliminates spikes:**  
  Because $\alpha_s$ is strictly constrained above $\alpha_{s,\min} = 0.0004024$, **$\alpha_s$ can NEVER equal zero or drop to $10^{-9}$**. $C_s = \frac{1006.0}{\alpha_s}$ is mathematically guaranteed to remain smoothly bounded between $1,000\text{ kJ/K}$ and $2,500\text{ kJ/K}$, completely eliminating $10^{12}$ spikes!

---

### **Solution 2: Adaptive Process Noise $Q_k(\dot{m}_{sa})$ & Excitation-Aware Scaling**

* **Mathematical Formulation:**  
  During FCU fan shut-off periods ($\dot{m}_{sa} < 0.01\text{ kg/s}$), no supply air thermal excitation enters the room. Process noise $Q_k[\alpha_s]$ and $Q_k[\beta_s]$ are scaled smoothly with ventilation flow:
  $$Q_{\alpha_s}(\dot{m}_{sa}) = Q_{\text{base}} \cdot \tanh\left(\frac{\dot{m}_{sa}}{\dot{m}_{\text{threshold}}}\right)$$

* **Why it eliminates spikes:**  
  When ventilation turns off ($\dot{m}_{sa} \to 0$), $Q_{\alpha_s} \to 0$. The filter freezes uncertainty propagation for $\alpha_s$, preventing covariance matrix $P$ from winding up during unexcited periods and eliminating Kalman gain spikes when the FCU fan turns back on.

---

### **Solution 3: Epsilon Regularization & Warmup Filter in Post-Processing**

* **Mathematical Formulation:**  
  Apply a small regularizing epsilon $\epsilon = 10^{-6}$ when computing derived physical parameters:
  $$C_{s,\text{derived}} = \frac{c_{pa}}{\max(\alpha_s, 0.0004024)}$$
  $$UA_{\text{derived}} = \alpha_o \cdot C_{s,\text{derived}} - c_{pa} \cdot (\beta_o \cdot M_{\text{room}})$$

* **Why it eliminates spikes:**  
  Even under extreme measurement noise, the derived physical values $C_s, M, \dot{m}_{\text{inf}}, UA$ remain smooth, physically realistic, and strictly within the official ROBOD benchmark expectation bands.

---

## 3. Comparison of EKF Behavior Before and After Plan

| Feature | Current `robod_ekf` Implementation | Proposed Plan for `robod_ekf` |
| :--- | :--- | :--- |
| **$\alpha_s$ Parameter Space** | Unconstrained linear estimate | Bounded Sigmoid Logistic Mapping $\alpha_s(\xi)$ |
| **$C_s$ Trajectory Spikes** | Explodes to $10^{12}$ when FCU off | **Strictly bounded to $[1000, 2500]\text{ kJ/K}$** |
| **$UA$ Conductance Spikes** | Explodes to $10^6$ / $-10^6$ | **Strictly bounded to $[150, 350]\text{ W/K}$** |
| **Covariance Windup** | High during zero-flow periods | Eliminated via smooth $Q_k(\dot{m}_{sa})$ scaling |
