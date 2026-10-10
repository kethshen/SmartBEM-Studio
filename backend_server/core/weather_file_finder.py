"""
Weather file resolver for SmartBEM Studio.
Downloads EPW files from NREL S3 or Firebase Storage based on the epw_url field.
"""
import os
import urllib.request


def _fetch_ddy(epw_url, epw_local_path):
    """Download the design-day file (.ddy) that sits next to the EPW in the EnergyPlus weather library.
    Used by core/site_from_weather.py for the design days (flaw A7). A failure only means the template's design days stay."""
    ddy_path = os.path.splitext(epw_local_path)[0] + ".ddy"
    if os.path.exists(ddy_path) and os.path.getsize(ddy_path) > 100:
        return ddy_path
    ddy_url = epw_url[:-4] + ".ddy" if epw_url.lower().endswith(".epw") else None
    if not ddy_url:
        return None
    try:
        req = urllib.request.Request(ddy_url, headers={"User-Agent": "SmartBEM-Studio/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        with open(ddy_path, "wb") as f:
            f.write(data)
        print(f"[Weather] Downloaded design days -> {ddy_path}")
        return ddy_path
    except Exception as e:
        print(f"[Weather] WARNING: no .ddy for this EPW ({e}); design days stay as in the template")
        return None


def resolve_epw(sim_settings, firebase_bucket=None, cache_dir="weather"):
    """
    Resolves the EPW file path for a simulation job.
    
    Priority:
    1. If sim_settings has a non-empty 'epw_url', use it:
       - If starts with 'https://' -> Download from NREL S3
       - If starts with 'firebase_storage:' -> Download from Firebase Storage
    2. Else fall back to sim_settings['weather_file'] (legacy filename)
    3. Else fall back to 'weather.epw' (absolute fallback)
    
    Returns:
        str: Local path to the EPW file.
    """
    os.makedirs(cache_dir, exist_ok=True)
    
    epw_url = sim_settings.get("epw_url", "").strip()
    
    # ---- Option 1: NREL S3 Direct URL ----
    if epw_url.startswith("https://"):
        # Extract filename from URL
        filename = epw_url.split("/")[-1]
        local_path = os.path.join(cache_dir, filename)
        
        # Cache: skip download if already exists
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            print(f"[Weather] Using cached: {local_path}")
            _fetch_ddy(epw_url, local_path)
            return local_path
        
        print(f"[Weather] Downloading from S3: {filename}...")
        try:
            req = urllib.request.Request(epw_url, headers={"User-Agent": "SmartBEM-Studio/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            with open(local_path, "wb") as f:
                f.write(data)
            print(f"[Weather] Downloaded {len(data)/1024:.1f} KB -> {local_path}")
            _fetch_ddy(epw_url, local_path)
            return local_path
        except Exception as e:
            print(f"[Weather] S3 download failed: {e}")
            # Fall through to legacy logic
    
    # ---- Option 2: Firebase Storage Upload ----
    elif epw_url.startswith("firebase_storage:"):
        storage_path = epw_url.replace("firebase_storage:", "").strip()
        filename = storage_path.split("/")[-1]
        local_path = os.path.join(cache_dir, filename)
        
        if firebase_bucket is None:
            print("[Weather] ERROR: Firebase bucket not available for custom EPW download.")
        else:
            print(f"[Weather] Downloading from Firebase Storage: {storage_path}...")
            try:
                blob = firebase_bucket.blob(storage_path)
                blob.download_to_filename(local_path)
                print(f"[Weather] Downloaded from Firebase -> {local_path}")
                return local_path
            except Exception as e:
                print(f"[Weather] Firebase download failed: {e}")
                # Fall through to legacy logic
    
    # ---- Legacy Fallback ----
    epw_name = sim_settings.get("weather_file", "weather.epw")
    
    # Check common locations
    if os.path.exists(epw_name):
        return epw_name
    elif os.path.exists(os.path.join(cache_dir, epw_name)):
        return os.path.join(cache_dir, epw_name)
    elif os.path.exists("weather.epw"):
        return "weather.epw"
    
    print(f"[Weather] WARNING: Could not find any EPW file. Using fallback: weather.epw")
    return "weather.epw"
