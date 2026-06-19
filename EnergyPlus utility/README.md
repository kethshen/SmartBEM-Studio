# EnergyPlus Python Utility Library

This directory contains the original **EnergyPlus Python Utility** helper library developed by project advisor **[Dr. D.H.S. Maithripala (@mugalan)](https://github.com/mugalan)**.

> [!NOTE]
> In the SmartHVAC Studio architecture, the core python files of this package are located inside `colab/eplus/` to serve as a local module for the FastAPI backend server running on Google Colab. This root directory serves as a reference copy and documents the underlying utility API.

## Core Modules & Features

1. **`eplus_util.py` (`EPlusUtil`):**
   - Implements a high-level wrapper to load models, configure simulation parameters, and run EnergyPlus.
   - Provides a unified **runtime callback registry** to inject custom python functions (e.g., EKF/Kalman tracking, custom actuation) at different timestep hooks without subclassing.
   - Features helper methods to query and log runtime actuators, variables, and meters.

2. **`colab_bootstrap.py` (`prepare_colab_eplus`):**
   - Automates the silent installation of EnergyPlus system dependencies on Linux/Ubuntu (Google Colab runtimes).
   - Configures path environment variables (`LD_LIBRARY_PATH`, `ENERGYPLUSDIR`) dynamically so `pyenergyplus` can be imported cleanly.

3. **`sql_explorer.py` (`EPlusSqlExplorer`):**
   - Parses the EnergyPlus SQLite output database (`eplusout.sql`).
   - Extracts time-series dataframes and exports them to CSV for plotting and post-processing.

## API Documentation & Usage
The original repository readme has been renamed to **[ADVISOR_README.md](ADVISOR_README.md)**. Open it for:
- Detailed installation guidelines (Colab vs. Local)
- Quickstart script examples
- Callback registration syntax
- Actuator, variable, and meter logging reference tables
- Kalman/EKF configuration options

---
*Source: [mugalan/energy-plus-utility](https://github.com/mugalan/energy-plus-utility)*
