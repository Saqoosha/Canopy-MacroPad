"""The power pads a straight stub cannot reach.

stitch.py walks outward from a pad along a ray until it finds room for a
via. On an empty board that placed all 67; with 768 traces on it, fifteen
pads had no clear ray in any direction -- U3.22, U3.26, U3.33, C4.2,
LED6.3, U2.4, USBC1.B4A9 and the rest. They are not unreachable, they are
enclosed: what they need is a path around the traces, which is exactly
what grid.py does for signals.

So this routes them the same way, with one difference. The goal is not
another pad -- it is anywhere a via may legally go, from which the plane
takes over. The search therefore runs to a set of candidate via sites
rather than to a terminal, and stops at the first one it can reach.

    python3 stitch_hard.py            plan only
    python3 stitch_hard.py --apply    draw it, then audit
"""

import json
import sys

import audit
import geom
import grid
import route
import stitch
from bridge import execute

MIL = 0.0254
MM = 1.0 / MIL

# A via is a connection only when a plane exists on the other side. VBUS
# has no plane; sending it through this pass creates a via to nowhere and
# leaves the pad as an island. stitch_last.py routes VBUS to existing VBUS
# copper instead.
PLANE_NETS = ("GND", "3V3")


def unconnected_pads(data):
    """Pads of a plane net with no via and no route reaching them."""
    import connect
    broken, plane_nets, _ = connect.analyse(connect._fetch())
    want = set()
    for net, islands in broken.items():
        if net not in PLANE_NETS:
            continue
        # The big island is the one on the plane; everything else is orphaned.
        islands = sorted(islands, key=len, reverse=True)
        for isl in islands[1:]:
            for name in isl:
                want.add((net, name))
    owned, _ = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    out = []
    for cid, pads in owned.items():
        for p in pads:
            key = (p["net"], f"{by_id[cid]['des']}.{p['num']}")
            if key in want:
                out.append((key[1], p))
    return out


def plan(data, verbose=True):
    g = route.build_grid(data)
    targets = unconnected_pads(data)
    if verbose:
        print(f"  {len(targets)} pads to reach: "
              f"{', '.join(n for n, _ in targets)}")

    out, failed = [], []
    for name, p in targets:
        net = p["net"]
        starts = route.pad_cells(g, p, net)
        if not starts:
            failed.append((name, "the pad itself is fully blocked"))
            continue
        # Any cell where a via fits is a goal: the plane is on the other
        # side of it. Restricted to a band around the pad so the stub does
        # not wander the whole board to save one via.
        goals = []
        ci, cj = g.cell_of(p["x"], p["y"])
        span = int(6.0 / route.CELL_MM)
        for j in range(max(0, cj - span), min(g.ny, cj + span)):
            for i in range(max(0, ci - span), min(g.nx, ci + span)):
                if not g.free_via(i, j, net):
                    continue
                for l in g.layers:
                    if g.free_for(l, i, j, net):
                        goals.append((l, i, j))
        if not goals:
            failed.append((name, "no legal via site within 6 mm"))
            continue
        path = g.search(starts, goals, net)
        if path is None:
            failed.append((name, "no path to any via site"))
            continue

        drawn, drills = [], []
        for kind, a, b in grid.simplify(path):
            ax, ay = g.xy_of(a[1], a[2])
            bx, by = g.xy_of(b[1], b[2])
            if kind == "line":
                out.append({"kind": "line", "net": net, "layer": a[0],
                            "x1": round(ax, 3), "y1": round(ay, 3),
                            "x2": round(bx, 3), "y2": round(by, 3),
                            "w": round(route.TRACE_W_MM / MIL, 3)})
                drawn.append((a[0], geom.segment(ax, ay, bx, by,
                                                 route.TRACE_W_MM / MIL)))
            else:
                out.append({"kind": "via", "net": net,
                            "x": round(ax, 3), "y": round(ay, 3)})
                drawn.append((None, geom.circle(
                    ax, ay, route.VIA_OUTER_MM / 2 / MIL)))
                drills.append((ax, ay))
        # The end of the path is where the via to the plane goes.
        el, ei, ej = path[-1]
        ex, ey = g.xy_of(ei, ej)
        if not any(it["kind"] == "via" and abs(it["x"] - ex) < 1
                   and abs(it["y"] - ey) < 1 for it in out):
            out.append({"kind": "via", "net": net,
                        "x": round(ex, 3), "y": round(ey, 3)})
            drawn.append((None, geom.circle(ex, ey,
                                            route.VIA_OUTER_MM / 2 / MIL)))
            drills.append((ex, ey))
        inflate = (route.TRACE_W_MM / 2 + route.CLEAR_MM) / MIL
        via_inflate = (route.VIA_OUTER_MM / 2 + route.CLEAR_MM) / MIL
        for layer, poly in drawn:
            g.mark_shape(layer, poly, inflate, net)
            g.mark_shape(layer, poly, via_inflate, net, via=True)
        for x, y in drills:
            g.mark_drill(geom.circle(x, y, route.VIA_HOLE_MM / 2 / MIL),
                         (route.VIA_HOLE_MM / 2 + route.HOLE_CLEAR_MM) / MIL)
        if verbose:
            print(f"  {name:12} reached, "
                  f"{len([i for i in out if i['net'] == net])} pieces so far")
    return out, failed


def main():
    import build
    build.open_project_pcb()
    data = audit._fetch()
    print("\nplan:")
    out, failed = plan(data)
    print(f"\n  {len([i for i in out if i['kind']=='line'])} traces, "
          f"{len([i for i in out if i['kind']=='via'])} vias")
    if failed:
        print(f"  {len(failed)} still unreachable:")
        for name, why in failed:
            print(f"    {name:12} {why}")

    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to draw it)")
        return
    print("\napply:")
    route.apply(out)
    print("\nverify:")
    if not audit.control(audit._fetch()):
        raise SystemExit("the key cell was disturbed")
    f = audit.findings(audit._fetch())
    if f:
        for kind, d, msg in f[:12]:
            print(f"    {d:+8.3f} mm  {kind:12} {msg}")
        raise SystemExit(f"{len(f)} overlaps")
    print("  no overlaps")


if __name__ == "__main__":
    main()
