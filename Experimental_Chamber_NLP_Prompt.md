# SmartBEM Studio — Experimental Rig NLP Prompt Guide

This document contains a comprehensive, highly accurate natural language description of the **Department of Mechanical Engineering Test Rig (Peradeniya Environmental Chamber)** derived section-by-section from `hanger_chamber_base_template_v3.idf`.

Copy and paste the detailed prompt below directly into the **Simulation Setup (NLP) Studio** (`web/pages/nlp.html`) to generate the exact EnergyPlus BEM baseline model.

---

## 📋 Comprehensive Natural Language Prompt for NLP Studio

```text
Create an EnergyPlus building energy model for a nested two-zone experimental test facility located in Peradeniya, Sri Lanka (Latitude 7.25°N, Longitude 80.59°E, Elevation 475m, Timezone UTC+5.5). Set the simulation timestep to 60 steps per hour (1-minute temporal resolution).

1. OUTER HANGAR ZONE:
Model a large unconditioned industrial hangar measuring 80.0 meters long, 17.0 meters wide, with a 12.0 meter wall eave height and a gable roof reaching 14.0 meters at the ridge. Construct the hangar floor using a 200mm heavyweight concrete slab on ground. Construct the exterior hangar walls using 100mm brick with sand-cement plaster on both sides. Construct the gable roof using outer 0.6mm corrugated asbestos sheets, a 150mm air gap, and an inner 3.2mm ceiling board. Model 350 m2 of internal brick partition walls to account for internal thermal mass. Set the unconditioned hangar natural infiltration rate to 3.0 air changes per hour (ACH) to represent continuous top eave ventilation gaps. Include general lighting at 8 W/m2 and equipment at 10 W/m2.

2. INNER ENVIRONMENTAL TEST CHAMBER ZONE:
Inside the unconditioned hangar, model a compact, highly insulated environmental test chamber measuring 2.0 meters long by 2.0 meters wide by 2.0 meters high (total volume 8.0 m3, floor area 4.0 m2). Construct all chamber walls, ceiling, and roof using 10cm Polyurethane (PU) rigid foam insulation panels with thermal conductivity 0.0265 W/m-K, density 45 kg/m3, and specific heat 916 J/kg-K. Construct the chamber floor on a wood stud base frame. Set the sealed chamber infiltration rate to a baseline of 0.011 air changes per hour (ACH).

3. HVAC & SUPPLY AIR BLOWER SYSTEM:
Equip the inner test chamber with a dedicated Packaged Terminal Split AC unit supply system providing 16.0°C supply air through an 11cm diameter supply duct (cross-sectional area 0.0095 m2) with a maximum cooling airflow capacity of 0.05 m3/s (100 CFM). Include dynamic supply air mass flow controls driven by an external 1-minute flow schedule reflecting fan speed % and mixer damper opening %. Model a pre-test heat soak internal heater of 320 W operating from 00:00 to 07:40 AM to bring the chamber air into pre-test thermal equilibrium at 29.7°C prior to active cooling pulldown.

4. OCCUPANCY & INTERNAL LOADS:
Define chamber internal loads with a design occupancy density of 15 m2 per person, an activity level of 120 W per person, lighting at 8 W/m2, and equipment at 10 W/m2. Enable SQLite summary reporting and zone temperature output at 1-minute intervals.
```

---

## 🔍 Section-by-Section IDF Breakdown & Parameter Reference

### Section 1: Site Location & Temporal Resolution
* **Location:** Peradeniya, Sri Lanka ($7.2535^{\circ}\text{N}, 80.5916^{\circ}\text{E}$, Altitude $475\text{m}$, Timezone UTC+5.5).
* **Timestep:** $60$ timesteps per hour ($1$-minute simulation resolution).
* **RunPeriod:** July 21, 2026 test day period.

---

### Section 2: Outer Hangar Zone
* **Dimensions:** $80.0\text{m (Length)} \times 17.0\text{m (Width)} \times 12.0\text{m (Eave Height)}$, Gable ridge $14.0\text{m}$.
* **Floor Construction:** $200\text{mm}$ Heavyweight concrete slab ($\text{Const\_M15\_200mm\_heavyweight\_concrete}$).
* **Wall Construction:** $100\text{mm}$ SLS 855 brick core + $10\text{mm}$ cement-sand plaster on both sides ($\text{Hanger\_Outer\_Wall\_240mm}$).
* **Roof Construction:** $0.6\text{mm}$ Corrugated sheet + $150\text{mm}$ air gap + $3.2\text{mm}$ ceiling board ($\text{Hanger\_Roof\_Assembly}$).
* **Internal Thermal Mass:** $350.0\text{ m}^2$ internal partition brick walls ($\text{Hanger\_Internal\_Partition\_Walls}$).
* **Infiltration:** $3.00\text{ ACH}$ continuous open-eave infiltration.

---

### Section 3: Inner Environmental Test Chamber Zone
* **Dimensions:** $2.0\text{m} \times 2.0\text{m} \times 2.0\text{m}$ (Volume $8.0\text{ m}^3$, Floor Area $4.0\text{ m}^2$).
* **Insulation Panels:** $10\text{cm}$ Polyurethane (PU) rigid foam wall panel ($\text{Chamber\_PU\_Foam}$).
  * Thermal Conductivity ($k_{\text{foam}}$): $0.02650\text{ W/(m}\cdot\text{K)}$
  * Specific Heat ($c_{p,\text{foam}}$): $916.0\text{ J/(kg}\cdot\text{K)}$
  * Density ($\rho_{\text{foam}}$): $45.0\text{ kg/m}^3$
  * Derived Conductance ($UA_0$): $5.76\text{ W/K}$
  * Derived Thermal Capacitance ($C_{s,0}$): $25,000\text{ J/K}$
* **Infiltration:** Calibrated baseline $0.0110\text{ ACH}$.

---

### Section 4: HVAC & Dynamic Airflow Supply Controls
* **AC Unit:** Packaged Terminal Split AC / Ideal Loads System.
* **Supply Air Temperature:** Constant $16.0^{\circ}\text{C}$ supply cooling air.
* **Duct Diameter:** $11\text{cm}$ diameter circular duct ($A_{\text{duct}} = \pi \times 0.055^2 = 0.0095033\text{ m}^2$).
* **Maximum Flow Rate:** $0.050\text{ m}^3\text{/s}$ (~100 CFM).
* **Pre-Test Heat Soak:** $320\text{ W}$ thermal soak heater from 00:00 to 07:40 AM ($\text{Chamber\_PreTest\_HeatSoak}$).
* **Dynamic Airflow Schedule:** 1-minute mass flow schedule (`FLOW_RATE_SCHEDULE`) calculated from:
  $$v_{\text{air}} = v_{\text{off}} + \frac{\text{mixer}}{100}(v_{\text{on}} - v_{\text{off}})$$
  $$m_{sa} = \rho_{\text{air}} \cdot v_{\text{air}} \cdot A_{\text{duct}}$$

---

### Section 5: Internal Loads & Occupancy Schedules
* **Occupancy:** $15.0\text{ m}^2\text{/person}$ floor area design density.
* **Metabolic Rate:** $120\text{ W/person}$ light work activity.
* **Lighting:** $8.0\text{ W/m}^2$.
* **Equipment:** $10.0\text{ W/m}^2$.
