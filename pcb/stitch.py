"""Give every power pad a via down to its plane.

The two inner planes were poured and only one of them survived: GND filled,
3V3 vanished. Not a bug -- every 3V3 pad on this board is surface mount on
the bottom, so nothing reached layer 15 at all, and copper that connects to
nothing gets discarded. GND filled only because the USB-C's mounting pads
are through-hole and happened to touch it.

So the planes are not waiting for routing. They are waiting for vias, and
that is a job with no judgment in it: 73 pads, each wanting one via beside
it and a stub to reach it. Doing it here rather than leaving it to a router
also takes 73 of the board's 215 pads off the router's plate.

Not via-in-pad: a via inside a pad wicks solder away from the joint during
reflow, and this board is going to a PCBA line. Each via sits clear of its
pad with a short trace between.

Every position is checked against the same geometry `layout.py` uses -- the
switch holes, the keepouts, every other pad, and every via already placed --
before it is committed. Nothing is placed that has not been proved to fit.

    python3 stitch.py            plan only
    python3 stitch.py --apply    place the vias and stubs, then verify
"""

import json
import math
import os
import sys

import audit
import connect
import geom
from bridge import execute

MIL = 0.0254
MM = 1.0 / MIL

PLANE_NETS = ("GND", "3V3")

# From the board's own rule set: viaOuterdiameterDefault 0.45,
# viaInnerdiameterDefault 0.30. Read back rather than typed in, so a
# change to the rules cannot leave this file describing a different via.
VIA_OUTER_MM = 0.45
VIA_HOLE_MM = 0.30

CLEAR_MM = 0.20         # to anything of another net
HOLE_CLEAR_MM = 0.30    # board rule: drilled edge to drilled edge
STEP_MM = 0.10
SMT_PAD_TO_VIA_MM = 0.05

# Two attempts, in order. The first is what a via beside a discrete pad
# should look like: fat stub, via close by. The second exists for the
# RP2040 -- a 0.4 mm-pitch QFN has little room beside its pins even for a
# 0.45 mm
# via, and a 0.20 mm stub leaving a 0.20 mm pad has exactly 0.20 mm to its
# neighbours, which is the clearance, which fails. 0.15 mm buys 0.025 mm
# on each side and lets the stub walk out past the package before it needs
# a via. Five of sixty-seven pads need the second attempt and they are all
# on U3.
ATTEMPTS = [
    {"stub": 0.20, "reach": 1.60},
    {"stub": 0.15, "reach": 4.00},
    # A third, longer reach for after the signals are in. Run on an empty
    # board this file placed all 67; run after routing, with 708 traces on
    # the board, fourteen pads had nothing within 4 mm. The stub is still
    # a straight line, which is this file's real limit -- a pad hemmed in
    # on every side needs a path, not a longer ray -- so whatever still
    # fails is reported by name rather than quietly dropped.
    {"stub": 0.15, "reach": 8.00},
]


def _rules():
    js = """
    const cur = await eda.pcb_Drc.getCurrentRuleConfiguration();
    const v = cur.config.Physics["Via Size"].viaSize.form;
    return {outer: v.viaOuterdiameterDefault, hole: v.viaInnerdiameterDefault};
    """
    got = execute(js)
    return got["outer"], got["hole"]


def _obstacles(data, exclude_net=None):
    """Every piece of copper and every hole, as (polygon, bbox, net)."""
    out = []
    owned, free = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    for p in free:
        poly = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
        out.append((poly, geom.bbox(poly), None))
    for cid, pads in owned.items():
        for p in pads:
            poly = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
            out.append((poly, geom.bbox(poly), p["net"] or None))
    for v in data["vias"]:
        poly = geom.pad_polygon(v["x"], v["y"], 0, ["ROUND", v["dia"]])
        out.append((poly, geom.bbox(poly), v["net"] or None))
    # Traces. This file was written before the board had any, and left
    # them out -- so run after routing it dropped power vias straight onto
    # signal traces, 39 overlaps down to -0.182 mm. An obstacle list is
    # only as complete as the board was on the day it was written.
    for l in data["lines"]:
        if l["layer"] not in (1, 2):
            continue
        poly = geom.segment(l["x1"], l["y1"], l["x2"], l["y2"], l["w"])
        out.append((poly, geom.bbox(poly), l["net"] or None))
    # The reverse-mount pixels shine through rectangular board openings.
    # They are not EasyEDA pads or keepout regions, so they used to be
    # invisible here: the first legal-looking direction from every pixel's
    # GND pad put both its stub and via straight through the opening.  Treat
    # the actual routed-board cutout as a netless obstacle, exactly as the
    # signal router does.  A stub leaving away from the opening remains
    # legal; only copper approaching the opening is rejected.
    for _, poly in audit.pixel_openings(data):
        out.append((poly, geom.bbox(poly), None))
    return out


