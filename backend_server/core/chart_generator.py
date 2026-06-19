import os
import plotly.graph_objects as go

# Distinct color palette for zones (rgba for faces, rgb for edges)
ZONE_PALETTE = [
    {"face": "rgba(100, 160, 220, 0.25)", "edge": "rgb(40, 100, 180)"},   # Blue
    {"face": "rgba(240, 160,  60, 0.25)", "edge": "rgb(200, 110,  10)"},  # Orange
    {"face": "rgba(100, 200, 130, 0.25)", "edge": "rgb( 30, 140,  60)"},  # Green
    {"face": "rgba(220, 100, 160, 0.25)", "edge": "rgb(170,  30, 100)"},  # Pink
    {"face": "rgba(160, 120, 220, 0.25)", "edge": "rgb(100,  50, 180)"},  # Purple
    {"face": "rgba(220, 220,  80, 0.25)", "edge": "rgb(160, 160,  10)"},  # Yellow
    {"face": "rgba(100, 210, 210, 0.25)", "edge": "rgb( 20, 150, 150)"},  # Teal
    {"face": "rgba(220, 130,  80, 0.25)", "edge": "rgb(170,  70,  20)"},  # Brown-orange
]

# Fixed surface type overrides (take precedence over zone colour)
SURF_COLORS = {
    "Roof":   {"face": "rgba(160, 60,  60, 0.45)", "edge": "rgb(120, 20, 20)"},
    "Floor":  {"face": "rgba( 80, 80,  80, 0.50)", "edge": "rgb( 30, 30, 30)"},
    "Window": {"face": "rgba( 50,150, 255, 0.55)", "edge": "rgb( 20,100,200)"},
    "Door":   {"face": "rgba(139, 69,  19, 0.75)", "edge": "rgb( 80, 40, 10)"},
    # Interior partitions — warm amber, very transparent
    "Partition": {"face": "rgba(255, 200, 80, 0.20)", "edge": "rgb(200, 140, 10)"},
}


