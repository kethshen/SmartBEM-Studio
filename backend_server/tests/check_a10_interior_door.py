"""A10 check: does a door between two zones (custom engine, multi-zone) run in EnergyPlus?

Same 3-zone layout as check_a9_multizone_placement.py, plus one 1 m x 2 m door on Z_A's east wall,
which is shared with Z_B. The code mirrors it onto Z_B's west wall. EnergyPlus must accept the pair
(each door names its twin), the two doors must have the same world corners, and the run must finish.
Usage (from backend_server/):  python3 tests/check_a10_interior_door.py [path/to/energyplus]
"""
import os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_a9_multizone_placement as a9   # noqa: E402  (also sets up paths and cwd)

a9.ZONES[0]["door_east"] = {"width": 1.0, "height": 2.0, "ref_x": "left", "offset_x": 1.0}


def door_rows(eio_text):
    """Door rows (listed as 'HeatTransfer Surface' with class Door) and their world vertices (Output:Surfaces:List, DetailsWithVertices)."""
    out = {}
    for l in eio_text.splitlines():
        f = [c.strip() for c in l.split(",")]
        if f[0] == "HeatTransfer Surface" and len(f) > 2 and f[2] == "Door":
            out[f[1]] = (f[17], [round(float(v), 2) for v in f[-12:]])   # (outside boundary object, 12 coords)
    return out


def main():
    eplus = sys.argv[1] if len(sys.argv) > 1 else "/usr/local/EnergyPlus-25-1-0/energyplus"
    work = tempfile.mkdtemp(prefix="a10_")
    idf_path = os.path.join(work, "a10_interior_door.idf")
    open(idf_path, "w").write(a9.build_idf())
    r = subprocess.run([eplus, "-d", work, idf_path], capture_output=True, text=True)
    err = open(os.path.join(work, "eplusout.err")).read()
    severe = re.findall(r"\*\* Severe  \*\*.*", err) + re.findall(r"\*\*  Fatal  \*\*.*", err)
    print("EnergyPlus exit code:", r.returncode, "| output in", work)
    for s in severe[:6]:
        print("  ", s)
    if r.returncode != 0:
        print("RESULT: the run stops (A10 confirmed)")
        return 1
    doors = door_rows(open(os.path.join(work, "eplusout.eio")).read())
    for n, (obj, v) in doors.items():
        pts = sorted(tuple(v[i:i + 3]) for i in range(0, 12, 3))
        print(f"  {n:22} twin={obj:22} corners={pts}")
    a, b = doors.get("Z_A_WALL_EAST_DOOR"), doors.get("Z_B_WALL_WEST_DOOR")
    ok = bool(a and b) and a[0] == "Z_B_WALL_WEST_DOOR" and b[0] == "Z_A_WALL_EAST_DOOR" and \
        sorted(tuple(a[1][i:i + 3]) for i in range(0, 12, 3)) == sorted(tuple(b[1][i:i + 3]) for i in range(0, 12, 3))
    print("RESULT:", "the door pair runs and lines up" if ok else "the run finished but the door pair is wrong")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
