# pcb/footprint.py
"""Assert the Choc v2 footprint has every hole the switch needs.

A footprint that is missing a hole still builds, still passes DRC, and still
looks right -- it simply refuses the switch, once, on the assembled unit.

Every hole here is a standalone non-plated pad (round or, for the v2 mount,
oblong), not a component pin: the switch pins, alignment posts and v2 mount
pass through them, but the electrical connection the Choc socket makes is
its own SMD pads, placed by build.place_sockets() and unrelated to this
file.
"""
import params
from bridge import execute

MULTI = 12   # EPCB_LayerId.MULTI; the enum object is absent from the bridge
             # execution context (see build.py's TOP), so the documented
             # literal is what works.

# params.mm_to_mil() rounds to the nearest whole mil, so any single
# conversion is off the true value by at most 0.5 mil. The size this module
# asks EasyEDA to create with, and the size it later reads back and compares
# against, are each the result of one such rounding -- not necessarily the
# *same* rounding, once a hole's origin is a hand-placed pad or a different
# code path rather than this module's own place_switch_holes(). Two
# independent roundings of the same nominal value can disagree by up to
# 0.5 + 0.5 = 1 mil, so 1 mil is the tolerance below the smallest gap that
# still means "the same hole" -- and it stays far under the table's
# smallest real gap between two different sizes (post_l/post_r's Ø1.90 vs
# the centre's Ø5.00 is nowhere close; the tightest pair, v2_mount's
# 1.50 mm SLOT diameter vs post_l/post_r's Ø1.90, is still 15 mil apart:
# 59 mil vs 75 mil), so it cannot mask an actually-wrong drill.
DIAMETER_TOLERANCE_MIL = 1


def place_switch_holes(centre_mm):
    """Create every params.SWITCH_HOLES entry as a hole at centre_mm.

    A round entry (a bare diameter, mm) is drawn as an ELLIPSE pad with a
    matching ROUND hole. An oblong entry (a (width, height) mm pair --
    only v2_mount today) is drawn as an OVAL pad with a matching SLOT
    hole: EPCB_PrimitivePadHoleType has no OVAL member, only ROUND and
    SLOT (see pcb/README.md), and a live round-trip through this bridge
    confirmed `hole` comes back as `["SLOT", diameter, length]` -- diameter
    paired with width, length with height, both preserved to the mil.
    Metallization is off throughout -- a plain drilled clearance hole, not
    a plated barrel. Returns the created primitiveIds.
    """
    cx, cy = centre_mm
    ids = []
    for name, (dx, dy), size in params.SWITCH_HOLES:
        x = params.mm_to_mil(cx + dx)
        y = params.mm_to_mil(cy + dy)
        if isinstance(size, tuple):
            w = params.mm_to_mil(size[0])
            h = params.mm_to_mil(size[1])
            pad_js = f'["OVAL", {w}, {h}]'
            hole_js = f'["SLOT", {w}, {h}]'
        else:
            d = params.mm_to_mil(size)
            pad_js = f'["ELLIPSE", {d}, {d}]'
            hole_js = f'["ROUND", {d}]'
        js = (
            f"const p = await eda.pcb_PrimitivePad.create("
            f'{MULTI}, "{name}", {x}, {y}, 0, '
            f"{pad_js}, undefined, "
            f"{hole_js}, 0, 0, 0, false, 0); "
            "return p ? p.primitiveId : null;"
        )
        pid = execute(js)
        if not pid:
            raise AssertionError(f"pad create returned nothing for hole {name}")
        ids.append(pid)
    return ids


def clear_switch_holes():
    """Delete every already-placed switch-hole pad.

    Sockets and pixels are surface-mount (their pads' `hole` reads null, as
    read back and confirmed live), so every pad carrying a hole today is one
    of ours. Clearing all of them is safe and leaves the rest of the board
    untouched.
    """
    js = (
        "const all = await eda.pcb_PrimitivePad.getAll(); "
        "const holed = (all || []).filter(p => p.hole); "
        "if (holed.length) { await eda.pcb_PrimitivePad.delete("
        "holed.map(p => p.primitiveId)); } "
        "const left = await eda.pcb_PrimitivePad.getAll(); "
        "return (left || []).filter(p => p.hole).length;"
    )
    left = execute(js)
    if left:
        raise AssertionError(f"clear left {left} holed pads behind")


