# Web Pages Directory

This directory contains the individual subpages composing the **SmartBEM Studio** dashboard.

## Pages Overview

### 1. `nlp.html` (Simulation Setup)
- **Purpose:** The main configuration hub where users interact with the tool.
- **Key Functions:**
  - Enter natural language descriptions of the building geometry, materials, and schedules.
  - Connect to the FastAPI Colab server using the Ngrok URL.
  - Run connectivity checks for AI APIs (Gemini, HuggingFace, OpenAI).
  - Search and select from 7,000+ global weather locations.
  - Browse and search the material dictionary to find valid EnergyPlus objects.

### 2. `results.html` (Results Dashboard)
- **Purpose:** The visualization interface to analyze thermal performance.
- **Key Functions:**
  - Renders time-series charts (via Plotly) displaying zone temperatures, outdoor temperatures, solar radiation, heating/cooling coil loads, and electricity consumption.
  - Connects to three.js viewers to display a 3D structural model of the generated zone geometry.
  - Links to the system log output and raw simulation files.

### 3. `ekf.html` (Extended Kalman Filter Dashboard)
- **Purpose:** Monitor parameter estimation tracking in real-time.
- **Key Functions:**
  - Interfaces with EKF runs to display state estimates (e.g., thermal capacitance, infiltration rates, internal gains) against true measurements.
  - Tracks convergence and error bounds.

### 4. `diff_viewer.html` (IDF Diff Viewer)
- **Purpose:** Visual debugging and transparency for generated models.
- **Key Functions:**
  - Compares the base template (`Base.idf`) with the newly generated building configuration.
  - Renders a line-by-line colored diff (red for removals, green for additions) showing exactly what the AI preprocessor and geometry engine modified in the EnergyPlus code.

### 5. `architecture.html` (System Architecture)
- **Purpose:** Academic documentation of the framework.
- **Key Functions:**
  - Displays the multi-layer diagram detailing the flow from the client browser through the Ngrok tunnel to the Google Colab GPU server running Ollama and EnergyPlus.

### 6. `about.html` (Credits & Context)
- **Purpose:** Project background.
- **Key Functions:**
  - Mentions the project details for the Faculty of Engineering, University of Peradeniya.
  - References the author (Kethaka Shehan) and supervisor (Dr. D.H.S. Maithripala).

---
*Note: All subpages share the global styling parameters defined in `style.css` and `design_system.css` located in the root of the `web/` folder.*
