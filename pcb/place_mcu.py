# pcb/place_mcu.py
"""Place the schematic's RP2040 block onto the existing key-field PCB.

Does not call openProject (that discards unsaved schematic edits). Does
not touch SK1-SK6 or LED1-LED6. Unique IDs are copied from the schematic
so airwires can join. Coordinates are 1 mil.

The board is 21.59 mm deep and the sockets already occupy y 12.0-19.2 mm,
the pixels y 4.2-7.8 mm. The QFN-56 and the USB-C footprint only fit in
the X-gaps between pixels, below the sockets. USB-C is rotated 90 so the
tongue points +x (out the right tab) and shifted down so it misses SK6.
"""
import json
import sys

import params
from bridge import execute

BOTTOM = 2  # EPCB_LayerId.BOTTOM
PCB_PAGE = 3  # EDMT_EditorDocumentType.PCB
MARGIN_MIL = 20
PARK_Y = -800

# Schematic supplierId -> library device uuid. Cloned uuids from
# getState_Component() cannot be passed to pcb create() -- watched:
# TypeError. The 0402s whose LCSC is a manufacturer PN fall back to the
# same-package Basic Part in params (15 pF / 100 nF / 1 µF).
DEV_BY_SID = {
    "C2961140": params.DEV_RP2040,
    "C179171": params.DEV_FLASH,
    "C9900091606": params.DEV_CRYSTAL,
    "C5446": params.DEV_LDO,
    "C165948": params.DEV_USB_C,
    "C323793": params.DEV_ESD,
    "C318884": params.DEV_BOOT_SW,
    "C25100": params.DEV_R_27R,
    "C25905": params.DEV_R_5K1,
    "C11702": params.DEV_R_1K,
    "C52923": params.DEV_C_1U,
    "C1525": params.DEV_C_100N,
    "C1548": params.DEV_C_15P,
    "0402CG150J500NT.1": params.DEV_C_15P,
    "CL05B104KO5NNNC.1": params.DEV_C_100N,
    "CL05A105KA5NQNC.1": params.DEV_C_1U,
}

KEEP_PREFIXES = ("SK", "LED")


def open_pcb():
    js = (
        "const proj = await eda.dmt_Project.getCurrentProjectInfo(); "
        "const name = (proj && (proj.friendlyName || proj.name)) || ''; "
        "const pcbs = await eda.dmt_Pcb.getAllPcbsInfo(); "
        "if (!pcbs || !pcbs.length) return {error: 'no PCB'}; "
        "let doc = await eda.dmt_SelectControl.getCurrentDocumentInfo(); "
        "if (!(doc && doc.documentType === 3 && doc.uuid === pcbs[0].uuid)) { "
        "await eda.dmt_EditorControl.openDocument(pcbs[0].uuid); "
        "doc = await eda.dmt_SelectControl.getCurrentDocumentInfo(); "
        "} "
        "return {opened: name, pcb: pcbs[0].name, documentType: doc.documentType};"
    )
    got = execute(js)
    if got.get("error"):
        raise SystemExit(got["error"])
    if got["documentType"] != PCB_PAGE:
        raise SystemExit(f"active document is type {got['documentType']}, not PCB")
    print(f"opened {got['opened']} / {got['pcb']}")


def open_schematic():
    js = (
        "const pages = await eda.dmt_Schematic.getAllSchematicPagesInfo(); "
        "if (!pages || !pages.length) return {error: 'no schematic'}; "
        "await eda.dmt_EditorControl.openDocument(pages[0].uuid); "
        "return {page: pages[0].name};"
    )
    got = execute(js)
    if got.get("error"):
        raise SystemExit(got["error"])


def schematic_parts():
    open_schematic()
    rows = execute(
        """
const comps = await eda.sch_PrimitiveComponent.getAll();
const out = [];
for (const c of comps || []) {
  if (c.getState_ComponentType() !== 'part') continue;
  out.push({
    des: c.getState_Designator(),
    uid: c.getState_UniqueId(),
    sid: c.getState_SupplierId && c.getState_SupplierId()
  });
}
return out;
""",
        timeout=60,
    )
    if len(rows) != 29:
        raise AssertionError(f"expected 29 schematic parts, got {len(rows)}")
    return rows


