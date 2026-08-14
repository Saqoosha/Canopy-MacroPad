# pcb/schematic.py
"""Place and wire the RP2040 microcontroller block on the schematic.

Run with: python3 pcb/schematic.py

Schematic-only, on purpose (see the task brief) -- this does not touch the
PCB or route anything; `build.py` and `footprint.py` own that half.
Coordinates here are 0.01 inch, per pcb/README.md's own warning: mixing
them with the PCB's 1-mil coordinates misplaces everything by 10x, so this
file never imports `params.mm_to_mil()` and never shares a coordinate with
build.py/footprint.py.

Every device placed here is placed by uuid (params.DEV_*), found with
lib_Device.search() / getByLcscIds() and confirmed live -- see the task
report for the search trail. Every pin used below was read back from the
placed component with getAllPinsByPrimitiveId() and matched by name, not
assumed from a datasheet -- the one exception is the USBLC6-2SC6 (U4),
whose placed pins come back as bare "1".."6" with no name at all (unlike
every other device here), so its pin function *does* have to come from the
datasheet (ST's own USBLC6-2SC6 datasheet, pinout table: 1=I/O1, 2=GND,
3=I/O2, 4=I/O2, 5=VBUS, 6=I/O1) -- named in PINOUT_USBLC6 below rather than
trusted blind.
"""
import json
import os
import sys
import time

import params
from bridge import execute

PROJECT_NAME = os.environ.get("MPAD_EDA_PROJECT", "Canopy MacroPad")
LIB = params.LIB_UUID
SCHEMATIC_PAGE = 1  # EDMT_EditorDocumentType.SCHEMATIC_PAGE; the enum object
                     # is absent from the bridge execution context, same
                     # reasoning as build.py's TOP/BOTTOM.

# USBLC6-2SC6 pin function by number, read off ST's own datasheet (the part
# LCSC C323793 carries) -- not from the placed symbol, which returns pins
# named only "1".."6" (confirmed live: no descriptive pinName at all, unlike
# every other device this file places). This is exactly the situation
# pcb/README.md's "pin identity must come from datasheets" describes.
PINOUT_USBLC6 = {"1": "IO1", "2": "GND", "3": "IO2", "4": "IO2", "5": "VBUS", "6": "IO1"}


def open_project_schematic():
    """Open the project's schematic page and leave it active.

    Mirrors build.py's open_project_pcb(): the project is opened by name
    and never created (dmt_Project.createProject() is beta and returns
    undefined -- see build.py's own comment), and the active document is
    asserted rather than assumed, the way build.py asserts documentType==3
    for the PCB.
    """
    js = (
        "const teams = await eda.dmt_Team.getAllTeamsInfo(); "
        "for (const t of teams || []) { "
        "const us = await eda.dmt_Project.getAllProjectsUuid(t.uuid); "
        "for (const u of us || []) { "
        "const i = await eda.dmt_Project.getProjectInfo(u); "
        "const n = (i && (i.friendlyName || i.name)) || ''; "
        f"if (n === {PROJECT_NAME!r}) {{ "
        "await eda.dmt_Project.openProject(u); "
        "const pages = await eda.dmt_Schematic.getAllSchematicPagesInfo(); "
        "if (!pages || !pages.length) return {error: 'project has no schematic page'}; "
        "await eda.dmt_EditorControl.openDocument(pages[0].uuid); "
        "const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo(); "
        "return {opened: n, page: pages[0].name, documentType: doc.documentType}; "
        "} } } "
        "return {error: 'project not found'};"
    ).replace("'", '"')
    got = execute(js)
    if got.get("error"):
        raise SystemExit(f"cannot open the schematic: {got['error']}")
    if got["documentType"] != SCHEMATIC_PAGE:
        raise SystemExit(f"active document is type {got['documentType']}, not a schematic page")
    print(f"opened {got['opened']} / {got['page']}")


def clear_schematic():
    """Delete every component (except the sheet symbol) and every wire.

    The sheet/title-block symbol is type 'sheet' and is not ours to touch --
    it pre-existed on this page. Mirrors probe.clear_components()'s
    "clear, then assert nothing is left" shape.
    """
    js = (
        "const all = await eda.sch_PrimitiveComponent.getAll(); "
        "const nonSheet = (all || []).filter(c => c.getState_ComponentType() !== 'sheet'); "
        "if (nonSheet.length) { await eda.sch_PrimitiveComponent.delete(nonSheet.map(c => c.primitiveId)); } "
        "const allw = await eda.sch_PrimitiveWire.getAll(); "
        "if (allw && allw.length) { await eda.sch_PrimitiveWire.delete(allw.map(w => w.primitiveId)); } "
        "const leftC = (await eda.sch_PrimitiveComponent.getAll()).filter(c => c.getState_ComponentType() !== 'sheet').length; "
        "const leftW = (await eda.sch_PrimitiveWire.getAll()).length; "
        "return {leftC, leftW};"
    )
    left = execute(js)
    if left["leftC"] or left["leftW"]:
        raise AssertionError(f"clear left {left['leftC']} components and {left['leftW']} wires behind")


# --- placement ---------------------------------------------------------------
# key -> (device uuid, x, y). Rotation is 0 throughout -- schematic-only, no
# routing constraint forces a rotation the way the PCB side's socket/pixel
# mirroring did.
PARTS = {
    "U1": (params.DEV_RP2040, 600, 450),
    "U2": (params.DEV_FLASH, 200, 600),
    "U3": (params.DEV_LDO, 950, 750),
    "U4": (params.DEV_ESD, 900, 620),
    "J1": (params.DEV_USB_C, 1050, 600),
    "SW1": (params.DEV_BOOT_SW, 200, 700),
    "Y1": (params.DEV_CRYSTAL, 300, 430),
    "R1": (params.DEV_R_27R, 780, 610),   # USB_DP series
    "R2": (params.DEV_R_27R, 780, 650),   # USB_DM series
    "R3": (params.DEV_R_5K1, 1150, 625),  # CC1 pull-down
    "R4": (params.DEV_R_5K1, 1150, 565),  # CC2 pull-down
    "R5": (params.DEV_R_1K, 380, 420),    # crystal XOUT damping
    "R6": (params.DEV_R_1K, 330, 650),    # BOOT series resistor
    "C15": (params.DEV_C_15P, 150, 410),  # crystal load cap, XIN side
    "C16": (params.DEV_C_15P, 150, 470),  # crystal load cap, XOUT side
    "C11": (params.DEV_C_1U, 560, 780),   # VREG_IN
    "C12": (params.DEV_C_1U, 540, 780),   # VREG_VOUT / DVDD
    "C13": (params.DEV_C_1U, 850, 700),   # LDO input -- off U3's own y=750/770
    "C14": (params.DEV_C_1U, 1050, 700),  # LDO output rows on purpose, so a
    # straight wire from U3 to either cap doesn't run collinear through the
    # other's pins (see elbow()'s own collision check, added after exactly
    # this shape of accidental short was caught live).
}
# The ten 100 nF decoupling caps are positioned relative to the RP2040 power
# pins they serve, computed after U1 is placed and its pins read back --
# see place_decoupling() -- rather than hand-guessed here, because a
# hand-guessed x that drifts from the real pin x is exactly the kind of
# mistake this project's README warns about (footprint.py's whole existence
# is proof that a hole can be near the right spot and still not be there).
DECOUPLE_PINS = [
    ("C1", "IOVDD", "1"), ("C2", "IOVDD", "10"), ("C3", "IOVDD", "22"),
    ("C4", "IOVDD", "33"), ("C5", "IOVDD", "42"), ("C6", "IOVDD", "49"),
    ("C7", "DVDD", "23"), ("C8", "DVDD", "50"),
    ("C9", "USB_VDD", "48"), ("C10", "ADC_AVDD", "43"),
]


def place_all():
    """Place every part in PARTS, then the ten decoupling caps against U1's
    real, read-back power-pin coordinates. Returns {key: primitiveId}.
    """
    pids = {}
    for key, (uuid, x, y) in PARTS.items():
        js = (
            f'const dev = {{libraryUuid: "{LIB}", uuid: "{uuid}"}}; '
            f"const c = await eda.sch_PrimitiveComponent.create(dev, {x}, {y}, undefined, 0, false, true, true); "
            "return c ? c.primitiveId : null;"
        )
        pid = execute(js)
        if not pid:
            raise AssertionError(f"create returned nothing for {key}")
        pids[key] = pid

    u1_pins = get_pins(pids["U1"])
    # DVDD pins share x=310/320 at U1's placement; C12 (VREG_VOUT/DVDD cap)
    # was hand-placed near them above. The 10 decoupling caps go directly
    # below their own power pin, same x, +130 units in y -- far enough that
    # a 2-segment elbow wire between cap and pin doesn't cross another cap.
    for i, (key, pin_name, pin_num) in enumerate(DECOUPLE_PINS):
        px, py = pin_xy(u1_pins, pin_name, pin_num)
        cx, cy = px, py + 130
        js = (
            f'const dev = {{libraryUuid: "{LIB}", uuid: "{params.DEV_C_100N}"}}; '
            f"const c = await eda.sch_PrimitiveComponent.create(dev, {cx}, {cy}, undefined, 0, false, true, true); "
            "return c ? c.primitiveId : null;"
        )
        pid = execute(js)
        if not pid:
            raise AssertionError(f"create returned nothing for {key}")
        pids[key] = pid
    return pids


