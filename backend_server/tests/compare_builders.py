"""A8 check: give the custom builder and the OpenStudio builder the same building, and compare what EnergyPlus reads.

Both builders get one params dict (the shape the AI produces): three zones as in check_a9 (A anchor, B east,
C north), windows, window U/SHGC, ventilation and infiltration ACH, gains and one HVAC type. Each IDF is run in
EnergyPlus the same way (design days, same outputs). The table is read from the .eio and the results, so it
shows what the simulation used, not what the code meant.
Needs the openstudio Python package.
Usage (from backend_server/):  python3 tests/compare_builders.py [hvac_type] [path/to/energyplus]
"""
import csv, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import idf_assembler                      # noqa: E402
from model_generator import AIPipelines   # noqa: E402

WALL = "Composite 2x4 Wood Stud R11"


def params(hvac):
    zones = [
        {"name": "Z_A", "length": 5.0, "width": 4.0, "height": 3.0, "wwr_south": 0.3, "wwr_west": 0.3},
        {"name": "Z_B", "length": 6.0, "width": 4.0, "height": 3.0, "relative_to": "Z_A", "direction": "East",
         "wwr_south": 0.3, "wwr_east": 0.3},
        {"name": "Z_C", "length": 5.0, "width": 3.0, "height": 3.0, "relative_to": "Z_A", "direction": "North",
         "wwr_north": 0.3},
    ]
    for z in zones:
        z.update(wall_layers=WALL, roof_layers=WALL)
    return {"is_multizone": True, "zones": zones, "hvac_type": hvac,
            "window_u_factor": 1.8, "window_shgc": 0.4,
            "ventilation_ach": 1.0, "infiltration_ach": 0.5,
            "people_density": 10.0, "light_density": 8.0, "equipment_density": 12.0,
            "floor_layers": WALL}


OUTPUTS = """
  Output:Variable,*,Site Outdoor Air Drybulb Temperature,Hourly;
  Output:Variable,*,Zone Air Temperature,Hourly;
  Output:Variable,*,Zone Air System Sensible Cooling Energy,Hourly;
  Output:Variable,*,Zone Air System Sensible Heating Energy,Hourly;
  Output:Variable,*,Zone Mechanical Ventilation Air Changes per Hour,Hourly;
  Output:Meter,Electricity:Facility,Hourly;
  Output:Surfaces:List,DetailsWithVertices;
  Output:SQLite,SimpleAndTabular;
  Output:Table:SummaryReports,EnvelopeSummary;
"""


def build(kind, hvac):
    p = params(hvac)
    if kind == "custom":
        ai = AIPipelines(secrets_path="/nonexistent", template_path="idf_templates/Base.idf")
        return ai._assemble_multizone_idf(p, {}, None, None, idf_assembler, [], {})
    from core import openstudio_builder   # needs the openstudio package (Python <= 3.13; 3.11.0 crashes on 3.14)
    return openstudio_builder.build_idf_from_params(p)


def run(idf, eplus, tag):
    work = tempfile.mkdtemp(prefix=f"a8_{tag}_")
    path = os.path.join(work, "m.idf")
    open(path, "w").write(re.sub(r"(?is)^\s*Output:(Variable|Meter|SQLite|Table:SummaryReports)\s*,.*?;", "", idf, flags=re.M) + OUTPUTS)
    r = subprocess.run([eplus, "-r", "-d", work, path], capture_output=True, text=True)
    return work, r.returncode


def eio_rows(work, key):
    eio = open(os.path.join(work, "eplusout.eio")).read().splitlines()
    head = next((l for l in eio if l.startswith(f"! <{key}>")), None)
    if not head:
        return [], []
    cols = [c.strip() for c in head.split(",")]
    return cols, [[c.strip() for c in l.split(",")] for l in eio if l.startswith(f"{key},") or l.startswith(f" {key},")]