def pcb_components():
    return execute(
        """
const all = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of all || []) {
  const id = c.getState_PrimitiveId();
  const bbox = await eda.pcb_Primitive.getPrimitivesBBox([id]);
  out.push({
    id, des: c.getState_Designator(),
    x: c.getState_X(), y: c.getState_Y(),
    layer: c.getState_Layer(), rot: c.getState_Rotation(),
    uid: c.getState_UniqueId(), bbox
  });
}
return out;
""",
        timeout=90,
    )


def keep(des):
    return any((des or "").startswith(p) for p in KEEP_PREFIXES)


def delete_mcu_parts(comps):
    ids = [c["id"] for c in comps if not keep(c.get("des") or "")]
    if not ids:
        return
    ok = execute(
        "return await eda.pcb_PrimitiveComponent.delete(" + json.dumps(ids) + ");"
    )
    print(f"  deleted {len(ids)} existing MCU/probe parts {ok}")


def place_parked(parts):
    """One footprint per schematic part, parked off the board, tagged
    with the schematic designator and uniqueId."""
    placed = []
    for i, p in enumerate(parts):
        sid = p["sid"] or ""
        uuid = DEV_BY_SID.get(sid)
        if not uuid:
            raise AssertionError(f"no device uuid for {p['des']} sid={sid!r}")
        x = 400 + i * 350
        js = (
            f"const dev = {{libraryUuid: {json.dumps(params.LIB_UUID)}, "
            f"uuid: {json.dumps(uuid)}}}; "
            f"const c = await eda.pcb_PrimitiveComponent.create("
            f"dev, {BOTTOM}, {x}, {PARK_Y}, 0, false); "
            "if (!c) throw new Error('create returned nothing for ' + "
            + json.dumps(p["des"])
            + "); "
            "const id = c.primitiveId; "
            "const back = await eda.pcb_PrimitiveComponent.modify(id, {"
            f"designator: {json.dumps(p['des'])}, "
            f"uniqueId: {json.dumps(p['uid'])}"
            "}); "
            "if (!back) throw new Error('modify returned nothing for ' + "
            + json.dumps(p["des"])
            + "); "
            "const bbox = await eda.pcb_Primitive.getPrimitivesBBox([id]); "
            "return {id, des: back.getState_Designator(), "
            "uid: back.getState_UniqueId(), "
            "x: back.getState_X(), y: back.getState_Y(), bbox};"
        )
        got = execute(js, timeout=30)
        if got["des"] != p["des"]:
            raise AssertionError(f"designator {p['des']!r} read back {got['des']!r}")
        if got["uid"] != p["uid"]:
            raise AssertionError(f"uniqueId {p['uid']!r} read back {got['uid']!r}")
        placed.append(got)
        print(f"  parked {got['des']:6} uid={got['uid']}")
    return placed


def bbox_size(b):
    return b["maxX"] - b["minX"], b["maxY"] - b["minY"]


def overlap(a, b, margin=0):
    return not (
        a["maxX"] + margin <= b["minX"]
        or b["maxX"] + margin <= a["minX"]
        or a["maxY"] + margin <= b["minY"]
        or b["maxY"] + margin <= a["minY"]
    )


def move(pid, x, y, rot=0):
    js = (
        f"const back = await eda.pcb_PrimitiveComponent.modify("
        f"{json.dumps(pid)}, {{x: {x}, y: {y}, rotation: {rot}, layer: {BOTTOM}}}); "
        "if (!back) throw new Error('move failed'); "
        "const bbox = await eda.pcb_Primitive.getPrimitivesBBox([back.getState_PrimitiveId()]); "
        "return {x: back.getState_X(), y: back.getState_Y(), rot: back.getState_Rotation(), "
        "layer: back.getState_Layer(), bbox};"
    )
    return execute(js)