def _keepouts():
    js = """
    const rs = await eda.pcb_PrimitiveRegion.getAll();
    return (rs||[]).filter(r => (r.ruleType||[]).indexOf(5) >= 0)
                   .map(r => r.complexPolygon);
    """
    out = []
    for poly in execute(js):
        nums = [v for v in geom._flatten(poly)
                if isinstance(v, (int, float)) and not isinstance(v, bool)]
        # A region stored as a CIRCLE keeps its keyword, so the numbers are
        # (cx, cy, r) and pairing them as points would put a keepout in the
        # wrong place. Read the keyword.
        flat = list(geom._flatten(poly))
        if "CIRCLE" in flat:
            i = flat.index("CIRCLE")
            cx, cy, r = flat[i + 1], flat[i + 2], flat[i + 3]
            out.append(geom.circle(cx, cy, r))
        else:
            pts = list(zip(nums[::2], nums[1::2]))
            if len(pts) >= 3:
                out.append(pts)
    return [(p, geom.bbox(p)) for p in out]


def _clear(poly, obstacles, net, clear_mil):
    b = geom.bbox(poly)
    for opoly, ob, onet in obstacles:
        if onet is not None and onet == net:
            continue
        if (b[0] - clear_mil > ob[2] or ob[0] > b[2] + clear_mil
                or b[1] - clear_mil > ob[3] or ob[1] > b[3] + clear_mil):
            continue
        if geom.distance(poly, opoly) < clear_mil:
            return False
    return True


