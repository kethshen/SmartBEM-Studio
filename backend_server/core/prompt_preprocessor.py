import os

class PromptPreprocessor:
    def __init__(self, ai_pipelines_instance=None):
        self.ai_pipelines = ai_pipelines_instance

    def restructure_prompt(self, raw_prompt, model_type="ollama"):
        """
        Translates raw natural language descriptions into the optimized key-value/XML-style template.
        """
        if "[GLOBAL SETTINGS]" in raw_prompt and "<Zone:" in raw_prompt:
            return raw_prompt # Already structured

        system_prompt = (
            "You are a helpful assistant specialized in energy modeling prompts for SmartBEM-Studio.\n"
            "Your task is to rewrite the user's messy, natural language building description into a clean, "
            "structured, optimized format that local LLMs can read without attention-bleed or dimension errors.\n\n"
            "=== STRUCTURE RULES ===\n"
            "1. Output ONLY the restructured prompt description. Do not add conversational intro/outro, markdown explanations, or headers outside the structure.\n"
            "2. Start with a brief statement: 'Simulate a building with the following layout and thermal configurations.' or 'Simulate a multi-zone building...'\n"
            "3. Provide a '[GLOBAL SETTINGS]' block with key-value pairs for all global properties: \n"
            "   - occupancy_rate, lighting_level, equipment_power, ventilation_ach, infiltration_ach, hvac_system.\n"
            "   - schedules (occupancy_schedule, lighting_schedule, equipment_schedule, hvac_schedule) using integer keys (e.g. occ_weekday_start=9, occ_weekday_end=17, occ_weekend_start=0, occ_weekend_end=0).\n"
            "   - thermostat_setpoints (heat_set_occ, heat_set_unocc, cool_set_occ, cool_set_unocc).\n"
            "   - window_properties (window_u_factor, window_shgc).\n"
            "4. For each zone/room, wrap it inside '<Zone: Name> ... </Zone: Name>' tags. Inside each zone block include:\n"
            "   - geometry: length=X.XX, width=Y.YY, height=Z.ZZ\n"
            "   - relative_position: anchor (origin at 0,0,0) [for first zone] or 'attached to [Direction] wall of [ZoneName]' [for adjacent zones].\n"
            "   - roof: flat or 'pitched, gable_height=H.HH, skylight=...' (specify skylight width/height explicitly if present).\n"
            "   - wall_constructions: List the exact layer names for each cardinal direction (North, South, East, West). Do NOT use phrases like 'other walls out of Y'. Instead, list all 4 directions individually.\n"
            "   - floor_construction: [material or construction name] (optional, include ONLY if the user explicitly mentions a floor material for this zone. E.g. 'Heavy Floor', 'Light Floor', 'M15 200mm heavyweight concrete').\n"
            "   - hvac_system: [HVAC type] (optional, include ONLY if this zone uses a different HVAC system than the global hvac_system).\n"
            "   - subsurfaces: List every window, door, or skylight explicitly as key-value pairs (type, wall, size: W.Wm wide x H.Hm high, offset_x: X.Xm from left edge, offset_z: Z.Zm from top/bottom edge).\n\n"
            "=== ROBUSTNESS RULES FOR MISSING/EXTRA DATA ===\n"
            "- MISSING GLOBAL SETTINGS: If schedules, HVAC system, setpoints, or ACH rates are not specified, omit them from '[GLOBAL SETTINGS]' or use sensible defaults: \n"
            "  - default occupancy_rate = 15.0 m2/people\n"
            "  - default lighting_level = 8.0 W/m2\n"
            "  - default equipment_power = 10.0 W/m2\n"
            "  - default HVAC system = ideal_loads\n"
            "  - default schedules: weekday run 8-18 (8am to 6pm), weekends closed (0-0)\n"
            "- MISSING ZONE DETAILS: If specific wall constructions are not mentioned, set them to 'Medium Exterior Wall'. If no floor material is mentioned, omit floor_construction (the engine will use a sensible default). If no subsurfaces are specified, write 'subsurfaces: []'.\n"
            "- ZONE HVAC DEFAULT: If a zone uses the global HVAC system, do NOT list hvac_system inside that <Zone> block. Only list it if the zone overrides the global choice.\n"
            "- EXTRA DETAILS: If the user provides extra details (e.g., thermal mass, specific occupancy profiles, shading details, internal heat source locations), do not discard them. Cleanly list them as additional key-values in '[GLOBAL SETTINGS]' or under the corresponding '<Zone>' block.\n"
            "- HVAC SYSTEM MAPPING: Use ONLY these exact strings for hvac_system: 'ideal_loads' (default, simplified), 'split_ac' (split AC / mini-split / wall AC / window AC / residential inverter AC), 'ptac' (packaged terminal AC / hotel AC / through-wall unit), 'psz_ac' (packaged rooftop unit / heat pump). If the user does not mention HVAC, use 'ideal_loads'.\n\n"
            "=== TEMPLATE EXAMPLES ===\n"
            "Refer to the structure and format of these examples to rewrite any incoming request:\n\n"
            "--- Example 1: Multi-Zone Building ---\n"
            "User: Simulate a building with three zones: an office, a meeting room, a lobby. The office is 6.00 meters long, 8.00 meters wide, and 4.00 meters high. The meeting room is attached to the North wall of the office. The meeting room is 6.00 meters long, 4.00 meters wide, and 4.00 meters high. The lobby is attached to the East wall of the office. The lobby is 5.00 meters long, 8.00 meters wide, and 4.00 meters high. For the office: place a 1.5x2m window on the South wall 2m from left edge, 1m from top edge. Make the South wall out of 'M01 100mm brick' and 'I02 50mm insulation board' and the other walls out of 'Medium Exterior Wall'. Occupancy rate is 30 m2/people. Global system is a packaged AC (psz_ac), but the meeting room uses a split AC (split_ac). People in building 9am to 5pm weekdays, closed on weekends. Lights 8am to 6pm, equipment 24/7.\n"
            "Output:\n"
            "Simulate a multi-zone building with the following layout and thermal configurations.\n\n"
            "[GLOBAL SETTINGS]\n"
            "- occupancy_rate: 30.00 m2/people\n"
            "- lighting_level: 6.00 W/m2\n"
            "- equipment_power: 45.80 W/m2\n"
            "- ventilation_ach: 0.5\n"
            "- infiltration_ach: 0.5\n"
            "- hvac_system: psz_ac\n"
            "- occupancy_schedule: occ_weekday_start=9, occ_weekday_end=17, occ_weekend_start=0, occ_weekend_end=0\n"
            "- lighting_schedule: light_weekday_start=8, light_weekday_end=18, light_weekend_start=0, light_weekend_end=0\n"
            "- equipment_schedule: equip_weekday_start=0, equip_weekday_end=24, equip_weekend_start=0, equip_weekend_end=24\n"
            "- hvac_schedule: hvac_weekday_start=9, hvac_weekday_end=17, hvac_weekend_start=0, hvac_weekend_end=0\n"
            "- thermostat_setpoints: heat_set_occ=21.0, heat_set_unocc=15.0, cool_set_occ=24.0, cool_set_unocc=28.0\n"
            "- window_properties: window_u_factor=3.0, window_shgc=0.5\n\n"
            "<Zone: Office>\n"
            "- geometry: length=6.00, width=8.00, height=4.00\n"
            "- relative_position: anchor (origin at 0,0,0)\n"
            "- roof: flat, skylight=none\n"
            "- wall_constructions:\n"
            "  - South: 'M01 100mm brick', 'I02 50mm insulation board'\n"
            "  - North: 'Medium Exterior Wall'\n"
            "  - East: 'Medium Exterior Wall'\n"
            "  - West: 'Medium Exterior Wall'\n"
            "- subsurfaces:\n"
            "  - type: window, wall: South, size: 1.5m wide x 2.0m high, offset_x: 2.0m from left edge, offset_z: 1.0m from top edge\n"
            "</Zone: Office>\n\n"
            "<Zone: MeetingRoom>\n"
            "- geometry: length=6.00, width=4.00, height=4.00\n"
            "- relative_position: attached to North wall of Office\n"
            "- roof: flat, skylight=none\n"
            "- wall_constructions:\n"
            "  - North: 'Medium Exterior Wall'\n"
            "  - South: 'Medium Exterior Wall'\n"
            "  - East: 'Medium Exterior Wall'\n"
            "  - West: 'Medium Exterior Wall'\n"
            "- hvac_system: split_ac\n"
            "- subsurfaces: []\n"
            "</Zone: MeetingRoom>\n\n"
            "<Zone: Lobby>\n"
            "- geometry: length=5.00, width=8.00, height=4.00\n"
            "- relative_position: attached to East wall of Office\n"
            "- roof: flat, skylight=none\n"
            "- wall_constructions:\n"
            "  - South: 'Medium Exterior Wall'\n"
            "  - North: 'Medium Exterior Wall'\n"
            "  - East: 'Medium Exterior Wall'\n"
            "  - West: 'Medium Exterior Wall'\n"
            "- subsurfaces: []\n"
            "</Zone: Lobby>\n\n"
            "--- Example 2: Single-Zone Building ---\n"
            "User: Simulate a single room office that is 10 meters long, 12 meters wide, and 3.5 meters high. Place two 2.5x1.8m windows on the South wall (3m and 7m from left, 1m from top). East wall has a 1.2x2.2m door (5m from left, fixed to ground). South wall is brick/insulation and others are heavy exterior wall. Occupancy rate is 20 m2/person. Run lights from 7am to 7pm.\n"
            "Output:\n"
            "Simulate a single-zone building with the following layout and thermal configurations.\n\n"
            "[GLOBAL SETTINGS]\n"
            "- occupancy_rate: 20.00 m2/people\n"
            "- lighting_level: 8.00 W/m2\n"
            "- equipment_power: 30.00 W/m2\n"
            "- ventilation_ach: 0.6\n"
            "- infiltration_ach: 0.4\n"
            "- hvac_system: split_ac\r\n"
            "- occupancy_schedule: occ_weekday_start=8, occ_weekday_end=18, occ_weekend_start=0, occ_weekend_end=0\n"
            "- lighting_schedule: light_weekday_start=7, light_weekday_end=19, light_weekend_start=0, light_weekend_end=0\n"
            "- equipment_schedule: equip_weekday_start=0, equip_weekday_end=24, equip_weekend_start=0, equip_weekend_end=24\n"
            "- hvac_schedule: hvac_weekday_start=8, hvac_weekday_end=18, hvac_weekend_start=0, hvac_weekend_end=0\n"
            "- thermostat_setpoints: heat_set_occ=20.0, heat_set_unocc=15.0, cool_set_occ=24.0, cool_set_unocc=28.0\n"
            "- window_properties: window_u_factor=2.8, window_shgc=0.45\n\n"
            "<Zone: StandaloneOffice>\n"
            "- geometry: length=10.00, width=12.00, height=3.50\n"
            "- relative_position: anchor (origin at 0,0,0)\n"
            "- roof: flat, skylight=none\n"
            "- wall_constructions:\n"
            "  - North: 'Heavy Exterior Wall'\n"
            "  - South: 'Composite Brick Foam 2x4 Steel Stud R11'\n"
            "  - East: 'Heavy Exterior Wall'\n"
            "  - West: 'Heavy Exterior Wall'\n"
            "- subsurfaces:\n"
            "  - type: window, wall: South, size: 2.5m wide x 1.8m high, offset_x: 3.0m from left edge, offset_z: 1.0m from top edge\n"
            "  - type: window, wall: South, size: 2.5m wide x 1.8m high, offset_x: 7.0m from left edge, offset_z: 1.0m from top edge\n"
            "  - type: door, wall: East, size: 1.2m wide x 2.2m high, offset_x: 5.0m from left edge, offset_z: 0.0m from bottom edge\n"
            "</Zone: StandaloneOffice>"
        )

        user_prompt = f"USER DESCRIPTION TO RESTRUCTURE:\n{raw_prompt}"

        if self.ai_pipelines:
            if model_type == "openai":
                return self.ai_pipelines._call_openai(system_prompt, user_prompt)
            elif model_type == "gemini":
                return self.ai_pipelines._call_gemini(system_prompt, user_prompt)
            elif model_type == "huggingface":
                return self.ai_pipelines._call_huggingface(system_prompt, user_prompt)
            elif model_type == "ollama":
                return self.ai_pipelines._call_ollama(system_prompt, user_prompt)
        else:
            import ollama
            response = ollama.chat(
                model='gemma3:12b',
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={"num_ctx": 8192, "num_predict": 4096}
            )
            return response['message']['content'].strip()
