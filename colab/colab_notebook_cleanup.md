# Colab Notebook Cleanup Guide

> Step-by-step instructions to clean up `Run_Connected_Experiment.ipynb`.
> Follow the cell numbers as they currently appear (top-to-bottom) in the notebook.

---

## Current Cell Layout (What You Have Now)

| # | Section Header | Content | Verdict |
|---|---|---|---|
| 1 | `# 1. Mount google drive` | `drive.mount(...)` | ✅ KEEP |
| 2 | *(no header)* | `os.chdir(colab_dir)`, copies `eplus` utility | ✅ KEEP |
| 3 | `# 2. Ollama local run` | `apt install zstd pciutils lshw` | ✅ KEEP |
| 4 | *(no header)* | `curl ... ollama install.sh` | ✅ KEEP |
| 5 | *(no header)* | `pip install ollama` | ✅ KEEP |
| 6 | *(no header)* | `!pkill ollama` | ⚠️ KEEP but move (see below) |
| 7 | *(no header)* | `os.environ['OLLAMA_HOST']` | ✅ KEEP |
| 8 | *(no header)* | Copy model weights from Drive → SSD | ✅ KEEP |
| 9 | *(no header)* | `nohup ollama serve` | ✅ KEEP |
| 10 | *(no header)* | `curl http://localhost:11434` (test) | ✅ KEEP |
| 11 | *(no header)* | `ollama pull gemma3:4b` | 🗑️ **DELETE** |
| 12 | *(no header)* | `ollama rm gemma3:270m` | 🗑️ **DELETE** |
| 13 | *(no header)* | `ollama list` | ✅ KEEP (useful sanity check) |
| 14 | *(no header)* | Ollama quick test (`what is rgb`) | ✅ KEEP (optional, good smoke test) |
| 15 | *SmartHVAC Backend header* | Markdown title cell | ✅ KEEP |
| 16 | `## 1. Mount drive` | Markdown header | 🗑️ **DELETE** (duplicate heading) |
| 17 | *(code)* | **🚨 THE DANGEROUS CELL** — Base.idf fixer + `rm -rf` | ⚠️ **MODIFY** (see below) |
| 18 | *(code)* | `!python verify_phase2.py` | ✅ KEEP (optional) |
| 19 | `## 2. Setup Environment` | `pip install -r requirements.txt` + eplus utility | ✅ KEEP |
| 20 | *(code)* | `sys.path.append(os.getcwd())` | 🗑️ **DELETE** (already done in Cell 2) |
| 21 | `## 3. Authentication` | Check `serviceAccountKey.json` | ✅ KEEP |
| 22 | `## 3. Initialize Modules` | `import firebase_admin` etc. | ✅ KEEP |
| 23 | *(code)* | Init `FirebaseConnector`, `AIPipelines` | ✅ KEEP |
| 24 | `## 4. Verify epw` | Check weather file exists | ✅ KEEP |
| 25 | `## 5. Verify Base.idf` | **Downloads Base.idf from Firebase Storage** + `generate_and_upload_diff()` | ⚠️ **MODIFY** (see below) |
| 26 | `## 6. Main polling loop` | The main loop | ✅ KEEP |

---

## Step-by-Step Instructions

### Step 1: Delete the `ollama pull` cell

> [!IMPORTANT]
> Cell 11 runs `!ollama pull gemma3:4b`. This downloads ~3 GB from the internet every session. You already copy the model from Drive in Cell 8, so this is redundant and wastes time.

**Action:** Delete the entire cell containing:
```python
!ollama pull gemma3:4b
```

---

### Step 2: Delete the `ollama rm` cell

> Cell 12 runs `!ollama rm gemma3:270m`. This was a one-time cleanup of an old model. It's no longer needed.

**Action:** Delete the entire cell containing:
```python
!ollama rm gemma3:270m
```

---

### Step 3: Delete the duplicate "## 1. Mount drive" markdown cell

> Cell 16 is a markdown cell that says `## 1. Mount drive`. This is a leftover duplicate of the section at the top. It does nothing and confuses the reading order.

**Action:** Delete this markdown cell.

---

### Step 4: 🚨 Fix the DANGEROUS "Base.idf fixer" cell (Cell 17)

> [!CAUTION]
> This is the cell that was **destroying your simulation output**. It contains a loop that strips everything from `Zone,` onwards in `Base.idf`, which deletes all Schedules, HVAC, Thermostat, and `Output:Variable` statements.

**Current code (DANGEROUS):**
```python
# 2. Forcefully fix Base.idf directly on the server to strip the Duplicate Zone
base_path = 'templates/Base.idf'
if os.path.exists(base_path):
    with open(base_path, 'r') as f:
        lines = f.readlines()

    # Strip everything from the first "Zone," onwards to remove duplicated geometry
    with open(base_path, 'w') as f:
        for i, line in enumerate(lines):
            if "Zone," in line.strip() and "Zone ONE" not in line and "Zone," == line.strip():
                pass # Just a safety
            if line.strip() == "Zone,":
                break
            f.write(line)
    print("Fixed Base.idf successfully!")
```

