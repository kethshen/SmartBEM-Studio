# SmartHVAC Studio: Intelligent Building Modeling & Simulation

[![AI Models](https://img.shields.io/badge/AI--Engine-GPT--4o%20%7C%20Gemini%20%7C%20Llama%203.1-blueviolet)](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)
[![EnergyPlus](https://img.shields.io/badge/Simulation-EnergyPlus-green)](https://energyplus.net/)
[![Firebase](https://img.shields.io/badge/Cloud-Firebase-orange)](https://firebase.google.com/)

**SmartHVAC Studio** is an advanced framework for the modeling, simulation, and intelligent control of HVAC systems. It bridges the gap between complex engineering simulations (EnergyPlus) and intuitive user interaction through Natural Language Processing (NLP) and a modern web dashboard.

## 🏗 System Architecture (5-Layer Model)

1.  **Layer 1: Frontend UI** - Interactive web dashboard for configuration and visualization.
2.  **Layer 2: Cloud Coordination** - Firebase Firestore & Storage managing job queues and results.
3.  **Layer 3: Backend Worker** - Coordination engine polling for tasks and executing the pipeline.
4.  **Layer 4: AI Engine** - Multi-model integration (OpenAI, Gemini, HuggingFace) for intelligent building generation.
5.  **Layer 5: Simulation Engine** - EnergyPlus core for high-fidelity thermal and environmental calculations.

---

## 📂 Repository Structure

```text
SmartHVAC-Studio/
├── web/                    # Modern Dashboard (HTML/JS/Vanilla CSS)
├── colab/                  # Backend Execution Environment
│   ├── backend/            # Core Python modules (AI Pipelines, Firebase Connector)
│   ├── templates/          # Base IDF files and building templates
│   └── Run_Connected_Experiment.ipynb  # Main Execution Notebook
├── Datasets/               # Curated EnergyPlus objects for modular building construction
└── EnergyPlus utility/     # Custom helper library for EKF and simulation hooks
```

---

## 🚀 Key Features

*   **Natural Language Building Configuration**: Modify parameters using intuitive text prompts.
*   **Multi-Model AI Integration**: GPT-4o, Gemini 2.0, and HuggingFace Llama 3.1.
*   **Real-time Job Tracking**: Watch simulation progress live on the dashboard.
*   **IDF Diff Viewer**: Compare generated configurations side-by-side.

---

## 👨‍💻 Author

**Kethaka Shehan:** Final Year Mechanical Engineering Undergraduate

**Supervisor:** [Dr. D.H.S. Maithripala (@mugalan)](https://github.com/mugalan)

Faculty of Engineering, University of Peradeniya,
Sri Lanka.
