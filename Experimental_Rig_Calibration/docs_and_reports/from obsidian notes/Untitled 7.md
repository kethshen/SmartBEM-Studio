# Chamber HVAC Equipment & Operational Schedules Review Document

**Source Documents:**  
* Hardware Rig Photo: [`real_rig.jpeg`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/real_rig.jpeg) (Tokyo Meter Co. Experimental Training Rig)
* Dashboard Monitor: [`ahu_web_ui.png`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/ahu_web_ui.png)  
* Target Base File: [`generated_idf.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/generated_idf.idf)

---

## 1. Intent & Review Overview

This artifact maps the exact physical controls from your **Experimental Rig Hardware ([`real_rig.jpeg`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/real_rig.jpeg))** directly into EnergyPlus HVAC objects (`ZoneHVAC:PackagedTerminalAirConditioner`, `Fan:OnOff`, `OutdoorAir:Mixer`, `Coil:Cooling:DX:SingleSpeed`, and Thermostat Schedules).

---

## 2. Experimental Rig Hardware vs. EnergyPlus HVAC Mapping

| Hardware Control / Feature | Physical Rig Setting | EnergyPlus Object & Parameter Assignment | Explanation & Context |
|:---|:---:|:---|:---|
| **MIX DAMPER** | **45% Open** (Fresh Air Intake) | `OutdoorAir:Mixer` Outdoor Air Flow Fraction $= \mathbf{0.45}$ | **Updated:** Damper open 45% during test runs to introduce fresh air |
| **MAIN BLOWER FAN** | **Continuous Operation** | `Fan:OnOff` Supply Air Fan Operating Mode $= \mathbf{\text{Always On Discrete}}$ | Blower runs continuously throughout all test runs (100% active airflow) |
| **COOLING COIL** | **DX Cooling Active** | `Coil:Cooling:DX:SingleSpeed` Availability $= \mathbf{\text{Always On Discrete}}$ | Single-speed DX cooling coil cycles to maintain setpoint |
| **HEATER & HUMIDIFIER** | **OFF (0%)** | `Coil:Heating:Electric` Availability $= \mathbf{\text{Always Off Discrete}}$ | Electric heating and humidification disabled |
| **COOLING SETPOINT** | **17.0 °C** | `Schedule:Day:Interval` (`COOLING_SETPOINT_SCH`) $= \mathbf{17.0^{\circ}\text{C}}$ | Constant 17.0°C cooling setpoint for all 24 hours |

---

## 3. Thermostat Controls & Temperature Schedules (`ThermostatSetpoint:DualSetpoint` & `Schedule:Day:Interval`)

| Property / Field | Confirmed Value | EnergyPlus Object Type | Physical Description |
|:---|:---:|:---|:---|
| **Cooling Setpoint** | **17.0 °C (Constant)** | `Schedule:Day:Interval` | **Confirmed:** Constant cooling setpoint for all 24 hours |
| **Heating Setpoint** | **10.0 °C (Constant)** | `Schedule:Day:Interval` | Heating setback (ensures electric heater is never triggered) |
| **Thermostat Control Type** | **Dual Setpoint (Type 4)** | `ZoneControl:Thermostat` | Controls both heating and cooling setpoints |
| **Control Schedule** | `Always On Continuous` | `Schedule:Constant` | Active 24 hours a day, 365 days a year |

---

## 4. Packaged Split AC Unit & Fan Configuration (`ZoneHVAC:PackagedTerminalAirConditioner` & `Fan:OnOff`)

| Property / Field | Standard Value | EnergyPlus Object Type | Reasonableness & Origin |
|:---|:---:|:---|:---|
| **Unit Name** | `Chamber_SplitAC` | `ZoneHVAC:PackagedTerminalAirConditioner` | Packaged split AC unit serving Chamber |
| **Availability Schedule** | `Always On Discrete` | `ZoneHVAC:PackagedTerminalAirConditioner` | AC unit active 24/7 |
| **Fan Operating Mode** | **`Always On Discrete`** | `ZoneHVAC:PackagedTerminalAirConditioner` | **Confirmed:** Blower runs continuously during testing |
| **Fan Total Efficiency** | **0.60 (60%)** | `Fan:OnOff` | **Standard Default:** Standard ASHRAE fan efficiency |
| **Pressure Rise** | **300 Pa** | `Fan:OnOff` | **Standard Default:** Standard duct pressure boost |
| **Motor Efficiency** | **0.80 (80%)** | `Fan:OnOff` | **Standard Default:** Standard electric motor efficiency |

---

## 5. DX Cooling Coil (`Coil:Cooling:DX:SingleSpeed`)

| Property / Field | Standard Value | EnergyPlus Object Type | Reasonableness & Origin |
|:---|:---:|:---|:---|
| **Coil Name** | `Coil Cooling DX Single Speed 1` | `Coil:Cooling:DX:SingleSpeed` | Direct expansion single-speed refrigerant cooling coil |
| **Availability Schedule** | `Always On Discrete` | `Coil:Cooling:DX:SingleSpeed` | Coil available for cooling calls 24/7 |
| **Rated COP** | **3.00 W/W** | `Coil:Cooling:DX:SingleSpeed` | **Standard Default:** Standard split AC Coefficient of Performance ($Q_{\text{cool}} / W_{\text{elec}}$) |
| **Airflow Rate** | **Autosize** | `Coil:Cooling:DX:SingleSpeed` | EnergyPlus automatically sizes airflow rate to match blower capacity |

---

## 6. Summary of IDF Objects to Inject

When updating `generated_idf.idf`, we will inject:

```idf
! 1. Constant 17.0 °C Cooling Setpoint Schedule
Schedule:Day:Interval,
  COOLING_SETPOINT_SCH_DefaultDay,        !- Name
  Temperature,                            !- Schedule Type Limits Name
  No,                                     !- Interpolate to Timestep
  24:00,                                  !- Time 1 {hh:mm}
  17.0;                                   !- Value Until Time 1 {C}

! 2. Constant 10.0 °C Heating Setpoint Schedule
Schedule:Day:Interval,
  HEATING_SETPOINT_SCH_DefaultDay,        !- Name
  Temperature,                            !- Schedule Type Limits Name
  No,                                     !- Interpolate to Timestep
  24:00,                                  !- Time 1 {hh:mm}
  10.0;                                   !- Value Until Time 1 {C}

! 3. Continuous Supply Fan Operating Mode (Always On Discrete)
! (In ZoneHVAC:PackagedTerminalAirConditioner object field):
! Always On Discrete,                     !- Supply Air Fan Operating Mode Schedule Name

! 4. Electric Heater Availability (OFF)
! (In Coil:Heating:Electric object field):
! Always Off Discrete,                    !- Availability Schedule Name
```

---

## 7. Next Steps Workflow

1. **User Final Review:** Please review this updated artifact.
2. **User Confirmation:** When you give the green light, we will proceed to inject these final HVAC objects and setpoint schedules into [`generated_idf.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/generated_idf.idf).
