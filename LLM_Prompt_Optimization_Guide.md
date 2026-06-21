# LLM Prompt Optimization Guide for SmartBEM-Studio

This guide explains how to format your building descriptions using structural cues and key-value formats to achieve **zero-error parameter extraction** on local LLMs (like `gemma3:12b`).

---

## 1. The Core Challenge of NLP Extraction

When you write a single, continuous paragraph describing multiple rooms (zones), the LLM processes it in one context window. For a small/medium local model (under 13B parameters), this creates several issues:

1. **Attention Bleed (Cross-Contamination)**: When multiple zones have South walls or use similar phrases like `"2m from left edge"`, the attention weights of the model overlap. The model gets confused and extracts the Lobby's door offset (`2m`) into the Meeting Room's door offset (`0.5m`).
2. **Override Logic Failures**: Asking the model to `"Make the South wall out of X construction and other walls out of Y"` requires multi-step logical reasoning (identify Y, assign Y to North/East/West, assign X to South). Local models frequently fail at this logic and apply X to the wrong walls or defaults to all walls.
3. **Flipped Dimensions**: If the model extracts `"1.5x2m window"` as a list of numbers, it can easily assign `width = 2.0` and `height = 1.5`, which rotates the window horizontally instead of vertically.

---

## 2. The Original Prompt (High Extraction Error Risk)

```text
Simulate a building with three zones: an office, a meeting room, a lobby

The office is 6.00 meters long, 8.00 meters wide, and 4.00 meters high. The meeting room is attached to the North wall of the office.

The meeting room is 6.00 meters long, 4.00 meters wide, and 4.00 meters high. The lobby is attached to the East wall of the office.

The lobby is 5.00 meters long, 8.00 meters wide, and 4.00 meters high.

For the office: place a 1.5x2m window on the South wall 2m from left edge, 1m from top edge. place a 0.8x1.5m window on the West wall 2m from left edge, 1.5m from top edge. place a 1x2.5m door on the West wall 5m from left edge, fix to ground. Make the South wall out of 'M01 100mm brick' and 'I02 50mm insulation board' and the other walls out of 'Medium Exterior Wall'.

For the meeting room: place a 1x1m window on the North wall 2m from left edge, 1.5m from top edge. place a 0.8x1.5m window on the West wall 1m from left edge, 1.5m from top edge. place a 1x2.5m door on the South wall 0.5m from left edge, fix to ground. Make the North wall out of 'M01 100mm brick' and 'I02 50mm insulation board' and the other walls out of 'Medium Exterior Wall'.

For the lobby: place a 2x2.5m door on the East wall 3m from left edge, fix to ground. place a 1x2.5m door on the South wall 2m from left edge, fix to ground. place a 1x1.5m window on the South wall 4.5m from left edge, 1.5m from top edge. Make the South wall out of 'M01 100mm brick' and 'I02 50mm insulation board' and the other walls out of 'Medium Exterior Wall'.

All three zone has pitched roofs with a gable height of 3 meters. Place a 2.0x1.5m skylight on the roof.

The occupancy rate is 30.00 m2/people, the lighting level is 6.00 W/m2, and the equipment power consumption is 45.80 W/m2.

All zones use a packaged AC unit (psz_ac).

People are in the building from 9am to 5pm on weekdays and completely closed on weekends.

The lights are on from 8am to 6pm, and the equipment runs 24/7.
```

---

## 3. The Optimized, "LLM-Friendly" Prompt

By structuring the description with XML-style zone tags and explicit key-value fields, you isolate the parameters so that the LLM has a clear, localized context to pull from.

