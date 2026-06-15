import os
import sys
import math
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
            if "people_density" not in z: z["people_density"] = params.get("people_density", 10.0)
            if "light_density" not in z: z["light_density"] = params.get("light_density", 10.0)
            if "equipment_density" not in z: z["equipment_density"] = params.get("equipment_density", 10.0)
            if "ventilation_ach" not in z: z["ventilation_ach"] = params.get("ventilation_ach", 0.5)
            if "infiltration_ach" not in z: z["infiltration_ach"] = params.get("infiltration_ach", 0.5)
            if "hvac_type" not in z: z["hvac_type"] = z.get("hvac_type") or params.get("hvac_type", "ideal_loads")

    # 2. Extract and resolve all required constructions & materials
    names_to_resolve = set(["Composite 2x4 Wood Stud R11", "Theoretical Glass [167]"])
    for z in zones:
        for key in ["wall_layers", "wall_layers_south", "wall_layers_north", "wall_layers_east", "wall_layers_west", "roof_layers", "window_layers"]:
            val = z.get(key)
            if val:
                if isinstance(val, str):
                    names_to_resolve.add(val)
                elif isinstance(val, list):
                    for item in val:
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
    def get_constr(name, default_name):
        opt = model.getConstructionByName(name)
        if opt.is_initialized():
            return opt.get()
        opt_def = model.getConstructionByName(default_name)
        if opt_def.is_initialized():
            return opt_def.get()
        return None

    wall_default = get_constr(params.get("wall_layers", "Composite 2x4 Wood Stud R11"), "Composite 2x4 Wood Stud R11")
    roof_default = get_constr(params.get("roof_layers", "Composite 2x4 Wood Stud R11"), "Composite 2x4 Wood Stud R11")
    window_default = get_constr(params.get("window_layers", "Theoretical Glass [167]"), "Theoretical Glass [167]")
    floor_default = get_constr("Composite 2x4 Wood Stud R11", "Composite 2x4 Wood Stud R11")

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
    if window_default: sub_ext_consts.setWindowConstruction(window_default)
    construction_set.setDefaultExteriorSubSurfaceConstructions(sub_ext_consts)

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

        # Set specific constructions overrides
        for key, surf in [("wall_layers_south", surf_south), ("wall_layers_north", surf_north),
                          ("wall_layers_east", surf_east), ("wall_layers_west", surf_west)]:
            c_val = z.get(key)
            if c_val:
                c_obj = get_constr(c_val, "Composite 2x4 Wood Stud R11")
                if c_obj: surf.setConstruction(c_obj)

        # Apply subsurfaces (WWR or precise Windows/Doors)
        wwr_s = float(z.get("wwr_south", 0.0))
        wwr_n = float(z.get("wwr_north", 0.0))
        wwr_e = float(z.get("wwr_east", 0.0))
        wwr_w = float(z.get("wwr_west", 0.0))

        def make_custom_subsurface(parent_surf, data, wall_width, wall_height, sub_type, name_suffix):
            if not data or not isinstance(data, dict): return
            w = float(data.get("width", 1.0))
            h = float(data.get("height", 1.0))
            offset_x = float(data.get("offset_x", 0.0))
            ref_x = data.get("ref_x", "center")
            offset_z = float(data.get("offset_z", 0.0))
            ref_z = data.get("ref_z", "center")

            w_off = offset_x if ref_x == "left" else (wall_width - w - offset_x if ref_x == "right" else (wall_width - w) / 2.0)
            h_off = offset_z if ref_z == "bottom" else (wall_height - h - offset_z if ref_z == "top" else (wall_height - h) / 2.0)

            # Interpolate relative geometry coplanar with the wall
            p_bl = parent_surf.vertices()[0]
            p_br = parent_surf.vertices()[1]

            def interpolate(pA, pB, frac):
                return openstudio.Point3d(
                    pA.x() + (pB.x() - pA.x()) * frac,
                    pA.y() + (pB.y() - pA.y()) * frac,
                    pA.z() + (pB.z() - pA.z()) * frac
                )

            sub_bl = interpolate(p_bl, p_br, w_off / wall_width)
            sub_br = interpolate(p_bl, p_br, (w_off + w) / wall_width)
            z_bottom = p_bl.z() + h_off
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

        # South Facade
        if z.get("window_south"):
            make_custom_subsurface(surf_south, z.get("window_south"), L, H, "FixedWindow", "Window")
        elif wwr_s > 0:
            surf_south.setWindowToWallRatio(wwr_s)
        if z.get("door_south"):
            make_custom_subsurface(surf_south, z.get("door_south"), L, H, "Door", "Door")

        # East Facade
        if z.get("window_east"):
            make_custom_subsurface(surf_east, z.get("window_east"), W, H, "FixedWindow", "Window")
        elif wwr_e > 0:
            surf_east.setWindowToWallRatio(wwr_e)
        if z.get("door_east"):
            make_custom_subsurface(surf_east, z.get("door_east"), W, H, "Door", "Door")

        # North Facade
        if z.get("window_north"):
            make_custom_subsurface(surf_north, z.get("window_north"), L, H, "FixedWindow", "Window")
        elif wwr_n > 0:
            surf_north.setWindowToWallRatio(wwr_n)
        if z.get("door_north"):
            make_custom_subsurface(surf_north, z.get("door_north"), L, H, "Door", "Door")

        # West Facade
        if z.get("window_west"):
            make_custom_subsurface(surf_west, z.get("window_west"), W, H, "FixedWindow", "Window")
        elif wwr_w > 0:
            surf_west.setWindowToWallRatio(wwr_w)
        if z.get("door_west"):
            make_custom_subsurface(surf_west, z.get("door_west"), W, H, "Door", "Door")

    # 5. Resolve Zone Adjacencies (Shared Walls)
    space_vector = openstudio.model.SpaceVector()
    for space in spaces:
        space_vector.push_back(space)

    openstudio.model.intersectSurfaces(space_vector)
    openstudio.model.matchSurfaces(space_vector)

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
            thermal_zone.setUseIdealAirLoads(True)
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
    Builds the OpenStudio model and translates it to an EnergyPlus IDF string.
    """
    model = build_openstudio_model(params)
    translator = openstudio.energyplus.ForwardTranslator()
    workspace = translator.translateModel(model)
    return str(workspace)
