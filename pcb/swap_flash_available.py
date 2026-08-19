"""Replace the unavailable XSON flash with JLCPCB-stocked C179171.

The live schematic uses W25Q64JVXGIQ (C2940195), whose XSON-8 symbol has
a ninth exposed-pad pin. C179171 is W25Q64JVSSIQ in SOIC-8. Its actual
EasyEDA symbol was test-placed and measured before this migration:

* at origin (170, 605), pins 1-4 land on the existing left wire ends;
* pins 5-8 land on the four horizontal stubs already present at x=250;
* the XSON-only EP wire and ground flag are deleted.

The operation creates and validates the replacement before deleting the
old part. It refuses any unexpected identity, coordinate, or pin map.

    python3 swap_flash_available.py            # report only
    python3 swap_flash_available.py --apply    # replace and verify
"""

import json
import os
import sys

import schematic as sch
from bridge import execute


PROJECT_UUID = "78dc44acfef533ed0a8fb74feeb342c9e0374a2909a81ae129ddfffffb35a4ff"
DEVICE_UUID = "8f2ba1ff5eccd8e9"
OLD_LCSC = "C2940195"
NEW_LCSC = "C179171"
NEW_MPN = "W25Q64JVSSIQ"
NEW_ORIGIN = (170, 605)

EP_WIRE_ID = "9637da04cca6dd49"
EP_FLAG_ID = "188f5ab3234b9370"

EXPECTED_PINS = {
    "1": ("CS#", 90, 620, "QSPI_SS"),
    "2": ("DO(IO1)", 90, 610, "QSPI_SD1"),
    "3": ("WP#(IO2)", 90, 600, "QSPI_SD2"),
    "4": ("GND", 90, 590, "GND"),
    "5": ("DI(IO0)", 250, 590, "QSPI_SD0"),
    "6": ("CLK", 250, 600, "QSPI_SCLK"),
    "7": ("HOLD#orRESET#(IO3)", 250, 610, "QSPI_SD3"),
    "8": ("VCC", 250, 620, "3V3"),
}


def live_state():
    sch.open_project_schematic()
    js = f"""
    const cs = await eda.sch_PrimitiveComponent.getAll();
    const ws = await eda.sch_PrimitiveWire.getAll();
    const u1 = (cs||[]).filter(c => c.designator === "U1");
    const probes = [];
    for (const c of u1) {{
      const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(
        c.primitiveId);
      probes.push({{id:c.primitiveId, sid:c.supplierId, mid:c.manufacturerId,
        x:c.x, y:c.y, unique:c.uniqueId,
        footprint:c.footprint && c.footprint.name,
        pins:(pins||[]).map(p=>[p.pinNumber,p.pinName,p.x,p.y])}});
    }}
    return {{count:(cs||[]).length, u1:probes,
      stale:(cs||[]).filter(c => c.supplierId === {json.dumps(NEW_LCSC)}
        && c.designator !== "U1").map(c=>({{id:c.primitiveId,des:c.designator,
          x:c.x,y:c.y}})),
      epWire:(ws||[]).filter(w=>w.primitiveId==={json.dumps(EP_WIRE_ID)})
        .map(w=>({{id:w.primitiveId,net:w.net,line:w.line}})),
      epFlag:(cs||[]).filter(c=>c.primitiveId==={json.dumps(EP_FLAG_ID)})
        .map(c=>({{id:c.primitiveId,x:c.x,y:c.y}}))}};
    """
    return execute(js, 120)


def validate_before(state):
    if len(state["u1"]) != 1:
        raise SystemExit(f"wanted one U1, found {state['u1']}")
    u1 = state["u1"][0]
    if u1["sid"] == NEW_LCSC:
        raise SystemExit("U1 is already C179171")
    if (u1["sid"], u1["mid"], u1["x"], u1["y"], u1["unique"]) != (
            OLD_LCSC, "W25Q64JVXGIQ", 145, 610, "gge2"):
        raise SystemExit(f"unexpected old U1: {u1}")
    if len(state["epWire"]) != 1 or state["epWire"][0]["net"] != "GND":
        raise SystemExit(f"unexpected XSON EP wire: {state['epWire']}")
    if len(state["epFlag"]) != 1 or (state["epFlag"][0]["x"],
                                      state["epFlag"][0]["y"]) != (240, 630):
        raise SystemExit(f"unexpected XSON EP flag: {state['epFlag']}")
    print(f"old U1 {u1['sid']} at ({u1['x']}, {u1['y']}); "
          f"{len(state['stale'])} stale C179171 test placements")
    return u1


def backup_source():
    source = execute("return await eda.sys_FileManager.getDocumentSource();", 120)
    if not source:
        raise SystemExit("schematic source empty before migration")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "schematic-before-c179171.txt")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(source)
        print(f"wrote {path}")


