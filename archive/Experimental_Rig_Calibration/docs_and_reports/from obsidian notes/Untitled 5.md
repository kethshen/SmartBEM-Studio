# Hanger Windows, Glazing & Infiltration Review Document

**Target Base File:** [`generated_idf.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/generated_idf.idf)

---

## 1. Intent & Review Overview

This artifact presents the exact proposed EnergyPlus objects for the **Side Wall Window Group Matrix**, **Glass Glazing Materials**, and **Hanger Infiltration / Eave Gap Ventilation** incorporating user adjustments.

---

## 2. Window Glass & Frame Materials (`WindowMaterial:Glazing` & `Construction`)

| Property / Field | Selected Value | EnergyPlus Object Assignment | Physical Meaning |
|:---|:---:|:---|:---|
| **Glazing Material** | **CLEAR 6MM** | `WindowMaterial:Glazing` | **Default EnergyPlus Material:** 6mm clear float glass |
| **Thickness** | **0.006 m (6 mm)** | `WindowMaterial:Glazing` | Glass pane thickness |
| **Solar Transmittance** | **0.775** | `WindowMaterial:Glazing` | Fraction of solar heat passing through glass |
| **Solar Reflectance** | **0.071** | `WindowMaterial:Glazing` | Fraction of solar heat reflected by glass surface |
| **Visible Transmittance** | **0.881** | `WindowMaterial:Glazing` | Fraction of daylight entering through window |
| **Thermal Conductivity** | **0.90 W/m·K** | `WindowMaterial:Glazing` | Glass thermal conductivity |
| **Window Assembly Name** | `Hanger_Window_Clear6mm` | `Construction` | Linked 1-layer window assembly |

---

## 3. Side Wall Window Group Geometry & Total Glass Area

Based on [`hanger side view windows.pdf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Readings_from_rig/solid%20model/hanger%20side%20view%20windows.pdf):

### Vertical Coordinates on North & South Long Walls (Height = 6.00 m)

| Window Tier | Bottom Edge Height ($Z_1$) | Top Edge Height ($Z_2$) | Tier Height | Tier Width | Window Area per Unit |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Lower Window Tier** | **1.20 m** | **3.30 m** | **2.10 m** | **1.10 m** | **$2.31\text{ m}^2$** |
| **Upper Window Tier** | **3.65 m** | **5.05 m** | **1.40 m** | **1.10 m** | **$1.54\text{ m}^2$** |

* Above $5.05\text{ m}$ is a $0.35\text{ m}$ solid wall strip up to $5.40\text{ m}$, topped by the **$0.60\text{ m}$ continuous open ventilation gap** ($5.40\text{ m} \rightarrow 6.00\text{ m}$).

### Short Explanation of Total Glass Area Calculation ($169.4\text{ m}^2$ per long wall):
1. **Window Units Count:** Along 1 long side wall ($80.10\text{m}$ total length), there are 11 structural bays $\times$ 4 window groups per bay = **44 window groups**.
2. **Lower Tier Area:** 44 lower windows $\times (2.10\text{m} \times 1.10\text{m}) = 44 \times 2.31\text{m}^2 = \mathbf{101.64\text{ m}^2}$.
3. **Upper Tier Area:** 44 upper windows $\times (1.40\text{m} \times 1.10\text{m}) = 44 \times 1.54\text{m}^2 = \mathbf{67.76\text{ m}^2}$.
4. **Total Side Glass Area:** $101.64\text{ m}^2 + 67.76\text{ m}^2 = \mathbf{169.4\text{ m}^2}$ glass per side wall.

---

## 4. Hanger Infiltration & Eave Opening (`ZoneInfiltration:DesignFlowRate`)

| Field / Parameter        |            Selected Value             | EnergyPlus Object Type            | Origin & Physical Explanation                                                                                                                                                       |
| :----------------------- | :-----------------------------------: | :-------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Object Name**          | `Hanger_Continuous_Eave_Infiltration` | `ZoneInfiltration:DesignFlowRate` | Models continuous fresh air draft through top 0.60m eave gap                                                                                                                        |
| **Target Zone**          |         `Hanger_ThermalZone`          | `ZoneInfiltration:DesignFlowRate` | Main Hanger air volume ($V \approx 10,600\text{ m}^3$)                                                                                                                              |
| **Schedule Name**        |        `Always On Continuous`         | `Schedule:Constant`               | Active 24 hours a day, 365 days a year                                                                                                                                              |
| **Air Exchange Rate**    |             **3.00 ACH**              | `ZoneInfiltration:DesignFlowRate` | **Origin:** ASHRAE Fundamentals / CIBSE Guide A recommendation for unconditioned high-eave industrial sheds with continuous open eave gaps ($87.4\text{ m}^2$ total open vent area) |
| **Constant Coefficient** |                **1.0**                | `ZoneInfiltration:DesignFlowRate` | Constant infiltration multiplier                                                                                                                                                    |

---

## 5. Summary of IDF Objects to Inject

When updating `generated_idf.idf`, we will inject:

```idf
! 1. Window Glass Construction
Construction,
  Hanger_Window_Clear6mm,     !- Name
  CLEAR 6MM;                  !- Layer 1 (EnergyPlus Default 6mm Clear Glass)

! 2. Continuous Eave Gap Infiltration (3.0 ACH)
ZoneInfiltration:DesignFlowRate,
  Hanger_Continuous_Eave_Infiltration, !- Name
  Hanger_ThermalZone,                  !- Zone Name
  Always On Continuous,                !- Schedule Name
  AirChanges/Hour,                     !- Calculation Method
  ,                                    !- Design Flow Rate {m3/s}
  ,                                    !- Flow per Area {m3/s-m2}
  ,                                    !- Flow per Exterior Surface Area {m3/s-m2}
  3.00,                                !- Air Changes per Hour {1/hr}
  1.0,                                 !- Constant Term Coefficient
  0.0,                                 !- Temperature Term Coefficient
  0.0,                                 !- Velocity Term Coefficient
  0.0;                                 !- Velocity Squared Term Coefficient
```

---

## 6. Next Steps Workflow

1. **User Final Review:** Please review this updated artifact.
2. **User Confirmation:** When you give the green light, we will proceed to update `generated_idf.idf` with these window constructions, window sub-surfaces, and infiltration objects.



Edited update_idf_windows.py
Ran command: `python update_idf_windows.py`
Ran command: `python -c "import os; os.remove(r'd:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\Readings_from_rig\update_idf_windows.py')"`

Done! Group 2 objects (**Windows, Glazing & Infiltration**) have been injected into [`generated_idf.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/generated_idf.idf).

---

### Short Summary of Updates Made:

1. **Window Glazing Material (`CLEAR 6MM`):**
   * Injected EnergyPlus built-in default material `CLEAR 6MM` ($6\text{ mm}$ thickness, $U \approx 5.8\text{ W/m}^2\text{K}$, Solar Transmittance $= 0.775$, Visible Transmittance $= 0.881$).
   * Created window assembly `Hanger_Window_Clear6mm`.

2. **Hanger Natural Infiltration (`Hanger_Continuous_Eave_Infiltration`):**
   * Injected `ZoneInfiltration:DesignFlowRate` set to **3.00 ACH** continuously to model fresh air exchange through the top $0.60\text{ m}$ open eave gap into the main Hanger volume.