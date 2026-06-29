import os
import sys
import threading
import uuid
import time
import tempfile
from fastapi import FastAPI, BackgroundTasks, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn
import nest_asyncio
from pyngrok import ngrok

# Setup scratch directories and redirect standard output/error to backend.log
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "smartbem_sim_runs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(OUTPUT_DIR, "backend.log")

class TeeStream:
    def __init__(self, filename, original_stream):
        self.file = open(filename, "a", encoding="utf-8", buffering=1)
        self.original_stream = original_stream

    def write(self, message):
        if self.original_stream:
            self.original_stream.write(message)
        self.file.write(message)

    def flush(self):
        if self.original_stream:
            self.original_stream.flush()
        self.file.flush()

# Import our custom modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.model_generator import AIPipelines
import energyplus_simulator

# Initialize FastAPI app
app = FastAPI(title="SmartBEM Studio Backend API")

# Allow CORS so the frontend can communicate directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the temp directory under /results static endpoint
app.mount("/results", StaticFiles(directory=OUTPUT_DIR), name="results")

# In-memory job tracking
jobs_db = {}

# Pydantic models for incoming requests
class SimulateRequest(BaseModel):
    prompt: str
    settings: dict

class SimulateResponse(BaseModel):
    job_id: str
    status: str

def run_simulation_pipeline(job_id: str, prompt: str, settings: dict):
    """
    Background worker that runs the full AI -> EnergyPlus pipeline.
    """
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = TeeStream(LOG_FILE_PATH, sys.stdout)
    sys.stderr = TeeStream(LOG_FILE_PATH, sys.stderr)

    try:
        jobs_db[job_id]["status"] = "processing"
        
        # 1. AI Generation (Generate IDF)
        print(f"[{job_id}] Starting AI Generation...")
        ai = AIPipelines(secrets_path="secrets.json", template_path="idf_templates/Base.idf")
        # Ensure we use ollama by default or what is in settings
        model_type = settings.get("model_type", "ollama")
        idf_content = ai.generate_idf_from_text(prompt, settings, model_type=model_type)
        
        if not idf_content:
            raise Exception("AI Pipeline failed to generate an IDF.")
        if idf_content.strip().startswith("!"):
            raise Exception(f"AI Generation Error:\n{idf_content}")

        # Save generated IDF to a temporary file outside the run directory
        # (Because energyplus_simulator will wipe the run directory before starting)
        raw_idf_path = os.path.join(OUTPUT_DIR, f"{job_id}_raw.idf")
        with open(raw_idf_path, "w", encoding="utf-8") as f:
            f.write(idf_content)
        
        job_dir = os.path.join(OUTPUT_DIR, job_id)

        # 2. Run EnergyPlus Simulation
        print(f"[{job_id}] Starting EnergyPlus Simulation...")
        epw_url = settings.get("epw_url")
        
        # We need to resolve the EPW to a local path (Download it if necessary)
        from core.weather_file_finder import resolve_epw
        epw_local_path = resolve_epw(settings, cache_dir="../weather_cache")
        if not epw_local_path:
             raise Exception(f"Failed to resolve EPW file from {epw_url}")

        # Run the actual simulation
        run_results = energyplus_simulator.run_simulation_job(
            job_id=job_id, 
            idf_path=raw_idf_path, 
            epw_path=epw_local_path, 
            config=settings,
            output_dir_base=OUTPUT_DIR
        )

        # 3. Read IDF content and CSV data to return to the frontend directly
        # Frontend Plotly uses the geometry from the IDF string
        ready_idf_path = os.path.join(job_dir, "_ready.idf")
        final_idf_content = ""
        if os.path.exists(ready_idf_path):
             with open(ready_idf_path, "r", encoding="utf-8") as f:
                  final_idf_content = f.read()
        else:
             final_idf_content = idf_content # fallback to raw

        # Read CSV data for Charts
        csv_data = ""
        if "csv" in run_results and os.path.exists(run_results["csv"]):
             with open(run_results["csv"], "r", encoding="utf-8") as f:
                  csv_data = f.read()

        # Update Job State as DONE
        jobs_db[job_id]["status"] = "done"
        jobs_db[job_id]["result"] = {
            "idf": final_idf_content,
            "csv_data": csv_data,
            "files": {k: f"/results/{job_id}/{os.path.basename(v)}" for k, v in run_results.items() if os.path.exists(str(v))}
        }
        print(f"[{job_id}] Pipeline completed successfully.")

    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        print(f"[{job_id}] Pipeline failed:\n{tb_str}")
        jobs_db[job_id]["status"] = "error"
        jobs_db[job_id]["error_message"] = f"Error: {str(e)}\n\nTraceback:\n{tb_str}"
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


class RunEKFRequest(BaseModel):
    room_num: int = 3
    dataset_path: Optional[str] = None

