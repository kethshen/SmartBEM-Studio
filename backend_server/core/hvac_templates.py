"""
One source of HVAC for both builders (flaw A8).

The custom builder and the OpenStudio builder both take their zone HVAC from the templates in
idf_templates/hvac/, so the same hvac_type gives the same equipment whichever builder made the model.
Each zone's outdoor air comes from one DesignSpecification:OutdoorAir that carries the requested
ventilation ACH (oa_spec_block); every template links to it through {OA_SPEC}.

  ideal_loads  ideal loads air system + outdoor air
  ptac         packaged terminal AC: DX cooling, electric heating, fan runs continuously
  split_ac     the same unit with the fan cycling with the compressor (a ductless split / mini-split)
  psz_ac       packaged single-zone AC (ASHRAE System 3): air loop, gas heating coil, DX cooling, constant fan
"""
import os

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "idf_templates", "hvac")
HVAC_TYPES = {
    "ideal_loads": ("ideal_loads.idf", {}),
    "ptac": ("ptac.idf", {"{FAN_MODE}": "1.0"}),
    "split_ac": ("ptac.idf", {"{FAN_MODE}": "0.0"}),
    "psz_ac": ("psz_ac.idf", {}),
}


def resolve_type(hvac_type):
    t = (hvac_type or "ideal_loads").strip().lower()
    if t not in HVAC_TYPES:
        print(f"[HVAC] Unknown hvac_type '{hvac_type}', using ideal_loads")
        t = "ideal_loads"
    return t


def hvac_block(hvac_type, zone_name, oa_spec_name):
    """IDF text for one zone's HVAC, linked to the zone's outdoor-air object."""
    t = resolve_type(hvac_type)
    fname, extra = HVAC_TYPES[t]
    with open(os.path.join(TEMPLATE_DIR, fname), "r", encoding="utf-8") as f:
        text = f.read()
    for k, v in extra.items():
        text = text.replace(k, v)
    return text.replace("{OA_SPEC}", oa_spec_name).replace("{ZONE_NAME}", zone_name)


def oa_spec_block(name, ach):
    """A zone's outdoor air as air changes per hour."""
    return f"""
  DesignSpecification:OutdoorAir,
    {name},                  !- Name
    AirChanges/Hour,         !- Outdoor Air Method
    0,                       !- Outdoor Air Flow per Person {{m3/s-person}}
    0,                       !- Outdoor Air Flow per Zone Floor Area {{m3/s-m2}}
    0,                       !- Outdoor Air Flow per Zone {{m3/s}}
    {float(ach)};            !- Outdoor Air Flow Air Changes per Hour {{1/hr}}
"""
