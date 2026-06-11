"""
Quick local test: generate a 4-zone IDF snippet and run the visualizer on it,
confirming zones appear at the correct world positions.
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from geometry_util import resolve_zone_origins, generate_multizone_geometry
from visualizer import generate_3d_html

zones = [
    {'name': 'Office',       'length': 6.0, 'width': 8.0, 'height': 4.0, 'wall_construction': 'Medium Exterior Wall', 'roof_construction': 'Light Roof/Ceiling'},
    {'name': 'Meeting Room', 'length': 6.0, 'width': 4.0, 'height': 4.0, 'relative_to': 'Office', 'direction': 'North', 'wall_construction': 'Medium Exterior Wall', 'roof_construction': 'Light Roof/Ceiling'},
    {'name': 'Lobby',        'length': 5.0, 'width': 8.0, 'height': 4.0, 'relative_to': 'Office', 'direction': 'East',  'wall_construction': 'Medium Exterior Wall', 'roof_construction': 'Light Roof/Ceiling'},
    {'name': 'Rest Room',    'length': 5.0, 'width': 4.0, 'height': 4.0, 'relative_to': 'Lobby',  'direction': 'North', 'wall_construction': 'Medium Exterior Wall', 'roof_construction': 'Light Roof/Ceiling'},
]

origins = resolve_zone_origins(zones)
print("Zone origins:", origins)

geo_idf, adj = generate_multizone_geometry(zones, origins)
print("Adjacencies:", adj)

# Build a minimal IDF file
header = """
  Version,25.2;
  GlobalGeometryRules,
    LowerLeftCorner,
    Counterclockwise,
    Relative;
"""

idf_text = header + geo_idf

idf_path = 'test_geometry.idf'
html_path = 'test_geometry.html'
with open(idf_path, 'w') as f:
    f.write(idf_text)

result = generate_3d_html(idf_path, html_path)
print("3D HTML generated:", result)
print(f"Open {os.path.abspath(html_path)} to view")