def apply(old, stale):
    js = f"""
    const oldId = {json.dumps(old['id'])};
    const stale = {json.dumps([c['id'] for c in stale])};
    const device = {{libraryUuid:{json.dumps(PROJECT_UUID)},
                     uuid:{json.dumps(DEVICE_UUID)}}};
    const made = await eda.sch_PrimitiveComponent.create(
      device, {NEW_ORIGIN[0]}, {NEW_ORIGIN[1]}, "", 0, false, true, true);
    if (!made) throw new Error("C179171 create returned nothing");
    const newId = made.primitiveId || made;
    const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(newId);
    const measured = (pins||[]).map(p=>[p.pinNumber,p.pinName,p.x,p.y]);
    const expected = {json.dumps({n: v[:3] for n, v in EXPECTED_PINS.items()})};
    const bad = measured.filter(p => !expected[p[0]] ||
      expected[p[0]][0]!==p[1] || expected[p[0]][1]!==p[2] ||
      expected[p[0]][2]!==p[3]);
    if (measured.length!==8 || bad.length) {{
      await eda.sch_PrimitiveComponent.delete([newId]);
      throw new Error("new symbol pin geometry mismatch: "+JSON.stringify(measured));
    }}
    await eda.sch_PrimitiveComponent.delete([oldId]);
    if (stale.length) await eda.sch_PrimitiveComponent.delete(stale);
    await eda.sch_PrimitiveWire.delete([{json.dumps(EP_WIRE_ID)}]);
    await eda.sch_PrimitiveComponent.delete([{json.dumps(EP_FLAG_ID)}]);
    await eda.sch_PrimitiveComponent.modify(newId, {{
      designator:"U1", uniqueId:"gge2", supplier:"LCSC",
      supplierId:{json.dumps(NEW_LCSC)}, manufacturer:"Winbond(华邦)",
      manufacturerId:{json.dumps(NEW_MPN)}}});
    if (!await eda.sch_Document.save()) throw new Error("schematic save failed");
    return {{newId, measured, removedStale:stale.length}};
    """
    return execute(js, 180)


def point_on_segment(x, y, ax, ay, bx, by):
    cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
    if abs(cross) > 1e-9:
        return False
    return (min(ax, bx) <= x <= max(ax, bx)
            and min(ay, by) <= y <= max(ay, by))


def verify():
    state = live_state()
    if state["stale"] or state["epWire"] or state["epFlag"]:
        raise SystemExit(f"migration debris remains: {state}")
    if len(state["u1"]) != 1:
        raise SystemExit(f"wanted one U1 after migration: {state['u1']}")
    u1 = state["u1"][0]
    if (u1["sid"], u1["mid"], u1["x"], u1["y"], u1["unique"]) != (
            NEW_LCSC, NEW_MPN, *NEW_ORIGIN, "gge2"):
        raise SystemExit(f"wrong replacement identity: {u1}")
    if u1["footprint"] != "SOIC-8_L5.3-W5.3-P1.27-LS8.0-BL":
        raise SystemExit(f"wrong replacement footprint: {u1['footprint']}")

    wires = execute("""
      const ws=await eda.sch_PrimitiveWire.getAll();
      return (ws||[]).map(w=>({net:w.net,line:w.line}));
    """, 120)
    pins = {str(n): (name, x, y) for n, name, x, y in u1["pins"]}
    bad = {}
    for number, (name, x, y, net) in EXPECTED_PINS.items():
        if pins.get(number) != (name, x, y):
            bad[number] = {"pin": pins.get(number), "want": (name, x, y)}
            continue
        touching = []
        for wire in wires:
            flat = []
            stack = [wire.get("line")]
            while stack:
                value = stack.pop()
                if isinstance(value, list):
                    stack.extend(reversed(value))
                elif isinstance(value, (int, float)):
                    flat.append(value)
            for i in range(0, len(flat) - 3, 2):
                if point_on_segment(x, y, *flat[i:i + 4]):
                    touching.append(wire.get("net"))
        if net not in touching:
            bad[number] = {"nets": touching, "want": net}
    if bad:
        raise SystemExit(f"replacement pins not connected: {bad}")
    print(f"verified {NEW_LCSC} {NEW_MPN}; 8/8 pins touch expected nets")
    return state


def main():
    state = live_state()
    old = validate_before(state)
    print(f"plan: C179171 at {NEW_ORIGIN}; remove XSON EP and stale test parts")
    if "--apply" not in sys.argv[1:]:
        print("report only; pass --apply to persist")
        return
    backup_source()
    result = apply(old, state["stale"])
    print(f"placed {result['newId']}; removed {result['removedStale']} stale parts")
    verify()


if __name__ == "__main__":
    main()
