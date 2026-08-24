"""Draw the live board to SVG, so it can be looked at without the client.

EasyEDA can show you the board, but only if you are sitting in front of
EasyEDA, and only one view at a time. The schematic round of this project
ended with "i cannot check, LOL" -- a document that was correct by every
assertion and unreadable to the person who has caught most of this
design's real faults by looking at it.

So: one file, opens in any browser, shows what is actually in the
document. `free` additionally shades every place a new part could go,
which is the map that placement should have been chosen from and was not.

    python3 plot.py            board.svg
    python3 plot.py free       board-free.svg, with the free area shaded
"""

import sys

import audit
import geom

MIL = 0.0254
SCALE = 8.0          # px per mm
PAD = 6.0            # mm of margin around the board

# Bottom-side parts are drawn lighter, the way a board looks held up to a
# light -- there is no "flip" here, both sides are shown at once, because
# what these pictures are for is finding a part on top of a hole.
STYLE = {
    "outline": ("none", "#111", 0.9),
    "hole":    ("#ffffff", "#c0392b", 0.7),
    "cutout":  ("#ffffff", "#c0392b", 0.7),
    "pad-1":   ("#c0392b", "none", 0),
    "pad-2":   ("#2471a3", "none", 0),
    # A trace polygon is the swept area of the stroke, so it is FILLED.
    # Styling it as an outline made all 116 of them invisible in a picture
    # whose entire job was showing that they cross things.
    "trace-1": ("#e74c3c", "none", 0),
    "trace-2": ("#3498db", "none", 0),
    "via":     ("#7d3c98", "none", 0),
    "free":    ("#27ae60", "none", 0),
}


def _poly(pts, kind, opacity=1.0, title=None):
    fill, stroke, sw = STYLE[kind]
    d = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
    t = f"<title>{title}</title>" if title else ""
    return (f'<polygon points="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" opacity="{opacity}">{t}</polygon>')


def render(data, shade_free=False, keep_prefixes=None):
    x0, y0, x1, y1 = audit.board_outline(data)
    w_mm = (x1 - x0) * MIL + 2 * PAD
    h_mm = (y1 - y0) * MIL + 2 * PAD

    def tx(p):
        # Board y grows upward; SVG y grows down.
        return ((p[0] - x0) * MIL + PAD, h_mm - ((p[1] - y0) * MIL + PAD))

    body = []
    if shade_free:
        for rx, ry, rw, rh in free_cells(data, keep_prefixes or ("LED", "SK")):
            a, b = tx((rx, ry)), tx((rx + rw, ry + rh))
            body.append(
                f'<rect x="{min(a[0],b[0]):.3f}" y="{min(a[1],b[1]):.3f}" '
                f'width="{abs(b[0]-a[0]):.3f}" height="{abs(b[1]-a[1]):.3f}" '
                f'fill="#27ae60" opacity="0.18"/>')

    edge = next((audit.polyline_points(p) for p in data.get("polylines") or []
                 if p["layer"] == audit.OUTLINE), None)
    if edge:
        body.append(_poly([tx(p) for p in edge], "outline"))
    else:
        body.append(_poly(
            [tx((x0, y0)), tx((x1, y0)), tx((x1, y1)), tx((x0, y1))],
            "outline"))

    owned, free = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}

    for l in data["lines"]:
        if l["layer"] not in (audit.TOP, audit.BOTTOM):
            continue
        pts = geom.segment(l["x1"], l["y1"], l["x2"], l["y2"], l["w"])
        body.append(_poly([tx(p) for p in pts], f"trace-{l['layer']}", 0.75,
                          l["net"] or "-"))

    for cid, pads in owned.items():
        des = by_id[cid]["des"]
        for p in pads:
            pts = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
            body.append(_poly([tx(q) for q in pts],
                              f"pad-{p['layer'] if p['layer'] in (1, 2) else 2}",
                              0.9, f"{des}.{p['num']} {p['net'] or '-'}"))

    for v in data["vias"]:
        pts = geom.pad_polygon(v["x"], v["y"], 0, ["ROUND", v["dia"]])
        body.append(_poly([tx(p) for p in pts], "via", 0.9, v["net"] or "-"))

    for p in free:
        pts = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
        body.append(_poly([tx(q) for q in pts], "hole", 1.0, p["num"]))

    for des, opening in audit.pixel_openings(data):
        body.append(_poly([tx(q) for q in opening], "cutout", 1.0,
                          f"{des} rectangular opening"))

    for cid, pads in owned.items():
        c = by_id[cid]
        px, py = tx((c["x"], c["y"]))
        body.append(f'<text x="{px:.2f}" y="{py:.2f}" font-size="1.6" '
                    f'font-family="monospace" fill="#000" text-anchor="middle" '
                    f'dominant-baseline="middle">{c["des"]}</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w_mm*SCALE:.0f}" height="{h_mm*SCALE:.0f}" '
            f'viewBox="0 0 {w_mm:.3f} {h_mm:.3f}">'
            f'<rect width="100%" height="100%" fill="#fdfdfa"/>'
            + "".join(body) + "</svg>")


def free_cells(data, keep_prefixes=("LED", "SK"), step=0.25, clear=0.20):
    """Every `step` cell that no kept obstacle reaches, in mil coordinates.

    "Kept" is the borrowed key cell -- the holes, the sockets, the pixels.
    Everything else is assumed to be about to move, which is the whole
    point: this is the map placement gets chosen from.
    """
    owned, free = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    boxes = []
    for p in free:
        boxes.append(geom.bbox(geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])))
    for cid, pads in owned.items():
        if not any(by_id[cid]["des"].startswith(k) for k in keep_prefixes):
            continue
        for p in pads:
            boxes.append(geom.bbox(
                geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])))
    m = clear / MIL
    boxes = [(a - m, b - m, c + m, d + m) for a, b, c, d in boxes]

    x0, y0, x1, y1 = audit.board_outline(data)
    s = step / MIL
    out = []
    yy = y0
    while yy < y1:
        run = None
        xx = x0
        while xx < x1:
            cx, cy = xx + s / 2, yy + s / 2
            ok = not any(bx0 <= cx <= bx1 and by0 <= cy <= by1
                         for bx0, by0, bx1, by1 in boxes)
            if ok:
                run = run or xx
            elif run is not None:
                out.append((run, yy, xx - run, s))
                run = None
            xx += s
        if run is not None:
            out.append((run, yy, x1 - run, s))
        yy += s
    return out


def main():
    data = audit._fetch()
    shade = "free" in sys.argv
    out = "out/board-free.svg" if shade else "out/board.svg"
    svg = render(data, shade_free=shade)
    import os
    os.makedirs("out", exist_ok=True)
    with open(out, "w") as f:
        f.write(svg)
    print(f"wrote {out} ({len(svg)/1024:.0f} kB)")
    if shade:
        cells = free_cells(data)
        area = sum(w * h for _, _, w, h in cells) * MIL * MIL
        x0, y0, x1, y1 = audit.board_outline(data)
        total = (x1 - x0) * (y1 - y0) * MIL * MIL
        print(f"free area {area:.1f} mm^2 of {total:.0f} mm^2 "
              f"({100*area/total:.0f}%)")


if __name__ == "__main__":
    main()