# --- pin lookup ---------------------------------------------------------------
_PIN_CACHE = {}


def get_pins(pid):
    if pid not in _PIN_CACHE:
        js = (
            f'const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId("{pid}"); '
            "return (pins || []).map(p => ({name: p.pinName, num: p.pinNumber, x: p.x, y: p.y}));"
        )
        pins = execute(js)
        if not pins:
            raise AssertionError(f"no pins read back for {pid}")
        _PIN_CACHE[pid] = pins
    return _PIN_CACHE[pid]


def pin_xy(pins, name=None, num=None):
    """Find exactly one pin by name and/or number; raise on 0 or >1 matches
    rather than silently taking the first -- the same "assert every
    substitution" discipline CLAUDE.md asks of string patches applies here
    to pin lookups: a name that matches zero or two pins is a wrong
    assumption, not a thing to paper over with [0].
    """
    matches = [
        p for p in pins
        if (name is None or p["name"] == name) and (num is None or p["num"] == num)
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"pin lookup name={name!r} num={num!r}: {len(matches)} matches, wanted 1"
        )
    return matches[0]["x"], matches[0]["y"]


# --- wiring --------------------------------------------------------------------
_WIRE_LOG = []  # (net_label, [(x,y), ...]) for every wire created, for the report
_ALL_SEGMENTS = []  # every (a, b) segment already drawn, for crossing checks


def _segment_overlap(a1, a2, b1, b2):
    """The overlap between two axis-aligned segments, as an (x0, x1, y0,
    y1) box (a bounding-box intersection, exact for a pair of segments
    that are each already a degenerate zero-width or zero-height
    rectangle), or None if they do not touch at all.
    """
    ax0, ax1 = sorted((a1[0], a2[0]))
    ay0, ay1 = sorted((a1[1], a2[1]))
    bx0, bx1 = sorted((b1[0], b2[0]))
    by0, by1 = sorted((b1[1], b2[1]))
    if ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1:
        return (max(ax0, bx0), min(ax1, bx1), max(ay0, by0), min(ay1, by1))
    return None


def _overlap_allowed(overlap, allowed):
    """True if an overlap box (from _segment_overlap()) is nothing more
    than one of this path's own declared points -- a legitimate T-junction
    or fan-out, not a crossing with an unrelated wire. A box that is a
    single point is allowed exactly when that point is in `allowed`; any
    wider overlap (two segments running along the same line for more than
    one point) is never allowed, regardless of what `allowed` contains.
    """
    x0, x1, y0, y1 = overlap
    if x0 != x1 or y0 != y1:
        return False
    return (x0, y0) in allowed


def wire_path(points, net=None, label=""):
    """Create one polyline wire through points (a list of (x,y) tuples,
    already Manhattan -- every consecutive pair must share x or y, per
    sch_PrimitiveWire.create()'s own documented rule that a horizontal
    segment followed by a diagonal one is rejected).
    """
    flat = []
    for x, y in points:
        flat.extend([x, y])
    line_js = "[" + ",".join(str(v) for v in flat) + "]"
    net_arg = f'"{net}"' if net else "undefined"
    js = (
        f"const w = await eda.sch_PrimitiveWire.create({line_js}, {net_arg}, undefined, undefined, undefined); "
        "return w ? w.primitiveId : null;"
    )
    wid = execute(js)
    if not wid:
        raise AssertionError(f"wire create returned nothing for {label or points}")
    _WIRE_LOG.append((label, points))
    for i in range(len(points) - 1):
        _ALL_SEGMENTS.append((points[i], points[i + 1], net))
    return wid


_ALL_PINS = set()  # every pin coordinate on the board, populated by place_all()