def arrange(parked, field):
    """Parked parts have rot-0 bboxes. Field is SK+LED occupancy."""
    by = {p["des"]: p for p in parked}

    def size_of(des):
        return bbox_size(by[des]["bbox"])

    # USB-C: rot 90, tongue +x, below SK6.
    usb = move(by["USBC1"]["id"], 0, PARK_Y - 400, 90)
    uw, uh = bbox_size(usb["bbox"])
    # Re-read origin-relative extents at rot 90 from this parking spot.
    ox, oy = usb["x"], usb["y"]
    rel = {
        "minX": usb["bbox"]["minX"] - ox,
        "maxX": usb["bbox"]["maxX"] - ox,
        "minY": usb["bbox"]["minY"] - oy,
        "maxY": usb["bbox"]["maxY"] - oy,
    }
    sk6 = next(c for c in field if c["des"] == "SK6")
    led6 = next(c for c in field if c["des"] == "LED6")
    board_w = params.mm_to_mil(params.BOARD_W)
    board_d = params.mm_to_mil(params.BOARD_D)
    # Tongue is +x (rel.maxX). Sit the tongue just past the right edge,
    # keep the body below SK6 and to the right of LED6.
    want_x = board_w - rel["maxX"] + params.mm_to_mil(0.15)
    want_y = sk6["bbox"]["minY"] - MARGIN_MIL - rel["maxY"]
    if want_y + rel["minY"] < MARGIN_MIL:
        want_y = MARGIN_MIL - rel["minY"]
    usb = move(by["USBC1"]["id"], want_x, want_y, 90)
    print(
        f"  USBC1 rot90 @({usb['x']:.0f},{usb['y']:.0f}) "
        f"bbox {uw/params.MIL_PER_MM:.2f}x{uh/params.MIL_PER_MM:.2f} mm"
    )
    if overlap(usb["bbox"], sk6["bbox"]) or overlap(usb["bbox"], led6["bbox"]):
        raise AssertionError(
            f"USBC1 overlaps SK6 or LED6: usb={usb['bbox']} "
            f"sk6={sk6['bbox']} led6={led6['bbox']}"
        )

    occupied = [c["bbox"] for c in field] + [usb["bbox"]]

    # Pixel X-gaps, y from board front up to the sockets.
    leds = sorted((c for c in field if c["des"].startswith("LED")), key=lambda c: c["x"])
    sks = sorted((c for c in field if c["des"].startswith("SK")), key=lambda c: c["x"])
    socket_top = min(c["bbox"]["minY"] for c in sks)
    gaps = []
    prev = MARGIN_MIL
    for led in leds:
        left, right = prev, led["bbox"]["minX"] - MARGIN_MIL
        if right - left > 40:
            gaps.append((left, right, MARGIN_MIL, socket_top - MARGIN_MIL))
        prev = led["bbox"]["maxX"] + MARGIN_MIL
    if board_w - prev > 40:
        gaps.append((prev, board_w - MARGIN_MIL, MARGIN_MIL, socket_top - MARGIN_MIL))

    def place_in_gap(des, rot=0):
        w, h = size_of(des)
        if rot in (90, 270):
            w, h = h, w
        # rot-0 parked bbox origin offset
        b0 = by[des]["bbox"]
        # After a rotation we must place then measure; for rot 0 we can
        # compute origin from the parked bbox.
        for i, (x0, x1, y0, y1) in enumerate(gaps):
            if (x1 - x0) < w + 1 or (y1 - y0) < h + 1:
                continue
            if rot == 0:
                origin_x = x0 - (b0["minX"] - by[des]["x"])
                origin_y = y0 - (b0["minY"] - by[des]["y"])
                # keep max inside the gap
                max_x = origin_x + (b0["maxX"] - by[des]["x"])
                max_y = origin_y + (b0["maxY"] - by[des]["y"])
                if max_x > x1:
                    origin_x -= max_x - x1
                if max_y > y1:
                    origin_y -= max_y - y1
                got = move(by[des]["id"], origin_x, origin_y, 0)
            else:
                # park at rot, then shift into the gap
                trial = move(by[des]["id"], 0, PARK_Y - 600, rot)
                ox, oy = trial["x"], trial["y"]
                relx0 = trial["bbox"]["minX"] - ox
                rely0 = trial["bbox"]["minY"] - oy
                relx1 = trial["bbox"]["maxX"] - ox
                rely1 = trial["bbox"]["maxY"] - oy
                origin_x = x0 - relx0
                origin_y = y0 - rely0
                if origin_x + relx1 > x1:
                    origin_x = x1 - relx1
                if origin_y + rely1 > y1:
                    origin_y = y1 - rely1
                got = move(by[des]["id"], origin_x, origin_y, rot)
            for occ in occupied:
                if overlap(got["bbox"], occ, margin=0):
                    break
            else:
                occupied.append(got["bbox"])
                # consume the used left of the gap so the next part
                # sits to the right rather than stacking
                gaps[i] = (got["bbox"]["maxX"] + MARGIN_MIL, x1, y0, y1)
                print(
                    f"  {des:6} rot{rot} @({got['x']:.0f},{got['y']:.0f}) "
                    f"in gap x {x0:.0f}-{x1:.0f}"
                )
                return got
        raise AssertionError(f"no gap fits {des} {w:.0f}x{h:.0f} mil")

    # Largest first, USB already placed.
    order = ["U3", "U1", "SW1", "D1", "U4", "U2"]
    for des in order:
        place_in_gap(des, 0)

    # Passives: a row along the front of the board (y below the pixels).
    # The pixel-gap packer consumed leftover X and left C6+ overlapping USB.
    done = {"USBC1", "U3", "U1", "SW1", "D1", "U4", "U2"}
    rest = [p["des"] for p in parked if p["des"] not in done]
    near = (
        ["C1", "C2", "R2", "R1"]
        + [f"C{i}" for i in range(3, 15)]
        + ["C15", "C16", "R3", "R4", "R5", "R6"]
    )
    rest_sorted = [d for d in near if d in rest] + [d for d in rest if d not in near]
    front_y0 = MARGIN_MIL
    front_y1 = min(c["bbox"]["minY"] for c in leds) - MARGIN_MIL
    cursor = MARGIN_MIL
    board_w = params.mm_to_mil(params.BOARD_W)
    for des in rest_sorted:
        w, h = size_of(des)
        if h > front_y1 - front_y0:
            raise AssertionError(
                f"{des} {h:.0f} mil tall, front strip only {front_y1-front_y0:.0f}"
            )
        b0 = by[des]["bbox"]
        placed = False
        x = cursor
        while x + w < board_w - MARGIN_MIL:
            origin_x = x - (b0["minX"] - by[des]["x"])
            origin_y = front_y0 - (b0["minY"] - by[des]["y"])
            got = move(by[des]["id"], origin_x, origin_y, 0)
            hit = any(overlap(got["bbox"], occ) for occ in occupied)
            if not hit and got["bbox"]["maxY"] <= front_y1 + 0.05:
                occupied.append(got["bbox"])
                cursor = got["bbox"]["maxX"] + MARGIN_MIL
                print(f"  {des:6} front @({got['x']:.0f},{got['y']:.0f})")
                placed = True
                break
            x += max(20, int(w / 2))
        if not placed:
            raise AssertionError(f"no front-row slot for {des}")

    return occupied


