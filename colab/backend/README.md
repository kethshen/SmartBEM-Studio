# Backend Core Modules

This directory contains the Python modules that implement the API server, AI prompt engineering, geometry generation, and results visualization.

## Module Registry

### 1. `fastapi_server.py`
- **Description:** Implements the REST API endpoints.
- **Key Functions:**
  - `/simulate`: Primary endpoint that receives the natural language prompt, triggers the generation, runs EnergyPlus, and returns the visualization data.
  - `/test-connection`: Health check endpoint.
  - Integrates the Ngrok library to establish a public tunnel.

### 2. `ai_generator.py`
- **Description:** Orchestrates the LLM prompt formatting.
- **Key Functions:**
  - Implements the **two-pass RAG preprocessor** to extract building parameters.
  - Queries local Ollama API (`qwen3.5:9b`).

### 3. `geometry_util.py`
- **Description:** Coordinates zone math.
- **Key Functions:**
  - Converts textual zone descriptions into concrete spatial layouts (X, Y, Z coordinates).
  - Handles adjacencies, partition walls, window-to-wall ratios (WWR), and door locations.

### 4. `idf_extractor.py`
- **Description:** Assembles the output model.
- **Key Functions:**
  - Merges the geometry layout and material properties into a valid EnergyPlus Input Data File (`.idf`) using the template base.

### 5. `weather_resolver.py`
- **Description:** Resolves geographic locations.
- **Key Functions:**
  - Matches the user's weather search to latitude/longitude coordinates and fetches the corresponding `.epw` weather file from NREL's S3 storage.

### 6. `dataset_indexer.py` & `index.json`
- **Description:** Pre-compiles building material libraries.
- **Key Functions:**
  - Extracts construction layers, window glass, and thermal masses from the EnergyPlus dataset and saves them in `index.json` to feed the RAG search.

### 7. `visualizer.py`
- **Description:** Post-processes simulation outputs.
- **Key Functions:**
  - Queries the resulting `eplusout.sql` SQLite file and generates interactive Plotly timeseries charts.

---
*All endpoints are called asynchronously to prevent request timeouts during long-running EnergyPlus simulations.*
