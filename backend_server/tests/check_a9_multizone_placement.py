"""A9 check: are multi-zone (custom engine) zones simulated where coordinates_calculator means to put them?

Builds a 3-zone model with no AI and no doors (A anchor 5x4, B east of A 6x4, C north of A 5x3, all 3 m high),
runs EnergyPlus (design days only, as Base.idf sets), and compares each zone's box from the .eio
'Zone Information' rows with the box the code intended (origin + L, W, H).
Usage (from backend_server/):  python3 tests/check_a9_multizone_placement.py [path/to/energyplus]
"""
import os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "core"))
os.chdir(ROOT)

import idf_assembler                      # noqa: E402
import coordinates_calculator             # noqa: E402
from model_generator import AIPipelines   # noqa: E402

ZONES = [
    {"name": "Z_A", "length": 5.0, "width": 4.0, "height": 3.0},
    {"name": "Z_B", "length": 6.0, "width": 4.0, "height": 3.0, "relative_to": "Z_A", "direction": "East"},
    {"name": "Z_C", "length": 5.0, "width": 3.0, "height": 3.0, "relative_to": "Z_A", "direction": "North"},
]
CONSTR = "Composite 2x4 Wood Stud R11"


def build_idf():
    zones = [dict(z, wall_construction=CONSTR, roof_construction=CONSTR) for z in ZONES]
    ai = AIPipelines(secrets_path="/nonexistent", template_path="idf_templates/Base.idf")
    idf = ai._assemble_multizone_idf({"zones": zones}, {}, None, None, idf_assembler, [], {})
    return idf + "\n  Output:Surfaces:List,\n    DetailsWithVertices;\n"


def intended():
    origins = coordinates_calculator.resolve_zone_origins([dict(z) for z in ZONES])
    return {z["name"].upper(): (origins[z["name"]][0], origins[z["name"]][0] + z["length"],
                                origins[z["name"]][1], origins[z["name"]][1] + z["width"],
                                origins[z["name"]][2], origins[z["name"]][2] + z["height"]) for z in ZONES}


def simulated(eio_text):
    """Zone Information rows: name, north, origin x,y,z, centroid x,y,z, type, mult, ..., then min/max x,y,z."""
    head = next(l for l in eio_text.splitlines() if l.startswith("! <Zone Information>"))
    cols = [c.strip() for c in head.split(",")]
    ix = {k: cols.index(k) for k in ["Minimum X {m}", "Maximum X {m}", "Minimum Y {m}", "Maximum Y {m}",
                                     "Minimum Z {m}", "Maximum Z {m}", "Floor Area {m2}", "Volume {m3}"]}
    out = {}
    for l in eio_text.splitlines():
        if l.startswith(" Zone Information,"):
            f = [c.strip() for c in l.split(",")]
            out[f[1]] = tuple(float(f[ix[k]]) for k in ix)
    return out


def main():
    eplus = sys.argv[1] if len(sys.argv) > 1 else "/usr/local/EnergyPlus-25-1-0/energyplus"
    work = tempfile.mkdtemp(prefix="a9_")
    idf_path = os.path.join(work, "a9_three_zones.idf")
    open(idf_path, "w").write(build_idf())
    r = subprocess.run([eplus, "-d", work, idf_path], capture_output=True, text=True)
    print("EnergyPlus exit code:", r.returncode, "| output in", work)
    err = open(os.path.join(work, "eplusout.err")).read()
    print("severe errors:", len(re.findall(r"\*\* Severe", err)), "| warnings:", len(re.findall(r"\*\* Warning", err)))
    sim = simulated(open(os.path.join(work, "eplusout.eio")).read())
    want = intended()
    ok = True
    print(f"{'zone':5} {'intended x / y / z box':38} {'EnergyPlus x / y / z box':38} area  vol")
    for name, w in want.items():
        s = sim[name]
        match = all(abs(a - b) < 0.01 for a, b in zip(w, s[:6]))
        ok &= match
        fmt = lambda b: f"{b[0]:5.1f}–{b[1]:<5.1f} {b[2]:5.1f}–{b[3]:<5.1f} {b[4]:4.1f}–{b[5]:<4.1f}"
        print(f"{name:5} {fmt(w):38} {fmt(s):38} {s[6]:5.1f} {s[7]:5.1f}  {'OK' if match else 'MISPLACED'}")
    print("RESULT:", "zones are where the code intends" if ok else "zones are NOT where the code intends (A9 confirmed)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