def summary(work, idf):
    out = {}
    err = open(os.path.join(work, "eplusout.err")).read()
    out["severe errors"] = len(re.findall(r"\*\* Severe", err))
    cols, rows = eio_rows(work, "Zone Information")
    if rows:
        i = {k: cols.index(k) for k in cols}
        for r in rows:
            z = r[1].split("_THERMALZONE")[0]
            out[f"{z} floor m² / volume m³"] = f"{float(r[i['Floor Area {m2}']]):.1f} / {float(r[i['Volume {m3}']]):.1f}"
            out[f"{z} window area m²"] = f"{float(r[i['Exterior Window Area {m2}']]):.2f}"
    cols, rows = eio_rows(work, "Zone Internal Gains Nominal")
    for r in rows:
        z = r[1].split("_THERMALZONE")[0]
        out[f"{z} people / lights / equip"] = f"{float(r[4]):.1f} m²/p, {float(r[6]):.1f}, {float(r[7]):.1f} W/m²"
    cols, rows = eio_rows(work, "ZoneInfiltration Airflow Stats Nominal")
    ach = next((j for j, c in enumerate(cols) if c.startswith("ACH")), None)
    if rows and ach is not None:
        out["infiltration ACH (nominal)"] = " / ".join(f"{float(r[ach]):.2f}" for r in rows)
    # glazing actually used: EnergyPlus's Envelope Summary, Exterior Fenestration table
    import sqlite3
    sql = os.path.join(work, "eplusout.sql")
    if os.path.exists(sql):
        q = ("SELECT RowName, ColumnName, Value FROM TabularDataWithStrings WHERE ReportName='EnvelopeSummary' "
             "AND TableName='Exterior Fenestration' AND ColumnName IN ('Construction','Glass U-Factor','Glass SHGC')")
        rows = sqlite3.connect(sql).execute(q).fetchall()
        per = {}
        for rn, cn, v in rows:
            if rn.upper().startswith("TOTAL") or rn.upper().startswith("NORTH") or "AVERAGE" in rn.upper():
                continue
            per.setdefault(rn, {})[cn] = v.strip()
        kinds = sorted({f"{d.get('Construction','?')}: U {d.get('Glass U-Factor','?')}, SHGC {d.get('Glass SHGC','?')}" for d in per.values()})
        out["window glazing used"] = "; ".join(kinds) or "-"
    # HVAC objects in the IDF
    kinds = ["ZoneHVAC:IdealLoadsAirSystem", "ZoneHVAC:PackagedTerminalAirConditioner", "ZoneHVAC:PackagedTerminalHeatPump",
             "AirLoopHVAC", "Coil:Cooling:DX:SingleSpeed", "Coil:Heating:Electric", "Coil:Heating:DX:SingleSpeed"]
    start = lambda k: r"(?im)^\s*" + re.escape(k) + r"\s*,\s*$"   # an object's first line, not a reference to it
    out["HVAC objects"] = ", ".join(f"{k.split(':')[-1]}×{len(re.findall(start(k), idf))}"
                                    for k in kinds if re.search(start(k), idf)) or "-"
    out["Sizing:Zone objects"] = str(len(re.findall(r"(?im)^\s*Sizing:Zone\s*,", idf)))
    out["IDF version"] = (re.search(r"(?im)^\s*Version\s*,\s*([\d.]+)", idf) or [None, "?"])[1]
    # results
    csvp = os.path.join(work, "eplusout.csv")
    if os.path.exists(csvp):
        rows = list(csv.reader(open(csvp)))
        h = rows[0]
        def col_sum(pat, scale):
            s = 0.0
            for j, c in enumerate(h):
                if re.search(pat, c, re.I):
                    s += sum(float(x[j]) for x in rows[1:] if x[j])
            return s * scale
        def col_mean(pat):
            v = [float(x[j]) for j, c in enumerate(h) if re.search(pat, c, re.I) for x in rows[1:] if x[j]]
            return sum(v) / len(v) if v else float("nan")
        out["mech. ventilation ACH (mean)"] = f"{col_mean('Mechanical Ventilation Air Changes'):.2f}"
        out["zone cooling, design days (kWh)"] = f"{col_sum('Sensible Cooling Energy', 1/3.6e6):.1f}"
        out["zone heating, design days (kWh)"] = f"{col_sum('Sensible Heating Energy', 1/3.6e6):.1f}"
        out["facility electricity (kWh)"] = f"{col_sum('Electricity:Facility', 1/3.6e6):.1f}"
    return out


def main():
    hvac = sys.argv[1] if len(sys.argv) > 1 else "ideal_loads"
    eplus = sys.argv[2] if len(sys.argv) > 2 else "/usr/local/EnergyPlus-25-1-0/energyplus"
    res = {}
    for kind in ["custom", "openstudio"]:
        idf = build(kind, hvac)
        work, code = run(idf, eplus, kind)
        res[kind] = summary(work, idf)
        res[kind]["exit code"] = str(code)
        print(f"[{kind}] output in {work}")
    keys = list(dict.fromkeys(list(res["custom"]) + list(res["openstudio"])))
    print(f"\nhvac_type = {hvac}\n{'':38} {'custom':42} openstudio")
    for k in keys:
        a, b = str(res["custom"].get(k, "-")), str(res["openstudio"].get(k, "-"))
        print(f"{k:38} {a:42} {b}{'' if a == b else '   ≠'}")


if __name__ == "__main__":
    main()
