import os
import shutil
import pandas as pd
import matplotlib.pyplot as plt
from eplus.colab_bootstrap import prepare_colab_eplus

def run_simulation_job(job_id, idf_path, epw_path, config=None, output_dir_base="sim_runs"):
    """
    Executes an EnergyPlus simulation for a specific job.
    
    Args:
        job_id (str): Unique Job ID.
        idf_path (str): Path to the model.idf file.
        epw_path (str): Path to the weather.epw file.
        config (dict): Simulation configuration (e.g., {"run_type": "annual", "outputs": [...]}).
        output_dir_base (str): Base directory for simulation outputs.
        
    Returns:
        dict: Paths to result files (images, csvs, sql).
    """
    if config is None:
        config = {}
        
    # 1. Prepare Colab Environment (Safe to call repeatedly)
    print(f"[{job_id}] Bootstrapping EnergyPlus (Verbose)...")
    prepare_colab_eplus(silent=False)
    
    # Lazy import to avoid loading pyenergyplus before bootstrap
    from eplus.eplus_util import EPlusUtil
    from eplus.sql_explorer import EPlusSqlExplorer
    from backend import visualizer
    
    # 2. Setup Run Directory
    run_dir = os.path.join(output_dir_base, job_id)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)
    
    # 3. Initialize Utility
    print(f"[{job_id}] Initializing EPlusUtil...")
    util = EPlusUtil(verbose=1)
    
    # 4. Configure Model (no CO2, no Output:Variable stripping)
    util.set_model(idf=idf_path, epw=epw_path, out_dir=run_dir, add_co2=False)

    # 5. Inject Output Objects directly into IDF (bypasses ensure_* chain reliability issues)
    # Read the IDF, strip any existing Output:Variable/SQLite, inject ours cleanly.
    import re as _re, pathlib as _pl

    _idf_text = _pl.Path(idf_path).read_text(encoding="utf-8", errors="ignore")

    # Strip any existing Output:Variable and Output:SQLite blocks (deduplicate)
    _idf_text = _re.sub(r'(?is)^\s*Output\s*:\s*Variable\s*,.*?;[ \t]*\r?\n?', '', _idf_text, flags=_re.MULTILINE)
    _idf_text = _re.sub(r'(?is)^\s*Output\s*:\s*SQLite\s*,.*?;[ \t]*\r?\n?', '', _idf_text, flags=_re.MULTILINE)
    _idf_text = _re.sub(r'(?is)^\s*Output\s*:\s*Meter\s*,.*?;[ \t]*\r?\n?', '', _idf_text, flags=_re.MULTILINE)

    # Append our required output blocks
    _idf_text = _idf_text.rstrip() + """

  Output:SQLite,
    SimpleAndTabular;         !- Output Type

  Output:Variable,*,Zone Air Temperature,Hourly;
  Output:Variable,*,Zone Mean Air Temperature,Hourly;
  Output:Variable,*,Site Outdoor Air Drybulb Temperature,Hourly;
  Output:Variable,*,Zone Air System Sensible Cooling Energy,Hourly;
  Output:Variable,*,Zone Air System Sensible Heating Energy,Hourly;
  Output:Variable,*,System Node Mass Flow Rate,Hourly;
  Output:Variable,*,Zone Mechanical Ventilation Mass Flow Rate,Hourly;
  Output:Meter,Electricity:Facility,Hourly;
  Output:Meter,NaturalGas:Facility,Hourly;

"""
    _ready_idf_path = os.path.join(run_dir, "_ready.idf")
    with open(_ready_idf_path, "w", encoding="utf-8") as _f:
        _f.write(_idf_text)

    # Update util to use our prepared IDF
    util.idf = _ready_idf_path
    print(f"[{job_id}] Ready IDF written: {_ready_idf_path}")
    print(f"[{job_id}] Output:SQLite and Output:Variable blocks injected directly.")

    # 6. Run Simulation
    run_type = config.get("run_type", "design_day").lower() # Default to design_day for speed
    print(f"[{job_id}] Starting Simulation (Type: {run_type}), IDF: {util.idf}...")

    try:
        if "annual" in run_type:
            util.run_annual()
        else:
            # Default to design day
            util.run_design_day()
    except Exception as e:
        print(f"[{job_id}] Simulation Failed: {e}")
        raise e

    print(f"[{job_id}] Simulation Complete. Extracting Results...")

    # ---- DIAGNOSTICS: print EnergyPlus error log ----
    err_path = os.path.join(run_dir, "eplusout.err")
    if os.path.exists(err_path):
        with open(err_path, "r", encoding="utf-8", errors="ignore") as _ef:
            _err_lines = _ef.readlines()
        # Print last 60 lines so we see any severe errors
        print(f"[{job_id}] === eplusout.err (last 60 lines) ===")
        for _ln in _err_lines[-60:]:
            print("  " + _ln.rstrip())
        print(f"[{job_id}] === end eplusout.err ===")
    else:
        print(f"[{job_id}] WARNING: eplusout.err not found!")

    # ---- DIAGNOSTICS: inspect SQL directly ----
    _sql_diag_path = os.path.join(run_dir, "eplusout.sql")
    if os.path.exists(_sql_diag_path):
        import sqlite3 as _sq3
        try:
            _conn = _sq3.connect(_sql_diag_path)
            _rd_count = _conn.execute("SELECT COUNT(*) FROM ReportData").fetchone()[0]
            print(f"[{job_id}] SQL ReportData rows: {_rd_count}")
            if _rd_count > 0:
                _vars = _conn.execute(
                    "SELECT d.Name, d.KeyValue, d.ReportingFrequency, COUNT(*) "
                    "FROM ReportData r JOIN ReportDataDictionary d "
                    "ON r.ReportDataDictionaryIndex=d.ReportDataDictionaryIndex "
                    "GROUP BY d.Name, d.KeyValue, d.ReportingFrequency "
                    "ORDER BY COUNT(*) DESC LIMIT 20"
                ).fetchall()
                print(f"[{job_id}] Variables in SQL:")
                for _v in _vars:
                    print(f"  {_v}")
            else:
                print(f"[{job_id}] SQL has ZERO ReportData rows — EnergyPlus did not report any variables.")
                # Check if the Time table has any entries (did simulation step at all?)
                _time_count = _conn.execute("SELECT COUNT(*) FROM Time").fetchone()[0]
                print(f"[{job_id}] SQL Time rows: {_time_count}")
                _ep_count = _conn.execute("SELECT COUNT(*) FROM EnvironmentPeriods").fetchone()[0]
                print(f"[{job_id}] SQL EnvironmentPeriods rows: {_ep_count}")
                if _ep_count > 0:
                    _eps = _conn.execute("SELECT * FROM EnvironmentPeriods").fetchall()
                    for _ep in _eps:
                        print(f"  EnvironmentPeriod: {_ep}")
            _conn.close()
        except Exception as _sqe:
            print(f"[{job_id}] SQL diagnostic error: {_sqe}")
    else:
        print(f"[{job_id}] SQL file does not exist at all!")

    # 7. Extract Results (Data Mining)
    results = {}
    sql_path = os.path.join(run_dir, "eplusout.sql")
    if not os.path.exists(sql_path):
        err_path = os.path.join(run_dir, "eplusout.err")
        err_msg = ""
        if os.path.exists(err_path):
            with open(err_path, "r", encoding="utf-8", errors="ignore") as f:
                err_msg = f.read()
        raise Exception(f"Simulation did not produce eplusout.sql.\nEnergyPlus Engine Error Log:\n{err_msg}")

    xp = EPlusSqlExplorer(sql_path)

    # Always include design days — this run type only has sizing periods, no weather periods
    is_design_day_run = run_type == "design_day"

    def _make_placeholder_png(path, label):
        """Generate a 'Not Available' placeholder image so the frontend always gets a file."""
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, f"{label}\nNot Available for this run type",
                ha='center', va='center', fontsize=16, color='#888',
                transform=ax.transAxes)
        ax.set_axis_off()
        plt.tight_layout()
        plt.savefig(path, dpi=80)
        plt.close()

    def _plot_series(df, var_name, img_path, job_id):
        """Plot a single-key series DataFrame (columns: timestamp, value)."""
        plt.figure(figsize=(10, 6))
        plt.plot(range(len(df)), df["value"], label=var_name, linewidth=1.5)
        plt.title(f"{var_name}")
        plt.xlabel("Time Step")
        plt.ylabel("Value")
        plt.legend()
        plt.grid(True, alpha=0.4)
        plt.tight_layout()
        plt.savefig(img_path, dpi=120)
        plt.close()

    def _plot_multi_series(wide_df, var_name, img_path):
        """Plot a wide DataFrame (timestamp + multiple zone columns)."""
        plt.figure(figsize=(12, 6))
        zone_cols = [c for c in wide_df.columns if c != "timestamp"]
        for col in zone_cols:
            plt.plot(range(len(wide_df)), wide_df[col], label=col, linewidth=1.5)
        plt.title(var_name)
        plt.xlabel("Time Step")
        plt.ylabel("Value")
        if len(zone_cols) <= 10:
            plt.legend(fontsize=8)
        plt.grid(True, alpha=0.4)
        plt.tight_layout()
        plt.savefig(img_path, dpi=120)
        plt.close()

    # -----------------------------------------------------------------
    # Plot 1: Zone Air Temperature  (supports multi-zone wide CSV)
    # -----------------------------------------------------------------
    try:
        df_temp = xp.auto_extract_series("Zone Air Temperature", to_kwh=False,
                                         include_design_days=is_design_day_run)
        if df_temp is not None and not df_temp.empty:
            img_path = os.path.join(run_dir, "plot.png")
            _plot_series(df_temp, "Zone Air Temperature", img_path, job_id)
            results["plot"] = img_path
            # Build a wide CSV with one column per zone for the frontend Chart.js
            try:
                conn_tmp = __import__("sqlite3").connect(sql_path)
                env_filter = "AND (ep.EnvironmentName IS NULL OR 1=1)" if is_design_day_run else \
                             "AND ep.EnvironmentType = 'WeatherRunPeriod'"
                wide_sql = f"""
                    SELECT t.TimeIndex,
                           d.KeyValue AS zone,
                           r.Value
                    FROM ReportData r
                    JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
                    JOIN Time t ON r.TimeIndex = t.TimeIndex
                    LEFT JOIN EnvironmentPeriods ep ON t.EnvironmentPeriodIndex = ep.EnvironmentPeriodIndex
                    WHERE d.Name = 'Zone Air Temperature'
                    {env_filter}
                    ORDER BY t.TimeIndex, d.KeyValue
                """
                import pandas as _pd
                df_wide_raw = _pd.read_sql_query(wide_sql, conn_tmp)
                conn_tmp.close()
                if not df_wide_raw.empty:
                    df_wide = df_wide_raw.pivot_table(index="TimeIndex", columns="zone", values="Value")
                    df_wide.reset_index(drop=True, inplace=True)
                    df_wide.columns = [f"Zone Air Temperature:{c}" for c in df_wide.columns]
                    csv_path = os.path.join(run_dir, "results.csv")
                    df_wide.to_csv(csv_path, index=False)
                    results["csv"] = csv_path
            except Exception as csv_err:
                print(f"[{job_id}] Wide CSV generation failed: {csv_err}")
                # Fallback — save simple two-column CSV
                csv_path = os.path.join(run_dir, "results.csv")
                df_temp.to_csv(csv_path, index=False)
                results["csv"] = csv_path
        else:
            print(f"[{job_id}] Warning: No data found for Zone Air Temperature")
            _make_placeholder_png(os.path.join(run_dir, "plot.png"), "Zone Air Temperature")
            results["plot"] = os.path.join(run_dir, "plot.png")
    except Exception as e:
        print(f"[{job_id}] Error plotting Zone Air Temperature: {e}")
        _make_placeholder_png(os.path.join(run_dir, "plot.png"), "Zone Air Temperature")
        results["plot"] = os.path.join(run_dir, "plot.png")

    # -----------------------------------------------------------------
    # Plot 2: System Node Mass Flow Rate  (HVAC airflow)
    # -----------------------------------------------------------------
    try:
        df_flow = xp.auto_extract_series("System Node Mass Flow Rate", to_kwh=False,
                                         include_design_days=is_design_day_run)
        if df_flow is not None and not df_flow.empty:
            img_path = os.path.join(run_dir, "plot_ekf.png")
            _plot_series(df_flow, "System Node Mass Flow Rate (kg/s)", img_path, job_id)
            results["plot_ekf"] = img_path
        else:
            print(f"[{job_id}] Warning: No data found for System Node Mass Flow Rate")
            _make_placeholder_png(os.path.join(run_dir, "plot_ekf.png"), "System Node Mass Flow Rate")
            results["plot_ekf"] = os.path.join(run_dir, "plot_ekf.png")
    except Exception as e:
        print(f"[{job_id}] Error plotting System Node Mass Flow Rate: {e}")
        _make_placeholder_png(os.path.join(run_dir, "plot_ekf.png"), "System Node Mass Flow Rate")
        results["plot_ekf"] = os.path.join(run_dir, "plot_ekf.png")

    # -----------------------------------------------------------------
    # Plot 3: Outdoor Weather Temperature
    # -----------------------------------------------------------------
    try:
        df_wx = xp.auto_extract_series("Site Outdoor Air Drybulb Temperature", to_kwh=False,
                                        include_design_days=is_design_day_run)
        if df_wx is not None and not df_wx.empty:
            img_path = os.path.join(run_dir, "plot_weather.png")
            _plot_series(df_wx, "Outdoor Drybulb Temperature (°C)", img_path, job_id)
            results["plot_weather"] = img_path
        else:
            print(f"[{job_id}] Warning: No data found for Site Outdoor Air Drybulb Temperature")
            _make_placeholder_png(os.path.join(run_dir, "plot_weather.png"), "Outdoor Air Temperature")
            results["plot_weather"] = os.path.join(run_dir, "plot_weather.png")
    except Exception as e:
        print(f"[{job_id}] Error plotting weather: {e}")
        _make_placeholder_png(os.path.join(run_dir, "plot_weather.png"), "Outdoor Air Temperature")
        results["plot_weather"] = os.path.join(run_dir, "plot_weather.png")

    # -----------------------------------------------------------------
    # Plot 4: Energy Consumption
    #   → Try Electricity:Facility meter first
    #   → Fall back to summing Zone Cooling + Heating energy
    # -----------------------------------------------------------------
    try:
        df_elec = xp.auto_extract_series("Electricity:Facility", to_kwh=False,
                                          include_design_days=is_design_day_run)
        if df_elec is not None and not df_elec.empty:
            img_path = os.path.join(run_dir, "plot_energy.png")
            _plot_series(df_elec, "Electricity:Facility (J)", img_path, job_id)
            results["plot_energy"] = img_path
        else:
            raise ValueError("Electricity:Facility meter empty — trying zone energy fallback")
    except Exception:
        # Fallback: aggregate Zone Cooling + Heating Sensible Energy
        try:
            df_cool = xp.auto_extract_series("Zone Air System Sensible Cooling Energy", to_kwh=False,
                                              include_design_days=is_design_day_run)
            df_heat = xp.auto_extract_series("Zone Air System Sensible Heating Energy", to_kwh=False,
                                              include_design_days=is_design_day_run)
            if (df_cool is not None and not df_cool.empty) or (df_heat is not None and not df_heat.empty):
                import pandas as _pd2
                frames = []
                if df_cool is not None and not df_cool.empty:
                    frames.append(df_cool.rename(columns={"value": "Cooling (J)"}))
                if df_heat is not None and not df_heat.empty:
                    frames.append(df_heat.rename(columns={"value": "Heating (J)"}))
                df_energy = frames[0] if len(frames) == 1 else \
                    _pd2.merge(frames[0], frames[1], on="timestamp", how="outer")
                img_path = os.path.join(run_dir, "plot_energy.png")
                plt.figure(figsize=(10, 6))
                if "Cooling (J)" in df_energy.columns:
                    plt.plot(range(len(df_energy)), df_energy["Cooling (J)"],
                             label="Sensible Cooling", color="steelblue", linewidth=1.5)
                if "Heating (J)" in df_energy.columns:
                    plt.plot(range(len(df_energy)), df_energy["Heating (J)"],
                             label="Sensible Heating", color="tomato", linewidth=1.5)
                plt.title("HVAC Energy (Cooling + Heating)")
                plt.xlabel("Time Step")
                plt.ylabel("Energy (J)")
                plt.legend()
                plt.grid(True, alpha=0.4)
                plt.tight_layout()
                plt.savefig(img_path, dpi=120)
                plt.close()
                results["plot_energy"] = img_path
            else:
                print(f"[{job_id}] Warning: No energy data found at all")
                _make_placeholder_png(os.path.join(run_dir, "plot_energy.png"), "Energy Consumption")
                results["plot_energy"] = os.path.join(run_dir, "plot_energy.png")
        except Exception as e2:
            print(f"[{job_id}] Error plotting energy fallback: {e2}")
            _make_placeholder_png(os.path.join(run_dir, "plot_energy.png"), "Energy Consumption")
            results["plot_energy"] = os.path.join(run_dir, "plot_energy.png")
    
    # 8. Add SQL and IDF to results
    results["idf"] = idf_path
    
    # 9. Generate HTML Summary of IDF objects
    try:
        with open(idf_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        objects = []
        current_type = None
        current_name = None
        current_fields = []
        
        for raw_line in lines:
            line = raw_line.strip()
            if line.startswith('!') or not line:
                continue
                
            line_no_comment = line
            if '!' in line:
                line_no_comment = line[:line.index('!')].strip()
                
            if not current_type:
                if line_no_comment.endswith(','):
                    current_type = line_no_comment[:-1].strip()
                elif line_no_comment.endswith(';'):
                    objects.append({"type": line_no_comment[:-1].strip(), "name": "N/A", "fields": []})
                    current_type = None
            elif not current_name:
                if line_no_comment.endswith(',') or line_no_comment.endswith(';'):
                    current_name = line_no_comment[:-1].strip()
                    if line_no_comment.endswith(';'):
                        objects.append({"type": current_type, "name": current_name, "fields": []})
                        current_type = None
                        current_name = None
            else:
                # We are parsing fields
                current_fields.append(line)
                if line_no_comment.endswith(';'):
                    objects.append({"type": current_type, "name": current_name, "fields": list(current_fields)})
                    current_type = None
                    current_name = None
                    current_fields = []
                    
        grouped = {}
        for obj in objects:
            t = obj["type"]
            n = obj["name"]
            if t not in grouped:
                grouped[t] = []
            if n != "N/A" and n:
                grouped[t].append(obj)
                
        html = f'''<html><head><title>IDF Object Summary</title><style>
        body{{font-family: -apple-system, sans-serif; padding: 40px; background: #f8f9fa;}}
        .card{{background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; break-inside: avoid;}}
        h1{{color: #1a73e8;}} h2{{color: #333; font-size: 1.1em; border-bottom: 1px solid #eee; padding-bottom: 5px;}}
        ul{{list-style-type: none; padding-left: 0;}} li{{padding: 8px 0; border-bottom: 1px solid #f0f0f0;}}
        details{{margin-top: 5px;}} summary{{cursor: pointer; color: #1a73e8; font-weight: 500; outline: none; list-style: none; display: flex; align-items: center;}}
        summary::-webkit-details-marker {{display: none;}}
        summary::before {{content: "▶ "; font-size: 0.8em; margin-right: 5px; color: #888; transition: transform 0.2s;}}
        details[open] summary::before {{transform: rotate(90deg);}}
        .fields-list{{background: #fafafa; padding: 10px 15px; border-radius: 4px; margin-top: 5px; font-family: monospace; font-size: 0.9em; color: #555;}}
        .fields-list div{{padding: 2px 0;}}
        </style></head><body><h1>IDF Component Summary</h1><p style="color:gray">Job ID: {job_id}</p><div style="column-count: 2; column-gap: 40px;">'''
        
        for t in sorted(grouped.keys()):
            objs = grouped[t]
            if objs:
                html += f'<div class="card"><h2>{t} <span style="color:gray; font-weight:normal; font-size:0.8em;">({len(objs)})</span></h2><ul>'
                for obj in objs:
                    n = obj["name"]
                    fields = obj["fields"]
                    if not fields:
                        html += f'<li>{n}</li>'
                    else:
                        html += f'<li><details><summary>{n}</summary><div class="fields-list">'
                        for f in fields:
                            # Safely escape HTML characters like < and >
                            f_clean = f.replace("<", "&lt;").replace(">", "&gt;")
                            html += f'<div>{f_clean}</div>'
                        html += '</div></details></li>'
                html += '</ul></div>'
        html += '</div></body></html>'
        
        summary_path = os.path.join(run_dir, "summary.html")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(html)
            
        results["summary"] = summary_path
        print(f"[{job_id}] Successfully generated summary.html")
    except Exception as e:
        print(f"[{job_id}] Error generating summary: {e}")
        
    # 10. Generate 3D HTML
    try:
        geometry_path = os.path.join(run_dir, "geometry.html")
        if visualizer.generate_3d_html(idf_path, geometry_path):
            results["geometry"] = geometry_path
            print(f"[{job_id}] Successfully generated geometry.html")
    except Exception as e:
        print(f"[{job_id}] Error generating 3D geometry: {e}")

    return results
