"""Cluster MCU-block parts by net after convert, without recreating them.

Convert / Import Changes from Schematic is what owns the nets and the
flying wires. This file only calls pcb_PrimitiveComponent.modify on
existing ids. SK/LED/USBC stay where params put them.

Run: python3 pcb/cluster.py
"""
import json
import sys

import params
from bridge import execute
from place_mcu import (
    BOTTOM,
    MARGIN_MIL,
    assert_layout,
    bbox_size,
    keep,
    move,
    open_pcb,
    overlap,
    pcb_components,
)

INNER1 = 15  # EPCB_LayerId.INNER1
INNER2 = 16  # EPCB_LayerId.INNER2


def save():
    saved = execute("return await eda.pcb_Document.save();")
    if saved is not True:
        raise AssertionError(f"save returned {saved!r}")
    print("saved")


def inside_board(bbox, w, d, margin=MARGIN_MIL):
    return (
        bbox["minX"] >= margin
        and bbox["minY"] >= margin
        and bbox["maxX"] <= w - margin
        and bbox["maxY"] <= d - margin
    )


def try_move(pid, x, y, rot, occupied, w, d):
    got = move(pid, x, y, rot)
    if not inside_board(got["bbox"], w, d):
        return None
    if any(overlap(got["bbox"], occ, margin=0) for occ in occupied):
        return None
    return got


def search_move(pid, x0, y0, rot, occupied, w, d, span=400, step=25):
    """Try (x0,y0) then a spiral of nearby origins."""
    got = try_move(pid, x0, y0, rot, occupied, w, d)
    if got:
        return got
    for r in range(step, span + 1, step):
        for dx, dy in (
            (r, 0),
            (-r, 0),
            (0, r),
            (0, -r),
            (r, r),
            (r, -r),
            (-r, r),
            (-r, -r),
        ):
            got = try_move(pid, x0 + dx, y0 + dy, rot, occupied, w, d)
            if got:
                return got
    return None


def enable_4_layer():
    ok = execute("return await eda.pcb_Layer.setTheNumberOfCopperLayers(4);")
    layers = execute(
        "return (await eda.pcb_Layer.getAllLayers())"
        ".filter(l => [1,2,15,16].includes(l.id))"
        ".map(l => ({id:l.id, name:l.name, status:l.layerStatus}));"
    )
    print(f"  4-layer set={ok} layers={layers}")
    inner = [l for l in layers if l["id"] in (INNER1, INNER2)]
    if not all(l["status"] == 1 for l in inner):
        raise AssertionError(f"inner layers still unused: {inner}")
    print("  [ok ] Inner1 and Inner2 in use")


def pour_planes():
    """Do not create inner pours or plane layers from the API.

    pcb_PrimitivePour.create() leaves an outline Copper Manager lists, but
    rebuildCopperRegion / Rebuild All / Shift+B throw
    `Cannot read properties of undefined (reading 'length')` and fill
    nothing. Watched.

    modifyLayer(INNER*, {type: 'PLANE'}) flips the type flag and does not
    create a PlaneZone, so the canvas has nothing to click. Watched.

    Inner1/Inner2 stay SIGNAL. Draw the planes in the GUI:
    Place → Copper Region → Rectangle, covering the board, Inner1/GND
    then Inner2/3V3, then Shift+B.
    """
    existing = execute(
        "const p = await eda.pcb_PrimitivePour.getAll(); "
        "if (p && p.length) { "
        "await eda.pcb_PrimitivePour.delete(p.map(x => x.primitiveId)); "
        "return p.length; } return 0;"
    )
    if existing:
        print(f"  deleted {existing} API pour outline(s)")
    js = """
const t1 = await eda.pcb_Layer.modifyLayer(15, {type: 'SIGNAL'});
const t2 = await eda.pcb_Layer.modifyLayer(16, {type: 'SIGNAL'});
const layers = (await eda.pcb_Layer.getAllLayers())
  .filter(l => [15,16].includes(l.id))
  .map(l => ({id:l.id, name:l.name, type:l.type}));
return {t1, t2, layers};
"""
    got = execute(js)
    print(f"  inner layers {got}")
    print("  draw in GUI: Place → Copper Region → Rectangle")
    print("  Inner1 net GND, Inner2 net 3V3, then Shift+B")


