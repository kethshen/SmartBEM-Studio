import os

def generate_zone_geometry(
    L, W, H, 
    wwr_s=0.0, wwr_n=0.0, wwr_e=0.0, wwr_w=0.0, 
    wall_s="{EXTERIOR_WALL_CONSTR}", wall_n="{EXTERIOR_WALL_CONSTR}", 
    wall_e="{EXTERIOR_WALL_CONSTR}", wall_w="{EXTERIOR_WALL_CONSTR}",
    door_s=None, door_n=None, door_e=None, door_w=None,
    window_s=None, window_n=None, window_e=None, window_w=None,
    zone_name="ZONE ONE",
    roof_type="flat",
    roof_pitch_height=2.0,
    skylight_data=None):
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

    def make_triangle_surface(name, surf_type, constr, out_bound, sun, wind, v1, v2, v3):
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
    3,                       !- Number of Vertices
    {v1[0]:.2f}, {v1[1]:.2f}, {v1[2]:.2f},  !- X,Y,Z ==> Vertex 1
    {v2[0]:.2f}, {v2[1]:.2f}, {v2[2]:.2f},  !- X,Y,Z ==> Vertex 2
    {v3[0]:.2f}, {v3[1]:.2f}, {v3[2]:.2f};  !- X,Y,Z ==> Vertex 3
"""

    def make_skylight(roof_name, v1, v2, v3, v4, roof_width, roof_height_slant, skylight_data):
        if not skylight_data or not isinstance(skylight_data, dict):
            return ""
        sky_w = float(skylight_data.get("width", 1.0))
        sky_l = float(skylight_data.get("length", 1.0))
        
        w_off = (roof_width - sky_w) / 2.0
        h_off = (roof_height_slant - sky_l) / 2.0
        
        def interpolate_2d(p_bl, p_br, p_tl, frac_w, frac_h):
            x = p_bl[0] + (p_br[0]-p_bl[0])*frac_w + (p_tl[0]-p_bl[0])*frac_h
            y = p_bl[1] + (p_br[1]-p_bl[1])*frac_w + (p_tl[1]-p_bl[1])*frac_h
            z = p_bl[2] + (p_br[2]-p_bl[2])*frac_w + (p_tl[2]-p_bl[2])*frac_h
            return (x, y, z)
            
        win_v1 = interpolate_2d(v1, v2, v4, w_off/roof_width, h_off/roof_height_slant) # bottom-left
        win_v2 = interpolate_2d(v1, v2, v4, (w_off+sky_w)/roof_width, h_off/roof_height_slant) # bottom-right
        win_v3 = interpolate_2d(v1, v2, v4, (w_off+sky_w)/roof_width, (h_off+sky_l)/roof_height_slant) # top-right
        win_v4 = interpolate_2d(v1, v2, v4, w_off/roof_width, (h_off+sky_l)/roof_height_slant) # top-left
        
        return f"""
  FenestrationSurface:Detailed,
    {roof_name}_Skylight,  !- Name
    Window,                  !- Surface Type
    {{WINDOW_CONSTR}},         !- Construction Name
    {roof_name},             !- Building Surface Name
    ,                        !- Outside Boundary Condition Object
    0,                       !- View Factor to Ground
    ,                        !- Frame and Divider Name
    1,                       !- Multiplier
    4,                       !- Number of Vertices
    {win_v1[0]:.2f}, {win_v1[1]:.2f}, {win_v1[2]:.2f},  !- X,Y,Z ==> Vertex 1
    {win_v2[0]:.2f}, {win_v2[1]:.2f}, {win_v2[2]:.2f},  !- X,Y,Z ==> Vertex 2
    {win_v3[0]:.2f}, {win_v3[1]:.2f}, {win_v3[2]:.2f},  !- X,Y,Z ==> Vertex 3
    {win_v4[0]:.2f}, {win_v4[1]:.2f}, {win_v4[2]:.2f};  !- X,Y,Z ==> Vertex 4
