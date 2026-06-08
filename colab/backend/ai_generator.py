import os
import json
import openai
from google import genai 
from huggingface_hub import InferenceClient

class AIPipelines:
    def __init__(self, secrets_path="secrets.json", template_path="templates/Base.idf"):
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

        # 1. Load the Menu
        import sys
        # ensure we can import from backend dir
        sys.path.append(os.path.dirname(__file__))
        import geometry_util
        import idf_extractor

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

        except Exception as e:
            print(f"Warning: Could not load index.json or RAG failed: {e}")
            construction_menu = ["Composite 2x4 Wood Stud R11"]

        # 2. Construct Prompt for JSON
        weather_file = config.get('weather_file', 'Unknown')
        system_prompt = (
            "You are an expert EnergyPlus consultant integrating modular components. "
            "Your task is to analyze the user's natural language request and output a JSON dictionary containing the building parameters.\n"
            "CRITICAL RULES:\n"
            "1. OUTPUT FORMAT: Return ONLY valid JSON. No markdown wrappers, no explanations.\n"
            "2. ZONE DETECTION: If the user describes a SINGLE room/zone (e.g., 'a 10x8m office'), set 'is_multizone': false and return the SINGLE-ZONE schema. "
            "If the user describes MULTIPLE rooms/zones (e.g., 'a living room with a bedroom to the north'), set 'is_multizone': true and return the MULTI-ZONE schema.\n\n"
            "=== SINGLE-ZONE SCHEMA (is_multizone: false) ===\n"
            "Required JSON keys:\n"
            "   - 'is_multizone' (boolean, false)\n"
            "   - 'length' (float), 'width' (float), 'height' (float)\n"
            "   - 'wall_construction' (string, default global wall). 'wall_constr_south', 'wall_constr_north', 'wall_constr_east', 'wall_constr_west' (strings, specific wall constructions. Pick EXACTLY from menu. If not specified, leave empty or same as global)\n"
            "   - 'roof_construction' (string)\n"
            "   - 'wwr_south', 'wwr_north', 'wwr_east', 'wwr_west' (floats between 0 and 1, Window-to-Wall Ratios for each face. Default 0.0. If user gives a single global WWR, set all 4 to that value. If they specify certain walls, apply only to those and set others to 0.0.)\n"
            "   - 'window_south', 'window_north', 'window_east', 'window_west' (objects for custom windows overriding WWR. Schema: {\"width\": float, \"height\": float, \"offset_x\": float, \"ref_x\": \"left\"|\"right\"|\"center\", \"offset_z\": float, \"ref_z\": \"bottom\"|\"top\"|\"center\"} or null. Default null)\n"
            "   - 'door_south', 'door_north', 'door_east', 'door_west' (objects for custom doors. Schema: {\"width\": float, \"height\": float, \"offset_x\": float, \"ref_x\": \"left\"|\"right\"|\"center\", \"offset_z\": float, \"ref_z\": \"bottom\"|\"top\"|\"center\"} or null. Default null)\n"
            "   - 'people_density' (float, m2/person. Default 10.0)\n"
            "   - 'light_density' (float, W/m2. Default 10.0)\n"
            "   - 'equipment_density' (float, W/m2. Default 10.0)\n"
            "   - 'ventilation_ach' (float. Default 0.5)\n"
            "   - 'infiltration_ach' (float. Default 0.5)\n"
            "   - 'heat_set_occ' (float, Celsius. Default 21.0), 'heat_set_unocc' (float, Celsius. Default 15.0)\n"
            "   - 'cool_set_occ' (float, Celsius. Default 24.0), 'cool_set_unocc' (float, Celsius. Default 28.0)\n"
            "   - 'window_u_factor' (float. Default 3.0), 'window_shgc' (float. Default 0.5)\n"
            "   - 'occ_weekday_start', 'occ_weekday_end', 'occ_weekend_start', 'occ_weekend_end' (integers 0-24 for occupancy. Default 0, 24, 0, 24. If closed on weekends, set weekend start and end to 0)\n"
            "   - 'light_weekday_start', 'light_weekday_end', 'light_weekend_start', 'light_weekend_end' (integers 0-24 for lights. Default 0, 24, 0, 24)\n"
            "   - 'equip_weekday_start', 'equip_weekday_end', 'equip_weekend_start', 'equip_weekend_end' (integers 0-24 for equipment. Default 0, 24, 0, 24)\n"
            "   - 'hvac_weekday_start', 'hvac_weekday_end', 'hvac_weekend_start', 'hvac_weekend_end' (integers 0-24 for HVAC. Default 7, 18, 7, 18)\n"
            "   - 'hvac_type' (string): The HVAC system type. Pick from: 'ideal_loads', 'ptac', 'psz_ac'.\n"
            "     - 'ideal_loads': Simplified perfect system, best for envelope studies (DEFAULT if user doesn't mention HVAC).\n"
            "     - 'ptac': Packaged Terminal Air Conditioner with DX cooling and electric heating. Best for hotels, small rooms, apartments.\n"
            "     - 'psz_ac': Packaged Single Zone AC with gas furnace heating and DX cooling. Best for retail, small commercial, warehouses.\n\n"
            "=== MULTI-ZONE SCHEMA (is_multizone: true) ===\n"
            "Required JSON keys:\n"
            "   - 'is_multizone' (boolean, true)\n"
            "   - 'zones' (array of zone objects). Each zone object has:\n"
            "     - 'name' (string, short snake_case name e.g. 'LivingRoom', 'Bedroom')\n"
            "     - 'length' (float, X-axis extent in meters)\n"
            "     - 'width' (float, Y-axis extent in meters)\n"
            "     - 'height' (float, Z-axis extent in meters)\n"
            "     - 'relative_to' (string or null): name of the zone this one is attached to. null for the FIRST/anchor zone.\n"
            "     - 'direction' (string or null): Which wall of 'relative_to' this zone attaches to. Pick from: 'North', 'South', 'East', 'West'. null for anchor zone.\n"
            "     - 'wall_construction' (string, from menu)\n"
            "     - 'roof_construction' (string, from menu)\n"
            "     - 'wwr_south', 'wwr_north', 'wwr_east', 'wwr_west' (floats 0-1. Default 0.0)\n"
            "     - 'window_south', 'window_north', 'window_east', 'window_west' (custom window objects or null)\n"
            "     - 'door_south', 'door_north', 'door_east', 'door_west' (custom door objects or null)\n"
            "     - 'people_density' (float, m2/person. Default 10.0)\n"
            "     - 'light_density' (float, W/m2. Default 10.0)\n"
            "     - 'equipment_density' (float, W/m2. Default 10.0)\n"
            "     - 'ventilation_ach' (float. Default 0.5)\n"
            "     - 'infiltration_ach' (float. Default 0.5)\n"
            "     - 'hvac_type' (string): 'ideal_loads', 'ptac', or 'psz_ac'. Default 'ideal_loads'.\n"
            "     - CRITICAL: DO NOT include any schedules, setpoints, window_u_factor, or window_shgc inside individual zone objects! Those are global root-level keys only. Repeating them inside zones will cause output truncation.\n"
            "   - 'heat_set_occ', 'heat_set_unocc', 'cool_set_occ', 'cool_set_unocc' (floats, global setpoints shared across all zones)\n"
            "   - 'window_u_factor', 'window_shgc' (floats, global)\n"
            "   - 'occ_weekday_start', 'occ_weekday_end', 'occ_weekend_start', 'occ_weekend_end' (integers, global occupancy schedule)\n"
            "   - 'light_weekday_start', 'light_weekday_end', 'light_weekend_start', 'light_weekend_end' (integers, global light schedule)\n"
            "   - 'equip_weekday_start', 'equip_weekday_end', 'equip_weekend_start', 'equip_weekend_end' (integers, global equipment schedule)\n"
            "   - 'hvac_weekday_start', 'hvac_weekday_end', 'hvac_weekend_start', 'hvac_weekend_end' (integers, global hvac schedule)\n\n"
            "IMPORTANT MULTI-ZONE RULES:\n"
            "   - The FIRST zone in the array is the ANCHOR zone (relative_to=null, direction=null).\n"
            "   - All subsequent zones MUST reference an existing zone by name in 'relative_to'.\n"
            "   - Adjacent zones share a wall. The shared dimension MUST match (e.g., if Bedroom is North of LivingRoom, both must have the same 'length').\n"
            "   - DO NOT compute coordinates. Python will compute all coordinates from relative_to and direction.\n"
            "   - CRITICAL: DO NOT duplicate/repeat schedule or setpoint fields (like occ_weekday_start, heat_set_occ, window_u_factor, etc.) inside the zone objects. Keep them strictly at the global root level only.\n\n"
            "3. For the construction keys, you MUST pick the closest matching name from this exact menu array:\n"
            f"{construction_menu}\n"
        )

        user_prompt = (
            f"USER TASK: {nlp_text}\n"
            f"CONFIG: {json.dumps(config)}\n\n"
            "OUTPUT ONLY VALID JSON:"
        )

        # 3. Call AI
        try:
            if model_type == "openai":
                json_output = self._call_openai(system_prompt, user_prompt)
            elif model_type == "gemini":
                json_output = self._call_gemini(system_prompt, user_prompt)
            elif model_type == "huggingface":
                json_output = self._call_huggingface(system_prompt, user_prompt)
            elif model_type == "ollama":
                json_output = self._call_ollama(system_prompt, user_prompt)
            else:
                return f"! Error: Unknown model type '{model_type}'"
            
            # Clean possible markdown block
            json_output = json_output.replace("```json", "").replace("```", "").strip()
            
            # 4. Parse AI Parameters
            try:
                params = json.loads(json_output)
            except json.JSONDecodeError as je:
                print(f"[AI] Initial JSON parse failed: {je}. Attempting repair...")
                try:
                    params = self._repair_truncated_json(json_output)
                    print("[AI] JSON successfully repaired and parsed!")
                except Exception as re:
                    print(f"[AI] Repair failed: {re}")
                    raise je
            
            # ========== MULTI-ZONE vs SINGLE-ZONE ROUTER ==========
            is_multizone = params.get("is_multizone", False)
            
            if is_multizone:
                print("[AI Assembler] *** MULTI-ZONE mode detected ***")
                return self._assemble_multizone_idf(params, config, construction_menu, index_data, idf_extractor)
            
            # ========== SINGLE-ZONE PATH (existing, untouched) ==========
            print("[AI Assembler] Single-zone mode")
            L = params.get("length", 10.0)
            W = params.get("width", 10.0)
            H = params.get("height", 3.0)
            # Wall and Roof Parsing
            global_wall = params.get("wall_construction", "Composite 2x4 Wood Stud R11")
            wall_s = params.get("wall_constr_south", global_wall) or global_wall
            wall_n = params.get("wall_constr_north", global_wall) or global_wall
            wall_e = params.get("wall_constr_east", global_wall) or global_wall
            wall_w = params.get("wall_constr_west", global_wall) or global_wall
            
            roof_name = params.get("roof_construction", "Composite 2x4 Wood Stud R11")
            
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

            # 5. Extract and Validate Dependencies
            extracted_blocks = {}
            default_constr = "Composite 2x4 Wood Stud R11"

            # Validate walls
            idf_extractor.resolve_dependencies("Construction", wall_s, extracted_blocks)
            if f"Construction::{wall_s}" not in extracted_blocks and wall_s != default_constr:
                print(f"[AI Assembler] Fallback: Wall South '{wall_s}' not found, using default.")
                wall_s = default_constr
                idf_extractor.resolve_dependencies("Construction", default_constr, extracted_blocks)
                
            idf_extractor.resolve_dependencies("Construction", wall_n, extracted_blocks)
            if f"Construction::{wall_n}" not in extracted_blocks and wall_n != default_constr:
                print(f"[AI Assembler] Fallback: Wall North '{wall_n}' not found, using default.")
                wall_n = default_constr
                idf_extractor.resolve_dependencies("Construction", default_constr, extracted_blocks)
                
            idf_extractor.resolve_dependencies("Construction", wall_e, extracted_blocks)
            if f"Construction::{wall_e}" not in extracted_blocks and wall_e != default_constr:
                print(f"[AI Assembler] Fallback: Wall East '{wall_e}' not found, using default.")
                wall_e = default_constr
                idf_extractor.resolve_dependencies("Construction", default_constr, extracted_blocks)
                
            idf_extractor.resolve_dependencies("Construction", wall_w, extracted_blocks)
            if f"Construction::{wall_w}" not in extracted_blocks and wall_w != default_constr:
                print(f"[AI Assembler] Fallback: Wall West '{wall_w}' not found, using default.")
                wall_w = default_constr
                idf_extractor.resolve_dependencies("Construction", default_constr, extracted_blocks)

            idf_extractor.resolve_dependencies("Construction", roof_name, extracted_blocks)
            if f"Construction::{roof_name}" not in extracted_blocks and roof_name != default_constr:
                print(f"[AI Assembler] Fallback: Roof '{roof_name}' not found, using default.")
                roof_name = default_constr
                idf_extractor.resolve_dependencies("Construction", default_constr, extracted_blocks)

            idf_extractor.resolve_dependencies("Construction", global_wall, extracted_blocks)
            if f"Construction::{global_wall}" not in extracted_blocks and global_wall != default_constr:
                global_wall = default_constr
                idf_extractor.resolve_dependencies("Construction", default_constr, extracted_blocks)

            # 6. Build Geometry (Now passing directional WWRs, Materials, and custom Windows/Doors)
            geometry_idf = geometry_util.generate_zone_geometry(
                L, W, H, 
                wwr_s, wwr_n, wwr_e, wwr_w,
                wall_s, wall_n, wall_e, wall_w,
                door_s, door_n, door_e, door_w,
                window_s, window_n, window_e, window_w
            )

            # 6.5 Load HVAC Template
            hvac_idf_block = ""
            hvac_template_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "hvac")
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
            
            final_idf = final_idf.replace("{WINDOW_CONSTR}", "Theoretical Glass [167]")

            return final_idf

        except json.JSONDecodeError as je:
             print(f"[AI] Error parsing JSON from AI output: {je}")
             return f"! Error: AI failed to output valid JSON. Result was: {json_output}"
        except Exception as e:
            print(f"[AI] Error generating IDF: {e}")
            return f"! Analysis Error: {str(e)}"

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

    def _call_ollama(self, system, user):
        try:
            import ollama
        except ImportError:
            raise ValueError("Ollama python package is not installed. Please install it in Colab: !pip install ollama")
            
        try:
            # Using gemma3:4b since it successfully downloaded to your drive!
            response = ollama.chat(
                model='gemma3:4b', 
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                options={"num_ctx": 8192, "num_predict": 4096}
            )
            content = response['message']['content']
            return self._sanitize_output(content)
        except Exception as e:
            return f"! Analysis Error: Ollama Local Exception -> {str(e)}"

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

    def _assemble_multizone_idf(self, params, config, construction_menu, index_data, idf_extractor):
        """
        Assembles a multi-zone IDF from the AI's JSON output.
        Called when is_multizone is True.
        """
        import sys
        sys.path.append(os.path.dirname(__file__))
        import geometry_util

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
        zone_origins = geometry_util.resolve_zone_origins(zones)
        print(f"[AI Assembler MZ] Zone origins: {zone_origins}")

        # --- Step 3: Extract and validate material dependencies ---
        extracted_blocks = {}
        default_constr = "Composite 2x4 Wood Stud R11"
        for z in zones:
            w_name = z.get("wall_construction") or default_constr
            idf_extractor.resolve_dependencies("Construction", w_name, extracted_blocks)
            if f"Construction::{w_name}" not in extracted_blocks and w_name != default_constr:
                print(f"[AI Assembler MZ] Fallback: Wall '{w_name}' not found, using default.")
                z["wall_construction"] = default_constr
                idf_extractor.resolve_dependencies("Construction", default_constr, extracted_blocks)

            r_name = z.get("roof_construction") or default_constr
            idf_extractor.resolve_dependencies("Construction", r_name, extracted_blocks)
            if f"Construction::{r_name}" not in extracted_blocks and r_name != default_constr:
                print(f"[AI Assembler MZ] Fallback: Roof '{r_name}' not found, using default.")
                z["roof_construction"] = default_constr
                idf_extractor.resolve_dependencies("Construction", default_constr, extracted_blocks)

        # --- Step 4: Generate multi-zone geometry with adjacencies ---
        geometry_idf, adjacency_info = geometry_util.generate_multizone_geometry(zones, zone_origins)

        # --- Step 5: Load HVAC templates for each zone ---
        hvac_idf_block = ""
        hvac_template_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "hvac")
        for z in zones:
            zone_hvac = z.get("hvac_type", "ideal_loads")
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
            z_people = z.get("people_density", 10.0)
            z_lights = z.get("light_density", 10.0)
            z_equip = z.get("equipment_density", 10.0)
            z_infil = z.get("infiltration_ach", 0.5)
            z_vent = z.get("ventilation_ach", 0.5)

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
        final_idf = final_idf.replace("{EXTERIOR_WALL_CONSTR}", global_wall)
        final_idf = final_idf.replace("{ROOF_CONSTR}", roof_name)
        final_idf = final_idf.replace("{FLOOR_CONSTR}", global_wall)
        final_idf = final_idf.replace("{WINDOW_CONSTR}", "Theoretical Glass [167]")

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

