"""Place the board's components, having first measured where there is room.

The layout this replaces was produced by asking for one and accepting what
came back. It put the RP2040's pads across a switch hole, ran thirty-five
traces through holes nothing had told the router about, and shorted
seventy-seven pairs of nets to each other -- and every one of those is
invisible in the client unless you already know where to look. The audit
that found them is `audit.py`; this file is the other half, the part that
does not place anything it has not first proved fits.

Three things it does, in order, and none of them on trust:

  strip()   -- delete every trace and via. Routing is downstream of
               placement and there is no such thing as keeping some of it.
  place()   -- move each component to the free position nearest its
               target, where "free" is measured against the switch holes,
               the sockets, the pixels, and everything already placed.
  verify()  -- audit.findings() must come back empty.

The key cell -- the switch holes, the six sockets, the six pixels -- is
never moved. It was borrowed from a shipping board, it is assembled and
proven, and `audit.py --control` exists to keep this file from touching it.

    python3 layout.py            plan only, changes nothing
    python3 layout.py --apply    strip, place, verify
"""

import math
import sys

import audit
import board_edge
import geom
import params as P
from bridge import execute

MIL = 0.0254
MM = 1.0 / MIL

FIXED_PREFIXES = ("LED", "SK")   # the borrowed key cell; never moved

# Parts allowed to hang off the board edge. Exactly one, and it is not a
# loosened rule: a USB-C receptacle's shield tabs reach 0.14 mm past the
# edge because the plug arrives from outside the board, and the case's
# USB opening is cut to the plug, not to the socket. The check refusing
# it was the check working -- so the exemption is named here rather than
# by widening the margin for everything.
EDGE_PARTS = {"USBC1"}

# How close two things may come. Placement is checked at this; the audit
# then re-checks at its own, tighter, thresholds, so a part that only just
# passes here still has to survive the instrument that found the mess.
PLACE_CLEAR_MM = 0.25

# Search: step, and how far from a target the placer may wander before it
# gives up. A part that cannot be placed within this is a plan error, not
# something to solve by searching harder.
STEP_MM = 0.25
SEARCH_R_MM = 14.0


# Targets, in millimetres, board coordinates. y grows toward the sockets;
# the pixels sit at y 6.06 and the switch centres at y 10.795.
#
# Two drafts of this table are worth remembering, because both were
# arithmetic mistakes that looked like design:
#
#   The first put every target ten millimetres too far right. The key
#   centres are 9.525 + n * 19.05, so the sixth is at 104.775 and the
#   field ends at 114.30, and a hand-added 114.775 sent every target into
#   a neighbour's pixel. The placer refusing to place the flash is what
#   surfaced it. `switch_x()` exists so a target is a claim the file
#   cannot get wrong twice.
#
#   The second fitted everything into the pockets between the pixels --
#   11.8 mm wide, 9.4 deep -- because the board was 21.59 mm and there was
#   nowhere else. It fitted. The crystal came out 0.46 mm from the RP2040
#   and 0.55 from a pixel, the flash sat a key column away with 19 mm of
#   QSPI between, and two thirds of the parts were crammed into the
#   right-hand third of the board with the left half empty. Every gap was
#   legal and the whole thing was wrong, which is the failure mode a
#   clearance check cannot report: it answers "do these touch", and the
#   question was "is there room to route this afterwards".
#
# The board is 18 mm longer now (params.MCU_BAY_W) and everything but the
# BOOT switch lives in that bay. The same numbers come out at 1.88 mm
# crystal-to-MCU and 0.71 mm MCU-to-flash, with the flash adjacent so QSPI
# is ~3 mm.
def switch_x(n):
    """Centre of key n (1-based), in millimetres."""
    return 9.525 + (n - 1) * 19.05


def pocket_x(n):
    """Centre of the gap between key n and key n+1."""
    return (switch_x(n) + switch_x(n + 1)) / 2