def plan(data, verbose=True):
    outer, hole = _rules()
    if abs(outer - VIA_OUTER_MM) > 0.02 or abs(hole - VIA_HOLE_MM) > 0.02:
        raise SystemExit(
            f"the board's default via is {outer:.3f}/{hole:.3f} mm but this "
            f"file was written for {VIA_OUTER_MM}/{VIA_HOLE_MM}")
    if verbose:
        print(f"  via {outer:.3f} mm outer, {hole:.3f} mm hole")

    owned, _ = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    outline = audit.board_outline(data)
    obstacles = _obstacles(data)
    # Same-net copper is deliberately transparent to _clear(), but a via
    # must stay off EVERY SMT pad for assembly. Without this second,
    # net-independent list a via planned for one GND capacitor can land in
    # the adjacent GND pad of another capacitor.
    smt_pads = [
        geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
        for pads in owned.values() for p in pads if not p["hole"]
    ]
    via_pad_clear = SMT_PAD_TO_VIA_MM / MIL
    keeps = _keepouts()
    if verbose:
        print(f"  {len(keeps)} no-wire regions to stay out of")

    _, plane_nets, _ = connect.analyse(connect._fetch())
    targets = []
    for cid, pads in owned.items():
        for p in pads:
            plane_layer = plane_nets.get(p["net"])
            touches_plane = (
                plane_layer is not None
                and p["layer"] in (audit.MULTI, plane_layer)
            )
            if (p["net"] in PLANE_NETS and plane_layer is not None
                    and not p["hole"] and not touches_plane):
                targets.append((f"{by_id[cid]['des']}.{p['num']}", p))
    # ONLY= narrows this to one component. The RP2040's power pins are the
    # most constrained pads on the board -- a 0.4 mm-pitch QFN has less
    # room around a pin than anything else here -- so they are stitched
    # BEFORE the signals are routed, and the rest afterwards. Run the other
    # way round, three of them (U3.42, .43, .44) end up with no legal via
    # site and no path to any 3V3 copper at all.
    only = os.environ.get("MPAD_STITCH_ONLY")
    if only:
        keep = set(only.split(","))
        targets = [t for t in targets if t[0].split(".")[0] in keep]
    only_pads = {s for s in os.environ.get("MPAD_STITCH_ONLY_PADS", "").split(",")
                 if s}
    if only_pads:
        targets = [t for t in targets if t[0] in only_pads]
    skip = {s for s in os.environ.get("MPAD_STITCH_SKIP", "").split(",") if s}
    if skip:
        targets = [t for t in targets if t[0].split(".")[0] not in skip]
    targets.sort(key=lambda t: (t[1]["net"], t[1]["x"], t[1]["y"]))

    r_mil = outer / 2.0 / MIL
    clear = CLEAR_MM / MIL
    hole_clear = HOLE_CLEAR_MM / MIL
    hole_mil = hole / MIL
    step = STEP_MM / MIL
    placed, failed = [], []

    # Pins 48 and 49 are adjacent 3V3 pins on U3's bottom edge. Routing
    # signals first traps both; giving each a via first puts two drill holes
    # in the same escape corridor. Join them to one shared via outside the
    # QFN instead. One via is ample for the two supply pins, and the two
    # short 0.15 mm stubs leave the neighbouring DVDD and USB_DP exits open.
    special = {name: p for name, p in targets if name in ("U3.48", "U3.49")}
    if len(special) == 2:
        p48, p49 = special["U3.48"], special["U3.49"]
        vx = (p48["x"] + p49["x"]) / 2.0
        vy = min(p48["y"], p49["y"]) - 0.90 / MIL
        via = geom.circle(vx, vy, r_mil)
        stubs = [geom.segment(p["x"], p["y"], vx, vy, 0.15 / MIL)
                 for p in (p48, p49)]
        if (_clear(via, obstacles, "3V3", clear)
                and all(geom.distance(via, pad) >= via_pad_clear
                        for pad in smt_pads)
                and all(_clear(s, obstacles, "3V3", clear) for s in stubs)):
            for n, p, make_via in (("U3.48", p48, True),
                                   ("U3.49", p49, False)):
                placed.append({"name": n, "net": "3V3", "px": p["x"],
                               "py": p["y"], "vx": round(vx, 3),
                               "vy": round(vy, 3), "w": 0.15,
                               "make_via": make_via,
                               "d": round(math.hypot(vx - p["x"],
                                                     vy - p["y"]) * MIL, 3)})
            obstacles.append((via, geom.bbox(via), "3V3"))
            for stub in stubs:
                obstacles.append((stub, geom.bbox(stub), "3V3"))
            targets = [(n, p) for n, p in targets if n not in special]
        else:
            raise SystemExit("shared U3.48/U3.49 fanout is no longer clear")

    drill_sites = [(v["x"], v["y"], v["hole"]) for v in data["vias"]]
    if len(special) == 2:
        drill_sites.append((vx, vy, hole_mil))

    for name, p in targets:
        pad = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
        pb = geom.bbox(pad)
        # Start just outside the pad and spiral out. Sixteen directions is
        # enough to find a gap without pretending to optimise.
        start = max(pb[2] - pb[0], pb[3] - pb[1]) / 2.0 + r_mil + clear
        best = None
        for attempt in ATTEMPTS:
            sw = attempt["stub"] / MIL
            for k in range(int(attempt["reach"] / STEP_MM) + 1):
                rad = start + k * step
                for i in range(16):
                    a = 2 * math.pi * i / 16
                    vx = p["x"] + rad * math.cos(a)
                    vy = p["y"] + rad * math.sin(a)
                    via = geom.circle(vx, vy, r_mil)
                    vb = geom.bbox(via)
                    if any(math.hypot(vx - ox, vy - oy)
                           < hole_mil / 2.0 + oh / 2.0 + hole_clear
                           for ox, oy, oh in drill_sites):
                        continue
                    if (vb[0] < outline[0] + clear
                            or vb[2] > outline[2] - clear
                            or vb[1] < outline[1] + clear
                            or vb[3] > outline[3] - clear):
                        continue
                    if any(geom.distance(via, kp) < clear
                           for kp, kb in keeps
                           if not (vb[0] > kb[2] or kb[0] > vb[2]
                                   or vb[1] > kb[3] or kb[1] > vb[3])):
                        continue
                    if any(geom.distance(via, other_pad) < via_pad_clear
                           for other_pad in smt_pads):
                        continue
                    stub = geom.segment(p["x"], p["y"], vx, vy, sw)
                    if not _clear(via, obstacles, p["net"], clear):
                        continue
                    if not _clear(stub, obstacles, p["net"], clear):
                        continue
                    best = (vx, vy, attempt["stub"])
                    break
                if best:
                    break
            if best:
                break
        if not best:
            failed.append(name)
            continue
        vx, vy, sw_mm = best
        placed.append({"name": name, "net": p["net"], "px": p["x"],
                       "py": p["y"], "vx": round(vx, 3), "vy": round(vy, 3),
                       "w": sw_mm, "make_via": True,
                       "d": round(math.hypot(vx - p["x"], vy - p["y"]) * MIL, 3)})
        drill_sites.append((vx, vy, hole_mil))
        via = geom.circle(vx, vy, r_mil)
        obstacles.append((via, geom.bbox(via), p["net"]))
        stub = geom.segment(p["x"], p["y"], vx, vy, sw_mm / MIL)
        obstacles.append((stub, geom.bbox(stub), p["net"]))

    if verbose:
        for net in PLANE_NETS:
            mine = [q for q in placed if q["net"] == net]
            if mine:
                wide = sum(1 for q in mine if q["w"] == ATTEMPTS[0]["stub"])
                vias = sum(1 for q in mine if q.get("make_via", True))
                print(f"  {net:5} {vias:3} vias / {len(mine)} pads, stub "
                      f"{min(q['d'] for q in mine):.2f}-"
                      f"{max(q['d'] for q in mine):.2f} mm, "
                      f"{wide} wide / {len(mine) - wide} narrow")
        if failed:
            print(f"  {len(failed)} pads could not take a via: "
                  f"{', '.join(failed[:10])}")
    return placed, failed


