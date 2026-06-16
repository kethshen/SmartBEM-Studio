# Repository Structure

```
SmartHVAC-Studio/
│
├── web/                          # Web Dashboard (Vanilla JS/HTML/CSS)
│   ├── index.html                # Home page (entry point)
│   ├── style.css                 # Component styles
│   ├── design_system.css         # CSS design tokens (colours, typography)
│   ├── script.js                 # Global JS (sidebar, backend connection)
│   ├── assets/                   # Icons, images
│   ├── data/
│   │   └── weather_index.json    # Global EPW weather station database (~7000 stations)
│   └── pages/
│       ├── nlp.html              # Simulation Setup (main AI input page)
│       ├── results.html          # Results viewer (charts & plots)
│       ├── ekf.html              # EKF Estimation module
│       ├── architecture.html     # System architecture diagram
│       └── about.html            # Project info & credits
│
├── colab/                        # Backend (runs on Google Colab)
│   ├── Run_Connected_Experiment.ipynb  ← Start here
│   ├── EKF_Runner.ipynb          # Extended Kalman Filter notebook
│   ├── requirements.txt          # Python dependencies
│   │
│   ├── backend/                  # Core Python pipeline modules
│   │   ├── fastapi_server.py     # FastAPI app (HTTP endpoints)
│   │   ├── ai_generator.py       # Ollama prompt orchestration (2-pass RAG)
│   │   ├── geometry_util.py      # Multi-zone coordinate & adjacency engine
│   │   ├── idf_extractor.py      # IDF file assembly from AI output
│   │   ├── visualizer.py         # Plotly chart generation from simulation results
│   │   ├── weather_resolver.py   # EPW file download & caching from NREL S3
│   │   ├── dataset_indexer.py    # EnergyPlus dataset RAG indexer
│   │   └── index.json            # Pre-built dataset index for RAG
│   │
│   ├── templates/                # EnergyPlus base files
│   │   ├── Base.idf              # Base EnergyPlus template
│   │   ├── catalog.json          # HVAC system catalog
│   │   └── hvac/                 # Modular HVAC IDF snippets (psz_ac, vav, etc.)
│   │
│   └── eplus/                    # EnergyPlus Python utility library
│       ├── eplus_util.py         # Full EnergyPlus utility library
│       ├── colab_bootstrap.py    # Colab environment setup helper
│       └── sql_explorer.py       # EnergyPlus SQLite result parser
│
├── EKF/                          # Extended Kalman Filter research module
│   ├── Real_EKF.py               # EKF implementation (nonlinear state-space)
│   ├── EKF_System_Reference.md   # Mathematical reference & derivation
│   └── Practise demos/           # Worked examples and test cases
│
├── Datasets/                     # EnergyPlus IDD object library (used for RAG)
│
├── scripts/
│   └── build_weather_index.py    # Dev utility: regenerate web/data/weather_index.json
│                                 # from NREL EnergyPlus master GeoJSON
│
├── Demo_user_descriptions.md     # Sample building prompts for testing
├── .gitignore
└── README.md
```

## Runtime-only directories (gitignored, created automatically)

| Path | Created by | Contents |
|---|---|---|
| `colab/weather/` | `weather_resolver.py` | Downloaded EPW files (cached) |
| `colab/RunFiles/` | Simulation pipeline | Generated `.idf` files per job |
| `colab/sim_runs/` | EnergyPlus runner | Raw simulation output files |
| `colab/ollama_models/` | Ollama on Colab | Downloaded model weights |
| `colab/secrets.json` | You | Ngrok authtoken (never commit) |
