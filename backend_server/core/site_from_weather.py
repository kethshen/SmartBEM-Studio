"""
Site location and design days from the chosen weather file (flaw A7).

Base.idf carries Chicago's Site:Location and two Chicago design days, and the default run type
simulates only the design days, so without this every job ran in Chicago whatever weather was picked.

- Site:Location comes from the EPW's first line (LOCATION,city,state,country,source,WMO,lat,lon,tz,elev).
- Design days come from the .ddy file that sits next to the EPW in the EnergyPlus weather library
  (same name, .ddy). We keep the usual pair: annual heating 99.6 % and annual cooling 0.4 % DB=>MWB.
  If no .ddy is found, the template's design days stay and the returned info says so.
"""
import os
import re

_OBJ = re.compile(r"(?is)^\s*(SizingPeriod:DesignDay\s*,.*?;)", re.MULTILINE)
_SITE = re.compile(r"(?is)^\s*Site:Location\s*,.*?;[ \t]*\r?\n?", re.MULTILINE)


def _strip_comments(block):
    return "\n".join(l.split("!")[0] for l in block.splitlines())


def location_from_epw(epw_path):
    """(name, lat, lon, time_zone, elevation) from the EPW header, or None."""
    try:
        with open(epw_path, "r", encoding="utf-8", errors="ignore") as f:
            first = f.readline()
    except OSError:
        return None
    f = [x.strip() for x in first.split(",")]
    if len(f) < 10 or f[0].upper() != "LOCATION":
        return None
    try:
        lat, lon, tz, elev = (float(v) for v in f[6:10])
    except ValueError:
        return None
    name = "_".join(p for p in (f[1], f[3], f[4], f[5]) if p and p != "-")
    return name.replace(",", " "), lat, lon, tz, elev


def design_days_from_ddy(ddy_path):
    """The heating 99.6 % and cooling 0.4 % DB=>MWB design days from a .ddy file, as IDF text blocks."""
    if not ddy_path or not os.path.exists(ddy_path):
        return []
    # strip comments first: .ddy comments contain ';' (e.g. "{Degrees; N=0, S=180}"), which would end an object early
    text = _strip_comments(open(ddy_path, "r", encoding="utf-8", errors="ignore").read())
    picked = {}
    for block in _OBJ.findall(text):
        fields = [x.strip() for x in block.rstrip(";").split(",")]
        low = fields[1].lower() if len(fields) > 1 else ""
        tidy = "SizingPeriod:DesignDay,\n" + ",\n".join("    " + f for f in fields[1:]) + ";"
        if "htg 99.6%" in low and "heating" not in picked:
            picked["heating"] = tidy
        elif "clg .4%" in low and "db=>mwb" in low and "cooling" not in picked:
            picked["cooling"] = tidy
    return [picked[k] for k in ("heating", "cooling") if k in picked]


def apply_site(idf_text, epw_path, ddy_path=None):
    """Return (new_idf_text, info). info says what was used, for the job log and results."""
    info = {"epw": os.path.basename(epw_path) if epw_path else None}

    loc = location_from_epw(epw_path) if epw_path else None
    if loc:
        name, lat, lon, tz, elev = loc
        site = (f"\n  Site:Location,\n    {name},  !- Name\n    {lat:.4f},  !- Latitude {{deg}}\n"
                f"    {lon:.4f},  !- Longitude {{deg}}\n    {tz:.2f},  !- Time Zone {{hr}}\n    {elev:.1f};  !- Elevation {{m}}\n")
        idf_text = _SITE.sub("", idf_text).rstrip() + "\n" + site
        info["location"] = f"{name} ({lat:.2f}, {lon:.2f}), from the EPW"
    else:
        info["location"] = "template Site:Location kept (EPW header not readable)"

    if ddy_path is None and epw_path:
        ddy_path = os.path.splitext(epw_path)[0] + ".ddy"
    days = design_days_from_ddy(ddy_path)
    if len(days) == 2:
        idf_text = re.sub(r"(?is)^\s*SizingPeriod:DesignDay\s*,.*?;[ \t]*\r?\n?", "", idf_text, flags=re.MULTILINE)
        idf_text = idf_text.rstrip() + "\n\n  " + "\n\n  ".join(days) + "\n"
        info["design_days"] = [_strip_comments(d).split(",")[1].strip() for d in days] + ["from " + os.path.basename(ddy_path)]
    else:
        info["design_days"] = ["WARNING: no usable .ddy next to the EPW; the template's (Chicago) design days were kept"]
    return idf_text, info
