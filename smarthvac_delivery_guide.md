# SmartHVAC Studio — FYP Delivery & Repository Cleanup Guide

> **Author:** Kethaka Shehan | ME420 Final Year Project  
> **Architecture:** Vanilla JS Web UI → Ngrok Tunnel → FastAPI (Google Colab) → Ollama + EnergyPlus

---

## Part 1: What a Friend/Junior Needs to Do (The User Workflow)

This is the **complete, step-by-step experience** for anyone who wants to try your project. They need nothing installed on their machine except a web browser.

### Prerequisites (One-time, ~5 minutes)
- A Google Account (for Google Colab + Google Drive)
- ~8 GB of free space in their Google Drive (for the Ollama model)

---

### Step 1: Start the Backend on Google Colab

1. Go to the **SmartHVAC-Studio GitHub repository**.
2. Open the **`colab/Run_Connected_Experiment.ipynb`** notebook. Click the **"Open in Colab"** badge (or download and upload it to their own Google Colab).
3. In Colab, click **Runtime → Run All**.
4. The notebook will automatically:
   - Install all dependencies (`pip install fastapi pyngrok uvicorn ...`)
   - Mount their Google Drive
   - Download the Ollama model (`gemma3:4b`) to their Google Drive (~4.7 GB, **only on the first run**)
   - Start the EnergyPlus environment
   - Start the FastAPI server
   - **Print a public Ngrok URL** at the bottom of the last cell, like:
     ```
     ✅ SmartHVAC Backend is LIVE at: https://a1b2-34-56.ngrok-free.app
     ```
5. **Copy that URL.**

> **Note:** On the first run, the model download may take 10–15 minutes depending on internet speed. On every subsequent run, the model loads instantly from Google Drive.