#   Everything but the BOOT switch now lives in the bay between the last
#   key and the USB tab -- params.BAY_X0..BAY_X1, 18 mm wide and the full
#   21.59 deep, with no switch hole in it. The previous table squeezed the
#   same parts into the key pockets and got the crystal to within 0.46 mm
#   of the MCU; nothing there was illegal and none of it left room for the
#   routing that has to come afterwards.
PLAN = [
    # designator, target (x, y), rotation, why.  Rotation is part of the
    # electrical placement: it turns a pin row toward the thing it serves.
    ("USBC1", (P.USB_CX, 10.795), 270, "fixed by the case, mouth outward"),
    ("U3",    (120.50, 11.00),       0, "RP2040; keys left/right, QSPI and USB down"),

    # QSPI belongs directly below U3.  At zero degrees the flash's left
    # column is SS/SD1/SD2 and its right column is SD0/SCLK/SD3 -- the same
    # two groups as U3's bottom row.  Rotating it put one group toward the
    # board edge and turned SCLK/SD0 into 20 mm detours.
    ("U1",    (119.10, 4.20),        0, "flash directly under the QSPI pins"),

    # Oscillator block, immediately above XIN/XOUT.
    ("U2",    (121.00, 18.20),       0, "crystal directly above XIN/XOUT"),
    ("R2",    (122.10, 16.20),     270, "XOUT series, between U3 and crystal"),
    ("C1",    (118.50, 19.60),       0, "XIN load cap at the crystal"),
    ("C2",    (123.40, 18.20),      90, "XTAL_B load cap at the crystal"),

    # DVDD capacitors sit at the three DVDD exits rather than in a row at
    # the board edge.  The search may nudge them, but not into a different
    # functional block.
    ("C3",    (121.55, 15.35),      90, "top DVDD pin"),
    ("C4",    (116.10, 6.70),      270, "lower-left DVDD, GND facing outward"),
    ("C5",    (123.10, 6.55),       90, "lower-right DVDD escape"),

    # One 3V3 capacitor per power group, wrapped around U3.  C14 is the
    # flash-local capacitor; C16 remains the LDO output bulk capacitor.
    ("C6",    (115.80, 8.40),      180, "U3 left-bottom 3V3, pin 1 facing U3.1"),
    ("C7",    (115.80, 12.00),     180, "U3 left-top 3V3, pin 1 facing U3.10"),
    ("C8",    (120.65, 15.55),      90, "U3.22 top 3V3, pin 1 facing U3"),
    ("C9",    (123.20, 15.35),      90, "U3 top-right 3V3"),
    ("C10",   (125.20, 12.15),      90, "U3 right-top 3V3"),
    ("C11",   (125.20, 8.25),       90, "U3 right-bottom 3V3"),
    ("C12",   (120.90, 6.35),        0, "U3 lower 3V3"),
    ("C13",   (124.45, 5.55),       90, "U3 lower-right 3V3"),
    ("C14",   (121.15, 2.00),        0, "flash-local 3V3"),

    # USB data flows left-to-right: U3 -> R3/R4 -> D1 -> receptacle.
    # D1 at 90 degrees presents IO1/IO2 on both its left and right sides.
    ("R3",    (125.80, 9.85),        0, "USB D+ series before ESD"),
    ("R4",    (125.80, 11.75),       0, "USB D- series before ESD"),
    ("D1",    (128.50, 10.80),      90, "USB ESD pass-through toward connector"),
    ("R5",    (132.00, 8.10),       90, "CC2 pulldown at connector"),
    ("R6",    (132.00, 13.50),      90, "CC1 pulldown at connector"),

    # Regulator at the top of the USB tab, away from the differential pair.
    ("U4",    (130.10, 19.30),       0, "LDO beside VBUS entry"),
    ("C15",   (133.00, 19.30),      90, "LDO VBUS input"),
    ("C16",   (127.50, 19.30),      90, "LDO 3V3 output"),

    # BOOT is not externally accessible; the case is opened to press it.
    # It lives beside USB-C now, where it is easy to identify and reach.
    # R1 follows it so moving the switch does not create a long BOOT spur.
    ("SW1",   (131.50, 3.50),        0, "BOOT beside the USB-C receptacle"),
    ("R1",    (128.00, 3.00),        0, "BOOT series resistor beside SW1"),
]


def _by_designator(data):
    owned, free = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    return {by_id[cid]["des"]: (by_id[cid], pads)
            for cid, pads in owned.items()}, free


def _pad_shapes(comp, pads, x, y, rotation):
    """A component's pads and body at a proposed origin and rotation.

    Pad positions are transformed from the live component, not re-derived
    from a footprint.  That keeps the live document as the source of truth
    while still letting electrical orientation be part of placement.
    """
    da = math.radians(rotation - comp["rot"])
    ca, sa = math.cos(da), math.sin(da)

    def point(px, py):
        lx, ly = px - comp["x"], py - comp["y"]
        return x + lx * ca - ly * sa, y + lx * sa + ly * ca

    def shape_at(p, shape):
        if shape and shape[0] == "POLYGON":
            old = geom.pad_polygon(p["x"], p["y"], p["r"], shape)
            return [point(px, py) for px, py in old]
        px, py = point(p["x"], p["y"])
        return geom.pad_polygon(px, py, p["r"] + da, shape)

    out = []
    for p in pads:
        out.append(shape_at(p, p["pad"]))
        if p["hole"]:
            out.append(shape_at(p, p["hole"]))
    body = geom.body_polygon(comp["fp"], x, y, rotation, MM)
    if body:
        out.append(body)
    return out


