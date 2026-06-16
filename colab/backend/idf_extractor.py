import os
import json
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATASET_ROOT = os.path.join(BASE_DIR, "Datasets")
INDEX_PATH = os.path.join(os.path.dirname(__file__), "index.json")

def load_index():
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

INDEX = load_index()

def clean_idf_text(text):
    """Remove comments to avoid parsing issues and join lines."""
    lines = []
    for line in text.split('\n'):
        if '!' in line:
            line = line.split('!')[0]
        line = line.strip()
        if line:
            lines.append(line)
    return "".join(lines)  # No spaces, pure string for exact matching

def extract_raw_block(content, obj_type, obj_name):
    blocks = content.split(';')
    target = re.sub(r'\s+', '', f"{obj_type},{obj_name}").lower()
    
    for raw_block in blocks:
        if not raw_block.strip(): continue
        cleaned = clean_idf_text(raw_block).lower()
        cleaned = re.sub(r'\s+', '', cleaned)
        if cleaned.startswith(target):
            # Return original format to maintain beautiful indentation
            return raw_block.strip() + ";"
    return None

def resolve_dependencies(obj_type, obj_name, extracted_blocks=None):
    """
    Given a name, finds the IDF block. If it's a Construction, 
    it reads the materials inside and recursively extracts them too!
    """
    if extracted_blocks is None:
        extracted_blocks = {}
        
    # Search index FIRST to determine true type
    filepath = None
    true_type = obj_type
    if obj_type in INDEX and obj_name in INDEX[obj_type]:
        filepath = INDEX[obj_type][obj_name]
    else:
        # Search across all types just in case
        for t_key in INDEX:
            if obj_name in INDEX[t_key]:
                filepath = INDEX[t_key][obj_name]
                true_type = t_key
                break
                
    key = f"{true_type}::{obj_name}"
    if key in extracted_blocks:
        return extracted_blocks
        
    if not filepath:
        print(f"Warning: {obj_name} not found in Datasets.")
        return extracted_blocks
        
    with open(os.path.join(DATASET_ROOT, filepath), 'r', encoding='utf-8') as f:
        content = f.read()
        
    raw_block = extract_raw_block(content, true_type, obj_name)
    
    if raw_block:
        extracted_blocks[key] = raw_block
        
        # DEPENDENCY RESOLVER: Extract Materials from inside Constructions
        if "construction" in true_type.lower():
            # Get clean parts, ignoring newlines and comments
            clean_str = ""
            for line in raw_block.split('\n'):
                if '!' in line: line = line.split('!')[0]
                clean_str += line.strip()
            
            # e.g., Construction, Name, Layer1, Layer2;
            parts = [p.strip() for p in clean_str.split(';')[0].split(',')]
            if len(parts) > 2:
                # parts[0]=Construction, parts[1]=Name, parts[2:]=Layers (Materials)
                for layer_name in parts[2:]:
                    # Recursively fetch this material!
                    resolve_dependencies("Material", layer_name, extracted_blocks)
                    
    return extracted_blocks

def get_construction_layers(obj_name):
    """Returns a list of material names for a given construction, or None if it's not a construction."""
    filepath = None
    for t_key in INDEX:
        if "construction" in t_key.lower() and obj_name in INDEX[t_key]:
            filepath = INDEX[t_key][obj_name]
            break
    if not filepath: return None
    
    with open(os.path.join(DATASET_ROOT, filepath), 'r', encoding='utf-8') as f:
        content = f.read()
    raw_block = extract_raw_block(content, "Construction", obj_name)
    if not raw_block: return None
    
    clean_str = ""
    for line in raw_block.split('\n'):
        if '!' in line: line = line.split('!')[0]
        clean_str += line.strip()
    parts = [p.strip() for p in clean_str.split(';')[0].split(',')]
    if len(parts) > 2:
        return parts[2:]
    return None

if __name__ == "__main__":
    # TEST RUN
    print("Testing Extractor on 'Composite 2x4 Wood Stud R11'...")
    results = resolve_dependencies("Construction", "Composite 2x4 Wood Stud R11")
    
    for k, v in results.items():
        print(f"\n--- Extracted: {k} ---")
        print(v)
        
    print(f"\nTotal Blocks Extracted automatically: {len(results)}")
