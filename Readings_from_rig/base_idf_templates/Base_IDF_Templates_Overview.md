# Appendix D: EnergyPlus Base Model Architecture & IDF Template Specification

---

## 1. Overview & Model Objectives

The physical experimental facility consists of an insulated test chamber constructed inside a large unconditioned hangar building. To capture both the external ambient-to-hangar thermal buffer dynamics and the inner chamber thermal response, EnergyPlus is configured as a **nested two-zone thermal system**.

The master uncalibrated model geometry and thermal specifications are defined in **[`base_idf_templates/chamber_base_template.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/base_idf_templates/chamber_base_template.idf)**. This template serves as the input baseline for all optimization runners (`calibrated_v1` through `calibrated_v5`).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ OUTER HANGAR ZONE (80m x 18m x 6m Eave, 8.3m Peak) — Unconditioned Buffer   │
│                                                                             │
│         ┌─────────────────────────────────────────────────┐                 │
│         │ INNER CHAMBER ZONE (2.0m x 2.0m x 2.0m = 8m³)   │                 │
│         │ • Polyurethane Foam Insulation Walls (10 cm)    │                 │
│         │ • Internal Thermal Capacitance (Eqpt + Struct)   │                 │
│         │ • Air Loop HVAC Supply / Sensor Feedback Ports   │                 │
│         └─────────────────────────────────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Thermal Zone Geometries

### 2.1 Zone 1: Outer Hangar Zone (`Hanger_ThermalZone`)
* **Geometry:** $80.0\text{ m (Length)} \times 18.0\text{ m (Width)} \times 6.0\text{ m (Eave Height)}$ with a gable roof peaking at $8.3\text{ m}$ ($2.3\text{ m}$ pitch height).
* **Boundary Condition:** Exposed to outdoor ambient weather on all 4 vertical walls and gable roof surfaces.
* **Openings & Infiltration:** Natural infiltration driven by upper wall ventilation gaps ($0.60\text{ m}$) and window apertures.

### 2.2 Zone 2: Inner Test Chamber Zone (`Chamber_ThermalZone`)
* **Geometry:** $2.0\text{ m} \times 2.0\text{ m} \times 2.0\text{ m}$ cube ($V = 8.0\text{ m}^3$, Surface Area $A = 24.0\text{ m}^2$).
* **Boundary Condition:** All 6 surfaces (North, South, East, West walls, Roof, Floor) border the `Hanger_ThermalZone`, acting as an unconditioned buffer space between ambient weather and chamber walls.

---

## 3. Material Constructions & Thermal Properties

### 3.1 Chamber Envelope Layer (`Chamber_PU_Foam`)
The test chamber walls are fabricated using rigid Polyurethane (PU) foam insulation panels:

* **Thickness ($d$):** $0.100\text{ m}$ ($10\text{ cm}$)
* **Thermal Conductivity ($k_{\text{foam}}$):** $0.0220\text{ W/(m}\cdot\text{K)}$ (Baseline uncalibrated) $\longrightarrow$ **$0.02650\text{ W/(m}\cdot\text{K)}$** (ASHRAE Calibrated Master)
* **Density ($\rho_{\text{foam}}$):** $32.0\text{ kg/m}^3$ (Baseline uncalibrated) $\longrightarrow$ **$45.0\text{ kg/m}^3$** (ASHRAE Calibrated Master)
* **Specific Heat ($c_{p,\text{foam}}$):** $1500.0\text{ J/(kg}\cdot\text{K)}$ (Baseline uncalibrated) $\longrightarrow$ **$916.0\text{ J/(kg}\cdot\text{K)}$** (ASHRAE Calibrated Master)

### 3.2 Hangar Envelope Construction (`Hanger_Composite_Wall_250mm`)
* **Outer Layer:** Cement Plaster ($15\text{ mm}$, $k = 0.72\text{ W/(m}\cdot\text{K)}$, $\rho = 1860\text{ kg/m}^3$)
* **Core Layer:** Sri Lanka Standard Brick (SLS 855) ($220\text{ mm}$, $k = 0.77\text{ W/(m}\cdot\text{K)}$, $\rho = 1920\text{ kg/m}^3$)
* **Inner Layer:** Cement Plaster ($15\text{ mm}$, $k = 0.72\text{ W/(m}\cdot\text{K)}$, $\rho = 1860\text{ kg/m}^3$)

---

## 4. Internal Thermal Mass & Infiltration Setup

* **Internal Thermal Mass (`Chamber_Internal_Mass`):** Added to model structural aluminum framing, equipment casing, and internal sensor hardware thermal capacitance ($C_s$).
* **Infiltration Rate (`ZoneInfiltration:DesignFlowRate`):**
  * Baseline uncalibrated infiltration: $0.50\text{ ACH}$
  * Calibrated master infiltration: **$0.0110\text{ ACH}$** ($0.0000244\text{ m}^3/\text{s}$), confirming high airtightness of the insulated chamber envelope.

---

## 5. Energy Management System (EMS) & HVAC Coupling

The template IDF contains EnergyPlus EMS objects that enable real-time sensor telemetry injection during dynamic calibration runs:

* **`EnergyManagementSystem:Sensor`**: Monitors ambient outdoor conditions, supply air temperature ($T_{sa}$), and fan velocity.
* **`EnergyManagementSystem:Actuator`**: Overrides supply airflow rate ($m_{sa}$) and zone heat gain ($q_{\text{occ}}$) dynamically per timestep.
* **Simulation Timestep (`Timestep`):** Set to **$60\text{ timesteps/hour}$ ($\Delta t = 1.0\text{ min}$ resolution)** during high-resolution calibration runs to match minute-by-minute sensor logging frequency.