def _clears(shapes, obstacles, clear_mil):
    for s in shapes:
        sb = geom.bbox(s)
        for o, ob in obstacles:
            if (sb[0] - clear_mil > ob[2] or ob[0] > sb[2] + clear_mil
                    or sb[1] - clear_mil > ob[3] or ob[1] > sb[3] + clear_mil):
                continue
            if geom.distance(s, o) < clear_mil:
                return False
    return True


def _within_board(shapes, outline, margin_mil):
    x0, y0, x1, y1 = outline
    for s in shapes:
        b = geom.bbox(s)
        if (b[0] < x0 + margin_mil or b[2] > x1 - margin_mil
                or b[1] < y0 + margin_mil or b[3] > y1 - margin_mil):
            return False
    return True


def plan(data, verbose=True):
    """Choose a position for every part in PLAN. Touches nothing."""
    parts, free_pads = _by_designator(data)
    outline = audit.board_outline(data)
    clear = PLACE_CLEAR_MM / MIL
    step = STEP_MM / MIL
    reach = int(SEARCH_R_MM / STEP_MM)

    obstacles = []
    for p in free_pads:
        poly = geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
        obstacles.append((poly, geom.bbox(poly)))
    for _, poly in audit.pixel_openings(data):
        obstacles.append((poly, geom.bbox(poly)))
    for des, (comp, pads) in parts.items():
        if any(des.startswith(k) for k in FIXED_PREFIXES):
            for poly in _pad_shapes(comp, pads, comp["x"], comp["y"],
                                    comp["rot"]):
                obstacles.append((poly, geom.bbox(poly)))

    # Which footprints could not be given a body, and are they ones we
    # decided did not need one. A body model that quietly covers nothing
    # is the same failure as a check that never fires, and this one did
    # exactly that until it was made to say so out loud.
    unmodelled = sorted({
        comp["fp"] for comp, _ in parts.values()
        if geom.body_polygon(comp["fp"], 0, 0, 0, MM) is None})
    surprises = [f for f in unmodelled if f not in geom.NO_BODY_EXPECTED]
    if surprises:
        raise SystemExit(
            f"no body for {surprises} -- either add it to "
            f"geom.BODY_OVERRIDE_MM or, if the pads really do bound it, to "
            f"geom.NO_BODY_EXPECTED. Silently placing against pads alone is "
            f"how a part ends up sitting on 5 mm of someone else's plastic.")
    if verbose and unmodelled:
        print(f"  (pads-only, by decision: {', '.join(unmodelled)})")

    named = {des for des, _, _, _ in PLAN}
    missing = set(parts) - named - {d for d in parts
                                    if any(d.startswith(k)
                                           for k in FIXED_PREFIXES)}
    if missing:
        raise SystemExit(f"PLAN does not mention {sorted(missing)} -- a part "
                         f"left out is a part left where the old layout put it")

    chosen = []
    for des, (tx, ty), rotation, why in PLAN:
        if des not in parts:
            raise SystemExit(f"{des} is in PLAN but not on the board")
        comp, pads = parts[des]
        tx_mil, ty_mil = tx * MM, ty * MM
        best = None
        # Rings outward from the target, so the first hit is the nearest.
        for ring in range(reach + 1):
            cands = []
            if ring == 0:
                cands = [(0, 0)]
            else:
                for i in range(-ring, ring + 1):
                    cands += [(i, -ring), (i, ring), (-ring, i), (ring, i)]
            cands.sort(key=lambda c: c[0] * c[0] + c[1] * c[1])
            for gx, gy in cands:
                nx = tx_mil + gx * step
                ny = ty_mil + gy * step
                shapes = _pad_shapes(comp, pads, nx, ny, rotation)
                if des not in EDGE_PARTS and not _within_board(
                        shapes, outline, 0.30 / MIL):
                    continue
                if not _clears(shapes, obstacles, clear):
                    continue
                best = (nx, ny, shapes)
                break
            if best:
                break
        if not best:
            raise SystemExit(
                f"{des}: nothing within {SEARCH_R_MM} mm of "
                f"({tx:.2f}, {ty:.2f}) is clear. The plan is wrong, not the "
                f"search -- widen the region or move the part elsewhere.")
        nx, ny, shapes = best
        for poly in shapes:
            obstacles.append((poly, geom.bbox(poly)))
        moved = math.hypot(nx - tx_mil, ny - ty_mil) * MIL
        chosen.append((des, comp["id"], nx, ny, rotation))
        if verbose:
            print(f"  {des:6} -> ({nx*MIL:7.2f}, {ny*MIL:6.2f}) mm r{rotation:<3}"
                  f"  {'' if moved < 0.01 else f'[nudged {moved:.2f}]':16}"
                  f" {why}")
    return chosen