**Replace the ENTIRE cell with:**
```python
import os, sys, importlib, shutil

# 1. Clean up stale simulation folders
for folder in ['../sim_runs', 'sim_runs', 'RunFiles']:
    if os.path.exists(folder):
        shutil.rmtree(folder)

# 2. Force Python to reload the latest python files from disk
sys.path.append(os.getcwd())
import backend.geometry_util as geometry_util
import simulation_runner
importlib.reload(geometry_util)
importlib.reload(simulation_runner)

print("✅ Cache cleared and modules reloaded. Ready to simulate.")
```

> [!NOTE]
> We removed the Base.idf fixer because we already removed the hardcoded geometry from `Base.idf` itself. There's no longer a `Zone,` line to find, so the fixer was either doing nothing or actively harmful.

---

### Step 5: Delete the duplicate `sys.path.append` cell (Cell 20)

> Cell 20 just does `sys.path.append(os.getcwd())`. This is already done in Cell 2 and again in the replacement code from Step 4.

**Action:** Delete the entire cell containing:
```python
sys.path.append(os.getcwd())
```

---

### Step 6: 🚨 Fix the "Download Base.idf from Firebase" cell (Cell 25)

> [!WARNING]
> This cell downloads `Base.idf` from Firebase Storage, **overwriting your local copy on Google Drive**. If the version in Firebase Storage is outdated (e.g., still has the old hardcoded geometry, or missing placeholders), it will undo all our fixes every time you run it.

**Current problematic function:**
```python
def download_template(template_name="Base.idf"):
    blob = bucket.blob(f"templates/{template_name}")
    blob.download_to_filename(f"templates/{template_name}")  # ← OVERWRITES local file!
```

**You have two options:**

**Option A (Recommended): Delete the download, keep only `generate_and_upload_diff()`**

Replace the cell with:
```python
import difflib

def generate_and_upload_diff(base_path, new_path, job_id):
    """Generates an HTML diff between Base.idf and in.idf and uploads it."""
    try:
        with open(base_path, 'r') as f:
            base_lines = f.readlines()
        with open(new_path, 'r') as f:
            new_lines = f.readlines()

        diff_html = difflib.HtmlDiff().make_file(
            base_lines, new_lines,
            fromdesc='Base Template',
            todesc='Generated IDF',
            context=True,
            numlines=3
        )

        diff_path = f"jobs/{job_id}/diff.html"
        with open(diff_path, "w") as f:
            f.write(diff_html)

        bucket = storage.bucket()
        blob = bucket.blob(f"jobs/{job_id}/diff.html")
        blob.upload_from_filename(diff_path, content_type="text/html")
        print(f"   📊 Uploaded Diff HTML to Storage.")
        return True
    except Exception as e:
        print(f"   ❌ Failed to generate diff: {e}")
        return False

# Verify Base.idf exists locally (from Drive, NOT from Firebase Storage)
base_path = 'templates/Base.idf'
if os.path.exists(base_path):
    print(f"✅ Base.idf found: {base_path} ({os.path.getsize(base_path)/1024:.1f} KB)")
else:
    print(f"❌ Base.idf NOT found at {base_path}!")
```

**Option B: Upload your fixed local copy TO Firebase Storage (run once)**

If you want Firebase Storage to have the latest version, run this **once** after the fix:
```python
bucket = storage.bucket()
blob = bucket.blob("templates/Base.idf")
blob.upload_from_filename("templates/Base.idf", content_type="text/plain")
print("✅ Uploaded fixed Base.idf to Firebase Storage.")
```
Then switch to Option A permanently.

---

### Step 7: Move `pkill ollama` to the correct position (Cell 6)

> Cell 6 (`!pkill ollama`) is currently between the `pip install ollama` and the `OLLAMA_HOST` env var cells. This is fine, but it should be placed **right before** the `nohup ollama serve` cell (Cell 9) so the flow reads:
> kill old → set env → copy models → start server

**Action:** Move Cell 6 so it appears immediately before Cell 9 (`nohup ollama serve`).

---

## Final Clean Cell Order

After cleanup, your notebook should have this flow:

```
Section 1: Environment Setup
  ├── Mount Google Drive
  ├── Set working directory + copy eplus
  ├── Install zstd, pciutils
  ├── Install Ollama engine
  └── pip install ollama

Section 2: Ollama Boot
  ├── Set OLLAMA_HOST env var
  ├── pkill ollama (kill stale instances)
  ├── Copy model weights Drive → SSD
  ├── nohup ollama serve
  ├── curl localhost:11434 (test)
  ├── ollama list (verify)
  └── Quick LLM test (optional)

Section 3: Backend Setup
  ├── Clean stale folders + reload modules (FIXED Cell 17)
  ├── pip install -r requirements.txt + eplus utility
  ├── Check serviceAccountKey.json
  ├── Initialize FirebaseConnector + AIPipelines
  ├── Verify weather file
  └── Verify Base.idf (NO download, just check exists)

Section 4: Run
  └── Main polling loop
```
