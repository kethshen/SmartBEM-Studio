import re

with open("backend/geometry_util.py", "r") as f:
    content = f.read()

# Replace make_window
window_repl = """    def make_window(wall_name, v1, v2, wall_width, wall_height, wwr_val, window_data=None):
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
        
        return f\"\"\"
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
\"\"\""""

content = re.sub(r'    def make_window\(.*?\n(?:        .*?\n)*?\"\"\"', window_repl, content, flags=re.MULTILINE, count=1)


door_repl = """    def make_door(wall_name, v1, v2, wall_width, wall_height, door_data):
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
            h_off = 0.0
        else:
            if "x" not in str(door_data): return ""
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
        
        return f\"\"\"
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
\"\"\""""

content = re.sub(r'    def make_door\(.*?\n(?:        .*?\n)*?\"\"\"', door_repl, content, flags=re.MULTILINE, count=1)


walls_repl = """    # CCW Vertices viewed from OUTSIDE
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
    idf_str += make_door("Wall_West", v1, v2, W, H, door_w)"""

content = re.sub(r'    # CCW Vertices viewed from OUTSIDE\n(?:    .*?\n){19}', walls_repl + '\n', content, count=1)


window_mz_repl = window_repl.replace("make_window(", "make_window_mz(")
door_mz_repl = door_repl.replace("make_door(", "make_door_mz(")

content = re.sub(r'    def make_window_mz\(.*?\n(?:        .*?\n)*?\"\"\"', window_mz_repl, content, flags=re.MULTILINE, count=1)
content = re.sub(r'    def make_door_mz\(.*?\n(?:        .*?\n)*?\"\"\"', door_mz_repl, content, flags=re.MULTILINE, count=1)

mz_walls_repl = """        walls = [
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
        
        for wall_dir, surf_name, v1, v2, v3, v4, wall_w_dim, wall_h_dim, wwr, win_data, dr_data in walls:"""

content = re.sub(r'        walls = \[\n(?:            .*?\n)*?        \]\n        \n        for wall_dir, surf_name, v1, v2, v3, v4, wall_w_dim, wall_h_dim, wwr, win_data, dr_data in walls:', mz_walls_repl, content, count=1)


content = content.replace("make_window_mz(surf_name, v1, v4", "make_window_mz(surf_name, v1, v2")
content = content.replace("make_door_mz(surf_name, v1, v4", "make_door_mz(surf_name, v1, v2")


with open("backend/geometry_util.py", "w") as f:
    f.write(content)

print("done")
