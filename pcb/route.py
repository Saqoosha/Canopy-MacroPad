"""Route the signal nets, because the client's autorouter will not.

Three runs of Route - Auto Routing produced nothing: no traces, no vias,
and no log entry. Both plausible blockers were found and fixed on the way
-- a board edge drawn as four lines instead of one closed polyline, and
two inner planes that had silently vanished when the board was widened --
and the third run was as quiet as the first.

What makes routing this by hand reasonable is the placement. Every
component is on the bottom, so a scan of the two edge channels found 24
and 11 obstacles on the bottom layer and ZERO on the top, across 139 mm.
The long runs therefore have an empty highway; only the escapes from
under a package are difficult, and those are what the grid search in
grid.py is for.

Order matters and is deliberate: the six key nets and the pixel chain are
routed first, because they are the ones with no alternative path, and a
short local net that grabbed a channel lane first would push a long one
into a detour it cannot take.

    python3 route.py            plan only
    python3 route.py --apply    draw it, then audit and check connectivity
"""

import json
import sys

import audit
import connect
import geom
import grid
from bridge import execute

MIL = 0.0254
MM = 1.0 / MIL

TOP, BOTTOM = 1, 2

# 0.13 mm is just over the economical two-layer process's 5 mil minimum.
# A 0.15 mm trace leaving the RP2040's 0.4 mm-pitch pads left only
# 0.120-0.125 mm to an adjacent pad, so it could not satisfy the matching
# 0.13 mm copper-clearance rule even on a perfectly orthogonal escape.
TRACE_W_MM = 0.13
CLEAR_MM = 0.13
CELL_MM = 0.10
# A via centre is quantised to this grid, so an exact geometric 0.13 mm
# clearance can round a few microns under the rule (C4.1 measured 0.129 mm
# in the first two-layer GND-tree pass).  Keep a small routing-only guard;
# it does not change the fabrication rule or copper dimensions.
VIA_GRID_GUARD_MM = 0.02
# Keep every drilled via in JLCPCB's ordinary-cost 0.30/0.45 mm class.  The
# 0.45 mm annulus still lets every QFN/flash transition sit outside its SMT
# pad, while the 0.30 mm drill avoids the advanced-process surcharge.
VIA_OUTER_MM = 0.45
VIA_HOLE_MM = 0.30
HOLE_CLEAR_MM = 0.30
# Keep the via annulus itself off every SMT pad, even when both carry the
# same net.  Same-net copper overlap is electrically legal, so the normal
# obstacle maps deliberately allow it; for assembly it is undesirable
# because a drill opening in the paste area can wick solder away.  A small
# positive gap also makes the intent unambiguous to manufacturing checkers
# that classify annulus overlap, rather than drill overlap, as via-in-pad.
SMT_PAD_TO_VIA_MM = 0.05

# Long first: a key net has one way out of its socket and one way into the
# MCU, and everything else has alternatives.
PLANE_NETS = ("GND", "3V3")

PRIORITY = [
    # The scarce resource is the escape from under the RP2040: 56 pins in a
    # 7 mm square, and the first route out of a corner takes the corridor
    # the next one wanted. Routed long-first, the last four U3 nets --
    # QSPI_SD3, USB_DP, USB_DM, DVDD -- came back "no path" with everything
    # else done. They are not harder; they were later. So the nets whose
    # only difficulty is leaving U3 go first, and the ones with a whole
    # empty channel to play with go last.
    # The flash now sits directly below this row. Route the whole local bus
    # before USB or DVDD consumes its escape space. Its 90-degree SOIC
    # orientation presents two signal columns to this row; route the right
    # column first because it also borders the USB escape corridor.
    "QSPI_SD0", "QSPI_SCLK", "QSPI_SD3",
    "QSPI_SS", "QSPI_SD1", "QSPI_SD2",
    "USB_DP", "USB_DM", "DVDD",
    "XIN", "XOUT", "XTAL_B",
    "KEY0", "KEY1", "KEY2", "KEY3", "KEY4", "KEY5",
    "PIXEL", "PIXEL1", "PIXEL2", "PIXEL3", "PIXEL4", "PIXEL5",
    "USB_DP_RAW", "USB_DM_RAW", "VBUS", "CC1", "CC2", "BOOT"]