def assert_layout(comps):
    mcu = [c for c in comps if not keep(c.get("des") or "")]
    field = [c for c in comps if keep(c.get("des") or "")]
    if len(mcu) != 29:
        raise AssertionError(f"MCU parts {len(mcu)}, wanted 29")
    if len(field) != 12:
        raise AssertionError(f"field parts {len(field)}, wanted 12")
    bad = []
    for a in mcu:
        if a["layer"] != BOTTOM:
            bad.append(f"{a['des']} on layer {a['layer']}")
        for b in field:
            if overlap(a["bbox"], b["bbox"]):
                bad.append(f"{a['des']}/{b['des']}")
        for b in mcu:
            if a["des"] >= b["des"]:
                continue
            if overlap(a["bbox"], b["bbox"]):
                bad.append(f"{a['des']}/{b['des']}")
    if bad:
        raise AssertionError("layout: " + ", ".join(bad))
    print(f"  [ok ] 29 MCU parts on BOTTOM, no overlap with 12 field parts or each other")


def schematic_pad_nets():
    """(designator, padNumber) -> net, from schematic wire coincidence.

    GUI Update PCB / importChanges / setNetlist all left net count at 0
    with uniqueIds already matching. Pad.modify({net}) is the path that
    actually assigns airwires.
    """
    from schematic_tidy import open_schematic as open_sch
    from schematic_tidy import pin_on_any_wire, snapshot

    open_sch()
    data = snapshot()
    out = {}
    multi = []
    for p in data["parts"]:
        if p["type"] != "part":
            continue
        pads = {}
        for pin in p["pins"]:
            hits = pin_on_any_wire(pin, data["wires"])
            named = [h for h in hits if h]
            if not named:
                continue
            if len(set(named)) > 1:
                multi.append(f"{p['des']}.{pin['num']}={hits}")
                continue
            num = pin["num"] or pin["n"]
            pads[str(num)] = named[0]
        out[p["des"]] = pads
    if multi:
        raise AssertionError("schematic pin on two nets: " + ", ".join(multi))
    n = sum(len(v) for v in out.values())
    names = sorted({net for pads in out.values() for net in pads.values()})
    print(f"  schematic: {n} pins on {len(names)} nets")
    return out


