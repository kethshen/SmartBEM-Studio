# EnergyPlus Reference Datasets

This directory contains reference object libraries (in `.idf` and `.dat` formats) extracted from the official **EnergyPlus v25.2.0** installation.

> [!NOTE]
> These datasets are used by the SmartBEM Studio backend (primarily in the two-pass RAG and construction resolving pipelines) to retrieve standardized properties for building materials, construction assemblies, HVAC configurations, and schedules.

## Directory Structure & Contents

- **`Building Materials and Construction/`**
  - Standard material definitions (e.g., concrete, brick, insulation, wood) and composite construction layers used to define thermal envelopes.
- **`Economics and Reporting/`**
  - Predefined tariff structures, lifecycle cost parameters, and standard report configurations.
- **`Fluid and Thermal Properties/`**
  - Reference data for thermophysical properties of various liquids and gases (e.g., water, glycols) used in HVAC loop modeling.
- **`Ground Source Systems/`**
  - Reference datasets for modeling ground-coupled heat exchangers (GLHEs).
- **`HVAC Equipment and Performance/`**
  - Performance curves, curves for chillers, boilers, DX coils, and packaged heat pump equipment.
- **`Renewable Energy and Power Generation/`**
  - Solar collectors, photovoltaic module performance data (calibrated to the Sandia PV database), and generator properties.
- **`Schedules and Environmental Factors/`**
  - Environmental impact factors, standard US holidays, DST schedules, and predefined precipitation schedules.
- **`Window and Glazing Systems/`**
  - Glazing materials, gas fills, window blinds, screens, and standard window assemblies.

## Usage in SmartBEM Studio

During the AI generation phase:
1. The **two-pass prompt preprocessor** parses the user's natural language input.
2. It queries these libraries (specifically the material and construction datasets) to find valid EnergyPlus matching object names and properties.
3. It integrates these definitions into the final generated building description to ensure the EnergyPlus engine can compile and simulate the IDF file successfully without missing reference dependencies.

---
*Source: Official EnergyPlus v25.2.0 Installation Datasets.*