"""

    def make_window(wall_name, v1, v2, wall_width, wall_height, wwr_val, window_data=None):
        if window_data and isinstance(window_data, dict):
            # Custom Window Placement
            win_w = float(window_data.get("width") if window_data.get("width") is not None else 1.0)
            win_h = float(window_data.get("height") if window_data.get("height") is not None else 1.0)
            offset_x = float(window_data.get("offset_x") if window_data.get("offset_x") is not None else 0.0)
            ref_x = window_data.get("ref_x") or "center"
            offset_z = float(window_data.get("offset_z") if window_data.get("offset_z") is not None else 0.0)
            ref_z = window_data.get("ref_z") or "center"
            
            if ref_x == "left":
                w_off = offset_x
            elif ref_x == "right":
                w_off = wall_width - win_w - offset_x
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
            
        win_bl_x, win_bl_y, win_bl_z = interpolate(v1, v2, w_off / wall_width)
        win_br_x, win_br_y, win_br_z = interpolate(v1, v2, (w_off + win_w) / wall_width)
        
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
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 1
    {win_br_x:.2f}, {win_br_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 2
    {win_br_x:.2f}, {win_br_y:.2f}, {z_top:.2f},  !- X,Y,Z ==> Vertex 3
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_top:.2f};  !- X,Y,Z ==> Vertex 4
"""

    def make_door(wall_name, v1, v2, wall_width, wall_height, door_data=None):
        if not door_data: return ""
        
        if isinstance(door_data, dict):
            door_w = float(door_data.get("width") if door_data.get("width") is not None else 1.0)
            door_h = float(door_data.get("height") if door_data.get("height") is not None else 2.0)
            offset_x = float(door_data.get("offset_x") if door_data.get("offset_x") is not None else 0.0)
            ref_x = door_data.get("ref_x") or "center"
            
            if ref_x == "left":
                w_off = offset_x
            elif ref_x == "right":
                w_off = wall_width - door_w - offset_x
            else:
                w_off = (wall_width - door_w) / 2.0
                
            # Force all doors to start at ground level
            h_off = 0.0
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
            h_off = 0
        
        def interpolate(pA, pB, frac):
            return (pA[0] + (pB[0]-pA[0])*frac, pA[1] + (pB[1]-pA[1])*frac, pA[2] + (pB[2]-pA[2])*frac)
            
        win_bl_x, win_bl_y, win_bl_z = interpolate(v1, v2, w_off / wall_width)
        win_br_x, win_br_y, win_br_z = interpolate(v1, v2, (w_off + door_w) / wall_width)
        
        z_bottom = v1[2] + h_off
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
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 1
    {win_br_x:.2f}, {win_br_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 2
    {win_br_x:.2f}, {win_br_y:.2f}, {z_top:.2f},  !- X,Y,Z ==> Vertex 3
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_top:.2f};  !- X,Y,Z ==> Vertex 4
"""

    # Using placeholder text that our backend Assembler will string-replace later for roof and floor
    roof_constr = "{ROOF_CONSTR}"
    floor_constr = "{FLOOR_CONSTR}"
    
    # CCW Vertices viewed from OUTSIDE
    # Wall South (Facing -Y)
    v1, v2, v3, v4 = (0, 0, 0), (L, 0, 0), (L, 0, H), (0, 0, H)
    idf_str += make_surface("Wall_South", "Wall", wall_s, "Outdoors", "SunExposed", "WindExposed", v1, v2, v3, v4)
    idf_str += make_window("Wall_South", v1, v2, L, H, wwr_s, window_s)
    idf_str += make_door("Wall_South", v1, v2, L, H, door_s)
    
    # Wall East (Facing +X)
    v1, v2, v3, v4 = (L, 0, 0), (L, W, 0), (L, W, H), (L, 0, H)
    idf_str += make_surface("Wall_East", "Wall", wall_e, "Outdoors", "SunExposed", "WindExposed", v1, v2, v3, v4)
    idf_str += make_window("Wall_East", v1, v2, W, H, wwr_e, window_e)
    idf_str += make_door("Wall_East", v1, v2, W, H, door_e)
    
    # Wall North (Facing +Y)
    v1, v2, v3, v4 = (L, W, 0), (0, W, 0), (0, W, H), (L, W, H)
    idf_str += make_surface("Wall_North", "Wall", wall_n, "Outdoors", "SunExposed", "WindExposed", v1, v2, v3, v4)
    idf_str += make_window("Wall_North", v1, v2, L, H, wwr_n, window_n)
    idf_str += make_door("Wall_North", v1, v2, L, H, door_n)
    
    # Wall West (Facing -X)
    v1, v2, v3, v4 = (0, W, 0), (0, 0, 0), (0, 0, H), (0, W, H)
    idf_str += make_surface("Wall_West", "Wall", wall_w, "Outdoors", "SunExposed", "WindExposed", v1, v2, v3, v4)
    idf_str += make_window("Wall_West", v1, v2, W, H, wwr_w, window_w)
    idf_str += make_door("Wall_West", v1, v2, W, H, door_w)
    
    # Roof & Gable
    if roof_type.lower() == "pitched":
        slant_w = L
        slant_h = math.sqrt((W/2)**2 + roof_pitch_height**2)
        
        # South Slope
        s_v1, s_v2, s_v3, s_v4 = (0, 0, H), (L, 0, H), (L, W/2, H+roof_pitch_height), (0, W/2, H+roof_pitch_height)
        idf_str += make_surface("Roof_South", "Roof", roof_constr, "Outdoors", "SunExposed", "WindExposed", s_v1, s_v2, s_v3, s_v4)
        
        # North Slope
        n_v1, n_v2, n_v3, n_v4 = (L, W, H), (0, W, H), (0, W/2, H+roof_pitch_height), (L, W/2, H+roof_pitch_height)
        idf_str += make_surface("Roof_North", "Roof", roof_constr, "Outdoors", "SunExposed", "WindExposed", n_v1, n_v2, n_v3, n_v4)
        
        # East Gable
        idf_str += make_triangle_surface("Gable_East", "Wall", wall_e, "Outdoors", "SunExposed", "WindExposed", (L, 0, H), (L, W, H), (L, W/2, H+roof_pitch_height))
        # West Gable
        idf_str += make_triangle_surface("Gable_West", "Wall", wall_w, "Outdoors", "SunExposed", "WindExposed", (0, W, H), (0, 0, H), (0, W/2, H+roof_pitch_height))
        
        if skylight_data:
            idf_str += make_skylight("Roof_South", s_v1, s_v2, s_v3, s_v4, slant_w, slant_h, skylight_data)
    else:
        # Flat Roof
        r_v1, r_v2, r_v3, r_v4 = (0, W, H), (0, 0, H), (L, 0, H), (L, W, H)
        idf_str += make_surface("Roof", "Roof", roof_constr, "Outdoors", "SunExposed", "WindExposed", r_v1, r_v2, r_v3, r_v4)
        if skylight_data:
            idf_str += make_skylight("Roof", r_v1, r_v2, r_v3, r_v4, L, W, skylight_data)
                       
    # Floor (Facing -Z)
    idf_str += make_surface("Floor", "Floor", floor_constr, "Ground", "NoSun", "NoWind", 
                       (0, W, 0), (L, W, 0), (L, 0, 0), (0, 0, 0))
                       
    return idf_str

if __name__ == "__main__":
    # Test
    print("Testing Geometry generation for a 10m x 8m x 3m house.")
    geometry_idf = generate_zone_geometry(L=10, W=8, H=3, wwr_s=0.2, wwr_n=0.1)
    print(geometry_idf)
    print("Successfully Generated 6 BuildingSurfaces and 1 Zone object!")


# ============================================================================
# MULTI-ZONE GEOMETRY FUNCTIONS
# ============================================================================

def resolve_zone_origins(zones):
    """
    Resolves absolute (X, Y, Z) origins for each zone based on relative layout.
    
    The first zone (anchor) is placed at (0, 0, 0).
    Subsequent zones are placed relative to their reference zone based on direction.
    
    Direction semantics (from the reference zone's perspective):
      - 'North': new zone is placed at ref_origin_y + ref_width  (along +Y)
      - 'South': new zone is placed at ref_origin_y - new_width  (along -Y)
      - 'East':  new zone is placed at ref_origin_x + ref_length (along +X)
      - 'West':  new zone is placed at ref_origin_x - new_length (along -X)
    
    Returns: dict mapping zone_name -> (origin_x, origin_y, origin_z)
    """
    origins = {}
    zone_dims = {}  # name -> (L, W, H)
    
    for z in zones:
        name = z["name"]
        L = z.get("length", 10.0)
        W = z.get("width", 10.0)
        H = z.get("height", 3.0)
        zone_dims[name] = (L, W, H)
        
        ref = z.get("relative_to", None)
        direction = z.get("direction", None)
        
        if ref in [None, "null", "Null", "NULL", "none", "None", ""]:
            ref = None
        else:
            ref = str(ref).strip()
            
        if direction in [None, "null", "Null", "NULL", "none", "None", ""]:
            direction = None
        else:
            direction = str(direction).strip()
            
        print(f"[AI Assembler MZ] Resolving origin for '{name}'. ref='{ref}', direction='{direction}'")
        
        if ref is None or direction is None:
            # Anchor zone
            print(f"[AI Assembler MZ] -> '{name}' is treated as an ANCHOR zone at (0,0,0)")
            origins[name] = (0.0, 0.0, 0.0)
        else:
            actual_ref = None
            # Aggressive matching: strip, lower, and check substrings just in case AI adds prefixes like 'The '
            for o_name in origins:
                norm_o = o_name.strip().lower()
                norm_r = ref.strip().lower()
                if norm_o == norm_r or norm_o in norm_r or norm_r in norm_o:
                    actual_ref = o_name
                    break
                    
            if actual_ref is None:
                print(f"[WARNING] Zone '{name}' references '{ref}' which has not been defined yet! Falling back to Anchor (0,0,0)")
                origins[name] = (0.0, 0.0, 0.0)
                continue
                
            ref_origin = origins[actual_ref]
            ref_L, ref_W, ref_H = zone_dims[actual_ref]
            
            direction_upper = direction.strip().capitalize()
            
            if direction_upper == "North":
                # New zone placed along +Y from the reference zone's north wall
                ox = ref_origin[0]
                oy = ref_origin[1] + ref_W
                oz = ref_origin[2]
            elif direction_upper == "South":
                # New zone placed along -Y from the reference zone's south wall
                ox = ref_origin[0]
                oy = ref_origin[1] - W
                oz = ref_origin[2]
            elif direction_upper == "East":
                # New zone placed along +X from the reference zone's east wall
                ox = ref_origin[0] + ref_L
                oy = ref_origin[1]
                oz = ref_origin[2]
            elif direction_upper == "West":
                # New zone placed along -X from the reference zone's west wall
                ox = ref_origin[0] - L
                oy = ref_origin[1]
                oz = ref_origin[2]
            else:
                raise ValueError(f"Unknown direction '{direction}' for zone '{name}'")
            
            origins[name] = (ox, oy, oz)
    
    return origins


def generate_multizone_geometry(zones, zone_origins):
    """
    Generates EnergyPlus geometry IDF text for multiple zones with automatic 
    adjacency detection.
    
    For each zone, generates 6 surfaces (4 walls + roof + floor).
    Detects shared walls between adjacent zones and configures:
      - Outside Boundary Condition = Surface
      - Outside Boundary Condition Object = adjacent wall name
      - Reversed vertex winding for the second surface
    
    Returns: (idf_string, adjacency_info_list)
    """
    import math
    
    idf_str = ""
    adjacency_info = []
    
    # Pre-compute all zone bounding boxes for adjacency detection
    zone_boxes = {}
    for z in zones:
        name = z["name"]
        L = z.get("length", 10.0)
        W = z.get("width", 10.0)
        H = z.get("height", 3.0)
        ox, oy, oz = zone_origins[name]
        zone_boxes[name] = {
            "L": L, "W": W, "H": H,
            "ox": ox, "oy": oy, "oz": oz,
            "x_min": ox, "x_max": ox + L,
            "y_min": oy, "y_max": oy + W,
            "z_min": oz, "z_max": oz + H
        }
    
    # Build adjacency map: for each zone's wall, check if another zone shares that face
    # A wall is shared if two zones have a coincident face segment
    adjacency_map = {}  # (zone_name, wall_dir) -> adjacent_zone_name
    
    zone_names = [z["name"] for z in zones]
    for i, name_a in enumerate(zone_names):
        box_a = zone_boxes[name_a]
        for j, name_b in enumerate(zone_names):
            if i >= j:
                continue
            box_b = zone_boxes[name_b]
            
            # Check if A's North wall == B's South wall (same Y coordinate, overlapping X range)
            if (abs(box_a["y_max"] - box_b["y_min"]) < 0.001 and
                box_a["x_min"] < box_b["x_max"] - 0.001 and
                box_a["x_max"] > box_b["x_min"] + 0.001):
                adjacency_map[(name_a, "North")] = name_b
                adjacency_map[(name_b, "South")] = name_a
                adjacency_info.append(f"{name_a}_North <-> {name_b}_South")
            
            # Check if A's South wall == B's North wall
            if (abs(box_a["y_min"] - box_b["y_max"]) < 0.001 and
                box_a["x_min"] < box_b["x_max"] - 0.001 and
                box_a["x_max"] > box_b["x_min"] + 0.001):
                adjacency_map[(name_a, "South")] = name_b
                adjacency_map[(name_b, "North")] = name_a
                adjacency_info.append(f"{name_a}_South <-> {name_b}_North")
            
            # Check if A's East wall == B's West wall (same X coordinate, overlapping Y range)
            if (abs(box_a["x_max"] - box_b["x_min"]) < 0.001 and
                box_a["y_min"] < box_b["y_max"] - 0.001 and
                box_a["y_max"] > box_b["y_min"] + 0.001):
                adjacency_map[(name_a, "East")] = name_b
                adjacency_map[(name_b, "West")] = name_a
                adjacency_info.append(f"{name_a}_East <-> {name_b}_West")
            
            # Check if A's West wall == B's East wall
            if (abs(box_a["x_min"] - box_b["x_max"]) < 0.001 and
                box_a["y_min"] < box_b["y_max"] - 0.001 and
                box_a["y_max"] > box_b["y_min"] + 0.001):
                adjacency_map[(name_a, "West")] = name_b
                adjacency_map[(name_b, "East")] = name_a
                adjacency_info.append(f"{name_a}_West <-> {name_b}_East")
    print(f"[Geometry MZ] Detected {len(adjacency_info)} adjacencies: {adjacency_info}")
    
    # Sync subsurfaces (doors/windows) across adjacent walls
    for z in zones:
        name_a = z["name"]
        for wdir, opp_dir in [("North", "South"), ("South", "North"), ("East", "West"), ("West", "East")]:
            adj_key = (name_a, wdir)
            if adj_key in adjacency_map:
                name_b = adjacency_map[adj_key]
                zone_b = next((x for x in zones if x["name"] == name_b), None)
                if not zone_b: continue
                
                door_key_a = f"door_{wdir.lower()}"
                door_key_b = f"door_{opp_dir.lower()}"
                if z.get(door_key_a) and not zone_b.get(door_key_b):
                    d_data = z[door_key_a].copy()
                    rx = d_data.get("ref_x", "center")
                    if rx == "left": d_data["ref_x"] = "right"
                    elif rx == "right": d_data["ref_x"] = "left"
                    zone_b[door_key_b] = d_data
                    
                win_key_a = f"window_{wdir.lower()}"
                win_key_b = f"window_{opp_dir.lower()}"
                if z.get(win_key_a) and not zone_b.get(win_key_b):
                    w_data = z[win_key_a].copy()
                    rx = w_data.get("ref_x", "center")
                    if rx == "left": w_data["ref_x"] = "right"
                    elif rx == "right": w_data["ref_x"] = "left"
                    zone_b[win_key_b] = w_data
                    
                wwr_key_a = f"wwr_{wdir.lower()}"
                wwr_key_b = f"wwr_{opp_dir.lower()}"
                if z.get(wwr_key_a, 0) > 0 and zone_b.get(wwr_key_b, 0) == 0:
                    zone_b[wwr_key_b] = z[wwr_key_a]
    
    # Interior partition construction placeholder
    partition_constr = "{INTERIOR_PARTITION_CONSTR}"
    
    # Helper to make a surface
    def make_surface(name, surf_type, constr, zone_name, out_bound, bound_obj, sun, wind, v1, v2, v3, v4):
        vf = "0.50" if surf_type == "Wall" else "0"
        bound_obj_str = bound_obj if bound_obj else ""
        return f"""
  BuildingSurface:Detailed,
    {name},                  !- Name
    {surf_type},             !- Surface Type
    {constr},                !- Construction Name
    {zone_name},             !- Zone Name
    ,                        !- Space Name
    {out_bound},             !- Outside Boundary Condition
    {bound_obj_str},         !- Outside Boundary Condition Object
    {sun},                   !- Sun Exposure
    {wind},                  !- Wind Exposure
    {vf},                    !- View Factor to Ground
    4,                       !- Number of Vertices
    {v1[0]:.2f}, {v1[1]:.2f}, {v1[2]:.2f},  !- X,Y,Z ==> Vertex 1
    {v2[0]:.2f}, {v2[1]:.2f}, {v2[2]:.2f},  !- X,Y,Z ==> Vertex 2
    {v3[0]:.2f}, {v3[1]:.2f}, {v3[2]:.2f},  !- X,Y,Z ==> Vertex 3
    {v4[0]:.2f}, {v4[1]:.2f}, {v4[2]:.2f};  !- X,Y,Z ==> Vertex 4
"""
    def make_triangle_surface(name, surf_type, constr, zone_name, out_bound, bound_obj, sun, wind, v1, v2, v3):
        vf = "0.50" if surf_type == "Wall" else "0"
        bound_obj_str = bound_obj if bound_obj else ""
        return f"""
  BuildingSurface:Detailed,
    {name},                  !- Name
    {surf_type},             !- Surface Type
    {constr},                !- Construction Name
    {zone_name},             !- Zone Name
    ,                        !- Space Name
    {out_bound},             !- Outside Boundary Condition
    {bound_obj_str},         !- Outside Boundary Condition Object
    {sun},                   !- Sun Exposure
    {wind},                  !- Wind Exposure
    {vf},                    !- View Factor to Ground
    3,                       !- Number of Vertices
    {v1[0]:.2f}, {v1[1]:.2f}, {v1[2]:.2f},  !- X,Y,Z ==> Vertex 1
    {v2[0]:.2f}, {v2[1]:.2f}, {v2[2]:.2f},  !- X,Y,Z ==> Vertex 2
    {v3[0]:.2f}, {v3[1]:.2f}, {v3[2]:.2f};  !- X,Y,Z ==> Vertex 3
"""

    def make_skylight_mz(roof_name, v1, v2, v3, v4, roof_width, roof_height_slant, skylight_data):
        if not skylight_data or not isinstance(skylight_data, dict):
            return ""
        sky_w = float(skylight_data.get("width", 1.0))
        sky_l = float(skylight_data.get("length", 1.0))
        
        w_off = (roof_width - sky_w) / 2.0
        h_off = (roof_height_slant - sky_l) / 2.0
        
        def interpolate_2d(p_bl, p_br, p_tl, frac_w, frac_h):
            x = p_bl[0] + (p_br[0]-p_bl[0])*frac_w + (p_tl[0]-p_bl[0])*frac_h
            y = p_bl[1] + (p_br[1]-p_bl[1])*frac_w + (p_tl[1]-p_bl[1])*frac_h
            z = p_bl[2] + (p_br[2]-p_bl[2])*frac_w + (p_tl[2]-p_bl[2])*frac_h
            return (x, y, z)
            
        win_v1 = interpolate_2d(v1, v2, v4, w_off/roof_width, h_off/roof_height_slant) # bottom-left
        win_v2 = interpolate_2d(v1, v2, v4, (w_off+sky_w)/roof_width, h_off/roof_height_slant) # bottom-right
        win_v3 = interpolate_2d(v1, v2, v4, (w_off+sky_w)/roof_width, (h_off+sky_l)/roof_height_slant) # top-right
        win_v4 = interpolate_2d(v1, v2, v4, w_off/roof_width, (h_off+sky_l)/roof_height_slant) # top-left
        
        return f"""
  FenestrationSurface:Detailed,
    {roof_name}_Skylight,  !- Name
    Window,                  !- Surface Type
    {{WINDOW_CONSTR}},         !- Construction Name
    {roof_name},             !- Building Surface Name
    ,                        !- Outside Boundary Condition Object
    0,                       !- View Factor to Ground
    ,                        !- Frame and Divider Name
    1,                       !- Multiplier
    4,                       !- Number of Vertices
    {win_v1[0]:.2f}, {win_v1[1]:.2f}, {win_v1[2]:.2f},  !- X,Y,Z ==> Vertex 1
    {win_v2[0]:.2f}, {win_v2[1]:.2f}, {win_v2[2]:.2f},  !- X,Y,Z ==> Vertex 2
    {win_v3[0]:.2f}, {win_v3[1]:.2f}, {win_v3[2]:.2f},  !- X,Y,Z ==> Vertex 3
    {win_v4[0]:.2f}, {win_v4[1]:.2f}, {win_v4[2]:.2f};  !- X,Y,Z ==> Vertex 4
"""

    def make_window_mz(wall_name, v1, v2, wall_width, wall_height, wwr_val, window_data=None):
        """Generate window for multi-zone (same logic as single-zone make_window)."""
        if window_data and isinstance(window_data, dict):
            win_w = float(window_data.get("width") if window_data.get("width") is not None else 1.0)
            win_h = float(window_data.get("height") if window_data.get("height") is not None else 1.0)
            offset_x = float(window_data.get("offset_x") if window_data.get("offset_x") is not None else 0.0)
            ref_x = window_data.get("ref_x") or "center"
            offset_z = float(window_data.get("offset_z") if window_data.get("offset_z") is not None else 0.0)
            ref_z = window_data.get("ref_z") or "center"
            
            if ref_x == "left":
                w_off = offset_x
            elif ref_x == "right":
                w_off = wall_width - win_w - offset_x
            else:
                w_off = (wall_width - win_w) / 2.0
                
            if ref_z == "bottom":
                h_off = offset_z
            elif ref_z == "top":
                h_off = wall_height - win_h - offset_z
            else:
                h_off = (wall_height - win_h) / 2.0
        else:
            if not wwr_val or wwr_val <= 0 or wwr_val >= 1:
                return ""
            win_w = wall_width * math.sqrt(wwr_val)
            win_h = wall_height * math.sqrt(wwr_val)
            w_off = (wall_width - win_w) / 2.0
            h_off = (wall_height - win_h) / 2.0
        
        def interpolate(pA, pB, frac):
            return (pA[0] + (pB[0]-pA[0])*frac, pA[1] + (pB[1]-pA[1])*frac, pA[2] + (pB[2]-pA[2])*frac)
            
        win_bl_x, win_bl_y, win_bl_z = interpolate(v1, v2, w_off / wall_width)
        win_br_x, win_br_y, win_br_z = interpolate(v1, v2, (w_off + win_w) / wall_width)
        
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
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 1
    {win_br_x:.2f}, {win_br_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 2
    {win_br_x:.2f}, {win_br_y:.2f}, {z_top:.2f},  !- X,Y,Z ==> Vertex 3
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_top:.2f};  !- X,Y,Z ==> Vertex 4
"""

    def make_door_mz(wall_name, v1, v2, wall_width, wall_height, door_data, constr="{EXTERIOR_DOOR_CONSTR}"):
        """Generate door for multi-zone. constr allows specifying interior vs exterior door construction."""
        if not door_data:
            return ""
        
        if isinstance(door_data, dict):
            door_w = float(door_data.get("width") if door_data.get("width") is not None else 1.0)
            door_h = float(door_data.get("height") if door_data.get("height") is not None else 2.0)
            offset_x = float(door_data.get("offset_x") if door_data.get("offset_x") is not None else 0.0)
            ref_x = door_data.get("ref_x") or "center"
            
            if ref_x == "left":
                w_off = offset_x
            elif ref_x == "right":
                w_off = wall_width - door_w - offset_x
            else:
                w_off = (wall_width - door_w) / 2.0
                
            # Force all doors to start at ground level
            h_off = 0.0
        else:
            if "x" not in str(door_data):
                return ""
            try:
                parts = str(door_data).lower().split("x")
                door_w = float(parts[0])
                door_h = float(parts[1])
            except:
                return ""
            w_off = (wall_width - door_w) / 2.0
            h_off = 0
        
        def interpolate(pA, pB, frac):
            return (pA[0] + (pB[0]-pA[0])*frac, pA[1] + (pB[1]-pA[1])*frac, pA[2] + (pB[2]-pA[2])*frac)
            
        win_bl_x, win_bl_y, win_bl_z = interpolate(v1, v2, w_off / wall_width)
        win_br_x, win_br_y, win_br_z = interpolate(v1, v2, (w_off + door_w) / wall_width)
        
        z_bottom = v1[2] + h_off
        z_top = z_bottom + door_h
        
        return f"""
  FenestrationSurface:Detailed,
    {wall_name}_Door,      !- Name
    Door,                  !- Surface Type
    {constr},  !- Construction Name
    {wall_name},             !- Building Surface Name
    ,                        !- Outside Boundary Condition Object
    0.5,                     !- View Factor to Ground
    ,                        !- Frame and Divider Name
    1,                       !- Multiplier
    4,                       !- Number of Vertices
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 1
    {win_br_x:.2f}, {win_br_y:.2f}, {z_bottom:.2f},  !- X,Y,Z ==> Vertex 2
    {win_br_x:.2f}, {win_br_y:.2f}, {z_top:.2f},  !- X,Y,Z ==> Vertex 3
    {win_bl_x:.2f}, {win_bl_y:.2f}, {z_top:.2f};  !- X,Y,Z ==> Vertex 4
"""

    # Generate geometry for each zone
    for z in zones:
        name = z["name"]
        L = z.get("length", 10.0)
        W = z.get("width", 10.0)
        H = z.get("height", 3.0)
        ox, oy, oz = zone_origins[name]
        
        wall_constr = z.get("wall_construction", "{EXTERIOR_WALL_CONSTR}")
        roof_constr = "{ROOF_CONSTR}"
        floor_constr = "{FLOOR_CONSTR}"
        
        wwr_s = z.get("wwr_south", 0.0)
        wwr_n = z.get("wwr_north", 0.0)
        wwr_e = z.get("wwr_east", 0.0)
        wwr_w = z.get("wwr_west", 0.0)
        
        window_s = z.get("window_south", None)
        window_n = z.get("window_north", None)
        window_e = z.get("window_east", None)
        window_w = z.get("window_west", None)
        
        door_s = z.get("door_south", None)
        door_n = z.get("door_north", None)
        door_e = z.get("door_east", None)
        door_w = z.get("door_west", None)
        
        # Zone Object
        idf_str += f"""
  Zone,
    {name},                  !- Name
    0,                       !- Direction of Relative North {{deg}}
    {ox:.2f},                !- X Origin {{m}}
    {oy:.2f},                !- Y Origin {{m}}
    {oz:.2f},                !- Z Origin {{m}}
    1,                       !- Type
    1,                       !- Multiplier
    autocalculate,           !- Ceiling Height {{m}}
    autocalculate;           !- Volume {{m3}}
"""
        
        # --- Generate 4 walls ---
        # Use LOCAL coordinates (relative to zone origin) since we set Zone X/Y/Z Origin
        
        # Wall definitions: (wall_dir, surf_name, v1, v2, v3, v4, wall_dim_for_windows, wall_h_dim, wwr, window_data, door_data)
        walls = [
            ("South", f"{name}_Wall_South",
             (0, 0, 0), (L, 0, 0), (L, 0, H), (0, 0, H),
             L, H, wwr_s, window_s, door_s),
            ("East", f"{name}_Wall_East",
             (L, 0, 0), (L, W, 0), (L, W, H), (L, 0, H),
             W, H, wwr_e, window_e, door_e),
            ("North", f"{name}_Wall_North",
             (L, W, 0), (0, W, 0), (0, W, H), (L, W, H),
             L, H, wwr_n, window_n, door_n),
            ("West", f"{name}_Wall_West",
             (0, W, 0), (0, 0, 0), (0, 0, H), (0, W, H),
             W, H, wwr_w, window_w, door_w),
        ]
        
        for wall_dir, surf_name, v1, v2, v3, v4, wall_w_dim, wall_h_dim, wwr, win_data, dr_data in walls:
            adj_key = (name, wall_dir)
            
            if adj_key in adjacency_map:
                # This wall is shared with another zone — make it an interior partition
                adj_zone = adjacency_map[adj_key]
                # Determine the opposite wall name
                opposite_dirs = {"North": "South", "South": "North", "East": "West", "West": "East"}
                adj_wall_name = f"{adj_zone}_Wall_{opposite_dirs[wall_dir]}"
                
                idf_str += make_surface(
                    surf_name, "Wall", partition_constr, name,
                    "Surface", adj_wall_name, "NoSun", "NoWind",
                    v1, v2, v3, v4
                )
                # Allow doors on interior partition walls (between zones), but not windows.
                # Interior doors use a special opaque construction.
                if dr_data:
                    idf_str += make_door_mz(surf_name, v1, v2, wall_w_dim, wall_h_dim, dr_data,
                                            constr="Interior_Door_Constr")
            else:
                # Exterior wall
                idf_str += make_surface(
                    surf_name, "Wall", wall_constr, name,
                    "Outdoors", None, "SunExposed", "WindExposed",
                    v1, v2, v3, v4
                )
                # Add windows and doors only on exterior walls
                idf_str += make_window_mz(surf_name, v1, v2, wall_w_dim, wall_h_dim, wwr, win_data)
                idf_str += make_door_mz(surf_name, v1, v2, wall_w_dim, wall_h_dim, dr_data)
        
        # Roof & Gable
        roof_type = z.get("roof_type", "flat").lower()
        roof_pitch_height = float(z.get("roof_pitch_height", 2.0))
        skylight_data = z.get("skylight", None)
        
        if roof_type == "pitched":
            # Ridge is at Y = W/2, parallel to X-axis
            import math
            slant_w = L
            slant_h = math.sqrt((W/2)**2 + roof_pitch_height**2)
            
            # South Slope: From South Wall (Y=0) up to Ridge (Y=W/2)
            s_v1, s_v2, s_v3, s_v4 = (0, 0, H), (L, 0, H), (L, W/2, H+roof_pitch_height), (0, W/2, H+roof_pitch_height)
            idf_str += make_surface(
                f"{name}_Roof_South", "Roof", roof_constr, name,
                "Outdoors", None, "SunExposed", "WindExposed",
                s_v1, s_v2, s_v3, s_v4
            )
            # North Slope: From North Wall (Y=W) up to Ridge (Y=W/2)
            n_v1, n_v2, n_v3, n_v4 = (L, W, H), (0, W, H), (0, W/2, H+roof_pitch_height), (L, W/2, H+roof_pitch_height)
            idf_str += make_surface(
                f"{name}_Roof_North", "Roof", roof_constr, name,
                "Outdoors", None, "SunExposed", "WindExposed",
                n_v1, n_v2, n_v3, n_v4
            )
            
            # East Gable Triangle
            idf_str += make_triangle_surface(
                f"{name}_Gable_East", "Wall", wall_constr, name,
                "Outdoors", None, "SunExposed", "WindExposed",
                (L, 0, H), (L, W, H), (L, W/2, H+roof_pitch_height)
            )
            # West Gable Triangle
            idf_str += make_triangle_surface(
                f"{name}_Gable_West", "Wall", wall_constr, name,
                "Outdoors", None, "SunExposed", "WindExposed",
                (0, W, H), (0, 0, H), (0, W/2, H+roof_pitch_height)
            )
            
            # Add skylight on the South Slope if specified
            if skylight_data:
                idf_str += make_skylight_mz(f"{name}_Roof_South", s_v1, s_v2, s_v3, s_v4, slant_w, slant_h, skylight_data)
                
        else:
            # Flat Roof
            r_v1, r_v2, r_v3, r_v4 = (0, W, H), (0, 0, H), (L, 0, H), (L, W, H)
            idf_str += make_surface(
                f"{name}_Roof", "Roof", roof_constr, name,
                "Outdoors", None, "SunExposed", "WindExposed",
                r_v1, r_v2, r_v3, r_v4
            )
            if skylight_data:
                idf_str += make_skylight_mz(f"{name}_Roof", r_v1, r_v2, r_v3, r_v4, L, W, skylight_data)
        
        # Floor
        idf_str += make_surface(
            f"{name}_Floor", "Floor", floor_constr, name,
            "Ground", None, "NoSun", "NoWind",
            (0, W, 0), (L, W, 0), (L, 0, 0), (0, 0, 0)
        )
    
    # Add interior partition construction material
    idf_str += """
  Material,
    Interior_Partition_Material, !- Name
    MediumSmooth,            !- Roughness
    0.1,                     !- Thickness {m}
    0.5,                     !- Conductivity {W/m-K}
    1000.0,                  !- Density {kg/m3}
    1000.0,                  !- Specific Heat {J/kg-K}
    0.9,                     !- Thermal Absorptance
    0.7,                     !- Solar Absorptance
    0.7;                     !- Visible Absorptance

  Construction,
    Interior_Partition,      !- Name
    Interior_Partition_Material; !- Outside Layer

  Material,
    Interior_Door_Material,  !- Name
    MediumSmooth,            !- Roughness
    0.045,                   !- Thickness {m}
    0.15,                    !- Conductivity {W/m-K}
    600.0,                   !- Density {kg/m3}
    1000.0,                  !- Specific Heat {J/kg-K}
    0.9,                     !- Thermal Absorptance
    0.6,                     !- Solar Absorptance
    0.6;                     !- Visible Absorptance

  Construction,
    Interior_Door_Constr,    !- Name
    Interior_Door_Material;  !- Outside Layer
"""
    
    # Replace the placeholder
    idf_str = idf_str.replace("{INTERIOR_PARTITION_CONSTR}", "Interior_Partition")
    
    return idf_str, adjacency_info
