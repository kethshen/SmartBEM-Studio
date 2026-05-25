"""
One-time utility script to build weather_index.json from the NREL EnergyPlus master GeoJSON.
Run this once to generate web/data/weather_index.json.
"""
import json
import urllib.request
import re
import os
import sys

GEOJSON_URL = "https://raw.githubusercontent.com/NREL/EnergyPlus/develop/weather/master.geojson"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "web", "data", "weather_index.json")

def extract_url_from_html(html_string):
    """Extract the href URL from an HTML anchor tag like '<a href=URL>text</a>'."""
    match = re.search(r'href=["\']?([^"\'>\s]+\.epw)', html_string)
    if match:
        return match.group(1)
    # If no anchor tag, check if it's already a raw URL
    if html_string.startswith("http") and html_string.endswith(".epw"):
        return html_string
    return None

def main():
    print("Downloading master.geojson from NREL GitHub...")
    req = urllib.request.Request(GEOJSON_URL, headers={"User-Agent": "SmartHVAC-Studio/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    
    data = json.loads(raw)
    features = data.get("features", [])
    print(f"Parsed {len(features)} weather stations from GeoJSON.")
    
    index = []
    skipped = 0
    for feat in features:
        props = feat.get("properties", {})
        
        # Extract title (location name)
        title = props.get("title", "").strip()
        if not title:
            continue
        
        # Extract the EPW download URL — may be wrapped in <a href=...> tags
        epw_raw = props.get("epw", "")
        epw_url = extract_url_from_html(epw_raw)
        if not epw_url:
            skipped += 1
            continue
        
        # Extract coordinates for potential future map use
        coords = feat.get("geometry", {}).get("coordinates", [None, None])
        
        entry = {
            "title": title,
            "epw_url": epw_url,
            "lon": coords[0] if len(coords) > 0 else None,
            "lat": coords[1] if len(coords) > 1 else None,
        }
        index.append(entry)
    
    # Sort alphabetically by title for easier searching
    index.sort(key=lambda x: x["title"].lower())
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=None, separators=(",", ":"))  # Compact JSON
    
    file_size = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"[OK] Built weather_index.json with {len(index)} entries ({file_size:.1f} KB)")
    if skipped:
        print(f"     Skipped {skipped} entries with no valid EPW URL.")
    print(f"     Saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
