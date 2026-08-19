"""Audit vias whose drill opening intersects a component's SMT pad.

Annular copper touching a same-net pad is normal fanout.  The manufacturing
risk begins when the drilled opening reaches the solderable pad area: during
reflow it can wick solder away from the joint unless the via is filled and
capped.  This audit therefore reports three different relationships instead
of calling every copper overlap "via-in-pad":

* centre-in-pad -- the via centre lies inside the pad;
* drill-in-pad  -- the actual drilled opening intersects the pad;
* annulus-only  -- only the via's outer copper overlaps the pad.

The board uses no via-in-pad process.  U3's exposed GND pad is fanned out to
ordinary vias outside its paste area by ``thermal_fanout.py``.  Therefore
every annular overlap found here is unexpected and remains a build failure.

Read-only.  Nothing here writes to the EasyEDA document.
"""

import audit
import geom

MIL = 0.0254

def classify(data):
    owned, _ = audit.component_pads(data)
    components = {c["id"]: c for c in data["comps"]}
    results = []

    for component_id, pads in owned.items():
        component = components[component_id]
        for pad in pads:
            if pad["hole"]:
                continue
            pad_poly = geom.pad_polygon(
                pad["x"], pad["y"], pad["r"], pad["pad"]
            )
            for via in data["vias"]:
                annulus = geom.circle(via["x"], via["y"], via["dia"] / 2.0)
                if geom.distance(annulus, pad_poly) > 0:
                    continue
                drill = geom.circle(via["x"], via["y"], via["hole"] / 2.0)
                centre = geom.point_in_or_near(via["x"], via["y"], pad_poly, 0)
                drill_overlap = geom.distance(drill, pad_poly) <= 0
                results.append({
                    "via_id": via["id"],
                    "component": component["des"],
                    "pad": str(pad["num"]),
                    "pad_net": pad["net"] or "",
                    "via_net": via["net"] or "",
                    "pad_x": pad["x"],
                    "pad_y": pad["y"],
                    "pad_shape": pad["pad"],
                    "via_x": via["x"],
                    "via_y": via["y"],
                    "via_hole": via["hole"],
                    "via_dia": via["dia"],
                    "x_mm": via["x"] * MIL,
                    "y_mm": via["y"] * MIL,
                    "centre": centre,
                    "drill": drill_overlap,
                    "footprint_owned": via["id"].startswith(component_id),
                })
    return results


def main():
    data = audit._fetch()
    results = classify(data)
    unexpected = results
    risky = [r for r in unexpected if r["drill"]]
    centred = [r for r in results if r["centre"]]
    annulus_only = [r for r in unexpected if not r["drill"]]

    print(f"vias: {len(data['vias'])}")
    print(f"SMT-pad annulus overlaps: {len(results)}")
    print(f"unexpected drill opening intersections: {len(risky)}")
    print(f"via centre inside SMT pad: {len(centred)}")
    print(f"unexpected SMT-pad overlaps: {len(unexpected)}")
    print(f"annulus-only same-net fanout: {len(annulus_only)}")

    for result in unexpected:
        net_mark = "same net" if result["pad_net"] == result["via_net"] else "NET MISMATCH"
        print(
            f"  {result['component']}.{result['pad']:<3} "
            f"{result['pad_net'] or '-':<14} via {result['via_net'] or '-':<14} "
            f"at ({result['x_mm']:.3f}, {result['y_mm']:.3f}) mm  "
            f"{'centre' if result['centre'] else 'edge'}  {net_mark}"
        )

        touching_lines = []
        for line in data["lines"]:
            if line["layer"] not in (1, 2) or line["net"] != result["via_net"]:
                continue
            line_poly = geom.segment(
                line["x1"], line["y1"], line["x2"], line["y2"], line["w"]
            )
            drill_centre = geom.circle(result["via_x"], result["via_y"], 0.01)
            if geom.distance(drill_centre, line_poly) <= 0:
                touching_lines.append(line)
        if touching_lines:
            for line in touching_lines:
                print(
                    f"      L{line['layer']} w={line['w'] * MIL:.3f} mm "
                    f"({line['x1'] * MIL:.3f},{line['y1'] * MIL:.3f}) -> "
                    f"({line['x2'] * MIL:.3f},{line['y2'] * MIL:.3f})"
                )
        else:
            print("      no same-net top/bottom trace crosses via centre")

    if unexpected:
        raise SystemExit(
            f"{len(unexpected)} unexpected vias overlap SMT pads; "
            "dogbone every router-created via"
        )


if __name__ == "__main__":
    main()