def _pads_near(x_mil, y_mil, radius_mil):
    # IPCB_PrimitivePad has no `holeDiameter` property -- confirmed live,
    # and absent from the class reference. The real shape is `hole`:
    # `[EPCB_PrimitivePadHoleType.ROUND, diameter]`,
    # `[EPCB_PrimitivePadHoleType.SLOT, diameter, length]`, or null for an
    # SMD pad with no hole at all. The raw tuple is returned rather than
    # collapsed to a diameter here -- ROUND and SLOT need different
    # comparisons in _hole_matches(), and a caller that only ever checked
    # `hole[0] === 'ROUND'` would silently read every SLOT hole (v2_mount)
    # as if it had no hole at all. `hole` is None for the no-hole case,
    # which is what the presence check below actually checks -- proximity
    # alone does not mean a hole is there.
    js = (
        "const all = await eda.pcb_PrimitivePad.getAll(); "
        "return (all || []).map(p => ({x: p.x, y: p.y, hole: p.hole || null}));"
    )
    pads = execute(js) or []
    return [
        p for p in pads
        if abs(p["x"] - x_mil) <= radius_mil and abs(p["y"] - y_mil) <= radius_mil
    ]


def _hole_matches(hole, want_size):
    """True if a live `hole` value matches a params.SWITCH_HOLES entry.

    want_size is a bare diameter (mm, round) or a (width, height) mm pair
    (oblong -- only v2_mount today). A ROUND hole only ever matches a bare
    diameter; a SLOT hole only ever matches a pair, diameter against width
    and length against height -- confirmed live that a SLOT round-trips as
    ["SLOT", diameter, length] with both values preserved to the mil. This
    is a strict shape match on top of the size tolerance: a round hole
    sitting where an oval was asked for (or vice versa) is a wrong hole,
    not a within-tolerance one.
    """
    if hole is None:
        return False
    kind = hole[0]
    if isinstance(want_size, tuple):
        if kind != "SLOT":
            return False
        want_w = params.mm_to_mil(want_size[0])
        want_h = params.mm_to_mil(want_size[1])
        return (
            abs(hole[1] - want_w) <= DIAMETER_TOLERANCE_MIL
            and abs(hole[2] - want_h) <= DIAMETER_TOLERANCE_MIL
        )
    if kind != "ROUND":
        return False
    want_d = params.mm_to_mil(want_size)
    return abs(hole[1] - want_d) <= DIAMETER_TOLERANCE_MIL


def _size_label(size):
    if isinstance(size, tuple):
        return f"{size[0]:.2f}x{size[1]:.2f} oval"
    return f"{size:.2f} round"


def assert_holes_present(centre_mm):
    """Every entry in params.SWITCH_HOLES must exist, as a hole, at its
    offset, matching its nominal shape and sized within
    DIAMETER_TOLERANCE_MIL.

    A pad near the right position with no hole, a hole of the wrong shape
    (ROUND where a SLOT was wanted or vice versa), or a hole of the wrong
    size all fail this -- proximity is necessary but not sufficient.
    """
    cx, cy = centre_mm
    problems = []
    for name, (dx, dy), size in params.SWITCH_HOLES:
        want_x = params.mm_to_mil(cx + dx)
        want_y = params.mm_to_mil(cy + dy)
        near = _pads_near(want_x, want_y, 4)
        holed = [p for p in near if p["hole"] is not None]
        right = [p for p in holed if _hole_matches(p["hole"], size)]
        if right:
            continue
        label = _size_label(size)
        if holed:
            got = holed[0]["hole"]
            problems.append(
                f"{name} at ({want_x}, {want_y}) has hole {got}, "
                f"wanted {label} (mm)"
            )
        else:
            problems.append(f"{name} ({label}) at ({want_x}, {want_y})")
    if problems:
        raise AssertionError("combo footprint is missing: " + "; ".join(problems))
    print(f"  [ok ] combo footprint: {len(params.SWITCH_HOLES)} holes present")
