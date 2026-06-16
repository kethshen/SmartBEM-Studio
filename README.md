# SmartHVAC Studio

**Intelligent Building Modeling, Simulation & Estimation**  
*ME420 Final Year Project — Faculty of Engineering, University of Peradeniya*

[![EnergyPlus](https://img.shields.io/badge/Simulation-EnergyPlus_24.1-green)](https://energyplus.net/)
[![Ollama](https://img.shields.io/badge/AI-Ollama_qwen3.5:9b-blueviolet)](https://ollama.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Colab](https://img.shields.io/badge/Runtime-Google_Colab-F9AB00)](https://colab.research.google.com/)

---

## What is this?

SmartHVAC Studio lets you simulate a building's thermal energy performance by simply **describing it in plain English**. There is no complex software to learn - just type something like:

> *"Create a 3-zone office. Zone A is a 6x8m open office. Zone B is a 4x4m meeting room attached to the North wall of Zone A. Use concrete walls and double-glazed windows on the south."*

A local AI model (Ollama `qwen3.5:9b`) interprets your description, generates a valid EnergyPlus IDF model, runs a full thermal simulation on Google Colab's GPU, and returns interactive charts of zone temperatures, energy loads, and weather data - all in your browser.

The project also includes an **Extended Kalman Filter (EKF)** module for estimating hidden building parameters from real sensor data.

---

## System Architecture

```
[Web Dashboard]  ──HTTP──►  [Ngrok Tunnel]  ──►  [FastAPI Server]  (Google Colab)
  (Browser)      ◄──JSON──                  ◄──       │
                                                       ├─► Ollama gemma3:4b  (AI)
                                                       ├─► Geometry Engine   (Python)
                                                       └─► EnergyPlus 25.1   (Simulation)
```

| Layer | Technology | Role |
|---|---|---|
| Frontend | Vanilla JS / HTML / CSS | Prompt input, 3D viewer, result charts |
| Tunnel | Ngrok | Exposes the Colab server to the browser |
| API Server | FastAPI + Uvicorn | Receives jobs, orchestrates the pipeline |
| AI Engine | Ollama `qwen3.5:9b` | Extracts geometry & materials from text |
| Simulation | EnergyPlus 25.1 | High-fidelity thermal simulation |

---

## Quick Start

### Prerequisites
- A **Google Account** (for Google Colab + Google Drive)
- **~8 GB free** in your Google Drive (to downoload the Ollama model - first run only)
- A free **Ngrok account** (to get your Authtoken)

---

### Step 1 — Create your `secrets.json`

Create a file at `colab/secrets.json` with your Ngrok Authtoken:

```json
{
  "ngrok_authtoken": "YOUR_NGROK_AUTHTOKEN_HERE"
}
```

> ⚠️ This file is in `.gitignore`. Never commit it.

---

### Step 2 — Start the Backend (Google Colab)

1. Open `colab/Run_Connected_Experiment.ipynb` in Google Colab.
2. Click **Runtime → Run All**.
3. The notebook will automatically:
   - Install all dependencies
   - Mount your Google Drive
   - Download `qwen3.5:9b` to your Drive (~8 GB, **first run only**)
   - Start the FastAPI server and Ngrok tunnel
4. At the end of the last cell, you'll see:
   ```
   ✅ SmartHVAC Backend is LIVE at: https://xxxx-xx-xx.ngrok-free.app
   ```
5. **Copy that URL.**

> 💡 On subsequent runs, the model loads instantly from Google Drive.

---

### Step 3 — Open the Web Dashboard

Download or clone the repository, then open `web/index.html` in any browser. No local server required.

---

### Step 4 — Connect & Simulate

1. Paste the Ngrok URL into the **Backend URL** field on the dashboard.
2. Click **Connect** — the status indicator turns green ✅.
3. Go to **Simulation Setup**, type your building description, and click **Generate & Simulate**.

---

### Troubleshooting

| Problem | Fix |
|---|---|
| Colab session disconnected | Click **Runtime → Run All** again. Copy the new Ngrok URL and reconnect. |
| "Backend Offline" on dashboard | Make sure the Colab notebook is still running and the URL is correct. |
| Model download is slow | First-time only (~10–15 min). Subsequent runs load from Drive in seconds. |

---

## Repository Structure

```
SmartHVAC-Studio/
├── web/          # Web Dashboard (HTML / CSS / JS)
├── colab/        # Backend — FastAPI server, AI pipeline, EnergyPlus runner
├── EKF/          # Extended Kalman Filter module
├── Datasets/     # EnergyPlus object library (used for RAG)
└── scripts/      # Developer utilities
```

For the full annotated breakdown of every file and folder, see [STRUCTURE.md](STRUCTURE.md).

## Key Technical Features

- **Two-Pass Agentic RAG:** The AI pipeline runs two Ollama passes — a *Planner* pass to extract zone layouts and a *Builder* pass to resolve material/window/schedule details from the EnergyPlus dataset library.
- **Multi-Zone Geometry Engine:** Automatically computes `LowerLeftCorner` coordinates and Counter-Clockwise vertex ordering for any number of adjacent zones, meeting EnergyPlus's strict geometric requirements.
- **Runtime EPW Download:** Weather files are fetched directly from NREL's S3 at simulation time based on the user's selection — no large EPW files committed to the repo.
- **Extended Kalman Filter (EKF):** Estimates latent building parameters (thermal capacitance, infiltration rate, internal heat gain) from time-series sensor data using a nonlinear state-space model.

---

## Author

**Kethaka Shehan** - Final Year Mechanical Engineering Undergraduate  
**Supervisor:** [Dr. D.H.S. Maithripala (@mugalan)](https://github.com/mugalan)

Department of Mechanical Engineering, Faculty of Engineering, University of Peradeniya, Sri Lanka.