```text
Simulate a multi-zone building with the following layout and thermal configurations.

[GLOBAL SETTINGS]
- occupancy_rate: 30.00 m2/people
- lighting_level: 6.00 W/m2
- equipment_power: 45.80 W/m2
- ventilation_ach: 0.5
- infiltration_ach: 0.5
- hvac_system: psz_ac
- occupancy_schedule: occ_weekday_start=9, occ_weekday_end=17, occ_weekend_start=0, occ_weekend_end=0
- lighting_schedule: light_weekday_start=8, light_weekday_end=18, light_weekend_start=0, light_weekend_end=0
- equipment_schedule: equip_weekday_start=0, equip_weekday_end=24, equip_weekend_start=0, equip_weekend_end=24
- hvac_schedule: hvac_weekday_start=9, hvac_weekday_end=17, hvac_weekend_start=0, hvac_weekend_end=0
- thermostat_setpoints: heat_set_occ=21.0, heat_set_unocc=15.0, cool_set_occ=24.0, cool_set_unocc=28.0
- window_properties: window_u_factor=3.0, window_shgc=0.5

<Zone: Office>
- geometry: length=6.00, width=8.00, height=4.00
- relative_position: anchor (origin at 0,0,0)
- roof: pitched, gable_height=3.00, skylight=2.0m wide by 1.5m long
- wall_constructions:
  - South: 'M01 100mm brick', 'I02 50mm insulation board'
  - North: 'Medium Exterior Wall'
  - East: 'Medium Exterior Wall'
  - West: 'Medium Exterior Wall'
- subsurfaces:
  - type: window, wall: South, size: 1.5m wide x 2.0m high, offset_x: 2.0m from left edge, offset_z: 1.0m from top edge
  - type: window, wall: West, size: 0.8m wide x 1.5m high, offset_x: 2.0m from left edge, offset_z: 1.5m from top edge
  - type: door, wall: West, size: 1.0m wide x 2.5m high, offset_x: 5.0m from left edge, offset_z: 0.0m from bottom edge
</Zone: Office>

<Zone: MeetingRoom>
- geometry: length=6.00, width=4.00, height=4.00
- relative_position: attached to North wall of Office
- roof: pitched, gable_height=3.00, skylight=2.0m wide by 1.5m long
- wall_constructions:
  - North: 'M01 100mm brick', 'I02 50mm insulation board'
  - South: 'Medium Exterior Wall'
  - East: 'Medium Exterior Wall'
  - West: 'Medium Exterior Wall'
- subsurfaces:
  - type: window, wall: North, size: 1.0m wide x 1.0m high, offset_x: 2.0m from left edge, offset_z: 1.5m from top edge
  - type: window, wall: West, size: 0.8m wide x 1.5m high, offset_x: 1.0m from left edge, offset_z: 1.5m from top edge
  - type: door, wall: South, size: 1.0m wide x 2.5m high, offset_x: 0.5m from left edge, offset_z: 0.0m from bottom edge
</Zone: MeetingRoom>

<Zone: Lobby>
- geometry: length=5.00, width=8.00, height=4.00
- relative_position: attached to East wall of Office
- roof: pitched, gable_height=3.00, skylight=2.0m wide by 1.5m long
- wall_constructions:
  - South: 'M01 100mm brick', 'I02 50mm insulation board'
  - North: 'Medium Exterior Wall'
  - East: 'Medium Exterior Wall'
  - West: 'Medium Exterior Wall'
- subsurfaces:
  - type: door, wall: East, size: 2.0m wide x 2.5m high, offset_x: 3.0m from left edge, offset_z: 0.0m from bottom edge
  - type: door, wall: South, size: 1.0m wide x 2.5m high, offset_x: 2.0m from left edge, offset_z: 0.0m from bottom edge
  - type: window, wall: South, size: 1.0m wide x 1.5m high, offset_x: 4.5m from left edge, offset_z: 1.5m from top edge
</Zone: Lobby.
```

---

## 4. Key Improvements and Why They Work

### 1. Context Isolation (`<Zone: Name> ... </Zone: Name>`)
* **Why**: LLM attention heads are highly sensitive to structured boundaries. Encapsulating each room's descriptions inside XML-style tags tells the parser, "When looking for `MeetingRoom` details, only look between these boundaries."
* **Result**: Eliminates parameter mixing. The model will no longer mistake the Office window offset `2m` for the Meeting Room door offset `0.5m`.

