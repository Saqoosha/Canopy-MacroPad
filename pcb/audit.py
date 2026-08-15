"""Geometric audit of the live board: what overlaps what.

DRC answers "does this violate a rule". This answers a blunter question --
"is anything sitting on top of anything else" -- about the things a rule
set does not know are special: the switch holes, which are free pads with
no net and so are invisible to every net-aware clearance check.

Distances are millimetres and negative means overlap. Everything is
measured between polygons, never between bounding boxes: the first version
of this file used the box of a component's pads, and a Choc hot-swap
socket is two pads 11 mm apart with the switch pin holes in the gap
between them, so it reported all six sockets as sitting on two holes each.
Thirty-three findings, every one false, every one confident. `--control`
is the run that keeps that from coming back.

Read-only. Nothing here writes to the document.
"""

import sys

import geom
import params
from bridge import execute

MIL = 0.0254

TOP = 1
BOTTOM = 2
OUTLINE = 11
MULTI = 12

# Copper-to-copper is the board's OWN rule, 0.102 mm track-to-track (which
# is itself stricter than JLCPCB's 0.0889 four-layer capability). It used
# to be a rounder, larger guess, and that guess was the wrong kind of
# wrong: routing legally at 0.13 mm produced a dozen "findings" of +0.017
# to +0.047 mm -- gaps that are fine by the rule the board is checked
# against and fine by the fab, reported as faults. An instrument stricter
# than the thing it measures does not fail safe; it fails noisy, and noise
# is what a real finding hides in.
BOARD_CLEARANCE_MM = 0.102
TRACE_TO_PAD_MM = BOARD_CLEARANCE_MM
PAD_TO_PAD_MM = BOARD_CLEARANCE_MM
# Holes keep the larger margin. They are drilled, not etched, and their
# position tolerance is a fab's, not a plotter's.
TRACE_TO_HOLE_MM = 0.20
PAD_TO_HOLE_MM = 0.20


def _fetch():
    js = """
    const out = {};
    const comps = await eda.pcb_PrimitiveComponent.getAll();
    out.comps = (comps||[]).map(c => ({
      id: c.primitiveId, des: c.designator, x: c.x, y: c.y,
      rot: c.rotation, layer: c.layer,
      fp: c.footprint && (c.footprint.name || ''),
    }));
    const pads = await eda.pcb_PrimitivePad.getAll();
    out.pads = (pads||[]).map(p => ({
      id: p.primitiveId, num: p.padNumber, x: p.x, y: p.y, r: p.rotation,
      layer: p.layer, hole: p.hole, net: p.net, pad: p.pad,
    }));
    const ls = await eda.pcb_PrimitiveLine.getAll();
    out.lines = (ls||[]).map(l => ({
      id: l.primitiveId, x1: l.startX, y1: l.startY, x2: l.endX, y2: l.endY,
      w: l.lineWidth, layer: l.layer, net: l.net,
    }));
    const pls = await eda.pcb_PrimitivePolyline.getAll();
    out.polylines = (pls||[]).map(p => ({
      id: p.primitiveId, layer: p.layer, w: p.lineWidth, net: p.net,
      poly: p.polygon && p.polygon.polygon
        ? p.polygon.polygon : (p.polygon || p.complexPolygon),
    }));
    const vs = await eda.pcb_PrimitiveVia.getAll();
    out.vias = (vs||[]).map(v => ({
      id: v.primitiveId, x: v.x, y: v.y, net: v.net,
      hole: v.holeDiameter, dia: v.diameter,
    }));
    return out;
    """
    return execute(js)


def _shares_layer(a, b):
    """Two layers touch if they are equal or either is multi-layer."""
    return a == b or a == MULTI or b == MULTI


