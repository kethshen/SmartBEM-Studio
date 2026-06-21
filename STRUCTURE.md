# Repository Structure

```
SmartBEM-Studio/
│
├── web/                          # Web Dashboard (Vanilla JS/HTML/CSS)
│   ├── index.html                # Home page (entry point)
│   ├── style.css                 # Component styles
│   ├── design_system.css         # CSS design tokens (colours, typography)
│   ├── script.js                 # Global JS (sidebar, backend connection)
│   ├── assets/                   # Icons, images
│   ├── data/
│   │   ├── weather_index.json    # Global EPW weather station database (~7000 stations)
│   │   └── index.json            # Material & construction dictionary index for UI search
│   └── pages/
│       ├── nlp.html              # Simulation Setup (main AI input page)
│       ├── results.html          # Results viewer (charts & plots)
│       ├── ekf.html              # EKF Estimation module
│       ├── architecture.html     # System architecture diagram
│       └── about.html            # Project info & credits
│
├── backend_server/                 # Backend (runs on Google Colab / server)
│   ├── main_backend.ipynb        # Start here (main server bootstrapper)
│   ├── EKF_Runner.ipynb          # Extended Kalman Filter notebook
│   ├── requirements.txt          # Python dependencies
│   │
│   ├── core/                     # Core Python pipeline modules
│   │   ├── fastapi_server.py     # FastAPI app (HTTP endpoints)
│   │   ├── model_generator.py    # Ollama prompt orchestration (2-pass RAG)
│   │   ├── coordinates_calculator.py # Multi-zone coordinate & adjacency engine
│   │   ├── idf_assembler.py      # IDF file assembly from AI output
│   │   ├── chart_generator.py    # Plotly chart generation from simulation results
│   │   ├── weather_file_finder.py # EPW file download & caching from NREL S3
│   │   ├── material_dict_compiler.py # EnergyPlus dataset RAG indexer
│   │   ├── prompt_preprocessor.py # Prompt structuring preprocessor
│   │   └── index.json            # Pre-built dataset index for RAG
│   │
│   ├── idf_templates/            # EnergyPlus base files
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
| `backend_server/weather_cache/` | `weather_file_finder.py` | Downloaded EPW files (cached) |
| `backend_server/RunFiles/` | Simulation pipeline | Generated `.idf` files per job |
| `backend_server/sim_runs/` | EnergyPlus runner | Raw simulation output files |
| `backend_server/ollama_models/` | Ollama on Colab | Downloaded model weights |
| `backend_server/secrets.json` | You | Ngrok authtoken (never commit) |
