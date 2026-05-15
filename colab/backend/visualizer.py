import os
import plotly.graph_objects as go

def generate_3d_html(idf_path, output_path):
    """
    Parses an EnergyPlus IDF file for geometry objects and generates an interactive 3D HTML plot.
    """
    with open(idf_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    surfaces = []
    current_type = None
    current_fields = []
    
    # Simple IDF parser for geometry
    # Read all lines, strip comments, join into one string, split by ';'
    full_text = ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith('!'):
            continue
        line_no_comment = line.split('!')[0].strip()
        full_text += line_no_comment

    objects = full_text.split(';')
    for obj in objects:
        if not obj.strip():
            continue
        fields = [f.strip() for f in obj.split(',')]
        if not fields:
            continue
            
        obj_type = fields[0]
        if obj_type in ["BuildingSurface:Detailed", "FenestrationSurface:Detailed"]:
            if len(fields) < 10:
                continue
            
            name = fields[1]
            surf_type = fields[2]
            
            num_vert_idx = 11 if obj_type == "BuildingSurface:Detailed" else 9
            try:
                num_verts = int(fields[num_vert_idx])
                vertices = []
                for i in range(num_verts):
                    x = float(fields[num_vert_idx + 1 + i*3])
                    y = float(fields[num_vert_idx + 2 + i*3])
                    z = float(fields[num_vert_idx + 3 + i*3])
                    vertices.append((x, y, z))
                surfaces.append({"name": name, "type": surf_type, "vertices": vertices})
            except Exception as e:
                print(f"Error parsing vertices for {name}: {e}")

    if not surfaces:
        print("No geometry surfaces found in IDF.")
        return False

    fig = go.Figure()
    
    # Store unique vertices to label them later without cluttering
    unique_vertices = set()

    # Color map
    colors = {
        "Wall": "rgba(200, 200, 200, 0.4)",  # Transparent gray
        "Roof": "rgba(150, 50, 50, 0.5)",    # Transparent dark red
        "Floor": "rgba(100, 100, 100, 0.6)", # Solid gray
        "Window": "rgba(50, 150, 255, 0.6)", # Transparent blue
        "Door": "rgba(139, 69, 19, 0.8)"     # Solid brown
    }
    
    line_colors = {
        "Wall": "rgb(50, 50, 50)",
        "Roof": "rgb(100, 20, 20)",
        "Floor": "rgb(30, 30, 30)",
        "Window": "rgb(20, 100, 200)",
        "Door": "rgb(80, 40, 10)"
    }

    for surf in surfaces:
        stype = surf["type"]
        name = surf["name"]
        verts = surf["vertices"]
        if len(verts) < 3:
            continue
            
        x = [v[0] for v in verts]
        y = [v[1] for v in verts]
        z = [v[2] for v in verts]
        
        # Add to unique vertices
        for v in verts:
            unique_vertices.add(v)

        # 1. Solid edges (Scatter3d line)
        # Close the loop
        xl = x + [x[0]]
        yl = y + [y[0]]
        zl = z + [z[0]]
        
        fig.add_trace(go.Scatter3d(
            x=xl, y=yl, z=zl,
            mode='lines',
            line=dict(color=line_colors.get(stype, 'black'), width=4),
            name=f"{name} (Edges)",
            showlegend=False,
            hoverinfo='skip'
        ))

        # 2. Transparent face (Mesh3d)
        # For a 4-vertex face, we need 2 triangles: (0, 1, 2) and (0, 2, 3)
        if len(verts) == 4:
            i = [0, 0]
            j = [1, 2]
            k = [2, 3]
        else:
            # simple fan triangulation for convex polygons
            i = [0] * (len(verts) - 2)
            j = list(range(1, len(verts) - 1))
            k = list(range(2, len(verts)))

        fig.add_trace(go.Mesh3d(
            x=x, y=y, z=z,
            i=i, j=j, k=k,
            color=colors.get(stype, 'rgba(100,100,100,0.5)'),
            name=name,
            opacity=1.0, # opacity handled by rgba color
            hoverinfo='name'
        ))

    # 3. Add text labels for coordinates
    vx = [v[0] for v in unique_vertices]
    vy = [v[1] for v in unique_vertices]
    vz = [v[2] for v in unique_vertices]
    v_text = [f"<b>({v[0]:.1f}, {v[1]:.1f}, {v[2]:.1f})</b>" for v in unique_vertices]
    
    fig.add_trace(go.Scatter3d(
        x=vx, y=vy, z=vz,
        mode='markers+text',
        marker=dict(size=4, color='black'),
        text=v_text,
        textposition="top center",
        textfont=dict(size=14, color="black"),
        name="Coordinates",
        hoverinfo="text"
    ))

    # 4. Global Origin Point
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0],
        mode='markers+text',
        marker=dict(size=8, color='red', symbol='diamond'),
        text=["<b>Global Origin (0,0,0)</b>"],
        textposition="bottom right",
        textfont=dict(size=16, color="red"),
        name="Origin",
        hoverinfo="skip"
    ))

    # 5. North Direction Arrow (along +Y axis)
    max_y = max(vy) if vy else 10
    fig.add_trace(go.Scatter3d(
        x=[0, 0], y=[max_y + 1, max_y + max_y*0.2 + 2], z=[0, 0],
        mode='lines+text',
        line=dict(color='green', width=8),
        text=["", "<b>⬆ NORTH</b>"],
        textposition="top center",
        textfont=dict(size=18, color="green"),
        name="North Direction",
        hoverinfo="skip"
    ))

    fig.update_layout(
        title="Generated Building Geometry",
        scene=dict(
            xaxis_title='X (m)',
            yaxis_title='Y (m)',
            zaxis_title='Z (m)',
            aspectmode='data' # Keeps the scale 1:1:1
        ),
        margin=dict(l=0, r=0, b=0, t=40)
    )

    fig.write_html(output_path)
    return True

if __name__ == "__main__":
    # Test script if run directly
    import sys
    if len(sys.argv) > 2:
        generate_3d_html(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python visualizer.py <idf_path> <output_html_path>")