def strip():
    """Delete every trace and via. Leaves the board outline alone."""
    js = f"""
    const ls = await eda.pcb_PrimitiveLine.getAll();
    const kill = (ls||[]).filter(l => l.layer === {audit.TOP}
                                   || l.layer === {audit.BOTTOM})
                         .map(l => l.primitiveId);
    const vs = await eda.pcb_PrimitiveVia.getAll();
    const vkill = (vs||[]).map(v => v.primitiveId);
    if (kill.length) await eda.pcb_PrimitiveLine.delete(kill);
    if (vkill.length) await eda.pcb_PrimitiveVia.delete(vkill);
    const after = await eda.pcb_PrimitiveLine.getAll();
    const vafter = await eda.pcb_PrimitiveVia.getAll();
    const edge = (after||[]).filter(l => l.layer === {audit.OUTLINE});
    return {{
      traces: kill.length, vias: vkill.length,
      linesLeft: (after||[]).length,
      outlineLeft: edge.length,
      segs: edge.map(l => [l.startX, l.startY, l.endX, l.endY]),
      viasLeft: (vafter||[]).length,
    }};
    """
    got = execute(js)
    print(f"  stripped {got['traces']} traces, {got['vias']} vias")
    if got["viasLeft"]:
        raise SystemExit(f"{got['viasLeft']} vias survived the strip")
    if got["linesLeft"] != got["outlineLeft"]:
        raise SystemExit(
            f"{got['linesLeft'] - got['outlineLeft']} non-outline lines "
            f"survived the strip")
    # One identity, one closed path, and now one explicit radius. Four
    # touching lines still are not a board outline to EasyEDA.
    board_edge.verify()


# Region rule types, from EPCB_PrimitiveRegionRuleType. Enums are not
# reachable in the execution context, so these are the documented literals.
NO_COMPONENTS = 2
NO_WIRES = 5
NO_POURS = 7
NO_INNER_ELECTRICAL_LAYERS = 8
LAYER_MULTI = 12

KEEPOUT_CLEAR_MM = 0.25


