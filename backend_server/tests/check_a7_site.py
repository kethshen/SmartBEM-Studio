"""A7 check: does a job use the chosen weather file's location and design days, not Chicago's?

Fetches a weather file the way the server does (resolve_epw, which now also fetches the .ddy), builds
the A9 three-zone model, applies core/site_from_weather.apply_site as the simulator does, runs
EnergyPlus (design days, the default run type) and reads back what E+ used: the location from the .eio,
and the design-day names and outdoor temperature range from the output.
Usage (from backend_server/):  python3 tests/check_a7_site.py [epw_url] [path/to/energyplus]
Default epw_url: Colombo-Katunayake, Sri Lanka.
"""
import csv, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_a9_multizone_placement as a9   # noqa: E402  (sets up paths and cwd)
from weather_file_finder import resolve_epw   # noqa: E402
from site_from_weather import apply_site      # noqa: E402

URL = ("https://energyplus-weather.s3.amazonaws.com/asia_wmo_region_2/LKA/LKA_Colombo-Katunayake.434500_SWERA/"
       "LKA_Colombo-Katunayake.434500_SWERA.epw")


def run(idf_text, epw, eplus, tag):
    work = tempfile.mkdtemp(prefix=f"a7_{tag}_")
    p = os.path.join(work, "m.idf")
    open(p, "w").write(idf_text)
    r = subprocess.run([eplus, "-r", "-w", epw, "-d", work, p], capture_output=True, text=True)
    eio = open(os.path.join(work, "eplusout.eio")).read()
    loc = next(l for l in eio.splitlines() if l.lstrip().startswith("Site:Location,"))
    envs = [l.split(",")[1].strip() for l in eio.splitlines() if l.lstrip().startswith("Environment,")]
    rows = list(csv.reader(open(os.path.join(work, "eplusout.csv"))))
    i = rows[0].index("Environment:Site Outdoor Air Drybulb Temperature [C](Hourly)")
    t = [float(x[i]) for x in rows[1:]]
    return r.returncode, loc, envs, (min(t), max(t))


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else URL
    eplus = sys.argv[2] if len(sys.argv) > 2 else "/usr/local/EnergyPlus-25-1-0/energyplus"
    cache = os.path.join(tempfile.gettempdir(), "a7_weather_cache")
    epw = resolve_epw({"epw_url": url}, cache_dir=cache)
    print("EPW:", epw, "| .ddy present:", os.path.exists(epw[:-4] + ".ddy"))
    base = a9.build_idf()
    fixed, info = apply_site(base, epw)
    print("apply_site:", info)
    ok = True
    for tag, text in [("before", base), ("after", fixed)]:
        code, loc, envs, (tmin, tmax) = run(text, epw, eplus, tag)
        print(f"{tag:6} exit {code} | {loc.strip()[:70]} | design days {envs} | outdoor {tmin:.1f}–{tmax:.1f} °C")
        if tag == "after":
            ok = code == 0 and "CHICAGO" not in loc.upper() and all("CHICAGO" not in e.upper() for e in envs)
    print("RESULT:", "the run uses the chosen location and its design days" if ok else "Chicago is still used")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
