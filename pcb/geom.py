"""Polygon distance, so an overlap finding means an overlap.

The first version of the audit measured components by the bounding box of
their pads. A Choc hot-swap socket is two pads 11 mm apart with nothing
between them, and the switch pin holes sit in exactly that nothing -- so
every socket was reported as sitting on two holes it was borrowed,
verbatim, from a shipping board to clear. Thirty-three findings, all
false, all confident.

The fix is to stop approximating. Every pad, hole and trace becomes a
convex polygon, and distance is measured between polygons: negative when
they overlap, positive when they do not, and never a summary of a shape
that has a hole in the middle of it.
"""

import math

CIRCLE_SEGMENTS = 24


def circle(cx, cy, r, n=CIRCLE_SEGMENTS):
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def rect(cx, cy, w, h, rot=0.0):
    a = rot
    ca, sa = math.cos(a), math.sin(a)
    hw, hh = w / 2.0, h / 2.0
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca)
            for x, y in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]


def rounded_rect(x, y, w, h, radius, segments_per_corner=6):
    """Clockwise points for an axis-aligned rounded rectangle."""
    r = min(radius, w / 2.0, h / 2.0)
    if r <= 0:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    out = []
    for cx, cy, start in (
            (x + w - r, y + r, -math.pi / 2),
            (x + w - r, y + h - r, 0),
            (x + r, y + h - r, math.pi / 2),
            (x + r, y + r, math.pi)):
        for i in range(segments_per_corner + 1):
            a = start + i * math.pi / 2 / segments_per_corner
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def stadium(cx, cy, w, h, rot=0.0, n=CIRCLE_SEGMENTS):
    """A rounded-end slot: the OVAL pad and SLOT hole shapes."""
    r = min(w, h) / 2.0
    d = (max(w, h) - 2 * r) / 2.0
    horiz = w >= h
    pts = []
    for sign in (1, -1):
        c = (sign * d, 0.0) if horiz else (0.0, sign * d)
        base = 0.0 if sign > 0 else math.pi
        if not horiz:
            base = math.pi / 2 if sign > 0 else -math.pi / 2
        for i in range(n // 2 + 1):
            t = base - math.pi / 2 + math.pi * i / (n // 2)
            pts.append((c[0] + r * math.cos(t), c[1] + r * math.sin(t)))
    ca, sa = math.cos(rot), math.sin(rot)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def segment(x1, y1, x2, y2, width, n=CIRCLE_SEGMENTS):
    """A trace: the swept area of a round-capped stroke of `width`."""
    r = width / 2.0
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return circle(x1, y1, r, n)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    pts = []
    for i in range(n // 2 + 1):
        t = math.pi * i / (n // 2)
        c, s = math.cos(t), math.sin(t)
        pts.append((x2 + r * (ux * s + nx * c), y2 + r * (uy * s + ny * c)))
    for i in range(n // 2 + 1):
        t = math.pi * i / (n // 2)
        c, s = math.cos(t), math.sin(t)
        pts.append((x1 - r * (ux * s + nx * c), y1 - r * (uy * s + ny * c)))
    return pts


def pad_polygon(x, y, rot, shape):
    """One `pad` or `hole` field from the client, as a polygon.

    `rot` is RADIANS. A component's rotation is degrees and a pad's is
    radians, in the same document, from the same client -- the only sixteen
    rotated pads on this board are the USB-C connector's, and reading them
    as degrees would have turned pi/2 into 1.6 degrees and left the shield
    tabs lying flat across the board edge with nothing complaining.

    A POLYGON pad is different again: its points are already in board
    coordinates and already rotated, so it takes neither the translation
    nor the rotation. Its list is a path -- 'L' and 'ARC' tokens sit
    between the numbers -- and arcs are approximated by their endpoints,
    which is conservative for a keep-out and not for anything else.
    """
    if not shape:
        return None
    kind = shape[0]
    if kind in ("ELLIPSE", "ROUND"):
        d = shape[1] if len(shape) < 3 else max(shape[1], shape[2])
        return circle(x, y, d / 2.0)
    if kind in ("OVAL", "SLOT"):
        return stadium(x, y, shape[1], shape[2], rot)
    if kind in ("RECT", "ROUNDRECT"):
        return rect(x, y, shape[1], shape[2], rot)
    if kind == "POLYGON":
        nums = [v for v in _flatten(shape[1])
                if isinstance(v, (int, float)) and not isinstance(v, bool)]
        pts = list(zip(nums[::2], nums[1::2]))
        if len(pts) < 3:
            raise ValueError(f"POLYGON pad with {len(pts)} points")
        return pts
    # Unknown shape: refuse rather than guess a size. The caller must see
    # this, because a silently-skipped pad is a check that cannot fire.
    raise ValueError(f"unknown pad shape {kind!r}")


import re

# `[-_]L`, not `-L`: every one of these names spells it `SOP-8_L5.3-W5.3`,
# with an underscore before the L, and a pattern anchored on the hyphen
# matched nothing at all. It did not fail -- it returned None for every
# part on the board, which reads exactly like "this footprint declares no
# body" and let a QFN-56 be placed as if it were four rows of pads with
# air in the middle. `bodies()` exists so that silence has to be listed.
_LW = re.compile(r"[-_]L(\d+(?:\.\d+)?)-W(\d+(?:\.\d+)?)")

# Footprints that genuinely state no body, and do not need one: a chip
# resistor or capacitor is smaller than its own pads, so the pads already
# bound it, and the USB-C receptacle is the one part whose position the
# case fixes rather than this file.
NO_BODY_EXPECTED = ("C0402", "R0402", "USB-C_SMD-TYPE-C-31-M-12_1")

# Footprints whose name carries no dimensions and whose body matters. The
# Choc hot-swap socket is the one that does: its two pads are 11 mm apart
# with the switch pin holes between them, so pads alone say the middle is
# empty and a part placed there would sit on 5 mm of plastic.
#
# The numbers are case/params.py's SOCKET_LOCAL -- measured from the same
# crkbd cell the pads were borrowed from, already grown for the moulding --
# expressed here relative to the footprint origin rather than the switch
# centre, which is where SOCKET_OFFSET_MM puts that origin.
BODY_OVERRIDE_MM = {
    "CONN-SMD_HOTPLUGPAKAGE__C9900010116": (14.0, 5.2),
}


def body_polygon(footprint_name, cx, cy, rot_deg, mil_per_mm):
    """The part's body, from its footprint name, or None if unknown.

    LCSC's footprint names state the body as `-L<len>-W<wid>-`, in
    millimetres, with L along x at zero rotation. Verified against four
    of this board's parts before it was trusted: the SOT-23-6's 2.9 x 1.6
    sits inside a 2.43 x 3.37 pad span the right way round, and the
    crystal's 3.2 x 2.5 inside 3.60 x 2.75.

    A name that does not state one returns None rather than a guess. The
    caller then knows only the pads, which is the truth -- and a fallback
    of "body = bounding box of the pads" would be worse than nothing here,
    because for the socket that box contains the switch holes.
    """
    if not footprint_name:
        return None
    wh = BODY_OVERRIDE_MM.get(footprint_name)
    if wh is None:
        m = _LW.search(footprint_name)
        if not m:
            return None
        wh = (float(m.group(1)), float(m.group(2)))
    return rect(cx, cy, wh[0] * mil_per_mm, wh[1] * mil_per_mm,
                math.radians(rot_deg))


def _flatten(v):
    """Every scalar inside nested lists and dicts, in order.

    Dicts are walked too, because the client wraps geometry inconsistently:
    a pad's POLYGON field is a bare list, and a polyline's `polygon` field
    is an object with a `polygon` list inside it. A version of this that
    only descended into lists returned nothing for the second, which read
    as "this board has no outline" -- for a board whose outline was right
    there.
    """
    if isinstance(v, dict):
        for x in v.values():
            yield from _flatten(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _flatten(x)
    else:
        yield v


def point_in_or_near(px, py, poly, tol):
    """Is the point inside the polygon, or within `tol` of its edge?"""
    inside = True
    n = len(poly)
    best = float("inf")
    for k in range(n):
        ax, ay = poly[k]
        bx, by = poly[(k + 1) % n]
        ex, ey = bx - ax, by - ay
        L2 = ex * ex + ey * ey
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * ex
                                                   + (py - ay) * ey) / L2))
        best = min(best, math.hypot(px - (ax + t * ex), py - (ay + t * ey)))
        if (bx - ax) * (py - ay) - (by - ay) * (px - ax) < 0:
            inside = False
    return inside or best <= tol


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _seg_seg_dist(a, b, c, d):
    def pt_seg(p, s, e):
        sx, sy = e[0] - s[0], e[1] - s[1]
        L2 = sx * sx + sy * sy
        if L2 == 0.0:
            return math.hypot(p[0] - s[0], p[1] - s[1])
        t = max(0.0, min(1.0, ((p[0] - s[0]) * sx + (p[1] - s[1]) * sy) / L2))
        return math.hypot(p[0] - (s[0] + t * sx), p[1] - (s[1] + t * sy))
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


def _axes(poly):
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L > 1e-12:
            yield (-dy / L, dx / L)


def _project(poly, ax):
    vs = [p[0] * ax[0] + p[1] * ax[1] for p in poly]
    return min(vs), max(vs)


def penetration(a, b):
    """Overlap depth of two convex polygons, or None if they are apart.

    Separating-axis: the smallest overlap across every edge normal is how
    far one would have to move to come apart.
    """
    depth = float("inf")
    for ax in list(_axes(a)) + list(_axes(b)):
        a0, a1 = _project(a, ax)
        b0, b1 = _project(b, ax)
        if a1 < b0 or b1 < a0:
            return None
        depth = min(depth, min(a1 - b0, b1 - a0))
    return depth


def distance(a, b):
    """Signed gap between two convex polygons: negative means overlap.

    Cheap reject on bounding boxes first -- this runs O(n^2) over a few
    hundred shapes and the boxes throw out almost all of it.
    """
    ax0, ay0, ax1, ay1 = bbox(a)
    bx0, by0, bx1, by1 = bbox(b)
    dx = max(ax0 - bx1, bx0 - ax1)
    dy = max(ay0 - by1, by0 - ay1)
    if dx > 0 or dy > 0:
        gap = math.hypot(max(dx, 0.0), max(dy, 0.0))
        if gap > 0:
            # Boxes are apart, so the shapes are at least this far apart.
            # Fall through only when the box gap is small enough that the
            # exact answer could still matter to a caller's threshold.
            if gap > 50.0:
                return gap
    pen = penetration(a, b)
    if pen is not None:
        return -pen
    best = float("inf")
    for i in range(len(a)):
        for j in range(len(b)):
            best = min(best, _seg_seg_dist(
                a[i], a[(i + 1) % len(a)], b[j], b[(j + 1) % len(b)]))
    return best
