# SmartHVAC Studio: Intelligent Building Modeling & Simulation

[![AI Models](https://img.shields.io/badge/AI--Engine-Local--Ollama-blueviolet)](https://ollama.com/)
[![EnergyPlus](https://img.shields.io/badge/Simulation-EnergyPlus-green)](https://energyplus.net/)
[![Firebase](https://img.shields.io/badge/Cloud-Firebase-orange)](https://firebase.google.com/)

**SmartHVAC Studio** is an advanced framework for the modeling, simulation, and intelligent control of HVAC systems developed for a Final Year Project (FYP). It bridges the gap between complex engineering simulations (EnergyPlus) and intuitive user interaction through Natural Language Processing (NLP) powered by local LLMs, and a modern web dashboard.

## 🏗 System Architecture (5-Layer Model)

1.  **Layer 1: Frontend UI** - An interactive web dashboard (Vanilla JS/CSS) for configuring prompts, viewing 3D building geometry, and visualizing simulation charts.
2.  **Layer 2: Cloud Coordination** - Firebase Firestore & Storage acting as the bridge, managing job queues, transferring IDF files, and syncing SQLite results back to the client.
3.  **Layer 3: Backend Worker (Google Colab)** - A persistent background task running in Google Colab that polls the cloud for jobs, handles dynamic geometry generation, and coordinates the pipeline.
4.  **Layer 4: AI Engine (Local Ollama)** - Fully private, local Large Language Models (like `gemma3:4b`) deployed via Ollama. It extracts multi-zone dimensions, material parameters, and adjacency layouts from natural language prompts.
5.  **Layer 5: Simulation Engine (EnergyPlus)** - EnergyPlus executes the dynamically assembled `.idf` files, performing high-fidelity thermal simulations and outputting `eplusout.sql` databases.

---

## 📂 Repository Structure

```text
SmartHVAC-Studio/
├── web/                    # Modern Dashboard (HTML/JS/Vanilla CSS)
├── colab/                  # Backend Execution Environment (Colab/Local)
│   ├── backend/            # Core Python modules (ai_generator, geometry_util, visualizer)
│   ├── templates/          # Base IDF files, HVAC modules, and building templates
│   ├── sim_runs/           # Working directories for individual EnergyPlus jobs
│   └── Run_Connected_Experiment.ipynb  # Main Execution Notebook
├── Datasets/               # Curated EnergyPlus objects for modular building construction
└── EnergyPlus utility/     # Custom helper library for EKF and simulation hooks
```

---

## 🚀 Key Features

*   **Natural Language Building Configuration**: Define room dimensions, windows, materials, and schedules using intuitive text prompts.
*   **Local AI Generation**: Fully private, cost-free building configuration using local LLMs (e.g., `gemma3:4b`) via Ollama.
*   **Multi-Zone Geometry Engine**: Dynamically calculates coordinate systems and automatically detects wall adjacencies for complex building layouts from AI JSON outputs.
*   **EnergyPlus 3D Validation**: Strict enforcement of `LowerLeftCorner` and Counter-Clockwise vertex ordering to guarantee simulation stability and accurate 3D plotting.
*   **Automated SQLite Parsing & Plotting**: Intelligent querying of `eplusout.sql` to generate interactive `plotly` charts for zone temperatures, energy loads, and weather data.
*   **Real-time Job Tracking**: Watch simulation progress live on the dashboard, connected seamlessly via Firebase.

---

## 👨‍💻 Author

**Kethaka Shehan:** Final Year Mechanical Engineering Undergraduate

**Supervisor:** [Dr. D.H.S. Maithripala (@mugalan)](https://github.com/mugalan)

Faculty of Engineering, University of Peradeniya,
Sri Lanka.