def generate_3d_html(idf_path, output_path):
    """
    Parses an EnergyPlus IDF file for geometry objects and generates an
    interactive 3D HTML plot.  Supports both single-zone and multi-zone IDFs.
    Zones are colour-coded; interior partition walls are visually distinct.
    """
    with open(idf_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    # ------------------------------------------------------------------ #
    # 1. Lightweight IDF tokeniser                                        #
    # ------------------------------------------------------------------ #
    full_text = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('!'):
            continue
        full_text += stripped.split('!')[0].strip() + " "

    objects = [o.strip() for o in full_text.split(';') if o.strip()]

    # ------------------------------------------------------------------ #
    # 2. Collect Zone names (order matters — palette assignment)          #
    # ------------------------------------------------------------------ #
    zone_order = []          # list of zone names in IDF order
    zone_origins = {}        # zone_name -> (ox, oy, oz)
    zone_dims    = {}        # zone_name -> (L, W, H) — estimated later

    for obj in objects:
        fields = [f.strip() for f in obj.split(',')]
        if not fields:
            continue
        if fields[0].upper() == "ZONE":
            if len(fields) >= 2:
                zname = fields[1]
                zone_order.append(zname)
                ox = float(fields[3]) if len(fields) > 3 and fields[3].strip() else 0.0
                oy = float(fields[4]) if len(fields) > 4 and fields[4].strip() else 0.0
                oz = float(fields[5]) if len(fields) > 5 and fields[5].strip() else 0.0
                zone_origins[zname] = (ox, oy, oz)

    # Map zone name -> palette index
    zone_palette_idx = {zname: i % len(ZONE_PALETTE) for i, zname in enumerate(zone_order)}

    # ------------------------------------------------------------------ #
    # 3. Parse surfaces                                                   #
    # ------------------------------------------------------------------ #
    surfaces = []

    # Build a quick wall-name -> zone-name map so windows/doors can look up their zone
    wall_to_zone = {}
    for obj in objects:
        fields = [f.strip() for f in obj.split(',')]
        if not fields:
            continue
        if fields[0] == "BuildingSurface:Detailed" and len(fields) >= 5:
            wall_name = fields[1]
            zone_name = fields[4]
            wall_to_zone[wall_name] = zone_name

    for obj in objects:
        fields = [f.strip() for f in obj.split(',')]
        if not fields:
            continue

        obj_type = fields[0]
        if obj_type not in ["BuildingSurface:Detailed", "FenestrationSurface:Detailed"]:
            continue
        if len(fields) < 10:
            continue

        name      = fields[1]
        surf_type = fields[2]   # Wall / Roof / Floor / Window / Door
        if obj_type == "BuildingSurface:Detailed":
            zone_name = fields[4]
        else:
            # FenestrationSurface: no direct zone field; look up from parent wall
            parent_wall = fields[4]
            zone_name = wall_to_zone.get(parent_wall, "")

        # Detect interior partitions (Outside Boundary Condition == Surface)
        is_partition = False
        if obj_type == "BuildingSurface:Detailed":
            obc = fields[6].strip().lower() if len(fields) > 6 else ""
            if obc == "surface":
                is_partition = True

        num_vert_idx = 11 if obj_type == "BuildingSurface:Detailed" else 9
        try:
            num_verts_str = fields[num_vert_idx].strip()
            if num_verts_str:
                num_verts = int(num_verts_str)
            else:
                num_verts = (len(fields) - (num_vert_idx + 1)) // 3
            verts = []
            # Vertices in IDF are LOCAL to zone origin (Coordinate System = Relative).
            # We must add the zone origin offset to get absolute world coordinates for plotting.
            zox, zoy, zoz = zone_origins.get(zone_name, (0.0, 0.0, 0.0))
            for vi in range(num_verts):
                x = float(fields[num_vert_idx + 1 + vi*3]) + zox
                y = float(fields[num_vert_idx + 2 + vi*3]) + zoy
                z = float(fields[num_vert_idx + 3 + vi*3]) + zoz
                verts.append((x, y, z))

            surfaces.append({
                "name": name,
                "type": surf_type,
                "zone": zone_name,
                "is_partition": is_partition,
                "vertices": verts,
            })
        except Exception as e:
            print(f"[Chart Generator] Error parsing vertices for '{name}': {e}")

    if not surfaces:
        print("[Chart Generator] No geometry surfaces found in IDF.")
        return False

    # ------------------------------------------------------------------ #
    # 4. Build figure                                                     #
    # ------------------------------------------------------------------ #
    fig = go.Figure()
    unique_vertices = set()
    # Track zone bounding boxes for label placement
    zone_x_vals = {z: [] for z in zone_order}
    zone_y_vals = {z: [] for z in zone_order}
    zone_z_vals = {z: [] for z in zone_order}

    for surf in surfaces:
        stype     = surf["type"]
        zname     = surf["zone"]
        name      = surf["name"]
        verts     = surf["vertices"]
        is_part   = surf["is_partition"]

        if len(verts) < 3:
            continue

        # Accumulate zone vertices for label placement
        if zname in zone_x_vals:
            zone_x_vals[zname].extend(v[0] for v in verts)
            zone_y_vals[zname].extend(v[1] for v in verts)
            zone_z_vals[zname].extend(v[2] for v in verts)

        # ---- Determine colours ----------------------------------------
        if stype in SURF_COLORS:
            fcolor = SURF_COLORS[stype]["face"]
            ecolor = SURF_COLORS[stype]["edge"]
        elif is_part:
            fcolor = SURF_COLORS["Partition"]["face"]
            ecolor = SURF_COLORS["Partition"]["edge"]
        else:
            pidx   = zone_palette_idx.get(zname, 0)
            fcolor = ZONE_PALETTE[pidx]["face"]
            ecolor = ZONE_PALETTE[pidx]["edge"]

        x = [v[0] for v in verts]
        y = [v[1] for v in verts]
        z = [v[2] for v in verts]

        for v in verts:
            unique_vertices.add(v)

        # ---- Edges -------------------------------------------------------
        xl = x + [x[0]]
        yl = y + [y[0]]
        zl = z + [z[0]]

        fig.add_trace(go.Scatter3d(
            x=xl, y=yl, z=zl,
            mode='lines',
            line=dict(color=ecolor, width=3),
            name=f"{name} (edges)",
            showlegend=False,
            hoverinfo='skip'
        ))

        # ---- Face --------------------------------------------------------
        if len(verts) == 4:
            tri_i = [0, 0]
            tri_j = [1, 2]
            tri_k = [2, 3]
        else:
            tri_i = [0] * (len(verts) - 2)
            tri_j = list(range(1, len(verts) - 1))
            tri_k = list(range(2, len(verts)))

        hover_label = (
            f"<b>{name}</b><br>"
            f"Type: {stype}"
            + (" (Partition)" if is_part else "")
            + (f"<br>Zone: {zname}" if zname else "")
        )

        fig.add_trace(go.Mesh3d(
            x=x, y=y, z=z,
            i=tri_i, j=tri_j, k=tri_k,
            color=fcolor,
            name=name,
            opacity=1.0,          # alpha baked into fcolor rgba
            hovertemplate=hover_label + "<extra></extra>",
            showlegend=False,
        ))

    # ------------------------------------------------------------------ #
    # 5. Zone name labels at zone centroid                                #
    # ------------------------------------------------------------------ #
    if len(zone_order) > 1:
        for zname in zone_order:
            if not zone_x_vals.get(zname):
                continue
            cx = sum(zone_x_vals[zname]) / len(zone_x_vals[zname])
            cy = sum(zone_y_vals[zname]) / len(zone_y_vals[zname])
            cz = max(zone_z_vals[zname])   # top of zone

            pidx = zone_palette_idx.get(zname, 0)
            ecolor = ZONE_PALETTE[pidx]["edge"]

            fig.add_trace(go.Scatter3d(
                x=[cx], y=[cy], z=[cz + 0.3],
                mode='markers+text',
                marker=dict(size=6, color=ecolor, symbol='circle'),
                text=[f"<b>{zname}</b>"],
                textposition="top center",
                textfont=dict(size=14, color=ecolor),
                name=zname,
                showlegend=True,
                hoverinfo='skip'
            ))

    # ------------------------------------------------------------------ #
    # 6. Vertex coordinate labels (shown only when zoomed in)            #
    # ------------------------------------------------------------------ #
    vx = [v[0] for v in unique_vertices]
    vy = [v[1] for v in unique_vertices]
    vz = [v[2] for v in unique_vertices]
    v_text = [f"({v[0]:.1f}, {v[1]:.1f}, {v[2]:.1f})" for v in unique_vertices]

    fig.add_trace(go.Scatter3d(
        x=vx, y=vy, z=vz,
        mode='markers+text',
        marker=dict(size=4, color='rgba(0,0,0,0.6)'),
        text=v_text,
        textposition="top center",
        textfont=dict(size=10, color="black"),
        hovertemplate="%{text}<extra></extra>",
        name="Vertices",
        showlegend=False,
    ))

    # ------------------------------------------------------------------ #
    # 7. Global origin + North arrow                                      #
    # ------------------------------------------------------------------ #
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0],
        mode='markers+text',
        marker=dict(size=8, color='red', symbol='diamond'),
        text=["<b>Origin (0,0,0)</b>"],
        textposition="bottom right",
        textfont=dict(size=13, color="red"),
        name="Origin",
        hoverinfo='skip',
        showlegend=False,
    ))

    max_y_val = max(vy) if vy else 10
    arrow_len = max(max_y_val * 0.15, 2)
    fig.add_trace(go.Scatter3d(
        x=[0, 0], y=[max_y_val + 0.5, max_y_val + 0.5 + arrow_len], z=[0, 0],
        mode='lines+text',
        line=dict(color='green', width=6),
        text=["", "<b>N</b>"],
        textposition="top center",
        textfont=dict(size=16, color="green"),
        name="North",
        hoverinfo='skip',
        showlegend=False,
    ))

    # ------------------------------------------------------------------ #
    # 8. Layout                                                           #
    # ------------------------------------------------------------------ #
    n_zones = len(zone_order)
    title = (
        "Multi-Zone Building Geometry"
        if n_zones > 1
        else "Building Geometry"
    )
    if zone_order:
        title += f" — {n_zones} Zone{'s' if n_zones > 1 else ''}: " + ", ".join(zone_order)

    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        scene=dict(
            xaxis_title='X (m)',
            yaxis_title='Y (m)',
            zaxis_title='Z (m)',
            aspectmode='data',
        ),
        margin=dict(l=0, r=0, b=0, t=50),
        legend=dict(
            x=0.01, y=0.99,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="rgba(0,0,0,0.2)",
            borderwidth=1,
        ),
    )

    fig.write_html(output_path)
    print(f"[Chart Generator] 3D HTML saved to: {output_path}")
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        generate_3d_html(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python chart_generator.py <idf_path> <output_html_path>")

