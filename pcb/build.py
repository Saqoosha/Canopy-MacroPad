# pcb/build.py
"""Build the key field and prove it landed where it was told to.

Run with: python3 pcb/build.py [--inject] [--inject-pixel]

--inject places the last socket half a pitch out and --inject-pixel nudges
one pixel's y off its switch's offset -- two distinct faults, so each check
can be watched going red on its own rather than trusted from the other's
failure. A run that has only ever been green is not evidence.
"""
import os
import sys

import board_edge
import params
import probe
from bridge import execute

# The project is opened by name and never created. dmt_Project.createProject()
# returns undefined under every argument shape tried -- six of them, no
# exception raised, no project appearing -- and the sibling
# dmt_Folder.getAllFoldersUuid() throws on a missing internal `rootList`. The
# folder subsystem simply is not populated in this client's local, half-offline
# mode, and creation rides on it. So the project is made by hand in the GUI
# once, and this constant names whichever one that is.
PROJECT_NAME = os.environ.get("MPAD_EDA_PROJECT", "Canopy MacroPad")
TOP = 1          # EPCB_LayerId.TOP; the enum object is absent from the bridge
                 # execution context, so the documented literal is what works.
BOTTOM = 2       # EPCB_LayerId.BOTTOM; same reasoning as TOP.

# Residual expected between crkbd's and this EasyEDA device's own drawing of
# the same physical socket -- confirmed up to ~0.18 mm, not chased further.
# 0.30 mm is generous against that and still two orders of magnitude below
# the ~6 mm miss Fault 1 actually produced, so it cannot mask a real one.
SOCKET_PAD_TOLERANCE_MM = 0.30


