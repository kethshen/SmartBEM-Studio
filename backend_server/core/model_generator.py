import os
import json

try:
    import openai
except ImportError:
    openai = None

try:
    from google import genai
except ImportError:
    genai = None

try:
    from huggingface_hub import InferenceClient
except ImportError:
    InferenceClient = None


class AIPipelines:
    def __init__(self, secrets_path="secrets.json", template_path="idf_templates/Base.idf"):
        # 1. Load Secrets
        self.api_keys = {}
        if os.path.exists(secrets_path):
            with open(secrets_path, "r") as f:
                self.api_keys = json.load(f)
        else:
            print(f"[AI] Warning: {secrets_path} not found. AI generation will fail.")

        # 2. Configure OpenAI
        if "OPENAI_API_KEY" in self.api_keys:
            try:
                self.openai_client = openai.OpenAI(api_key=self.api_keys["OPENAI_API_KEY"])
            except Exception as e:
                print(f"[AI] Failed to init OpenAI: {e}")
                self.openai_client = None
        else:
            self.openai_client = None

        # 3. Configure Gemini (New SDK)
        if "GEMINI_API_KEY" in self.api_keys:
             try:
                self.gemini_client = genai.Client(api_key=self.api_keys["GEMINI_API_KEY"])
             except Exception as e:
                print(f"[AI] Failed to init Gemini: {e}")
                self.gemini_client = None
        else:
            self.gemini_client = None

        # 3.5 Configure HuggingFace
        if "HUGGINGFACE_API_KEY" in self.api_keys:
            self.hf_api_key = self.api_keys["HUGGINGFACE_API_KEY"]
            try:
                self.hf_client = InferenceClient(api_key=self.hf_api_key)
            except Exception as e:
                print(f"[AI] Failed to init HuggingFace: {e}")
                self.hf_client = None
        else:
            self.hf_api_key = None
            self.hf_client = None

        # 4. Load Base Template
        self.base_idf = ""
        if os.path.exists(template_path):
            with open(template_path, "r") as f:
                self.base_idf = f.read()
        else:
             print(f"[AI] Warning: {template_path} not found. Using empty string.")

    def generate_idf_from_text(self, nlp_text, config, model_type="openai"):
        """
        Generates a modified IDF by requesting JSON from the AI and combining modules.
        """
        print(f"[AI] Generating Modular IDF using model: {model_type}")

        # Check if the prompt needs structuring
        if "[GLOBAL SETTINGS]" not in nlp_text and "<Zone:" not in nlp_text:
            print("[AI] Raw prompt detected. Running Prompt Structurer pre-processing pass...")
            try:
                from core.prompt_preprocessor import PromptPreprocessor
                structurer = PromptPreprocessor(ai_pipelines_instance=self)
                structured_prompt = structurer.restructure_prompt(nlp_text, model_type=model_type)
                print(f"[AI] Restructured Prompt generated:\n{structured_prompt}\n")
                nlp_text = structured_prompt
            except Exception as e:
                print(f"[AI] Prompt preprocessor failed, falling back to raw prompt: {e}")

        # 1. Load the Menu
        import sys
        # ensure we can import from backend dir
        sys.path.append(os.path.dirname(__file__))
        import coordinates_calculator
        import idf_assembler

        try:
            with open(os.path.join(os.path.dirname(__file__), "index.json"), 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            # --- PASS 1: The Planner (Extract Keywords) ---
            print(f"[AI RAG] Running Pass 1 (Planner) to extract keywords...")
            keywords = self._generate_search_keywords(nlp_text, model_type)
            print(f"[AI RAG] Extracted Keywords: {keywords}")

            # --- RETRIEVER: Filter the Massive Menu ---
            all_constructions = list(index_data.get("Construction", {}).keys())
            
            # Simple scoring function: How many keywords are in the construction name?
            def score_item(item_name):
                return sum(1 for kw in keywords if kw.lower() in item_name.lower())
                
            # Sort by score and take the top 15 most relevant walls/roofs!
            construction_menu = sorted(all_constructions, key=score_item, reverse=True)[:15]
            print(f"[AI RAG] Filtered Menu down to 15 items: {construction_menu}")
            
            # Extract raw materials for dynamic constructions
            raw_materials = []
            for cat in ["Material", "Material:NoMass", "Material:AirGap"]:
                raw_materials.extend(list(index_data.get(cat, {}).keys()))
            raw_materials = sorted(raw_materials, key=score_item, reverse=True)[:15]
            
            # Extract window materials for dynamic windows
            window_materials = []
            for cat in ["WindowMaterial:Glazing", "WindowMaterial:Gas"]:
                window_materials.extend(list(index_data.get(cat, {}).keys()))
            window_materials = sorted(window_materials, key=score_item, reverse=True)[:10]

        except Exception as e:
            print(f"Warning: Could not load index.json or RAG failed: {e}")
            construction_menu = ["Composite 2x4 Wood Stud R11"]
            raw_materials = ["M01 100mm brick", "I02 50mm insulation board"]
            window_materials = ["Clear 3mm"]

        # 2. Decomposed Pipeline: Step 1 - Extract Topology and Global Parameters
        try:
            # Step 1: Extract Topology and Global Parameters
            print("[AI] Step 1: Extracting building topology & global parameters...")
            topology_json = self._extract_topology(nlp_text, config, model_type)
            if topology_json.startswith("!"):
                return topology_json
            
            try:
                params = json.loads(topology_json)
            except json.JSONDecodeError as je:
                print(f"[AI] Topology JSON parse failed: {je}. Attempting repair...")
                try:
                    params = self._repair_truncated_json(topology_json)
                    print("[AI] Topology JSON successfully repaired and parsed!")
                except Exception as re:
                    print(f"[AI] Topology repair failed: {re}")
                    return f"! Error: AI failed to output valid JSON for topology. Result was: {topology_json}"

            is_multizone = params.get("is_multizone", False)
            zones = params.get("zones", [])

            # Step 2: Extract details for each zone in a loop
            completed_zones = []
            for z in zones:
                z_name = z["name"]
                print(f"[AI] Step 2: Extracting details for zone '{z_name}'...")
                zone_details_json = self._extract_zone_details(nlp_text, z_name, construction_menu, raw_materials, window_materials, model_type)
                if zone_details_json.startswith("!"):
                    return zone_details_json
                
                try:
                    z_details = json.loads(zone_details_json)
                except json.JSONDecodeError as je:
                    print(f"[AI] Zone details JSON parse failed for '{z_name}': {je}. Attempting repair...")
                    try:
                        z_details = self._repair_truncated_json(zone_details_json)
                        print(f"[AI] Zone details JSON for '{z_name}' successfully repaired and parsed!")
                    except Exception as re:
                        print(f"[AI] Zone details repair failed for '{z_name}': {re}")
                        return f"! Error: AI failed to output valid JSON for zone '{z_name}'. Result was: {zone_details_json}"
                
                # 1. Copy all non-subsurface keys from z_details to z
                for key, val in z_details.items():
                    if key != "subsurfaces":
                        z[key] = val

                # 2. Extract subsurfaces list
                subsurfaces = z_details.get("subsurfaces", [])

                # 3. Initialize all directional window/door fields
                for direction in ["south", "north", "east", "west"]:
                    z[f"window_{direction}"] = None
                    z[f"door_{direction}"] = None
                    try:
                        z[f"wwr_{direction}"] = float(z.get(f"wwr_{direction}") or 0.0)
                    except (ValueError, TypeError):
                        z[f"wwr_{direction}"] = 0.0

                # 4. Map the subsurfaces list to specific directional keys
                if isinstance(subsurfaces, list):
                    for sub in subsurfaces:
                        if not isinstance(sub, dict):
                            continue
                        sub_type = sub.get("type")
                        wall_dir = sub.get("wall")
                        if not sub_type or not wall_dir:
                            continue
                        
                        wall_dir = wall_dir.strip().capitalize()
                        if wall_dir not in ["South", "North", "East", "West"]:
                            continue
                            
                        # Extract and parse dimensions
                        w = sub.get("width")
                        h = sub.get("height")
                        
                        try:
                            w = float(w) if w is not None else 1.0
                            h = float(h) if h is not None else 1.0
                        except (ValueError, TypeError):
                            w = 1.0
                            h = 1.0
                            
                        # Door Aspect Ratio Guard: doors are always vertical (height >= width)
                        if sub_type == "door" and w > h:
                            print(f"[AI Guard] Automatically swapped flipped door dimensions on zone '{z_name}' {wall_dir} wall: width={h}, height={w}")
                            w, h = h, w
                            
                        sub["width"] = w
                        sub["height"] = h
                        
                        direction = wall_dir.lower()
                        if sub_type == "window":
                            z[f"window_{direction}"] = sub
                            z[f"wwr_{direction}"] = 0.0  # Override WWR to avoid overlapping subsurfaces
                        elif sub_type == "door":
                            z[f"door_{direction}"] = sub

                completed_zones.append(z)

            params["zones"] = completed_zones

            # If single-zone mode, map zone-specific details to the root level of params
            if not is_multizone and len(completed_zones) > 0:
                first_zone = completed_zones[0]
                for key, val in first_zone.items():
                    params[key] = val
                params["length"] = first_zone.get("length", params.get("length", 10.0))
                params["width"] = first_zone.get("width", params.get("width", 10.0))
                params["height"] = first_zone.get("height", params.get("height", 3.0))
            
            # ========== ROUTER: Custom Template vs OpenStudio SDK ==========
            generator_type = config.get("generator_type", "custom")
            if generator_type == "openstudio":
                print("[AI Assembler] *** Routing to OpenStudio SDK Builder ***")
                from core import openstudio_builder
                return openstudio_builder.build_idf_from_params(params)

            # ========== MULTI-ZONE vs SINGLE-ZONE ROUTER (Custom Engine) ==========
            is_multizone = params.get("is_multizone", False)
            
            custom_constructions_list = []
            extracted_blocks = {}
            
            if is_multizone:
                print("[AI Assembler MZ] *** MULTI-ZONE mode detected ***")
                return self._assemble_multizone_idf(params, config, construction_menu, index_data, idf_assembler, custom_constructions_list, extracted_blocks)
            
            # ========== SINGLE-ZONE PATH (existing, untouched) ==========
            print("[AI Assembler] Single-zone mode")
            L = params.get("length", 10.0)
            W = params.get("width", 10.0)
            H = params.get("height", 3.0)
            # Wall, Roof, and Window Parsing
            global_wall_layers = params.get("wall_layers", "Composite 2x4 Wood Stud R11")
            global_wall = self._resolve_construction(global_wall_layers, "Wall_Global", custom_constructions_list, idf_assembler, extracted_blocks)
            
            wall_s_layers = params.get("wall_layers_south", global_wall_layers) or global_wall_layers
            wall_s = self._resolve_construction(wall_s_layers, "Wall_S", custom_constructions_list, idf_assembler, extracted_blocks)
            
            wall_n_layers = params.get("wall_layers_north", global_wall_layers) or global_wall_layers
            wall_n = self._resolve_construction(wall_n_layers, "Wall_N", custom_constructions_list, idf_assembler, extracted_blocks)
            
            wall_e_layers = params.get("wall_layers_east", global_wall_layers) or global_wall_layers
            wall_e = self._resolve_construction(wall_e_layers, "Wall_E", custom_constructions_list, idf_assembler, extracted_blocks)
            
            wall_w_layers = params.get("wall_layers_west", global_wall_layers) or global_wall_layers
            wall_w = self._resolve_construction(wall_w_layers, "Wall_W", custom_constructions_list, idf_assembler, extracted_blocks)
            
            roof_layers = params.get("roof_layers", "Composite 2x4 Wood Stud R11")
            roof_name = self._resolve_construction(roof_layers, "Roof", custom_constructions_list, idf_assembler, extracted_blocks)

            window_layers = params.get("window_layers", "Theoretical Glass [167]")
            window_constr = self._resolve_construction(window_layers, "Window", custom_constructions_list, idf_assembler, extracted_blocks)
            
            # WWR Parsing
            global_wwr = params.get("wwr", 0.0) # Fallback if AI hallucinates old key
            wwr_s = params.get("wwr_south", global_wwr)
            wwr_n = params.get("wwr_north", global_wwr)
            wwr_e = params.get("wwr_east", global_wwr)
            wwr_w = params.get("wwr_west", global_wwr)

            window_s = params.get("window_south", None)
            window_n = params.get("window_north", None)
            window_e = params.get("window_east", None)
            window_w = params.get("window_west", None)

            door_s = params.get("door_south", None)
            door_n = params.get("door_north", None)
            door_e = params.get("door_east", None)
            door_w = params.get("door_west", None)
            
            # Thermodynamic defaults
            people = params.get("people_density", 10.0)
            lights = params.get("light_density", 10.0)
            equip = params.get("equipment_density", 10.0)
            vent = params.get("ventilation_ach", 0.5)
            infil = params.get("infiltration_ach", 0.5)
            heat_occ = params.get("heat_set_occ", 21.0)
            heat_unocc = params.get("heat_set_unocc", 15.0)
            cool_occ = params.get("cool_set_occ", 24.0)
            cool_unocc = params.get("cool_set_unocc", 28.0)
            win_u = params.get("window_u_factor", 3.0)
            win_shgc = params.get("window_shgc", 0.5)
            hvac_type = params.get("hvac_type", "ideal_loads")
            
            # Schedule Parsing
            occ_wd_start = params.get("occ_weekday_start", 0)
            occ_wd_end = params.get("occ_weekday_end", 24)
            occ_we_start = params.get("occ_weekend_start", 0)
            occ_we_end = params.get("occ_weekend_end", 24)
            
            lgt_wd_start = params.get("light_weekday_start", 0)
            lgt_wd_end = params.get("light_weekday_end", 24)
            lgt_we_start = params.get("light_weekend_start", 0)
            lgt_we_end = params.get("light_weekend_end", 24)
            
            eqp_wd_start = params.get("equip_weekday_start", 0)
            eqp_wd_end = params.get("equip_weekday_end", 24)
            eqp_we_start = params.get("equip_weekend_start", 0)
            eqp_we_end = params.get("equip_weekend_end", 24)
            
            hvac_wd_start = params.get("hvac_weekday_start", 7)
            hvac_wd_end = params.get("hvac_weekday_end", 18)
            hvac_we_start = params.get("hvac_weekend_start", 7)
            hvac_we_end = params.get("hvac_weekend_end", 18)
            
            def make_compact_schedule(name, val_off, val_on, wd_s, wd_e, we_s, we_e):
                wd_s = max(0, min(24, int(wd_s if wd_s is not None else 0)))
                wd_e = max(0, min(24, int(wd_e if wd_e is not None else 24)))
                we_s = max(0, min(24, int(we_s if we_s is not None else 0)))
                we_e = max(0, min(24, int(we_e if we_e is not None else 24)))
                
                def day_lines(start, end):
                    """Return a list of 'Until: HH:00, value' strings for one day-type."""
                    if start == 0 and end == 0:
                        return [f"    Until: 24:00, {val_off}"]
                    elif start == 0 and end == 24:
                        return [f"    Until: 24:00, {val_on}"]
                    else:
                        parts = []
                        if start > 0:
                            parts.append(f"    Until: {start:02d}:00, {val_off}")
                        parts.append(f"    Until: {end:02d}:00, {val_on}")
                        if end < 24:
                            parts.append(f"    Until: 24:00, {val_off}")
                        return parts
                
                wd_lines = day_lines(wd_s, wd_e)
                we_lines = day_lines(we_s, we_e)
                
                # Build fields list — all get commas except the very last which gets semicolon
                fields = []
                fields.append(f"    {name}")
                fields.append("    Any Number")
                fields.append("    Through: 12/31")
                fields.append("    For: Weekdays SummerDesignDay WinterDesignDay CustomDay1 CustomDay2")
                fields.extend(wd_lines)
                fields.append("    For: Weekends Holidays AllOtherDays")
                fields.extend(we_lines)
                
                # Join with comma-newline, last field gets semicolon
                body = ",\n".join(fields[:-1]) + ",\n" + fields[-1] + ";\n"
                
                return "\n  Schedule:Compact,\n" + body + "\n"

            schedules_block = ""
            schedules_block += make_compact_schedule("OCCUPANCY_SCH", 0, 1, occ_wd_start, occ_wd_end, occ_we_start, occ_we_end)
            schedules_block += make_compact_schedule("LIGHTING_SCH", 0, 1, lgt_wd_start, lgt_wd_end, lgt_we_start, lgt_we_end)
            schedules_block += make_compact_schedule("EQUIPMENT_SCH", 0, 1, eqp_wd_start, eqp_wd_end, eqp_we_start, eqp_we_end)
            schedules_block += make_compact_schedule("HEATING_SETPOINT_SCH", heat_unocc, heat_occ, hvac_wd_start, hvac_wd_end, hvac_we_start, hvac_we_end)
            schedules_block += make_compact_schedule("COOLING_SETPOINT_SCH", cool_unocc, cool_occ, hvac_wd_start, hvac_wd_end, hvac_we_start, hvac_we_end)

            # Validate hvac_type against allowed options
            allowed_hvac = ["ideal_loads", "ptac", "psz_ac"]
            if hvac_type not in allowed_hvac:
                print(f"[AI Assembler] Unknown hvac_type '{hvac_type}', falling back to ideal_loads")
                hvac_type = "ideal_loads"

            print(f"[AI Assembler] AI Selected -> L:{L}, W:{W}, Wall_S:{wall_s}, WWR_S:{wwr_s}, Door_S:{door_s}, HVAC:{hvac_type}")

            # 6. Extract material blocks from Datasets
            # 6. Extract material blocks from Datasets
            default_wall = "Composite 2x4 Wood Stud R11"
            default_win = "Theoretical Glass [167]"
            for constr in [global_wall, wall_s, wall_n, wall_e, wall_w, roof_name]:
                if constr and not constr.startswith("Custom_"):
                    idf_assembler.resolve_dependencies("Construction", constr, extracted_blocks)
                    if f"Construction::{constr}" not in extracted_blocks and constr != default_wall:
                        print(f"[AI Assembler] Fallback: Construction '{constr}' not found.")
                        idf_assembler.resolve_dependencies("Construction", default_wall, extracted_blocks)
            
            if window_constr and not window_constr.startswith("Custom_"):
                idf_assembler.resolve_dependencies("Construction", window_constr, extracted_blocks)
                if f"Construction::{window_constr}" not in extracted_blocks and window_constr != default_win:
                    print(f"[AI Assembler] Fallback: Window Construction '{window_constr}' not found.")
                    idf_assembler.resolve_dependencies("Construction", default_win, extracted_blocks)

            # 6. Build Geometry (Now passing directional WWRs, Materials, and custom Windows/Doors)
            # Roof properties
            roof_type = params.get("roof_type", "flat")
            roof_pitch_height = params.get("roof_pitch_height", 2.0)
            skylight_data = params.get("skylight", None)
            
            # 5. Generate Geometry
            geometry_idf = coordinates_calculator.generate_zone_geometry(
                L, W, H,
                wwr_s, wwr_n, wwr_e, wwr_w,
                wall_s, wall_n, wall_e, wall_w,
                door_s, door_n, door_e, door_w,
                window_s, window_n, window_e, window_w,
                zone_name="ZONE ONE",
                roof_type=roof_type,
                roof_pitch_height=roof_pitch_height,
                skylight_data=skylight_data
            )

            # 6.5 Load HVAC Template
            hvac_idf_block = ""
            hvac_template_dir = os.path.join(os.path.dirname(__file__), "..", "idf_templates", "hvac")
            hvac_template_path = os.path.join(hvac_template_dir, f"{hvac_type}.idf")
            if os.path.exists(hvac_template_path):
                with open(hvac_template_path, "r", encoding="utf-8") as hf:
                    hvac_idf_block = hf.read()
                # Replace zone name placeholder in HVAC template
                hvac_idf_block = hvac_idf_block.replace("{ZONE_NAME}", "ZONE ONE")
                print(f"[AI Assembler] Loaded HVAC template: {hvac_type}.idf ({len(hvac_idf_block)} chars)")
            else:
                print(f"[AI Assembler] WARNING: HVAC template not found at {hvac_template_path}, falling back to ideal_loads")
                fallback_path = os.path.join(hvac_template_dir, "ideal_loads.idf")
                if os.path.exists(fallback_path):
                    with open(fallback_path, "r", encoding="utf-8") as hf:
                        hvac_idf_block = hf.read()
                    hvac_idf_block = hvac_idf_block.replace("{ZONE_NAME}", "ZONE ONE")

            # 7. Stitch it all together
            final_idf = self.base_idf + "\n\n"
            for block in custom_constructions_list:
                final_idf += block + "\n\n"
            for block in extracted_blocks.values():
                final_idf += block + "\n\n"
            
            final_idf += geometry_idf

            # 8. Replace placeholder constructions and thermodynamics inside the geometry and Base
            final_idf = final_idf.replace("{EXTERIOR_WALL_CONSTR}", global_wall)
            final_idf = final_idf.replace("{ROOF_CONSTR}", roof_name)
            final_idf = final_idf.replace("{FLOOR_CONSTR}", global_wall) # Simplified for now
            
            # Inject HVAC system block
            final_idf = final_idf.replace("{HVAC_SYSTEM_BLOCK}", hvac_idf_block)
            
            # Inject generic door construction
            door_constr_block = """
  Material,
    Generic_Door_Material,   !- Name
    Smooth,                  !- Roughness
    0.05,                    !- Thickness {m}
    0.15,                    !- Conductivity {W/m-K}
    600,                     !- Density {kg/m3}
    1000,                    !- Specific Heat {J/kg-K}
    0.9,                     !- Thermal Absorptance
    0.7,                     !- Solar Absorptance
    0.7;                     !- Visible Absorptance

  Construction,
    Generic_Door_Constr,     !- Name
    Generic_Door_Material;   !- Outside Layer
"""
            final_idf = final_idf.replace("{EXTERIOR_DOOR_CONSTR}", "Generic_Door_Constr")
            if "Generic_Door_Constr" in final_idf and "Generic_Door_Material" not in final_idf:
                final_idf += door_constr_block
            
            # Base.idf replaces
            final_idf = final_idf.replace("{PEOPLE_DENSITY}", str(people))
            final_idf = final_idf.replace("{LIGHT_DENSITY}", str(lights))
            final_idf = final_idf.replace("{EQUIP_DENSITY}", str(equip))
            final_idf = final_idf.replace("{INFILTRATION_ACH}", str(infil))
            final_idf = final_idf.replace("{VENTILATION_ACH}", str(vent))
            
            # Setpoints and Windows
            final_idf = final_idf.replace("{HEAT_OCC}", str(heat_occ))
            final_idf = final_idf.replace("{HEAT_UNOCC}", str(heat_unocc))
            final_idf = final_idf.replace("{COOL_OCC}", str(cool_occ))
            final_idf = final_idf.replace("{COOL_UNOCC}", str(cool_unocc))
            final_idf = final_idf.replace("{WINDOW_U_FACTOR}", str(win_u))
            final_idf = final_idf.replace("{WINDOW_SHGC}", str(win_shgc))
            
            # Inject generated schedules
            final_idf = final_idf.replace("{SCHEDULES_BLOCK}", schedules_block)
            
            # Replace schedule name placeholders in People/Lights/Equipment objects
            final_idf = final_idf.replace("{OCCUPANCY_SCH}", "OCCUPANCY_SCH")
            final_idf = final_idf.replace("{LIGHTING_SCH}", "LIGHTING_SCH")
            final_idf = final_idf.replace("{EQUIPMENT_SCH}", "EQUIPMENT_SCH")
            
            if not window_constr:
                window_constr = "Theoretical Glass [167]"
            final_idf = final_idf.replace("{WINDOW_CONSTR}", window_constr)

            return final_idf

        except json.JSONDecodeError as je:
             print(f"[AI] Error parsing JSON from AI output: {je}")
             return f"! Error: AI failed to output valid JSON. Result was: {json_output}"
        except Exception as e:
            print(f"[AI] Error generating IDF: {e}")
            return f"! Analysis Error: {str(e)}"

    def _extract_topology(self, nlp_text, config, model_type):
        system_prompt = (
            "You are an expert EnergyPlus consultant. Your task is to analyze the user's natural language request and output a JSON dictionary extracting the building's zones, layout dimensions, and global variables.\n"
            "CRITICAL RULES:\n"
            "1. OUTPUT FORMAT: Return ONLY valid JSON. No markdown wrappers, no explanations.\n"
            "2. ZONE DETECTION: If the user describes a SINGLE room/zone (e.g., 'a 10x8m office'), set 'is_multizone': false. "
            "If the user describes MULTIPLE rooms/zones, set 'is_multizone': true.\n\n"
            "=== OUTPUT SCHEMA ===\n"
            "Required JSON keys:\n"
            "   - 'is_multizone' (boolean)\n"
            "   - 'zones' (array of zone objects). If is_multizone is false, include exactly one zone. Each zone object has:\n"
            "     - 'name' (string, e.g. 'Office', 'MeetingRoom', 'Lobby')\n"
            "     - 'length' (float, X-axis dimension)\n"
            "     - 'width' (float, Y-axis dimension)\n"
            "     - 'height' (float, Z-axis dimension)\n"
            "     - 'relative_to' (string or null): Name of adjacent zone this one is attached to. Set null for first zone.\n"
            "     - 'direction' (string or null): Side of attachment. Pick: 'North', 'South', 'East', 'West'. Set null for first zone.\n"
            "     - 'roof_type' (string: 'flat' or 'pitched'. Default 'flat')\n"
            "     - 'roof_pitch_height' (float, default 2.0)\n"
            "   - 'people_density' (float, global default: 10.0)\n"
            "   - 'light_density' (float, global default: 10.0)\n"
            "   - 'equipment_density' (float, global default: 10.0)\n"
            "   - 'ventilation_ach' (float, global default: 0.5)\n"
            "   - 'infiltration_ach' (float, global default: 0.5)\n"
            "   - 'hvac_type' (string: 'ideal_loads', 'ptac', 'psz_ac')\n"
            "   - 'heat_set_occ', 'heat_set_unocc', 'cool_set_occ', 'cool_set_unocc' (floats, global setpoints)\n"
            "   - 'window_u_factor', 'window_shgc' (floats, global)\n"
            "   - 'occ_weekday_start', 'occ_weekday_end', 'occ_weekend_start', 'occ_weekend_end' (integers, occupancy schedule)\n"
            "   - 'light_weekday_start', 'light_weekday_end', 'light_weekend_start', 'light_weekend_end' (integers, lighting schedule)\n"
            "   - 'equip_weekday_start', 'equip_weekday_end', 'equip_weekend_start', 'equip_weekend_end' (integers, equipment schedule)\n"
            "   - 'hvac_weekday_start', 'hvac_weekday_end', 'hvac_weekend_start', 'hvac_weekend_end' (integers, HVAC schedule)\n"
        )
        user_prompt = (
            f"USER TASK: {nlp_text}\n"
            f"CONFIG: {json.dumps(config)}\n\n"
            "OUTPUT ONLY VALID JSON:"
        )
        
        if model_type == "openai":
            output = self._call_openai(system_prompt, user_prompt)
        elif model_type == "gemini":
            output = self._call_gemini(system_prompt, user_prompt)
        elif model_type == "huggingface":
            output = self._call_huggingface(system_prompt, user_prompt)
        elif model_type == "ollama":
            output = self._call_ollama(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown model type '{model_type}'")
            
        return output.replace("```json", "").replace("```", "").strip()

    def _extract_zone_details(self, nlp_text, zone_name, construction_menu, raw_materials, window_materials, model_type):
        system_prompt = (
            f"You are an expert EnergyPlus consultant. Analyze the user's prompt and extract the windows, doors, skylights, and construction layers for the zone '{zone_name}' ONLY.\n"
            "CRITICAL RULES:\n"
            "1. OUTPUT FORMAT: Return ONLY valid JSON. No markdown wrappers, no explanations.\n"
            "2. ZERO-HALLUCINATION CONSTRAINT: Do NOT include any custom windows or doors on any walls unless they are explicitly requested for '{zone_name}' in the text. If none are specified, return an empty array for subsurfaces. Do not copy windows/doors from other zones.\n"
            "3. NO-OVERLAP VALIDATION: If a wall has both a door and a window, ensure their offsets do not overlap.\n\n"
            "=== OUTPUT SCHEMA ===\n"
            "Required JSON keys:\n"
            "   - 'wall_layers' (string or array of strings: pick from CONSTRUCTION MENU or ordered list from RAW MATERIAL MENU)\n"
            "   - 'wall_layers_south', 'wall_layers_north', 'wall_layers_east', 'wall_layers_west' (string or array of strings. If not specified, leave null)\n"
            "   - 'roof_layers' (string or array of strings)\n"
            "   - 'window_layers' (string or array of strings)\n"
            "   - 'skylight' (object: {\"width\": float, \"length\": float} or null)\n"
            "   - 'wwr_south', 'wwr_north', 'wwr_east', 'wwr_west' (floats 0-1, default 0.0. Use window-to-wall ratios if custom windows are not specified)\n"
            "   - 'subsurfaces' (array of objects): List of windows and doors explicitly requested for this zone. Empty array [] if none. Each subsurface object has:\n"
            "     - 'type' (string: 'window' or 'door')\n"
            "     - 'wall' (string: 'South', 'North', 'East', or 'West')\n"
            "     - 'width' (float: dimension in meters)\n"
            "     - 'height' (float: dimension in meters)\n"
            "     - 'offset_x' (float: offset distance from reference edge)\n"
            "     - 'ref_x' (string: 'left', 'right', or 'center')\n"
            "     - 'offset_z' (float: offset distance from reference edge)\n"
            "     - 'ref_z' (string: 'bottom', 'top', or 'center')\n"
            "     Note: if \"fix to ground\" -> 'ref_z': \"bottom\", 'offset_z': 0.0. If \"X meters from left edge\" -> 'ref_x': \"left\", 'offset_x': X. If \"X meters from top edge\" -> 'ref_z': \"top\", 'offset_z': X. Otherwise use default offset values.\n"
            "=== CRITICAL DIMENSION RULES ===\n"
            "1. DIMENSION ORDER RULE: All dimensions specified in 'AxB' format (e.g. '1x2.5m door' or '0.8x1.5m window') MUST be parsed as width = A and height = B. NEVER swap them. For example, a 1x2.5m door MUST have width = 1.0 and height = 2.5.\n"
            f"CONSTRUCTION MENU: {construction_menu}\n"
            f"RAW MATERIAL MENU: {raw_materials}\n"
            f"WINDOW MATERIAL MENU: {window_materials}\n"
        )
        user_prompt = (
            f"USER TASK: {nlp_text}\n"
            "OUTPUT ONLY VALID JSON:"
        )
        
        if model_type == "openai":
            output = self._call_openai(system_prompt, user_prompt)
        elif model_type == "gemini":
            output = self._call_gemini(system_prompt, user_prompt)
        elif model_type == "huggingface":
            output = self._call_huggingface(system_prompt, user_prompt)
        elif model_type == "ollama":
            output = self._call_ollama(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown model type '{model_type}'")
            
        return output.replace("```json", "").replace("```", "").strip()

    def _call_openai(self, system, user):
        if not self.openai_client:
            raise ValueError("OpenAI API Key missing or client failed to init.")
            
        response = self.openai_client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content
        return self._sanitize_output(content)

    def _call_gemini(self, system, user):
        if not self.gemini_client:
             raise ValueError("Gemini API Key missing or client failed to init.")
            
        # Gemini (New SDK) uses models.generate_content
        full_prompt = f"{system}\n\n{user}"
        response = self.gemini_client.models.generate_content(
            model='gemini-2.5-flash-lite', 
            contents=full_prompt
        )
        return self._sanitize_output(response.text)

    def _call_huggingface(self, system, user):
        if not self.hf_client:
            raise ValueError("HuggingFace Client missing or API Key not provided.")
            
        try:
            response = self.hf_client.chat.completions.create(
                model="meta-llama/Llama-3.1-8B-Instruct",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                max_tokens=1500,
                temperature=0.2
            )
            content = response.choices[0].message.content
            return self._sanitize_output(content)
        except Exception as e:
            return f"! Analysis Error: HuggingFace API Exception -> {str(e)}"

    def _call_ollama(self, system, user, format=None):
        try:
            import ollama
        except ImportError:
            raise ValueError("Ollama python package is not installed. Please install it in Colab: !pip install ollama")
            
        try:
            # Using gemma3:12b since it is more capable!
            chat_kwargs = {
                "model": 'gemma3:12b', 
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                "options": {"num_ctx": 8192, "num_predict": 4096}
            }
            if format:
                chat_kwargs["format"] = format
                
            response = ollama.chat(**chat_kwargs)
            content = response['message']['content']
            return self._sanitize_output(content)
        except Exception as e:
            return f"! Analysis Error: Ollama Local Exception -> {str(e)}"

    def _resolve_construction(self, layers, prefix, custom_constructions_list, idf_assembler, extracted_blocks):
        if not layers:
            return None
        if isinstance(layers, str):
            return layers
        if isinstance(layers, list) and len(layers) > 0:
            if len(layers) == 1:
                return layers[0]
                
            # Flatten any Constructions into their Materials to avoid EnergyPlus nested construction errors
            flat_layers = []
            for layer in layers:
                c_layers = idf_assembler.get_construction_layers(layer)
                if c_layers:
                    flat_layers.extend(c_layers)
                else:
                    flat_layers.append(layer)
                    
            # Build custom construction
            name = f"Custom_{prefix}_{len(custom_constructions_list) + 1}"
            block = f"Construction,\n  {name},"
            for i, layer in enumerate(flat_layers):
                idf_assembler.resolve_dependencies("Material", layer, extracted_blocks)
                if i == len(flat_layers) - 1:
                    block += f"\n  {layer};"
                else:
                    block += f"\n  {layer},"
            block += "\n"
            custom_constructions_list.append(block)
            return name
        return None

    def _generate_search_keywords(self, nlp_text, model_type):
        """Pass 1: Asks the AI to extract or infer search keywords."""
        system_prompt = (
            "You are a Keyword Extractor for an EnergyPlus RAG system.\n"
            "Analyze the user's prompt about a building and extract a dynamic list of search keywords related to building materials and walls.\n"
            "RULE 1: If the user mentions specific materials (e.g., 'steel', 'wood stud', 'brick'), extract exactly those words.\n"
            "RULE 2: If the prompt is vague (e.g., 'normal building'), infer generic terms: 'standard', 'wood', 'brick', 'insulation'.\n"
            "RULE 3: Return ONLY a comma-separated list of keywords. NO markdown. NO explanations."
        )
        try:
            if model_type == "openai":
                response = self._call_openai(system_prompt, nlp_text)
            elif model_type == "gemini":
                response = self._call_gemini(system_prompt, nlp_text)
            elif model_type == "huggingface":
                response = self._call_huggingface(system_prompt, nlp_text)
            elif model_type == "ollama":
                response = self._call_ollama(system_prompt, nlp_text)
            else:
                return ["office", "wood", "standard"]
            
            keywords = [k.strip() for k in response.split(",") if k.strip()]
            return keywords if keywords else ["office", "wood", "standard"]
        except Exception as e:
            print(f"[AI Planner] Keyword Extraction Failed: {e}")
            return ["office", "wood", "standard"]

    def _sanitize_output(self, text):
        """Removes markdown wrappers if present."""
        clean = text.strip()
        if clean.startswith("```"):
            # Find first newline
            first_newline = clean.find("\n")
            if first_newline != -1:
                clean = clean[first_newline+1:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    def _repair_truncated_json(self, s):
        """Attempts to repair a truncated JSON string and parse it."""
        s = s.strip()
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass

        def close_brackets(prefix):
            open_stack = []
            in_string = False
            escaped = False
            i = 0
            while i < len(prefix):
                c = prefix[i]
                if escaped:
                    escaped = False
                    i += 1
                    continue
                if c == '\\':
                    escaped = True
                    i += 1
                    continue
                if c == '"':
                    in_string = not in_string
                    i += 1
                    continue
                if not in_string:
                    if c == '{' or c == '[':
                        open_stack.append(c)
                    elif c == '}':
                        if open_stack and open_stack[-1] == '{':
                            open_stack.pop()
                    elif c == ']':
                        if open_stack and open_stack[-1] == '[':
                            open_stack.pop()
                i += 1
                
            closure = ""
            if in_string:
                closure += '"'
                
            for item in reversed(open_stack):
                if item == '{':
                    closure += '}'
                elif item == '[':
                    closure += ']'
            return closure

        search_limit = min(len(s), 1500)
        for offset in range(search_limit):
            length = len(s) - offset
            prefix = s[:length]
            closure = close_brackets(prefix)
            candidate = prefix + closure
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
                
        raise ValueError("Could not repair JSON")

    def _assemble_multizone_idf(self, params, config, construction_menu, index_data, idf_assembler, custom_constructions_list, extracted_blocks):
        """
        Assembles a multi-zone IDF from the AI's JSON output.
        Called when is_multizone is True.
        """
        import sys
        sys.path.append(os.path.dirname(__file__))
        import coordinates_calculator

        zones = params.get("zones", [])
        if not zones:
            return "! Error: Multi-zone mode selected but no zones array found in AI output."

        print(f"[AI Assembler MZ] Processing {len(zones)} zones...")

        # --- Global parameters (shared across zones) ---
        heat_occ = params.get("heat_set_occ", 21.0)
        heat_unocc = params.get("heat_set_unocc", 15.0)
        cool_occ = params.get("cool_set_occ", 24.0)
        cool_unocc = params.get("cool_set_unocc", 28.0)
        win_u = params.get("window_u_factor", 3.0)
        win_shgc = params.get("window_shgc", 0.5)

        # Schedule Parsing (global)
        occ_wd_start = params.get("occ_weekday_start", 0)
        occ_wd_end = params.get("occ_weekday_end", 24)
        occ_we_start = params.get("occ_weekend_start", 0)
        occ_we_end = params.get("occ_weekend_end", 24)

        lgt_wd_start = params.get("light_weekday_start", 0)
        lgt_wd_end = params.get("light_weekday_end", 24)
        lgt_we_start = params.get("light_weekend_start", 0)
        lgt_we_end = params.get("light_weekend_end", 24)

        eqp_wd_start = params.get("equip_weekday_start", 0)
        eqp_wd_end = params.get("equip_weekday_end", 24)
        eqp_we_start = params.get("equip_weekend_start", 0)
        eqp_we_end = params.get("equip_weekend_end", 24)

        hvac_wd_start = params.get("hvac_weekday_start", 7)
        hvac_wd_end = params.get("hvac_weekday_end", 18)
        hvac_we_start = params.get("hvac_weekend_start", 7)
        hvac_we_end = params.get("hvac_weekend_end", 18)

        # --- Schedules (same helper as single-zone) ---
        def make_compact_schedule(name, val_off, val_on, wd_s, wd_e, we_s, we_e):
            wd_s = max(0, min(24, int(wd_s if wd_s is not None else 0)))
            wd_e = max(0, min(24, int(wd_e if wd_e is not None else 24)))
            we_s = max(0, min(24, int(we_s if we_s is not None else 0)))
            we_e = max(0, min(24, int(we_e if we_e is not None else 24)))

            def day_lines(start, end):
                if start == 0 and end == 0:
                    return [f"    Until: 24:00, {val_off}"]
                elif start == 0 and end == 24:
                    return [f"    Until: 24:00, {val_on}"]
                else:
                    parts = []
                    if start > 0:
                        parts.append(f"    Until: {start:02d}:00, {val_off}")
                    parts.append(f"    Until: {end:02d}:00, {val_on}")
                    if end < 24:
                        parts.append(f"    Until: 24:00, {val_off}")
                    return parts

            wd_lines = day_lines(wd_s, wd_e)
            we_lines = day_lines(we_s, we_e)

            fields = []
            fields.append(f"    {name}")
            fields.append("    Any Number")
            fields.append("    Through: 12/31")
            fields.append("    For: Weekdays SummerDesignDay WinterDesignDay CustomDay1 CustomDay2")
            fields.extend(wd_lines)
            fields.append("    For: Weekends Holidays AllOtherDays")
            fields.extend(we_lines)

            body = ",\n".join(fields[:-1]) + ",\n" + fields[-1] + ";\n"
            return "\n  Schedule:Compact,\n" + body + "\n"

        schedules_block = ""
        schedules_block += make_compact_schedule("OCCUPANCY_SCH", 0, 1, occ_wd_start, occ_wd_end, occ_we_start, occ_we_end)
        schedules_block += make_compact_schedule("LIGHTING_SCH", 0, 1, lgt_wd_start, lgt_wd_end, lgt_we_start, lgt_we_end)
        schedules_block += make_compact_schedule("EQUIPMENT_SCH", 0, 1, eqp_wd_start, eqp_wd_end, eqp_we_start, eqp_we_end)
        schedules_block += make_compact_schedule("HEATING_SETPOINT_SCH", heat_unocc, heat_occ, hvac_wd_start, hvac_wd_end, hvac_we_start, hvac_we_end)
        schedules_block += make_compact_schedule("COOLING_SETPOINT_SCH", cool_unocc, cool_occ, hvac_wd_start, hvac_wd_end, hvac_we_start, hvac_we_end)

        # --- Step 2: Resolve zone origins from relative layout ---
        zone_origins = coordinates_calculator.resolve_zone_origins(zones)
        print(f"[AI Assembler MZ] Zone origins: {zone_origins}")

        # --- Step 3: Extract and validate material dependencies ---
        default_constr = "Composite 2x4 Wood Stud R11"
        for z in zones:
            w_layers = z.get("wall_layers") or z.get("wall_construction") or default_constr
            w_name = self._resolve_construction(w_layers, f"Wall_{z['name']}", custom_constructions_list, idf_assembler, extracted_blocks)
            if w_name and not w_name.startswith("Custom_"):
                idf_assembler.resolve_dependencies("Construction", w_name, extracted_blocks)
                if f"Construction::{w_name}" not in extracted_blocks and w_name != default_constr:
                    print(f"[AI Assembler MZ] Fallback: Wall '{w_name}' not found, using default.")
                    w_name = default_constr
                    idf_assembler.resolve_dependencies("Construction", default_constr, extracted_blocks)
            z["wall_construction"] = w_name

            r_layers = z.get("roof_layers") or z.get("roof_construction") or default_constr
            r_name = self._resolve_construction(r_layers, f"Roof_{z['name']}", custom_constructions_list, idf_assembler, extracted_blocks)
            if r_name and not r_name.startswith("Custom_"):
                idf_assembler.resolve_dependencies("Construction", r_name, extracted_blocks)
                if f"Construction::{r_name}" not in extracted_blocks and r_name != default_constr:
                    print(f"[AI Assembler MZ] Fallback: Roof '{r_name}' not found, using default.")
                    r_name = default_constr
                    idf_assembler.resolve_dependencies("Construction", default_constr, extracted_blocks)
            z["roof_construction"] = r_name
            
            win_layers = z.get("window_layers") or z.get("window_construction")
            win_name = None
            if win_layers:
                win_name = self._resolve_construction(win_layers, f"Window_{z['name']}", custom_constructions_list, idf_assembler, extracted_blocks)
                if win_name and not win_name.startswith("Custom_"):
                    idf_assembler.resolve_dependencies("Construction", win_name, extracted_blocks)
            z["window_construction"] = win_name

        # --- Step 4: Generate multi-zone geometry with adjacencies ---
        geometry_idf, adjacency_info = coordinates_calculator.generate_multizone_geometry(zones, zone_origins)

        # --- Step 5: Load HVAC templates for each zone ---
        hvac_idf_block = ""
        hvac_template_dir = os.path.join(os.path.dirname(__file__), "..", "idf_templates", "hvac")
        for z in zones:
            zone_hvac = z.get("hvac_type") or params.get("hvac_type") or "ideal_loads"
            allowed_hvac = ["ideal_loads", "ptac", "psz_ac"]
            if zone_hvac not in allowed_hvac:
                zone_hvac = "ideal_loads"

            hvac_template_path = os.path.join(hvac_template_dir, f"{zone_hvac}.idf")
            if os.path.exists(hvac_template_path):
                with open(hvac_template_path, "r", encoding="utf-8") as hf:
                    zone_hvac_block = hf.read()
                zone_hvac_block = zone_hvac_block.replace("{ZONE_NAME}", z["name"])
                hvac_idf_block += zone_hvac_block + "\n"
            else:
                fallback_path = os.path.join(hvac_template_dir, "ideal_loads.idf")
                if os.path.exists(fallback_path):
                    with open(fallback_path, "r", encoding="utf-8") as hf:
                        zone_hvac_block = hf.read()
                    zone_hvac_block = zone_hvac_block.replace("{ZONE_NAME}", z["name"])
                    hvac_idf_block += zone_hvac_block + "\n"

        # --- Step 6: Generate per-zone People/Lights/Equipment/Infiltration/Ventilation/Thermostat ---
        zone_objects_block = ""
        for z in zones:
            zn = z["name"]
            z_people = z.get("people_density") if z.get("people_density") is not None else params.get("people_density", 10.0)
            z_lights = z.get("light_density") if z.get("light_density") is not None else params.get("light_density", 10.0)
            z_equip = z.get("equipment_density") if z.get("equipment_density") is not None else params.get("equipment_density", 10.0)
            z_infil = z.get("infiltration_ach") if z.get("infiltration_ach") is not None else params.get("infiltration_ach", 0.5)
            z_vent = z.get("ventilation_ach") if z.get("ventilation_ach") is not None else params.get("ventilation_ach", 0.5)

            zone_objects_block += f"""
  People,
    {zn}_PEOPLE,              !- Name
    {zn},                     !- Zone or ZoneList Name
    OCCUPANCY_SCH,            !- Number of People Schedule Name
    Area/Person,              !- Number of People Calculation Method
    ,                         !- Number of People
    ,                         !- People per Zone Floor Area {{person/m2}}
    {z_people},               !- Zone Floor Area per Person {{m2/person}}
    0.3,                      !- Fraction Radiant
    ,                         !- Sensible Heat Fraction
    ACTIVITY_SCH;             !- Activity Level Schedule Name

  Lights,
    {zn}_LIGHTS,              !- Name
    {zn},                     !- Zone or ZoneList Name
    LIGHTING_SCH,             !- Schedule Name
    Watts/Area,               !- Design Level Calculation Method
    ,                         !- Lighting Level {{W}}
    {z_lights},               !- Watts per Zone Floor Area {{W/m2}}
    ,                         !- Watts per Person {{W/person}}
    0,                        !- Return Air Fraction
    0.42,                     !- Fraction Radiant
    0.18,                     !- Fraction Visible
    1;                        !- Fraction Replaceable

  ElectricEquipment,
    {zn}_EQUIP,               !- Name
    {zn},                     !- Zone or ZoneList Name
    EQUIPMENT_SCH,            !- Schedule Name
    Watts/Area,               !- Design Level Calculation Method
    ,                         !- Design Level {{W}}
    {z_equip},                !- Watts per Zone Floor Area {{W/m2}}
    ,                         !- Watts per Person {{W/person}}
    0,                        !- Fraction Latent
    0.3,                      !- Fraction Radiant
    0,                        !- Fraction Lost
    General;                  !- End-Use Subcategory

  ZoneInfiltration:DesignFlowRate,
    {zn}_Infiltration,        !- Name
    {zn},                     !- Zone or ZoneList Name
    ALWAYS_ON,                !- Schedule Name
    AirChanges/Hour,          !- Design Flow Rate Calculation Method
    ,                         !- Design Flow Rate {{m3/s}}
    ,                         !- Flow per Zone Floor Area {{m3/s-m2}}
    ,                         !- Flow per Exterior Surface Area {{m3/s-m2}}
    {z_infil};                !- Air Changes per Hour {{1/hr}}

  DesignSpecification:OutdoorAir,
    {zn}_OA,                  !- Name
    AirChanges/Hour,          !- Outdoor Air Method
    0,                        !- Outdoor Air Flow per Person {{m3/s-person}}
    0,                        !- Outdoor Air Flow per Zone Floor Area {{m3/s-m2}}
    0,                        !- Outdoor Air Flow per Zone {{m3/s}}
    {z_vent};                 !- Outdoor Air Flow Air Changes per Hour {{1/hr}}

  ZoneControl:Thermostat,
    {zn}_Thermostat,          !- Name
    {zn},                     !- Zone or ZoneList Name
    ALWAYS 4,                 !- Control Type Schedule Name
    ThermostatSetpoint:DualSetpoint,  !- Control 1 Object Type
    {zn}_DualSP;              !- Control 1 Name

  ThermostatSetpoint:DualSetpoint,
    {zn}_DualSP,              !- Name
    HEATING_SETPOINT_SCH,     !- Heating Setpoint Temperature Schedule Name
    COOLING_SETPOINT_SCH;     !- Cooling Setpoint Temperature Schedule Name
"""

        # --- Step 7: Stitch together the final IDF ---
        # Use base template but strip the single-zone People/Lights/Equipment/Infiltration/Ventilation/Thermostat
        # since we generate per-zone versions above
        base_idf = self.base_idf
        # Remove single-zone objects from Base.idf (they are replaced by per-zone ones)
        # We do this by replacing them with empty strings
        import re
        # Remove People object
        base_idf = re.sub(r'\n\s*People,.*?;', '', base_idf, flags=re.DOTALL)
        # Remove Lights object
        base_idf = re.sub(r'\n\s*Lights,.*?;', '', base_idf, flags=re.DOTALL)
        # Remove ElectricEquipment object
        base_idf = re.sub(r'\n\s*ElectricEquipment,.*?;', '', base_idf, flags=re.DOTALL)
        # Remove ZoneInfiltration
        base_idf = re.sub(r'\n\s*ZoneInfiltration:DesignFlowRate,.*?;', '', base_idf, flags=re.DOTALL)
        # Remove DesignSpecification:OutdoorAir
        base_idf = re.sub(r'\n\s*DesignSpecification:OutdoorAir,.*?;', '', base_idf, flags=re.DOTALL)
        # Remove ZoneControl:Thermostat
        base_idf = re.sub(r'\n\s*ZoneControl:Thermostat,.*?;', '', base_idf, flags=re.DOTALL)
        # Remove ThermostatSetpoint:DualSetpoint
        base_idf = re.sub(r'\n\s*ThermostatSetpoint:DualSetpoint,.*?;', '', base_idf, flags=re.DOTALL)

        final_idf = base_idf + "\n\n"
        for block in custom_constructions_list:
            final_idf += block + "\n\n"
        for block in extracted_blocks.values():
            final_idf += block + "\n\n"

        final_idf += geometry_idf + "\n\n"
        final_idf += zone_objects_block + "\n\n"

        # Replace HVAC placeholder
        final_idf = final_idf.replace("{HVAC_SYSTEM_BLOCK}", hvac_idf_block)

        # Inject generic door construction if needed
        door_constr_block = """
  Material,
    Generic_Door_Material,   !- Name
    Smooth,                  !- Roughness
    0.05,                    !- Thickness {m}
    0.15,                    !- Conductivity {W/m-K}
    600,                     !- Density {kg/m3}
    1000,                    !- Specific Heat {J/kg-K}
    0.9,                     !- Thermal Absorptance
    0.7,                     !- Solar Absorptance
    0.7;                     !- Visible Absorptance

  Construction,
    Generic_Door_Constr,     !- Name
    Generic_Door_Material;   !- Outside Layer
"""
        final_idf = final_idf.replace("{EXTERIOR_DOOR_CONSTR}", "Generic_Door_Constr")
        if "Generic_Door_Constr" in final_idf and "Generic_Door_Material" not in final_idf:
            final_idf += door_constr_block

        # Global replacements
        global_wall = zones[0].get("wall_construction") or "Composite 2x4 Wood Stud R11"
        roof_name = zones[0].get("roof_construction") or "Composite 2x4 Wood Stud R11"
        window_name = zones[0].get("window_construction") or "Theoretical Glass [167]"
        final_idf = final_idf.replace("{EXTERIOR_WALL_CONSTR}", global_wall)
        final_idf = final_idf.replace("{ROOF_CONSTR}", roof_name)
        final_idf = final_idf.replace("{FLOOR_CONSTR}", global_wall)
        final_idf = final_idf.replace("{WINDOW_CONSTR}", window_name)

        final_idf = final_idf.replace("{WINDOW_U_FACTOR}", str(win_u))
        final_idf = final_idf.replace("{WINDOW_SHGC}", str(win_shgc))

        final_idf = final_idf.replace("{SCHEDULES_BLOCK}", schedules_block)
        final_idf = final_idf.replace("{OCCUPANCY_SCH}", "OCCUPANCY_SCH")
        final_idf = final_idf.replace("{LIGHTING_SCH}", "LIGHTING_SCH")
        final_idf = final_idf.replace("{EQUIPMENT_SCH}", "EQUIPMENT_SCH")

        # Remove any remaining single-zone placeholders that are now unused
        final_idf = final_idf.replace("{PEOPLE_DENSITY}", "10.0")
        final_idf = final_idf.replace("{LIGHT_DENSITY}", "10.0")
        final_idf = final_idf.replace("{EQUIP_DENSITY}", "10.0")
        final_idf = final_idf.replace("{INFILTRATION_ACH}", "0.5")
        final_idf = final_idf.replace("{VENTILATION_ACH}", "0.5")
        final_idf = final_idf.replace("{HEAT_OCC}", str(heat_occ))
        final_idf = final_idf.replace("{HEAT_UNOCC}", str(heat_unocc))
        final_idf = final_idf.replace("{COOL_OCC}", str(cool_occ))
        final_idf = final_idf.replace("{COOL_UNOCC}", str(cool_unocc))

        print(f"[AI Assembler MZ] Final IDF: {len(final_idf)} chars, {len(zones)} zones")
        return final_idf

    def test_connections(self, check_openai=True, check_gemini=True, check_hf=True):
        """Tests connectivity to APIs based on flags."""
        results = {"openai": False, "gemini": False, "hf": False, "details": ""}
        
        # Test OpenAI
        if check_openai:
            if self.openai_client:
                try:
                    self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo", messages=[{"role": "user", "content": "hi"}], max_tokens=1
                    )
                    results["openai"] = True
                except Exception as e:
                    results["details"] += f"OpenAI Fail: {str(e)}; "
            else:
                 results["details"] += "OpenAI Client Missing; "
        else:
             results["details"] += "OpenAI Skipped; "
        
        # Test Gemini
        if check_gemini:
            if self.gemini_client:
                try:
                    self.gemini_client.models.generate_content(
                        model='gemini-2.5-flash-lite', contents="hi"
                    )
                    results["gemini"] = True
                except Exception as e:
                    results["details"] += f"Gemini Fail: {str(e)}; "
            else:
                 results["details"] += "Gemini Client Missing; "
        else:
             results["details"] += "Gemini Skipped; "
             
        # Test HuggingFace
        if check_hf:
            if self.hf_client:
                try:
                    self.hf_client.chat.completions.create(
                        model="meta-llama/Llama-3.1-8B-Instruct",
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=1
                    )
                    print("[AI] HuggingFace Test: ✅ Success")
                    results["hf"] = True
                except Exception as e:
                    print(f"[AI] HuggingFace Test Exception ❌: {str(e)}")
                    results["details"] += f"HF Exception: {str(e)}; "
            else:
                print("[AI] HuggingFace Test ❌: Missing API Key or Client Init Failed.")
                results["details"] += "HF Client Missing; "
        else:
            results["details"] += "HF Skipped; "
                
        return results

