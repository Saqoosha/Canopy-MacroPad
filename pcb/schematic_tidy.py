# pcb/schematic_tidy.py
"""Annotate and space the schematic so a human can read it.

Run with: python3 pcb/schematic_tidy.py
         python3 pcb/schematic_tidy.py --report   # also print USB D- / empty nets
         python3 pcb/schematic_tidy.py --layout   # move parts; do not use yet

Default is annotate-only: number the `?` designators, move nothing.
`--layout` is how the previous pass wiped the page on timeout.

Does not redesign the circuit and does not change a component value or a
net name. Coordinates here are 0.01 inch -- the schematic unit, never the
PCB's 1-mil unit (see pcb/README.md).

The async primitive pattern is the one the class reference documents:
get the primitive, .toAsync(), setState_*(), await .done(). Enums are
absent from the bridge execution context, so documentType 1 is the
literal for EDMT_EditorDocumentType.SCHEMATIC_PAGE, and the PDF export
type is the literal "PDF" for ESCH_ExportDocumentFileType.PDF.
"""
import base64
import json
import os
import re
import sys

from bridge import execute

PROJECT_NAME = os.environ.get("MPAD_EDA_PROJECT", "Canopy MacroPad")
SCHEMATIC_PAGE = 1  # EDMT_EditorDocumentType.SCHEMATIC_PAGE
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
EXPORT_PDF = os.path.join(OUT_DIR, "schematic-page.pdf")

# Destination windows from the brief. A part's origin (setState_X/Y) lands
# inside its group's window. The RP2040 symbol is taller than its window,
# so the bounding box is allowed to spill; the origin is not.
REGIONS = {
    "rp2040": (300, 620, 180, 460),
    "flash": (660, 880, 180, 340),
    "crystal": (660, 880, 370, 480),
    "ldo": (90, 280, 500, 700),
    "usb": (90, 360, 180, 460),
    "boot": (380, 560, 520, 640),
    "ports": (660, 1010, 520, 780),
    "keys": (50, 1100, 960, 1200),
}

# Group by what the part *is*, not where it currently sits. LCSC numbers
# are the identity schematic.py already matches on (the cloned device uuid
# is not the uuid that was passed to create()).
GROUP_BY_LCSC = {
    "C2961140": "rp2040",       # RP2040
    "C179171": "flash",         # W25Q64JVSSIQ, SOIC-8-208mil
    "C9900091606": "crystal",   # ABM8-272-T3
    "C5446": "ldo",             # XC6206
    "C323793": "usb",           # USBLC6-2SC6
    "C165948": "usb",           # TYPE-C-31-M-12
    "C318884": "boot",          # BOOT switch
    "C25100": "usb",            # 27 Ω USB series
    "C25905": "usb",            # 5.1 kΩ CC pull-downs
    "C1548": "crystal",         # 15 pF load caps
    "C1525": "rp2040",          # 100 nF decoupling
    "C9900010116": "keys",      # Kailh CPG135001S30 socket
    "C5149201": "keys",         # SK6812MINI-E
}

# USBLC6-2SC6 pin function by number, from ST's datasheet (same table
# schematic.py carries). The placed symbol returns pins named "1".."6".
USBLC6_PINOUT = {
    "1": "IO1",
    "2": "GND",
    "3": "IO2",
    "4": "IO2",
    "5": "VBUS",
    "6": "IO1",
}


def open_schematic():
    """Leave the project's schematic page active.

    Does not call openProject -- that discards unsaved edits. The project
    is already open; this only switches to the schematic page if the
    active document is something else, then asserts documentType is 1.
    """
    js = (
        "const proj = await eda.dmt_Project.getCurrentProjectInfo(); "
        "const name = (proj && (proj.friendlyName || proj.name)) || ''; "
        "if (name !== " + json.dumps(PROJECT_NAME) + ") { "
        "return {error: 'current project is ' + JSON.stringify(name)}; "
        "} "
        "const pages = await eda.dmt_Schematic.getAllSchematicPagesInfo(); "
        "if (!pages || !pages.length) return {error: 'project has no schematic page'}; "
        "let doc = await eda.dmt_SelectControl.getCurrentDocumentInfo(); "
        "if (!(doc && doc.documentType === 1 && doc.uuid === pages[0].uuid)) { "
        "await eda.dmt_EditorControl.openDocument(pages[0].uuid); "
        "doc = await eda.dmt_SelectControl.getCurrentDocumentInfo(); "
        "} "
        "return {opened: name, page: pages[0].name, documentType: doc.documentType, uuid: doc.uuid};"
    )
    got = execute(js)
    if got.get("error"):
        raise SystemExit(f"cannot open the schematic: {got['error']}")
    if got["documentType"] != SCHEMATIC_PAGE:
        raise SystemExit(
            f"active document is type {got['documentType']}, not a schematic page"
        )
    print(f"opened {got['opened']} / {got['page']}")


def save_schematic():
    """Persist the open schematic. `sch_Document.save()` returns false on
    upload failure, which is indistinguishable from a no-op, so treat
    false as an error rather than 'probably fine'.
    """
    got = execute("return await eda.sch_Document.save();")
    if got is not True:
        raise AssertionError(f"sch_Document.save() returned {got!r}")
    print("saved")


def snapshot():
    """Every non-sheet component, every wire, and each part's pins."""
    js = r"""
const comps = await eda.sch_PrimitiveComponent.getAll();
const parts = [];
for (const c of comps || []) {
  const type = c.getState_ComponentType();
  if (type === 'sheet') continue;
  const id = c.getState_PrimitiveId();
  const other = c.getState_OtherProperty() || {};
  const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(id);
  const attrs = await eda.sch_PrimitiveAttribute.getAll(id);
  const vis = [];
  for (const a of attrs || []) {
    if (a.getState_ValueVisible() === true) {
      vis.push({
        k: a.getState_Key(),
        v: a.getState_Value(),
        x: a.getState_X(),
        y: a.getState_Y()
      });
    }
  }
  let mfr = null;
  for (const a of attrs || []) {
    if (a.getState_Key() === 'Manufacturer Part') mfr = a.getState_Value();
  }
  const bbox = await eda.sch_Primitive.getPrimitivesBBox([id]);
  parts.push({
    id: id,
    type: type,
    des: c.getState_Designator() || '',
    name: c.getState_Name() || '',
    x: c.getState_X(),
    y: c.getState_Y(),
    net: c.getState_Net() || '',
    sid: c.getState_SupplierId() || '',
    val: other.Value || '',
    mfr: mfr || '',
    bbox: bbox || null,
    vis: vis,
    pins: (pins || []).map(p => ({
      n: p.getState_PinName() || '',
      num: p.getState_PinNumber() || '',
      x: p.getState_X(),
      y: p.getState_Y()
    }))
  });
}
const wires = await eda.sch_PrimitiveWire.getAll();
const wout = [];
for (const w of wires || []) {
  wout.push({
    id: w.getState_PrimitiveId(),
    net: w.getState_Net(),
    line: w.getState_Line()
  });
}
return {parts: parts, wires: wout};
"""
    return execute(js, timeout=90)


def census_from(wires):
    """Count of wires per net name, empty string included."""
    counts = {}
    for w in wires:
        net = w.get("net")
        if net is None:
            net = ""
        counts[net] = counts.get(net, 0) + 1
    return counts


def print_census(label, counts):
    print(f"net census {label}: {len(counts)} names, {sum(counts.values())} wires")
    for net in sorted(counts, key=lambda n: (n == "", n)):
        shown = net if net != "" else "(empty)"
        print(f"  {shown}: {counts[net]}")


def prefix_of(des):
    m = re.match(r"^([A-Za-z]+)", des or "")
    if not m:
        raise AssertionError(f"designator {des!r} has no letter prefix")
    return m.group(1)


