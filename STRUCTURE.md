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
│       ├── ekf.html              # EKF Estimation module (Plotly integration)
│       ├── architecture.html     # System architecture diagram
│       ├── diff_viewer.html      # Compare different generated IDF text outputs
│       ├── idf_viewer.html       # Visual IDF object inspector
│       └── about.html            # Project info & credits
│
├── backend_server/               # Backend (FastAPI server & orchestration pipeline)
│   ├── main_backend.ipynb        # Start here (main Colab backend server bootstrapper)
│   ├── requirements.txt          # Python dependencies
│   │
│   ├── core/                     # Core Python pipeline modules
│   │   ├── fastapi_server.py     # FastAPI app (HTTP endpoints & simulation/EKF routers)
│   │   ├── model_generator.py    # Ollama prompt orchestration (2-pass RAG)
│   │   ├── coordinates_calculator.py # Multi-zone coordinate & adjacency engine
│   │   ├── idf_assembler.py      # IDF file assembly from AI output
│   │   ├── chart_generator.py    # Plotly chart generation from simulation results
│   │   ├── weather_file_finder.py # EPW file download & caching from NREL S3
│   │   ├── material_dict_compiler.py # EnergyPlus dataset RAG indexer
│   │   ├── prompt_preprocessor.py # Prompt structuring preprocessor
│   │   └── index.json            # Pre-built dataset index for RAG
│   │
│   ├── idf_templates/            # EnergyPlus base templates
│   │   ├── Base.idf              # Base EnergyPlus template
│   │   ├── catalog.json          # HVAC system catalog
│   │   └── hvac/                 # Modular HVAC IDF snippets (psz_ac, split_ac, etc.)
│   │
│   └── eplus/                    # EnergyPlus Python bootstrap & parser tools
│       ├── eplus_util.py         # Full EnergyPlus utility library
│       ├── colab_bootstrap.py    # Colab environment setup helper (downloads EP release)
│       └── sql_explorer.py       # EnergyPlus SQLite result parser
│
├── EKF/                          # Extended Kalman Filter research module
│   ├── Real_EKF_ROBOD.py         # 10-state EKF estimation script (runs on Colab backend)
│   ├── EKF_System_Reference.md   # Mathematical reference & state-space derivation
│   ├── Datasets for EKF/         # ROBOD Room 3 sensor datasets for EKF analysis
│   └── Practise demos/           # Python worked examples and test cases
│
├── Datasets/                     # EnergyPlus IDD object libraries (RAG materials data)
├── EnergyPlus utility/           # Standalone Python wrappers for EnergyPlus executions
├── scripts/                      # Developer utilities (e.g. building weather index maps)
├── LLM_Prompt_Optimization_Guide.md # Prompt templates & optimization rules for building simulation
├── STRUCTURE.md                  # Annotated repository structure guide (this file)
├── user_description.md           # Production-grade 3-zone building specification example prompt
└── README.md                     # Main repository quickstart and setup instructions
```

## Runtime-only directories (gitignored, created automatically)

| Path | Created by | Contents |
|---|---|---|
| `backend_server/weather_cache/` | `weather_file_finder.py` | Downloaded EPW files (cached) |
| `backend_server/RunFiles/` | Simulation pipeline | Generated `.idf` files per job |
| `backend_server/sim_runs/` | EnergyPlus runner | Raw simulation output files |
| `backend_server/ollama_models/` | Ollama on Colab | Downloaded model weights |
| `backend_server/secrets.json` | You | Ngrok authtoken (never commit) |

---

## Detailed System Flowchart

Here is the complete end-to-end execution pipeline from raw prompt inputs to final dynamic charts:

```mermaid
flowchart TD
    %% Styling
    classDef llm fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b;
    classDef engine fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20;
    classDef db fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100;
    classDef ui fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    
    A["User Natural Language Prompt"] --> B["Prompt Preprocessor Gemma 3 12B"]
    class B llm;
    
    B -->|Restructures prompt into Global Settings and XML tags| C["Structured Intermediate Prompt"]
    
    %% RAG Pass 1
    C --> D["Pass 1 RAG Planner Ollama Keyword Extractor"]
    class D llm;
    
    D -->|Generates Search Keywords| E["Extracted Material Keywords"]
    C -->|Crawls for quoted strings| F["Pinned Database Materials"]
    
    E --> G["RAG Semantic Score Engine"]
    F --> G
    class G engine;
    
    H[("Local Datasets index.json")] -->|Retrieves catalog items| G
    class H db;
    
    G -->|Frequency-Based Token Intersection and Context Boosts| I["Candidate Material Menus Top 25"]
    
    %% RAG Pass 2
    C --> J["Pass 2 RAG Builder"]
    I --> J
    
    J -->|Pass 2A Extract Topology| K["Topology JSON Global Settings and Zone Lists"]
    class J llm;
    
    K -->|Loop for each Zone| L["Pass 2B Extract Zone Details"]
    class L llm;
    
    L -->|Maps materials from menus and subsurfaces| M["Zone details JSON"]
    
    M --> N["JSON Auto-Repairer Adds missing quotes and braces"]
    class N engine;
    
    N -->|Clean output| O["Merged Building Schema JSON"]
    
    %% Geometry Calculations
    O --> P["Multi-Zone Geometry Engine coordinates_calculator.py"]
    class P engine;
    
    P -->|3D CCW Vertex Sorting and Normal Vector plane projections| Q["Correct CCW Wall Vertices"]
    P -->|Splits partially attached walls into separate surfaces| R["Interzone Wall Boundary Mapping"]
    P -->|Clips and aligns windows and doors relative to wall edges| S["Subsurface Coordinates"]
    P -->|Generates Flat Pitched Gable or Pyramid Hip structures| T["Roof Surface Coordinates"]
    
    Q --> U["IDF Assembler OpenStudio and EnergyPlus"]
    R --> U
    S --> U
    T --> U
    class U engine;
    
    V[("IDF Base Template and HVAC Templates")] -->|Injects custom parameters| U
    class V db;
    
    U --> W["Assembled Valid idf File"]
    
    %% Weather & Execution
    W --> X["Runtime EPW Weather Fetcher"]
    class X engine;
    
    Y[("NREL S3 Weather DB or Custom Upload")] -->|Retrieves epw| X
    class Y db;
    
    X --> Z["EnergyPlus Simulation Engine on Google Colab"]
    class Z engine;
    
    Z -->|Simulates hourly heat-balance and sizing loop| AA["Output Database eplusout.sql"]
    class AA db;
    
    %% Post-processing
    AA --> AB["SQLite Output Parser"]
    class AB engine;
    
    AB -->|Relational JOIN query of ReportData and Time tables| AC["JSON Simulated Output Payload Wh to kWh"]
    
    AC --> AD["Plotly Interactive Dashboard Charts"]
    class AD ui;
```
