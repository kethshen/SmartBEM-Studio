# EnergyPlus Calibrated IDF EKF Framework

This directory contains the EnergyPlus 1-minute benchmark Extended Kalman Filters for building state estimation, physical parameter recovery, and occupancy tracking.

---

## 📁 Directory Structure

* **`ep_single_ekf/`**: 10-State Single Extended Kalman Filter (`ep_single_ekf.py`).
* **`ep_dual_ekf/`**: Decoupled Dual Extended Kalman Filter (`ep_dual_ekf.py`).

---

## 🏛️ Simulation Model & Weather Inputs

* **Calibrated EnergyPlus IDF Model:** [`hanger_chamber_after_calibrated_v3.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Experimental_Rig_Calibration/calibrated_v3_dynamic_supply_controls/hanger_chamber_after_calibrated_v3.idf)
* **EPW Weather Files:** Generated in [`Experimental_Rig_Calibration/sensor_readings/weather/`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/Experimental_Rig_Calibration/sensor_readings/weather) using `generate_weather_epw.py`.

---

## 💻 Commands to Run

```powershell
# Run Single EKF Benchmark
python "d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\EKF\energyplus_calibrated_idf_ekf\ep_single_ekf\ep_single_ekf.py"

# Run Dual EKF Benchmark
python "d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartBEM-Studio\EKF\energyplus_calibrated_idf_ekf\ep_dual_ekf\ep_dual_ekf.py"
```