def classify(parts):
    """Assign each part to a region group by electrical identity."""
    chips = {}
    for p in parts:
        if p["sid"] == "C2961140":
            chips["rp2040"] = p
        elif p["sid"] == "C5446":
            chips["ldo"] = p
        elif p["sid"] == "C9900091606":
            chips["crystal"] = p
        elif p["sid"] == "C318884":
            chips["boot"] = p

    def dist2(a, b):
        return (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2

    groups = {k: [] for k in REGIONS}
    for p in parts:
        if p["type"] == "netport":
            groups["ports"].append(p)
            continue
        g = GROUP_BY_LCSC.get(p["sid"])
        if g is None and p["sid"] == "C11702":
            # Two 1 kΩ: crystal XOUT damping vs BOOT series. Same LCSC,
            # different nets -- pick by which chip they sit with.
            d_xtal = dist2(p, chips["crystal"]) if "crystal" in chips else 1e18
            d_boot = dist2(p, chips["boot"]) if "boot" in chips else 1e18
            g = "crystal" if d_xtal <= d_boot else "boot"
        elif g is None and p["sid"] == "C52923":
            # Four 1 µF: VREG_IN/VREG_VOUT on the RP2040, Vin/Vout on the
            # LDO. Same LCSC, different rails.
            d_u1 = dist2(p, chips["rp2040"]) if "rp2040" in chips else 1e18
            d_ldo = dist2(p, chips["ldo"]) if "ldo" in chips else 1e18
            g = "rp2040" if d_u1 <= d_ldo else "ldo"
        if g is None:
            raise AssertionError(
                f"no group for {p['id']} sid={p['sid']!r} des={p['des']!r}"
            )
        groups[g].append(p)
    return groups


def origins_for(groups):
    """Hand-placed origins inside each region, spaced for labels."""
    pos = {}

    def take(group, sid=None, pred=None):
        got = [
            p
            for p in groups[group]
            if (sid is None or p["sid"] == sid) and (pred is None or pred(p))
        ]
        got.sort(key=lambda p: (p["x"], p["y"]))
        return got

    rp = take("rp2040", "C2961140")
    if len(rp) != 1:
        raise AssertionError(f"expected one RP2040, got {len(rp)}")
    # Origin 540: the QFN-56 symbol is 231 x 381, so the body sits at
    # ~420-651 x 130-511 and leaves x 300-420 inside the window for the
    # decoupling column. Origin 420 (tried first) put that body on top of
    # the USB-C / ESD / CC cluster -- watched overlapping U3/D1 and U3/R5.
    pos[rp[0]["id"]] = (540, 320)
    caps = take("rp2040", pred=lambda p: p["sid"] != "C2961140")
    for i, p in enumerate(caps):
        col, row = divmod(i, 6)
        pos[p["id"]] = (320 + col * 60, 185 + row * 52)

    flash = take("flash")
    if len(flash) != 1:
        raise AssertionError(f"expected one flash, got {len(flash)}")
    pos[flash[0]["id"]] = (800, 250)

    xtal = take("crystal", "C9900091606")
    if len(xtal) != 1:
        raise AssertionError(f"expected one crystal, got {len(xtal)}")
    pos[xtal[0]["id"]] = (770, 425)
    load = take("crystal", "C1548")
    if len(load) != 2:
        raise AssertionError(f"expected two 15pF, got {len(load)}")
    pos[load[0]["id"]] = (690, 395)
    pos[load[1]["id"]] = (690, 455)
    damp = take("crystal", "C11702")
    if len(damp) != 1:
        raise AssertionError(f"expected one crystal 1k, got {len(damp)}")
    pos[damp[0]["id"]] = (840, 425)

    ldo = take("ldo", "C5446")
    if len(ldo) != 1:
        raise AssertionError(f"expected one LDO, got {len(ldo)}")
    pos[ldo[0]["id"]] = (190, 600)
    rail = take("ldo", "C52923")
    if len(rail) != 2:
        raise AssertionError(f"expected two LDO 1uF, got {len(rail)}")
    pos[rail[0]["id"]] = (120, 540)
    pos[rail[1]["id"]] = (120, 660)

    usbc = take("usb", "C165948")
    esd = take("usb", "C323793")
    r27 = take("usb", "C25100")
    rcc = take("usb", "C25905")
    if len(usbc) != 1 or len(esd) != 1 or len(r27) != 2 or len(rcc) != 2:
        raise AssertionError(
            f"USB group: usbc={len(usbc)} esd={len(esd)} 27R={len(r27)} 5k1={len(rcc)}"
        )
    pos[usbc[0]["id"]] = (120, 300)
    pos[esd[0]["id"]] = (210, 230)
    pos[r27[0]["id"]] = (190, 380)
    pos[r27[1]["id"]] = (190, 435)
    pos[rcc[0]["id"]] = (270, 380)
    pos[rcc[1]["id"]] = (270, 435)

    sw = take("boot", "C318884")
    rboot = take("boot", "C11702")
    if len(sw) != 1 or len(rboot) != 1:
        raise AssertionError(f"BOOT group: sw={len(sw)} 1k={len(rboot)}")
    pos[sw[0]["id"]] = (430, 560)
    pos[rboot[0]["id"]] = (510, 560)

    ports = take("ports")
    for i, p in enumerate(ports):
        pos[p["id"]] = (700 + (i % 6) * 50, 560 + (i // 6) * 40)

    assigned = sum(len(v) for v in groups.values())
    if len(pos) != assigned:
        missing = [
            p["id"] for g in groups.values() for p in g if p["id"] not in pos
        ]
        raise AssertionError(f"origins missing for {missing}")

    by_id = {p["id"]: gname for gname, ps in groups.items() for p in ps}
    for pid, (x, y) in pos.items():
        xmin, xmax, ymin, ymax = REGIONS[by_id[pid]]
        if not (xmin <= x <= xmax and ymin <= y <= ymax):
            raise AssertionError(
                f"{pid} origin ({x},{y}) outside {by_id[pid]} {REGIONS[by_id[pid]]}"
            )
    return pos


def annotate(parts):
    """Replace each placeholder ? with a number, per prefix, left-to-right then top-to-bottom.

    Only `type == 'part'` is numbered. Net flags and net ports have empty
    designators on purpose; numbering them would invent U?/R? collisions
    that EasyEDA then treats as the same component as a real part.
    """
    pending = [
        p for p in parts if p.get("type") == "part" and "?" in (p["des"] or "")
    ]
    if not pending:
        print("  designators already numbered, leaving them")
        return {p["id"]: p["des"] for p in parts}
    by_prefix = {}
    for p in pending:
        pref = prefix_of(p["des"])
        by_prefix.setdefault(pref, []).append(p)
    mapping = {}
    for pref, group in sorted(by_prefix.items()):
        ordered = sorted(group, key=lambda p: (p["x"], p["y"]))
        for i, p in enumerate(ordered, start=1):
            mapping[p["id"]] = f"{pref}{i}"
    payload = json.dumps(mapping)
    js = (
        "const M = "
        + payload
        + "; "
        "const out = {}; "
        "for (const id of Object.keys(M)) { "
        "const prim = await eda.sch_PrimitiveComponent.get(id); "
        "if (!prim) throw new Error('get returned nothing for ' + id); "
        "const a = prim.toAsync(); "
        "a.setState_Designator(M[id]); "
        "await a.done(); "
        "const back = await eda.sch_PrimitiveComponent.get(id); "
        "out[id] = back.getState_Designator(); "
        "} "
        "return out;"
    )
    got = execute(js, timeout=90)
    for pid, want in mapping.items():
        have = got.get(pid)
        if have != want:
            raise AssertionError(f"designator write {pid}: wanted {want!r}, read {have!r}")
    return mapping


def assert_designators(parts):
    """Read every designator back: no '?', none duplicated. Print the list."""
    seen = {}
    rows = []
    for p in sorted(parts, key=lambda q: (prefix_of(q["des"]), q["x"], q["y"])):
        d = p["des"]
        if "?" in d:
            raise AssertionError(f"designator still contains '?': {d!r} ({p['id']})")
        if d in seen:
            raise AssertionError(f"duplicate designator {d!r}: {seen[d]} and {p['id']}")
        seen[d] = p["id"]
        rows.append(p)
    print("designators (read back):")
    for p in rows:
        extra = p["val"] or p["mfr"] or p["sid"]
        print(f"  {p['des']:8}  {p['sid']:12}  {extra}  @({p['x']},{p['y']})")
    print(f"  [ok ] {len(rows)} unique designators, none contain '?'")
    return rows


# schematic.py's un-tidied origins, keyed by the designator annotate()
# assigns when numbering those coordinates left-to-right then top-to-bottom.
# Used only when a wire still sits on the old geometry after a part move
# whose setState_Line was rejected (diagonal segments) -- then pin
# coincidence against the *current* pin list is empty and the original
# vertices have to be mapped back.
UNTIDY_ORIGIN = {
    "C1": (150, 410), "C2": (150, 470),
    "C3": (510, 780), "C4": (520, 780),
    "C5": (540, 780), "C6": (560, 780),
    "C7": (580, 780), "C8": (590, 780),
    "C9": (600, 780), "C10": (610, 780),
    "C11": (620, 780), "C12": (630, 780),
    "C13": (650, 780), "C14": (660, 780),
    "C15": (850, 700), "C16": (1050, 700),
    "D1": (900, 620),
    "R1": (330, 650), "R2": (380, 420),
    "R3": (780, 610), "R4": (780, 650),
    "R5": (1150, 565), "R6": (1150, 625),
    "SW1": (200, 700),
    "U1": (200, 600), "U2": (300, 430), "U3": (600, 450), "U4": (950, 750),
    "USBC1": (1050, 600),
}

VIA_Y = 70  # above the RP2040 body (bbox minY ~130)


def line_points(line):
    pts = []
    if not line:
        return pts
    if line and isinstance(line[0], (int, float)):
        for i in range(0, len(line) - 1, 2):
            pts.append((line[i], line[i + 1]))
        return pts
    for seg in line:
        pts.extend(line_points(seg))
    return pts


def _near(a, b, eps=0.05):
    return abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps


def collect_wire_hits(wires, parts):
    """Which pins each wire actually touches, by coincidence.

    Tries current pin coordinates first, then the un-tidied coordinates
    (current pin minus the delta from UNTIDY_ORIGIN) so a wire that was
    left behind by a failed setState_Line still reports its net.
    """
    current = []
    untidy = []
    for p in parts:
        for pin in p["pins"]:
            ident = (p["id"], pin["n"], pin["num"])
            current.append((pin["x"], pin["y"], ident))
            if p["des"] in UNTIDY_ORIGIN:
                ox, oy = UNTIDY_ORIGIN[p["des"]]
                dx, dy = p["x"] - ox, p["y"] - oy
                untidy.append((pin["x"] - dx, pin["y"] - dy, ident))
    hits = {}
    for w in wires:
        found = []
        seen = set()
        for x, y in line_points(w.get("line")):
            ident = None
            for px, py, i in current:
                if _near((x, y), (px, py)):
                    ident = i
                    break
            if ident is None:
                for px, py, i in untidy:
                    if _near((x, y), (px, py)):
                        ident = i
                        break
            if ident and ident not in seen:
                seen.add(ident)
                found.append(ident)
        hits[w["id"]] = found
    return hits


def snake_line(pins, all_pins):
    """One manhattan polyline that visits every pin via a rail at VIA_Y.

    Drops onto a pin along the pin's own x only when that x is not a
    crowded pin column -- otherwise it offsets 40 units so the drop
    cannot run down the RP2040's left column (watched: XOUT setState_Line
    along x=290 shorted QSPI_SCLK/SD0/SD1/SD2/SD3 and XIN).
    """
    uniq = []
    for pt in pins:
        if pt not in uniq:
            uniq.append(pt)
    if len(uniq) < 2:
        return None

    def crowded(x):
        return sum(1 for px, py in all_pins if abs(px - x) < 1) > 2

    def spur(x, y):
        vx = x - 40 if crowded(x) else x
        return vx, y

    pts = []
    for i, (x, y) in enumerate(uniq):
        vx, _ = spur(x, y)
        if i == 0:
            pts.extend([x, y, vx, y, vx, VIA_Y])
        elif i == len(uniq) - 1:
            pts.extend([vx, VIA_Y, vx, y, x, y])
        else:
            pts.extend([vx, VIA_Y, vx, y, x, y, vx, y, vx, VIA_Y])
    return pts


def layout(parts, origins, wires):
    """Move each part, then rebuild each wire as a manhattan snake
    through the same pins it already touched -- same net, same count.
    """
    hits = collect_wire_hits(wires, parts)
    for w in wires:
        print(f"  wire {w.get('net')!r} touches {len(hits.get(w['id'], []))} pins")

    moves = []
    for p in parts:
        nx, ny = origins[p["id"]]
        if nx != p["x"] or ny != p["y"]:
            moves.append({"id": p["id"], "x": nx, "y": ny})
    payload = json.dumps({"moves": moves})
    js = (
        "const P = "
        + payload
        + "; "
        "for (const m of P.moves) { "
        "const prim = await eda.sch_PrimitiveComponent.get(m.id); "
        "if (!prim) throw new Error('get returned nothing for ' + m.id); "
        "const a = prim.toAsync(); "
        "a.setState_X(m.x); "
        "a.setState_Y(m.y); "
        "await a.done(); "
        "} "
        "return {movedParts: P.moves.length};"
    )
    got = execute(js, timeout=90)
    print(f"  moved {got['movedParts']} parts")

    after = snapshot()
    by_ident = {}
    all_pins = []
    for p in after["parts"]:
        for pin in p["pins"]:
            by_ident[(p["id"], pin["n"], pin["num"])] = (pin["x"], pin["y"])
            all_pins.append((pin["x"], pin["y"]))

    routes = []
    for w in wires:
        pin_xy = []
        for ident in hits.get(w["id"], []):
            if ident in by_ident:
                pin_xy.append(by_ident[ident])
        line = snake_line(pin_xy, all_pins)
        if line:
            routes.append({"id": w["id"], "line": line, "net": w.get("net")})
    if routes:
        payload = json.dumps({"routes": routes})
        js = (
            "const P = "
            + payload
            + "; "
            "let n = 0; "
            "for (const r of P.routes) { "
            "const w = await eda.sch_PrimitiveWire.get(r.id); "
            "if (!w) throw new Error('wire get returned nothing for ' + r.id); "
            "const a = w.toAsync(); "
            "a.setState_Line(r.line); "
            "await a.done(); "
            "n += 1; "
            "} "
            "return {movedWires: n};"
        )
        wgot = execute(js, timeout=90)
        print(f"  rebuilt {wgot['movedWires']} wires")
    return got


def boxes_overlap(a, b):
    return a["minX"] < b["maxX"] and a["maxX"] > b["minX"] and a["minY"] < b["maxY"] and a["maxY"] > b["minY"]


def label_box(p):
    """Primitive bbox union visible text, so value/designator collisions count."""
    b = p.get("bbox")
    if not b:
        raise AssertionError(f"{p['des']} has no bbox")
    minx, miny, maxx, maxy = b["minX"], b["minY"], b["maxX"], b["maxY"]
    for v in p.get("vis") or []:
        text = v.get("v") or ""
        if text == "={Value}":
            text = p.get("val") or text
        elif text == "={Manufacturer Part}":
            text = p.get("mfr") or text
        elif v.get("k") == "Designator":
            text = p.get("des") or text
        width = max(36, 6 * max(len(text), 1))
        height = 12
        x = v["x"] if v["x"] is not None else p["x"]
        y = v["y"] if v["y"] is not None else p["y"]
        minx = min(minx, x)
        miny = min(miny, y - height)
        maxx = max(maxx, x + width)
        maxy = max(maxy, y + 4)
    return {"minX": minx, "minY": miny, "maxX": maxx, "maxY": maxy}


def assert_no_overlap(parts):
    bad = []
    boxes = [(p, label_box(p)) for p in parts]
    for i, (pa, ba) in enumerate(boxes):
        for pb, bb in boxes[i + 1 :]:
            if boxes_overlap(ba, bb):
                bad.append((pa["des"], pb["des"], ba, bb))
    if bad:
        detail = ", ".join(f"{a}/{b}" for a, b, _, _ in bad)
        raise AssertionError(f"overlapping bounding areas: {detail}")
    print(f"  [ok ] no bounding-area overlap among {len(parts)} parts")


def clear_overlay():
    """Drop the grey loading cover EasyEDA leaves up when an export times out.

    showLoading() "阻止用户进一步操作" -- menus go dead, clicks go nowhere.
    Watched: getExportDocumentFile hung past the bridge's 30s, the cover
    stayed, and every menu item was unselectable until this ran.
    """
    execute(
        "eda.sys_LoadingAndProgressBar.destroyLoading(); "
        "eda.sys_LoadingAndProgressBar.destroyProgressBar(); "
        "eda.sys_LoadingAndProgressBar.showProgressBar(100); "
        "eda.sys_LoadingAndProgressBar.destroyProgressBar(); "
        "eda.sys_LoadingAndProgressBar.destroyLoading(); "
        "return {cleared: true};"
    )


def export_page():
    """PDF via SCH_ManufactureData.getExportDocumentFile. File type is the
    documented literal 'PDF' (ESCH_ExportDocumentFileType.PDF); the enum
    object is not in the execution context.
    """
    js = r"""
const f = await eda.sch_ManufactureData.getExportDocumentFile(
  'schematic-page',
  'PDF',
  {theme: 'Black on White', size: 'Original Size'},
  'Current Schematic Page'
);
if (!f) return {error: 'getExportDocumentFile returned undefined'};
const buf = await f.arrayBuffer();
const bytes = new Uint8Array(buf);
let bin = '';
const chunk = 0x8000;
for (let i = 0; i < bytes.length; i += chunk) {
  bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
}
return {name: f.name || 'schematic-page.pdf', size: bytes.length, type: f.type || '', b64: btoa(bin)};
"""
    try:
        got = execute(js, timeout=120)
    except Exception:
        clear_overlay()
        raise
    clear_overlay()
    if got.get("error"):
        print(f"export: {got['error']}")
        return None
    os.makedirs(OUT_DIR, exist_ok=True)
    data = base64.b64decode(got["b64"])
    if len(data) != got["size"]:
        raise AssertionError(
            f"export size mismatch: header {got['size']}, decoded {len(data)}"
        )
    with open(EXPORT_PDF, "wb") as fh:
        fh.write(data)
    print(f"exported {EXPORT_PDF} ({len(data)} bytes, name={got['name']!r})")
    return len(data)


def pin_on_any_wire(pin, wires, eps=0.05):
    hits = []
    for w in wires:
        for x, y in line_points(w.get("line")):
            if abs(x - pin["x"]) < eps and abs(y - pin["y"]) < eps:
                hits.append(w["net"] if w.get("net") is not None else "")
                break
    return hits


def report_usb(parts, wires):
    """Task 4a -- report only. Do not rewire."""
    u1 = next((p for p in parts if p["sid"] == "C2961140"), None)
    usbc = next((p for p in parts if p["sid"] == "C165948"), None)
    esd = next((p for p in parts if p["sid"] == "C323793"), None)
    r27 = [p for p in parts if p["sid"] == "C25100"]
    names = sorted({(w.get("net") or "") for w in wires})
    print("USB D- (report, not a fix)")
    print(f"  wire net names present: {names}")
    dp_raw = [n for n in names if n == "USB_DP_RAW"]
    dm_like = [n for n in names if "DM" in n or n.endswith("_DN") or "D-" in n]
    print(f"  USB_DP_RAW in census: {bool(dp_raw)}")
    print(f"  D-ish net names in census: {dm_like or '(none)'}")
    if u1:
        for want in ("USB_DP", "USB_DM"):
            pins = [q for q in u1["pins"] if q["n"] == want]
            for q in pins:
                hits = pin_on_any_wire(q, wires)
                print(
                    f"  U {u1['des']}.{want} @{q['x']},{q['y']}  wire nets={hits or '(none)'}"
                )
    if usbc:
        for q in usbc["pins"]:
            if q["n"] in ("DP1", "DP2", "DN1", "DN2"):
                hits = pin_on_any_wire(q, wires)
                print(
                    f"  {usbc['des']}.{q['n']} @{q['x']},{q['y']}  wire nets={hits or '(none)'}"
                )
    if esd:
        for q in esd["pins"]:
            func = USBLC6_PINOUT.get(q["num"], "?")
            hits = pin_on_any_wire(q, wires)
            print(
                f"  {esd['des']} pin {q['num']} ({func}) @{q['x']},{q['y']}  wire nets={hits or '(none)'}"
            )
    for r in sorted(r27, key=lambda p: (p["x"], p["y"])):
        for q in r["pins"]:
            hits = pin_on_any_wire(q, wires)
            print(
                f"  {r['des']} pin {q['num']} @{q['x']},{q['y']}  wire nets={hits or '(none)'}"
            )


# The merged USB_DP_RAW polyline as recovered from d382fe3, 34 vertices.
# Kept so a failed split can put the short back rather than leave D-
# floating. Do not reuse it as a route -- it shorts DP to DN at x=1025.
MERGED_USB_DP_RAW = [
    1025, 605, 1015, 605, 870, 605, 1015, 605, 870, 560, 870, 605,
    870, 680, 870, 605, 800, 605, 870, 605, 800, 610, 800, 605,
    1025, 595, 1025, 605, 1025, 595, 1025, 585, 1015, 585, 1025, 585,
    1015, 595, 1025, 595, 1025, 615, 1025, 605, 1025, 615, 1015, 615,
    930, 615, 1015, 615, 930, 560, 930, 615, 930, 680, 930, 615,
    800, 615, 930, 615, 800, 650, 800, 615,
]

# D+ only. Notch at x=1025 so DP1→DP2 does not run down the connector
# column through DN1 at (1015, 595). Does not share a coordinate with
# USB_DM_LINE -- a shared vertex is how the previous pair merged.
USB_DP_LINE = [
    1015, 605, 1025, 605, 1025, 585, 1015, 585,
    1025, 585, 1025, 605, 870, 605,
    870, 560, 870, 680,
    870, 605, 800, 605, 800, 610,
]

# D- only. Notch at x=1035, not 1025 -- that x is D+'s.
USB_DM_LINE = [
    1015, 615, 1035, 615, 1035, 595, 1015, 595,
    1035, 595, 1035, 615, 930, 615,
    930, 560, 930, 680,
    930, 615, 800, 615, 800, 650,
]


def _flat_pts(flat):
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def _assert_manhattan(flat, label):
    pts = _flat_pts(flat)
    for a, b in zip(pts, pts[1:]):
        if a[0] != b[0] and a[1] != b[1]:
            raise AssertionError(f"{label} diagonal {a} → {b}")


def _shared_vertices(a, b):
    return set(_flat_pts(a)) & set(_flat_pts(b))


def name_empty_usb_cc(parts, wires):
    """Give the four USB/CC stubs the net names create() dropped.

    Does not move anything. The stubs already sit on the right pins;
    getState_Net() is empty because coincidence-inheritance does not
    populate it (pcb/README.md).
    """
    hits = collect_wire_hits(wires, parts)
    by_id = {p["id"]: p["des"] for p in parts}
    want = {}
    for w in wires:
        labels = set()
        for pid, n, num in hits.get(w["id"], []):
            labels.add((by_id.get(pid, pid), n or num))
        net = w.get("net") or ""
        if ("U3", "USB_DP") in labels and net in ("", "USB_DP"):
            want[w["id"]] = "USB_DP"
        elif ("U3", "USB_DM") in labels and net in ("", "USB_DM"):
            want[w["id"]] = "USB_DM"
        elif ("USBC1", "CC1") in labels and net in ("", "CC1"):
            want[w["id"]] = "CC1"
        elif ("USBC1", "CC2") in labels and net in ("", "CC2"):
            want[w["id"]] = "CC2"
    if set(want.values()) != {"USB_DP", "USB_DM", "CC1", "CC2"}:
        raise AssertionError(f"empty USB/CC stubs not 1:1: {want}")
    payload = json.dumps(want)
    js = (
        "const M = " + payload + "; "
        "const out = {}; "
        "for (const id of Object.keys(M)) { "
        "const w = await eda.sch_PrimitiveWire.modify(id, {net: M[id]}); "
        "if (!w) throw new Error('modify returned nothing for ' + id); "
        "out[id] = w.net; "
        "} "
        "return out;"
    )
    got = execute(js, timeout=60)
    for wid, net in want.items():
        if got.get(wid) != net:
            raise AssertionError(f"setState_Net {wid}: wanted {net!r}, read {got.get(wid)!r}")
    print(f"  named {len(want)} stubs: {sorted(want.values())}")
    return want


def split_usb_raw(wires):
    """Cut D- out of the merged USB_DP_RAW wire and give it its own net.

    `modify({line})` echoes the request and does not persist; `toAsync().
    setState_Line()` throws `modify failed!`. The shape that actually
    works: delete the one merged wire, then create short 2-point stubs
    per net. EasyEDA merges stubs of the same net into one object --
    that is fine, so long as D+ and D- share no vertex.
    """
    _assert_manhattan(USB_DP_LINE, "USB_DP_LINE")
    _assert_manhattan(USB_DM_LINE, "USB_DM_LINE")
    shared = _shared_vertices(USB_DP_LINE, USB_DM_LINE)
    if shared:
        raise AssertionError(f"D+/D- routes share vertices {shared}")

    merged = [w for w in wires if (w.get("net") or "") == "USB_DP_RAW"]
    if len(merged) != 1:
        raise AssertionError(f"expected one USB_DP_RAW wire, got {len(merged)}")
    wid = merged[0]["id"]
    before_line = [int(v) for v in (merged[0].get("line") or [])]
    if before_line != MERGED_USB_DP_RAW:
        raise AssertionError(
            f"USB_DP_RAW line is not the recovered merge ({len(before_line)} "
            f"numbers); refusing to rewrite a wire we have not inspected"
        )

    dp_segs = [
        ((1015, 605), (1025, 605)),
        ((1025, 605), (1025, 585)),
        ((1025, 585), (1015, 585)),
        ((1025, 605), (870, 605)),
        ((870, 605), (870, 560)),
        ((870, 605), (870, 680)),
        ((870, 605), (800, 605)),
        ((800, 605), (800, 610)),
    ]
    dm_segs = [
        ((1015, 615), (1035, 615)),
        ((1035, 615), (1035, 595)),
        ((1035, 595), (1015, 595)),
        ((1035, 615), (930, 615)),
        ((930, 615), (930, 560)),
        ((930, 615), (930, 680)),
        ((930, 615), (800, 615)),
        ((800, 615), (800, 650)),
    ]

    def segs_js(segs, net):
        bits = []
        for (x1, y1), (x2, y2) in segs:
            bits.append(
                f"w = await eda.sch_PrimitiveWire.create([{x1},{y1},{x2},{y2}], "
                f"{json.dumps(net)}, undefined, undefined, undefined); "
                "if (!w) throw new Error('create failed for ' + "
                f"{json.dumps(net)}); ids.push(w.primitiveId);"
            )
        return "".join(bits)

    restore = (
        "await eda.sch_PrimitiveWire.create("
        + json.dumps(MERGED_USB_DP_RAW)
        + ", 'USB_DP_RAW', undefined, undefined, undefined);"
    )
    js = (
        f"const del = await eda.sch_PrimitiveWire.delete({json.dumps(wid)}); "
        "const ids = []; "
        "let w; "
        "try { "
        + segs_js(dp_segs, "USB_DP_RAW")
        + segs_js(dm_segs, "USB_DM_RAW")
        + "return {deleted: del, created: ids.length}; "
        "} catch (e) { "
        + restore
        + "throw e; "
        "}"
    )
    got = execute(js, timeout=60)
    print(f"  deleted merged USB_DP_RAW; created {got['created']} stubs")
    return wid


def assert_usb_split(parts, wires):
    """D+ pins and D- pins sit on different named nets, and no wire hits both."""
    hits = collect_wire_hits(wires, parts)
    by_id = {p["id"]: p["des"] for p in parts}
    dp_pins = {("USBC1", "DP1"), ("USBC1", "DP2"), ("D1", "1"), ("D1", "6"), ("R3", "2")}
    dm_pins = {("USBC1", "DN1"), ("USBC1", "DN2"), ("D1", "3"), ("D1", "4"), ("R4", "2")}
    dp_nets, dm_nets = set(), set()
    for w in wires:
        labels = set()
        for pid, n, num in hits.get(w["id"], []):
            labels.add((by_id.get(pid, pid), n or num))
        on_dp = labels & dp_pins
        on_dm = labels & dm_pins
        if on_dp and on_dm:
            raise AssertionError(
                f"wire {w['id'][:12]} net={w.get('net')!r} still hits D+ {on_dp} and D- {on_dm}"
            )
        if on_dp:
            dp_nets.add(w.get("net") or "")
        if on_dm:
            dm_nets.add(w.get("net") or "")
    if dp_nets != {"USB_DP_RAW"}:
        raise AssertionError(f"D+ pins on {dp_nets}, wanted USB_DP_RAW only")
    if dm_nets != {"USB_DM_RAW"}:
        raise AssertionError(f"D- pins on {dm_nets}, wanted USB_DM_RAW only")
    print("  [ok ] USB_DP_RAW and USB_DM_RAW are separate nets")


def report_empty_nets(parts, wires):
    """Task 4b -- report only. What each empty-named wire connects."""
    empty = [w for w in wires if not w.get("net")]
    print(f"empty-net wires: {len(empty)}")
    pin_index = []
    for p in parts:
        for q in p["pins"]:
            pin_index.append((p["des"], q["n"] or q["num"], q["x"], q["y"]))
    for i, w in enumerate(empty, start=1):
        pts = line_points(w.get("line"))
        ends = []
        seen = set()
        for x, y in pts:
            for des, name, px, py in pin_index:
                if abs(x - px) < 0.05 and abs(y - py) < 0.05:
                    key = (des, name)
                    if key not in seen:
                        seen.add(key)
                        ends.append(f"{des}.{name}@{px},{py}")
        print(f"  [{i}] id={w['id']} points={pts} connects={ends or '(no pin coincidence)'}")


def _create_flag(kind, net, x, y):
    js = (
        f'const f = await eda.sch_PrimitiveComponent.createNetFlag('
        f'{json.dumps(kind)}, {json.dumps(net)}, {x}, {y}, 0, false); '
        "return f ? f.primitiveId : null;"
    )
    fid = execute(js)
    if not fid:
        raise AssertionError(f"{net} flag create returned nothing at ({x},{y})")
    return fid


def _create_stub(a, b, net):
    js = (
        f"const w = await eda.sch_PrimitiveWire.create("
        f"[{a[0]},{a[1]},{b[0]},{b[1]}], {json.dumps(net)}, undefined, undefined, undefined); "
        "if (!w) throw new Error('stub create failed for ' + " + json.dumps(net) + "); "
        "return w.primitiveId;"
    )
    wid = execute(js)
    if not wid:
        raise AssertionError(f"{net} stub create returned nothing {a}->{b}")
    return wid


def resolve_overlaps(parts, wires):
    """Unstack the 3V3 flags on U3's IOVDD row, and space C3-C14.

    Moving a component does not take its wires with it (watched on C3).
    Stubs are deleted and recreated; no part is deleted.
    """
    real = [p for p in parts if p.get("type") == "part"]
    flags = [p for p in parts if p.get("type") == "netflag"]
    u3 = next(p for p in real if p["des"] == "U3")

    # --- U3 3V3 flags sitting on the IOVDD pin row -------------------------
    u3_flags = [
        p for p in flags
        if p.get("net") == "3V3" and 550 <= p["x"] <= 690 and 640 <= p["y"] <= 680
    ]
    pin_by_xy = {}
    for pin in u3["pins"]:
        pin_by_xy[(pin["x"], pin["y"])] = pin
    stub_ids = []
    moves = []
    for fl in u3_flags:
        pin_xy = None
        stub = None
        for w in wires:
            pts = line_points(w.get("line"))
            on_flag = any(abs(x - fl["x"]) < 0.05 and abs(y - fl["y"]) < 0.05 for x, y in pts)
            if not on_flag:
                continue
            stub = w
            for x, y in pts:
                if (x, y) in pin_by_xy:
                    pin_xy = (x, y)
                    break
        if pin_xy is None:
            raise AssertionError(f"U3 3V3 flag {fl['id']} has no stub to a U3 pin")
        if stub:
            stub_ids.append(stub["id"])
        moves.append({"flag": fl["id"], "x": pin_xy[0], "y": 720, "pin": pin_xy})

    if stub_ids:
        ok = execute(
            "return await eda.sch_PrimitiveWire.delete(" + json.dumps(stub_ids) + ");"
        )
        print(f"  deleted {len(stub_ids)} U3 3V3 stubs ok={ok}")
    for m in moves:
        execute(
            "return await eda.sch_PrimitiveComponent.modify("
            + json.dumps(m["flag"])
            + ", {x: "
            + str(m["x"])
            + ", y: "
            + str(m["y"])
            + "});"
        )
        _create_stub(m["pin"], (m["x"], m["y"]), "3V3")
    print(f"  moved {len(moves)} U3 3V3 flags to y=720")

    # --- C3-C14: space to pitch 40, rewrite power stubs --------------------
    caps = sorted(
        [p for p in real if p["des"] in {f"C{i}" for i in range(3, 15)}],
        key=lambda p: p["x"],
    )
    if len(caps) != 12:
        raise AssertionError(f"expected C3-C14 (12), got {len(caps)}")

    cap_flags = [
        p for p in flags
        if p.get("net") in ("3V3", "GND") and 500 <= p["x"] <= 720 and 740 <= p["y"] <= 810
    ]
    cap_stub_ids = []
    flag_pts = {(p["x"], p["y"]) for p in cap_flags}
    for w in wires:
        pts = line_points(w.get("line"))
        if len(pts) > 4:
            continue
        if any(any(abs(x - fx) < 0.05 and abs(y - fy) < 0.05 for fx, fy in flag_pts) for x, y in pts):
            cap_stub_ids.append(w["id"])
    dvdd = [w for w in wires if (w.get("net") or "") == "DVDD"]
    if len(dvdd) != 1:
        raise AssertionError(f"expected one DVDD wire, got {len(dvdd)}")
    dvdd_id = dvdd[0]["id"]

    if cap_stub_ids:
        execute("return await eda.sch_PrimitiveWire.delete(" + json.dumps(cap_stub_ids) + ");")
        print(f"  deleted {len(cap_stub_ids)} cap-row stubs")
    if cap_flags:
        fids = [p["id"] for p in cap_flags]
        # netflags only -- assert before delete
        for p in cap_flags:
            if p.get("type") != "netflag":
                raise AssertionError(f"refusing to delete non-flag {p}")
        execute("return await eda.sch_PrimitiveComponent.delete(" + json.dumps(fids) + ");")
        print(f"  deleted {len(fids)} stacked cap-row flags")
    execute("return await eda.sch_PrimitiveWire.delete(" + json.dumps(dvdd_id) + ");")
    print("  deleted DVDD bus (will recreate to new cap pins)")

    start_x, pitch, cap_y = 400, 40, 780
    for i, cap in enumerate(caps):
        nx = start_x + i * pitch
        execute(
            "return await eda.sch_PrimitiveComponent.modify("
            + json.dumps(cap["id"])
            + f", {{x: {nx}, y: {cap_y}}});"
        )
        print(f"  {cap['des']} {cap['x']} -> {nx}")

    after = snapshot()
    caps2 = {
        p["des"]: p
        for p in after["parts"]
        if p.get("type") == "part" and p["des"] in {f"C{i}" for i in range(3, 15)}
    }
    u3 = next(p for p in after["parts"] if p.get("des") == "U3")

    def pin1(cap):
        pins = cap["pins"]
        return min(pins, key=lambda q: q["x"])

    def pin2(cap):
        pins = cap["pins"]
        return max(pins, key=lambda q: q["x"])

    def u3pin(*names):
        got = [q for q in u3["pins"] if q["n"] in names]
        return [(q["x"], q["y"]) for q in got]

    # DVDD: U3 VREG_VOUT + both DVDD pins + C3/C4/C5 left pins
    dvdd_targets = u3pin("VREG_VOUT", "DVDD")
    for des in ("C3", "C4", "C5"):
        p = pin1(caps2[des])
        dvdd_targets.append((p["x"], p["y"]))
    # rail at y=700, drops to each target
    rail_y = 700
    xs = sorted({x for x, y in dvdd_targets})
    segs = [((xs[0], rail_y), (xs[-1], rail_y))]
    for x, y in dvdd_targets:
        segs.append(((x, rail_y), (x, y)))
    for a, b in segs:
        if a == b:
            continue
        _create_stub(a, b, "DVDD")
    _create_flag("Power", "DVDD", pin1(caps2["C3"])["x"], 815)
    _create_stub((pin1(caps2["C3"])["x"], 815), (pin1(caps2["C3"])["x"], pin1(caps2["C3"])["y"]), "DVDD")
    print("  recreated DVDD rail")

    for des in (f"C{i}" for i in range(6, 15)):
        p = pin1(caps2[des])
        fx, fy = p["x"], 815
        _create_flag("Power", "3V3", fx, fy)
        _create_stub((fx, fy), (p["x"], p["y"]), "3V3")
    for des in (f"C{i}" for i in range(3, 15)):
        p = pin2(caps2[des])
        fx, fy = p["x"], 745
        _create_flag("Ground", "GND", fx, fy)
        _create_stub((fx, fy), (p["x"], p["y"]), "GND")
    print("  placed 3V3/GND flags at pitch 40")

    # designator above, value below, now that pitch is 40
    for des, cap in caps2.items():
        attrs = execute(
            "const a = await eda.sch_PrimitiveAttribute.getAll("
            + json.dumps(cap["id"])
            + "); "
            "return (a||[]).map(x => ({id: x.primitiveId, k: x.getState_Key(), vis: x.getState_ValueVisible()}));"
        )
        for a in attrs or []:
            if a["k"] == "Designator" and a.get("vis"):
                execute(
                    "return await eda.sch_PrimitiveAttribute.modify("
                    + json.dumps(a["id"])
                    + f", {{x: {cap['x'] - 8}, y: {cap_y + 22}}});"
                )
            if a["k"] == "Name" and a.get("vis"):
                execute(
                    "return await eda.sch_PrimitiveAttribute.modify("
                    + json.dumps(a["id"])
                    + f", {{x: {cap['x'] - 8}, y: {cap_y - 22}}});"
                )

    final = snapshot()
    caps3 = [
        p for p in final["parts"]
        if p.get("type") == "part" and p["des"] in {f"C{i}" for i in range(3, 15)}
    ]
    assert_no_overlap(caps3)
    real_n = sum(1 for p in final["parts"] if p.get("type") == "part")
    if real_n != 29:
        raise AssertionError(f"part count became {real_n}, wanted 29")
    print(f"  [ok ] C3-C14 no longer overlap, still {real_n} parts")
    return final


def wire_usb_connector(parts, wires):
    """Replace the USB-C star that runs through the pin column with stubs
    that leave left of the symbol, then reach D1 / U4 / C15 / R5 / R6.

    Does not move or delete parts. Same-net stubs may merge; different
    nets share no vertex -- that is how D+ last shorted to D- at x=1025.
    Notch x values are 10 apart in the gap between D1 (maxX ~950) and the
    USBC1 pin column (x=1015):
      955 GND, 965 VBUS, 975 CC2, 985 CC1, 995 DP, 1005 DN.
    CC1/CC2 go around the body (y=675 below, y=505 above) instead of
    through it, which is where their net names were sitting on the pins.
    """
    segs = {
        "USB_DP_RAW": [
            ((1015, 605), (995, 605)),
            ((1015, 585), (995, 585)),
            ((995, 585), (995, 605)),
            ((995, 605), (870, 605)),
            ((870, 605), (870, 560)),
            ((870, 605), (870, 680)),
            ((870, 605), (800, 605)),
            ((800, 605), (800, 610)),
        ],
        "USB_DM_RAW": [
            ((1015, 615), (1005, 615)),
            ((1015, 595), (1005, 595)),
            ((1005, 595), (1005, 615)),
            ((1005, 615), (930, 615)),
            ((930, 615), (930, 560)),
            ((930, 615), (930, 680)),
            ((930, 615), (800, 615)),
            ((800, 615), (800, 650)),
        ],
        "VBUS": [
            ((1015, 555), (965, 555)),
            ((1015, 645), (965, 645)),
            ((965, 555), (965, 645)),
            ((965, 645), (910, 645)),
            ((910, 645), (910, 680)),
            ((910, 680), (910, 750)),
            ((900, 680), (910, 680)),
            ((830, 700), (830, 750)),
            ((830, 750), (910, 750)),
        ],
        "CC1": [
            ((1015, 625), (985, 625)),
            ((985, 625), (985, 675)),
            ((985, 675), (1130, 675)),
            ((1130, 675), (1130, 625)),
        ],
        "CC2": [
            ((1015, 565), (975, 565)),
            ((975, 565), (975, 505)),
            ((975, 505), (1130, 505)),
            ((1130, 505), (1130, 565)),
        ],
        "GND": [
            ((1015, 545), (955, 545)),
            ((1015, 655), (955, 655)),
            ((955, 545), (955, 655)),
            ((955, 530), (955, 545)),
        ],
    }
    for net, path in segs.items():
        for a, b in path:
            if a[0] != b[0] and a[1] != b[1]:
                raise AssertionError(f"{net} diagonal {a} → {b}")
            if a == b:
                raise AssertionError(f"{net} zero-length {a}")
    verts = {}
    for net, path in segs.items():
        verts[net] = set()
        for a, b in path:
            verts[net].add(a)
            verts[net].add(b)
    nets = list(verts)
    for i, a in enumerate(nets):
        for b in nets[i + 1 :]:
            shared = verts[a] & verts[b]
            if shared:
                raise AssertionError(f"{a} and {b} share vertices {shared}")

    delete_ids = []
    for w in wires:
        net = w.get("net") or ""
        if net in ("USB_DP_RAW", "USB_DM_RAW", "VBUS", "CC1", "CC2"):
            delete_ids.append(w["id"])
            continue
        if net != "GND":
            continue
        pts = line_points(w.get("line"))
        # Left USBC1 GND rail only -- the EH rail at x=1115 stays.
        if any(abs(x - 990) < 0.05 and 520 <= y <= 660 for x, y in pts):
            delete_ids.append(w["id"])
    if not delete_ids:
        raise AssertionError("no USB-C wires to replace")

    left_gnd_flag = [
        p for p in parts
        if p.get("type") == "netflag"
        and p.get("net") == "GND"
        and abs(p["x"] - 990) < 0.05
        and abs(p["y"] - 530) < 0.05
    ]
    if len(left_gnd_flag) != 1:
        raise AssertionError(
            f"expected one left USBC1 GND flag at (990,530), got {len(left_gnd_flag)}"
        )

    ok = execute(
        "return await eda.sch_PrimitiveWire.delete(" + json.dumps(delete_ids) + ");"
    )
    print(f"  deleted {len(delete_ids)} USB-C wires ok={ok}")
    execute(
        "return await eda.sch_PrimitiveComponent.delete("
        + json.dumps([left_gnd_flag[0]["id"]])
        + ");"
    )
    print("  deleted left USBC1 GND flag")

    created = 0
    for net, path in segs.items():
        for a, b in path:
            _create_stub(a, b, net)
            created += 1
    _create_flag("Ground", "GND", 955, 530)
    print(f"  created {created} stubs + 1 GND flag")


def assert_usb_connector(parts, wires):
    """USBC1 data/power pins sit on the named nets, off the symbol body."""
    hits = collect_wire_hits(wires, parts)
    by_id = {p["id"]: p["des"] for p in parts}
    want = {
        ("USBC1", "DP1"): "USB_DP_RAW",
        ("USBC1", "DP2"): "USB_DP_RAW",
        ("USBC1", "DN1"): "USB_DM_RAW",
        ("USBC1", "DN2"): "USB_DM_RAW",
        ("USBC1", "CC1"): "CC1",
        ("USBC1", "CC2"): "CC2",
        ("USBC1", "VBUS"): "VBUS",
        ("D1", "1"): "USB_DP_RAW",
        ("D1", "6"): "USB_DP_RAW",
        ("D1", "3"): "USB_DM_RAW",
        ("D1", "4"): "USB_DM_RAW",
        ("D1", "5"): "VBUS",
        ("R3", "2"): "USB_DP_RAW",
        ("R4", "2"): "USB_DM_RAW",
        ("R6", "1"): "CC1",
        ("R5", "1"): "CC2",
        ("U4", "Vin"): "VBUS",
        ("C15", "1"): "VBUS",
    }
    found = {k: set() for k in want}
    for w in wires:
        net = w.get("net") or ""
        for pid, n, num in hits.get(w["id"], []):
            des = by_id.get(pid, pid)
            for key in ((des, n), (des, num)):
                if key in found:
                    found[key].add(net)
    for key, net in want.items():
        have = found.get(key) or set()
        if have != {net}:
            raise AssertionError(f"{key[0]}.{key[1]} on {have}, wanted {net}")
    assert_usb_split(parts, wires)
    usbc = next(p for p in parts if p["des"] == "USBC1")
    body = usbc["bbox"]
    for w in wires:
        net = w.get("net") or ""
        if net not in ("CC1", "CC2", "USB_DP_RAW", "USB_DM_RAW", "VBUS"):
            continue
        for x, y in line_points(w.get("line")):
            if body["minX"] < x < body["maxX"] and body["minY"] < y < body["maxY"]:
                raise AssertionError(
                    f"{net} vertex ({x},{y}) is inside USBC1 body {body}"
                )
    print("  [ok ] USB-C nets named, D+/D- separate, wires off the body")


def _on_segment(p, a, b, eps=0.05):
    ax, ay = a
    bx, by = b
    px, py = p
    if abs(ax - bx) < eps:
        return abs(px - ax) < eps and min(ay, by) - eps <= py <= max(ay, by) + eps
    if abs(ay - by) < eps:
        return abs(py - ay) < eps and min(ax, bx) - eps <= px <= max(ax, bx) + eps
    return False


def wire_qspi(parts, wires):
    """Split the two merged QSPI stars and name the four remaining empty stubs.

    Live: one empty wire hits QSPI_SCLK+SD3+CLK+IO3, another hits
    SD1+SD2+DO+/WP. Same merge as USB D+/D- -- shared notch x. Does not
    move or delete parts. Different nets share no vertex. SD1/SD2/SS go
    around the flash body (bbox ~100-290 x 580-630) rather than through it.
    """
    segs = {
        "QSPI_SCLK": [
            ((470, 510), (460, 510)),
            ((460, 510), (460, 600)),
            ((460, 600), (300, 600)),
        ],
        "QSPI_SD3": [
            ((470, 530), (450, 530)),
            ((450, 530), (450, 610)),
            ((450, 610), (300, 610)),
        ],
        "QSPI_SD0": [
            ((470, 560), (300, 560)),
            ((300, 560), (300, 590)),
        ],
        "QSPI_SD1": [
            ((470, 550), (440, 550)),
            ((440, 550), (440, 570)),
            ((440, 570), (80, 570)),
            ((80, 570), (80, 610)),
            ((80, 610), (90, 610)),
        ],
        "QSPI_SD2": [
            ((470, 540), (430, 540)),
            ((430, 540), (430, 640)),
            ((430, 640), (70, 640)),
            ((70, 640), (70, 600)),
            ((70, 600), (90, 600)),
        ],
        "QSPI_SS": [
            ((470, 580), (420, 580)),
            ((420, 580), (420, 670)),
            ((420, 670), (60, 670)),
            ((60, 670), (60, 620)),
            ((60, 620), (90, 620)),
            ((470, 580), (310, 580)),
            ((310, 580), (310, 650)),
        ],
        "BOOT": [
            ((350, 650), (350, 690)),
            ((350, 690), (180, 690)),
            ((180, 690), (180, 710)),
        ],
        "XOUT": [
            ((400, 420), (470, 420)),
        ],
    }
    allowed = {
        "QSPI_SCLK": {(470, 510), (300, 600)},
        "QSPI_SD3": {(470, 530), (300, 610)},
        "QSPI_SD0": {(470, 560), (300, 590)},
        "QSPI_SD1": {(470, 550), (90, 610)},
        "QSPI_SD2": {(470, 540), (90, 600)},
        "QSPI_SS": {(470, 580), (90, 620), (310, 650)},
        "BOOT": {(350, 650), (180, 710)},
        "XOUT": {(400, 420), (470, 420)},
    }
    for net, path in segs.items():
        for a, b in path:
            if a[0] != b[0] and a[1] != b[1]:
                raise AssertionError(f"{net} diagonal {a} → {b}")
            if a == b:
                raise AssertionError(f"{net} zero-length {a}")
    verts = {}
    for net, path in segs.items():
        verts[net] = set()
        for a, b in path:
            verts[net].add(a)
            verts[net].add(b)
    nets = list(verts)
    for i, a in enumerate(nets):
        for b in nets[i + 1 :]:
            shared = verts[a] & verts[b]
            if shared:
                raise AssertionError(f"{a} and {b} share vertices {shared}")

    pin_xy = []
    for p in parts:
        if p.get("type") != "part":
            continue
        for q in p["pins"]:
            pin_xy.append(((q["x"], q["y"]), p["des"], q["n"] or q["num"]))
    for net, path in segs.items():
        ok = allowed[net]
        for a, b in path:
            for xy, des, name in pin_xy:
                if xy in ok:
                    continue
                if _on_segment(xy, a, b):
                    raise AssertionError(
                        f"{net} {a}->{b} hits {des}.{name} at {xy}"
                    )

    empty = [w for w in wires if not (w.get("net") or "")]
    if len(empty) != 6:
        raise AssertionError(f"expected 6 empty-net wires, got {len(empty)}")
    delete_ids = [w["id"] for w in empty]

    keep_verts = set()
    for w in wires:
        if w["id"] in delete_ids:
            continue
        keep_net = w.get("net") or ""
        for x, y in line_points(w.get("line")):
            keep_verts.add(((x, y), keep_net))
    for net, vs in verts.items():
        for v in vs:
            for xy, knet in keep_verts:
                if abs(xy[0] - v[0]) < 0.05 and abs(xy[1] - v[1]) < 0.05 and knet != net:
                    raise AssertionError(
                        f"new {net} vertex {v} sits on existing {knet!r} at {xy}"
                    )

    ok = execute(
        "return await eda.sch_PrimitiveWire.delete(" + json.dumps(delete_ids) + ");"
    )
    print(f"  deleted {len(delete_ids)} empty QSPI/XOUT/BOOT wires ok={ok}")

    created = 0
    for net, path in segs.items():
        for a, b in path:
            _create_stub(a, b, net)
            created += 1
    print(f"  created {created} named stubs")


def assert_qspi(parts, wires):
    """QSPI/BOOT/XOUT pins sit on their own named nets; the two shorts are gone."""
    hits = collect_wire_hits(wires, parts)
    by_id = {p["id"]: p["des"] for p in parts}
    want = {
        ("U3", "QSPI_SCLK"): "QSPI_SCLK",
        ("U1", "CLK"): "QSPI_SCLK",
        ("U3", "QSPI_SD3"): "QSPI_SD3",
        ("U1", "IO3"): "QSPI_SD3",
        ("U3", "QSPI_SD0"): "QSPI_SD0",
        ("U1", "DI(IO0)"): "QSPI_SD0",
        ("U3", "QSPI_SD1"): "QSPI_SD1",
        ("U1", "DO(IO1)"): "QSPI_SD1",
        ("U3", "QSPI_SD2"): "QSPI_SD2",
        ("U1", "IO2"): "QSPI_SD2",
        ("U3", "QSPI_SS"): "QSPI_SS",
        ("U1", "CS#"): "QSPI_SS",
        ("R1", "1"): "QSPI_SS",
        ("R1", "2"): "BOOT",
        ("SW1", "1"): "BOOT",
        ("U3", "XOUT"): "XOUT",
        ("R2", "2"): "XOUT",
    }
    found = {k: set() for k in want}
    for w in wires:
        net = w.get("net") or ""
        labels = set()
        for pid, n, num in hits.get(w["id"], []):
            des = by_id.get(pid, pid)
            labels.add((des, n or num))
            for key in ((des, n), (des, num), (des, n or num)):
                if key in found:
                    found[key].add(net)
        if {("U3", "QSPI_SCLK"), ("U3", "QSPI_SD3")} <= labels:
            raise AssertionError(f"wire net={net!r} still shorts SCLK to SD3")
        if {("U3", "QSPI_SD1"), ("U3", "QSPI_SD2")} <= labels:
            raise AssertionError(f"wire net={net!r} still shorts SD1 to SD2")
    for key, net in want.items():
        have = found.get(key) or set()
        if have != {net}:
            raise AssertionError(f"{key[0]}.{key[1]} on {have}, wanted {net}")
    empty = [w for w in wires if not (w.get("net") or "")]
    if empty:
        raise AssertionError(f"{len(empty)} empty-net wires remain")
    print("  [ok ] QSPI/BOOT/XOUT named, SCLK≠SD3, SD1≠SD2")


def _part_by_des(parts, des):
    got = [p for p in parts if p.get("des") == des]
    if len(got) != 1:
        raise AssertionError(f"expected one {des}, got {len(got)}")
    return got[0]


def _pin(part, name=None, num=None):
    matches = [
        q for q in part["pins"]
        if (name is None or q["n"] == name) and (num is None or q["num"] == num)
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"{part['des']} pin name={name!r} num={num!r}: {len(matches)} matches"
        )
    return (matches[0]["x"], matches[0]["y"])


def assert_bodies_clear(parts, flags):
    """Part bodies do not overlap each other or a netflag. Labels can still
    collide; this is the check a person looking at the page can use."""
    real = [p for p in parts if p.get("type") == "part"]
    bad = []
    for i, a in enumerate(real):
        ba = a.get("bbox")
        if not ba:
            raise AssertionError(f"{a['des']} has no bbox")
        for b in real[i + 1 :]:
            bb = b.get("bbox")
            if bb and boxes_overlap(ba, bb):
                bad.append(f"{a['des']}/{b['des']}")
        for f in flags:
            fb = f.get("bbox")
            if fb and boxes_overlap(ba, fb):
                bad.append(f"{a['des']}/flag({f.get('net')}@{f['x']},{f['y']})")
    if bad:
        raise AssertionError(f"overlapping bodies (human check is blind): {', '.join(bad)}")
    print(f"  [ok ] {len(real)} part bodies clear of each other and {len(flags)} flags")


def wire_xtal(parts, wires):
    """Pull XIN and XTAL_B off the GND star, and space C1/C2 so a person
    can see the crystal without flags sitting on it.

    Live: U3.XIN, U2 pin 1 and C1.2 are one GND wire; R2.1, U2 pin 3 and
    C2.2 are another. C1.1 and C2.1 are floating. Does not delete parts.
    C1/C2 move left/down; U2 and R2 stay.
    """
    c1 = _part_by_des(parts, "C1")
    c2 = _part_by_des(parts, "C2")
    execute(
        "return await eda.sch_PrimitiveComponent.modify("
        + json.dumps(c1["id"])
        + ", {x: 100, y: 400});"
    )
    execute(
        "return await eda.sch_PrimitiveComponent.modify("
        + json.dumps(c2["id"])
        + ", {x: 100, y: 520});"
    )
    print("  moved C1 -> (100,400), C2 -> (100,520)")

    hits = collect_wire_hits(wires, parts)
    by_id = {p["id"]: p["des"] for p in parts}
    delete_ids = []
    for w in wires:
        labels = set()
        for pid, n, num in hits.get(w["id"], []):
            labels.add((by_id.get(pid, pid), n or num))
        if (w.get("net") or "") != "GND":
            continue
        if labels & {
            ("U3", "XIN"),
            ("U2", "1"),
            ("U2", "3"),
            ("R2", "1"),
            ("C1", "2"),
            ("C2", "2"),
        }:
            delete_ids.append(w["id"])
    flag_xy = {(180, 410), (180, 470), (345, 420), (255, 440)}
    flag_ids = []
    for p in parts:
        if p.get("type") != "netflag":
            continue
        if (p["x"], p["y"]) in flag_xy:
            if p.get("net") != "GND":
                raise AssertionError(f"refusing to delete non-GND flag {p}")
            flag_ids.append(p["id"])
            for w in wires:
                if w["id"] in delete_ids:
                    continue
                pts = line_points(w.get("line"))
                if len(pts) > 4:
                    continue
                if any(abs(x - p["x"]) < 0.05 and abs(y - p["y"]) < 0.05 for x, y in pts):
                    delete_ids.append(w["id"])
    if not delete_ids:
        raise AssertionError("no crystal GND-star wires to replace")
    if len(flag_ids) != 4:
        raise AssertionError(f"expected 4 crystal GND flags, got {len(flag_ids)}")

    ok = execute(
        "return await eda.sch_PrimitiveWire.delete(" + json.dumps(delete_ids) + ");"
    )
    print(f"  deleted {len(delete_ids)} merged crystal wires ok={ok}")
    execute(
        "return await eda.sch_PrimitiveComponent.delete(" + json.dumps(flag_ids) + ");"
    )
    print("  deleted 4 GND flags that sat on the crystal")

    after = snapshot()
    u2 = _part_by_des(after["parts"], "U2")
    u3 = _part_by_des(after["parts"], "U3")
    r2 = _part_by_des(after["parts"], "R2")
    c1 = _part_by_des(after["parts"], "C1")
    c2 = _part_by_des(after["parts"], "C2")
    xin = _pin(u3, "XIN")
    xout = _pin(u3, "XOUT")
    y1 = _pin(u2, num="1")
    y3 = _pin(u2, num="3")
    gnds = [(q["x"], q["y"]) for q in u2["pins"] if q["n"] == "GND"]
    r2n, r2f = _pin(r2, num="1"), _pin(r2, num="2")
    c1_gnd = min(((q["x"], q["y"]) for q in c1["pins"]), key=lambda t: t[0])
    c1_sig = max(((q["x"], q["y"]) for q in c1["pins"]), key=lambda t: t[0])
    c2_gnd = min(((q["x"], q["y"]) for q in c2["pins"]), key=lambda t: t[0])
    c2_sig = max(((q["x"], q["y"]) for q in c2["pins"]), key=lambda t: t[0])
    print(f"  XIN {xin} Y1 {y1} C1sig {c1_sig} C1gnd {c1_gnd}")
    print(f"  XTAL_B R2 {r2n} Y3 {y3} C2sig {c2_sig} C2gnd {c2_gnd}")
    print(f"  XOUT {xout} R2far {r2f} U2 GND {gnds}")

    # XIN drops below U3.XIN (not up through XOUT at y=420), under U2,
    # in to pin 1 from above. C1's signal pin is left of that, same net.
    segs = {
        "XIN": [
            (xin, (xin[0], 460)),
            ((xin[0], 460), (280, 460)),
            ((280, 460), (280, 410)),
            ((280, 410), (y1[0], 410)),
            ((y1[0], 410), y1),
            ((280, 410), (280, c1_sig[1])),
            ((280, c1_sig[1]), c1_sig),
        ],
        "XTAL_B": [
            (r2n, (r2n[0], y3[1])),
            ((r2n[0], y3[1]), y3),
            (y3, (y3[0], c2_sig[1])),
            ((y3[0], c2_sig[1]), c2_sig),
        ],
        "GND": [
            (c1_gnd, (c1_gnd[0] - 20, c1_gnd[1])),
            ((c1_gnd[0] - 20, c1_gnd[1]), (c1_gnd[0] - 20, c1_gnd[1] - 20)),
            (c2_gnd, (c2_gnd[0] - 20, c2_gnd[1])),
            ((c2_gnd[0] - 20, c2_gnd[1]), (c2_gnd[0] - 20, c2_gnd[1] + 20)),
        ],
    }
    # U2 case GND pins: drop away from the oscillator row, not toward R2.
    for gx, gy in gnds:
        if gx > u2["x"]:
            segs["GND"].append(((gx, gy), (gx, gy - 35)))
        else:
            segs["GND"].append(((gx, gy), (gx - 30, gy)))

    # C1_sig join: if y isn't 410, add a vertical. Filter zero-length.
    cleaned = {}
    for net, path in segs.items():
        out = []
        for a, b in path:
            if a == b:
                continue
            if a[0] != b[0] and a[1] != b[1]:
                raise AssertionError(f"{net} diagonal {a} → {b}")
            out.append((a, b))
        cleaned[net] = out
    segs = cleaned

    # XIN may have duplicated (280,410)->c1_sig and (280,410)->(y1[0],410)
    # if c1_sig is on y=410; that's same-net T, OK.

    verts = {}
    for net, path in segs.items():
        verts[net] = set()
        for a, b in path:
            verts[net].add(a)
            verts[net].add(b)
    nets = list(verts)
    for i, a in enumerate(nets):
        for b in nets[i + 1 :]:
            shared = verts[a] & verts[b]
            if shared:
                raise AssertionError(f"{a} and {b} share vertices {shared}")

    pin_xy = []
    for p in after["parts"]:
        if p.get("type") != "part":
            continue
        for q in p["pins"]:
            pin_xy.append(((q["x"], q["y"]), p["des"], q["n"] or q["num"]))
    allowed = {
        "XIN": {xin, y1, c1_sig},
        "XTAL_B": {r2n, y3, c2_sig},
        "GND": set(gnds) | {c1_gnd, c2_gnd},
    }
    for net, path in segs.items():
        okp = allowed[net]
        for a, b in path:
            for xy, des, name in pin_xy:
                if xy in okp:
                    continue
                if _on_segment(xy, a, b):
                    raise AssertionError(f"{net} {a}->{b} hits {des}.{name} at {xy}")

    keep_verts = set()
    deleted = set(delete_ids)
    for w in after["wires"]:
        knet = w.get("net") or ""
        for x, y in line_points(w.get("line")):
            keep_verts.add(((x, y), knet))
    for net, vs in verts.items():
        for v in vs:
            for xy, knet in keep_verts:
                if abs(xy[0] - v[0]) < 0.05 and abs(xy[1] - v[1]) < 0.05 and knet != net:
                    raise AssertionError(
                        f"new {net} vertex {v} sits on existing {knet!r} at {xy}"
                    )

    created = 0
    for net, path in segs.items():
        for a, b in path:
            _create_stub(a, b, net)
            created += 1
    _create_flag("Ground", "GND", c1_gnd[0] - 20, c1_gnd[1] - 20)
    _create_flag("Ground", "GND", c2_gnd[0] - 20, c2_gnd[1] + 20)
    for gx, gy in gnds:
        if gx > u2["x"]:
            _create_flag("Ground", "GND", gx, gy - 35)
        else:
            _create_flag("Ground", "GND", gx - 30, gy)
    print(f"  created {created} stubs + 4 GND flags")
    return after


def assert_xtal(parts, wires):
    hits = collect_wire_hits(wires, parts)
    by_id = {p["id"]: p["des"] for p in parts}
    want = {
        ("U3", "XIN"): "XIN",
        ("U2", "1"): "XIN",
        ("C1", "2"): "XIN",
        ("U3", "XOUT"): "XOUT",
        ("R2", "2"): "XOUT",
        ("R2", "1"): "XTAL_B",
        ("U2", "3"): "XTAL_B",
        ("C2", "2"): "XTAL_B",
        ("C1", "1"): "GND",
        ("C2", "1"): "GND",
    }
    found = {k: set() for k in want}
    for w in wires:
        net = w.get("net") or ""
        labels = set()
        for pid, n, num in hits.get(w["id"], []):
            des = by_id.get(pid, pid)
            labels.add((des, n or num))
            for key in ((des, n), (des, num), (des, n or num)):
                if key in found:
                    found[key].add(net)
        osc = labels & {("U2", "1"), ("U2", "3"), ("U3", "XIN"), ("U3", "XOUT")}
        gndp = {lab for lab in labels if lab[1] == "GND"}
        if osc and gndp:
            raise AssertionError(f"wire net={net!r} still mixes oscillator {osc} with GND {gndp}")
    for key, net in want.items():
        have = found.get(key) or set()
        if have != {net}:
            raise AssertionError(f"{key[0]}.{key[1]} on {have}, wanted {net}")
    u2 = _part_by_des(parts, "U2")
    for q in u2["pins"]:
        if q["n"] == "GND":
            nets = set(pin_on_any_wire(q, wires))
            if nets != {"GND"}:
                raise AssertionError(f"U2.GND #{q['num']} on {nets}")
    flags = [
        p for p in parts
        if p.get("type") == "netflag"
        and 50 <= p["x"] <= 420
        and 360 <= p["y"] <= 560
    ]
    cluster = [
        p for p in parts
        if p.get("des") in ("U2", "C1", "C2", "R2")
    ]
    assert_bodies_clear(cluster, flags)
    print("  [ok ] XIN / XTAL_B / XOUT separate from GND")


def wire_decouple(parts, wires):
    """Unshare C3-C14 pins and give each cap a power leg and a GND leg.

    Pitch 40 put cap i pin2 on cap i+1 pin1, so EasyEDA merged them --
    C3-C13 had both legs on DVDD or 3V3. Pitch 50 leaves 10 units between
    neighbouring pins. Does not delete parts. One rail + one flag per net
    so a person can see the row.
    """
    caps = sorted(
        [p for p in parts if p.get("type") == "part" and p["des"] in {f"C{i}" for i in range(3, 15)}],
        key=lambda p: int(p["des"][1:]),
    )
    if len(caps) != 12:
        raise AssertionError(f"expected C3-C14, got {[p['des'] for p in caps]}")

    delete_ids = []
    for w in wires:
        net = w.get("net") or ""
        pts = line_points(w.get("line"))
        if net == "DVDD":
            delete_ids.append(w["id"])
            continue
        if net == "3V3" and len(pts) <= 4 and any(abs(y - 780) < 0.05 for x, y in pts):
            delete_ids.append(w["id"])
            continue
        if net == "GND" and len(pts) <= 2 and any(
            abs(y - 780) < 0.05 and 400 <= x <= 870 for x, y in pts
        ):
            delete_ids.append(w["id"])

    flag_ids = []
    for p in parts:
        if p.get("type") != "netflag":
            continue
        if not (370 <= p["x"] <= 870):
            continue
        if abs(p["y"] - 745) < 0.05 or abs(p["y"] - 815) < 0.05:
            if p.get("net") not in ("GND", "3V3", "DVDD"):
                raise AssertionError(f"refusing to delete {p.get('net')} flag")
            flag_ids.append(p["id"])
    if not delete_ids:
        raise AssertionError("no cap-row stubs to replace")
    if len(flag_ids) < 10:
        raise AssertionError(f"expected cap-row flags, got {len(flag_ids)}")

    ok = execute(
        "return await eda.sch_PrimitiveWire.delete(" + json.dumps(delete_ids) + ");"
    )
    print(f"  deleted {len(delete_ids)} cap-row wires ok={ok}")
    execute(
        "return await eda.sch_PrimitiveComponent.delete(" + json.dumps(flag_ids) + ");"
    )
    print(f"  deleted {len(flag_ids)} cap-row flags")

    start_x, pitch, cap_y = 360, 50, 820
    for i, cap in enumerate(caps):
        nx = start_x + i * pitch
        execute(
            "return await eda.sch_PrimitiveComponent.modify("
            + json.dumps(cap["id"])
            + f", {{x: {nx}, y: {cap_y}}});"
        )
        print(f"  {cap['des']} {cap['x']},{cap['y']} -> {nx},{cap_y}")

    after = snapshot()
    caps2 = {
        p["des"]: p
        for p in after["parts"]
        if p.get("type") == "part" and p["des"] in {f"C{i}" for i in range(3, 15)}
    }
    u3 = _part_by_des(after["parts"], "U3")

    def left_right(cap):
        pts = [(q["x"], q["y"]) for q in cap["pins"]]
        return min(pts, key=lambda t: t[0]), max(pts, key=lambda t: t[0])

    pin1 = {}
    pin2 = {}
    for des, cap in caps2.items():
        a, b = left_right(cap)
        pin1[des], pin2[des] = a, b
        if abs(b[0] - a[0]) < 30:
            raise AssertionError(f"{des} pin span {b[0]-a[0]} too small")
    ordered = [f"C{i}" for i in range(3, 15)]
    for a, b in zip(ordered, ordered[1:]):
        gap = pin1[b][0] - pin2[a][0]
        if gap < 5:
            raise AssertionError(f"{a} pin2 and {b} pin1 still coincide (gap {gap})")

    dvdd_caps = ["C3", "C4", "C5"]
    v3_caps = [f"C{i}" for i in range(6, 15)]
    dvdd_pins = [(q["x"], q["y"]) for q in u3["pins"] if q["n"] in ("DVDD", "VREG_VOUT")]
    if len(dvdd_pins) != 3:
        raise AssertionError(f"U3 DVDD/VREG_VOUT pins: {dvdd_pins}")

    dvdd_rail_y, v3_rail_y, gnd_rail_y = 700, 860, 770
    dvdd_xs = [p[0] for p in dvdd_pins] + [pin1[d][0] for d in dvdd_caps]
    v3_xs = [pin1[d][0] for d in v3_caps]
    gnd_xs = [pin2[d][0] for d in ordered]

    segs = {
        "DVDD": [
            ((min(dvdd_xs), dvdd_rail_y), (max(dvdd_xs), dvdd_rail_y)),
        ],
        "3V3": [
            ((min(v3_xs), v3_rail_y), (max(v3_xs), v3_rail_y)),
        ],
        "GND": [
            ((min(gnd_xs), gnd_rail_y), (max(gnd_xs), gnd_rail_y)),
        ],
    }
    for x, y in dvdd_pins:
        segs["DVDD"].append(((x, dvdd_rail_y), (x, y)))
    for d in dvdd_caps:
        x, y = pin1[d]
        segs["DVDD"].append(((x, dvdd_rail_y), (x, y)))
    for d in v3_caps:
        x, y = pin1[d]
        segs["3V3"].append(((x, v3_rail_y), (x, y)))
    for d in ordered:
        x, y = pin2[d]
        segs["GND"].append(((x, gnd_rail_y), (x, y)))

    # flags off the cap bodies: DVDD left of rail, 3V3 above its rail, GND right
    dvdd_flag = (min(dvdd_xs), dvdd_rail_y - 25)
    v3_flag = (min(v3_xs), v3_rail_y + 25)
    gnd_flag = (min(gnd_xs) - 25, gnd_rail_y)
    segs["DVDD"].append((dvdd_flag, (dvdd_flag[0], dvdd_rail_y)))
    segs["3V3"].append((v3_flag, (v3_flag[0], v3_rail_y)))
    segs["GND"].append((gnd_flag, (min(gnd_xs), gnd_rail_y)))

    cleaned = {}
    for net, path in segs.items():
        out = []
        for a, b in path:
            if a == b:
                continue
            if a[0] != b[0] and a[1] != b[1]:
                raise AssertionError(f"{net} diagonal {a} → {b}")
            out.append((a, b))
        cleaned[net] = out
    segs = cleaned

    verts = {}
    for net, path in segs.items():
        verts[net] = set()
        for a, b in path:
            verts[net].add(a)
            verts[net].add(b)
    nets = list(verts)
    for i, a in enumerate(nets):
        for b in nets[i + 1 :]:
            shared = verts[a] & verts[b]
            if shared:
                raise AssertionError(f"{a} and {b} share vertices {shared}")

    # existing U3 3V3 rail lives at y=700; DVDD rail is also y=700.
    # they must not meet. U3 3V3 min x is 560; DVDD max x is max(dvdd_xs).
    if max(dvdd_xs) >= 560:
        raise AssertionError(f"DVDD rail x={max(dvdd_xs)} would touch U3 3V3 rail at 560")

    pin_xy = []
    for p in after["parts"]:
        if p.get("type") != "part":
            continue
        for q in p["pins"]:
            pin_xy.append(((q["x"], q["y"]), p["des"], q["n"] or q["num"]))
    allowed = {
        "DVDD": set(dvdd_pins) | {pin1[d] for d in dvdd_caps},
        "3V3": {pin1[d] for d in v3_caps},
        "GND": {pin2[d] for d in ordered},
    }
    for net, path in segs.items():
        okp = allowed[net]
        for a, b in path:
            for xy, des, name in pin_xy:
                if xy in okp:
                    continue
                if _on_segment(xy, a, b):
                    raise AssertionError(f"{net} {a}->{b} hits {des}.{name} at {xy}")

    keep_verts = set()
    for w in after["wires"]:
        knet = w.get("net") or ""
        for x, y in line_points(w.get("line")):
            keep_verts.add(((x, y), knet))
    for net, vs in verts.items():
        for v in vs:
            for xy, knet in keep_verts:
                if abs(xy[0] - v[0]) < 0.05 and abs(xy[1] - v[1]) < 0.05 and knet != net:
                    raise AssertionError(
                        f"new {net} vertex {v} sits on existing {knet!r} at {xy}"
                    )

    created = 0
    for net, path in segs.items():
        for a, b in path:
            _create_stub(a, b, net)
            created += 1
    _create_flag("Power", "DVDD", *dvdd_flag)
    _create_flag("Power", "3V3", *v3_flag)
    _create_flag("Ground", "GND", *gnd_flag)
    print(f"  created {created} stubs + 3 flags")


def assert_decouple(parts, wires):
    hits = collect_wire_hits(wires, parts)
    by_id = {p["id"]: p["des"] for p in parts}
    want = {}
    for des in ("C3", "C4", "C5"):
        want[(des, "1")] = "DVDD"
        want[(des, "2")] = "GND"
    for i in range(6, 15):
        want[(f"C{i}", "1")] = "3V3"
        want[(f"C{i}", "2")] = "GND"
    found = {k: set() for k in want}
    for w in wires:
        net = w.get("net") or ""
        for pid, n, num in hits.get(w["id"], []):
            des = by_id.get(pid, pid)
            for key in ((des, n), (des, num), (des, n or num)):
                if key in found:
                    found[key].add(net)
    for key, net in want.items():
        have = found.get(key) or set()
        if have != {net}:
            raise AssertionError(f"{key[0]}.{key[1]} on {have}, wanted {net}")
    u3 = _part_by_des(parts, "U3")
    for q in u3["pins"]:
        if q["n"] in ("DVDD", "VREG_VOUT"):
            nets = set(pin_on_any_wire(q, wires))
            if nets != {"DVDD"}:
                raise AssertionError(f"U3.{q['n']} #{q['num']} on {nets}")
        if q["n"] in ("IOVDD", "VREG_IN", "USB_VDD", "ADC_AVDD"):
            nets = set(pin_on_any_wire(q, wires))
            if nets != {"3V3"}:
                raise AssertionError(f"U3.{q['n']} #{q['num']} on {nets}")
    caps = [
        p for p in parts
        if p.get("type") == "part" and p["des"] in {f"C{i}" for i in range(3, 15)}
    ]
    flags = [
        p for p in parts
        if p.get("type") == "netflag"
        and 300 <= p["x"] <= 1000
        and 650 <= p["y"] <= 900
    ]
    assert_bodies_clear(caps, flags)
    pin_pts = []
    for cap in caps:
        for q in cap["pins"]:
            pin_pts.append((q["x"], q["y"], cap["des"], q["num"]))
    for i, a in enumerate(pin_pts):
        for b in pin_pts[i + 1 :]:
            if abs(a[0] - b[0]) < 0.05 and abs(a[1] - b[1]) < 0.05:
                raise AssertionError(
                    f"{a[2]}.{a[3]} and {b[2]}.{b[3]} still share ({a[0]},{a[1]})"
                )
    print("  [ok ] C3-C14 pin1 power / pin2 GND, pins do not coincide")


# Flag origin -> (net, kind, pin_xy, new_flag_xy). Kind is Ground/Power.
# Stubs into the part body; new origin is off the bbox, same net, no
# shared vertex with a different net.
FLAGS_OFF_BODY = [
    ((105, 590), "GND", "Ground", (90, 590), (70, 590)),
    ((285, 620), "3V3", "Power", (300, 620), (320, 620)),
    ((485, 370), "3V3", "Power", (470, 370), (450, 370)),
    ((1045, 700), "3V3", "Power", (1030, 700), (1010, 700)),
]


def flags_off_bodies(parts, wires):
    """Move the four flags whose stubs ran into a part body.

    Idempotent: already-moved flags are left alone. Does not delete parts.
    """
    flag_by_xy = {
        (p["x"], p["y"]): p
        for p in parts
        if p.get("type") == "netflag"
    }
    pending = []
    for old, net, kind, pin, new in FLAGS_OFF_BODY:
        if old in flag_by_xy:
            pending.append((old, net, kind, pin, new, flag_by_xy[old]))
        elif new in flag_by_xy and flag_by_xy[new].get("net") == net:
            print(f"  {net} flag already at {new}")
        else:
            raise AssertionError(f"no {net} flag at {old} or {new}")
    if not pending:
        print("  [ok ] flags already off part bodies")
        return

    delete_flags = []
    delete_wires = []
    for old, net, kind, pin, new, fl in pending:
        if fl.get("net") != net:
            raise AssertionError(f"flag at {old} is {fl.get('net')} not {net}")
        delete_flags.append(fl["id"])
        found = None
        for w in wires:
            pts = line_points(w.get("line"))
            if len(pts) > 4:
                continue
            if any(abs(x - old[0]) < 0.05 and abs(y - old[1]) < 0.05 for x, y in pts):
                if any(abs(x - pin[0]) < 0.05 and abs(y - pin[1]) < 0.05 for x, y in pts):
                    found = w["id"]
                    break
        if not found:
            raise AssertionError(f"no stub from {pin} to flag {old}")
        delete_wires.append(found)

    keep = set()
    skip = set(delete_wires)
    for w in wires:
        if w["id"] in skip:
            continue
        knet = w.get("net") or ""
        for x, y in line_points(w.get("line")):
            keep.add(((x, y), knet))
    for old, net, kind, pin, new, fl in pending:
        for xy, knet in keep:
            if abs(xy[0] - new[0]) < 0.05 and abs(xy[1] - new[1]) < 0.05 and knet != net:
                raise AssertionError(f"new {net} {new} hits existing {knet} {xy}")

    ok = execute(
        "return await eda.sch_PrimitiveWire.delete(" + json.dumps(delete_wires) + ");"
    )
    print(f"  deleted {len(delete_wires)} stubs {ok}")
    ok = execute(
        "return await eda.sch_PrimitiveComponent.delete("
        + json.dumps(delete_flags)
        + ");"
    )
    print(f"  deleted {len(delete_flags)} flags {ok}")
    for old, net, kind, pin, new, fl in pending:
        _create_stub(pin, new, net)
        _create_flag(kind, net, new[0], new[1])
        print(f"  {net} flag {old} -> {new}")


def tidy_labels(parts):
    """Hide manufacturer names sitting on pin columns, and fill empty
    capacitor Values from the manufacturer PN so a person can read the
    row. Does not change a part, a net, or a pin.
    """
    by_des = {p["des"]: p for p in parts if p.get("type") == "part"}
    hide_name = []
    for des in ("USBC1", "D1"):
        if des not in by_des:
            raise AssertionError(f"missing {des}")
        hide_name.append(by_des[des]["id"])
    # 0402CG150 = 15 pF; CL05B104 = 100 nF; CL05A105 = 1 µF.
    values = {}
    for des in ("C1", "C2"):
        values[by_des[des]["id"]] = "15pF"
    for des in ("C3", "C4") + tuple(f"C{i}" for i in range(7, 15)):
        values[by_des[des]["id"]] = "100nF"
    for des in ("C5", "C6"):
        values[by_des[des]["id"]] = "1uF"

    payload = json.dumps({"hide": hide_name, "values": values})
    js = (
        "const M = " + payload + "; "
        "const out = {hidden: [], values: {}}; "
        "for (const id of M.hide) { "
        "const attrs = await eda.sch_PrimitiveAttribute.getAll(id); "
        "for (const a of attrs || []) { "
        "if (a.getState_Key() !== 'Name') continue; "
        "if (a.getState_ValueVisible() !== true) continue; "
        "const got = await eda.sch_PrimitiveAttribute.modify("
        "a.getState_PrimitiveId(), {valueVisible: false}); "
        "if (!got) throw new Error('hide Name failed for ' + id); "
        "out.hidden.push(id); "
        "} "
        "} "
        "for (const id of Object.keys(M.values)) { "
        "const want = M.values[id]; "
        "const attrs = await eda.sch_PrimitiveAttribute.getAll(id); "
        "let aid = null; "
        "for (const a of attrs || []) { "
        "if (a.getState_Key() === 'Value') { aid = a.getState_PrimitiveId(); break; } "
        "} "
        "if (!aid) throw new Error('no Value attr on ' + id); "
        "const got = await eda.sch_PrimitiveAttribute.modify(aid, {value: want}); "
        "if (!got) throw new Error('set Value failed for ' + id); "
        "const c = await eda.sch_PrimitiveComponent.get(id); "
        "const other = Object.assign({}, c.getState_OtherProperty() || {}); "
        "other.Value = want; "
        "const back = await eda.sch_PrimitiveComponent.modify(id, {otherProperty: other}); "
        "if (!back) throw new Error('otherProperty.Value failed for ' + id); "
        "out.values[id] = want; "
        "} "
        "return out;"
    )
    got = execute(js, timeout=90)
    if len(got.get("hidden") or []) != len(hide_name):
        raise AssertionError(f"hid Name on {got.get('hidden')}, wanted {hide_name}")
    if set(got.get("values") or {}) != set(values):
        raise AssertionError(f"set values {got.get('values')}, wanted {values}")
    print(f"  hid Name on USBC1, D1")
    print(f"  set {len(values)} capacitor Values (15pF / 100nF / 1uF)")


def main(argv=None):

    import argparse

    parser = argparse.ArgumentParser(
        description="Annotate and space the schematic. Default is annotate-only."
    )
    parser.add_argument(
        "--layout",
        action="store_true",
        help="also move parts and rebuild wires. Off by default: a timeout "
        "mid-layout is how the previous pass wiped the page.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print USB D- and empty-net wire reports; does not rewire.",
    )
    parser.add_argument(
        "--split-usb",
        action="store_true",
        help="name USB/CC stubs and split the merged USB_DP_RAW short. "
        "Does not move parts.",
    )
    parser.add_argument(
        "--overlaps",
        action="store_true",
        help="unstack U3 3V3 flags and space C3-C14. Does not delete parts.",
    )
    parser.add_argument(
        "--wire-usb",
        action="store_true",
        help="reroute USB-C stubs off the pin column. Does not move parts.",
    )
    parser.add_argument(
        "--wire-qspi",
        action="store_true",
        help="split merged QSPI shorts and name empty stubs. Does not move parts.",
    )
    parser.add_argument(
        "--wire-xtal",
        action="store_true",
        help="split XIN/XTAL_B off GND and space C1/C2. Moves those two caps only.",
    )
    parser.add_argument(
        "--wire-decouple",
        action="store_true",
        help="unshare C3-C14 pins and wire pin1 to power / pin2 to GND.",
    )
    parser.add_argument(
        "--flags-off",
        action="store_true",
        help="move the four flags whose stubs ran into a part body.",
    )
    parser.add_argument(
        "--tidy-labels",
        action="store_true",
        help="hide USBC1/D1 manufacturer names; fill empty C1-C14 Values.",
    )
    args = parser.parse_args(argv)

    open_schematic()
    before = snapshot()
    census_before = census_from(before["wires"])
    print_census("BEFORE", census_before)
    print(f"parts: {len(before['parts'])}  wires: {len(before['wires'])}")

    if args.flags_off or args.tidy_labels:
        n_parts = sum(1 for p in before["parts"] if p.get("type") == "part")
        if args.flags_off:
            flags_off_bodies(before["parts"], before["wires"])
            before = snapshot()
        if args.tidy_labels:
            tidy_labels(before["parts"])
            before = snapshot()
        after = before
        n_after = sum(1 for p in after["parts"] if p.get("type") == "part")
        if n_after != n_parts:
            raise AssertionError(f"part count {n_parts} -> {n_after}")
        real = [p for p in after["parts"] if p.get("type") == "part"]
        flags = [p for p in after["parts"] if p.get("type") == "netflag"]
        assert_bodies_clear(real, flags)
        print_census("AFTER", census_from(after["wires"]))
        print(f"parts: {len(after['parts'])}  wires: {len(after['wires'])}")
        save_schematic()
        return

    if args.wire_decouple:
        n_parts = sum(1 for p in before["parts"] if p.get("type") == "part")
        wire_decouple(before["parts"], before["wires"])
        after = snapshot()
        n_after = sum(1 for p in after["parts"] if p.get("type") == "part")
        if n_after != n_parts:
            raise AssertionError(f"part count {n_parts} -> {n_after}")
        assert_decouple(after["parts"], after["wires"])
        print_census("AFTER", census_from(after["wires"]))
        print(f"parts: {len(after['parts'])}  wires: {len(after['wires'])}")
        save_schematic()
        return

    if args.wire_xtal:
        n_parts = sum(1 for p in before["parts"] if p.get("type") == "part")
        wire_xtal(before["parts"], before["wires"])
        after = snapshot()
        n_after = sum(1 for p in after["parts"] if p.get("type") == "part")
        if n_after != n_parts:
            raise AssertionError(f"part count {n_parts} -> {n_after}")
        assert_xtal(after["parts"], after["wires"])
        print_census("AFTER", census_from(after["wires"]))
        print(f"parts: {len(after['parts'])}  wires: {len(after['wires'])}")
        save_schematic()
        return

    if args.wire_qspi:
        n_parts = sum(1 for p in before["parts"] if p.get("type") == "part")
        wire_qspi(before["parts"], before["wires"])
        after = snapshot()
        n_after = sum(1 for p in after["parts"] if p.get("type") == "part")
        if n_after != n_parts:
            raise AssertionError(f"part count {n_parts} -> {n_after}")
        assert_qspi(after["parts"], after["wires"])
        print_census("AFTER", census_from(after["wires"]))
        print(f"parts: {len(after['parts'])}  wires: {len(after['wires'])}")
        save_schematic()
        return

    if args.wire_usb:
        n_parts = sum(1 for p in before["parts"] if p.get("type") == "part")
        wire_usb_connector(before["parts"], before["wires"])
        after = snapshot()
        n_after = sum(1 for p in after["parts"] if p.get("type") == "part")
        if n_after != n_parts:
            raise AssertionError(f"part count {n_parts} -> {n_after}")
        assert_usb_connector(after["parts"], after["wires"])
        print_census("AFTER", census_from(after["wires"]))
        print(f"parts: {len(after['parts'])}  wires: {len(after['wires'])}")
        save_schematic()
        return

    if args.overlaps:
        resolve_overlaps(before["parts"], before["wires"])
        save_schematic()
        return

    if args.split_usb:
        name_empty_usb_cc(before["parts"], before["wires"])
        split_usb_raw(before["wires"])
        after = snapshot()
        real = [p for p in after["parts"] if p.get("type") == "part"]
        assert_designators(real)
        assert_usb_split(after["parts"], after["wires"])
        print_census("AFTER", census_from(after["wires"]))
        print(f"parts: {len(after['parts'])}  wires: {len(after['wires'])}")
        report_usb(after["parts"], after["wires"])
        save_schematic()
        return

    mapping = annotate(before["parts"])
    print(f"annotated {len(mapping)} parts")

    if args.layout:
        groups = classify(before["parts"])
        for name, ps in groups.items():
            print(f"  group {name}: {len(ps)}")
        origins = origins_for(groups)
        layout(before["parts"], origins, before["wires"])

    after = snapshot()
    real = [p for p in after["parts"] if p.get("type") == "part"]
    assert_designators(real)
    if args.layout:
        assert_no_overlap(after["parts"])

    census_after = census_from(after["wires"])
    print_census("AFTER", census_after)
    if census_before != census_after:
        raise AssertionError(
            f"net census changed:\n  before={census_before}\n  after={census_after}"
        )
    print("  [ok ] net census unchanged")
    save_schematic()

    if args.layout:
        try:
            size = export_page()
        except Exception as e:
            print(f"export failed (annotation already committed): {e}")
            size = None
        if size is None:
            print("no export exists that produced a file from this call")
        else:
            print(f"export file size: {size} bytes")

    if args.report:
        report_usb(after["parts"], after["wires"])
        report_empty_nets(after["parts"], after["wires"])


if __name__ == "__main__":
    sys.exit(main())
