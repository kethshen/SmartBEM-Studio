# SmartBEM Studio — Utility Scripts

This directory contains development and utility scripts for managing the system's datasets, indexes, and other runtime configurations.

## Included Scripts

### 1. `build_weather_index.py`
This script is a one-time utility to generate the global weather station registry used by the web dashboard.
- **What it does:** 
  - Downloads the official master weather station dataset (`master.geojson`) from the [NREL EnergyPlus GitHub repository](https://github.com/NREL/EnergyPlus).
  - Parses and filters the features to extract the location names, geographic coordinates (latitude and longitude), and the direct download links to the `.epw` files.
  - Compiles and sorts them into a compacted JSON file.
- **Output Path:** Generates [weather_index.json](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/web/data/weather_index.json).
- **How to Run:**
  ```bash
  python scripts/build_weather_index.py
  ```

---
*Note: Make sure your environment has internet connectivity when running these scripts as they retrieve datasets dynamically from external repositories.*