def apply(placed):
    js = """
    const vs = %s;
    const outer = %f, hole = %f;
    let vias = 0, stubs = 0;
    for (const v of vs) {
      if (v.make_via !== false) {
        const via = await eda.pcb_PrimitiveVia.create(v.net, v.vx, v.vy,
                                                      hole, outer);
        if (via) vias += 1;
      }
      const t = await eda.pcb_PrimitiveLine.create(v.net, 2, v.px, v.py,
                                                   v.vx, v.vy,
                                                   v.w / 0.0254, false);
      if (t) stubs += 1;
    }
    return {vias: vias, stubs: stubs, askedVias: vs.filter(v => v.make_via !== false).length,
            askedStubs: vs.length};
    """ % (json.dumps(placed), VIA_OUTER_MM / MIL, VIA_HOLE_MM / MIL)
    got = execute(js, timeout=280.0)
    print(f"  {got['vias']}/{got['askedVias']} vias, "
          f"{got['stubs']}/{got['askedStubs']} stubs")
    if (got["vias"] != got["askedVias"]
            or got["stubs"] != got["askedStubs"]):
        raise SystemExit("some vias or stubs were not created")


def main():
    import build
    build.open_project_pcb()
    data = audit._fetch()
    print("\nplan:")
    placed, failed = plan(data)
    if failed:
        print(f"\n  {len(failed)} pads still have nowhere to put a via. "
              f"They are NOT on their plane, and connect.py will say so.")

    if "--apply" not in sys.argv:
        print(f"\n({len(placed)} vias planned -- pass --apply to place them)")
        return

    print("\napply:")
    apply(placed)

    print("\nverify:")
    if not audit.control(audit._fetch()):
        raise SystemExit("the key cell was disturbed")
    f = audit.findings(audit._fetch())
    if f:
        for kind, d, msg in f[:15]:
            print(f"    {d:+8.3f} mm  {kind:12} {msg}")
        raise SystemExit(f"{len(f)} overlaps after stitching")
    print("  no overlaps")


if __name__ == "__main__":
    main()