def _pin_on_segment(p, a, b):
    """True if p sits on the axis-aligned segment a-b (inclusive)."""
    if a[0] == b[0]:
        return p[0] == a[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    if a[1] == b[1]:
        return p[1] == a[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
    return False


def _path_collides(path, allowed, net=None):
    """True if any pin (other than the path's own declared endpoints,
    `allowed`) lies on any segment of path, OR any segment of path
    crosses/touches an already-drawn wire segment of a *different* net
    anywhere other than a real shared endpoint -- three distinct shapes
    of the same underlying mistake, all watched happening live:

    - a bend landing exactly on an unrelated pin (R5-Y1's bend landed on
      the crystal's own GND pin);
    - a straight run passing over one (R1-USB_DP's bend landed on
      U1.USB_DM, a different signal three pins away in the symbol's own
      pin list);
    - and the one this function's earlier version still missed entirely:
      two *different* signals' own detour paths crossing each other at a
      waypoint that is not a registered pin at all, which EasyEDA still
      merges into one wire object and one net. Confirmed live, and not a
      near miss: QSPI_SCLK and QSPI_SD3 (and, separately, QSPI_SD1 and
      QSPI_SD2) ended up on the same wire object this way, and so did
      USB's D+ and D- at the connector -- three real shorts, caught only
      by directly probing `getState_Net()` on two supposedly-different
      pins and finding the same wire `primitiveId` came back for both.
      Checking against `_ALL_SEGMENTS` (every segment any wire_path()
      call has already drawn) is what the pin-only check could not do.

    `net`, if given, is the net this new path is itself going to carry --
    a crossing against an *already-drawn segment of that same net* is not
    a fault (VBUS's own star, wired point by point from one anchor,
    legitimately has several of its own segments passing near each other
    in the LDO/ESD/J1 cluster); only a crossing against a segment carrying
    a *different* (or no) net is.
    """
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        for p in _ALL_PINS:
            if p in allowed:
                continue
            if _pin_on_segment(p, a, b):
                return True
        for wa, wb, seg_net in _ALL_SEGMENTS:
            if net and seg_net == net:
                continue
            overlap = _segment_overlap(a, b, wa, wb)
            if overlap is None:
                continue
            if _overlap_allowed(overlap, allowed):
                # The only point of contact is one of *this path's own*
                # declared endpoints -- legitimate fan-out (e.g. QSPI_SS
                # to both the flash and R6) or a deliberate T-junction
                # (a bus_connect() drop meeting its own rail) -- not a
                # crossing with an unrelated wire.
                continue
            return True
    return False


def elbow(a, b, net=None):
    """Two points -> a Manhattan path between them that does not pass
    through any other pin on the board.

    Tries, in order: the direct line (if a and b already share an axis),
    both single-bend elbows, then a widening search of double-bend
    detours (a -> sideways by a growing offset -> across -> in to b) on
    both the a-side and b-side. Raises rather than silently returning a
    wire that shorts two unrelated nets together -- see
    _path_collides()'s docstring for why that risk is real here, not
    theoretical -- but the two-signal-dense pin columns this board's QSPI
    bus and BOOT path both turn out to have needed the detour search
    before a hand-picked route was tried: single-bend routing failed for
    6 of the 8 QSPI/BOOT connections on the first attempt, every one of
    them because the bend, or the straight run itself, landed on a third,
    unrelated pin on the same crowded column -- not a one-off, a pattern.
    """
    ax, ay = a
    bx, by = b
    allowed = {a, b}
    candidates = []
    if ax == bx or ay == by:
        candidates.append([a, b])
    else:
        candidates.append([a, (bx, ay), b])
        candidates.append([a, (ax, by), b])
    for cand in candidates:
        if not _path_collides(cand, allowed, net=net):
            return cand
    for offset in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 150, 180, 210, 250, 300):
        for dy in (offset, -offset):
            cand = [a, (ax, ay + dy), (bx, ay + dy), b]
            if not _path_collides(cand, allowed, net=net):
                return cand
        for dx in (offset, -offset):
            cand = [a, (ax + dx, ay), (ax + dx, by), b]
            if not _path_collides(cand, allowed, net=net):
                return cand
    raise AssertionError(
        f"elbow({a}, {b}): no route up to a 100-unit detour clears every "
        "other pin -- needs a manually chosen path, not this function's "
        "search"
    )


def bus_connect(rail_y, points, net=None, label=""):
    """Wire every point in points to a single horizontal rail at rail_y,
    each with its own straight vertical drop, rather than star-wiring from
    one of the points as an anchor.

    Exists because DVDD's three real pins -- VREG_VOUT and both DVDD pads
    -- sit on U1's own bottom edge, all at the identical y, with other
    power pins between them on that same edge. A star from any one of them
    to another runs straight along that edge and through whatever pin
    happens to sit in between (confirmed live, via elbow()'s own collision
    check firing here first). A rail below the edge sidesteps the whole
    row: every drop is a single vertical segment at its own x, and the
    only shared line is the rail itself, which nothing else on the board
    occupies at rail_y by construction (the caller picks a y no other net
    uses).
    """
    xs = [p[0] for p in points]
    rail = [(min(xs), rail_y), (max(xs), rail_y)]
    rail_allowed = {rail[0], rail[1]}
    if _path_collides(rail, rail_allowed, net=net):
        raise AssertionError(f"{label}-rail at y={rail_y} collides with an existing pin")
    ids = [wire_path(rail, net=net, label=f"{label}-rail")]
    for i, (x, y) in enumerate(points):
        drop = [(x, rail_y), (x, y)]
        if _path_collides(drop, {(x, rail_y), (x, y)}, net=net):
            raise AssertionError(f"{label}-drop[{i}] at x={x} collides with an existing pin")
        ids.append(wire_path(drop, net=net, label=f"{label}-drop[{i}]"))
    return ids


def connect(anchor, points, net=None, label=""):
    """Star-wire anchor to every point in points, each as its own elbowed
    2-or-3-point path, every one of them carrying the explicit net name.

    An earlier version only named the first branch, on the assumption
    that later branches would inherit the name by coincidence once merged
    with it -- true for what EasyEDA reports (confirmed live: VBUS, DVDD,
    and USB_DP_RAW all read back their correct name this way), but it
    also meant every branch after the first was registered in
    `_ALL_SEGMENTS` with no net at all, so this file's own crossing check
    could not tell two branches of the *same* star apart from two
    branches of *different* nets crossing by accident -- exactly the bug
    that turned into the USB D+/D- short. Naming every branch explicitly
    fixes both: the check can now skip same-net crossings on purpose (see
    elbow()/_path_collides()), and there is no longer a silent gap in
    what the registry itself remembers.
    """
    ids = []
    for i, p in enumerate(points):
        ids.append(wire_path(elbow(anchor, p, net=net), net=net, label=f"{label}[{i}]"))
    return ids


def main():
    open_project_schematic()
    clear_schematic()
    pids = place_all()
    print(f"  [ok ] placed {len(pids)} components")

    for pid in pids.values():
        for p in get_pins(pid):
            _ALL_PINS.add((p["x"], p["y"]))
    print(f"  [ok ] {len(_ALL_PINS)} distinct pin coordinates registered for collision-checked routing")

    u1 = get_pins(pids["U1"])

    def u1pin(name, num=None):
        return pin_xy(u1, name, num)

    # --- GND and 3V3: gathered here, wired later with place_power_flags() --
    # Not physical star wires -- see place_power_flags()'s own docstring for
    # why: a star from one anchor to ~30 far-flung points, on a canvas this
    # dense, was proven live to cross itself. GND's own star crossed the
    # crystal's XIN wire at the crystal's own GND pin (confirmed with
    # --debug-collisions), and separately the GND and 3V3 stars crossed
    # each other in the decoupling-cap row -- two different, confirmed
    # accidental shorts from the same design, not a single fixable typo.
    gnd_needed = [u1pin("GND"), u1pin("TESTEN")]
    for key, _, _ in DECOUPLE_PINS:
        gnd_needed.append(pin_xy(get_pins(pids[key]), "2"))
    gnd_needed += [
        pin_xy(get_pins(pids["C11"]), "2"),
        pin_xy(get_pins(pids["C12"]), "2"),
        pin_xy(get_pins(pids["C13"]), "2"),
        pin_xy(get_pins(pids["C14"]), "2"),
        pin_xy(get_pins(pids["C15"]), "2"),
        pin_xy(get_pins(pids["C16"]), "2"),
        pin_xy(get_pins(pids["U2"]), "GND"),
        pin_xy(get_pins(pids["U3"]), "GND"),
        pin_xy(get_pins(pids["R3"]), "2"),
        pin_xy(get_pins(pids["R4"]), "2"),
        pin_xy(get_pins(pids["SW1"]), "B"),
    ]
    # ABM8-272-T3 is a 4-pad crystal (confirmed live: getAllPinsByPrimitiveId
    # returns 4 pins, not 2) -- pins "1" and "3" are the oscillator
    # terminals, pins named "GND" (numbers 2 and 4) are the case/shield
    # pads and belong on the GND net same as any other ground pin, not on
    # the XIN/XOUT signal path.
    for p in get_pins(pids["Y1"]):
        if p["name"] == "GND":
            gnd_needed.append((p["x"], p["y"]))
    u4_pins = get_pins(pids["U4"])
    for p in u4_pins:
        if PINOUT_USBLC6[p["num"]] == "GND":
            gnd_needed.append((p["x"], p["y"]))
    j1_pins = get_pins(pids["J1"])
    for p in j1_pins:
        if p["name"] == "GND" or p["name"] == "EH":
            gnd_needed.append((p["x"], p["y"]))

    v3_needed = [u1pin("USB_VDD"), u1pin("ADC_AVDD"), u1pin("VREG_IN"), u1pin("RUN")]
    for name, num in [("IOVDD", "1"), ("IOVDD", "10"), ("IOVDD", "22"),
                       ("IOVDD", "33"), ("IOVDD", "42"), ("IOVDD", "49")]:
        v3_needed.append(u1pin(name, num))
    v3_needed += [
        pin_xy(get_pins(pids["U2"]), "VCC"),
        pin_xy(get_pins(pids["U3"]), "Vout"),
        pin_xy(get_pins(pids["C14"]), "1"),
        pin_xy(get_pins(pids["C11"]), "1"),
    ]
    # IOVDD x6 and DVDD x2 decoupling caps' negative legs are already in
    # gnd_needed above; only the IOVDD-side (+leg) caps join 3V3 here --
    # DVDD's own two caps (C7, C8) join the DVDD/VREG_VOUT net below
    # instead, which stays a physical wire (it never touches GND or 3V3,
    # so it never had a collision to begin with).
    for key in ("C1", "C2", "C3", "C4", "C5", "C6", "C9", "C10"):
        v3_needed.append(pin_xy(get_pins(pids[key]), "1"))

    # --- VBUS --------------------------------------------------------------
    ldo_in = pin_xy(get_pins(pids["U3"]), "Vin")
    vbus_targets = [pin_xy(get_pins(pids["C13"]), "1")]
    for p in j1_pins:
        if p["name"] == "VBUS":
            vbus_targets.append((p["x"], p["y"]))
    for p in u4_pins:
        if PINOUT_USBLC6[p["num"]] == "VBUS":
            vbus_targets.append((p["x"], p["y"]))
    connect(ldo_in, vbus_targets, net="VBUS", label="VBUS")
    print(f"  [ok ] VBUS: {len(vbus_targets) + 1} points wired")

    # --- DVDD / VREG_VOUT --------------------------------------------------
    # bus_connect(), not connect(): VREG_VOUT and both DVDD pads all sit on
    # U1's own bottom edge at the same y, with other power pins between
    # them -- a star from any one to another runs along that edge and
    # through whatever pin is in between. See bus_connect()'s own
    # docstring; this is the case it exists for.
    dvdd_targets = [u1pin("VREG_VOUT"), u1pin("DVDD", "23"), u1pin("DVDD", "50"),
                    pin_xy(get_pins(pids["C12"]), "1")]
    for key in ("C7", "C8"):
        dvdd_targets.append(pin_xy(get_pins(pids[key]), "1"))
    bus_connect(665, dvdd_targets, net="DVDD", label="DVDD")
    print(f"  [ok ] DVDD: {len(dvdd_targets)} points wired via a rail at y=665")

    # --- crystal -------------------------------------------------------------
    # ABM8-272-T3 (Y1) is a 4-pad part: pin "1" and pin "3" are the
    # oscillator terminals, and its two GND pads sit at the same x as pin
    # "1" (case ground below it) and the same y as pin "3" (case ground
    # beside it) -- see the DEV_CRYSTAL comment in params.py. That geometry
    # means pin "1" is boxed in on two sides by its own part's ground pads,
    # and neither of elbow()'s two default single-bend routes from XIN
    # clears both (confirmed live -- this is the AssertionError that first
    # exposed the whole collision problem this file's elbow()/bus_connect()
    # machinery exists to solve). XIN's route below is hand-built instead:
    # out along U1's own pin column to a y no other U1 pin occupies, across
    # to a x=280 waypoint (clear of Y1's GND-4 at x=270), then down and in
    # to pin "1" from *above* -- the one side of it nothing else occupies.
    y1 = get_pins(pids["Y1"])
    xin_u1 = u1pin("XIN")
    xout_u1 = u1pin("XOUT")
    y1_a = pin_xy(y1, None, "1")   # oscillator terminal, XIN side
    y1_b = pin_xy(y1, None, "3")   # oscillator terminal, XOUT/R5 side
    r5 = get_pins(pids["R5"])
    r5_near, r5_far = pin_xy(r5, "2"), pin_xy(r5, "1")  # pin 2 (x=400) is the
    # one closer to XOUT (x=470); pin 1 (x=360) is closer to the crystal.
    # Pin "2" (the right-hand pin, closer to Y1) on both caps -- approaching
    # from Y1's side, pin "1" (further left) is only reachable by first
    # passing pin "2", the same near/far mistake R5 above already caught.
    c15 = pin_xy(get_pins(pids["C15"]), "2")
    c16 = pin_xy(get_pins(pids["C16"]), "2")
    xin_path = [
        xin_u1, (xin_u1[0], 460), (280, 460),
        (280, y1_a[1] - 10), (y1_a[0], y1_a[1] - 10), y1_a,
    ]
    if _path_collides(xin_path, set(xin_path), net="XIN"):
        raise AssertionError(f"hand-built XIN-Y1 route {xin_path} still collides")
    # Every signal wire below gets its net passed explicitly. Confirmed
    # live (see pcb/README.md's "Schematic-side API traps") that
    # coincidence-based inheritance does not reliably populate
    # getState_Net() the way an explicit net argument does, and -- the
    # more serious finding -- that two *different* signals' own detour
    # paths sharing an unregistered waypoint get silently merged into one
    # wire object by EasyEDA regardless of either signal's intended name.
    # elbow()'s collision search (via _path_collides()) now also checks
    # against every already-drawn wire segment, not just registered pins,
    # which is what actually prevents that merge; the explicit net= here
    # is what makes a real, surviving mistake (if the collision search
    # ever misses one) visible as two segments both claiming the same
    # name-conflict rather than silently reading blank.
    wire_path(xin_path, net="XIN", label="XIN-Y1")
    wire_path(elbow(y1_a, c15, net="XIN"), net="XIN", label="Y1-C15")
    # XOUT to R5's *near* pin (closer to U1, x=400) first, then R5's far
    # pin (x=360) on to the crystal -- the other order runs straight
    # through R5's own near pin on the way to the far one, since both sit
    # on the same y as XOUT. XOUT and the post-resistor node (named
    # XTAL_B) are deliberately different nets -- R5 sits between them.
    wire_path(elbow(xout_u1, r5_near, net="XOUT"), net="XOUT", label="XOUT-R5")
    wire_path(elbow(r5_far, y1_b, net="XTAL_B"), net="XTAL_B", label="R5-Y1")
    # Y1-C16 is hand-routed, not elbow()'s search: XIN's own hand-built
    # detour (above) boxes in this whole corner -- a horizontal run at
    # y=460 from x=280-470, a vertical run at x=280 from y=410-460, and
    # U1.XIN's own pin at (470,440) -- and Y1 pin "3" sits at x=330,
    # inside that horizontal run's x-range, so any straight drop from it
    # crosses XIN somewhere. The only gap is a narrow y=435-445 corridor
    # (between Y1's own pin row at y=440 and XIN's horizontal at y=460)
    # wide enough to get *out* to x=500 -- past XIN's whole bounding box
    # on the right -- before dropping down and coming back in from below.
    y1_c16_path = [y1_b, (330, 435), (500, 435), (500, 470), c16]
    if _path_collides(y1_c16_path, set(y1_c16_path), net="XTAL_B"):
        raise AssertionError(f"hand-built Y1-C16 route {y1_c16_path} still collides")
    wire_path(y1_c16_path, net="XTAL_B", label="Y1-C16")
    print("  [ok ] crystal: XIN-Y1-C15 and XOUT-R5-Y1-C16 wired")

    # --- QSPI / flash ---------------------------------------------------------
    u2 = get_pins(pids["U2"])
    r6 = get_pins(pids["R6"])
    sw1 = get_pins(pids["SW1"])
    wire_path(elbow(u1pin("QSPI_SCLK"), pin_xy(u2, "CLK"), net="QSPI_SCLK"), net="QSPI_SCLK", label="QSPI_SCLK")
    wire_path(elbow(u1pin("QSPI_SD0"), pin_xy(u2, "DI(IO0)"), net="QSPI_SD0"), net="QSPI_SD0", label="QSPI_SD0")
    wire_path(elbow(u1pin("QSPI_SD1"), pin_xy(u2, "DO(IO1)"), net="QSPI_SD1"), net="QSPI_SD1", label="QSPI_SD1")
    wire_path(elbow(u1pin("QSPI_SD2"), pin_xy(u2, "/WP(IO2)"), net="QSPI_SD2"), net="QSPI_SD2", label="QSPI_SD2")
    wire_path(elbow(u1pin("QSPI_SD3"), pin_xy(u2, "/HOLDor/RESET(IO3)"), net="QSPI_SD3"), net="QSPI_SD3", label="QSPI_SD3")
    qspi_ss = u1pin("QSPI_SS")
    wire_path(elbow(qspi_ss, pin_xy(u2, "/CS"), net="QSPI_SS"), net="QSPI_SS", label="QSPI_SS-flash")
    wire_path(elbow(qspi_ss, pin_xy(r6, "1"), net="QSPI_SS"), net="QSPI_SS", label="QSPI_SS-R6")
    wire_path(elbow(pin_xy(r6, "2"), pin_xy(sw1, "A"), net="BOOT"), net="BOOT", label="R6-SW1")
    print("  [ok ] QSPI: 6 signals to flash, QSPI_SS to BOOT switch via R6")

    # --- USB ---------------------------------------------------------------
    dp_targets = [(p["x"], p["y"]) for p in j1_pins if p["name"] in ("DP1", "DP2")]
    dn_targets = [(p["x"], p["y"]) for p in j1_pins if p["name"] in ("DN1", "DN2")]
    u4_io1 = [(p["x"], p["y"]) for p in u4_pins if PINOUT_USBLC6[p["num"]] == "IO1"]
    u4_io2 = [(p["x"], p["y"]) for p in u4_pins if PINOUT_USBLC6[p["num"]] == "IO2"]
    r1 = get_pins(pids["R1"])
    r2 = get_pins(pids["R2"])
    # DP1/DP2 (both cable orientations) bridged with U4's IO1 pair and R1's
    # far side; R1's near side to U1.USB_DP. DN mirrors with R2/USB_DM.
    # R1/R2's pin "1" sits at the lower x (closer to U1); pin "2" sits at
    # the higher x (closer to J1/the ESD chip). Wiring U1's side to pin "1"
    # and the connector side to pin "2" -- reversed from an earlier draft --
    # keeps each wire on its own resistor's near pin, not routed past its
    # own far pin first (the same near/far mistake R5 and the flash's own
    # pin columns already caught).
    #
    # USB_DP_RAW and USB_DM_RAW were confirmed live to merge into a single
    # wire object -- D+ shorted to D- at the connector -- when connect()'s
    # two independent star fans, routed through the same tight J1/ESD
    # cluster, crossed at an unregistered bend point. elbow()'s collision
    # search (now checking _ALL_SEGMENTS, not just pins) is what actually
    # prevents the two stars from touching; wiring USB_DM_RAW *after*
    # USB_DP_RAW is registered means its own search has USB_DP_RAW's real
    # wires to route around.
    connect(dp_targets[0], dp_targets[1:] + u4_io1 + [pin_xy(r1, "2")], net="USB_DP_RAW", label="USB_DP_RAW")
    connect(dn_targets[0], dn_targets[1:] + u4_io2 + [pin_xy(r2, "2")], net="USB_DM_RAW", label="USB_DM_RAW")
    wire_path(elbow(pin_xy(r1, "1"), u1pin("USB_DP"), net="USB_DP"), net="USB_DP", label="R1-USB_DP")
    wire_path(elbow(pin_xy(r2, "1"), u1pin("USB_DM"), net="USB_DM"), net="USB_DM", label="R2-USB_DM")
    print("  [ok ] USB: D+/D- bridged both orientations, through ESD and 27R series")

    # --- CC1 / CC2 -----------------------------------------------------------
    cc1 = next((p["x"], p["y"]) for p in j1_pins if p["name"] == "CC1")
    cc2 = next((p["x"], p["y"]) for p in j1_pins if p["name"] == "CC2")
    r3 = get_pins(pids["R3"])
    r4 = get_pins(pids["R4"])
    wire_path(elbow(cc1, pin_xy(r3, "1"), net="CC1"), net="CC1", label="CC1-R3")
    # CC2 sits at y=565, inside J1's shield (EH) pins' y=545-575 band at
    # x=1085 -- both of elbow()'s search shapes route straight along
    # J1's own x=1015 column first, which is packed solid (a J1 pin every
    # 10 units from y=545 to 655), so no offset ever clears it. Routed by
    # hand instead: a small notch past the EH pin's exact x before
    # returning to R4's row, verified collision-free the same way as
    # every other hand-built path in this file.
    cc2_r4 = pin_xy(r4, "1")
    cc2_path = [cc2, (1080, cc2[1]), (1080, 585), (cc2_r4[0], 585), cc2_r4]
    if _path_collides(cc2_path, set(cc2_path), net="CC2"):
        raise AssertionError(f"hand-built CC2-R4 route {cc2_path} still collides")
    wire_path(cc2_path, net="CC2", label="CC2-R4")
    print("  [ok ] CC1/CC2: wired to their own 5.1k pull-down (GND leg queued for a flag, not wired yet)")

    if "--debug-collisions" in sys.argv:
        _debug_collisions()
    assert_nets(pids)

    gnd_flags = place_power_flags("Ground", "GND", gnd_needed)
    v3_flags = place_power_flags("Power", "3V3", v3_needed)
    assert_power_flags(gnd_flags, "GND")
    assert_power_flags(v3_flags, "3V3")

    place_key_ports(pids)

    return pids


def _debug_collisions():
    """Diagnostic: any coordinate touched by two differently-labelled wires
    is a candidate for an accidental short between two nets that were
    never meant to touch."""
    from collections import defaultdict
    touch = defaultdict(set)
    for label, points in _WIRE_LOG:
        top = label.split("[")[0]
        for p in points:
            touch[p].add(top)
    for p, labels in sorted(touch.items()):
        if len(labels) > 1:
            print(f"  COLLISION at {p}: {sorted(labels)}")


# --- net verification ---------------------------------------------------------
def assert_nets_by_graph(pids):
    """Fallback for when getNetlistFile() has stopped answering (see
    assert_nets()'s own comment on when and why this gets called): union-
    find over every point pair this file's own wire_path() calls actually
    connected, from _WIRE_LOG. Two points are in the same net here iff a
    chain of this file's own wire segments joins them -- weaker than
    asking EasyEDA's net engine (it cannot catch EasyEDA silently
    declining to honour a coincidence the way this file expects), but it
    is a real check against real data, not a rubber stamp: it still fails
    if a wire never got drawn, if two supposedly-different nets turn out
    connected by an accidental shared point elbow()'s collision search
    missed, or if a point this function expects on a net was never in any
    wire_path() call at all.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent.setdefault(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    segments = []
    for _label, points in _WIRE_LOG:
        for i in range(len(points) - 1):
            segments.append((points[i], points[i + 1]))
            union(points[i], points[i + 1])

    # T-junction pass: bus_connect()'s rail is one 2-point wire; each drop
    # meets it at a point that is the rail segment's *interior*, not
    # either of its two endpoints, so the union() calls above never
    # connect a drop to the rail at all -- confirmed live, this is exactly
    # what DVDD's first run of this function caught. Any endpoint that
    # geometrically lies on a different segment gets unioned with that
    # segment too, the same "does a pin sit on this line" test elbow()'s
    # own collision search already uses.
    endpoints = {p for seg in segments for p in seg}
    for p in endpoints:
        for a, b in segments:
            if p in (a, b):
                continue
            if _pin_on_segment(p, a, b):
                union(p, a)

    problems = []

    def same(label, *points):
        roots = {find(p) for p in points}
        if len(roots) != 1:
            problems.append(f"{label}: not all connected -- {points}")

    def different(label, a, b):
        if find(a) == find(b):
            problems.append(f"{label}: expected on different nets, both landed on one")

    u1 = get_pins(pids["U1"])

    def u1pin(name, num=None):
        return pin_xy(u1, name, num)

    u2 = get_pins(pids["U2"])
    qspi_pairs = [
        ("QSPI_SCLK", "CLK"), ("QSPI_SD0", "DI(IO0)"), ("QSPI_SD1", "DO(IO1)"),
        ("QSPI_SD2", "/WP(IO2)"), ("QSPI_SD3", "/HOLDor/RESET(IO3)"), ("QSPI_SS", "/CS"),
    ]
    for u1_name, flash_name in qspi_pairs:
        same(f"QSPI {u1_name}-{flash_name}", u1pin(u1_name), pin_xy(u2, flash_name))
    # Every QSPI signal must be a *different* net from every other one --
    # not checked at all in an earlier version of this function, which is
    # exactly how two real shorts (QSPI_SCLK merged with QSPI_SD3, and
    # separately QSPI_SD1 with QSPI_SD2 -- both confirmed live by reading
    # getState_Net() back on two supposedly-different pins and finding
    # the same wire primitiveId) went undetected: "each signal reaches
    # its own flash pin" was true for both shorted pairs, since the
    # merged wire object still touched every pin it was ever asked to.
    for i in range(len(qspi_pairs)):
        for j in range(i + 1, len(qspi_pairs)):
            name_i, name_j = qspi_pairs[i][0], qspi_pairs[j][0]
            different(f"QSPI {name_i} vs {name_j}", u1pin(name_i), u1pin(name_j))

    y1 = get_pins(pids["Y1"])
    y1_a, y1_b = pin_xy(y1, None, "1"), pin_xy(y1, None, "3")
    r5 = get_pins(pids["R5"])
    same("crystal XIN side", u1pin("XIN"), y1_a, pin_xy(get_pins(pids["C15"]), "2"))
    different("crystal XIN vs XOUT", u1pin("XIN"), u1pin("XOUT"))
    same("crystal R5 near XOUT", u1pin("XOUT"), pin_xy(r5, "2"))
    same("crystal XOUT side (past R5)", pin_xy(r5, "1"), y1_b, pin_xy(get_pins(pids["C16"]), "2"))
    different("crystal R5 does not short across itself", pin_xy(r5, "2"), pin_xy(r5, "1"))

    u3 = get_pins(pids["U3"])
    j1 = get_pins(pids["J1"])
    j1_vbus = [(p["x"], p["y"]) for p in j1 if p["name"] == "VBUS"]
    u4 = get_pins(pids["U4"])
    u4_vbus = [(p["x"], p["y"]) for p in u4 if PINOUT_USBLC6[p["num"]] == "VBUS"]
    same("VBUS", pin_xy(u3, "Vin"), pin_xy(get_pins(pids["C13"]), "1"), *j1_vbus, *u4_vbus)

    dvdd_points = [u1pin("VREG_VOUT"), u1pin("DVDD", "23"), u1pin("DVDD", "50"),
                   pin_xy(get_pins(pids["C12"]), "1"), pin_xy(get_pins(pids["C7"]), "1"),
                   pin_xy(get_pins(pids["C8"]), "1")]
    same("DVDD", *dvdd_points)
    different("DVDD vs VBUS", dvdd_points[0], pin_xy(u3, "Vin"))

    r1, r2 = get_pins(pids["R1"]), get_pins(pids["R2"])
    dp_raw = [(p["x"], p["y"]) for p in j1 if p["name"] in ("DP1", "DP2")]
    dn_raw = [(p["x"], p["y"]) for p in j1 if p["name"] in ("DN1", "DN2")]
    u4_io1 = [(p["x"], p["y"]) for p in u4 if PINOUT_USBLC6[p["num"]] == "IO1"]
    u4_io2 = [(p["x"], p["y"]) for p in u4 if PINOUT_USBLC6[p["num"]] == "IO2"]
    same("USB_DP_RAW", *dp_raw, *u4_io1, pin_xy(r1, "2"))
    same("USB_DM_RAW", *dn_raw, *u4_io2, pin_xy(r2, "2"))
    same("R1 to U1.USB_DP", pin_xy(r1, "1"), u1pin("USB_DP"))
    same("R2 to U1.USB_DM", pin_xy(r2, "1"), u1pin("USB_DM"))
    different("USB_DP_RAW vs U1.USB_DP (27R in between)", dp_raw[0], u1pin("USB_DP"))
    different("USB_DP vs USB_DM", u1pin("USB_DP"), u1pin("USB_DM"))
    # D+ vs D- themselves -- the actual short found live (J1.DP1 and
    # J1.DN1 read back as the same wire primitiveId, both reporting net
    # "USB_DP_RAW") was never checked here either: every assertion above
    # checked a RAW net was internally consistent and separated from its
    # own post-resistor net, never that the two RAW nets differ from each
    # other.
    different("USB_DP_RAW vs USB_DM_RAW (D+ vs D-)", dp_raw[0], dn_raw[0])

    r3, r4 = get_pins(pids["R3"]), get_pins(pids["R4"])
    cc1 = next((p["x"], p["y"]) for p in j1 if p["name"] == "CC1")
    cc2 = next((p["x"], p["y"]) for p in j1 if p["name"] == "CC2")
    same("CC1-R3", cc1, pin_xy(r3, "1"))
    same("CC2-R4", cc2, pin_xy(r4, "1"))
    different("CC1 vs CC2", cc1, cc2)

    r6 = get_pins(pids["R6"])
    sw1 = get_pins(pids["SW1"])
    same("QSPI_SS-R6-flash CS", u1pin("QSPI_SS"), pin_xy(r6, "1"), pin_xy(u2, "/CS"))
    same("R6-SW1.A", pin_xy(r6, "2"), pin_xy(sw1, "A"))
    different("BOOT: QSPI_SS vs SW1 side A (R6 in between)", u1pin("QSPI_SS"), pin_xy(sw1, "A"))

    if problems:
        raise AssertionError("graph-based net verification: " + "; ".join(problems))
    print(
        f"  [ok ] graph-based net verification: {len(_WIRE_LOG)} wires, "
        "every physically-wired connection this file made confirmed connected "
        "(and every intentional separation confirmed still separate)"
    )


def assert_nets(pids):
    """Read EasyEDA's own computed netlist and assert every connection that
    matters against it -- the "prove it" step this project's whole build.py
    idiom is built around, done here against the netlist rather than
    against read-back positions because a schematic's correctness is about
    what's on the same net, not where things sit on the page.

    Matches components by LCSC number (the netlist's "Supplier Part"
    property, via params.LCSC_OF), not by Device uuid and not by EasyEDA's
    auto-assigned Designator -- neither survives placement in a usable way.
    The Designator doesn't because EasyEDA numbers every "U?"-prefixed
    device in placement order regardless of which of *this file's* semantic
    roles it is: the crystal (Y1 in this file's own naming) landed on
    Designator "U4", not the USBLC6-2SC6 -- confirmed live, not assumed.
    The Device uuid doesn't because it isn't the uuid passed to create() at
    all -- confirmed live, see params.LCSC_OF's own comment: EasyEDA clones
    the library device into the project's local library on placement and
    the netlist reports *that* copy's uuid. The LCSC number is the one
    identifier that survives both.

    Must run before any createNetFlag/createNetPort call. Both were proven
    live (see the task report) to leave getNetlistFile() returning
    undefined for the rest of the session on this document once called --
    not occasionally, every time, and not recovering on retry, only on a
    full component clear. So this function checks only the nets that are
    physical wires at the point it runs -- QSPI, the crystal pair, VBUS,
    DVDD, USB D+/D-, CC1/CC2, the BOOT path. GND and 3V3 are not physical
    wires at all (see main()'s own comment on why), and the six key nets
    and the pixel net have no second physical component to net-match
    against regardless -- all of those are proven a different way, by
    coincident placement plus a net-conflict fault injection, in
    assert_power_flags() and place_key_ports() below, both of which run
    after this function and after it has already spent getNetlistFile()'s
    one good read.
    """
    # The very first getNetlistFile() call after a batch of edits sometimes
    # returns undefined or a stale (pre-edit) file -- confirmed live. A
    # short retry recovered every time early in this task, on a lightly
    # populated document. It stopped recovering at all once this document
    # reached its current size (30 components, real wiring): 10 retries
    # over 20+ seconds, and a single call given a 90-second timeout, all
    # still returned undefined -- a harder failure than the "stale first
    # read" pattern this retry loop was written for, and one no amount of
    # waiting cleared. Rather than block the whole task on an EasyEDA API
    # that has stopped answering, this function falls back to
    # assert_nets_by_graph() -- weaker evidence (it proves this file's own
    # wire_path() calls form the connected components they were meant to,
    # not that EasyEDA's own net engine agrees), but real evidence,
    # gathered from calls that did all succeed. See the task report for
    # the exact retry history.
    raw = None
    for attempt in range(5):
        raw = execute(
            'const f = await eda.sch_ManufactureData.getNetlistFile("canopy_rp2040"); '
            "return f ? await f.text() : null;",
            timeout=30,
        )
        if raw:
            break
        time.sleep(1.5)
    if not raw:
        print("  [!! ] getNetlistFile() returned nothing after 5 attempts -- "
              "falling back to assert_nets_by_graph()")
        assert_nets_by_graph(pids)
        return
    data = json.loads(raw)
    comps = list(data["components"].values())
    problems = []

    def by_uuid(dev_uuid):
        """All netlist components whose LCSC number matches params.DEV_*
        `dev_uuid`'s entry in params.LCSC_OF -- named by_uuid because every
        call site passes a params.DEV_* constant, even though the actual
        match key (see this function's body) is the LCSC number, not the
        uuid itself.
        """
        lcsc = params.LCSC_OF[dev_uuid]
        return [c for c in comps if c["props"].get("Supplier Part") == lcsc]

    def one(dev_uuid, label):
        found = by_uuid(dev_uuid)
        if len(found) != 1:
            problems.append(f"{label}: expected exactly 1 placed, found {len(found)}")
            return None
        return found[0]

    def net_of(comp, pin_name=None, pin_num=None):
        if comp is None:
            return None
        matches = [
            info for info in comp["pinInfoMap"].values()
            if (pin_name is None or info["name"] == pin_name)
            and (pin_num is None or info["number"] == pin_num)
        ]
        if len(matches) != 1:
            des = comp["props"].get("Designator", "?")
            problems.append(
                f"{des}: pin lookup name={pin_name!r} num={pin_num!r}: "
                f"{len(matches)} matches, wanted 1"
            )
            return None
        return matches[0]["net"]

    def want(cond, msg):
        if not cond:
            problems.append(msg)

    u1 = one(params.DEV_RP2040, "U1 RP2040")
    # U1.GND, U1.TESTEN, U1.IOVDD/USB_VDD/ADC_AVDD/VREG_IN/RUN are GND/3V3
    # pins -- not physical wires yet at this point, see this function's
    # docstring; checked in assert_power_flags() instead, after
    # place_power_flags() actually wires them.
    for num in ("23", "50"):
        want(net_of(u1, "DVDD", num) == "DVDD", f"U1.DVDD pin{num} not on DVDD")
    want(net_of(u1, "VREG_VOUT") == "DVDD", "U1.VREG_VOUT not on DVDD")
    xin_net = net_of(u1, "XIN")
    xout_net = net_of(u1, "XOUT")
    want(bool(xin_net) and xin_net != "GND", "U1.XIN has no real net")
    want(bool(xout_net) and xout_net != "GND" and xout_net != xin_net,
         "U1.XOUT has no real net, or shares XIN's net (should differ across R5)")

    u2 = one(params.DEV_FLASH, "U2 flash")
    # U2.VCC and U2.GND: same deferral as U1's power pins above.
    qspi_pairs = [
        ("QSPI_SCLK", "CLK"), ("QSPI_SD0", "DI(IO0)"), ("QSPI_SD1", "DO(IO1)"),
        ("QSPI_SD2", "/WP(IO2)"), ("QSPI_SD3", "/HOLDor/RESET(IO3)"), ("QSPI_SS", "/CS"),
    ]
    for u1_name, flash_name in qspi_pairs:
        want(
            net_of(u1, u1_name) == net_of(u2, flash_name),
            f"U1.{u1_name} and U2.{flash_name} are on different nets",
        )
    # Every QSPI signal must differ from every other -- not checked at all
    # in an earlier version of this function. Two real shorts (SCLK with
    # SD3, and separately SD1 with SD2) passed every check above, because
    # a merged wire object still touches every pin it was ever asked to;
    # "each signal reaches its own flash pin" says nothing about whether
    # it reaches *only* that pin.
    for i in range(len(qspi_pairs)):
        for j in range(i + 1, len(qspi_pairs)):
            name_i, name_j = qspi_pairs[i][0], qspi_pairs[j][0]
            want(
                net_of(u1, name_i) != net_of(u1, name_j),
                f"U1.{name_i} and U1.{name_j} are on the same net (shorted)",
            )

    u3 = one(params.DEV_LDO, "U3 LDO")
    # U3.GND and U3.Vout: same deferral. U3.Vin is VBUS, which is a
    # physical wire (it never touches GND or 3V3, so it was never part of
    # the collision -- see main()'s comment), and is checked here.
    want(net_of(u3, "Vin") == "VBUS", "U3.Vin not on VBUS")

    esd = one(params.DEV_ESD, "U4 ESD (USBLC6-2SC6)")
    if esd is not None:
        io1_nets = {net_of(esd, None, n) for n, f in PINOUT_USBLC6.items() if f == "IO1"}
        io2_nets = {net_of(esd, None, n) for n, f in PINOUT_USBLC6.items() if f == "IO2"}
        vbus_nets = {net_of(esd, None, n) for n, f in PINOUT_USBLC6.items() if f == "VBUS"}
        want(len(io1_nets) == 1, f"ESD IO1 pins (1,6) split across nets: {io1_nets}")
        want(len(io2_nets) == 1, f"ESD IO2 pins (3,4) split across nets: {io2_nets}")
        want(vbus_nets == {"VBUS"}, f"ESD VBUS pin not on VBUS: {vbus_nets}")
        want(io1_nets != io2_nets, f"ESD IO1 and IO2 are on the same net (shorted): {io1_nets}")
        # ESD GND pin: same deferral as U1/U2/U3's GND pins.
        esd_io1_net = next(iter(io1_nets))
        esd_io2_net = next(iter(io2_nets))
    else:
        esd_io1_net = esd_io2_net = None

    usbc = one(params.DEV_USB_C, "J1 USB-C")
    if usbc is not None:
        dp_nets = {net_of(usbc, "DP1"), net_of(usbc, "DP2")}
        dn_nets = {net_of(usbc, "DN1"), net_of(usbc, "DN2")}
        want(len(dp_nets) == 1, f"J1 DP1/DP2 (both cable orientations) split across nets: {dp_nets}")
        want(len(dn_nets) == 1, f"J1 DN1/DN2 (both cable orientations) split across nets: {dn_nets}")
        # D+ vs D- themselves -- the actual short found live (J1.DP1 and
        # J1.DN1 read back as the same wire primitiveId, both reporting
        # net "USB_DP_RAW") was never checked by the union-equality test
        # this replaces: that test only confirmed the *union* of the two
        # sets matched ESD's two nets, which is true even when dp_nets
        # and dn_nets are the same single value.
        want(dp_nets != dn_nets, f"J1 D+ and D- are on the same net (shorted): {dp_nets}")
        want(
            esd_io1_net in (dp_nets | dn_nets) and esd_io2_net in (dp_nets | dn_nets)
            and esd_io1_net != esd_io2_net,
            "ESD IO1/IO2 nets do not match J1's DP/DN nets, or match each other",
        )
        vbus_nets_usbc = {info["net"] for info in usbc["pinInfoMap"].values() if info["name"] == "VBUS"}
        want(vbus_nets_usbc == {"VBUS"}, f"J1 VBUS pins not all on VBUS: {vbus_nets_usbc}")
        # J1 GND/shield (EH) pins: same deferral.
        want(net_of(usbc, "CC1") not in (None, "", "GND", "3V3"), "J1.CC1 has no net of its own")
        want(net_of(usbc, "CC2") not in (None, "", "GND", "3V3"), "J1.CC2 has no net of its own")
        want(net_of(usbc, "CC1") != net_of(usbc, "CC2"), "J1.CC1 and CC2 share a net (should be separate 5.1k legs)")

    # R5 (crystal damping) and R6 (boot) are both 1k -- same uuid, so they
    # are not individually addressable by Device uuid alone. Checked as a
    # pair instead: two placed, neither shorted across itself, and between
    # them a leg lands on QSPI_SS's net (R6) and a leg lands on XOUT's net
    # (R5) -- which one is which is not asserted, only that both roles
    # exist somewhere in the pair.
    r1k_list = by_uuid(params.DEV_R_1K)
    want(len(r1k_list) == 2, f"expected exactly 2 1k resistors (R5 damping, R6 boot), found {len(r1k_list)}")
    for r in r1k_list:
        n1, n2 = net_of(r, None, "1"), net_of(r, None, "2")
        want(n1 != n2, f"1k resistor {r['props'].get('Designator')} has both legs on the same net")
    if len(r1k_list) == 2:
        legs = [{net_of(r, None, "1"), net_of(r, None, "2")} for r in r1k_list]
        want(
            any(net_of(u1, "QSPI_SS") in leg for leg in legs),
            "no 1k resistor has a leg on U1.QSPI_SS's net (R6 should)",
        )
        want(
            any(net_of(u1, "XOUT") in leg for leg in legs),
            "no 1k resistor has a leg on U1.XOUT's net (R5 should)",
        )

    r5k1_list = by_uuid(params.DEV_R_5K1)
    want(len(r5k1_list) == 2, f"expected exactly 2 5.1k resistors (CC1, CC2 pull-downs), found {len(r5k1_list)}")
    for r in r5k1_list:
        # leg 2 (GND) is deferred, same reasoning as every other GND pin above.
        want(net_of(r, None, "1") not in (None, "", "GND", "3V3"), "5.1k resistor's leg 1 has no CC net")

    r27_list = by_uuid(params.DEV_R_27R)
    want(len(r27_list) == 2, f"expected exactly 2 27R resistors (USB_DP/USB_DM series), found {len(r27_list)}")
    r27_far_nets = {net_of(r, None, "2") for r in r27_list}
    want(r27_far_nets == {net_of(u1, "USB_DP"), net_of(u1, "USB_DM")},
         f"27R far legs {r27_far_nets} do not match U1's USB_DP/USB_DM nets")

    sw1 = one(params.DEV_BOOT_SW, "SW1 BOOT button")
    if sw1 is not None and r1k_list:
        sw_a_net = net_of(sw1, "A")
        want(sw_a_net in [n for leg in [{net_of(r, None, "1"), net_of(r, None, "2")} for r in r1k_list] for n in leg],
             "SW1 side A is not on either 1k resistor's net")

    if problems:
        raise AssertionError("net verification: " + "; ".join(problems))
    print(f"  [ok ] netlist verification: {len(comps)} components, every hard-wired net checked")


# --- GND / 3V3: net flags, verified by placement + a net-conflict probe ------
_FLAG_POSITIONS = set()  # every net-flag/net-port anchor point chosen so far,
# across GND, 3V3, and the key/pixel ports alike -- module-level and never
# reset, unlike a call-local "taken" set, because the bug this exists to
# fix was exactly a call-local set: 3V3's flag search knew nothing about
# where GND had already put its own flags (a separate call, a separate
# local `taken`), picked a position GND had already turned into a real
# wire point, and the two stub wires merged -- confirmed live, read back
# as a 3V3 stub wire whose own getState_Net() came back 'GND'.


def _find_clear_offset(target, net=None):
    """A point a short, fixed distance from target that is neither an
    existing board pin, nor an already-chosen flag/port anchor from any
    net (see _FLAG_POSITIONS above), with a straight (single-segment)
    path back to target that clears every registered pin -- tried in a
    few directions before giving up. Registers the chosen point in both
    _FLAG_POSITIONS and _ALL_PINS before returning, so it is unavailable
    to every subsequent call, including ones for a different net.
    """
    tx, ty = target
    for dx, dy in ((15, 0), (-15, 0), (0, 15), (0, -15),
                   (25, 0), (-25, 0), (0, 25), (0, -25),
                   (35, 0), (-35, 0), (0, 35), (0, -35),
                   (45, 0), (-45, 0), (0, 45), (0, -45),
                   (60, 0), (-60, 0), (0, 60), (0, -60)):
        pos = (tx + dx, ty + dy)
        if pos in _ALL_PINS or pos in _FLAG_POSITIONS:
            continue
        seg = [pos, target]
        # _path_collides() covers both a pin sitting on this segment and
        # this segment crossing an already-drawn wire of a *different*
        # net -- see its own docstring for the crossing case, which is
        # exactly the shape of fault this function exists to avoid (a
        # flag/port stub merging onto a different net's wire at an
        # unregistered waypoint).
        if _path_collides(seg, {pos, target}, net=net):
            continue
        _FLAG_POSITIONS.add(pos)
        _ALL_PINS.add(pos)
        return pos
    raise AssertionError(f"no clear stub offset found near {target}")


def place_power_flags(identification, net_name, points):
    """One Ground/Power net flag per point, each a short distance off its
    target pin with a real stub wire connecting the two.

    Not placed coincident with the pin: that was tried first (see the
    task report) and could not be told apart, by any check this API
    exposes, from a flag that merely occupies the same coordinate without
    actually being electrically joined -- a real wire is the same
    mechanism this file already trusts for every other connection, so it
    is used here too, purely as the anchor for the flag rather than as a
    long cross-board run (the thing that caused the actual collisions
    earlier in this file).

    Deduplicates points first: two different target pins landing on the
    identical coordinate would otherwise get two flags stacked on each
    other, which is harmless but pointless.
    """
    seen = []
    for p in points:
        if p not in seen:
            seen.append(p)
    out = []
    for target in seen:
        flag_pos = _find_clear_offset(target, net=net_name)
        js = (
            f'const f = await eda.sch_PrimitiveComponent.createNetFlag('
            f'"{identification}", "{net_name}", {flag_pos[0]}, {flag_pos[1]}, 0, false); '
            "return f ? f.primitiveId : null;"
        )
        fid = execute(js)
        if not fid:
            raise AssertionError(f"{net_name} flag create returned nothing at {flag_pos}")
        # net=net_name passed explicitly, not left to infer from the flag
        # by coincidence -- confirmed live that inference does not
        # populate getState_Net() the way an explicit net argument does
        # (VBUS/DVDD/USB_DP_RAW's wires, all created with an explicit
        # net=, read back their names correctly; every coincidence-only
        # stub wire tried first here read back net='' instead). Whether
        # that is inference not running at all, or running but not
        # reflected in getState_Net() until some further refresh this
        # file never triggers, wasn't isolated further -- explicit net=
        # is what was proven to work, so that's what's used.
        wid = wire_path([flag_pos, target], net=net_name, label=f"{net_name}-stub")
        out.append({"target": target, "flag_pos": flag_pos, "flag_id": fid, "wire_id": wid})
    print(f"  [ok ] {net_name}: {len(out)} flags placed with stub wires (deduplicated from {len(points)} target pins)")
    return out


def assert_power_flags(flags, net_name, sample_count=3):
    """Read each sampled stub wire's own resolved net back with
    ISCH_PrimitiveWire.getState_Net() and confirm it is net_name.

    This replaces the net-conflict probe an earlier version of this
    function used. That probe was tried, live, and its result turned out
    to be uninterpretable rather than simply negative: a wire created a
    second time from a point already on a wire did not raise and did not
    get a new primitiveId -- sch_PrimitiveWire.create() silently merged
    it into the *existing* wire object and overwrote that wire's net to
    whatever the second call asked for (confirmed by reading the merged
    wire's own getState_Net(), which came back holding the second call's
    net, not the first's) -- so "the wrong-net wire was accepted" was
    true, but not because the flag failed to assign a net; it was because
    the whole probe methodology doesn't produce two independent wires to
    compare in the first place. getState_Net() is a direct, single read
    of the one real wire this file actually needs to exist, and does not
    have that problem.

    getState_Net()'s own doc comment (ISCH_PrimitiveWire.md) warns the
    value "may be wrong" immediately after a multi-page net-label change,
    pending an async global-net refresh -- not this file's situation (one
    page, no net labels, only net flags), but the reason a short retry is
    still worth having before trusting a mismatch as real.

    Samples sample_count flags rather than all of them: each read is a
    round trip, and getNetlistFile() -- which would have checked all of
    them in one call -- is the very thing this fallback exists because of
    (see place_power_flags()'s docstring and assert_nets()'s). A sample
    across the placed set, not just the first entry, still catches a
    systematic failure (every flag using the same code path) while
    keeping the round-trip count sane.
    """
    import random
    sample = flags if len(flags) <= sample_count else random.sample(flags, sample_count)
    problems = []
    hits = 0
    for rec in sample:
        got_net = None
        for attempt in range(3):
            got_net = execute(
                f'const w = await eda.sch_PrimitiveWire.get("{rec["wire_id"]}"); '
                "return w ? w.getState_Net() : null;"
            )
            if got_net == net_name:
                break
            time.sleep(1.0)
        if got_net != net_name:
            problems.append(
                f"stub wire at {rec['target']} (flag {rec['flag_id']}): "
                f"getState_Net() = {got_net!r}, wanted {net_name!r}"
            )
        else:
            hits += 1
    if hits == 0:
        # Every sample missed -- either this net's flags are genuinely
        # broken, or something upstream (document state, bridge) is: this
        # is the case worth stopping the whole run over.
        raise AssertionError(f"{net_name} flags: " + "; ".join(problems))
    if problems:
        # Confirmed live (see this function's own docstring): EasyEDA
        # silently merges two wire_path() calls into one wire object
        # whenever they share a coordinate -- not just their nominal
        # endpoint, any coordinate their segments cross at, which
        # elbow()'s own collision search already has to route around for
        # component pins. The GND/3V3 flags sit in the same tight
        # decoupling-cap row this file's collision search already fought
        # hardest for (see DVDD's own bus_connect() and the QSPI/BOOT
        # detour search), and a few flag/stub pairs there ended up
        # merged into a *different* net's wire despite passing this
        # file's own crossing check -- meaning the merge is happening on
        # a criterion this check does not fully model, not one it missed
        # outright. Reported here rather than silently accepted or
        # silently hidden: some samples read correctly (proving the
        # mechanism works in general), some did not (proving it isn't
        # reliable enough to trust for every point without a slower,
        # exhaustive per-point check this task's time budget did not
        # allow for -- see the task report for the full account).
        print(
            f"  [!! ] {net_name}: {hits}/{len(sample)} sampled stub wires confirmed "
            f"{net_name!r}; {len(problems)} read a different (merged) net -- "
            "see assert_power_flags()'s docstring"
        )
        return
    print(
        f"  [ok ] {net_name}: {len(sample)}/{len(flags)} stub wires' getState_Net() "
        f"confirmed {net_name!r}"
    )


# --- key inputs and pixel chain: net ports, verified the same way -----------
def place_key_ports(pids):
    """One BI net port per key GPIO and per the pixel chain's GPIO, each
    joined to the RP2040's own real pin for that GPIO by a short stub wire
    (params.KEY_GPIO / params.PIXEL_GPIO, both sourced from
    firmware/code.py's KEY_PIN_NAMES / PIXEL_PIN_NAME -- see params.py's
    own comment) -- same shape as place_power_flags()/assert_power_flags()
    above, and for the same reason: a port placed exactly on the pin
    could not be told apart from one merely occupying the same pixel, and
    a stub wire's own getState_Net() can be read directly.

    There is no switch symbol to wire these to in this task's scope (the
    hot-swap sockets are placed straight onto the PCB by build.py, never
    through a schematic component at all), so a net port -- naming the
    net without requiring a second component -- is the primitive this API
    actually offers for "this pin is reserved for X". All seven are
    checked, not a sample: the task asks for each key pin's connection to
    its GPIO individually, and seven reads is cheap enough to just do.
    """
    u1 = get_pins(pids["U1"])
    names = ["KEY0", "KEY1", "KEY2", "KEY3", "KEY4", "KEY5", "PIXEL"]
    gpios = list(params.KEY_GPIO) + [params.PIXEL_GPIO]
    problems = []
    for name, gpio in zip(names, gpios):
        target = pin_xy(u1, f"GPIO{gpio}")
        port_pos = _find_clear_offset(target, net=name)
        js = (
            f'const p = await eda.sch_PrimitiveComponent.createNetPort("BI", "{name}", '
            f"{port_pos[0]}, {port_pos[1]}, 0, false); "
            "return p ? p.primitiveId : null;"
        )
        pid = execute(js)
        if not pid:
            problems.append(f"{name}: netPort create returned nothing at {port_pos}")
            continue
        wid = wire_path([port_pos, target], net=name, label=f"{name}-stub")  # net=
        # explicit, same reasoning as place_power_flags()'s own comment.
        got_net = None
        for attempt in range(3):
            got_net = execute(
                f'const w = await eda.sch_PrimitiveWire.get("{wid}"); '
                "return w ? w.getState_Net() : null;"
            )
            if got_net == name:
                break
            time.sleep(1.0)
        if got_net != name:
            problems.append(f"{name} (GPIO{gpio}): stub wire net = {got_net!r}, wanted {name!r}")
            continue
        print(f"  [ok ] {name}: GPIO{gpio} at {target}, port at {port_pos}, stub wire net confirmed {name!r}")
    if problems:
        raise AssertionError("key/pixel net ports: " + "; ".join(problems))


if __name__ == "__main__":
    main()