### 2. Direct Construction Mapping (No "Other Walls" Logical Loops)
* **Why**: The original sentence `"Make the South wall out of brick... and other walls out of Medium Exterior Wall"` forces the LLM to write a negative conditional list (i.e. "not South"). This logic is often flawed in small models.
* **Result**: Specifying each cardinal direction (`North`, `South`, `East`, `West`) directly as a list maps directly to the backend JSON keys: `wall_layers_south`, `wall_layers_north`, etc., yielding a 100% correct construction assignment.

### 3. Explicit Dimension Labels (`Xm wide x Ym high`)
* **Why**: The backend expects a specific order: `width` first, `height` second. Stating `"size: 1.5m wide x 2.0m high"` is much more explicit than `"1.5x2m"`, ensuring the parser never flips doors and windows horizontally.

### 4. Direct Offset and Reference Alignment (`offset_x: 2.0m from left edge`)
* **Why**: The backend JSON schema reads `offset_x`, `ref_x`, `offset_z`, and `ref_z`. By structuring this phrase as `"offset_x: X.Xm from left edge, offset_z: Z.Zm from top edge"`, it matches the template engine directly, preventing the model from outputting arbitrary key names.

### 5. Explicit Integer Schedule Mapping (`occ_weekday_start=9, occ_weekday_end=17`)
* **Why**: Natural language descriptions like "weekends closed" or "runs 24/7" do not map directly to the integer keys (`occ_weekend_start`, `equip_weekday_end`) expected by the schema. The LLM will output `null` (None) for these keys, which causes comparisons like `we_s > 0` in Python to crash with a `TypeError`.
* **Result**: Providing explicit `start` and `end` integer hour values forces the LLM to output integer parameters, completely avoiding Python `NoneType` errors.

---

## 5. Single-Zone Optimized Prompt Template

For buildings with only a single zone (e.g., a standalone office, retail shop, or cabin), the relative position is simply anchored at the origin, and only one `<Zone>` block is needed.

### Example Single-Zone Prompt

```text
Simulate a single-zone building with the following layout and thermal configurations.

[GLOBAL SETTINGS]
- occupancy_rate: 20.00 m2/people
- lighting_level: 8.00 W/m2
- equipment_power: 30.00 W/m2
- ventilation_ach: 0.6
- infiltration_ach: 0.4
- hvac_system: psz_ac
- occupancy_schedule: occ_weekday_start=8, occ_weekday_end=18, occ_weekend_start=0, occ_weekend_end=0
- lighting_schedule: light_weekday_start=7, light_weekday_end=19, light_weekend_start=0, light_weekend_end=0
- equipment_schedule: equip_weekday_start=0, equip_weekday_end=24, equip_weekend_start=0, equip_weekend_end=24
- hvac_schedule: hvac_weekday_start=8, hvac_weekday_end=18, hvac_weekend_start=0, hvac_weekend_end=0
- thermostat_setpoints: heat_set_occ=20.0, heat_set_unocc=15.0, cool_set_occ=24.0, cool_set_unocc=28.0
- window_properties: window_u_factor=2.8, window_shgc=0.45

<Zone: StandaloneOffice>
- geometry: length=10.00, width=12.00, height=3.50
- relative_position: anchor (origin at 0,0,0)
- roof: flat, skylight=none
- wall_constructions:
  - North: 'Heavy Exterior Wall'
  - South: 'Composite Brick Foam 2x4 Steel Stud R11'
  - East: 'Heavy Exterior Wall'
  - West: 'Heavy Exterior Wall'
- subsurfaces:
  - type: window, wall: South, size: 2.5m wide x 1.8m high, offset_x: 3.0m from left edge, offset_z: 1.0m from top edge
  - type: window, wall: South, size: 2.5m wide x 1.8m high, offset_x: 7.0m from left edge, offset_z: 1.0m from top edge
  - type: door, wall: East, size: 1.2m wide x 2.2m high, offset_x: 5.0m from left edge, offset_z: 0.0m from bottom edge
</Zone: StandaloneOffice>
```
