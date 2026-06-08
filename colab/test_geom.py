import sys
sys.path.append(r"d:\UNI\Sem 7\ME420 Mech Eng Research Project\SmartHVAC-Studio\colab\backend")
import geometry_util

zones = [
    {
        "name": "Office",
        "length": 5.0,
        "width": 8.0,
        "height": 3.5,
        "door_west": {"width": 0.6, "height": 1.5, "offset_x": 0.5, "ref_x": "left"}
    }
]
zone_origins = {"Office": (0.0, 0.0, 0.0)}

idf_str, _ = geometry_util.generate_multizone_geometry(zones, zone_origins)

for line in idf_str.split("\n"):
    if "Office_Wall_West" in line or "Vertex" in line or "BuildingSurface:Detailed" in line or "FenestrationSurface:Detailed" in line:
        print(line)