def build_grid(data):
    x0, y0, x1, y1 = audit.board_outline(data)
    g = grid.Grid(x0, y0, x1, y1, CELL_MM)
    inflate = (TRACE_W_MM / 2 + CLEAR_MM) / MIL
    via_inflate = (VIA_OUTER_MM / 2 + CLEAR_MM + VIA_GRID_GUARD_MM) / MIL
    opening_inflate = (TRACE_W_MM / 2 + audit.TRACE_TO_HOLE_MM) / MIL
    opening_via_inflate = (VIA_OUTER_MM / 2 + audit.TRACE_TO_HOLE_MM) / MIL

    def block(layer, poly, net):
        g.mark_shape(layer, poly, inflate, net)
        g.mark_shape(layer, poly, via_inflate, net, via=True)

    def block_opening(poly, label):
        # A cut edge is not copper. Give both sides of a narrow passage the
        # same physical clearance, or A* hugs whichever opening it was never
        # told about. That is how KEY0/KEY3 ended up 0.130 mm from an LED
        # rectangle and 0.418 mm from the switch hole above it.
        g.mark_shape(None, poly, opening_inflate, label)
        g.mark_shape(None, poly, opening_via_inflate, label, via=True)

    owned, free = audit.component_pads(data)
    # The board edge itself.
    edge = inflate + 0.30 / MIL
    for b in ((x0 - 1e6, y0 - 1e6, x1 + 1e6, y0 + edge),
              (x0 - 1e6, y1 - edge, x1 + 1e6, y1 + 1e6),
              (x0 - 1e6, y0 - 1e6, x0 + edge, y1 + 1e6),
              (x1 - edge, y0 - 1e6, x1 + 1e6, y1 + 1e6)):
        g.mark_box(None, b, 0, "#edge")
        g.mark_box_via(b, 0, "#edge")

    for p in free:
        block_opening(
            geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"]), "#hole")
    for des, poly in audit.pixel_openings(data):
        block_opening(poly, f"#{des}-opening")
    cores = []
    for pads in owned.values():
        for p in pads:
            poly = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
            layer = None if p["hole"] else p["layer"]
            block(layer, poly, p["net"] or "#nc")
            if not p["hole"]:
                # Drill blocking is physical, not net-aware.  Inflate the
                # SMT pad by the via OUTER radius so the whole annulus, not
                # merely the hole, remains outside the solderable pad.
                g.mark_drill(
                    poly,
                    (VIA_OUTER_MM / 2 + SMT_PAD_TO_VIA_MM) / MIL,
                )
            cores.append((layer, geom.bbox(poly), p["net"] or "#nc"))
    for v in data["vias"]:
        block(None, geom.pad_polygon(v["x"], v["y"], 0,
                                     ["ROUND", v["dia"]]),
              v["net"] or "#nc")
        g.mark_drill(geom.circle(v["x"], v["y"], v["hole"] / 2),
                     (VIA_HOLE_MM / 2 + HOLE_CLEAR_MM) / MIL)
    for l in data["lines"]:
        if l["layer"] not in (TOP, BOTTOM):
            continue
        block(l["layer"], geom.segment(l["x1"], l["y1"], l["x2"],
                                       l["y2"], l["w"]),
              l["net"] or "#nc")
    # Last: give every pad its own body back, so a net can always reach
    # its own pads even where two halos contested the same cells.
    for layer, b, net in cores:
        g.stamp_core(layer, b, net)

    # KEY0 must cross the repeated narrow passage between the reverse-mount
    # LED openings and the switch centre holes.  Two grid rows are legal,
    # but their minimum edge clearances differ: y=8.0 mm gives only
    # 0.218 mm to the round hole, while y=7.9 mm gives 0.230 mm to the LED
    # opening and 0.318 mm to the round hole.  Prefer the latter -- the
    # farthest legal row on this 0.10 mm grid -- across the whole repeated
    # passage.  It remains a soft cost so the pad escapes can leave it.
    lane_x0, lane_y = g.cell_of(24.0 / MIL, 7.9 / MIL)
    lane_x1, _ = g.cell_of(109.4 / MIL, 7.9 / MIL)
    for net in ("KEY0", "KEY3"):
        g.preferred_lanes[net] = (lane_x0, lane_x1, lane_y, 0.05)
    return g


def pad_cells(g, p, net):
    """Cells a route may start or end on, for this pad.

    The pad's own cells are marked with its net, so they are free to it.
    """
    b = geom.bbox(geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"]))
    out = []
    # A drill does not make a Bottom pad into a through-pad.  The USB-C
    # footprint's B4A9/A4B9 pads have mechanical holes but copper only on
    # layer 2.  Treating every drilled pad as all-layer let VBUS routes start
    # on Top and never connect to the actual pad.  Only Multi-Layer copper
    # may be entered from either side.
    layers = g.layers if p["layer"] == audit.MULTI else [p["layer"]]
    i0, j0 = g.cell_of(b[0], b[1])
    i1, j1 = g.cell_of(b[2], b[3])
    for l in layers:
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                if g.free_for(l, i, j, net):
                    out.append((l, i, j))
    return out


def route_net(g, name, pads, out):
    """Connect every pad of one net, one terminal at a time."""
    groups = [pad_cells(g, p, name) for _, p in pads]
    if any(not c for c in groups):
        missing = [n for (n, _), c in zip(pads, groups) if not c]
        return f"{', '.join(missing)}: pad is fully blocked"
    tree = set(groups[0])
    for cells in groups[1:]:
        path = g.search(list(tree), cells, name)
        if path is None:
            return "no path"
        if name.startswith("PIXEL"):
            path = grid.chamfer_orthogonal_corners(path, g, name)
        drawn, drills = [], []
        for step in grid.simplify(path):
            kind, a, b = step
            ax, ay = g.xy_of(a[1], a[2])
            bx, by = g.xy_of(b[1], b[2])
            if kind == "line":
                out.append({"kind": "line", "net": name, "layer": a[0],
                            "x1": round(ax, 3), "y1": round(ay, 3),
                            "x2": round(bx, 3), "y2": round(by, 3),
                            "w": round(TRACE_W_MM / MIL, 3)})
                drawn.append((a[0], geom.segment(ax, ay, bx, by,
                                                 TRACE_W_MM / MIL)))
            else:
                out.append({"kind": "via", "net": name,
                            "x": round(ax, 3), "y": round(ay, 3)})
                drawn.append((None, geom.circle(ax, ay,
                                                VIA_OUTER_MM / 2 / MIL)))
                drills.append((ax, ay))
        # Everything the path touched now belongs to this net, and its
        # neighbours are blocked to others.
        inflate = (TRACE_W_MM / 2 + CLEAR_MM) / MIL
        via_inflate = (VIA_OUTER_MM / 2 + CLEAR_MM + VIA_GRID_GUARD_MM) / MIL
        for l, i, j in path:
            x, y = g.xy_of(i, j)
            tree.add((l, i, j))
        # Mark the copper that was actually DRAWN, not a dot per path
        # cell. Dots leave the span between two cells unmarked, and on a
        # diagonal step the midpoint of the real trace is half a cell
        # diagonal -- 0.071 mm -- further out than any dot. Later vias
        # landed exactly that much too close: +0.073 mm against a
        # 0.102 mm rule, twenty-seven times, with no actual overlap and
        # no way to see why from the numbers alone.
        for layer, poly in drawn:
            g.mark_shape(layer, poly, inflate, name)
            g.mark_shape(layer, poly, via_inflate, name, via=True)
        for x, y in drills:
            g.mark_drill(geom.circle(x, y, VIA_HOLE_MM / 2 / MIL),
                         (VIA_HOLE_MM / 2 + HOLE_CLEAR_MM) / MIL)
    return None


ROUND_LIMIT = 8


def plan(data, verbose=True):
    if verbose:
        probe = build_grid(data)
        print(f"  grid {probe.nx} x {probe.ny} cells of {CELL_MM} mm, "
              f"{len(probe.layers)} layers")

    owned, _ = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    nets = {}
    for cid, pads in owned.items():
        for p in pads:
            if p["net"]:
                nets.setdefault(p["net"], []).append(
                    (f"{by_id[cid]['des']}.{p['num']}", p))

    # The plane nets are not routed here. They are 73 pads that each want
    # one via to an inner layer, which stitch.py normally does after this.
    # Only U3.48 and U3.49 are pre-stitched: signal copper traps those two,
    # while pre-stitching all twelve U3 supply pins blocks the USB and crystal
    # escape corridors. A power via can usually move; a 0.4 mm-pitch signal
    # pad has only one or two cells to escape through.
    broken, _, _ = connect.analyse(connect._fetch())
    todo = [n for n in PRIORITY
            if n in broken and n in nets and n not in PLANE_NETS]
    todo += sorted(n for n in broken if n in nets and n not in PRIORITY
                   and n not in PLANE_NETS)

    # Greedy routing means whoever goes first takes the corridor, so a
    # failure is usually "you were late", not "there is no room". Hand
    # reordering just moves the failure: long-first failed on four U3
    # nets, U3-first failed on four others. So the order is learned --
    # whatever failed is promoted to the front and the whole thing is
    # replanned, until nothing fails or the set of failures stops
    # shrinking. Replanning from a clean grid each round is what makes
    # this safe; there is no partial state to unpick.
    best = None
    original = list(todo)
    locked = []
    promoted = []
    for attempt in range(1, ROUND_LIMIT + 1):
        g = build_grid(data)
        out, failed = [], []
        for name in todo:
            why = route_net(g, name, nets[name], out)
            if why:
                failed.append((name, why))
        names = [n for n, _ in failed]
        if verbose:
            print(f"  round {attempt}: {len(todo) - len(failed)}/{len(todo)} "
                  f"routed" + (f", stuck: {', '.join(names)}" if names else ""),
                  flush=True)
        # Keep the BEST round, not the last one. Round 2 of the first run
        # of this loop was worse than round 1 -- 26 routed against 28 --
        # and the loop happily returned it, because it was measuring
        # improvement and reporting whatever it had just done. Promoting
        # the failures does not monotonically help; it reshuffles who is
        # unlucky, so the search is over orderings and the answer is the
        # best one seen.
        if best is None or len(failed) < len(best[1]):
            best = (out, failed)
        if not failed:
            return best
        if attempt == ROUND_LIMIT:
            break
        # Keep every net that has ever failed at the front, in discovery
        # order. Moving only the latest failure to the front reversed the
        # hard-net order every round and cycled among USB_DP, KEY4 and KEY1:
        # each got a corridor by taking it from the previous one.
        for name in names:
            if name not in locked and name not in promoted:
                promoted.append(name)
        next_todo = locked + promoted + [
            n for n in original if n not in locked and n not in promoted]
        if next_todo == todo:
            break
        todo = next_todo
    return best


def apply(items):
    js = """
    const items = %s;
    const outer = %f, hole = %f;
    let lines = 0, vias = 0;
    for (const it of items) {
      if (it.kind === "via") {
        const v = await eda.pcb_PrimitiveVia.create(it.net, it.x, it.y,
                                                     hole, outer);
        if (v) vias += 1;
      } else {
        const l = await eda.pcb_PrimitiveLine.create(it.net, it.layer,
          it.x1, it.y1, it.x2, it.y2, it.w, false);
        if (l) lines += 1;
      }
    }
    return {lines, vias, asked: items.length};
    """ % (json.dumps(items), VIA_OUTER_MM / MIL, VIA_HOLE_MM / MIL)
    got = execute(js, timeout=280.0)
    print(f"  {got['lines']} traces, {got['vias']} vias "
          f"of {got['asked']} asked")
    if got["lines"] + got["vias"] != got["asked"]:
        raise SystemExit("some primitives were not created")


def main():
    import build
    build.open_project_pcb()
    data = audit._fetch()
    print("\nplan:")
    out, failed = plan(data)
    print(f"\n  {len([i for i in out if i['kind']=='line'])} traces, "
          f"{len([i for i in out if i['kind']=='via'])} vias, "
          f"{len(set(i['net'] for i in out))} nets")
    if failed:
        print(f"  {len(failed)} nets NOT routed:")
        for name, why in failed:
            print(f"    {name:12} {why}")

    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to draw it)")
        return
    if failed:
        raise SystemExit("refusing to apply a partial routing plan")
    print("\napply:")
    apply(out)
    print("\nverify:")
    if not audit.control(audit._fetch()):
        raise SystemExit("the key cell was disturbed")
    f = audit.findings(audit._fetch())
    if f:
        for kind, d, msg in f[:15]:
            print(f"    {d:+8.3f} mm  {kind:12} {msg}")
        raise SystemExit(f"{len(f)} overlaps after routing")
    print("  no overlaps")


if __name__ == "__main__":
    main()
