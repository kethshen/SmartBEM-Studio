import os

def generate_zone_geometry(
    L, W, H, 
    wwr_s=0.0, wwr_n=0.0, wwr_e=0.0, wwr_w=0.0, 
    wall_s="{EXTERIOR_WALL_CONSTR}", wall_n="{EXTERIOR_WALL_CONSTR}", 
    wall_e="{EXTERIOR_WALL_CONSTR}", wall_w="{EXTERIOR_WALL_CONSTR}",
    door_s=None, door_n=None, door_e=None, door_w=None,
    window_s=None, window_n=None, window_e=None, window_w=None,
    zone_name="ZONE ONE"):
    """
    Generates standard CCW EnergyPlus vertices for a rectangular zone.
    L = Length (X-axis)
    W = Width (Y-axis)
    H = Height (Z-axis)
    """
    import math
    idf_str = ""
    
    # Zone Object
    idf_str += f"""
  Zone,
    {zone_name},             !- Name
    0,                       !- Direction of Relative North {{deg}}
    0,                       !- X Origin {{m}}
    0,                       !- Y Origin {{m}}
    0,                       !- Z Origin {{m}}
    1,                       !- Type
    1,                       !- Multiplier
    autocalculate,           !- Ceiling Height {{m}}
    autocalculate;           !- Volume {{m3}}
"""
    
    def make_surface(name, surf_type, constr, out_bound, sun, wind, v1, v2, v3, v4):
        vf = "0.50" if surf_type == "Wall" else "0"
        return f"""
  BuildingSurface:Detailed,
    {name},                  !- Name
    {surf_type},             !- Surface Type
    {constr},                !- Construction Name
    {zone_name},             !- Zone Name
    ,                        !- Space Name
    {out_bound},             !- Outside Boundary Condition
    ,                        !- Outside Boundary Condition Object
    {sun},                   !- Sun Exposure
    {wind},                  !- Wind Exposure
    {vf},                    !- View Factor to Ground
    4,                       !- Number of Vertices
    {v1[0]:.2f}, {v1[1]:.2f}, {v1[2]:.2f},  !- X,Y,Z ==> Vertex 1
    {v2[0]:.2f}, {v2[1]:.2f}, {v2[2]:.2f},  !- X,Y,Z ==> Vertex 2
    {v3[0]:.2f}, {v3[1]:.2f}, {v3[2]:.2f},  !- X,Y,Z ==> Vertex 3
    {v4[0]:.2f}, {v4[1]:.2f}, {v4[2]:.2f};  !- X,Y,Z ==> Vertex 4
"""

    def make_window(wall_name, v1, v4, wall_width, wall_height, wwr_val, window_data=None):
        if window_data and isinstance(window_data, dict):
            # Custom Window Placement
            win_w = window_data.get("width", 1.0)
            win_h = window_data.get("height", 1.0)
            offset_x = window_data.get("offset_x", 0)
            ref_x = window_data.get("ref_x", "center")
            offset_z = window_data.get("offset_z", 0)
            ref_z = window_data.get("ref_z", "center")
            
            # v1 is Bottom-Right (from outside), v4 is Bottom-Left
            # If ref_x is 'left', it is offset from v4. So distance from v1 (w_off) is wall_width - win_w - offset_x
            if ref_x == "left":
                w_off = wall_width - win_w - offset_x
            elif ref_x == "right":
                w_off = offset_x
            else:
                w_off = (wall_width - win_w) / 2.0
                
            if ref_z == "bottom":
                h_off = offset_z
            elif ref_z == "top":
                h_off = wall_height - win_h - offset_z
            else:
                h_off = (wall_height - win_h) / 2.0
        else:
            # WWR Center Alignment (Fallback)
            if not wwr_val or wwr_val <= 0 or wwr_val >= 1: return ""
            win_w = wall_width * math.sqrt(wwr_val)
            win_h = wall_height * math.sqrt(wwr_val)
            w_off = (wall_width - win_w) / 2.0
            h_off = (wall_height - win_h) / 2.0
        
        def interpolate(pA, pB, frac):
            return (pA[0] + (pB[0]-pA[0])*frac, pA[1] + (pB[1]-pA[1])*frac, pA[2] + (pB[2]-pA[2])*frac)
            
        win_br_x, win_br_y, win_br_z = interpolate(v1, v4, w_off / wall_width)
        win_bl_x, win_bl_y, win_bl_z = interpolate(v1, v4, (w_off + win_w) / wall_width)
        
        z_bottom = v1[2] + h_off
        z_top = z_bottom + win_h
        
        return f"""
  FenestrationSurface:Detailed,
    {wall_name}_Window,      !- Name
    Window,                  !- Surface Type
    {{WINDOW_CONSTR}},         !- Construction Name
    {wall_name},             !- Building Surface Name
    ,                        !- Outside Boundary Condition Object
    0.5,                     !- View Factor to Ground
    ,                        !- Frame and Divider Name
    1,                       !- Multiplier
    4,                       !- Number of Vertices
    {win_br_x:.2f}, {win_br_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 1
    {win_br_x:.2f}, {win_br_y:.2f}, {z_top:.2f},  !- X,Y,Z ==> Vertex 2
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_top:.2f},  !- X,Y,Z ==> Vertex 3
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_bottom:.2f};  !- X,Y,Z ==> Vertex 4
"""

    def make_door(wall_name, v1, v4, wall_width, door_data):
        if not door_data: return ""
        
        if isinstance(door_data, dict):
            door_w = door_data.get("width", 1.0)
            door_h = door_data.get("height", 2.0)
            offset_x = door_data.get("offset_x", 0)
            ref_x = door_data.get("ref_x", "center")
            
            if ref_x == "left":
                w_off = wall_width - door_w - offset_x
            elif ref_x == "right":
                w_off = offset_x
            else:
                w_off = (wall_width - door_w) / 2.0
        else:
            # Fallback for old string format '1x2.5'
            if "x" not in str(door_data): return ""
            try:
                parts = str(door_data).lower().split("x")
                door_w = float(parts[0])
                door_h = float(parts[1])
            except:
                return "" # Invalid format
            w_off = (wall_width - door_w) / 2.0
        
        def interpolate(pA, pB, frac):
            return (pA[0] + (pB[0]-pA[0])*frac, pA[1] + (pB[1]-pA[1])*frac, pA[2] + (pB[2]-pA[2])*frac)
            
        win_br_x, win_br_y, win_br_z = interpolate(v1, v4, w_off / wall_width)
        win_bl_x, win_bl_y, win_bl_z = interpolate(v1, v4, (w_off + door_w) / wall_width)
        
        z_bottom = v1[2] # Floor level
        z_top = z_bottom + door_h
        
        return f"""
  FenestrationSurface:Detailed,
    {wall_name}_Door,      !- Name
    Door,                  !- Surface Type
    {{EXTERIOR_DOOR_CONSTR}},  !- Construction Name
    {wall_name},             !- Building Surface Name
    ,                        !- Outside Boundary Condition Object
    0.5,                     !- View Factor to Ground
    ,                        !- Frame and Divider Name
    1,                       !- Multiplier
    4,                       !- Number of Vertices
    {win_br_x:.2f}, {win_br_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 1
    {win_br_x:.2f}, {win_br_y:.2f}, {z_top:.2f},  !- X,Y,Z ==> Vertex 2
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_top:.2f},  !- X,Y,Z ==> Vertex 3
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_bottom:.2f};  !- X,Y,Z ==> Vertex 4
"""

    # Using placeholder text that our backend Assembler will string-replace later for roof and floor
    roof_constr = "{ROOF_CONSTR}"
    floor_constr = "{FLOOR_CONSTR}"
    
    # CCW Vertices viewed from OUTSIDE
    # Wall South (Facing -Y)
    v1, v2, v3, v4 = (L, 0, 0), (L, 0, H), (0, 0, H), (0, 0, 0)
    idf_str += make_surface("Wall_South", "Wall", wall_s, "Outdoors", "SunExposed", "WindExposed", v1, v2, v3, v4)
    idf_str += make_window("Wall_South", v1, v4, L, H, wwr_s, window_s)
    idf_str += make_door("Wall_South", v1, v4, L, door_s)
    
    # Wall East (Facing +X)
    v1, v2, v3, v4 = (L, W, 0), (L, W, H), (L, 0, H), (L, 0, 0)
    idf_str += make_surface("Wall_East", "Wall", wall_e, "Outdoors", "SunExposed", "WindExposed", v1, v2, v3, v4)
    idf_str += make_window("Wall_East", v1, v4, W, H, wwr_e, window_e)
    idf_str += make_door("Wall_East", v1, v4, W, door_e)
    
    # Wall North (Facing +Y)
    v1, v2, v3, v4 = (0, W, 0), (0, W, H), (L, W, H), (L, W, 0)
    idf_str += make_surface("Wall_North", "Wall", wall_n, "Outdoors", "SunExposed", "WindExposed", v1, v2, v3, v4)
    idf_str += make_window("Wall_North", v1, v4, L, H, wwr_n, window_n)
    idf_str += make_door("Wall_North", v1, v4, L, door_n)
    
    # Wall West (Facing -X)
    v1, v2, v3, v4 = (0, 0, 0), (0, 0, H), (0, W, H), (0, W, 0)
    idf_str += make_surface("Wall_West", "Wall", wall_w, "Outdoors", "SunExposed", "WindExposed", v1, v2, v3, v4)
    idf_str += make_window("Wall_West", v1, v4, W, H, wwr_w, window_w)
    idf_str += make_door("Wall_West", v1, v4, W, door_w)
    
    # Roof (Facing +Z)
    idf_str += make_surface("Roof", "Roof", roof_constr, "Outdoors", "SunExposed", "WindExposed", 
                       (0, W, H), (0, 0, H), (L, 0, H), (L, W, H))
                       
    # Floor (Facing -Z)
    idf_str += make_surface("Floor", "Floor", floor_constr, "Ground", "NoSun", "NoWind", 
                       (0, 0, 0), (L, 0, 0), (L, W, 0), (0, W, 0))
                       
    return idf_str

if __name__ == "__main__":
    # Test
    print("Testing Geometry generation for a 10m x 8m x 3m house.")
    geometry_idf = generate_zone_geometry(L=10, W=8, H=3, wwr_s=0.2, wwr_n=0.1)
    print(geometry_idf)
    print("Successfully Generated 6 BuildingSurfaces and 1 Zone object!")
