"""Fan the RP2040 exposed pad out to ordinary, assembly-safe GND vias.

The stock footprint put a 3x3 via array inside U3's exposed pad.  Electrically
that is excellent, but it makes the board require filled-and-capped
via-in-pad processing.  Four short bottom-layer spokes retain direct thermal
and ground paths while putting every drill opening outside the paste area.

    python3 thermal_fanout.py            verify/report only
    python3 thermal_fanout.py --apply    create missing vias and spokes
"""

import json
import sys

import audit
import geom
from bridge import execute

MIL = 0.0254
VIA_OUTER_MM = 0.45
VIA_HOLE_MM = 0.30
TRACE_W_MM = 0.20

# Offsets are in EasyEDA mil, relative to the centre of U3 pad 57.  The via
# annuli sit about 0.32 mm outside the pad; each spoke enters the pad by only
# 3 mil.  Two exits on the left and two on the bottom keep the QSPI and USB
# escape corridors on the other sides free.
FANOUT = (
    (-100.094, -48.071, -76.094, -48.071),
    (-100.094,  47.929, -76.094,  47.929),
    ( -64.094,  99.929, -64.094,  75.929),
    (  65.906,  99.929,  65.906,  75.929),
)


def _exposed_pad(data):
    owned, _ = audit.component_pads(data)
    components = {c["id"]: c for c in data["comps"]}
    found = []
    for cid, pads in owned.items():
        if components[cid]["des"] != "U3":
            continue
        found.extend(p for p in pads if str(p["num"]) == "57")
    if len(found) != 1:
        raise SystemExit(f"wanted one U3.57 exposed pad, found {len(found)}")
    pad = found[0]
    if pad["net"] != "GND" or pad["hole"]:
        raise SystemExit("U3.57 is no longer the SMT GND exposed pad")
    return pad


def targets(data):
    pad = _exposed_pad(data)
    return [
        {
            "vx": pad["x"] + vx,
            "vy": pad["y"] + vy,
            "ex": pad["x"] + ex,
            "ey": pad["y"] + ey,
        }
        for vx, vy, ex, ey in FANOUT
    ]


def _near(a, b, tolerance=0.6):
    return abs(a - b) <= tolerance


def _spokes_at(data, target, pad):
    """Bottom GND segments leaving the target via toward the exposed pad.

    EasyEDA splits or clips a line when later same-net routing lands on it,
    so the far endpoint is not stable after the complete board is drawn.
    The via endpoint, layer, net, width and inward direction are stable.
    """
    out = []
    for line in data["lines"]:
        if line["layer"] != 2 or line["net"] != "GND":
            continue
        ends = ((line["x1"], line["y1"], line["x2"], line["y2"]),
                (line["x2"], line["y2"], line["x1"], line["y1"]))
        for x1, y1, x2, y2 in ends:
            if not (_near(x1, target["vx"]) and _near(y1, target["vy"])):
                continue
            before = (x1 - pad["x"]) ** 2 + (y1 - pad["y"]) ** 2
            after = (x2 - pad["x"]) ** 2 + (y2 - pad["y"]) ** 2
            if after < before and abs(line["w"] * MIL - TRACE_W_MM) <= 0.01:
                out.append(line)
                break
    return out


def verify(data, expected):
    problems = []
    pad = _exposed_pad(data)
    pad_poly = geom.pad_polygon(pad["x"], pad["y"], pad["r"], pad["pad"])
    for i, target in enumerate(expected, 1):
        vias = [
            via for via in data["vias"]
            if _near(via["x"], target["vx"]) and _near(via["y"], target["vy"])
        ]
        if len(vias) != 1:
            problems.append(f"fanout {i}: found {len(vias)} vias")
            continue
        via = vias[0]
        if via["net"] != "GND":
            problems.append(f"fanout {i}: via net is {via['net'] or '-'}")
        if abs(via["dia"] * MIL - VIA_OUTER_MM) > 0.01:
            problems.append(f"fanout {i}: outer diameter is {via['dia'] * MIL:.3f} mm")
        if abs(via["hole"] * MIL - VIA_HOLE_MM) > 0.01:
            problems.append(f"fanout {i}: hole is {via['hole'] * MIL:.3f} mm")
        drill = geom.circle(via["x"], via["y"], via["hole"] / 2)
        if geom.distance(drill, pad_poly) <= 0:
            problems.append(f"fanout {i}: drill opening reaches U3.57")
        lines = _spokes_at(data, target, pad)
        if len(lines) != 1:
            problems.append(f"fanout {i}: found {len(lines)} bottom spokes")
    if problems:
        raise SystemExit("; ".join(problems))
    print(
        f"  four U3.57 external thermal vias: "
        f"{VIA_OUTER_MM:.2f}/{VIA_HOLE_MM:.2f} mm, no drill in pad"
    )


def apply(data, expected):
    # Refuse ambiguous partial geometry.  A clean rebuild has none; a second
    # invocation has one correct via and spoke at every target.
    missing = []
    for target in expected:
        vias = [
            via for via in data["vias"]
            if _near(via["x"], target["vx"]) and _near(via["y"], target["vy"])
        ]
        lines = _spokes_at(data, target, _exposed_pad(data))
        if not vias and not lines:
            missing.append(target)
        elif len(vias) != 1 or len(lines) != 1:
            raise SystemExit("partial or duplicate U3 thermal fanout geometry")
    if not missing:
        print("  thermal fanout already present")
        return
    js = """
    const targets = %s;
    let vias = 0, lines = 0;
    for (const t of targets) {
      const via = await eda.pcb_PrimitiveVia.create(
        "GND", t.vx, t.vy, %f, %f);
      const line = await eda.pcb_PrimitiveLine.create(
        "GND", 2, t.vx, t.vy, t.ex, t.ey, %f, false);
      if (via) vias += 1;
      if (line) lines += 1;
    }
    return {vias, lines};
    """ % (
        json.dumps(missing),
        VIA_HOLE_MM / MIL,
        VIA_OUTER_MM / MIL,
        TRACE_W_MM / MIL,
    )
    got = execute(js, timeout=120.0)
    if got != {"vias": len(missing), "lines": len(missing)}:
        raise SystemExit(f"thermal fanout creation incomplete: {got}")
    print(f"  created {got['vias']} vias and {got['lines']} spokes")


def main():
    import build

    build.open_project_pcb()
    data = audit._fetch()
    expected = targets(data)
    if "--apply" in sys.argv:
        apply(data, expected)
        data = audit._fetch()
    verify(data, expected)


if __name__ == "__main__":
    main()