def field_pad_nets():
    """Sockets and pixels are PCB-only; their nets are the schematic's
    KEY0-5 / PIXEL ports plus the chain hops and the two rails.

    SK pad 1 is the -x pad (switch pin A), pad 2 the +x pad (pin B).
    Either can be the GPIO side of a switch; pad 1 takes KEYn, pad 2 GND.
    Pixel pad numbers follow params.PIXEL_PAD_SIGNALS.
    """
    out = {}
    for i in range(6):
        out[f"SK{i + 1}"] = {"1": f"KEY{i}", "2": "GND"}
        din = "PIXEL" if i == 0 else f"PIXEL{i}"
        pads = {
            "1": "3V3",
            "3": "GND",
            "4": din,
        }
        if i < 5:
            pads["2"] = f"PIXEL{i + 1}"
        out[f"LED{i + 1}"] = pads
    return out


def assign_pad_nets(mapping):
    payload = json.dumps(mapping)
    js = (
        "const M = " + payload + "; "
        "const all = await eda.pcb_PrimitiveComponent.getAll(); "
        "const out = {set: 0, miss: [], read: {}}; "
        "for (const c of all || []) { "
        "const des = c.getState_Designator(); "
        "const pads = M[des]; "
        "if (!pads) continue; "
        "const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId("
        "c.getState_PrimitiveId()); "
        "const seen = {}; "
        "for (const p of pins || []) { "
        "const num = String(p.getState_PadNumber()); "
        "const net = pads[num]; "
        "if (!net) continue; "
        "const pid = p.getState_PrimitiveId(); "
        "const got = await eda.pcb_PrimitivePad.modify(pid, {net: net}); "
        "if (!got) throw new Error('pad modify failed ' + des + '.' + num); "
        "seen[num] = true; "
        "out.set++; "
        "} "
        "for (const num of Object.keys(pads)) { "
        "if (!seen[num]) out.miss.push(des + '.' + num); "
        "} "
        "} "
        "const names = await eda.pcb_Net.getAllNetName(); "
        "out.names = names || []; "
        "const probes = [['U3','5'], ['U3','47'], ['USBC1','A6'], "
        "['SK1','1'], ['LED1','4'], ['C1','1']]; "
        "for (const c of all || []) { "
        "const des = c.getState_Designator(); "
        "for (const [wdes, wnum] of probes) { "
        "if (des !== wdes) continue; "
        "const pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId("
        "c.getState_PrimitiveId()); "
        "for (const p of pins || []) { "
        "if (String(p.getState_PadNumber()) === wnum) { "
        "out.read[wdes + '.' + wnum] = p.getState_Net() || ''; "
        "} "
        "} "
        "} "
        "} "
        "try { await eda.pcb_Document.startCalculatingRatline(); } catch (e) {} "
        "return out;"
    )
    return execute(js, timeout=180)


def assign_nets():
    mapping = schematic_pad_nets()
    n_mcu = sum(len(v) for v in mapping.values())
    if n_mcu < 100:
        raise AssertionError(f"only {n_mcu} schematic pins have nets, expected ~113")
    mapping.update(field_pad_nets())
    n_all = sum(len(v) for v in mapping.values())
    open_pcb()
    got = assign_pad_nets(mapping)
    if got.get("miss"):
        raise AssertionError("pads missing on PCB: " + ", ".join(got["miss"]))
    if got["set"] != n_all:
        raise AssertionError(f"set {got['set']} pads, wanted {n_all}")
    names = got.get("names") or []
    print(f"  set {got['set']} pads, {len(names)} net names")
    expect = {
        "U3.5": "KEY0",
        "U3.47": "USB_DP",
        "USBC1.A6": "USB_DP_RAW",
        "SK1.1": "KEY0",
        "LED1.4": "PIXEL",
    }
    bad = []
    for k, want in expect.items():
        got_net = (got.get("read") or {}).get(k)
        if got_net != want:
            bad.append(f"{k}={got_net!r} wanted {want!r}")
    if bad:
        raise AssertionError("probe nets: " + "; ".join(bad))
    for k, want in expect.items():
        print(f"  [ok ] {k} = {want}")
    saved = execute("return await eda.pcb_Document.save();")
    if saved is not True:
        raise AssertionError(f"pcb_Document.save() returned {saved!r}")
    print("saved")


