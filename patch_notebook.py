import json
import os

NOTEBOOK_PATH = "d:/UNI/Sem 7/ME420 Mech Eng Research Project/SmartHVAC-Studio/colab/Run_Connected_Experiment.ipynb"

def patch():
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)
        
    NEW_CODE_BLOCK = """                    # --- PHASE 3: THE SYSTEM LOOP ---
                    selected_model = data.get("selectedModel", "openai")
                    print(f"   [Phase 3] Generating IDF using {selected_model}...")
                    
                    final_idf_string = ai.generate_idf_from_text(nlp_input, sim_settings, model_type=selected_model)
                    
                    if final_idf_string.startswith("! Error"):
                        raise Exception(f"AI Generation Failed: {final_idf_string}")
                        
                    # Save IDF
                    import os
                    idf_save_path = f"RunFiles/{job_id}_in.idf"
                    os.makedirs("RunFiles", exist_ok=True)
                    with open(idf_save_path, "w", encoding="utf-8") as f:
                        f.write(final_idf_string)
                        
                    print("   [Phase 3] Running Simulation via simulation_runner.py...")
                    import simulation_runner
                    
                    # Epw path usually defaults to "weather.epw" or from sim_settings
                    epw_name = sim_settings.get("weather_file", "weather.epw")
                    if not os.path.exists(epw_name) and os.path.exists("weather/" + epw_name):
                         epw_name = "weather/" + epw_name
                    elif not os.path.exists(epw_name):
                         epw_name = "weather.epw"
                         
                    sim_results = simulation_runner.run_simulation_job(
                        job_id=job_id,
                        idf_path=idf_save_path,
                        epw_path=epw_name,
                        config=sim_settings,
                        output_dir_base="sim_runs"
                    )
                    print("   [Phase 3] Simulation Complete! Uploading results to Storage...")
                    
                    # Upload to Storage
                    bucket = storage.bucket()
                    result_urls = {}
                    
                    for key, file_path in sim_results.items():
                        if os.path.exists(file_path):
                            blob_path = f"jobs/{job_id}/{os.path.basename(file_path)}"
                            blob = bucket.blob(blob_path)
                            
                            c_type = "image/png" if key == "plot" else "text/csv"
                            blob.upload_from_filename(file_path, content_type=c_type)
                            
                            # Store the direct URL
                            try:
                                blob.make_public()
                                result_urls[key] = blob.public_url
                            except:
                                result_urls[key] = f"gs://{bucket.name}/{blob_path}"
                            
                    db.collection("jobs").document(job_id).update({
                        "status": "done",
                        "resultPaths": result_urls,
                        "completedAt": datetime.now()
                    })
                    print(f"   ✅ Job Finished: {job_id}\\n")
"""

    patched = False
    for cell in nb.get('cells', []):
        if cell['cell_type'] == 'code':
            source = cell.get('source', [])
            source_text = "".join(source)
            if "# --- CALL YOUR EXISTING LOGIC HERE ---" in source_text:
                new_source = []
                in_replace = False
                for line in source:
                    if "# --- CALL YOUR EXISTING LOGIC HERE ---" in line:
                        in_replace = True
                        new_source.append(NEW_CODE_BLOCK)
                    elif 'print(f"   ✅ Job Finished: {job_id}")' in line:
                        in_replace = False
                    elif not in_replace:
                        new_source.append(line)
                
                cell['source'] = new_source
                patched = True
                
    if patched:
        with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
            json.dump(nb, f, indent=2)
        print("Notebook successfully patched with Phase 3 Logic!")
    else:
        print("Could not find the target section in notebook to patch.")

if __name__ == '__main__':
    patch()
