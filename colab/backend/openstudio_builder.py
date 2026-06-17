import os
import sys
import math
import re
import openstudio

# Ensure we can import from the backend directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.geometry_util import resolve_zone_origins
from backend import idf_extractor

def build_openstudio_model(params: dict) -> openstudio.model.Model:
    """
    Translates JSON building parameters into an OpenStudio Model,
    resolving layout geometry, materials, internal loads, schedules,
    and HVAC systems programmatically.
    """
    print("[OpenStudio Builder] Starting model generation...")

    # 1. Uniformly format Single-Zone and Multi-Zone structures
    is_multizone = params.get("is_multizone", False)
    if not is_multizone:
        zone_obj = {
            "name": "ZONE ONE",
            "length": params.get("length", 10.0),
            "width": params.get("width", 10.0),
            "height": params.get("height", 3.0),
            "relative_to": None,
            "direction": None,
            "wall_layers": params.get("wall_layers"),
            "wall_layers_south": params.get("wall_layers_south"),
            "wall_layers_north": params.get("wall_layers_north"),
            "wall_layers_east": params.get("wall_layers_east"),
            "wall_layers_west": params.get("wall_layers_west"),
            "roof_layers": params.get("roof_layers"),
            "window_layers": params.get("window_layers"),
            "roof_type": params.get("roof_type", "flat"),
            "roof_pitch_height": params.get("roof_pitch_height", 2.0),
            "skylight": params.get("skylight"),
            "wwr_south": params.get("wwr_south", 0.0),
            "wwr_north": params.get("wwr_north", 0.0),
            "wwr_east": params.get("wwr_east", 0.0),
            "wwr_west": params.get("wwr_west", 0.0),
            "window_south": params.get("window_south"),
            "window_north": params.get("window_north"),
            "window_east": params.get("window_east"),
            "window_west": params.get("window_west"),
            "door_south": params.get("door_south"),
            "door_north": params.get("door_north"),
            "door_east": params.get("door_east"),
            "door_west": params.get("door_west"),
            "people_density": params.get("people_density", 10.0),
            "light_density": params.get("light_density", 10.0),
            "equipment_density": params.get("equipment_density", 10.0),
            "ventilation_ach": params.get("ventilation_ach", 0.5),
            "infiltration_ach": params.get("infiltration_ach", 0.5),
            "hvac_type": params.get("hvac_type", "ideal_loads"),
        }
        zones = [zone_obj]
    else:
        zones = params.get("zones", [])
        # Apply global fallback values for multi-zone rooms
        for z in zones:
            z["people_density"] = z.get("people_density") if z.get("people_density") is not None else params.get("people_density", 10.0)
            z["light_density"] = z.get("light_density") if z.get("light_density") is not None else params.get("light_density", 10.0)
            z["equipment_density"] = z.get("equipment_density") if z.get("equipment_density") is not None else params.get("equipment_density", 10.0)
            z["ventilation_ach"] = z.get("ventilation_ach") if z.get("ventilation_ach") is not None else params.get("ventilation_ach", 0.5)
            z["infiltration_ach"] = z.get("infiltration_ach") if z.get("infiltration_ach") is not None else params.get("infiltration_ach", 0.5)
            z["hvac_type"] = z.get("hvac_type") or params.get("hvac_type") or "ideal_loads"

    # 2. Extract and resolve all required constructions & materials
    names_to_resolve = set(["Composite 2x4 Wood Stud R11", "Dbl Clr 3mm/13mm Air"])
    for z in zones:
        for key in ["wall_layers", "wall_layers_south", "wall_layers_north", "wall_layers_east", "wall_layers_west", "roof_layers", "window_layers"]:
            val = z.get(key)
            if val:
                if isinstance(val, str):
                    if val == "Theoretical Glass [167]":
                        val = "Dbl Clr 3mm/13mm Air"
                    names_to_resolve.add(val)
                elif isinstance(val, list):
                    for item in val:
                        if item == "Theoretical Glass [167]":
                            item = "Dbl Clr 3mm/13mm Air"
                        names_to_resolve.add(item)

    extracted_blocks = {}
    for name in names_to_resolve:
        idf_extractor.resolve_dependencies("Construction", name, extracted_blocks)

    # Compile blocks to an IDF string and reverse-translate into OpenStudio Model
    idf_string = ""
    for block in extracted_blocks.values():
        idf_string += block + "\n\n"

    print(f"[OpenStudio Builder] Loading {len(extracted_blocks)} materials/constructions from IDF datasets...")
    
    # Use a temporary file to load the Workspace safely and cross-platform
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".idf", mode="w", delete=False, encoding="utf-8") as temp_file:
        temp_file.write(idf_string)
        temp_path = temp_file.name

    try:
        opt_idf = openstudio.IdfFile.load(openstudio.path(temp_path))
        if not opt_idf.is_initialized():
            raise Exception("Failed to parse the materials/constructions IDF syntax.")
        workspace = openstudio.Workspace(opt_idf.get())
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass

    rt = openstudio.energyplus.ReverseTranslator()
    model = rt.translateWorkspace(workspace)

    # 3. Setup Default Construction Set
    def get_or_create_construction(layers_input, fallback_name=None):
        if not layers_input:
            if fallback_name:
                return get_or_create_construction(fallback_name)
            return None

        # Standardise single string to a list of layers
        if isinstance(layers_input, str):
            layers_input = [layers_input]

        if not isinstance(layers_input, list):
            return None

        # Flatten any nested constructions into materials
        flat_layers = []
        for layer in layers_input:
            if not isinstance(layer, str):
                continue
            c_layers = idf_extractor.get_construction_layers(layer)
            if c_layers:
                flat_layers.extend(c_layers)
            else:
                flat_layers.append(layer)

        # Map "Theoretical Glass [167]" to "Dbl Clr 3mm/13mm Air"
        mapped_layers = []
        for l in flat_layers:
            if l == "Theoretical Glass [167]":
                mapped_layers.append("Dbl Clr 3mm/13mm Air")
            else:
                mapped_layers.append(l)
        flat_layers = mapped_layers

        if not flat_layers:
            if fallback_name:
                return get_or_create_construction(fallback_name)
            return None

        # If it's a single layer and matches an existing Construction name in the model, return it
        if len(flat_layers) == 1:
            constr_opt = model.getConstructionByName(flat_layers[0])
            if constr_opt.is_initialized():
                return constr_opt.get()

        # Build unique name for custom construction based on layers
        sanitized_layers = [re.sub(r'[^a-zA-Z0-9]', '_', l) for l in flat_layers]
        custom_name = "Const_" + "_".join(sanitized_layers)

        existing_opt = model.getConstructionByName(custom_name)
        if existing_opt.is_initialized():
            return existing_opt.get()

        # Collect material objects from model
        materials = []
        for layer in flat_layers:
            mat_opt = model.getMaterialByName(layer)
            if mat_opt.is_initialized():
                materials.append(mat_opt.get())
            else:
                print(f"Warning: Material '{layer}' not found in OpenStudio model.")

        if not materials:
            if fallback_name:
                return get_or_create_construction(fallback_name)
            return None

        # Create new Construction
        new_constr = openstudio.model.Construction(model)
        new_constr.setName(custom_name)
        success = new_constr.setLayers(materials)
        if success:
            print(f"[OpenStudio Builder] Created custom construction '{custom_name}' with layers: {flat_layers}")
            return new_constr
        else:
            print(f"Error: Failed to set layers for construction '{custom_name}'.")
            if fallback_name:
                return get_or_create_construction(fallback_name)
            return None

    wall_default = get_or_create_construction(params.get("wall_layers", "Composite 2x4 Wood Stud R11"), "Composite 2x4 Wood Stud R11")
    roof_default = get_or_create_construction(params.get("roof_layers", "Composite 2x4 Wood Stud R11"), "Composite 2x4 Wood Stud R11")
    window_default = get_or_create_construction(params.get("window_layers", "Dbl Clr 3mm/13mm Air"), "Dbl Clr 3mm/13mm Air")
    floor_default = get_or_create_construction("Composite 2x4 Wood Stud R11", "Composite 2x4 Wood Stud R11")

    construction_set = openstudio.model.DefaultConstructionSet(model)
    construction_set.setName("Building Default Construction Set")

    ext_consts = openstudio.model.DefaultSurfaceConstructions(model)
    if wall_default: ext_consts.setWallConstruction(wall_default)
    if roof_default: ext_consts.setRoofCeilingConstruction(roof_default)
    if floor_default: ext_consts.setFloorConstruction(floor_default)
    construction_set.setDefaultExteriorSurfaceConstructions(ext_consts)

    int_consts = openstudio.model.DefaultSurfaceConstructions(model)
    if wall_default: int_consts.setWallConstruction(wall_default)
    if floor_default: int_consts.setFloorConstruction(floor_default)
    if roof_default: int_consts.setRoofCeilingConstruction(roof_default)
    construction_set.setDefaultInteriorSurfaceConstructions(int_consts)

    ground_consts = openstudio.model.DefaultSurfaceConstructions(model)
    if wall_default: ground_consts.setWallConstruction(wall_default)
    if floor_default: ground_consts.setFloorConstruction(floor_default)
    construction_set.setDefaultGroundContactSurfaceConstructions(ground_consts)

    sub_ext_consts = openstudio.model.DefaultSubSurfaceConstructions(model)
    if window_default: sub_ext_consts.setFixedWindowConstruction(window_default)
    if wall_default: sub_ext_consts.setDoorConstruction(wall_default)
    construction_set.setDefaultExteriorSubSurfaceConstructions(sub_ext_consts)

    sub_int_consts = openstudio.model.DefaultSubSurfaceConstructions(model)
    if window_default: sub_int_consts.setFixedWindowConstruction(window_default)
    if wall_default: sub_int_consts.setDoorConstruction(wall_default)
    construction_set.setDefaultInteriorSubSurfaceConstructions(sub_int_consts)

    model.getBuilding().setDefaultConstructionSet(construction_set)

    # 4. Resolve origins and build geometries
    origins = resolve_zone_origins(zones)
    space_objs = {}
    spaces = []

    for z in zones:
        name = z["name"]
        L = z.get("length", 10.0)
        W = z.get("width", 10.0)
        H = z.get("height", 3.0)
        ox, oy, oz = origins[name]

        # Create Space and Thermal Zone
        thermal_zone = openstudio.model.ThermalZone(model)
        thermal_zone.setName(f"{name}_ThermalZone")

        space = openstudio.model.Space(model)
        space.setName(name)
        space.setThermalZone(thermal_zone)
        space_objs[name] = space
        spaces.append(space)

        # Coordinate vertices (absolute)
        v_floor = [
            (ox, oy + W, oz),
            (ox + L, oy + W, oz),
            (ox + L, oy, oz),
            (ox, oy, oz)
        ]
        v_south = [
            (ox, oy, oz),
            (ox + L, oy, oz),
            (ox + L, oy, oz + H),
            (ox, oy, oz + H)
        ]
        v_east = [
            (ox + L, oy, oz),
            (ox + L, oy + W, oz),
            (ox + L, oy + W, oz + H),
            (ox + L, oy, oz + H)
        ]
        v_north = [
            (ox + L, oy + W, oz),
            (ox, oy + W, oz),
            (ox, oy + W, oz + H),
            (ox + L, oy + W, oz + H)
        ]
        v_west = [
            (ox, oy + W, oz),
            (ox, oy, oz),
            (ox, oy, oz + H),
            (ox, oy + W, oz + H)
        ]

        def create_surface(v_coords, s_name):
            pts = openstudio.Point3dVector()
            for cx, cy, cz in v_coords:
                pts.append(openstudio.Point3d(cx, cy, cz))
            surf = openstudio.model.Surface(pts, model)
            surf.setName(s_name)
            surf.setSpace(space)
            surf.assignDefaultSurfaceType()
            surf.assignDefaultBoundaryCondition()
            return surf

        surf_floor = create_surface(v_floor, f"{name}_Floor")
        surf_south = create_surface(v_south, f"{name}_Wall_South")
        surf_east = create_surface(v_east, f"{name}_Wall_East")
        surf_north = create_surface(v_north, f"{name}_Wall_North")
        surf_west = create_surface(v_west, f"{name}_Wall_West")

        # Roof geometry
        roof_type = z.get("roof_type", "flat").lower()
        roof_pitch_height = float(z.get("roof_pitch_height", 2.0))

        if roof_type == "pitched":
            v_roof_south = [
                (ox, oy, oz + H),
                (ox + L, oy, oz + H),
                (ox + L, oy + W/2, oz + H + roof_pitch_height),
                (ox, oy + W/2, oz + H + roof_pitch_height)
            ]
            v_roof_north = [
                (ox + L, oy + W, oz + H),
                (ox, oy + W, oz + H),
                (ox, oy + W/2, oz + H + roof_pitch_height),
                (ox + L, oy + W/2, oz + H + roof_pitch_height)
            ]
            v_gable_east = [
                (ox + L, oy, oz + H),
                (ox + L, oy + W, oz + H),
                (ox + L, oy + W/2, oz + H + roof_pitch_height)
            ]
            v_gable_west = [
                (ox, oy + W, oz + H),
                (ox, oy, oz + H),
                (ox, oy + W/2, oz + H + roof_pitch_height)
            ]
            surf_roof_s = create_surface(v_roof_south, f"{name}_Roof_South")
            surf_roof_n = create_surface(v_roof_north, f"{name}_Roof_North")
            surf_gable_e = create_surface(v_gable_east, f"{name}_Gable_East")
            surf_gable_w = create_surface(v_gable_west, f"{name}_Gable_West")
        else:
            v_roof = [
                (ox, oy + W, oz + H),
                (ox, oy, oz + H),
                (ox + L, oy, oz + H),
                (ox + L, oy + W, oz + H)
            ]
            surf_roof = create_surface(v_roof, f"{name}_Roof")

        # Specific constructions/materials overrides for this zone
        z_wall_layers = z.get("wall_layers")
        if z_wall_layers:
            z_wall_constr_obj = get_or_create_construction(z_wall_layers, "Composite 2x4 Wood Stud R11")
            if z_wall_constr_obj:
                for surf in [surf_south, surf_north, surf_east, surf_west]:
                    surf.setConstruction(z_wall_constr_obj)

        # Set specific orientation overrides
        for key, surf in [("wall_layers_south", surf_south), ("wall_layers_north", surf_north),
                          ("wall_layers_east", surf_east), ("wall_layers_west", surf_west)]:
            c_val = z.get(key)
            if c_val:
                c_obj = get_or_create_construction(c_val, "Composite 2x4 Wood Stud R11")
                if c_obj: surf.setConstruction(c_obj)

        # Specific roof_layers override for this zone
        z_roof_layers = z.get("roof_layers")
        if z_roof_layers:
            z_roof_constr_obj = get_or_create_construction(z_roof_layers, "Composite 2x4 Wood Stud R11")
            if z_roof_constr_obj:
                if roof_type == "pitched":
                    for r_surf in [surf_roof_s, surf_roof_n, surf_gable_e, surf_gable_w]:
                        r_surf.setConstruction(z_roof_constr_obj)
                else:
                    surf_roof.setConstruction(z_roof_constr_obj)

        # Retrieve window/door constructions for this zone to explicitly assign to subsurfaces
        z_window_constr = get_or_create_construction(z.get("window_layers"), "Dbl Clr 3mm/13mm Air") if z.get("window_layers") else window_default
        z_wall_constr = get_or_create_construction(z.get("wall_layers"), "Composite 2x4 Wood Stud R11") if z.get("wall_layers") else wall_default

        # Apply subsurfaces (WWR or precise Windows/Doors)
        wwr_s = float(z.get("wwr_south", 0.0))
        wwr_n = float(z.get("wwr_north", 0.0))
        wwr_e = float(z.get("wwr_east", 0.0))
        wwr_w = float(z.get("wwr_west", 0.0))

        def make_custom_subsurface(parent_surf, v_coords, data, wall_width, wall_height, sub_type, name_suffix):
            if not data or not isinstance(data, dict): return
            w = float(data.get("width", 1.0))
            h = float(data.get("height", 1.0))
            offset_x = float(data.get("offset_x", 0.0))
            ref_x = data.get("ref_x", "center")
            offset_z = float(data.get("offset_z", 0.0))
            ref_z = data.get("ref_z", "center")

            # Clamp dimensions to parent surface size with a small safety margin
            w = max(0.01, min(w, wall_width))
            h = max(0.01, min(h, wall_height))

            w_off = offset_x if ref_x == "left" else (wall_width - w - offset_x if ref_x == "right" else (wall_width - w) / 2.0)
            h_off = offset_z if ref_z == "bottom" else (wall_height - h - offset_z if ref_z == "top" else (wall_height - h) / 2.0)

            # Clamp offsets to fit inside wall boundaries
            w_off = max(0.0, min(w_off, wall_width - w))
            h_off = max(0.0, min(h_off, wall_height - h))

            # Interpolate relative geometry using the original un-reordered corner coordinates
            p_bl = v_coords[0]
            p_br = v_coords[1]

            def interpolate(pA, pB, frac):
                return openstudio.Point3d(
                    pA[0] + (pB[0] - pA[0]) * frac,
                    pA[1] + (pB[1] - pA[1]) * frac,
                    pA[2] + (pB[2] - pA[2]) * frac
                )

            sub_bl = interpolate(p_bl, p_br, w_off / wall_width)
            sub_br = interpolate(p_bl, p_br, (w_off + w) / wall_width)
            z_bottom = p_bl[2] + h_off
            z_top = z_bottom + h

            sub_v = openstudio.Point3dVector()
            sub_v.append(openstudio.Point3d(sub_bl.x(), sub_bl.y(), z_bottom))
            sub_v.append(openstudio.Point3d(sub_br.x(), sub_br.y(), z_bottom))
            sub_v.append(openstudio.Point3d(sub_br.x(), sub_br.y(), z_top))
            sub_v.append(openstudio.Point3d(sub_bl.x(), sub_bl.y(), z_top))

            sub = openstudio.model.SubSurface(sub_v, model)
            sub.setName(f"{parent_surf.nameString()}_{name_suffix}")
            sub.setSurface(parent_surf)
            sub.setSubSurfaceType(sub_type)

            # Explicitly set construction to avoid empty construction name translation error
            if sub_type == "FixedWindow" and z_window_constr:
                sub.setConstruction(z_window_constr)
            elif sub_type == "Door" and z_wall_constr:
                sub.setConstruction(z_wall_constr)

        # South Facade
        if z.get("window_south"):
            make_custom_subsurface(surf_south, v_south, z.get("window_south"), L, H, "FixedWindow", "Window")
        elif wwr_s > 0:
            surf_south.setWindowToWallRatio(wwr_s)
        if z.get("door_south"):
            make_custom_subsurface(surf_south, v_south, z.get("door_south"), L, H, "Door", "Door")

        # East Facade
        if z.get("window_east"):
            make_custom_subsurface(surf_east, v_east, z.get("window_east"), W, H, "FixedWindow", "Window")
        elif wwr_e > 0:
            surf_east.setWindowToWallRatio(wwr_e)
        if z.get("door_east"):
            make_custom_subsurface(surf_east, v_east, z.get("door_east"), W, H, "Door", "Door")

        # North Facade
        if z.get("window_north"):
            make_custom_subsurface(surf_north, v_north, z.get("window_north"), L, H, "FixedWindow", "Window")
        elif wwr_n > 0:
            surf_north.setWindowToWallRatio(wwr_n)
        if z.get("door_north"):
            make_custom_subsurface(surf_north, v_north, z.get("door_north"), L, H, "Door", "Door")

        # West Facade
        if z.get("window_west"):
            make_custom_subsurface(surf_west, v_west, z.get("window_west"), W, H, "FixedWindow", "Window")
        elif wwr_w > 0:
            surf_west.setWindowToWallRatio(wwr_w)
        if z.get("door_west"):
            make_custom_subsurface(surf_west, v_west, z.get("door_west"), W, H, "Door", "Door")

        # Centered subsurface helper (for roofs, skylights, etc.)
        def make_centered_subsurface(parent_surf, sub_w, sub_h, sub_type, name_suffix):
            p_verts = parent_surf.vertices()
            if len(p_verts) != 4: return None
            
            def dist(p1, p2):
                return math.sqrt((p1.x()-p2.x())**2 + (p1.y()-p2.y())**2 + (p1.z()-p2.z())**2)
                
            v0, v1, v2, v3 = p_verts[0], p_verts[1], p_verts[2], p_verts[3]
            L_u = dist(v0, v1)
            L_v = dist(v0, v3)
            
            if L_u <= 0 or L_v <= 0: return None
            
            # Clamp subsurface dimensions to fit parent with a margin
            w = min(sub_w, L_u * 0.9)
            h = min(sub_h, L_v * 0.9)
            
            frac_u = w / L_u
            frac_v = h / L_v
            
            u_start = (1.0 - frac_u) / 2.0
            u_end = u_start + frac_u
            v_start = (1.0 - frac_v) / 2.0
            v_end = v_start + frac_v
            
            def get_point(u, v):
                px0 = v0.x() + (v1.x() - v0.x()) * u
                py0 = v0.y() + (v1.y() - v0.y()) * u
                pz0 = v0.z() + (v1.z() - v0.z()) * u
                
                px1 = v3.x() + (v2.x() - v3.x()) * u
                py1 = v3.y() + (v2.y() - v3.y()) * u
                pz1 = v3.z() + (v2.z() - v3.z()) * u
                
                return openstudio.Point3d(
                    px0 + (px1 - px0) * v,
                    py0 + (py1 - py0) * v,
                    pz0 + (pz1 - pz0) * v
                )
                
            sub_v = openstudio.Point3dVector()
            sub_v.append(get_point(u_start, v_start))
            sub_v.append(get_point(u_end, v_start))
            sub_v.append(get_point(u_end, v_end))
            sub_v.append(get_point(u_start, v_end))
            
            sub = openstudio.model.SubSurface(sub_v, model)
            sub.setName(f"{parent_surf.nameString()}_{name_suffix}")
            sub.setSurface(parent_surf)
            sub.setSubSurfaceType(sub_type)
            if z_window_constr:
                sub.setConstruction(z_window_constr)
            return sub

        # Roof Skylights
        skylight_data = z.get("skylight")
        if skylight_data and isinstance(skylight_data, dict):
            s_w = float(skylight_data.get("width", 2.0))
            s_h = float(skylight_data.get("height", skylight_data.get("length", 1.5)))
            roof_surf = surf_roof_s if roof_type == "pitched" else (surf_roof if 'surf_roof' in locals() else None)
            if roof_surf:
                make_centered_subsurface(roof_surf, s_w, s_h, "Skylight", "Skylight")

    # 5. Resolve Zone Adjacencies (Shared Walls)
    space_vector = openstudio.model.SpaceVector()
    for space in spaces:
        space_vector.push_back(space)

    openstudio.model.intersectSurfaces(space_vector)
    openstudio.model.matchSurfaces(space_vector)

    # 5.5 Match/Mirror Subsurfaces on Shared Walls to avoid invalid blank Outside Boundary Condition Object severe error
    for surf in model.getSurfaces():
        if surf.outsideBoundaryCondition() == "Surface":
            adj_surf_opt = surf.adjacentSurface()
            if adj_surf_opt.is_initialized():
                adj_surf = adj_surf_opt.get()
                for sub_surf in surf.subSurfaces():
                    if not sub_surf.adjacentSubSurface().is_initialized():
                        # Create a mirrored copy of the subsurface on the adjacent surface
                        adj_vertices = openstudio.Point3dVector()
                        for v in reversed(sub_surf.vertices()):
                            adj_vertices.append(v)
                        new_sub = openstudio.model.SubSurface(adj_vertices, model)
                        new_sub.setName(f"{adj_surf.nameString()}_{sub_surf.nameString().split('_')[-1]}_Adj")
                        new_sub.setSurface(adj_surf)
                        new_sub.setSubSurfaceType(sub_surf.subSurfaceType())
                        if sub_surf.construction().is_initialized():
                            new_sub.setConstruction(sub_surf.construction().get())
                        
                        # Explicitly link them
                        new_sub.setAdjacentSubSurface(sub_surf)
                        sub_surf.setAdjacentSubSurface(new_sub)
                        print(f"[OpenStudio Builder] Mirrored subsurface {sub_surf.nameString()} to adjacent surface {adj_surf.nameString()} as {new_sub.nameString()}")

    # 6. Apply Internal Loads & Schedules
    def make_ruleset_schedule(name, val_off, val_on, wd_s, wd_e, we_s, we_e):
        sch = openstudio.model.ScheduleRuleset(model)
        sch.setName(name)
        default_day = sch.defaultDaySchedule()
        default_day.setName(f"{name}_DefaultDay")
        default_day.clearValues()

        if wd_s > 0:
            default_day.addValue(openstudio.Time(0, wd_s, 0, 0), val_off)
        if wd_e > wd_s:
            default_day.addValue(openstudio.Time(0, wd_e, 0, 0), val_on)
        if wd_e < 24:
            default_day.addValue(openstudio.Time(0, 24, 0, 0), val_off)

        # Weekend rule
        rule = openstudio.model.ScheduleRule(sch)
        rule.setName(f"{name}_WeekendRule")
        rule.setApplySaturday(True)
        rule.setApplySunday(True)
        day_sch = rule.daySchedule()
        day_sch.setName(f"{name}_WeekendDay")
        day_sch.clearValues()
        if we_s > 0:
            day_sch.addValue(openstudio.Time(0, we_s, 0, 0), val_off)
        if we_e > we_s:
            day_sch.addValue(openstudio.Time(0, we_e, 0, 0), val_on)
        if we_e < 24:
            day_sch.addValue(openstudio.Time(0, 24, 0, 0), val_off)

        return sch

    # Load schedule values from global params
    sch_occ = make_ruleset_schedule("OCCUPANCY_SCH", 0.0, 1.0, params.get("occ_weekday_start", 0), params.get("occ_weekday_end", 24), params.get("occ_weekend_start", 0), params.get("occ_weekend_end", 24))
    sch_light = make_ruleset_schedule("LIGHTING_SCH", 0.0, 1.0, params.get("light_weekday_start", 0), params.get("light_weekday_end", 24), params.get("light_weekend_start", 0), params.get("light_weekend_end", 24))
    sch_equip = make_ruleset_schedule("EQUIPMENT_SCH", 0.0, 1.0, params.get("equip_weekday_start", 0), params.get("equip_weekday_end", 24), params.get("equip_weekend_start", 0), params.get("equip_weekend_end", 24))
    
    sch_heat = make_ruleset_schedule("HEATING_SETPOINT_SCH", params.get("heat_set_unocc", 15.0), params.get("heat_set_occ", 21.0), params.get("hvac_weekday_start", 7), params.get("hvac_weekday_end", 18), params.get("hvac_weekend_start", 7), params.get("hvac_weekend_end", 18))
    sch_cool = make_ruleset_schedule("COOLING_SETPOINT_SCH", params.get("cool_set_unocc", 28.0), params.get("cool_set_occ", 24.0), params.get("hvac_weekday_start", 7), params.get("hvac_weekday_end", 18), params.get("hvac_weekend_start", 7), params.get("hvac_weekend_end", 18))

    thermostat = openstudio.model.ThermostatSetpointDualSetpoint(model)
    thermostat.setHeatingSetpointTemperatureSchedule(sch_heat)
    thermostat.setCoolingSetpointTemperatureSchedule(sch_cool)

    # Create a constant activity level schedule (120 W per person)
    sch_activity = openstudio.model.ScheduleConstant(model)
    sch_activity.setName("ACTIVITY_LEVEL_SCH")
    sch_activity.setValue(120.0)

    # Attach setpoints and load objects to spaces
    for z in zones:
        space = space_objs[z["name"]]
        thermal_zone = space.thermalZone().get()
        thermal_zone.setThermostatSetpointDualSetpoint(thermostat)

        # People
        people_def = openstudio.model.PeopleDefinition(model)
        people_def.setName(f"{z['name']}_PeopleDef")
        people_def.setSpaceFloorAreaperPerson(float(z.get("people_density", 10.0)))
        people_inst = openstudio.model.People(people_def)
        people_inst.setName(f"{z['name']}_People")
        people_inst.setSpace(space)
        people_inst.setNumberofPeopleSchedule(sch_occ)
        people_inst.setActivityLevelSchedule(sch_activity)

        # Lights
        light_def = openstudio.model.LightsDefinition(model)
        light_def.setName(f"{z['name']}_LightsDef")
        light_def.setWattsperSpaceFloorArea(float(z.get("light_density", 10.0)))
        light_inst = openstudio.model.Lights(light_def)
        light_inst.setName(f"{z['name']}_Lights")
        light_inst.setSpace(space)
        light_inst.setSchedule(sch_light)

        # Equipment
        equip_def = openstudio.model.ElectricEquipmentDefinition(model)
        equip_def.setName(f"{z['name']}_EquipDef")
        equip_def.setWattsperSpaceFloorArea(float(z.get("equipment_density", 10.0)))
        equip_inst = openstudio.model.ElectricEquipment(equip_def)
        equip_inst.setName(f"{z['name']}_Equip")
        equip_inst.setSpace(space)
        equip_inst.setSchedule(sch_equip)

        # Infiltration
        infil_ach = float(z.get("infiltration_ach", 0.5))
        if infil_ach > 0:
            infil = openstudio.model.SpaceInfiltrationDesignFlowRate(model)
            infil.setName(f"{z['name']}_Infiltration")
            infil.setSpace(space)
            infil.setAirChangesperHour(infil_ach)

        # Ventilation
        vent_ach = float(z.get("ventilation_ach", 0.5))
        if vent_ach > 0:
            oa = openstudio.model.DesignSpecificationOutdoorAir(model)
            oa.setName(f"{z['name']}_OutdoorAir")
            oa.setOutdoorAirFlowRateFractionSchedule(sch_occ)
            space.setDesignSpecificationOutdoorAir(oa)

    # 7. Apply HVAC Systems
    for z in zones:
        space = space_objs[z["name"]]
        thermal_zone = space.thermalZone().get()
        hvac_type = z.get("hvac_type", "ideal_loads").lower()

        if hvac_type == "ideal_loads":
            ideal_loads = openstudio.model.ZoneHVACIdealLoadsAirSystem(model)
            ideal_loads.setName(f"{z['name']}_IdealLoads")
            ideal_loads.addToThermalZone(thermal_zone)
            print(f"[OpenStudio Builder] Assigned Ideal Air Loads to {z['name']}")
        elif hvac_type == "ptac":
            fan = openstudio.model.FanConstantVolume(model)
            heating_coil = openstudio.model.CoilHeatingElectric(model)
            cooling_coil = openstudio.model.CoilCoolingDXSingleSpeed(model)
            ptac = openstudio.model.ZoneHVACPackagedTerminalAirConditioner(
                model,
                model.alwaysOnDiscreteSchedule(),
                fan,
                heating_coil,
                cooling_coil
            )
            ptac.setName(f"{z['name']}_PTAC")
            ptac.addToThermalZone(thermal_zone)
            print(f"[OpenStudio Builder] Assigned PTAC system to {z['name']}")
        elif hvac_type == "psz_ac":
            # Instantiate PTHP (Packaged Terminal Heat Pump) as single zone packaged AC
            try:
                fan = openstudio.model.FanConstantVolume(model)
                cooling_coil = openstudio.model.CoilCoolingDXSingleSpeed(model)
                heating_coil_dx = openstudio.model.CoilHeatingDXSingleSpeed(model)
                supp_heating_coil = openstudio.model.CoilHeatingElectric(model)
                pthp = openstudio.model.ZoneHVACPackagedTerminalHeatPump(
                    model,
                    model.alwaysOnDiscreteSchedule(),
                    fan,
                    heating_coil_dx,
                    cooling_coil,
                    supp_heating_coil
                )
            except Exception as e:
                print(f"[OpenStudio Builder] PTHP compound constructor failed: {e}. Falling back to default pthp.")
                pthp = openstudio.model.ZoneHVACPackagedTerminalHeatPump(model)

            pthp.setName(f"{z['name']}_PSZ_AC")
            pthp.addToThermalZone(thermal_zone)
            print(f"[OpenStudio Builder] Assigned PSZ-AC (PTHP) system to {z['name']}")

    # 8. Sizing Calculations & Simulation Control Setup
    sim_control = model.getSimulationControl()
    sim_control.setDoZoneSizingCalculation(True)
    sim_control.setDoSystemSizingCalculation(True)
    sim_control.setDoPlantSizingCalculation(True)

    print("[OpenStudio Builder] Model build complete!")
    return model