def place():
    parts = schematic_parts()
    open_pcb()
    comps = pcb_components()
    field = [c for c in comps if keep(c.get("des") or "")]
    if len(field) != 12:
        raise AssertionError(f"expected 12 SK+LED, got {len(field)} {[c['des'] for c in field]}")
    delete_mcu_parts(comps)
    parked = place_parked(parts)
    arrange(parked, field)
    after = pcb_components()
    assert_layout(after)
    saved = execute("return await eda.pcb_Document.save();")
    if saved is not True:
        raise AssertionError(f"pcb_Document.save() returned {saved!r}")
    print("saved")
    execute("try { await eda.pcb_Document.startCalculatingRatline(); } catch (e) {} return true;")
    print("ratlines requested")


def move_field():
    """SK/LED onto the case field, BOTTOM. Convert dumps them on TOP at
    schematic-relative coords (negative Y, off the outline). Move, do not
    recreate -- that is what strips EasyEDA's own nets and flying wires.
    """
    comps = pcb_components()
    by = {c["des"]: c for c in comps}
    dx = params.mm_to_mil(params.SOCKET_OFFSET_MM[0])
    dy = params.mm_to_mil(params.SOCKET_OFFSET_MM[1])
    pdx = params.mm_to_mil(params.PIXEL_OFFSET_MM[0])
    pdy = params.mm_to_mil(params.PIXEL_OFFSET_MM[1])
    sy = params.mm_to_mil(params.SWITCH_Y)
    for i, (cx, _) in enumerate(params.switch_centres_mm(), 1):
        sk = by.get(f"SK{i}")
        led = by.get(f"LED{i}")
        if not sk or not led:
            raise AssertionError(f"missing SK{i} or LED{i} after convert")
        x = params.mm_to_mil(cx) + dx
        y = sy + dy
        got = move(sk["id"], x, y, 0)
        print(f"  SK{i}  BOTTOM @({got['x']:.0f},{got['y']:.0f})")
        lx = params.mm_to_mil(cx) + pdx
        ly = sy + pdy
        got = move(led["id"], lx, ly, 180)
        print(f"  LED{i} BOTTOM rot180 @({got['x']:.0f},{got['y']:.0f})")


def park_existing(mcu):
    """Park convert-placed MCU parts off-board at rot 0, keep their ids."""
    parked = []
    for i, p in enumerate(mcu):
        got = move(p["id"], 400 + i * 350, PARK_Y, 0)
        parked.append(
            {
                "id": p["id"],
                "des": p["des"],
                "x": got["x"],
                "y": got["y"],
                "bbox": got["bbox"],
            }
        )
        print(f"  parked {p['des']:6}")
    return parked


def relayout():
    """Move the convert's 41 parts onto the board. Do not delete or
    recreate -- Import Changes from Schematic is what built the nets and
    the flying wires; pad.modify / create() is what used to throw them
    away.
    """
    open_pcb()
    move_field()
    comps = pcb_components()
    field = [c for c in comps if keep(c.get("des") or "")]
    mcu = [c for c in comps if not keep(c.get("des") or "")]
    if len(field) != 12:
        raise AssertionError(f"expected 12 SK+LED, got {len(field)}")
    if len(mcu) != 29:
        raise AssertionError(f"expected 29 MCU parts, got {len(mcu)}")
    parked = park_existing(mcu)
    arrange(parked, field)
    after = pcb_components()
    assert_layout(after)
    saved = execute("return await eda.pcb_Document.save();")
    if saved is not True:
        raise AssertionError(f"pcb_Document.save() returned {saved!r}")
    print("saved")
    execute(
        "try { await eda.pcb_Document.startCalculatingRatline(); } "
        "catch (e) {} return true;"
    )
    print("ratlines requested")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Place or net the MCU block.")
    parser.add_argument(
        "--nets",
        action="store_true",
        help="assign pad nets from the schematic; do not move or recreate parts",
    )
    parser.add_argument(
        "--relayout",
        action="store_true",
        help="move convert-placed parts onto the field; do not recreate",
    )
    args = parser.parse_args()
    if args.nets:
        assign_nets()
        return
    if args.relayout:
        relayout()
        return
    place()


if __name__ == "__main__":
    main()