> **Ngrok Account Required:** Ngrok requires a free account to get an Authtoken. The user must:
> 1. Sign up for a free account at [ngrok.com](https://ngrok.com).
> 2. Copy their **Authtoken** from the Ngrok dashboard.
> 3. Create a `secrets.json` file in the `colab/` directory of the repo (see the **Secrets Setup** section below for the exact format and location).

---

### Step 2: Open the Web Dashboard

1. Download or clone the full repository from GitHub.
2. Navigate into the `web/` folder.
3. Open `web/index.html` directly in any web browser. **No server or installation needed.**

---

### Step 3: Connect the Dashboard to Colab

1. On the web dashboard, find the **"Backend URL"** input field (on the main/NLP page).
2. Paste the Ngrok URL you copied from Colab.
3. Click **Connect**.
4. The status indicator will turn green: **"Backend Online ✅"**

---

### Step 4: Run a Simulation

1. Type a natural language prompt in the input box:
   > *"Create a 3-zone office building. Zone A is a 6x8m open office, Zone B is a 4x4m meeting room adjacent to Zone A on the east wall, and Zone C is a 3x3m server room adjacent to Zone B on the north. Use concrete walls and double-glazed windows on the south."*
2. Click **Generate & Simulate**.
3. Watch the dashboard update in real time:
   - AI extracts building geometry from your text
   - EnergyPlus runs the thermal simulation
   - Interactive Plotly charts appear showing zone temperatures, energy loads, and weather data
   - A 3D view of the building geometry is rendered

---

### Troubleshooting Quick Reference

| Problem | Fix |
|---|---|
| Colab session disconnected | Go back to Colab, click Runtime → Run All. Get new Ngrok URL and reconnect. |
| "Backend Offline" on dashboard | Make sure the Colab notebook is still running. Paste the correct Ngrok URL. |
| Model download is slow | First-time only. Wait for it to complete. Future runs load in seconds from Drive. |
| Simulation errors | Check the Colab cell output for error messages. |

---
---

## Part 2: Repository Cleanup — What to Add to `.gitignore`

These files and folders exist in the repo right now but should **not** be tracked by Git. They are personal, sensitive, auto-generated, or just development/testing artifacts.

> **Action:** Add these to your `.gitignore`. Do **NOT** delete them from your hard drive — `git rm --cached` will remove them from the repo history without deleting the actual files.

### 🔴 CRITICAL — Security / Secrets (Must Remove)

| Path | What It Is | Why Gitignore |
|---|---|---|
| `.env` | Environment variables file | Contains API keys, tokens, and secrets. **Never** commit this. |
| `colab/secrets.json` | User's personal Ngrok Authtoken | **This file must NOT be committed.** Each user creates their own version with their own Ngrok key (see Secrets Setup below). |
| `colab/serviceAccountKey.json` | Firebase Admin SDK key | A private key that grants full database access. Exposing this is a serious security breach. |
| `web/firebaseConfig.js` | Firebase web config | Contains your Firebase project API keys. *(Already in `.gitignore` — verify it's working.)* |

#### Secrets Setup — Instructions for the User

The `colab/secrets.json` file is **not included in the repo**. Each person who runs the project must create their own. Here is exactly what to do:

1. Sign up for a free account at [ngrok.com](https://ngrok.com).
2. Go to your Ngrok dashboard and copy your **Authtoken**.
3. In the repo, create a new file at exactly this path: **`colab/secrets.json`**
4. Paste the following content into it, replacing the placeholder with your real token:

```json
{
  "ngrok_authtoken": "YOUR_NGROK_AUTHTOKEN_HERE"
}
```

> ⚠️ Do **not** share this file or commit it to Git. It is already listed in `.gitignore` to prevent this.

---

### 🟠 Personal Notes & Study Material (Not Relevant to Users)

These are your personal learning notes, advisor meeting notes, and study materials. They are irrelevant to someone who just wants to run the project.

| Path | What It Is | Why Gitignore |
|---|---|---|
| `Obsidian/` | Entire Obsidian vault | Your personal knowledge base — advisor meeting notes, learning notes, project diary, literature reviews, presentations. Not part of the codebase. |
| `daily summary/` | Daily progress logs | Personal daily summaries of your work. Useful for you, irrelevant to a user. |
| `Research/` | Research literature folder | Literature review notebooks, PDFs, gap analysis, and presentation scripts. Academic, not operational. |
| `3. ME420_Evaluation scheme.pdf` | University grading rubric | A university document — has no place in a public codebase. |
| `SmartHVAC FYP Context Review.md` | AI context document | A large AI context/briefing document you used for development. Not for users. |
| `Roadmap_Suggestions.md` | Internal roadmap | Your personal feature roadmap. Not a user document. |
| `FastAPI_Ngrok_Explanation.md` | Your learning notes | Notes you wrote while learning FastAPI/Ngrok. Already baked into the codebase, not needed in the repo. |
| `useer_description.md` | Internal description file | Appears to be a personal working document, not user-facing. |
| `implementation_plan.md` (root) | AI-generated plan | Internal development plan created during coding sessions. |
| `patch_notebook.py` | Utility/dev script | A one-off script used during development. Not part of the product. |

---

### 🟡 Auto-Generated & Runtime Files (Clutter)

These are files created automatically when you run the code. They change every run and should never be tracked.

| Path | What It Is | Why Gitignore |
|---|---|---|
| `colab/sim_runs/` | EnergyPlus job output folders | Auto-generated per simulation run. Can be hundreds of MB. Every user generates their own in Colab. |
| `colab/RunFiles/` | IDF input files for runs | Auto-generated input files for each job. Same reason as sim_runs. |
| `colab/ollama_models/` | Downloaded Ollama model files | Gigabytes of model weights. Users download their own to their own Google Drive. |
| `colab/ollama.log` | Ollama server log | Runtime log file. Auto-generated each session. |
| `colab/weather.epw` | A single EPW weather file | An ad-hoc copy of a weather file. The canonical weather files are in `weather_files/`. |
| `colab/weather/` | Runtime weather directory | Auto-populated by the notebook at runtime. |
| `colab/__pycache__/` | Python bytecode cache | Auto-generated by Python. Never commit these. |
| `colab/backend/__pycache__/` | Python bytecode cache | Same as above. |
| `colab/eplus/__pycache__/` | Python bytecode cache | Same as above. |
| `.tmp.drivedownload/` | Google Drive sync temp | Google Drive's internal temp folder. Auto-generated. |
| `.tmp.driveupload/` | Google Drive sync temp | Google Drive's internal sync temp. Auto-generated. |
| `newplot.png` / `newplot (1).png` / `newplot (2).png` | Plotly screenshot exports | Auto-generated chart images from a Plotly session. |
| `generated_idf.idf` (root) | A generated IDF file | A test output at the root level. Not canonical. |
| `in.idf` (root) | A test IDF file | Appears to be a test input file. *(Already in `.gitignore`)* |
| `colab/jobs_job_*.csv` | Job summary CSV files | Auto-generated simulation result summaries. |

---

### 🟡 Development Testing Files (Not Part of Product)

| Path | What It Is | Why Gitignore |
|---|---|---|
| `colab/test_*.py` | All test Python scripts | `test_extract.py`, `test_geom.py`, `test_multizone.py`, `test_openstudio_builder.py`, `test_origins.py`, `test_sql.py`, `test_sql2.py`, `test_visualizer.py` — these are your personal debugging scripts. |
| `colab/test_*.html` | Test 3D geometry HTML exports | `test_geometry.html`, `test_multizone_3d.html`, `test_pitched.html` — large static HTML files (4.8 MB each!) generated while debugging the 3D viewer. |
| `colab/test_*.idf` | Test IDF files | `test_geometry.idf`, `test_multizone_output.idf`, `test_mz_3zone_os.idf`, etc. — manually created/tweaked IDF files from testing sessions. |
| `colab/verify_phase2.py` | Phase verification script | A one-off development checkpoint script. |
| `colab/rewrite_geom.py` | Geometry rewrite utility | A dev utility script used while building/debugging the geometry engine. |
| `colab/ollama_colab_youtube.py` | Learning/reference script | A script you wrote while learning Ollama + Colab. Not part of the product. |
| `colab/simulation_runner.py` | Standalone runner script | Appears to be an older/standalone version of the simulation logic. Check if it's still needed or superseded by `backend/`. |
| `colab/colab_notebook_cleanup.md` | Internal notes | Your personal notes about cleaning up the notebook. |
| `colab/EP Launch results/` | Local EnergyPlus output | Results from running EnergyPlus locally (not via Colab). |
| `Example IDF files/` | Reference IDF files | Sample/reference files you used while learning EnergyPlus. Not needed by users. |
| `EnergyPlus Documentation/` | EnergyPlus docs | Local copy of EnergyPlus documentation. Users can access this online. |
| `graphify-out/` | AI knowledge graph output | Auto-generated by the `graphify` tool used during development. Not needed by users. *(Already in `.gitignore` — verify it's working.)* |
| `docs/` | LaTeX and draft documents | Contains LaTeX source, compiled PDFs, and draft presentations for your academic report. Not operational code. *(Already in `.gitignore`)* |
| `scripts/desktop.ini` | Windows OS file | Windows shell metadata file. *(Already covered by `desktop.ini` rule)* |

---

### 🟢 What Should STAY in the Repo (The Clean Core)

After cleanup, your public repo should contain only these things:

```
SmartHVAC-Studio/
│
├── web/                         # ✅ The entire web dashboard
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   ├── design_system.css
│   ├── firebaseConfig.example.js  # ✅ Keep the EXAMPLE, not the real one
│   ├── assets/
│   ├── data/
│   │   └── weather_index.json   # ✅ Needed for weather selection UI
│   └── pages/
│       ├── nlp.html
│       ├── results.html
│       ├── architecture.html
│       ├── about.html
│       ├── ekf.html
│       └── idf_viewer.html
│
├── colab/
│   ├── Run_Connected_Experiment.ipynb  # ✅ The MAIN notebook users run
│   ├── backend/                         # ✅ All core Python modules
│   │   ├── __init__.py
│   │   ├── ai_generator.py
│   │   ├── dataset_indexer.py
│   │   ├── fastapi_server.py
│   │   ├── geometry_util.py
│   │   ├── idf_extractor.py
│   │   ├── index.json
│   │   ├── visualizer.py
│   │   └── weather_resolver.py
│   │   # firebase_connector.py — KEEP if still part of the pipeline
│   │   # openstudio_builder.py — Keep if used
│   ├── templates/               # ✅ Base IDF templates
│   │   ├── Base.idf
│   │   ├── catalog.json
│   │   └── hvac/
│   ├── requirements.txt         # ✅ Python dependencies
│   └── eplus/                   # ✅ EnergyPlus utility library
│       ├── eplus_util.py
│       ├── colab_bootstrap.py
│       ├── sql_explorer.py
│       └── __init__.py
│
├── EKF/                         # ✅ Extended Kalman Filter — part of the FYP
│   ├── Real_EKF.py
│   ├── EKF_System_Reference.md
│   ├── implementation_plan_for_EKF.md
│   └── Practise demos/
│
├── Datasets/                    # ✅ EnergyPlus object library (needed by backend)
├── weather_files/               # ✅ Sri Lanka EPW weather files
├── scripts/
│   └── build_weather_index.py   # ✅ Utility to rebuild the weather index
│
├── .gitignore                   # ✅
└── README.md                    # ✅ (needs to be updated — see Part 3)
```

---
---

## Part 3: Step-by-Step Repository Cleanup Process

Follow these steps in order. This is safe — nothing gets permanently deleted.

### Step 1: Update Your `.gitignore`

Add all the missing entries to your `.gitignore` file. Here is the **complete, clean `.gitignore`** to replace your current one:

```gitignore
# ============================================================
# SECURITY — Never commit these
# ============================================================
.env
*.env
colab/secrets.json
colab/serviceAccountKey.json
web/firebaseConfig.js

# ============================================================
# PERSONAL NOTES & ACADEMIC MATERIAL
# ============================================================
Obsidian/
daily summary/
Research/
3. ME420_Evaluation scheme.pdf
SmartHVAC FYP Context Review.md
Roadmap_Suggestions.md
FastAPI_Ngrok_Explanation.md
useer_description.md
implementation_plan.md
patch_notebook.py
docs/
EnergyPlus Documentation/

# ============================================================
# AUTO-GENERATED RUNTIME FILES
# ============================================================
colab/sim_runs/
colab/RunFiles/
colab/ollama_models/
colab/ollama.log
colab/weather/
colab/weather.epw
colab/jobs_job_*.csv
colab/EP Launch results/
colab/__pycache__/
colab/backend/__pycache__/
colab/eplus/__pycache__/
__pycache__/
.tmp.drivedownload/
.tmp.driveupload/
*.png
*.csv

# ============================================================
# DEVELOPMENT / TESTING ARTIFACTS
# ============================================================
colab/test_*.py
colab/test_*.html
colab/test_*.idf
colab/test_mz_os.idf
colab/test_sz_os.idf
colab/verify_phase2.py
colab/rewrite_geom.py
colab/ollama_colab_youtube.py
colab/simulation_runner.py
colab/colab_notebook_cleanup.md
Example IDF files/
graphify-out/
.agents/
in.idf
generated_idf.idf
newplot*.png

# ============================================================
# LATEX COMPILATION ARTIFACTS
# ============================================================
*.aux
*.log
*.out
*.toc
*.fls
*.fdb_latexmk
*.synctex.gz

# ============================================================
# OS & EDITOR JUNK
# ============================================================
.DS_Store
Thumbs.db
desktop.ini
Desktop.ini
.vscode/

# Node (future-proof)
node_modules/
```

---

### Step 2: Remove Already-Tracked Files from Git (Without Deleting Them)

Even after updating `.gitignore`, files that are **already tracked by Git** will keep showing up. You must "untrack" them. Run these commands in your terminal from the root of your repo:

```bash
# Remove the files from Git's index (tracking), but NOT from your hard drive
git rm --cached .env
git rm --cached colab/secrets.json
git rm --cached colab/serviceAccountKey.json
git rm --cached web/firebaseConfig.js

# For entire directories, use -r (recursive)
git rm -r --cached Obsidian/
git rm -r --cached "daily summary/"
git rm -r --cached Research/
git rm -r --cached docs/
git rm -r --cached graphify-out/
git rm -r --cached .agents/
git rm -r --cached colab/sim_runs/
git rm -r --cached colab/RunFiles/
git rm -r --cached colab/ollama_models/
git rm -r --cached "colab/EP Launch results/"
git rm -r --cached "Example IDF files/"
git rm -r --cached "EnergyPlus Documentation/"
git rm -r --cached colab/__pycache__/
git rm -r --cached .tmp.drivedownload/
git rm -r --cached .tmp.driveupload/

# Remove individual test and junk files
git rm --cached colab/ollama.log
git rm --cached colab/weather.epw
git rm --cached colab/verify_phase2.py
git rm --cached colab/rewrite_geom.py
git rm --cached colab/ollama_colab_youtube.py
git rm --cached colab/colab_notebook_cleanup.md
git rm --cached colab/simulation_runner.py
git rm --cached "SmartHVAC FYP Context Review.md"
git rm --cached Roadmap_Suggestions.md
git rm --cached FastAPI_Ngrok_Explanation.md
git rm --cached useer_description.md
git rm --cached implementation_plan.md
git rm --cached patch_notebook.py
git rm --cached "3. ME420_Evaluation scheme.pdf"
git rm --cached generated_idf.idf
git rm --cached in.idf
```

> ⚠️ **Important:** `git rm --cached` only removes the file from Git's tracking. Your actual files on your hard drive are **100% safe and untouched**.

---

### Step 3: Commit the Cleanup

After running the commands above, commit the cleanup as a single, dedicated commit:

```bash
git add .gitignore
git commit -m "chore: clean up repo — remove dev artifacts, personal notes, and secrets from tracking"
git push origin main
```

---

### Step 4: Update the README

After cleaning the repo, update `README.md` to reflect the new architecture (FastAPI + Ngrok, no Firebase dependency for the user) and add the exact user workflow from **Part 1** of this guide. The README should be the single source of truth for anyone landing on your GitHub page.

At minimum, the new README should have:
- A "Quick Start" section (the 4 steps from Part 1)
- An updated System Architecture diagram (5-Layer → 4-Layer, with Firebase replaced by Ngrok Tunnel)
- Prerequisites (Google Account, 8 GB Google Drive space)
- A note on the `secrets.json` setup (Ngrok Authtoken)

---

### Step 5: Verify the Clean State

After pushing, visit your repository on GitHub and verify:
- [ ] No `.env` or `secrets.json` files are visible
- [ ] No `Obsidian/`, `Research/`, or `daily summary/` folders are visible  
- [ ] No `colab/test_*.py` or `colab/test_*.html` files are visible
- [ ] No `colab/sim_runs/` folder is visible
- [ ] The `web/` folder, `colab/backend/`, `colab/templates/`, `colab/eplus/`, `Datasets/`, and `weather_files/` are all present and correct
- [ ] `web/firebaseConfig.example.js` is present (the example, NOT the real config)
- [ ] `colab/Run_Connected_Experiment.ipynb` is present and is the clean, latest version

---

*This guide was created on 2026-06-16 for the SmartHVAC Studio FYP by Kethaka Shehan, Faculty of Engineering, University of Peradeniya.*