def polyline_points(p):
    """Discrete points from the live polygon source.

    EasyEDA documents both IPCB_Polygon.discretize() and
    pcb_MathPolygon.discretize(); this client returns ``Not implemented``
    for both. The raw ``polygon.polygon`` source is available and stable.
    """
    src = p.get("poly")
    if isinstance(src, dict) and "polygon" in src:
        src = src["polygon"]
    if isinstance(src, list) and src and src[0] == "R":
        # R uses a screen-style upper-left anchor: positive height extends
        # toward decreasing board Y. Explicit L points use ordinary board Y.
        return geom.rounded_rect(src[1], src[2] - src[4],
                                 src[3], src[4], src[6])
    nums = [v for v in geom._flatten(src)
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return list(zip(nums[::2], nums[1::2]))


def board_outline(data):
    """Bounding box of the board edge, in mil.

    The edge is a single closed polyline, not four lines. It was four
    lines and the autorouter refused to start -- "Please draw a board
    outline first" -- against a rectangle that was geometrically perfect
    and closed to the mil. Four separately-created lines are four lines;
    the client wants one closed shape, and only says so at the point of
    use. Lines are still read here because a board drawn by hand may have
    them.
    """
    xs, ys = [], []
    for l in data["lines"]:
        if l["layer"] == OUTLINE:
            xs += [l["x1"], l["x2"]]
            ys += [l["y1"], l["y2"]]
    for p in data.get("polylines") or []:
        if p["layer"] != OUTLINE:
            continue
        pts = polyline_points(p)
        xs += [q[0] for q in pts]
        ys += [q[1] for q in pts]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def component_pads(data):
    """component primitiveId -> its pads, and the pads nothing owns.

    A component's pads carry the component's id as the prefix of their
    own, which is the only link the API offers.
    """
    ids = sorted((c["id"] for c in data["comps"]), key=len, reverse=True)
    owned, free = {i: [] for i in ids}, []
    for p in data["pads"]:
        for i in ids:
            if p["id"].startswith(i) and p["id"] != i:
                owned[i].append(p)
                break
        else:
            free.append(p)
    return owned, free


def pixel_openings(data):
    """The rectangular board cutout inside each reverse-mount LED.

    It belongs to the footprint, so it is not returned as a standalone pad
    or region by the board APIs. Omitting it let KEY0 and KEY3 pass only
    0.130 mm from the cut edge while every hole check reported clean.
    ``PIXEL_OPENING_MM`` is the actual footprint opening measured in
    params.py; each rectangle is transformed with its live component.
    """
    w = params.PIXEL_OPENING_MM[0] / MIL
    h = params.PIXEL_OPENING_MM[1] / MIL
    return [
        (c["des"], geom.rect(c["x"], c["y"], w, h,
                             __import__("math").radians(c["rot"])))
        for c in data["comps"] if c["des"].startswith("LED")
    ]


def _shapes(data):
    """Every drawn thing as (kind, label, layer, net, polygon)."""
    owned, free = component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    out = []
    for p in free:
        # A free pad with a hole is a switch hole; one without is stray.
        poly = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
        out.append(("hole", f"{p['num']}@({p['x']:.0f},{p['y']:.0f})",
                    p["layer"], p["net"], poly))
    for cid, pads in owned.items():
        des = by_id[cid]["des"]
        for p in pads:
            poly = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
            out.append(("pad", f"{des}.{p['num']}", p["layer"], p["net"], poly))
            if p["hole"]:
                out.append(("pad", f"{des}.{p['num']}", MULTI, p["net"],
                            geom.pad_polygon(p["x"], p["y"], p["r"], p["hole"])))
        # The part's own plastic. Pads alone said the middle of an SOP-8
        # was empty and let a footprint be considered for a spot occupied
        # by a hot-swap socket's body, and pads alone cannot answer "is
        # the crystal touching the pixel" at all -- which is a question
        # that got asked, of a picture, because nothing here could answer
        # it. Body-vs-hole is deliberately not a finding: a socket sits
        # over its own switch's pin holes by design.
        c = by_id[cid]
        body = geom.body_polygon(c["fp"], c["x"], c["y"], c["rot"], 1.0 / MIL)
        if body:
            out.append(("body", des, c["layer"], "", body))
    for des, poly in pixel_openings(data):
        out.append(("cutout", f"{des} opening", MULTI, "", poly))
    for l in data["lines"]:
        if l["layer"] not in (TOP, BOTTOM):
            continue
        out.append(("trace", l["id"][:8], l["layer"], l["net"],
                    geom.segment(l["x1"], l["y1"], l["x2"], l["y2"], l["w"])))
    for v in data["vias"]:
        out.append(("via", v["id"][:8], MULTI, v["net"],
                    geom.pad_polygon(v["x"], v["y"], 0, ["ROUND", v["dia"]])))
    return out


BODY_TO_BODY_MM = 0.20
BODY_TO_PAD_MM = 0.10


def _limit(ka, kb):
    kinds = {ka, kb}
    if "body" in kinds:
        return BODY_TO_BODY_MM if kinds == {"body"} else BODY_TO_PAD_MM
    if "hole" in kinds or "cutout" in kinds:
        return TRACE_TO_HOLE_MM if "trace" in kinds else PAD_TO_HOLE_MM
    if "trace" in kinds:
        return TRACE_TO_PAD_MM if "pad" in kinds else TRACE_TO_PAD_MM
    return PAD_TO_PAD_MM


def findings(data, limit_scale=1.0):
    """Every too-close pair, worst first.

    Same net is not a finding: a trace is supposed to land on its pad. A
    hole has no net and so is never excused by this.
    """
    shapes = _shapes(data)
    out = []
    for i in range(len(shapes)):
        ka, la, ly_a, na, pa = shapes[i]
        for j in range(i + 1, len(shapes)):
            kb, lb, ly_b, nb, pb = shapes[j]
            if la == lb:
                continue          # two pads of one part, or a trace with itself
            if "body" in (ka, kb) and {ka, kb} - {"body", "pad"}:
                # A body is a mechanical model and only two questions about
                # it are real: does this part hit another part, and does it
                # sit on another part's pad. It is NOT a copper obstacle.
                # Traces and vias run under component bodies all the time --
                # solder mask is what separates them -- and testing against
                # those produced fifty findings, every one of them a normal
                # board. Holes are excluded for a different reason: a socket
                # covers its own switch's pin holes by design.
                continue
            if not _shares_layer(ly_a, ly_b):
                continue
            if na and nb and na == nb:
                continue
            owner_a = la.split(".")[0].split()[0]
            owner_b = lb.split(".")[0].split()[0]
            if owner_a == owner_b and {ka, kb} <= {"pad", "body", "cutout"}:
                # One component's own copper, body and board opening. The
                # SK6812MINI-E intentionally leaves only 0.050 mm from its
                # four pads to its own rectangular opening; that footprint
                # fact must not exempt any *other* trace from the cut edge.
                continue
            lim = _limit(ka, kb) * limit_scale
            d = geom.distance(pa, pb) * MIL
            if d < lim:
                out.append((f"{ka}-{kb}", d,
                            f"{la} ({na or '-'}) vs {lb} ({nb or '-'})"))
    out.sort(key=lambda f: f[1])
    return out


def summary(data):
    owned, free = component_pads(data)
    return {
        "components": len(data["comps"]),
        "pads": len(data["pads"]),
        "free pads (switch holes)": len(free),
        "traces": len([l for l in data["lines"] if l["layer"] in (TOP, BOTTOM)]),
        "outline": ("one closed polyline"
                    if any(p["layer"] == OUTLINE
                           for p in data.get("polylines") or [])
                    else f'{len([l for l in data["lines"] if l["layer"] == OUTLINE])} loose lines'),
        "vias": len(data["vias"]),
    }


def control(data):
    """Negative control: the borrowed key cell must report clean.

    The switch holes, the sockets and the pixels came from a shipping
    board and are assembled and proven. If the audit accuses any of them,
    the audit is wrong -- which is exactly what happened the first time.
    """
    keep = {"LED", "SK"}
    subset = dict(data)
    subset["comps"] = [c for c in data["comps"]
                       if any(c["des"].startswith(k) for k in keep)]
    ids = [c["id"] for c in subset["comps"]]
    subset["pads"] = [p for p in data["pads"]
                      if not p["id"][:16] in {c["id"] for c in data["comps"]}
                      or any(p["id"].startswith(i) for i in ids)]
    subset["pads"] = [p for p in data["pads"]
                      if any(p["id"].startswith(i) for i in ids)
                      or not any(p["id"].startswith(c["id"])
                                 for c in data["comps"])]
    subset["lines"] = [l for l in data["lines"] if l["layer"] == OUTLINE]
    subset["vias"] = []
    f = findings(subset)
    print(f"control: key cell only -- {len(subset['comps'])} components, "
          f"{len(subset['pads'])} pads")
    if f:
        print(f"  FAILED: {len(f)} findings against known-good geometry")
        for kind, d, msg in f[:12]:
            print(f"   {d:+8.3f} mm  {kind:12} {msg}")
        return False
    print("  clean, as the assembled board says it must be")
    return True


def main():
    data = _fetch()
    if "--control" in sys.argv:
        raise SystemExit(0 if control(data) else 1)

    for k, v in summary(data).items():
        print(f"  {k:28} {v}")
    bo = board_outline(data)
    if bo:
        print(f"  {'board (mm)':28} "
              f"{(bo[2]-bo[0])*MIL:.2f} x {(bo[3]-bo[1])*MIL:.2f}")
    print()

    f = findings(data)
    if not f:
        print("no overlaps found")
        return
    kinds = {}
    for kind, _, _ in f:
        kinds[kind] = kinds.get(kind, 0) + 1
    print(f"{len(f)} findings: " +
          ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())))
    print()
    for kind, d, msg in f[:60]:
        print(f"  {d:+8.3f} mm  {kind:12} {msg}")
    if len(f) > 60:
        print(f"  ... {len(f) - 60} more")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