def run_ekf_pipeline(job_id: str, room_num: int, dataset_path: str = None):
    """
    Background worker that runs the 10-state EKF algorithm on a room dataset.
    """
    try:
        jobs_db[job_id]["status"] = "processing"
        
        # Prepare output directory under our static files path
        target_dir = os.path.join(OUTPUT_DIR, "ekf_runs", job_id)
        os.makedirs(target_dir, exist_ok=True)
        
        # Add root to path so we can import EKF module
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if root_dir not in sys.path:
            sys.path.append(root_dir)
        from EKF.Real_EKF_ROBOD import main as run_ekf_script
        
        print(f"[{job_id}] Starting EKF run for room {room_num}...")
        run_ekf_script(room_num=room_num, save_mode=True, results_dir=target_dir, dataset_path=dataset_path)
        
        # Get list of files generated
        generated_files = []
        if os.path.exists(target_dir):
            generated_files = sorted(os.listdir(target_dir))
        
        # Build relative URLs (using the mapped static mount /results)
        file_urls = {fname: f"/results/ekf_runs/{job_id}/{fname}" for fname in generated_files if fname.endswith(".png")}
        
        csv_url = None
        if "ekf_results.csv" in generated_files:
            csv_url = f"/results/ekf_runs/{job_id}/ekf_results.csv"
            
        jobs_db[job_id]["status"] = "done"
        jobs_db[job_id]["result"] = {
            "files": file_urls,
            "csv_url": csv_url
        }
        print(f"[{job_id}] EKF run completed successfully.")
        
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        print(f"[{job_id}] EKF run failed:\n{tb_str}")
        jobs_db[job_id]["status"] = "error"
        jobs_db[job_id]["error_message"] = f"Error: {str(e)}\n\nTraceback:\n{tb_str}"

@app.post("/api/run_ekf")
async def run_ekf(req: RunEKFRequest):
    job_id = f"ekf_room{req.room_num}_{time.strftime('%Y_%m_%d_%H_%M_%S')}"
    
    jobs_db[job_id] = {
        "status": "queued",
        "room_num": req.room_num,
        "created_at": time.time(),
        "result": None,
        "error_message": None
    }
    
    thread = threading.Thread(target=run_ekf_pipeline, args=(job_id, req.room_num, req.dataset_path))
    thread.start()
    
    return {"job_id": job_id, "status": "queued"}

@app.post("/api/upload_ekf_dataset")
async def upload_ekf_dataset(file: UploadFile = File(...)):
    """
    Accepts a CSV dataset file upload and saves it to a unique location under the temp directory.
    """
    os.makedirs(os.path.join(OUTPUT_DIR, "uploads"), exist_ok=True)
    file_id = str(uuid.uuid4())
    filename = f"ekf_upload_{file_id}_{file.filename}"
    file_path = os.path.join(OUTPUT_DIR, "uploads", filename)
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    return {"file_path": file_path, "filename": file.filename}


@app.post("/api/simulate", response_model=SimulateResponse)
async def simulate(req: SimulateRequest):
    """
    Accepts a prompt and simulation settings, creates a job, and starts the background worker.
    """
    job_id = f"job_{time.strftime('%Y_%m_%d_%H_%M_%S')}"
    
    # Initialize job in DB
    jobs_db[job_id] = {
        "status": "queued",
        "prompt": req.prompt,
        "settings": req.settings,
        "created_at": time.time(),
        "result": None,
        "error_message": None
    }
    
    # Start the processing thread
    thread = threading.Thread(target=run_simulation_pipeline, args=(job_id, req.prompt, req.settings))
    thread.start()
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """
    Returns the current status of the job and any results if done, omitting heavy data.
    """
    if job_id not in jobs_db:
        return {"status": "not_found", "error": "Job ID does not exist."}
    
    # Create a shallow copy to avoid mutating the in-memory database
    job_info = jobs_db[job_id].copy()
    if "result" in job_info and job_info["result"]:
        job_result = job_info["result"].copy()
        if "csv_data" in job_result:
            del job_result["csv_data"]
        if "idf" in job_result:
            del job_result["idf"]
        job_info["result"] = job_result
        
    return job_info

@app.get("/api/ping")
async def ping():
    """
    Simple health check for the frontend to verify the Ngrok URL is correct and online.
    """
    return {"status": "online", "message": "SmartBEM Backend is running."}

def start_server(port=8000):
    """
    Starts the FastAPI server with Ngrok tunneling in a Colab environment.
    """
    # Load Ngrok token from secrets.json (located one folder up in backend_server/)
    secrets_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secrets.json")
    if os.path.exists(secrets_path):
        import json
        with open(secrets_path, "r") as f:
            secrets = json.load(f)
            token = secrets.get("NGROK_AUTHTOKEN")
            if token and token != "YOUR_NGROK_AUTHTOKEN_HERE":
                ngrok.set_auth_token(token)
            else:
                print("⚠️ Warning: NGROK_AUTHTOKEN not set in secrets.json. Tunnel might fail or be restricted.")
    else:
        print(f"⚠️ Warning: {secrets_path} not found. Ngrok auth token not set.")

    # Open a ngrok tunnel to the dev server
    public_url = ngrok.connect(port).public_url
    print("*" * 60)
    print(f"🚀 SMART HVAC BACKEND IS LIVE!")
    print(f"🔗 COPY THIS URL TO YOUR WEB DASHBOARD: {public_url}")
    print(f"📄 VIEW SYSTEM LOGS AT: {public_url}/results/backend.log")
    print(f"💡 TO VIEW LIVE LOGS IN COLAB RUN: !tail -n 100 -f {LOG_FILE_PATH}")
    print("*" * 60)
    
    # Run Uvicorn in a separate thread to avoid Jupyter's asyncio loop conflict
    def run_uvicorn():
        # uvicorn.run needs a clean event loop
        uvicorn.run(app, host="0.0.0.0", port=port)
        
    server_thread = threading.Thread(target=run_uvicorn, daemon=True)
    server_thread.start()
    
    print(f"Server is running in the background. You can continue using the notebook.")

if __name__ == "__main__":
    start_server()
