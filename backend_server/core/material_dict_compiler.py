import os
import json

# Adjust this path based on the repository structure
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATASET_ROOT = os.path.join(BASE_DIR, "Datasets")

def clean_idf_text(text):
    """Remove comments to avoid parsing issues and join lines."""
    lines = []
    for line in text.split('\n'):
        # strip everything after '!'
        if '!' in line:
            line = line.split('!')[0]
        line = line.strip()
        if line:
            lines.append(line)
    return " ".join(lines) # Use space to join so 'A,\nB' becomes 'A, B'

def build_index():
    print(f"Scanning Datasets at: {DATASET_ROOT}")
    index = {}
    
    for dirpath, _, filenames in os.walk(DATASET_ROOT):
        for filename in filenames:
            if not filename.lower().endswith(".idf"):
                continue
                
            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, DATASET_ROOT).replace("\\", "/")
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"Failed to read {filepath}: {e}")
                continue
                
            cleaned = clean_idf_text(content)
            
            # split by semicolon to get complete objects
            objects = cleaned.split(';')
            
            for obj in objects:
                obj = obj.strip()
                if not obj: continue
                
                parts = [p.strip() for p in obj.split(',')]
                if len(parts) >= 2:
                    obj_type = parts[0]
                    obj_name = parts[1]
                    
                    if obj_type not in index:
                        index[obj_type] = {}
                        
                    # Save relative path
                    index[obj_type][obj_name] = rel_path

    # Save index
    index_path = os.path.join(os.path.dirname(__file__), "index.json")
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=4)
        
    total_objects = sum(len(v) for v in index.values())
    print(f"Success! Indexing complete. Generated index.json with {total_objects} objects across {len(index.keys())} categories.")

if __name__ == "__main__":
    build_index()
