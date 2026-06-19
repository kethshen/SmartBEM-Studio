# EnergyPlus Utility Codebase Summary

A concise reference for the `EnergyPlus utility` library.

---

## File: `eplus_util.py`
The core library (~6700 lines). Handles simulation execution, data extraction, and runtime interaction.

### Section A: System & Initialization (Lines 1-600)
*   **`EPlusUtil.__init__`**: Initializes the EnergyPlus API, creates a new state, and clears old callbacks.
*   **`_register_callbacks`**: internal helper that connects Python functions to EnergyPlus hooks (e.g., `callback_begin_zone_timestep_after_init_heat_balance`).
*   **`register_callback`**: Public method to add a custom callback function (low-level).
*   **`register_handlers`**: High-level method to register multiple named handlers (string-based) for specific events like "begin" or "end".

### Section B: Setup & Runners (Lines 600-2000)
*   **`set_model`**: Sets the IDF, EPW, and output directory; optionally triggers CO₂ patching.
*   **`prepare_run_with_co2`**: Patches the IDF to inject `ZoneAirContaminantBalance` and People objects for CO₂ tracking.
*   **`list_zone_names`**: Returns a list of all thermal zones in the model (scans IDF/SQL/API).
*   **`api_catalog_df`**: Returns a DataFrame of all available API actuators, variables, and meters.
*   **`run_annual`**: Runs a full annual simulation. Cleans old outputs, resets state, and calls `run_energyplus`.
*   **`run_design_day`**: Runs the simulation only for the design days (ignoring the weather file run period).
*   **`dry_run_min`**: Runs a minimal simulation (1 timestep) just to generate the dictionary files (RDD/MDD).
*   **`set_simulation_params`**: Patches the IDF's `SimulationControl` and `Timestep` objects.

### Section D: Runtime Helpers (Lines 3600-4400)
*   **`enable_hvac_off_via_schedules`**: Kill Switch. Forces HVAC routines to "Off" by overriding availability schedules to 0.0.
*   **`occupancy_handler`**: Stochastic Occupancy. Randomizes the number of people in each zone using a Poisson distribution.
*   **`co2_set_outdoor_ppm`**: Overrides the outdoor CO₂ concentration schedule dynamically during the run.
*   **`probe_zone_air_and_supply`**: **The Mega Probe.** Snapshots the entire building state (Air Temp/Humidity/CO₂ + Supply Flow/Temp) for every zone at every timestep.
*   **`api_check_zone_humidity_ratio`**: Validation tool to compare API-reported humidity against manually calculated humidity (Tetens formula).

### Section E: Outputs & Data (Lines 2000-3600)
*   **`ensure_output_sqlite`**: Patches IDF to add `Output:SQLite` so data is saved to `eplusout.sql`.
*   **`ensure_output_variables`**: Adds `Output:Variable` objects to the IDF without creating duplicates.
*   **`inspect_sql_meter`**: Prints a summary of available meter data in the SQL file.
*   **`get_sql_series_dataframe`**: **The Bridge.** Extracts time-series data from `eplusout.sql` into a tidy Pandas DataFrame.
*   **`plot_sql_series`**: Visualizes simulation results using interactive Plotly charts.
*   **`plot_sql_cov_heatmap`**: Generates a correlation heatmap between inputs and outputs.
*   **`export_weather_sql_to_csv`**: Extracts weather data (ground truth) from the results to a CSV file.

### Section F: Extended Kalman Filter (EKF) (Lines 4400-6700)
*   **`_ekf_update`**: Implements the math for the Extended Kalman Filter (Predict & Update steps).
*   **`_kf_prepare_inputs_zone_energy_model`**: Defines the "3R2C" physics model (thermal circuit) used by the filter.
*   **`probe_zone_air_and_supply_with_kf`**: Runs the EKF alongside the simulation, estimating hidden states and saving them to a custom SQL table.
*   **`runtime_get_actuator`**: Safe wrapper to get actuator values (handles caching & warmup checks).
*   **`runtime_set_actuator`**: Safe wrapper to set actuator values (handles caching, clamping, & logging).
*   **`runtime_get_variable`**: Safe wrapper to read variable values.
*   **`runtime_get_meter`**: Safe wrapper to read meter values.

---

## File: `colab_bootstrap.py`
Helper script for installing EnergyPlus on Linux/Colab.

*   **`prepare_colab_eplus`**: Main setup function. Installs dependencies, downloads E+, and configures the environment.
*   **`_apt_install`**: Installs required Linux packages (`libxcb`, `libx11`, etc.).
*   **`_ensure_libssl11`**: Installs `libssl1.1` (required legacy library) on modern Ubuntu systems.
*   **`_download_energyplus`**: Downloads and extracts the EnergyPlus tarball to the home directory.
*   **`_set_env_for_current_process`**: Sets `ENERGYPLUSDIR` and `LD_LIBRARY_PATH` variables so Python can find the DLLs.

---

## File: `sql_explorer.py`
Helper class for inspecting and extracting data from `eplusout.sql`.

*   **`EPlusSqlExplorer`**: Main class wrapping the SQLite connection.
*   **`auto_extract_series`**: Finds a variable, joins it with the Time table, and returns a DataFrame (converts J to kWh automatically).
*   **`list_sql_variables`**: Returns a list of all variables present in the output file.
*   **`list_tables`**: Lists all tables in the database.
*   **`peek`**: Shows the first 10 rows of a table.
*   **`get_table_data`**: Dumps an entire table (like the EKF results) to a DataFrame, auto-detecting timestamps.