def cluster():
    """U3 next to USB, crystal on XIN/XOUT, flash on QSPI, ESD on the
    connector, decoupling around the QFN. SK/LED/USBC do not move.
    """
    open_pcb()
    comps = {c["des"]: c for c in pcb_components()}
    w = params.mm_to_mil(params.BOARD_W)
    d = params.mm_to_mil(params.BOARD_D)
    occupied = [c["bbox"] for des, c in comps.items() if keep(des) or des == "USBC1"]

    led5 = comps["LED5"]["bbox"]
    led6 = comps["LED6"]["bbox"]
    u3 = comps["U3"]
    u3w, u3h = bbox_size(u3["bbox"])
    # LED5-LED6 X-gap, origin so the QFN sits in that column.
    gap_left = led5["maxX"] + MARGIN_MIL
    gap_right = led6["minX"] - MARGIN_MIL
    rel_min_x = u3["bbox"]["minX"] - u3["x"]
    rel_max_x = u3["bbox"]["maxX"] - u3["x"]
    origin_x = gap_left - rel_min_x
    if origin_x + rel_max_x > gap_right:
        origin_x = gap_right - rel_max_x
    rel_min_y = u3["bbox"]["minY"] - u3["y"]
    origin_y = MARGIN_MIL - rel_min_y
    got = search_move(u3["id"], origin_x, origin_y, 0, occupied, w, d)
    if not got:
        raise AssertionError("U3 did not fit in LED5-LED6 gap")
    occupied.append(got["bbox"])
    print(f"  U3    @({got['x']:.0f},{got['y']:.0f})")
    u3_bb = got["bbox"]
    alley_y = (u3_bb["maxY"] + min(c["bbox"]["minY"] for c in comps.values() if (c["des"] or "").startswith("SK"))) / 2

    def park_group(names, x0, y0, rot=0, span=350, step=20):
        for des in names:
            p = comps[des]
            got = search_move(p["id"], x0, y0, rot, occupied, w, d, span=span, step=step)
            if not got:
                raise AssertionError(f"{des} did not fit near ({x0:.0f},{y0:.0f})")
            occupied.append(got["bbox"])
            print(f"  {des:5} @({got['x']:.0f},{got['y']:.0f}) rot{rot}")
            x0 = got["bbox"]["maxX"] + MARGIN_MIL

    # Alley between LED tops and socket bottoms: XIN/XOUT face +y.
    park_group(["U2", "C1", "C2", "R2"], u3_bb["minX"] + 80, alley_y, span=120, step=10)

    # Flash in LED3-LED4 gap (full height). SOP-8 is too tall for the alley.
    led2 = comps["LED2"]["bbox"]
    led3 = comps["LED3"]["bbox"]
    led4 = comps["LED4"]["bbox"]
    park_group(["U1"], (led3["maxX"] + led4["minX"]) / 2, origin_y, span=200)

    usb = comps["USBC1"]["bbox"]
    led6 = comps["LED6"]["bbox"]
    # Under LED6 / left of USB: ESD, series, CC, LDO.
    park_group(["D1"], led6["minX"] + 120, MARGIN_MIL + 66, span=300, step=15)
    park_group(["R3", "R4"], led6["minX"] + 40, MARGIN_MIL + 30, span=300, step=15)
    park_group(["R5", "R6"], usb["minX"] - 100, usb["minY"] + 40, span=300, step=15)
    park_group(["U4", "C15", "C16"], led6["minX"] + 40, MARGIN_MIL + 30, span=350, step=15)

    led2 = comps["LED2"]["bbox"]
    park_group(["SW1", "R1"], (led2["maxX"] + led3["minX"]) / 2, origin_y, span=250)

    park_group(["C3", "C4", "C5"], u3_bb["minX"], MARGIN_MIL + 25, span=200)
    park_group([f"C{i}" for i in range(6, 15)], u3_bb["minX"] + 80, MARGIN_MIL + 25, span=400)

    after = pcb_components()
    assert_layout(after)
    execute(
        "try { await eda.pcb_Document.startCalculatingRatline(); } "
        "catch (e) {} return true;"
    )


def main():
    cluster()
    enable_4_layer()
    pour_planes()
    save()


if __name__ == "__main__":
    main()
