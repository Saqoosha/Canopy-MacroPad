"""Read-only checks for the visible routing details raised in review."""

import math

import audit
import board_edge
import geom
import params
import silk

MIL = 0.0254

# These two long key routes cross the narrow passage above another key's
# reverse-mount LED. The pair is geometry, not electrical association.
KEY_PASSAGES = {"KEY0": "LED2", "KEY3": "LED5"}
MAX_LANE_IMBALANCE_MM = 0.11  # one 0.10 mm router grid step, plus rounding
U4_EDGE_MIN_MM = 1.00


def _centre_holes(data):
    _, free = audit.component_pads(data)
    return [p for p in free if p["num"].upper() == "CENTRE"]


def assert_key_passages(data):
    leds = {c["des"]: c for c in data["comps"] if c["des"].startswith("LED")}
    centres = _centre_holes(data)
    openings = dict(audit.pixel_openings(data))
    for net, led_name in KEY_PASSAGES.items():
        led = leds[led_name]
        opening = openings[led_name]
        hole_pad = min(centres, key=lambda p: abs(p["x"] - led["x"]))
        hole = geom.pad_polygon(hole_pad["x"], hole_pad["y"],
                                hole_pad["r"], hole_pad["pad"])
        opening_box = geom.bbox(opening)
        hole_box = geom.bbox(hole)
        candidates = []
        for line in data["lines"]:
            if line["net"] != net or line["layer"] not in (audit.TOP, audit.BOTTOM):
                continue
            copper = geom.segment(line["x1"], line["y1"], line["x2"],
                                  line["y2"], line["w"])
            b = geom.bbox(copper)
            # It is only a "passage" when the copper actually lies between
            # the rectangular LED opening and the round centre hole.  A
            # route above both (KEY3 now does this) is safer and must not be
            # mistaken for a badly centred passage merely because it
            # crosses the LED's x coordinate.
            inside_gap = (b[1] >= opening_box[3] - 1e-3
                          and b[3] <= hole_box[1] + 1e-3)
            if b[0] <= led["x"] <= b[2] and inside_gap:
                do = geom.distance(copper, opening) * MIL
                dh = geom.distance(copper, hole) * MIL
                if do >= 0 and dh >= 0:
                    candidates.append((min(do, dh), abs(do - dh), do, dh, line))
        if not candidates:
            print(f"  {net}: avoids the narrow {led_name} passage")
            continue
        best = max(candidates, key=lambda x: x[0])
        clearance, imbalance, opening_gap, hole_gap, line = best
        if clearance < audit.TRACE_TO_HOLE_MM:
            raise SystemExit(
                f"{net} only clears {led_name} passage by {clearance:.3f} mm"
            )
        if imbalance > MAX_LANE_IMBALANCE_MM:
            raise SystemExit(
                f"{net} is not centred: LED {opening_gap:.3f} mm, "
                f"switch hole {hole_gap:.3f} mm"
            )
        y = (line["y1"] + line["y2"]) * MIL / 2
        print(
            f"  {net}: y={y:.3f} mm, LED {opening_gap:.3f} mm / "
            f"switch hole {hole_gap:.3f} mm"
        )


def assert_pixel_chamfers(data):
    nets = {"PIXEL2", "PIXEL3", "PIXEL4", "PIXEL5"}
    by_endpoint = {}
    for line in data["lines"]:
        if line["net"] not in nets or line["layer"] not in (audit.TOP, audit.BOTTOM):
            continue
        a = (line["layer"], round(line["x1"], 3), round(line["y1"], 3))
        b = (line["layer"], round(line["x2"], 3), round(line["y2"], 3))
        by_endpoint.setdefault((line["net"], a), []).append(
            (line["x2"] - line["x1"], line["y2"] - line["y1"]))
        by_endpoint.setdefault((line["net"], b), []).append(
            (line["x1"] - line["x2"], line["y1"] - line["y2"]))
    right_angles = []
    for (net, point), vectors in by_endpoint.items():
        for i, a in enumerate(vectors):
            for b in vectors[i + 1:]:
                la, lb = math.hypot(*a), math.hypot(*b)
                if la and lb and abs((a[0] * b[0] + a[1] * b[1]) / (la * lb)) < 1e-6:
                    right_angles.append((net, point))
    if right_angles:
        raise SystemExit(f"90-degree PIXEL corners remain: {right_angles}")
    print("  PIXEL2-5: no 90-degree trace corners")


def assert_u4_edge(data):
    owned, _ = audit.component_pads(data)
    comp = next(c for c in data["comps"] if c["des"] == "U4")
    shapes = [
        geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
        for p in owned[comp["id"]]
    ]
    body = geom.body_polygon(comp["fp"], comp["x"], comp["y"],
                             comp["rot"], 1.0 / MIL)
    if body:
        shapes.append(body)
    edge = geom.rounded_rect(0, 0, params.BOARD_W / MIL,
                             params.BOARD_D / MIL,
                             params.BOARD_CORNER_RADIUS / MIL)
    margins = []
    for shape in shapes:
        for point in shape:
            if not geom.point_in_or_near(point[0], point[1], edge, 0):
                raise SystemExit("U4 extends outside the rounded board")
            for i in range(len(edge)):
                margins.append(geom._seg_seg_dist(
                    point, point, edge[i], edge[(i + 1) % len(edge)]))
    margin = min(margins) * MIL
    if margin < U4_EDGE_MIN_MM:
        raise SystemExit(f"U4 edge margin is only {margin:.3f} mm")
    print(f"  U4: tightest body/pad edge margin {margin:.3f} mm")


def main():
    import build

    build.open_project_pcb()
    data = audit._fetch()
    board_edge.verify()
    silk.verify()
    assert_u4_edge(data)
    assert_key_passages(data)
    assert_pixel_chamfers(data)
    print("\nall polish checks passed")


if __name__ == "__main__":
    main()