def keepouts():
    """Ring every switch hole with a no-route, no-part, no-copper region.

    This is the fix for the thing that made the previous routing garbage.
    A switch hole is a free pad with **no net**, so nothing in a clearance
    rule set refers to it: the router is not being careless when it drives
    a trace through one, it is being told the hole is not there. Thirty-five
    traces went through holes and DRC reported none of them.

    A region says it in the language the client already enforces, so it
    binds the autorouter, a hand-drawn trace, and the inner-layer pour --
    that last one matters on a 4-layer board, where a plane will otherwise
    flood right up to the barrel of every switch pin.

    `audit.py` still checks independently afterwards. A rule the client
    enforces and a measurement of the result are not the same evidence,
    and this project has already been burnt once by trusting the first.
    """
    data = audit._fetch()
    owned, free = audit.component_pads(data)
    holes = [p for p in free if p["hole"]]
    if not holes:
        raise SystemExit("no free holes found -- the key cell is missing")

    pad_polys = [geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])
                 for pads in owned.values() for p in pads]

    # Grow each hole in its own shape. A bounding circle is the obvious
    # thing and it is wrong: the V2 mount is a 1.5 x 2.0 slot, a circle
    # round it is 2.5 wide, and that extra millimetre of bulge reached a
    # pad of the BOOT switch the placer had cleared correctly. Growing a
    # circle stays a circle and growing a stadium stays a stadium, so
    # both are exact rather than conservative-in-the-wrong-direction.
    specs, clear = [], KEEPOUT_CLEAR_MM / MIL
    for p in holes:
        kind = p["pad"][0]
        if kind in ("ELLIPSE", "ROUND"):
            r = p["pad"][1] / 2.0 + clear
            src = ["CIRCLE", round(p["x"], 3), round(p["y"], 3), round(r, 3)]
            ring = geom.circle(p["x"], p["y"], r)
        elif kind in ("OVAL", "SLOT"):
            ring = geom.stadium(p["x"], p["y"], p["pad"][1] + 2 * clear,
                                p["pad"][2] + 2 * clear, p["r"])
            # The path has to come back to its own first point. The API
            # docs say an open path is closed automatically -- it is not:
            # a triangle and a square were both refused, and the same
            # square with its first point repeated at the end was taken.
            src = [round(ring[0][0], 3), round(ring[0][1], 3)]
            for x, y in list(ring[1:]) + [ring[0]]:
                src += ["L", round(x, 3), round(y, 3)]
        else:
            raise SystemExit(f"hole {p['num']} is a {kind}, which this "
                             f"function has never been asked to grow")
        # A keepout that swallows a pad would make its own net unroutable,
        # and the failure would look like a router that cannot finish
        # rather than like a keepout that is too big.
        for pp in pad_polys:
            if geom.distance(ring, pp) < 0:
                raise SystemExit(
                    f"keepout for {p['num']} at "
                    f"({p['x']*MIL:.2f},{p['y']*MIL:.2f}) covers a pad -- "
                    f"reduce KEEPOUT_CLEAR_MM or move the part")
        specs.append({"n": p["num"], "src": src, "x": round(p["x"], 3)})

    # Ours are identified by their rule set and layer, not by name: the
    # `regionName` argument is accepted and then not stored -- read a
    # region back and it has no name field at all -- so a name-keyed
    # cleanup silently matches nothing and every run adds another
    # thirty-six regions on top of the last.
    rules = [NO_COMPONENTS, NO_WIRES, NO_POURS, NO_INNER_ELECTRICAL_LAYERS]
    js = """
    const specs = %s;
    const want = %s;
    const same = r => r.layer === %d && Array.isArray(r.ruleType)
      && r.ruleType.length === want.length
      && want.every(v => r.ruleType.indexOf(v) >= 0);
    const olds = await eda.pcb_PrimitiveRegion.getAll();
    const stale = (olds||[]).filter(same).map(r => r.primitiveId);
    if (stale.length) await eda.pcb_PrimitiveRegion.delete(stale);
    let made = 0;
    for (const s of specs) {
      const poly = eda.pcb_MathPolygon.createPolygon(s.src);
      if (!poly) continue;
      const r = await eda.pcb_PrimitiveRegion.create(%d, poly, want);
      if (r) made += 1;
    }
    const now = await eda.pcb_PrimitiveRegion.getAll();
    return {deleted: stale.length, asked: specs.length, made: made,
            total: (now||[]).length};
    """ % (__import__("json").dumps(specs), __import__("json").dumps(rules),
           LAYER_MULTI, LAYER_MULTI)
    got = execute(js, timeout=180.0)
    if got["made"] != got["asked"]:
        raise SystemExit(f"only {got['made']} of {got['asked']} keepouts were "
                         f"created -- the board is partly unguarded")
    print(f"  {got['made']} hole keepouts "
          f"(replaced {got['deleted']}), {got['total']} regions on the board")


def apply(chosen):
    moves = [{"id": cid, "x": round(x, 3), "y": round(y, 3), "r": rotation}
             for _, cid, x, y, rotation in chosen]
    js = """
    const moves = %s;
    let n = 0;
    for (const m of moves) {
      const r = await eda.pcb_PrimitiveComponent.modify(
        m.id, {x: m.x, y: m.y, rotation: m.r});
      if (r) n += 1;
    }
    return {asked: moves.length, moved: n};
    """ % __import__("json").dumps(moves)
    got = execute(js, timeout=180.0)
    if got["moved"] != got["asked"]:
        raise SystemExit(f"only {got['moved']} of {got['asked']} components "
                         f"moved -- the board is now half-placed")
    print(f"  moved {got['moved']} components")


def verify():
    data = audit._fetch()
    if not audit.control(data):
        raise SystemExit("the key cell was disturbed -- stop and look")
    f = audit.findings(data)
    if f:
        print(f"  {len(f)} overlaps remain:")
        for kind, d, msg in f[:20]:
            print(f"    {d:+8.3f} mm  {kind:12} {msg}")
        raise SystemExit("placement is not clean")
    print("  no overlaps: every pad, hole and part clears every other")
    return data


def main():
    import build
    build.open_project_pcb()
    data = audit._fetch()

    print("\nplan:")
    chosen = plan(data)

    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to change the board)")
        return

    print("\nstrip:")
    strip()
    print("\napply:")
    apply(chosen)
    print("\nkeepouts:")
    keepouts()
    print("\nverify:")
    verify()
    print("\nall checks passed")


if __name__ == "__main__":
    main()