def build_idf_from_params(params: dict) -> str:
    """
    Builds the OpenStudio model and translates it to an EnergyPlus IDF string,
    then post-processes it to inject essential sizing and weather simulation objects.
    """
    model = build_openstudio_model(params)
    translator = openstudio.energyplus.ForwardTranslator()
    workspace = translator.translateModel(model)
    idf_str = str(workspace)

    # 1. Clean existing sizing/environment/simulation controls if any exist
    classes_to_clean = [
        "SimulationControl",
        "Sizing:Parameters",
        "Site:Location",
        "SizingPeriod:DesignDay",
        "Site:GroundTemperature:BuildingSurface",
        "GlobalGeometryRules"
    ]
    for cls in classes_to_clean:
        pattern = r'(?is)(?:\r?\n|^)\s*' + re.escape(cls) + r'\s*,.*?;'
        idf_str = re.sub(pattern, '', idf_str)

    # 2. Extract sizing/environment objects from templates/Base.idf
    base_idf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "Base.idf")
    base_blocks = ""
    if os.path.exists(base_idf_path):
        try:
            with open(base_idf_path, "r", encoding="utf-8") as f:
                base_content = f.read()
            extracted = []
            for cls in classes_to_clean:
                pattern = r'(?im)^\s*(' + re.escape(cls) + r'\s*,[^;]*;)'
                matches = re.findall(pattern, base_content)
                for m in matches:
                    extracted.append(m)
            base_blocks = "\n\n".join(extracted)
        except Exception as e:
            print(f"[OpenStudio Builder] Error reading/extracting from Base.idf: {e}")

    # 3. Create Sizing:Zone objects for each zone in the model
    is_multizone = params.get("is_multizone", False)
    if not is_multizone:
        zones = [{"name": "ZONE ONE", "ventilation_ach": params.get("ventilation_ach", 0.5)}]
    else:
        zones = params.get("zones", [])

    sizing_zone_blocks = []
    for z in zones:
        zone_name = f"{z['name']}_ThermalZone"
        vent_ach = float(z.get("ventilation_ach", 0.5))
        oa_spec_name = f"{z['name']}_OutdoorAir" if vent_ach > 0 else ""
        
        sizing_zone_block = f"""
  Sizing:Zone,
    {zone_name},             !- Zone or ZoneList Name
    SupplyAirTemperature,    !- Zone Cooling Design Supply Air Temperature Input Method
    12.,                     !- Zone Cooling Design Supply Air Temperature {{C}}
    ,                        !- Zone Cooling Design Supply Air Temperature Difference {{deltaC}}
    SupplyAirTemperature,    !- Zone Heating Design Supply Air Temperature Input Method
    50.,                     !- Zone Heating Design Supply Air Temperature {{C}}
    ,                        !- Zone Heating Design Supply Air Temperature Difference {{deltaC}}
    0.008,                   !- Zone Cooling Design Supply Air Humidity Ratio {{kgWater/kgDryAir}}
    0.008,                   !- Zone Heating Design Supply Air Humidity Ratio {{kgWater/kgDryAir}}
    {oa_spec_name},          !- Design Specification Outdoor Air Object Name
    1.2,                     !- Zone Heating Sizing Factor
    1.2;                     !- Zone Cooling Sizing Factor
"""
        sizing_zone_blocks.append(sizing_zone_block)

    sizing_zone_blocks_str = "\n\n".join(sizing_zone_blocks)

    # 4. Append injected blocks to translated IDF
    idf_str = idf_str.rstrip() + "\n\n! === Sizing and Simulation Control Setup (Injected from Base.idf) ===\n\n"
    if base_blocks:
        idf_str += base_blocks + "\n\n"
    if sizing_zone_blocks_str:
        idf_str += sizing_zone_blocks_str + "\n"

    return idf_str
