"""
Offline test for multi-zone geometry generation.
Tests resolve_zone_origins() and generate_multizone_geometry() 
without calling any AI API.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
import geometry_util

# Simulate a 2-zone layout: LivingRoom (anchor) + Bedroom (North of LivingRoom)
test_zones = [
    {
        "name": "LivingRoom",
        "length": 6.0,
        "width": 5.0,
        "height": 3.0,
        "relative_to": None,
        "direction": None,
        "wall_construction": "Composite 2x4 Wood Stud R11",
        "wwr_south": 0.3,
        "wwr_north": 0.0,
        "wwr_east": 0.15,
        "wwr_west": 0.0,
    },
    {
        "name": "Bedroom",
        "length": 6.0,
        "width": 4.0,
        "height": 3.0,
        "relative_to": "LivingRoom",
        "direction": "North",
        "wall_construction": "Composite 2x4 Wood Stud R11",
        "wwr_south": 0.0,
        "wwr_north": 0.2,
        "wwr_east": 0.1,
        "wwr_west": 0.0,
    }
]

print("=" * 60)
print("TEST 1: resolve_zone_origins()")
print("=" * 60)

origins = geometry_util.resolve_zone_origins(test_zones)
for name, origin in origins.items():
    print(f"  {name}: origin = ({origin[0]:.1f}, {origin[1]:.1f}, {origin[2]:.1f})")

# Validate
assert origins["LivingRoom"] == (0.0, 0.0, 0.0), "LivingRoom should be at (0,0,0)"
assert origins["Bedroom"] == (0.0, 5.0, 0.0), "Bedroom should be at (0, 5, 0) — North of LivingRoom"
print("  ✅ Origins correct!")

print()
print("=" * 60)
print("TEST 2: generate_multizone_geometry()")
print("=" * 60)

idf_str, adjacencies = geometry_util.generate_multizone_geometry(test_zones, origins)

# Check adjacencies
print(f"  Adjacencies: {adjacencies}")
assert len(adjacencies) > 0, "Should detect at least 1 adjacency"
assert any("LivingRoom_North" in a and "Bedroom_South" in a for a in adjacencies), \
    "Should detect LivingRoom_North <-> Bedroom_South adjacency"
print("  ✅ Adjacency detection correct!")

# Check that both zones exist
assert "LivingRoom," in idf_str, "LivingRoom zone should exist"
assert "Bedroom," in idf_str, "Bedroom zone should exist"
print("  ✅ Both zones present in IDF")

# Check interior partition walls
assert "Surface" in idf_str, "Should have Surface boundary conditions"
assert "Interior_Partition" in idf_str, "Should have interior partition construction"
print("  ✅ Interior partition walls generated")

# Check that shared walls don't have windows
assert "LivingRoom_Wall_North_Window" not in idf_str, "No window on shared LivingRoom north wall"
assert "Bedroom_Wall_South_Window" not in idf_str, "No window on shared Bedroom south wall"
print("  ✅ No windows on shared walls")

# Check exterior walls have windows
assert "LivingRoom_Wall_South_Window" in idf_str, "LivingRoom south wall should have a window (wwr=0.3)"
assert "Bedroom_Wall_North_Window" in idf_str, "Bedroom north wall should have a window (wwr=0.2)"
print("  ✅ Windows on exterior walls present")

# Save the output for inspection
output_path = os.path.join(os.path.dirname(__file__), "test_multizone_output.idf")
with open(output_path, "w") as f:
    f.write(idf_str)
print(f"\n  📄 Full IDF output saved to: {output_path}")

print()
print("=" * 60)
print("TEST 3: 3-zone layout (LivingRoom + Bedroom_North + Kitchen_East)")
print("=" * 60)

test_zones_3 = [
    {
        "name": "LivingRoom",
        "length": 6.0, "width": 5.0, "height": 3.0,
        "relative_to": None, "direction": None,
        "wall_construction": "Composite 2x4 Wood Stud R11",
        "wwr_south": 0.3, "wwr_north": 0.0, "wwr_east": 0.0, "wwr_west": 0.15,
    },
    {
        "name": "Bedroom",
        "length": 6.0, "width": 4.0, "height": 3.0,
        "relative_to": "LivingRoom", "direction": "North",
        "wall_construction": "Composite 2x4 Wood Stud R11",
        "wwr_south": 0.0, "wwr_north": 0.2, "wwr_east": 0.1, "wwr_west": 0.0,
    },
    {
        "name": "Kitchen",
        "length": 4.0, "width": 5.0, "height": 3.0,
        "relative_to": "LivingRoom", "direction": "East",
        "wall_construction": "Composite 2x4 Wood Stud R11",
        "wwr_south": 0.2, "wwr_north": 0.0, "wwr_east": 0.25, "wwr_west": 0.0,
    }
]

origins_3 = geometry_util.resolve_zone_origins(test_zones_3)
for name, origin in origins_3.items():
    print(f"  {name}: origin = ({origin[0]:.1f}, {origin[1]:.1f}, {origin[2]:.1f})")

assert origins_3["Kitchen"] == (6.0, 0.0, 0.0), "Kitchen should be at (6, 0, 0) — East of LivingRoom"
print("  ✅ 3-zone origins correct!")

idf_3, adj_3 = geometry_util.generate_multizone_geometry(test_zones_3, origins_3)
print(f"  Adjacencies: {adj_3}")
assert len(adj_3) == 2, f"Should detect 2 adjacencies, got {len(adj_3)}"
print("  ✅ 3-zone adjacency detection correct!")

print()
print("🎉 ALL TESTS PASSED!")
