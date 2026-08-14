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
    xs = [params.mm_to_mil(x) for x, _ in params.switch_centres_mm()]
    y = params.mm_to_mil(params.SWITCH_Y)
    if inject:
        xs[-1] -= params.mm_to_mil(params.SWITCH_PITCH) // 2
        print(f"INJECTED: last socket moved to {xs[-1]}, the check must FAIL")
    for x in xs:
        js = (
            f'const dev = {{libraryUuid: "{params.LIB_UUID}", '
            f'uuid: "{params.DEV_MX_SOCKET}"}}; '
            f"const c = await eda.pcb_PrimitiveComponent.create("
            f"dev, {TOP}, {x}, {y}, 0, false); "
            "return c ? c.primitiveId : null;"
        )
        if not execute(js):
            raise AssertionError(f"create returned nothing for x={x}")
    return xs


def place_pixels(inject=False):
    """One pixel per switch, at params.PIXEL_OFFSET_MM from its centre.

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
            f"dev, {TOP}, {x}, {py}, 0, false); "
            "return c ? c.primitiveId : null;"
        )
        if not execute(js):
            raise AssertionError(f"create returned nothing for x={x}, y={py}")
    return list(zip(xs, ys))


def verify_pixel_pairing(placed):
    """Group every placed component by x and check each group is a pair.

    This reads pairing off the document, not off what was asked for: a
    socket and its pixel share x exactly (PIXEL_OFFSET_MM's x is 0.0), so
    each of the KEY_COUNT x-values must carry exactly two components,
    separated by exactly -PIXEL_OFFSET_MM's y. It does not determine which
    of the pair is the socket and which is the pixel -- it only checks
    `max(ys) - min(ys)` against the expected gap, so two components of the
    same kind that happened to land that far apart would pass just as
    silently as a correct pair.
    """
    want_gap = -params.mm_to_mil(params.PIXEL_OFFSET_MM[1])
    groups = {}
    for c in placed:
        groups.setdefault(c["x"], []).append(c["y"])

    if len(groups) != params.KEY_COUNT:
        raise AssertionError(
            f"expected {params.KEY_COUNT} x-groups, got {len(groups)}: "
            f"{sorted(groups)}"
        )

    bad = []
    for x, ys in sorted(groups.items()):
        if len(ys) != 2:
            bad.append((x, ys))
            continue
        gap = max(ys) - min(ys)
        if gap != want_gap:
            bad.append((x, ys))
    if bad:
        detail = ", ".join(f"x={x}: ys={ys}" for x, ys in bad)
        raise AssertionError(f"pixel pairing: {detail} (wanted gap {want_gap})")
    print(f"  [ok ] pixel pairing: {len(groups)} pairs, all gap {want_gap} mil")


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

    place_pixels(inject_pixel)
    placed_all = probe.placed_components()

    want_total = 2 * params.KEY_COUNT
    if len(placed_all) != want_total:
        raise AssertionError(f"placed {len(placed_all)} total, wanted {want_total}")
    print(f"  [ok ] total count: {len(placed_all)}")

    verify_pixel_pairing(placed_all)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
