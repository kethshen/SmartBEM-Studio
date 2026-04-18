import os

def generate_zone_geometry(L, W, H, zone_name="Main_Zone"):
    """
    Generates standard CCW EnergyPlus vertices for a rectangular zone.
    L = Length (X-axis)
    W = Width (Y-axis)
    H = Height (Z-axis)
    """
    idf_str = ""
    
    # Zone Object
    idf_str += f"""
  Zone,
    {zone_name},             !- Name
    0,                       !- Direction of Relative North {{deg}}
    0, 0, 0,                 !- X,Y,Z  {{m}}
    1,                       !- Type
    1,                       !- Multiplier
    autocalculate,           !- Ceiling Height {{m}}
    autocalculate;           !- Volume {{m3}}
"""
    
    def make_surface(name, surf_type, constr, out_bound, sun, wind, v1, v2, v3, v4):
        return f"""
  BuildingSurface:Detailed,
    {name},                  !- Name
    {surf_type},             !- Surface Type
    {constr},                !- Construction Name
    {zone_name},             !- Zone Name
    {out_bound},             !- Outside Boundary Condition
    ,                        !- Outside Boundary Condition Object
    {sun},                   !- Sun Exposure
    {wind},                  !- Wind Exposure
    autocalculate,           !- View Factor to Ground
    4,                       !- Number of Vertices
    {v1[0]:.2f}, {v1[1]:.2f}, {v1[2]:.2f},  !- X,Y,Z ==> Vertex 1
    {v2[0]:.2f}, {v2[1]:.2f}, {v2[2]:.2f},  !- X,Y,Z ==> Vertex 2
    {v3[0]:.2f}, {v3[1]:.2f}, {v3[2]:.2f},  !- X,Y,Z ==> Vertex 3
    {v4[0]:.2f}, {v4[1]:.2f}, {v4[2]:.2f};  !- X,Y,Z ==> Vertex 4
"""

    # Using placeholder text that our backend Assembler will string-replace later.
    wall_constr = "{EXTERIOR_WALL_CONSTR}"
    roof_constr = "{ROOF_CONSTR}"
    floor_constr = "{FLOOR_CONSTR}"
    
    # CCW Vertices viewed from OUTSIDE
    # Wall South (Facing -Y)
    idf_str += make_surface("Wall_South", "Wall", wall_constr, "Outdoors", "SunExposed", "WindExposed", 
                       (L, 0, 0), (L, 0, H), (0, 0, H), (0, 0, 0))
    # Wall East (Facing +X)
    idf_str += make_surface("Wall_East", "Wall", wall_constr, "Outdoors", "SunExposed", "WindExposed", 
                       (L, W, 0), (L, W, H), (L, 0, H), (L, 0, 0))
    # Wall North (Facing +Y)
    idf_str += make_surface("Wall_North", "Wall", wall_constr, "Outdoors", "SunExposed", "WindExposed", 
                       (0, W, 0), (0, W, H), (L, W, H), (L, W, 0))
    # Wall West (Facing -X)
    idf_str += make_surface("Wall_West", "Wall", wall_constr, "Outdoors", "SunExposed", "WindExposed", 
                       (0, 0, 0), (0, 0, H), (0, W, H), (0, W, 0))
    
    # Roof (Facing +Z)
    idf_str += make_surface("Roof", "Roof", roof_constr, "Outdoors", "SunExposed", "WindExposed", 
                       (0, W, H), (0, 0, H), (L, 0, H), (L, W, H))
                       
    # Floor (Facing -Z)
    idf_str += make_surface("Floor", "Floor", floor_constr, "Ground", "NoSun", "NoWind", 
                       (0, W, 0), (L, W, 0), (L, 0, 0), (0, 0, 0))
                       
    return idf_str

if __name__ == "__main__":
    # Test
    print("Testing Geometry generation for a 10m x 8m x 3m house.")
    geometry_idf = generate_zone_geometry(L=10, W=8, H=3)
    print(geometry_idf)
    print("Successfully Generated 6 BuildingSurfaces and 1 Zone object!")
