import os
import sys

# Ensure we can import from the colab directory
colab_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(colab_dir)

try:
    import openstudio
    print("OpenStudio SDK Version:", openstudio.openStudioLongVersion())
except ImportError:
    print("Error: OpenStudio is not installed in the local Python environment.")
    print("Please install it: pip install openstudio==3.10.0")
    sys.exit(1)

from backend.openstudio_builder import build_idf_from_params

# Single-zone test parameters
sz_params = {
    "is_multizone": False,
    "length": 12.0,
    "width": 8.0,
    "height": 3.0,
    "wall_layers": "Composite 2x4 Wood Stud R11",
    "roof_layers": "Composite 2x4 Wood Stud R11",
    "window_layers": "Theoretical Glass [167]",
    "wwr_south": 0.3,
    "wwr_north": 0.1,
    "hvac_type": "ptac"
}

# Multi-zone test parameters
mz_params = {
    "is_multizone": True,
    "zones": [
        {
            "name": "LivingRoom",
            "length": 10.0,
            "width": 6.0,
            "height": 3.0,
            "relative_to": None,
            "direction": None,
            "wwr_south": 0.2,
            "hvac_type": "ideal_loads"
        },
        {
            "name": "Bedroom",
            "length": 10.0,
            "width": 6.0, # Must match adjacent side dimension
            "height": 3.0,
            "relative_to": "LivingRoom",
            "direction": "North",
            "wwr_north": 0.1,
            "hvac_type": "ptac"
        }
    ],
    "people_density": 12.0,
    "light_density": 8.0,
    "equipment_density": 10.0,
    "hvac_type": "ideal_loads"
}

print("\n--- Running Single Zone OpenStudio translation test ---")
try:
    sz_idf = build_idf_from_params(sz_params)
    print("Success! Generated Single Zone IDF of length:", len(sz_idf))
    out_sz = os.path.join(colab_dir, "test_sz_os.idf")
    with open(out_sz, "w", encoding="utf-8") as f:
        f.write(sz_idf)
    print("Written to:", out_sz)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Failed Single Zone translation:", e)

print("\n--- Running Multi Zone OpenStudio translation test ---")
try:
    mz_idf = build_idf_from_params(mz_params)
    print("Success! Generated Multi Zone IDF of length:", len(mz_idf))
    out_mz = os.path.join(colab_dir, "test_mz_os.idf")
    with open(out_mz, "w", encoding="utf-8") as f:
        f.write(mz_idf)
    print("Written to:", out_mz)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Failed Multi Zone translation:", e)
