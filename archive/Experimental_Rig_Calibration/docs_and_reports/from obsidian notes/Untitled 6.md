# Chamber Envelope & Internal Heat Loads Review Document

**Target Base File:** [`generated_idf.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/generated_idf.idf)

---

## 1. Intent & Review Overview

This artifact presents the proposed EnergyPlus objects for the **Chamber Box Envelope ($100\text{mm}$ PU Foam)**, **Chamber Infiltration (Default Baseline)**, and **Internal Heat Loads (ESP32 Microcontroller = 1.0 W)** incorporating user adjustments.

---

## 2. Chamber Material & Construction (`Material` & `Construction`)

Per user instruction, we use **raw default physical material properties** for the initial baseline (calibration will be performed in later automated optimization loops):

| Property / Field | Selected Default Value | EnergyPlus Object Assignment | Physical Meaning |
|:---|:---:|:---|:---|
| **Material Name** | `Chamber_PU_Foam` | `Material` | Polyurethane foam wall panel |
| **Roughness** | **Smooth** | `Material` | Surface texture |
| **Thickness** | **0.100 m (100 mm)** | `Material` | PU foam wall panel thickness |
| **Thermal Conductivity ($k$)** | **0.0220 W/m·K** | `Material` | **Default Raw PU Foam Conductivity** |
| **Mass Density ($\rho$)** | **32.00 kg/m³** | `Material` | **Default Raw PU Foam Density** |
| **Specific Heat ($c_p$)** | **1500.00 J/kg·K** | `Material` | **Default Raw PU Foam Specific Heat** |
| **Thermal Absorptance** | **0.90** | `Material` | Longwave thermal radiation absorptance |
| **Solar Absorptance** | **0.70** | `Material` | Solar radiation absorptance |
| **Visible Absorptance** | **0.70** | `Material` | Visible light absorptance |
| **Wall Construction Name** | `Const_Chamber_PU_Foam` | `Construction` | Linked 1-layer chamber wall assembly |

---

## 3. Chamber Infiltration (`ZoneInfiltration:DesignFlowRate`) & Physical Context

| Field / Parameter | Selected Default Value | EnergyPlus Object Type | Origin & Physical Explanation |
|:---|:---:|:---|:---|
| **Object Name** | `Chamber_Infiltration` | `ZoneInfiltration:DesignFlowRate` | Models door seal leakage & wall hole drafts |
| **Target Zone** | `Chamber_ThermalZone` | `ZoneInfiltration:DesignFlowRate` | Internal $2\text{m} \times 2\text{m} \times 2\text{m}$ Chamber air volume |
| **Schedule Name** | `Always On Continuous` | `Schedule:Constant` | Active 24 hours a day continuously |
| **Air Exchange Rate** | **0.50 ACH** | `ZoneInfiltration:DesignFlowRate` | **Default Baseline:** Standard initial building infiltration rate (will be calibrated in optimization loops) |
| **Constant Coefficient** | **1.0** | `ZoneInfiltration:DesignFlowRate` | Constant infiltration multiplier |

> [!NOTE]
> **Physical Rig Leakage Context (User FYI):**
> The physical chamber has **2 holes of ~20mm diameter** in the chamber walls (used for sensor wiring & piping penetrations). These holes create continuous air leakage which contributes to the physical infiltration rate during testing.

---

## 4. Chamber Internal Heat Loads (`ElectricEquipment`, `People`, `Lights`)

| Load Category | Confirmed Value | EnergyPlus Object Type | Physical Description |
|:---|:---:|:---|:---|
| **Background Equipment** | **1.0 Watt** | `ElectricEquipment` (`Chamber_Equip`) | **Confirmed:** ESP32 microcontroller + temperature sensor logging heat gain |
| **Occupancy** | **0 Persons** | `People` (`Chamber_People`) | Chamber is completely unoccupied during testing |
| **Artificial Lighting** | **0 Watts** | `Lights` (`Chamber_Lights`) | Internal lights are turned OFF during testing |

---

## 5. Summary of IDF Objects to Inject

When updating `generated_idf.idf`, we will inject:

```idf
! 1. Chamber 100mm PU Foam Material (Default Properties)
Material,
  Chamber_PU_Foam,                   !- Name
  Smooth,                            !- Roughness
  0.1000,                            !- Thickness {m}
  0.0220,                            !- Thermal Conductivity {W/m-K}
  32.00,                             !- Density {kg/m3}
  1500.00,                           !- Specific Heat {J/kg-K}
  0.9000,                            !- Thermal Absorptance
  0.7000,                            !- Solar Absorptance
  0.7000;                            !- Visible Absorptance

! 2. Chamber Wall Construction
Construction,
  Const_Chamber_PU_Foam,             !- Name
  Chamber_PU_Foam;                    !- Layer 1

! 3. Chamber Infiltration (Default 0.50 ACH)
ZoneInfiltration:DesignFlowRate,
  Chamber_Infiltration,              !- Name
  Chamber_ThermalZone,               !- Zone Name
  Always On Continuous,              !- Schedule Name
  AirChanges/Hour,                   !- Calculation Method
  ,                                  !- Design Flow Rate {m3/s}
  ,                                  !- Flow per Area {m3/s-m2}
  ,                                  !- Flow per Exterior Surface Area {m3/s-m2}
  0.50,                              !- Air Changes per Hour {1/hr}
  1.0,                               !- Constant Term Coefficient
  0.0,                               !- Temperature Term Coefficient
  0.0,                               !- Velocity Term Coefficient
  0.0;                               !- Velocity Squared Term Coefficient

! 4. Background Equipment Heat Gain (ESP32 = 1.0W)
ElectricEquipment,
  Chamber_Equip,                     !- Name
  Chamber,                           !- Space Name
  Always On Continuous,              !- Schedule Name
  EquipmentLevel,                    !- Design Level Calculation Method
  1.0,                               !- Design Level {W}
  ,                                  !- Watts per Floor Area {W/m2}
  ;                                  !- Watts per Person {W/person}
```

---

## 6. Next Steps Workflow

1. **User Final Review:** Please review this updated artifact.
2. **User Confirmation:** When you give the green light, we will proceed to inject these objects into [`generated_idf.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/generated_idf.idf).
