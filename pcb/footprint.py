# pcb/footprint.py
"""Assert the combo footprint has every hole all three switches need.

A footprint that is missing a hole still builds, still passes DRC, and still
looks right -- it simply refuses the switch, once, on the assembled unit.

Every hole here is a standalone non-plated round pad, not a component pin:
the switch pins and plate-mount posts pass through them, but the electrical
connection each MX socket makes is its own SMD pads, placed by
build.place_sockets() and unrelated to this file.
"""
import params
from bridge import execute

MULTI = 12   # EPCB_LayerId.MULTI; the enum object is absent from the bridge
             # execution context (see build.py's TOP), so the documented
             # literal is what works.


def place_switch_holes(centre_mm):
    """Create every params.SWITCH_HOLES entry as a hole at centre_mm.

    Each is drawn as an ELLIPSE pad sized to the hole with a matching ROUND
    hole and metallization off -- a plain drilled clearance hole, not a
    plated barrel. Returns the created primitiveIds.
    """
    cx, cy = centre_mm
    ids = []
    for name, (dx, dy), dia in params.SWITCH_HOLES:
        x = params.mm_to_mil(cx + dx)
        y = params.mm_to_mil(cy + dy)
        d = params.mm_to_mil(dia)
        js = (
            f"const p = await eda.pcb_PrimitivePad.create("
            f'{MULTI}, "{name}", {x}, {y}, 0, '
            f'["ELLIPSE", {d}, {d}], undefined, '
            f'["ROUND", {d}], 0, 0, 0, false, 0); '
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
    # `[EPCB_PrimitivePadHoleType.ROUND, diameter]` or null for an SMD pad
    # with no hole at all. `d` here is only used for a human-readable
    # future error, not for the presence check below.
    js = (
        "const all = await eda.pcb_PrimitivePad.getAll(); "
        "return (all || []).map(p => ({x: p.x, y: p.y, "
        "d: (p.hole && p.hole[0] === 'ROUND') ? p.hole[1] : null}));"
    )
    pads = execute(js) or []
    return [
        p for p in pads
        if abs(p["x"] - x_mil) <= radius_mil and abs(p["y"] - y_mil) <= radius_mil
    ]


def assert_holes_present(centre_mm):
    """Every entry in params.SWITCH_HOLES must exist at its offset."""
    cx, cy = centre_mm
    missing = []
    for name, (dx, dy), dia in params.SWITCH_HOLES:
        want_x = params.mm_to_mil(cx + dx)
        want_y = params.mm_to_mil(cy + dy)
        near = _pads_near(want_x, want_y, 4)
        if not near:
            missing.append(f"{name} (Ø{dia:.2f}) at ({want_x}, {want_y})")
    if missing:
        raise AssertionError("combo footprint is missing: " + "; ".join(missing))
    print(f"  [ok ] combo footprint: {len(params.SWITCH_HOLES)} holes present")
