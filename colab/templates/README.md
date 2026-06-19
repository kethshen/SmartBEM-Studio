# EnergyPlus Templates Directory

This directory contains the baseline templates, modular HVAC system definitions, and catalog parameters that the backend uses to assemble generated models.

## Structure & File Registry

### 1. `Base.idf`
- **Description:** The foundation Input Data File (IDF) containing baseline building assumptions.
- **Contents:** Global simulation parameters, standard design days, baseline material/construction specifications, internal loads templates, and default reporting outputs.
- **Usage:** Serves as the starting canvas. The geometry engine and RAG pipeline write new zones, surfaces, windows, and custom constructions directly into this base file.

### 2. `catalog.json`
- **Description:** Configuration mapping catalog.
- **Usage:** Provides options mapping HVAC types (e.g., VAV, PSZ-AC, Ideal Loads) to template files and handles naming conventions.

### 3. `hvac/` (Subdirectory)
- **Description:** Modular HVAC snippet files.
- **Contents:** Includes standard system loops, schedules, and controller objects for specific heating/cooling setups (e.g., PSZ-AC, VAV, Ideal Loads).
- **Usage:** Dynamically merged into the baseline model when a user selects a specific HVAC system type on the frontend dashboard.

---
*Note: Make sure any modifications to `Base.idf` maintain syntax compatibility with EnergyPlus v25.2.0.*
