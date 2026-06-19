# EnergyPlus API Wrapper (Operational Copy)

This directory is an operational copy of the **EnergyPlus Python Utility** library. 

> [!NOTE]
> This folder is placed directly inside `colab/` to serve as a local python module (`eplus`) so the FastAPI backend can import it directly. The primary copy and development guide are located in the [EnergyPlus utility/](../EnergyPlus%20utility/) folder at the root of the repository.

## Core Modules

- **`__init__.py`:** Exposes the bootstrap method and handles lazy-loading.
- **`colab_bootstrap.py`:** Prepares the system environment, downloads EnergyPlus 25.1.0/25.2.0, and sets library path variables.
- **`eplus_util.py`:** Contains the `EPlusUtil` helper class that wraps simulation runs, registers callbacks, and interacts with actuators/variables.
- **`sql_explorer.py`:** Helper to extract pandas dataframes directly from `eplusout.sql`.

---
*For full usage guidelines, API tables, and callbacks reference, consult the main [ADVISOR_README.md](../EnergyPlus%20utility/ADVISOR_README.md).*
