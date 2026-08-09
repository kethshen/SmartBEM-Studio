import os
import sys
import subprocess
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Ensure stdout handles UTF-8 on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Paths
ENERGYPLUS_EXE = r"C:\EnergyPlusV25-2-0\energyplus.exe"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR = os.path.dirname(BASE_DIR)

TEMPLATE_IDF = os.path.join(STUDIO_DIR, "hanger_chamber_master.idf")
CALIBRATED_IDF = os.path.join(BASE_DIR, "chamber_calibrated.idf")
WEATHER_EPW = os.path.join(BASE_DIR, "sensor_readings", "weather", "test_day_weather.epw")
OUTPUT_DIR = os.path.join(BASE_DIR, "sim_output")

STANDARD_EPW_SRC = r"C:\EnergyPlusV25-2-0\WeatherData\USA_FL_Tampa.Intl.AP.722110_TMY3.epw"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_test_day_epw(cleaned_csv_path, output_epw_path):
    """
    Copies a standard valid 8760-hour EPW template, updates LOCATION to Colombo Sri Lanka,
    and overwrites July 21 (Month 7, Day 21) with actual outdoor sensor logs (outside_t).
    """
    df_sensor = pd.read_csv(cleaned_csv_path)
    t_out = df_sensor['outside_t'].fillna(30.0).values
    
    if len(t_out) >= 24:
        hourly_t = np.array_split(t_out, 24)
        hourly_t_avg = [np.mean(h) for h in hourly_t]
    else:
        hourly_t_avg = [30.0] * 24

    with open(STANDARD_EPW_SRC, "r", encoding="utf-8") as f:
        epw_lines = f.readlines()
        
    # Update LOCATION header line to Colombo Sri Lanka
    epw_lines[0] = "LOCATION,Colombo,Western,Sri Lanka,CUSTOM-RIG-TEST,434000,6.90,79.86,6.0,14.0\n"
    
    new_epw_lines = epw_lines[:8] # Keep original valid headers
    
    for line in epw_lines[8:]:
        parts = line.split(',')
        if len(parts) > 6:
            try:
                month = int(parts[1])
                day = int(parts[2])
                hour = int(parts[3])
                
                # Overwrite July 21 (Month 7, Day 21) with actual sensor data
                if month == 7 and day == 21:
                    t_sensor = hourly_t_avg[hour - 1] if 1 <= hour <= 24 else 30.0
                    parts[6] = f"{t_sensor:.1f}" # Dry Bulb Temperature
                    parts[7] = f"{t_sensor - 3.0:.1f}" # Dew Point Temperature
                    line = ",".join(parts)
            except Exception:
                pass
        new_epw_lines.append(line)
        
    with open(output_epw_path, "w", encoding="utf-8") as f:
        f.writelines(new_epw_lines)
    print(f"Generated custom EPW weather file (Colombo Sri Lanka July 21 calibrated): {output_epw_path}")

