"""Make EasyEDA's ratline calculation agree with the physical copper.

The router is deliberately allowed to enter any legal 0.10 mm grid cell
inside a pad.  That is electrically connected, and connect.py correctly
measures it as connected copper, but EasyEDA's ratline calculator can keep
an airwire when the copper does not cover the pad centre.  The short lines
shown on the Ratline layer were six instances of that disagreement.

The Ratlines panel identifies the exact endpoints.  There are seven ties on
six nets: four bottom-side flash pads whose top routes end on edge-overlapping
vias, two bottom-only USB VBUS pads reached through nearby route vias, and one
USB shield-to-GND-pad link.  Add only those seven shortest same-net links.

    python3 center_ties.py            report only
    python3 center_ties.py --apply    draw ties and verify every candidate
"""

import json
import math
import sys

import audit
import connect
import geom
import route
from bridge import execute


CENTER_TOL = 0.002 / audit.MIL

# Ratline endpoints selected in EasyEDA's Net panel.  These are stable pad
# names from the footprint, unlike the primitive IDs regenerated on each run.
# The mode names the diagnosed other endpoint. A pad-mode target also names
# its explicit anchor pad.
TARGETS = {
    "U1.6": ("via", None),             # QSPI_SCLK: bottom pad -> route via
    "U1.5": ("via", None),             # QSPI_SD0
    "U1.3": ("via", None),             # QSPI_SD2
    "U1.2": ("trace", None),           # QSPI_SD1: pad centre -> touching trace
    "U1.1": ("via", None),             # QSPI_SS
    "USBC1.A4B9": ("via", None),       # VBUS: pad centre -> route's safe via
    "USBC1.B4A9": ("via", None),
    "USBC1.1": ("pad", "USBC1.B1A12"),  # GND shield tab -> connector GND
}


def _layers_touch(pad, layer):
    # A drilled pad on Bottom is still bottom copper.  Only a Multi-Layer
    # pad carries copper through the stack.  Treating every `hole` as a
    # through connection hid the two genuinely missing VBUS vias.
    return pad["layer"] in (audit.MULTI, layer)


def _centre_covered(pad, data):
    """Whether a same-net trace already reaches the pad's exact centre."""
    for line in data["lines"]:
        if line["net"] != pad["net"] or line["layer"] not in (audit.TOP, audit.BOTTOM):
            continue
        if not _layers_touch(pad, line["layer"]):
            continue
        copper = geom.segment(line["x1"], line["y1"], line["x2"],
                              line["y2"], line["w"])
        # segment() points can be clockwise or counter-clockwise depending
        # on direction.  point_in_or_near() assumes one winding; a tiny
        # probe polygon makes endpoint coverage winding-independent.
        probe = geom.circle(pad["x"], pad["y"], CENTER_TOL)
        if geom.distance(copper, probe) <= 0:
            return True
    return False


def _nearest_via(pad, data):
    """Nearest same-net via whose annulus already touches ``pad``."""
    pad_poly = geom.pad_polygon(pad["x"], pad["y"], pad["r"], pad["pad"])
    best = None
    for via in data["vias"]:
        if via["net"] != pad["net"]:
            continue
        copper = geom.pad_polygon(via["x"], via["y"], 0,
                                  ["ROUND", via["dia"]])
        if geom.distance(pad_poly, copper) > connect.TOUCH_MM / audit.MIL:
            continue
        distance = math.hypot(via["x"] - pad["x"], via["y"] - pad["y"])
        item = (distance, pad["layer"], via["x"], via["y"], "via")
        if best is None or item[0] < best[0]:
            best = item
    return best


def _nearest_trace(pad, data):
    """Nearest point on same-net trace copper already touching ``pad``."""
    pad_poly = geom.pad_polygon(pad["x"], pad["y"], pad["r"], pad["pad"])
    best = None
    for line in data["lines"]:
        if line["net"] != pad["net"] or line["layer"] not in (
                audit.TOP, audit.BOTTOM):
            continue
        if not _layers_touch(pad, line["layer"]):
            continue
        copper = geom.segment(line["x1"], line["y1"], line["x2"],
                              line["y2"], line["w"])
        if geom.distance(pad_poly, copper) > connect.TOUCH_MM / audit.MIL:
            continue
        dx, dy = line["x2"] - line["x1"], line["y2"] - line["y1"]
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, (
            (pad["x"] - line["x1"]) * dx
            + (pad["y"] - line["y1"]) * dy
        ) / length2))
        x, y = line["x1"] + t * dx, line["y1"] + t * dy
        distance = math.hypot(x - pad["x"], y - pad["y"])
        item = (distance, line["layer"], x, y, "trace")
        if best is None or item[0] < best[0]:
            best = item
    return best


