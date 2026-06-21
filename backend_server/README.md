# SmartBEM Studio — Backend Server

This directory contains the simulation and AI processing backend for **SmartBEM Studio**. The backend is designed to run in a **Google Colab** environment to leverage GPU acceleration for the local LLM (Ollama) and run the Linux-native EnergyPlus simulation engine.

## Core Files & Entry Points

- **`main_backend.ipynb`:** The primary Jupyter notebook. It mounts Google Drive, boots Ollama, downloads the local LLM (`qwen3.5:9b`), pulls the FastAPI codebase from GitHub, and opens a public Ngrok tunnel to receive requests from the web dashboard.
- **`EMS_Cookbook.ipynb`:** Reference guide containing scripts and patterns for Energy Management System (EMS) control in EnergyPlus.
- **`requirements.txt`:** List of Python dependencies required to run the server.

## Directory Structure

- **`core/`:** Python files implementing the FastAPI server, the RAG preprocessor, the 3D geometry layout engine, and Plotly result visualizers.
- **`eplus/`:** The local copy of the advisor's EnergyPlus Python utility wrapper.
- **`idf_templates/`:** Base IDF configurations and modular HVAC object catalogs.
- **`weather_cache/`:** Cache folder where weather `.epw` files are downloaded during runtime.

## Runtime Directories (Gitignored)
These folders are generated automatically at runtime:
- `ollama_models/`: Cached LLM weights on Google Drive (persisted to avoid redownloading).
- `RunFiles/`: Dynamic folder containing generated `.idf` input files for active simulation jobs.
- `sim_runs/`: Output folders containing EnergyPlus raw results (SQLite databases, logs, errors, CSVs).

---
*For a detailed walkthrough of how this backend interacts with the frontend dashboard, see [smartbem_delivery_guide.md](../docs/smartbem_delivery_guide.md).*
