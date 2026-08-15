"""The last orphans: route them to same-net copper, not to a plane.

Two different mistakes are being corrected here.

VBUS has no plane. stitch_hard.py listed it beside GND and 3V3 and gave
USBC1.B4A9 a via to an inner layer that carries no VBUS copper at all --
a via to nowhere, which reads as progress and connects nothing. Only GND
and 3V3 have pours; everything else is pad-to-pad.

And four of the RP2040's 3V3 pins (U3.26, .42, .43, .44) have no legal
via site within 6 mm on a board this full. They do not need one: another
3V3 pin a few tenths away is already on the plane, and reaching it is the
same connection. So the goal here is the nearest CONNECTED pad of the
same net, found from connect.py's own islands rather than assumed.

    python3 stitch_last.py            plan only
    python3 stitch_last.py --apply    draw it, then audit
"""

import math
import sys

import audit
import connect
import geom
import grid
import route

MIL = 0.0254


def orphans_and_anchors(data):
    """(orphan pad, list of connected pads) per net, from the live islands."""
    broken, _, _ = connect.analyse(connect._fetch())
    owned, _ = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    named = {}
    for cid, pads in owned.items():
        for p in pads:
            named[f"{by_id[cid]['des']}.{p['num']}"] = p

    jobs = []
    for net, islands in broken.items():
        islands = sorted(islands, key=len, reverse=True)
        anchors = [named[n] for n in islands[0] if n in named]
        if not anchors:
            continue
        for isl in islands[1:]:
            for name in isl:
                if name in named:
                    jobs.append((net, name, named[name], anchors))
    return jobs


def plan(data, verbose=True):
    g = route.build_grid(data)
    jobs = orphans_and_anchors(data)
    if verbose:
        print(f"  {len(jobs)} orphan pads: "
              f"{', '.join(n for _, n, _, _ in jobs)}")

    out, failed = [], []
    for net, name, pad, anchors in jobs:
        starts = route.pad_cells(g, pad, net)
        if not starts:
            failed.append((name, "the pad itself is blocked"))
            continue
        # Nearest anchors first: a short hop to the neighbouring pin beats
        # a long one to the far side of the board.
        anchors = sorted(anchors, key=lambda a: math.hypot(
            a["x"] - pad["x"], a["y"] - pad["y"]))
        path = None
        for a in anchors[:8]:
            goals = route.pad_cells(g, a, net)
            if not goals:
                continue
            path = g.search(starts, goals, net)
            if path:
                break
        if path is None:
            failed.append((name, "no path to any connected pad of its net"))
            continue

        drawn, drills = [], []
        for kind, p, q in grid.simplify(path):
            ax, ay = g.xy_of(p[1], p[2])
            bx, by = g.xy_of(q[1], q[2])
            if kind == "line":
                out.append({"kind": "line", "net": net, "layer": p[0],
                            "x1": round(ax, 3), "y1": round(ay, 3),
                            "x2": round(bx, 3), "y2": round(by, 3),
                            "w": round(route.TRACE_W_MM / MIL, 3)})
                drawn.append((p[0], geom.segment(ax, ay, bx, by,
                                                 route.TRACE_W_MM / MIL)))
            else:
                out.append({"kind": "via", "net": net,
                            "x": round(ax, 3), "y": round(ay, 3)})
                drawn.append((None, geom.circle(
                    ax, ay, route.VIA_OUTER_MM / 2 / MIL)))
                drills.append((ax, ay))
        inflate = (route.TRACE_W_MM / 2 + route.CLEAR_MM) / MIL
        via_inflate = (route.VIA_OUTER_MM / 2 + route.CLEAR_MM) / MIL
        for layer, poly in drawn:
            g.mark_shape(layer, poly, inflate, net)
            g.mark_shape(layer, poly, via_inflate, net, via=True)
        for x, y in drills:
            g.mark_drill(geom.circle(x, y, route.VIA_HOLE_MM / 2 / MIL),
                         (route.VIA_HOLE_MM / 2 + route.HOLE_CLEAR_MM) / MIL)
        if verbose:
            print(f"  {name:12} -> connected copper")
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