def _nearest_copper(pad, data):
    candidates = [candidate for candidate in (
        _nearest_via(pad, data), _nearest_trace(pad, data)
    ) if candidate is not None]
    return min(candidates, default=None, key=lambda candidate: candidate[0])


def _named_pads(data):
    owned, _ = audit.component_pads(data)
    by_id = {component["id"]: component for component in data["comps"]}
    return {
        f"{by_id[component_id]['des']}.{pad['num']}": pad
        for component_id, pads in owned.items()
        for pad in pads
    }


def plan(data):
    named = _named_pads(data)
    ties, unresolved = [], []
    for name, (mode, anchor_name) in TARGETS.items():
        pad = named.get(name)
        if pad is None:
            unresolved.append(f"{name} (missing pad)")
            continue
        if not pad["net"] or _centre_covered(pad, data):
            continue
        if mode == "pad":
            anchor = named.get(anchor_name)
            if anchor is None or anchor["net"] != pad["net"]:
                unresolved.append(f"{name} (bad anchor {anchor_name})")
                continue
            distance = math.hypot(anchor["x"] - pad["x"],
                                  anchor["y"] - pad["y"])
            layer = audit.BOTTOM
            x, y, source = anchor["x"], anchor["y"], anchor_name
        else:
            candidate = _nearest_copper(pad, data)
            if candidate is None:
                unresolved.append(name)
                continue
            distance, layer, x, y, source = candidate
        if distance <= CENTER_TOL:
            continue
        ties.append({
            "kind": "line",
            "name": name,
            "net": pad["net"],
            "layer": layer,
            "x1": pad["x"],
            "y1": pad["y"],
            "x2": x,
            "y2": y,
            "w": route.TRACE_W_MM / audit.MIL,
            "source": source,
            "distance_mm": distance * audit.MIL,
        })
    return ties, unresolved


def apply(ties):
    items = [{key: value for key, value in tie.items()
              if key in ("kind", "net", "layer", "x1", "y1", "x2", "y2",
                         "w")}
             for tie in ties]
    js = """
    const items = %s;
    let made = 0;
    for (const it of items) {
      const line = await eda.pcb_PrimitiveLine.create(
        it.net, it.layer, it.x1, it.y1, it.x2, it.y2, it.w, false);
      if (line) made += 1;
    }
    return {made, asked: items.length};
    """ % json.dumps(items)
    result = execute(js, timeout=180.0)
    if result["made"] != result["asked"]:
        raise SystemExit(f"created {result['made']} of {result['asked']} centre ties")
    return result["made"]


def main():
    import build

    build.open_project_pcb()
    ties, unresolved = plan(audit._fetch())
    print(f"  {len(ties)} EasyEDA ratline ties needed")
    for tie in ties:
        print(f"    {tie['name']:10} {tie['net']:12} {tie['distance_mm']:.3f} mm "
              f"to {tie['source']} on layer {tie['layer']}")
    if unresolved:
        print(f"  {len(unresolved)} uncovered centres have no touching copper: "
              + ", ".join(unresolved))

    if "--apply" not in sys.argv:
        print("\n(report only -- pass --apply to draw the ties)")
        return
    if unresolved:
        raise SystemExit("refusing to create a tie without its diagnosed endpoint")

    made = apply(ties)
    print(f"\n  created {made} ties")
    remaining, unresolved = plan(audit._fetch())
    if remaining or unresolved:
        raise SystemExit(
            f"centre verification failed: {len(remaining)} ties and "
            f"{len(unresolved)} unresolved pads remain"
        )
    print("  every diagnosed ratline endpoint has copper over its pad centre")


if __name__ == "__main__":
    main()
