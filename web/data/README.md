# Web Data Directory

This directory stores all static data, dictionaries, registries, and reference files required by the frontend web dashboard.

## File Registry

### 1. `weather_index.json`
- **Description:** A consolidated database containing approximately ~7,000 global weather stations extracted from NREL's EnergyPlus weather repository.
- **Contents:** Location title, longitude, latitude, and direct download links to the corresponding `.epw` files.
- **Usage:** Populates the auto-complete search box in the Simulation Setup page so users can select locations globally.

### 2. `index.json`
- **Description:** Pre-built index dictionary cataloging materials and construction assemblies from the EnergyPlus object library.
- **Contents:** Names of materials, constructions, glazing, air gaps, shades, and blinds.
- **Usage:** Powers the **Material Dictionary** search engine on the Simulation Setup page, allowing users to copy valid EnergyPlus material names to use in prompts.

### 3. `reference_idf.idf`
- **Description:** A standard sample EnergyPlus Input Data File (IDF).
- **Usage:** Served as a reference model template during UI construction and configuration tests.

### 4. `reference_prompt.txt`
- **Description:** A text file containing sample prompts of typical building descriptions.
- **Usage:** Provides test inputs for validating natural language parsing behavior.

---
*Note: If you need to update the weather stations, run the `scripts/build_weather_index.py` utility script to download the latest master registry and overwrite `weather_index.json`.*
