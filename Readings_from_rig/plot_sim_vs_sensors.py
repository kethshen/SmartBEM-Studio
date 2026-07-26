import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Ensure stdout handles UTF-8 on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIM_CSV = os.path.join(BASE_DIR, "sim_output", "eplusout.csv")
SENSOR_CSV = os.path.join(BASE_DIR, "Full Day 1 part 6_2026-07-23.csv")
PLOT_OUT = os.path.join(BASE_DIR, "plots", "cleaning_validation", "simulation_vs_sensors_overlay.png")

def plot_overlay():
    if not os.path.exists(SIM_CSV):
        print(f"Error: Simulation CSV not found at {SIM_CSV}")
        return
    if not os.path.exists(SENSOR_CSV):
        print(f"Error: Sensor CSV not found at {SENSOR_CSV}")
        return

    # Read Simulation Output CSV
    df_sim = pd.read_csv(SIM_CSV)
    df_sim.columns = [c.strip() for c in df_sim.columns]
    
    # Extract temperature columns
    t_sim_outdoor_col = [c for c in df_sim.columns if "Site Outdoor Air Drybulb Temperature" in c][0]
    t_sim_chamber_col = [c for c in df_sim.columns if "CHAMBER_THERMALZONE:Zone Mean Air Temperature" in c][0]
    t_sim_hanger_col = [c for c in df_sim.columns if "HANGER_THERMALZONE:Zone Mean Air Temperature" in c][0]
    
    # Time vector for simulation (hours to minutes)
    sim_time_min = np.linspace(0, 83.0, len(df_sim))

    # Read Cleaned Sensor CSV (Part 6)
    df_sensor = pd.read_csv(SENSOR_CSV)
    df_sensor['timestamp'] = pd.to_datetime(df_sensor['timestamp'])
    df_sensor['time_min'] = (df_sensor['timestamp'] - df_sensor['timestamp'].iloc[0]).dt.total_seconds() / 60.0
    
    # Calculate weighted Tz
    r1 = df_sensor['room_1_t']
    r2 = df_sensor['room_2_t']
    df_sensor['weighted_Tz'] = 0.6 * r1.fillna(r2) + 0.4 * r2.fillna(r1)
    df_sensor['weighted_Tz_ema'] = df_sensor['weighted_Tz'].ewm(span=6, adjust=False).mean()
    df_sensor['outside_t_ema'] = df_sensor['outside_t'].ewm(span=6, adjust=False).mean()

    # Create Plot
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot Real Rig Sensors
    ax.plot(df_sensor['time_min'], df_sensor['outside_t_ema'], color='orange', linewidth=2.0, label='Real Sensor Outdoor Temp (T_out)')
    ax.plot(df_sensor['time_min'], df_sensor['weighted_Tz_ema'], color='darkblue', linewidth=2.5, label='Real Sensor Zone Temp (T_z) — 0.6*S1 + 0.4*S2')
    
    # Plot EnergyPlus Simulation Curves
    ax.plot(sim_time_min, df_sim[t_sim_outdoor_col], color='red', linestyle='--', linewidth=2.0, label='EnergyPlus Sim Outdoor Temp')
    ax.plot(sim_time_min, df_sim[t_sim_chamber_col], color='cyan', linestyle='--', linewidth=2.5, label='EnergyPlus Sim Chamber Zone Temp (T_sim)')
    ax.plot(sim_time_min, df_sim[t_sim_hanger_col], color='green', linestyle=':', linewidth=1.8, label='EnergyPlus Sim Hanger Zone Temp')

    ax.set_title("EnergyPlus Desktop Simulation vs. Real Test Rig Sensors Overlay (Part 6)", fontsize=14, fontweight='bold')
    ax.set_xlabel("Time (minutes)", fontsize=11)
    ax.set_ylabel("Temperature (°C)", fontsize=11)
    ax.legend(loc='best', frameon=True)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    plt.tight_layout()
    plt.savefig(PLOT_OUT, dpi=150)
    plt.close()
    
    print(f"Overlay comparison plot saved to: {PLOT_OUT}")
    
    # Calculate RMSE Error between simulation and sensors
    # Interpolate simulation temperature to sensor timestamps
    sim_interp_tz = np.interp(df_sensor['time_min'], sim_time_min, df_sim[t_sim_chamber_col])
    rmse = np.sqrt(np.mean((sim_interp_tz - df_sensor['weighted_Tz_ema'])**2))
    print(f"\n======================================================================")
    print(f"SIMULATION VERIFICATION METRICS:")
    print(f"  - Calculated Temperature RMSE (Sim vs Sensor): {rmse:.3f} °C")
    print(f"  - Target Baseline UA_effective: 52.83 W/K")
    print(f"  - Target Baseline Cs: 3.80 x 10^5 J/K")
    print(f"======================================================================\n")

if __name__ == "__main__":
    plot_overlay()