def update_idf_template():
    """
    Loads hanger_chamber_master.idf and deterministically updates the calibrated physical parameters:
    1. Version -> 25.2
    2. Material Chamber_PU_Foam -> k=0.08, rho=100, Cp=1543
    3. Material Brick_Core_220mm -> 0.220m (SLS 855)
    4. Material Cement_Plaster_15mm -> 0.015m
    5. RunPeriod -> July 21
    6. SimulationControl -> Run for weather file = Yes
    """
    if not os.path.exists(TEMPLATE_IDF):
        print(f"Error: Base template IDF not found at {TEMPLATE_IDF}")
        return False
        
    with open(TEMPLATE_IDF, "r", encoding="utf-8") as f:
        content = f.read()
        
    content = content.replace("25.1;                                   !- Version Identifier", "25.2;                                   !- Version Identifier")

    # Update Site:Location to Colombo Sri Lanka
    old_loc = """Site:Location,
    CHICAGO_IL_USA TMY2-94846,  !- Name
    41.78000,                !- Latitude {deg}
    -87.75000,               !- Longitude {deg}
    -6.000000,               !- Time Zone {hr}
    190.0000;"""
    
    new_loc = """Site:Location,
    COLOMBO_SRI_LANKA,        !- Name
    6.90000,                 !- Latitude {deg}
    79.86000,                !- Longitude {deg}
    6.000000,                !- Time Zone {hr}
    14.0000;"""
    content = content.replace(old_loc, new_loc)

    # Update Chamber_PU_Foam material parameters
    content = content.replace("0.0220,            !- Thermal Conductivity {W/m-K}", "0.0800,            !- Thermal Conductivity {W/m-K}")
    content = content.replace("32.00,             !- Density {kg/m3}", "100.00,            !- Density {kg/m3}")
    content = content.replace("1500.00,           !- Specific Heat {J/kg-K}", "1543.00,           !- Specific Heat {J/kg-K}")

    # Add 220mm Sri Lanka Standard Brick and 15mm Plaster materials
    sls_brick_materials = """
  Material,
    Cement_Plaster_15mm,                   !- Name
    Smooth,                  !- Roughness
    0.0150,             !- Thickness {m}
    0.7200,            !- Thermal Conductivity {W/m-K}
    1860.00,           !- Density {kg/m3}
    840.00;            !- Specific Heat {J/kg-K}

  Material,
    Brick_Core_220mm,                   !- Name
    MediumRough,             !- Roughness
    0.2200,             !- Thickness {m} (SLS 855 Sri Lanka Standard)
    0.7700,            !- Thermal Conductivity {W/m-K}
    1920.00,           !- Density {kg/m3}
    840.00;            !- Specific Heat {J/kg-K}

  Construction,
    Hanger_Composite_Wall_250mm,            !- Name
    Cement_Plaster_15mm,         !- Layer 1 (Outside)
    Brick_Core_220mm,            !- Layer 2 (Core)
    Cement_Plaster_15mm;         !- Layer 3 (Inside)
"""
    if "Hanger_Composite_Wall_250mm" not in content:
        content += sls_brick_materials

    # Replace RunPeriod block with EnergyPlus V25 valid syntax for July 21
    new_runperiod = """RunPeriod,
    Run Period 1,            !- Name
    7,                       !- Begin Month
    21,                      !- Begin Day of Month
    2026,                    !- Begin Year
    7,                       !- End Month
    21,                      !- End Day of Month
    2026,                    !- End Year
    Tuesday,                 !- Day of Week for Start Day
    No,                      !- Use Weather File Holidays and Special Days
    No,                      !- Use Weather File Daylight Saving Period
    No,                      !- Apply Weekend Holiday Rule
    Yes,                     !- Rain Indicator
    Yes;                     !- Snow Indicator
"""
    if "RunPeriod," in content:
        idx_start = content.find("RunPeriod,")
        idx_end = content.find(";", idx_start)
        if idx_start != -1 and idx_end != -1:
            content = content[:idx_start] + new_runperiod + content[idx_end+1:]

    content = content.replace("No,                      !- Run Simulation for Weather File Run Periods", "Yes,                     !- Run Simulation for Weather File Run Periods")
    content = content.replace("Yes,                     !- Run Simulation for Sizing Periods", "No,                      !- Run Simulation for Sizing Periods")
    
    with open(CALIBRATED_IDF, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Updated and saved calibrated IDF to: {CALIBRATED_IDF}")
    return True

def run_simulation():
    """Executes local EnergyPlus executable in 1-2 seconds."""
    if not os.path.exists(ENERGYPLUS_EXE):
        print(f"Error: EnergyPlus executable not found at {ENERGYPLUS_EXE}")
        return False
        
    cmd = [
        ENERGYPLUS_EXE,
        "-w", WEATHER_EPW,
        "-d", OUTPUT_DIR,
        CALIBRATED_IDF
    ]
    
    print(f"\nExecuting EnergyPlus V25 directly on desktop...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Run ReadVarsESO to update eplusout.csv
    readvars_exe = r"C:\EnergyPlusV25-2-0\PostProcess\ReadVarsESO.exe"
    if os.path.exists(readvars_exe):
        subprocess.run([readvars_exe], cwd=OUTPUT_DIR, capture_output=True)
        
    csv_file = os.path.join(OUTPUT_DIR, "eplusout.csv")
    if os.path.exists(csv_file) and os.path.getsize(csv_file) > 100:
        print("\n======================================================================")
        print("SUCCESS: Desktop EnergyPlus Simulation (Colombo Sri Lanka) finished!")
        print(f"Output CSV generated at: {csv_file}")
        print("======================================================================")
        return True
    else:
        print("EnergyPlus Output Log:")
        print(result.stdout)
        err_file = os.path.join(OUTPUT_DIR, "eplusout.err")
        if os.path.exists(err_file):
            with open(err_file, "r") as ef:
                print("\neplusout.err contents:\n", ef.read())
        return False

if __name__ == "__main__":
    print("======================================================================")
    print("SmartBEM Studio — Desktop EnergyPlus Local Calibration Runner")
    print("======================================================================\n")
    
    part6_csv = os.path.join(BASE_DIR, "Full Day 1 part 6_2026-07-23.csv")
    if os.path.exists(part6_csv):
        create_test_day_epw(part6_csv, WEATHER_EPW)
        
    if update_idf_template():
        run_simulation()
