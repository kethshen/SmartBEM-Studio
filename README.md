# SmartBEM Studio

**Intelligent Building Modeling, Simulation & Parameter Estimation**  
*ME420 Final Year Project — Department of Mechanical Engineering, Faculty of Engineering, University of Peradeniya*

[![EnergyPlus](https://img.shields.io/badge/Simulation-EnergyPlus_25.1.0-green)](https://energyplus.net/)
[![Ollama](https://img.shields.io/badge/AI-Ollama_gemma3:12b-blueviolet)](https://ollama.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Colab](https://img.shields.io/badge/Runtime-Google_Colab-F9AB00)](https://colab.research.google.com/)

---

## What is this?

SmartBEM Studio lets you simulate a building's thermal energy performance by simply **describing it in plain English**. There is no complex software to learn - just type something like:

> *"Create a 3-zone office. Zone A is a 6x8m open office. Zone B is a 4x4m meeting room attached to the North wall of Zone A. Use concrete walls and double-glazed windows on the south."*

A local AI model (`gemma3:12b` via Ollama) running on a GPU-accelerated Google Colab server interprets your description, generates a valid EnergyPlus IDF model, runs a full thermal simulation, and returns interactive charts of zone temperatures, energy loads, and weather data - all in your browser.

The project also includes an **Extended Kalman Filter (EKF)** dashboard to estimate hidden building parameters (thermal capacitance, infiltration flow, heat transfer coefficient, and occupant counts) from real sensor data.

---

## Quick Start

### Prerequisites
- A **Google Account** (for Google Colab + Google Drive)
- **~8–10 GB free** in your Google Drive (to cache the Ollama model - first run only)
- A free **Ngrok account** (to tunnel the Colab server to the web)

---

### Step 1 — Open the Backend Notebook in Colab

1. Locate the backend notebook file at [backend_server/main_backend.ipynb](backend_server/main_backend.ipynb) within this repository.
2. Upload and open this notebook in **Google Colab**.
3. Set the runtime type to GPU: Go to **Runtime → Change runtime type** and ensure a **T4 GPU** accelerator is selected.

---

### Step 2 — Configure Ngrok in Colab Secrets (🔑)

Instead of manually creating local configuration files, we load credentials securely using Google Colab secrets:
1. Create a free account at [ngrok.com](https://ngrok.com/).
2. Copy your **Authtoken** from your Ngrok dashboard.
3. In your Colab notebook window, click the key icon (**🔑 Secrets**) in the left sidebar.
4. Add a new secret with:
   - **Name**: `NGROK_AUTHTOKEN`
   - **Value**: *[Paste your copied Ngrok authtoken]*
5. Turn **ON** the "Notebook access" toggle for this secret.

---

### Step 3 — Clone the Repo & Start the Local Server

1. Clone this repository to your local system.
2. Open the repository folder in **VS Code**.
3. Open your terminal in VS Code, navigate to the web directory by running:
   ```bash
   cd web
   ```
4. Start a local Python server by running:
   ```bash
   python -m http.server 8000
   ```
5. Open your web browser and navigate to:
   ```
   http://localhost:8000
   ```
   This will open the web frontend dashboard UI.

---

### Step 4 — Run the Backend Server

> [!IMPORTANT]
> **Follow the step-by-step instructions documented in [backend_server/main_backend.ipynb](backend_server/main_backend.ipynb).** 

1. Select **Runtime → Run All** to run all cells.
2. The notebook will automatically:
   - Mount your Google Drive (to cache the large LLM weights)
   - Install all required dependencies (FastAPI, PyNgrok, OpenStudio SDK, etc.)
   - Download the `gemma3:12b` model to your Drive (**first run only**; takes ~8–10 mins, direct server-to-server download with zero personal internet data charges)
   - Start the local Ollama service, FastAPI server, and Ngrok tunnel
3. In **Section 12. Run FastAPI server and Ngrok**, wait for the live URL to print:
   ```
   It will print a url similar to - https://xxxx-xxxx-xxxx.ngrok-free.app (example)
   ```
4. **Copy that Ngrok URL.**

---

### Step 5 — Connect & Run Building Energy Simulation

#### A. Simulation Setup Page
1. Navigate to the **Simulation Setup** page in the dashboard.
2. Paste the copied Ngrok URL (from Colab Section 12) into the frontend UI under **Step 1: Connect to ngrok Colab Server**, and click **Connect** (the status indicator turns green).
3. Enter your building description in **Step 2: Add Building Description** (refer to the example description format in [user_description.md](user_description.md)).
   *Note: A **Material Catalogue** and **Object Catalogue** are also included on this page for your reference to give you an idea of what materials and parameters can be simulated.*
4. Set your configurations (location, weather, dates) under **Step 3: Simulation Settings** and click **Queue Simulation**.

#### B. Results Page
1. Navigate to the **Results** page in the dashboard.
2. Wait for the job row in the simulations table to change status from `running...` to `done`.
3. Click that row in the table, and the interactive results charts (temperatures, weather variables, electricity/gas loads) will load below.
4. Use the tab menu items on the result card to explore the simulation outputs:
   - **View Full IDF Text** to inspect the raw EnergyPlus Input Data File generated.
   - **View Object Summary** to check the parsed structural details (zone areas, constructions, surfaces).
   - **View 3D Model** to render the interactive 3D model of the building.

---

### Step 6 — Run EKF Parameter Estimation

1. Navigate to the **EKF** page in the dashboard.
2. Ensure your backend connection is active (paste the Ngrok URL and click **Connect** if not already connected).
3. Under **Step 2: Run EKF Analysis**:
   - Select a dataset (e.g. ROBOD Room 3) or click **Upload CSV** to upload a custom building operation CSV.
   - Click **▶ Run EKF**.
4. The backend executes the EKF estimation asynchronously. Once complete:
   - Interactive Plotly time-series results will stream back to the dashboard, organized into distinct sections (**Measured States**, **Estimated Compact Parameters**, and **Recovered Physical Parameters**).
   - Zoom, pan, and hover over individual parameters (thermal capacitance $C_s$, infiltration flow $m_{inf}$, UA heat transfer coefficient, and occupant counts $N$) to analyze the room thermal behavior.

---

## Example Description

For a comprehensive test of the system's capabilities, refer to [user_description.md](user_description.md). 

This file contains a detailed, production-grade example of a **3-zone building** specifying:
* **Custom constructions & material layers** (e.g. brick walls with insulation boards, heavyweight concrete floors)
* **Specific window, door, and skylight layouts** (with dimensional offsets)
* **Custom roofing profiles** (gable heights, roof ridge orientations, pyramid hip roofs)
* **HVAC system selections** (Packaged Terminal Air Conditioners vs Split ACs)
* **Occupancy profiles, internal heat loads, lighting levels, and operational schedules** (daily weekday/weekend occupancy, lighting, and equipment timetables).

---

## Repository Structure

```
SmartBEM-Studio/
├── web/                  # Web Dashboard (HTML / CSS / JS)
├── backend_server/       # Backend — FastAPI server, AI pipeline, EnergyPlus wrapper
├── EKF/                  # Extended Kalman Filter module (algorithms, datasets)
├── Datasets/             # EnergyPlus object library (RAG library for building materials)
├── EnergyPlus utility/   # Python wrappers for compiling, running & retrieving simulations
├── scripts/              # Helper scripts and developer utilities
├── STRUCTURE.md          # File-by-file annotated structure guide of the codebase
└── user_description.md   # 3-zone building specification example prompt
```

---

## Author

**Kethaka Shehan** - Final Year Mechanical Engineering Undergraduate  
**Supervisor:** [Dr. D.H.S. Maithripala (@mugalan)](https://github.com/mugalan)

*Department of Mechanical Engineering, Faculty of Engineering, University of Peradeniya, Sri Lanka.*
