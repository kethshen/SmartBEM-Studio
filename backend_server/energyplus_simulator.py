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
    from core import chart_generator
    
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
        else:
            print(f"[{job_id}] Warning: No data found for Zone Air Temperature")
            _make_placeholder_png(os.path.join(run_dir, "plot.png"), "Zone Air Temperature")
            results["plot"] = os.path.join(run_dir, "plot.png")
    except Exception as e:
        print(f"[{job_id}] Error plotting Zone Air Temperature: {e}")
        _make_placeholder_png(os.path.join(run_dir, "plot.png"), "Zone Air Temperature")
        results["plot"] = os.path.join(run_dir, "plot.png")

    # -----------------------------------------------------------------
    # Export Wide CSV (For Frontend Plotly Charts)
    # -----------------------------------------------------------------
    try:
        conn_tmp = __import__("sqlite3").connect(sql_path)
        # Use EnvironmentName for filtering sizing periods, since EnvironmentType column is sometimes missing
        env_filter = "AND (ep.EnvironmentName IS NULL OR 1=1)" if is_design_day_run else \
                     "AND (ep.EnvironmentName IS NULL OR ep.EnvironmentName NOT LIKE 'SizingPeriod:%')"
        wide_sql = f"""
            SELECT t.TimeIndex,
                   t.Month,
                   t.Day,
                   t.Hour,
                   COALESCE(ep.EnvironmentName, 'Simulation') AS env_name,
                   d.Name AS var_name,
                   d.KeyValue AS zone,
                   r.Value
            FROM ReportData r
            JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
            JOIN Time t ON r.TimeIndex = t.TimeIndex
            LEFT JOIN EnvironmentPeriods ep ON t.EnvironmentPeriodIndex = ep.EnvironmentPeriodIndex
            WHERE 1=1 {env_filter}
            ORDER BY t.TimeIndex
        """
        import pandas as _pd
        df_wide_raw = _pd.read_sql_query(wide_sql, conn_tmp)
        conn_tmp.close()
        
        if not df_wide_raw.empty:
            # Create a nice human readable timestamp string
            # Strip SizingPeriod:DesignDay from environment name
            df_wide_raw["env_short"] = df_wide_raw["env_name"].str.replace("SizingPeriod:DesignDay", "", case=False, regex=False).str.strip()
            df_wide_raw["Month"] = df_wide_raw["Month"].fillna(1).astype(int)
            df_wide_raw["Day"] = df_wide_raw["Day"].fillna(1).astype(int)
            df_wide_raw["Hour"] = df_wide_raw["Hour"].fillna(1).astype(int)
            
            # Format: "Chicago - 7/21 01:00"
            df_wide_raw["formatted_time"] = (
                df_wide_raw["env_short"] + " - " +
                df_wide_raw["Month"].astype(str) + "/" +
                df_wide_raw["Day"].astype(str) + " " +
                df_wide_raw["Hour"].apply(lambda h: f"{int(h):02d}:00")
            )

            # Vectorized column name generation for speed
            df_wide_raw["zone"] = df_wide_raw["zone"].fillna("")
            mask = df_wide_raw["zone"] != ""
            df_wide_raw["col_name"] = df_wide_raw["var_name"]
            df_wide_raw.loc[mask, "col_name"] = df_wide_raw["var_name"] + ":" + df_wide_raw["zone"]
            
            # Pivot table using TimeIndex as index
            df_wide = df_wide_raw.pivot_table(index="TimeIndex", columns="col_name", values="Value")
            df_wide.reset_index(inplace=True)
            
            # Map TimeIndex to formatted_time
            time_map = df_wide_raw.drop_duplicates("TimeIndex").set_index("TimeIndex")["formatted_time"]
            df_wide["Date/Time"] = df_wide["TimeIndex"].map(time_map)
            
            df_wide.drop(columns=["TimeIndex"], inplace=True)
            
            # Reorder columns to put Date/Time first
            cols = ["Date/Time"] + [c for c in df_wide.columns if c != "Date/Time"]
            df_wide = df_wide[cols]
            
            csv_path = os.path.join(run_dir, "results.csv")
            df_wide.to_csv(csv_path, index=False)
            results["csv"] = csv_path
            print(f"[{job_id}] Successfully generated wide results.csv with {len(df_wide)} rows.")
        else:
            print(f"[{job_id}] Warning: df_wide_raw is empty, no CSV generated.")
    except Exception as csv_err:
        print(f"[{job_id}] Wide CSV generation failed: {csv_err}")

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
                    
        # Identify all Zone names present in the IDF
        zone_names = set()
        for obj in objects:
            if obj["type"].upper() == "ZONE":
                zone_names.add(obj["name"].strip())

        # Normalize zone names for case-insensitive matching
        zone_names_lower = {z.lower(): z for z in zone_names}

        # Build surface mapping (surface_name_lower -> zone_name_original)
        surface_to_zone = {}
        for obj in objects:
            t_upper = obj["type"].upper()
            if t_upper in ("BUILDINGSURFACE:DETAILED", "SHADING:ZONE:DETAILED"):
                for f in obj["fields"]:
                    val_clean = f.split('!')[0].strip().rstrip(',;').strip().lower()
                    if val_clean in zone_names_lower:
                        surface_to_zone[obj["name"].strip().lower()] = zone_names_lower[val_clean]
                        break

        # Group objects by zone, and within each zone, by category
        zone_grouped = {z: {} for z in zone_names}
        zone_grouped["Global / Shared"] = {}

        # Category mappings for zone-specific objects
        ZONE_CATEGORIES = {
            "ZONE": "Zone Info / Metadata",
            "BUILDINGSURFACE:DETAILED": "Geometry & Surfaces",
            "FENESTRATIONSURFACE:DETAILED": "Geometry & Surfaces",
            "INTERNALMASS": "Geometry & Surfaces",
            "SHADING:ZONE:DETAILED": "Geometry & Surfaces",
            
            "PEOPLE": "Internal Gains",
            "LIGHTS": "Internal Gains",
            "ELECTRICEQUIPMENT": "Internal Gains",
            "GASEQUIPMENT": "Internal Gains",
            
            "ZONECONTROL:THERMOSTAT": "HVAC & Controls",
            "THERMOSTATSETPOINT:DUALSETPOINT": "HVAC & Controls",
            "ZONEHVAC:IDEALLOADSAIRSYSTEM": "HVAC & Controls",
            "ZONEHVAC:EQUIPMENTCONNECTIONS": "HVAC & Controls",
            "ZONEHVAC:EQUIPMENTLIST": "HVAC & Controls",
            "SIZING:ZONE": "HVAC & Controls",
            "ZONEINFILTRATION:DESIGNFLOWRATE": "HVAC & Controls",
            "DESIGNSPECIFICATION:OUTDOORAIR": "HVAC & Controls",
        }

        # Category mappings for global/shared objects
        GLOBAL_CATEGORIES = {
            "VERSION": "Simulation Settings",
            "SIMULATIONCONTROL": "Simulation Settings",
            "BUILDING": "Simulation Settings",
            "SHADOWCALCULATION": "Simulation Settings",
            "RUNPERIOD": "Simulation Settings",
            "SITE:LOCATION": "Simulation Settings",
            "OUTPUT:SQLITE": "Simulation Settings",
            "OUTPUT:VARIABLE": "Simulation Settings",
            "OUTPUT:METER": "Simulation Settings",
            "SIZING:PARAMETERS": "Simulation Settings",
            "GLOBALGEOMETRYRULES": "Simulation Settings",
            "LIFECYCLECOST:PARAMETERS": "Simulation Settings",
            "LIFECYCLECOST:USEPRICEESCALATION": "Simulation Settings",
            
            "CONSTRUCTION": "Constructions & Materials",
            "MATERIAL": "Constructions & Materials",
            "MATERIAL:NOMASS": "Constructions & Materials",
            "WINDOWMATERIAL:GLAZING": "Constructions & Materials",
            "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM": "Constructions & Materials",
            
            "SCHEDULE:COMPACT": "Schedules & Controls",
            "SCHEDULE:CONSTANT": "Schedules & Controls",
            "SCHEDULETYPELIMITS": "Schedules & Controls",
        }

        for obj in objects:
            t_upper = obj["type"].upper()
            n_clean = obj["name"].strip() if obj["name"] else ""
            
            # Skip objects that don't have a valid type
            if not obj["type"] or (obj["name"] == "N/A" and not obj["fields"]):
                continue
                
            assigned_zone = None
            if t_upper == "ZONE":
                assigned_zone = zone_names_lower.get(n_clean.lower(), n_clean)
            else:
                # 1. Check direct zone reference in fields
                for f in obj["fields"]:
                    val = f.split('!')[0].strip().rstrip(',;').strip().lower()
                    if val in zone_names_lower:
                        assigned_zone = zone_names_lower[val]
                        break
                
                # 2. Check parent surface reference
                if not assigned_zone:
                    for f in obj["fields"]:
                        val = f.split('!')[0].strip().rstrip(',;').strip().lower()
                        if val in surface_to_zone:
                            assigned_zone = surface_to_zone[val]
                            break

            # Add to grouped list
            if assigned_zone and assigned_zone in zone_grouped:
                cat = ZONE_CATEGORIES.get(t_upper, "Other Zone Objects")
                if cat not in zone_grouped[assigned_zone]:
                    zone_grouped[assigned_zone][cat] = []
                zone_grouped[assigned_zone][cat].append(obj)
            else:
                cat = GLOBAL_CATEGORIES.get(t_upper, "General / Other")
                if cat not in zone_grouped["Global / Shared"]:
                    zone_grouped["Global / Shared"][cat] = []
                zone_grouped["Global / Shared"][cat].append(obj)

        # Build list of sorted zones with Global/Shared at the front
        sorted_zones = ["Global / Shared"] + sorted([z for z in zone_grouped.keys() if z != "Global / Shared"])

        # Define color palette for dynamic cards
        colors = ["#2563eb", "#0d9488", "#7c3aed", "#d97706", "#db2777", "#4f46e5"]
        zone_colors = {}
        for idx, z in enumerate(sorted_zones):
            if z == "Global / Shared":
                zone_colors[z] = "#4b5563"
            else:
                zone_colors[z] = colors[idx % len(colors)]

        # Build sidebar HTML for quick navigation
        sidebar_html = '<div class="sidebar"><h3>Navigation</h3><ul>'
        for z in sorted_zones:
            categories = zone_grouped[z]
            if not categories or all(len(objs) == 0 for objs in categories.values()):
                continue
            icon = "⚙️" if z == "Global / Shared" else "🚪"
            z_id = "card_" + "".join(c if c.isalnum() else "_" for c in z)
            sidebar_html += f'<li><a href="#{z_id}">{icon} {z}</a></li>'
        sidebar_html += '</ul></div>'

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IDF Object Summary - SmartBEM Studio</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        
        html {{
            scroll-behavior: smooth;
        }}

        .layout-wrapper {{
            display: grid;
            grid-template-columns: 280px 1fr;
            gap: 32px;
            align-items: start;
        }}

        .sidebar {{
            position: sticky;
            top: 40px;
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-subtle);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
            padding: 24px;
        }}

        .sidebar h3 {{
            margin-top: 0;
            margin-bottom: 16px;
            font-size: 1rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 12px;
        }}

        .sidebar ul {{
            list-style: none;
            padding: 0;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .sidebar li a {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 14px;
            text-decoration: none;
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.95rem;
            border-radius: var(--radius-sm);
            transition: all 0.2s ease;
        }}

        .sidebar li a:hover {{
            background: #f1f5f9;
            color: var(--text-primary);
        }}

        .main-content {{
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}

        :root {{
            --bg-app: #f4f6fc;
            --bg-card: #ffffff;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --border-subtle: rgba(226, 232, 240, 0.8);
            --radius-lg: 16px;
            --radius-md: 12px;
            --radius-sm: 8px;
            --font-main: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            --font-mono: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }}

        body {{
            font-family: var(--font-main);
            background-color: var(--bg-app);
            color: var(--text-primary);
            margin: 0;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            background: linear-gradient(135deg, #1e293b, #0f172a);
            color: #ffffff;
            padding: 32px 40px;
            border-radius: var(--radius-lg);
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
            margin-bottom: 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }}

        header h1 {{
            margin: 0;
            font-size: 1.8rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        header p {{
            margin: 8px 0 0 0;
            color: #94a3b8;
            font-size: 0.95rem;
        }}

        .job-id {{
            background: rgba(255, 255, 255, 0.06);
            padding: 8px 16px;
            border-radius: var(--radius-sm);
            font-family: var(--font-mono);
            font-size: 0.85rem;
            color: #e2e8f0;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            align-items: start;
        }}

        .global-card {{
            grid-column: span 2;
        }}

        .zone-card {{
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-subtle);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            display: block;
        }}

        .zone-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.06);
        }}

        details.zone-card summary {{
            cursor: pointer;
            padding: 24px;
            list-style: none;
            user-select: none;
            transition: background-color 0.2s;
        }}

        details.zone-card summary::-webkit-details-marker {{
            display: none;
        }}

        details.zone-card summary:hover {{
            background-color: #fafbfd;
        }}

        .zone-header-wrapper {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            width: 100%;
        }}

        .card-chevron {{
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--text-muted);
            transition: transform 0.2s ease;
        }}

        details.zone-card[open] summary .card-chevron {{
            transform: rotate(90deg);
            color: var(--accent-color);
        }}

        .card-content {{
            padding: 24px;
            border-top: 1px solid #f1f5f9;
            background: var(--bg-card);
        }}

        .zone-title {{
            margin: 0;
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .zone-badge {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            padding: 4px 8px;
            border-radius: 20px;
            background: #f1f5f9;
            color: var(--text-secondary);
        }}

        .category-sec {{
            margin-bottom: 20px;
        }}

        .category-title {{
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin: 16px 0 10px 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .category-title::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: #e2e8f0;
            margin-left: 12px;
        }}

        .objects-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        details {{
            border: 1px solid #e2e8f0;
            border-radius: var(--radius-sm);
            background: #fafafa;
            overflow: hidden;
            transition: border-color 0.2s, background-color 0.2s;
        }}

        details[open] {{
            border-color: var(--accent-color);
            background: #ffffff;
        }}

        summary {{
            cursor: pointer;
            padding: 10px 14px;
            font-weight: 500;
            font-size: 0.9rem;
            color: var(--text-primary);
            list-style: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
            user-select: none;
            transition: background-color 0.2s;
        }}

        summary:hover {{
            background-color: #f1f5f9;
        }}

        summary::-webkit-details-marker {{
            display: none;
        }}

        .summary-chevron {{
            font-size: 1.1rem;
            font-weight: bold;
            color: var(--text-muted);
            transition: transform 0.2s ease;
        }}

        details[open] summary .summary-chevron {{
            transform: rotate(90deg);
            color: var(--accent-color);
        }}

        .fields-container {{
            border-top: 1px solid #f1f5f9;
            background: #ffffff;
        }}

        .fields-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }}

        .fields-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid #f1f5f9;
            vertical-align: top;
        }}

        .fields-table tr:last-child td {{
            border-bottom: none;
        }}

        .field-desc {{
            color: var(--text-secondary);
            font-weight: 500;
            width: 40%;
            border-right: 1px solid #f1f5f9;
        }}

        .field-val {{
            color: var(--text-primary);
            font-family: var(--font-mono);
            word-break: break-all;
            padding-left: 12px;
        }}

        .field-raw {{
            color: var(--text-secondary);
            font-family: var(--font-mono);
            background: #f8fafc;
            padding: 6px 12px;
            font-size: 0.8rem;
        }}

        /* Responsive adaptations */
        @media (max-width: 1024px) {{
            .layout-wrapper {{
                grid-template-columns: 1fr;
            }}
            .sidebar {{
                position: relative;
                top: 0;
            }}
        }}

        @media (max-width: 900px) {{
            .dashboard-grid {{
                grid-template-columns: 1fr;
            }}
            .global-card {{
                grid-column: span 1;
            }}
            details.zone-card[open] summary .card-chevron {{
                transform: rotate(90deg);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>SmartBEM Studio</h1>
                <p>Interactive Zone-wise Model Summary</p>
            </div>
            <div class="job-id">Job ID: {job_id}</div>
        </header>
        <div class="layout-wrapper">
            {sidebar_html}
            <div class="main-content">
                <div class="dashboard-grid">'''

        for z in sorted_zones:
            color = zone_colors[z]
            categories = zone_grouped[z]
            
            # Skip zones that have no objects at all
            if not categories or all(len(objs) == 0 for objs in categories.values()):
                continue
                
            # Count total objects in this zone
            total_objs = sum(len(objs) for objs in categories.values())
            
            icon = "⚙️" if z == "Global / Shared" else "🚪"
            card_class = "zone-card global-card" if z == "Global / Shared" else "zone-card"
            z_id = "card_" + "".join(c if c.isalnum() else "_" for c in z)
            html += f'''
            <details class="{card_class}" id="{z_id}" style="--accent-color: {color}; border-top: 4px solid {color};" open>
                <summary>
                    <div class="zone-header-wrapper">
                        <h2 class="zone-title">
                            <span>{icon} {z}</span>
                        </h2>
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span class="zone-badge">{total_objs} Objects</span>
                            <span class="card-chevron">›</span>
                        </div>
                    </div>
                </summary>
                <div class="card-content">
            '''
            
            # Sort categories so they appear in a consistent order
            for cat in sorted(categories.keys()):
                objs = categories[cat]
                if not objs:
                    continue
                    
                html += f'''
                <div class="category-sec">
                    <h3 class="category-title">{cat} <span style="font-weight: normal; font-size: 0.85em; color: var(--text-muted);">({len(objs)})</span></h3>
                    <div class="objects-list">
                '''
                
                for obj in objs:
                    n = obj["name"]
                    fields = obj["fields"]
                    
                    t_short = obj["type"]
                    display_name = n if (n and n != "N/A") else t_short
                    
                    if not fields:
                        html += f'''
                        <div style="padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: var(--radius-sm); background: #fafafa; font-size: 0.9rem; font-weight: 500; display: flex; justify-content: space-between; align-items: center;">
                            <span>{display_name}</span>
                            <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono); font-weight: normal;">{t_short}</span>
                        </div>
                        '''
                    else:
                        html += f'''
                        <details>
                            <summary>
                                <span style="display: flex; flex-direction: column; align-items: flex-start; gap: 2px;">
                                    <span>{display_name}</span>
                                    <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono); font-weight: normal;">{t_short}</span>
                                </span>
                                <span class="summary-chevron">›</span>
                            </summary>
                            <div class="fields-container">
                                <table class="fields-table">
                        '''
                        for f in fields:
                            # Safely escape HTML characters like < and >
                            f_clean = f.replace("<", "&lt;").replace(">", "&gt;")
                            if '!-' in f_clean:
                                parts = f_clean.split('!-')
                                val = parts[0].strip().rstrip(',;')
                                desc = parts[1].strip()
                                html += f'''
                                <tr>
                                    <td class="field-desc">{desc}</td>
                                    <td class="field-val">{val}</td>
                                </tr>
                                '''
                            else:
                                html += f'''
                                <tr>
                                    <td colspan="2" class="field-raw">{f_clean}</td>
                                </tr>
                                '''
                        html += '''
                                </table>
                            </div>
                        </details>
                        '''
                html += '''
                    </div>
                </div>
                '''
            html += '</div></details>'
        html += '</div></div></div></div></body></html>'
        
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
        if chart_generator.generate_3d_html(idf_path, geometry_path):
            results["geometry"] = geometry_path
            print(f"[{job_id}] Successfully generated geometry.html")
    except Exception as e:
        print(f"[{job_id}] Error generating 3D geometry: {e}")

    return results