def open_project_pcb():
    """Open the project's first PCB and leave it active.

    dmt_Project.createProject() is beta and returns undefined without
    explaining itself, so the project is made by hand once and opened here.
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
        "const pcbs = await eda.dmt_Pcb.getAllPcbsInfo(); "
        "if (!pcbs || !pcbs.length) return {error: 'project has no PCB'}; "
        "await eda.dmt_EditorControl.openDocument(pcbs[0].uuid); "
        "const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo(); "
        "return {opened: n, pcb: pcbs[0].name, documentType: doc.documentType}; "
        "} } } "
        "return {error: 'project not found'};"
    ).replace("'", '"')
    got = execute(js)
    if got.get("error"):
        raise SystemExit(f"cannot open the board: {got['error']}")
    if got["documentType"] != 3:
        raise SystemExit(f"active document is type {got['documentType']}, not PCB")
    print(f"opened {got['opened']} / {got['pcb']}")


def place_sockets(inject=False):
    """One socket per switch, at params.SOCKET_OFFSET_MM from its centre,
    on BOTTOM (the y-mirror Fault 1 needs, and where the design spec puts
    everything but the switch pads anyway -- see params.py's comment on
    SOCKET_OFFSET_MM).
    """
    dx = params.mm_to_mil(params.SOCKET_OFFSET_MM[0])
    dy = params.mm_to_mil(params.SOCKET_OFFSET_MM[1])
    xs = [params.mm_to_mil(x) + dx for x, _ in params.switch_centres_mm()]
    y = params.mm_to_mil(params.SWITCH_Y) + dy
    if inject:
        xs[-1] -= params.mm_to_mil(params.SWITCH_PITCH) // 2
        print(f"INJECTED: last socket moved to {xs[-1]}, the check must FAIL")
    for x in xs:
        js = (
            f'const dev = {{libraryUuid: "{params.LIB_UUID}", '
            f'uuid: "{params.DEV_CHOC_SOCKET}"}}; '
            f"const c = await eda.pcb_PrimitiveComponent.create("
            f"dev, {BOTTOM}, {x}, {y}, 0, false); "
            "return c ? c.primitiveId : null;"
        )
        if not execute(js):
            raise AssertionError(f"create returned nothing for x={x}")
    return xs


def place_pixels(inject=False):
    """One pixel per switch, at params.PIXEL_OFFSET_MM from its centre, on
    BOTTOM -- a reverse-mount pixel is soldered to the back and shines up
    through the board's opening; on TOP it lights the inside of the case
    instead. Adafruit's own Choc board (adafruit/Adafruit-NeoKey-CHOC-
    Breakout-PCB) places both SW1 and LED1 with Eagle's MR0 (mirrored),
    confirming this is true of the socket and the pixel alike, not just
    the socket Fault 1 already fixed.

    Rotated 180 -- BOTTOM alone (rotation 0) places VDD/DOUT/GND/DIN
    rotated 180 from where params.PIXEL_SIGNAL_QUADRANT (and both
    reference boards) put them: the part is electrically correct either
    way (the signal-to-pad mapping never moves), but with DOUT on -x and
    DIN on +x a left-to-right chain across the six switches would double
    back past its own component at every hop. Confirmed live, not
    derived by hand, that BOTTOM + rotation 180 is what actually produces
    the wanted quadrant for every pad -- see assert_pixel_signal_
    orientation()'s clean run below.

    --inject-pixel nudges pixel 0's y off that offset while leaving its x
    alone, so it fails the pairing check rather than the count -- a fault
    distinct from place_sockets()'s, which moves an x.
    """
    dx = params.mm_to_mil(params.PIXEL_OFFSET_MM[0])
    dy = params.mm_to_mil(params.PIXEL_OFFSET_MM[1])
    xs = [params.mm_to_mil(x) + dx for x, _ in params.switch_centres_mm()]
    y = params.mm_to_mil(params.SWITCH_Y) + dy
    ys = [y] * len(xs)
    if inject:
        ys[0] += params.mm_to_mil(params.SWITCH_PITCH) // 4
        print(f"INJECTED: pixel 0 moved to y={ys[0]}, the check must FAIL")
    for x, py in zip(xs, ys):
        js = (
            f'const dev = {{libraryUuid: "{params.LIB_UUID}", '
            f'uuid: "{params.DEV_PIXEL}"}}; '
            f"const c = await eda.pcb_PrimitiveComponent.create("
            f"dev, {BOTTOM}, {x}, {py}, 180, false); "
            "return c ? c.primitiveId : null;"
        )
        if not execute(js):
            raise AssertionError(f"create returned nothing for x={x}, y={py}")
    return list(zip(xs, ys))


def _quadrant_label(sx, sy):
    return f"{'+' if sx > 0 else '-'}x{'+' if sy > 0 else '-'}y"


def assert_pixel_signal_orientation(pixel_components):
    """Every pixel's VDD/DOUT/GND/DIN pads must sit in the quadrant
    params.PIXEL_SIGNAL_QUADRANT names for that signal, relative to that
    pixel's own origin -- not merely that a pad exists at some x, y.

    Geometry alone cannot answer this question: a pad's position means
    nothing until params.PIXEL_PAD_SIGNALS (the datasheet) says which
    signal that pad number carries. Failure messages name the signal, so
    "DOUT is on the wrong side" is what gets reported, not "pad 2 at
    unexpected x" -- a message that says nothing is wrong even when
    something clearly is.
    """
    problems = []
    for c in pixel_components:
        pins = execute(
            f'const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId("{c["id"]}"); '
            "return (pins || []).map(p => ({padNumber: p.padNumber, x: p.x, y: p.y}));"
        ) or []
        for p in pins:
            signal = params.PIXEL_PAD_SIGNALS.get(p["padNumber"])
            if signal is None:
                problems.append(
                    f"pixel at ({c['x']}, {c['y']}): pad {p['padNumber']} "
                    "has no entry in PIXEL_PAD_SIGNALS"
                )
                continue
            want = params.PIXEL_SIGNAL_QUADRANT[signal]
            got = (
                1 if p["x"] > c["x"] else (-1 if p["x"] < c["x"] else 0),
                1 if p["y"] > c["y"] else (-1 if p["y"] < c["y"] else 0),
            )
            if got != want:
                problems.append(
                    f"pixel at ({c['x']}, {c['y']}): {signal} is at "
                    f"{_quadrant_label(*got)}, wanted {_quadrant_label(*want)}"
                )
    if problems:
        raise AssertionError("pixel signal orientation: " + "; ".join(problems))
    print(
        f"  [ok ] pixel signal orientation: {len(pixel_components)} pixels, "
        "VDD/DOUT/GND/DIN all in the wanted quadrant"
    )


def verify_socket_pads(socket_components):
    """Every socket's own two SMD solder pads must land near
    params.SOCKET_PADS, offset from the switch centre that socket's origin
    was placed at -- not merely that the component's origin landed where
    place_sockets() put it.

    This is the check Fault 1 needed and none of the existing ones were:
    the device's origin is not at the switch centre (it is the midpoint of
    its own two pads), so a component read back at exactly the asked-for
    x/y says nothing about where its pads actually are. Matches each
    wanted pad position to its nearest real pad (not by padNumber, which
    depends on layer/rotation) and requires the match within
    SOCKET_PAD_TOLERANCE_MM.
    """
    problems = []
    for c in socket_components:
        pins = execute(
            f'const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId("{c["id"]}"); '
            "return (pins || []).map(p => ({x: p.x, y: p.y}));"
        ) or []
        actual_mm = [(p["x"] / params.MIL_PER_MM, p["y"] / params.MIL_PER_MM) for p in pins]
        # SOCKET_PADS is offset from the SWITCH CENTRE, not from the
        # component's own origin -- and the component's origin is itself
        # switch centre + SOCKET_OFFSET_MM, not the switch centre. Recover
        # the switch centre by subtracting that offset back out, rather
        # than adding SOCKET_PADS on top of the already-offset origin
        # (which double-counts SOCKET_OFFSET_MM and was wrong the first
        # time this was written -- caught by the very run meant to prove
        # the fix, not by inspection).
        switch_x_mm = c["x"] / params.MIL_PER_MM - params.SOCKET_OFFSET_MM[0]
        switch_y_mm = c["y"] / params.MIL_PER_MM - params.SOCKET_OFFSET_MM[1]
        want_mm = [
            (switch_x_mm + dx, switch_y_mm + dy)
            for (dx, dy), _size in params.SOCKET_PADS
        ]
        available = list(actual_mm)
        for wx, wy in want_mm:
            if not available:
                problems.append(
                    f"socket at ({c['x']}, {c['y']}) mil: no pad left to "
                    f"match wanted ({wx:.2f}, {wy:.2f}) mm"
                )
                continue
            best = min(available, key=lambda a: (a[0] - wx) ** 2 + (a[1] - wy) ** 2)
            dist = ((best[0] - wx) ** 2 + (best[1] - wy) ** 2) ** 0.5
            if dist > SOCKET_PAD_TOLERANCE_MM:
                problems.append(
                    f"socket at ({c['x']}, {c['y']}) mil: nearest real pad "
                    f"({best[0]:.2f}, {best[1]:.2f}) mm is {dist:.3f} mm from "
                    f"wanted ({wx:.2f}, {wy:.2f}) mm"
                )
            else:
                available.remove(best)
    if problems:
        raise AssertionError("socket pads not where crkbd's geometry says: " + "; ".join(problems))
    print(
        f"  [ok ] socket pads: {len(socket_components)} sockets, both pads "
        f"within {SOCKET_PAD_TOLERANCE_MM} mm of crkbd's SOCKET_PADS"
    )


def assert_component_layer(components, want_layer, label):
    """Every component in the list must be on want_layer.

    Fault 3: every check this project had asked where a component is in x
    and y; none asked which side of the board it is on. A reverse-mount
    pixel placed on TOP instead of BOTTOM passed count, position, and
    pairing checks perfectly while lighting the inside of the case instead
    of the keycap -- the component's origin was exactly where it should
    be, on the wrong face. Applies to sockets and pixels alike, since both
    are meant to live on BOTTOM (Fault 1's finding, for the socket;
    Adafruit's own Choc board -- both elements carry Eagle's MR0, mirrored
    -- for the pixel).
    """
    bad = [c for c in components if c["layer"] != want_layer]
    if bad:
        detail = ", ".join(
            f"{c['id']} at ({c['x']}, {c['y']}) is on layer {c['layer']}" for c in bad
        )
        raise AssertionError(f"{label}: wanted layer {want_layer}, {detail}")
    print(f"  [ok ] {label}: {len(components)} on layer {want_layer}")


def verify_component_positions(placed):
    """Every socket must sit at switch centre + SOCKET_OFFSET_MM and every
    pixel at switch centre + PIXEL_OFFSET_MM -- exact expected absolute
    positions, checked as a set against what's actually on the board.

    This replaces the old x-grouped pairing check, which relied on a
    socket and its pixel sharing x (PIXEL_OFFSET_MM's x is 0.0). Fault 1
    ends that coincidence on purpose: SOCKET_OFFSET_MM's x is 2.5, not 0,
    so a socket and its own switch's pixel no longer share an x-coordinate
    at all. A set-equality check needs no such coincidence and is strictly
    more precise than the old one, which only verified a vertical gap
    between *some* two components sharing an x -- it never confirmed
    either one was at the offset it claimed to be.
    """
    want = set()
    for x, y in params.switch_centres_mm():
        want.add((
            params.mm_to_mil(x + params.SOCKET_OFFSET_MM[0]),
            params.mm_to_mil(y + params.SOCKET_OFFSET_MM[1]),
        ))
        want.add((
            params.mm_to_mil(x + params.PIXEL_OFFSET_MM[0]),
            params.mm_to_mil(y + params.PIXEL_OFFSET_MM[1]),
        ))
    got = {(c["x"], c["y"]) for c in placed}
    missing = sorted(want - got)
    extra = sorted(got - want)
    if missing or extra:
        raise AssertionError(
            f"component positions: missing {missing}, extra {extra}"
        )
    print(f"  [ok ] component positions: {len(placed)} components, all at their expected offsets")


BOARD_OUTLINE = 11   # EPCB_LayerId.BOARD_OUTLINE; same "enum absent from the
                     # bridge context" reasoning as TOP/BOTTOM above. There
                     # is no dedicated board-shape API (pcb_BoardOutline does
                     # not exist, and DMT_Board is project-level multi-board
                     # management, a different "board" entirely) -- the
                     # outline is four ordinary lines on this layer, same as
                     # any other drawn shape.


def clear_board_outline():
    """Delete every line on BOARD_OUTLINE, so draw_board_outline() is safe
    to re-run rather than relying on however EasyEDA happens to treat a
    second create() call at coordinates identical to an existing line
    (observed to not duplicate, live -- but that's undocumented behaviour,
    not a guarantee, and this project's rule is not to trust an unproven
    check or an unproven mechanism either).
    """
    js = (
        "const all = await eda.pcb_PrimitiveLine.getAll(11); "
        "if (all && all.length) { await eda.pcb_PrimitiveLine.delete("
        "all.map(l => l.primitiveId)); } "
        "const left = await eda.pcb_PrimitiveLine.getAll(11); "
        "return (left || []).length;"
    )
    left = execute(js)
    if left:
        raise AssertionError(f"clear left {left} outline lines behind")


def draw_board_outline():
    """Draw the one rounded board edge shared with the case."""
    board_edge.apply()


def assert_within_outline():
    """Every pad -- switch hole, socket pad, pixel pad, all of them, since
    footprint.py's holes are pcb_PrimitivePad objects too -- must sit
    inside draw_board_outline()'s rectangle with margin.

    Reports the single tightest margin found, signed: negative means a pad
    is actually outside the board.
    """
    w = params.mm_to_mil(params.BOARD_W)
    d = params.mm_to_mil(params.BOARD_D)
    pads = execute(
        "const all = await eda.pcb_PrimitivePad.getAll(); "
        "return (all || []).map(p => ({x: p.x, y: p.y, pad: p.pad, padNumber: p.padNumber}));"
    ) or []
    if not pads:
        raise AssertionError("no pads on the board to check against the outline")

    tightest = None
    problems = []
    for p in pads:
        pw, ph = p["pad"][1], p["pad"][2]   # ELLIPSE/OVAL/RECT all carry
        hw, hh = pw / 2, ph / 2             # width, height at index 1, 2
        margins = {
            "left": p["x"] - hw,
            "right": w - (p["x"] + hw),
            "top": p["y"] - hh,
            "bottom": d - (p["y"] + hh),
        }
        side, m = min(margins.items(), key=lambda kv: kv[1])
        if tightest is None or m < tightest[0]:
            tightest = (m, p["padNumber"], side, p["x"], p["y"])
        if m < 0:
            problems.append(
                f"{p['padNumber']} at ({p['x']}, {p['y']}) is "
                f"{-m} mil past the {side} edge"
            )
    if problems:
        raise AssertionError("outside the board outline: " + "; ".join(problems))

    m, name, side, x, y = tightest
    print(
        f"  [ok ] board outline margin: tightest is {name} at ({x}, {y}), "
        f"{m} mil ({m * 0.0254:.3f} mm) from the {side} edge"
    )


def assert_drc():
    """Run EasyEDA's own DRC and raise unless it comes back clean.

    userInterface=true so a failure also leaves the bottom DRC panel open
    with the actual error list, since the boolean alone does not say what
    is wrong.
    """
    passed = execute("return await eda.pcb_Drc.check(true, true, false);")
    if not passed:
        raise AssertionError("DRC reported errors; open the PCB and read them")
    print("  [ok ] DRC")


def export_fabrication():
    """Pull Gerber, BOM and pick-and-place from the open PCB and demand
    each came back with bytes in it.

    A `File` that EasyEDA declines to fill still round-trips as a truthy
    object with a zero `.size` -- checking for the object's existence is
    not the same claim as checking that it holds data, and only the
    latter is what a fabricator can use.
    """
    js = (
        'const g = await eda.pcb_ManufactureData.getGerberFile("canopy_macropad"); '
        'const b = await eda.pcb_ManufactureData.getBomFile("canopy_macropad"); '
        'const p = await eda.pcb_ManufactureData.getPickAndPlaceFile("canopy_macropad"); '
        "return {gerber: g ? g.size : 0, bom: b ? b.size : 0, place: p ? p.size : 0};"
    )
    got = execute(js, timeout=120.0)
    for name, size in got.items():
        if not size:
            raise AssertionError(f"{name} came back empty")
    print(f"  [ok ] fabrication: {got}")


def main():
    inject_socket = "--inject" in sys.argv
    inject_pixel = "--inject-pixel" in sys.argv
    open_project_pcb()
    probe.clear_components()
    asked = place_sockets(inject_socket)
    placed = probe.placed_components()

    if len(placed) != params.KEY_COUNT:
        raise AssertionError(f"placed {len(placed)}, wanted {params.KEY_COUNT}")
    print(f"  [ok ] count: {len(placed)}")

    got_xs = [c["x"] for c in placed]
    if got_xs != sorted(asked):
        raise AssertionError(f"read back {got_xs}, asked for {sorted(asked)}")
    print(f"  [ok ] positions: {got_xs}")

    probe.assert_pitch(placed, params.mm_to_mil(params.SWITCH_PITCH), "socket pitch")
    verify_socket_pads(placed)
    assert_component_layer(placed, BOTTOM, "socket layer")

    place_pixels(inject_pixel)
    placed_all = probe.placed_components()

    want_total = 2 * params.KEY_COUNT
    if len(placed_all) != want_total:
        raise AssertionError(f"placed {len(placed_all)} total, wanted {want_total}")
    print(f"  [ok ] total count: {len(placed_all)}")

    verify_component_positions(placed_all)
    sock_ids = {c["id"] for c in placed}
    pixels = [c for c in placed_all if c["id"] not in sock_ids]
    assert_component_layer(pixels, BOTTOM, "pixel layer")
    assert_pixel_signal_orientation(pixels)

    draw_board_outline()
    assert_within_outline()

    assert_drc()
    export_fabrication()

    print("\nall checks passed")


if __name__ == "__main__":
    main()
