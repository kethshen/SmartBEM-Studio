import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR = os.path.dirname(BASE_DIR)
IDF_PATH = os.path.join(STUDIO_DIR, "hanger_chamber_master.idf")
ARTIFACT_OUT = r"C:\Users\ASUS\.gemini\antigravity-ide\brain\30f9feb6-f7e5-40c7-a4be-f148a0753aa8\idf_parameter_audit.md"

def parse_idf(idf_path):
    with open(idf_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    objects = []
    current_obj_type = None
    current_fields = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
            
        # Check if line contains inline comment
        if "!" in stripped:
            code_part, comment_part = stripped.split("!", 1)
            code_part = code_part.strip()
            comment_part = comment_part.strip()
        else:
            code_part = stripped
            comment_part = ""
            
        if not code_part:
            continue
            
        # If starting new object
        if current_obj_type is None:
            if "," in code_part:
                obj_type, val = code_part.split(",", 1)
                current_obj_type = obj_type.strip()
                val = val.strip().rstrip(",")
                current_fields.append((val, comment_part))
            elif ";" in code_part:
                obj_type = code_part.rstrip(";").strip()
                objects.append((obj_type, []))
                current_obj_type = None
                current_fields = []
            else:
                current_obj_type = code_part.strip()
        else:
            is_end = False
            if ";" in code_part:
                is_end = True
                val = code_part.rstrip(";").strip()
            else:
                val = code_part.rstrip(",").strip()
                
            current_fields.append((val, comment_part))
            
            if is_end:
                objects.append((current_obj_type, current_fields))
                current_obj_type = None
                current_fields = []
                
    return objects

def generate_audit_artifact():
    print(f"Parsing IDF file: {IDF_PATH}")
    objects = parse_idf(IDF_PATH)
    print(f"Parsed {len(objects)} EnergyPlus objects.")
    
    md_lines = [
        "# Complete EnergyPlus IDF Parameter Audit & Verification Table",
        "**Master Base File:** [`hanger_chamber_master.idf`](file:///d:/UNI/Sem%207/ME420%20Mech%20Eng%20Research%20Project/SmartBEM-Studio/hanger_chamber_master.idf)\n",
        "This artifact contains the **complete, line-by-line parameter audit** of every object in the base IDF file. Please review the current values and add comments/corrections so we can calibrate every single parameter to match your real physical rig before running the parameter tuning loops.\n",
        "---",
        "## Summary of Extracted IDF Objects\n",
        f"Total Objects Extracted: **{len(objects)}**\n",
        "| Object # | EnergyPlus Object Type | Object Name / Key | Number of Fields |",
        "|:---:|:---|:---|:---:|"
    ]
    
    # Table of object summaries
    for idx, (obj_type, fields) in enumerate(objects, start=1):
        obj_name = fields[0][0] if fields else "—"
        md_lines.append(f"| {idx} | `{obj_type}` | `{obj_name}` | {len(fields)} |")
        
    md_lines.append("\n---\n")
    md_lines.append("## Detailed Parameter Audit & Verification Table\n")
    md_lines.append("| Row # | Object Type | Object Name | Field Description / Name | Current IDF Value | Real Rig Condition / Your Correction |")
    md_lines.append("|:---:|:---|:---|:---|:---:|:---|")
    
    row_count = 0
    for idx, (obj_type, fields) in enumerate(objects, start=1):
        obj_name = fields[0][0] if fields else f"Object_{idx}"
        for f_idx, (val, comment) in enumerate(fields, start=1):
            row_count += 1
            field_desc = comment.replace("!-", "").strip() if comment else f"Field {f_idx}"
            # Escape pipe symbols for markdown table
            val_clean = str(val).replace("|", "\\|")
            field_clean = str(field_desc).replace("|", "\\|")
            obj_type_clean = str(obj_type).replace("|", "\\|")
            obj_name_clean = str(obj_name).replace("|", "\\|")
            
            md_lines.append(f"| {row_count} | `{obj_type_clean}` | `{obj_name_clean}` | {field_clean} | `{val_clean}` | |")
            
    artifact_content = "\n".join(md_lines)
    with open(ARTIFACT_OUT, "w", encoding="utf-8") as f:
        f.write(artifact_content)
        
    print(f"Generated IDF Parameter Audit Artifact ({row_count} total parameter rows) at: {ARTIFACT_OUT}")

if __name__ == "__main__":
    generate_audit_artifact()
