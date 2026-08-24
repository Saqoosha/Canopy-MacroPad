"""Replace PCB U1 with the C179171 SOIC-8 footprint.

The replacement is created and its eight pads are validated before the
old XSON component is deleted.  Pad nets and the schematic unique ID are
assigned explicitly so the PCB remains associated with schematic U1.

    python3 replace_flash_pcb.py            # report only
    python3 replace_flash_pcb.py --apply    # replace and verify
"""

import json
import sys

import build
from bridge import execute


LIBRARY_UUID = "0819f05c4eef4c71ace90d822a990e87"
DEVICE_UUID = "8dc2219f4e1a4d1597513c6c28c126c4"
OLD_LCSC = "C2940195"
NEW_LCSC = "C179171"
NEW_MPN = "W25Q64JVSSIQ"
FOOTPRINT = "SOIC-8_L5.3-W5.3-P1.27-LS8.0-BL"
BOTTOM = 2
TARGET = (4688.976, 165.354, 90)

PAD_NETS = {
    "1": "QSPI_SS",
    "2": "QSPI_SD1",
    "3": "QSPI_SD2",
    "4": "GND",
    "5": "QSPI_SD0",
    "6": "QSPI_SCLK",
    "7": "QSPI_SD3",
    "8": "3V3",
}


def state():
    build.open_project_pcb()
    js = """
    const cs=await eda.pcb_PrimitiveComponent.getAll();
    const out=[];
    for(const c of cs||[]) {
      if(c.designator!=="U1" && c.supplierId!=="C179171") continue;
      const ps=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(
        c.primitiveId);
      out.push({id:c.primitiveId,des:c.designator,sid:c.supplierId,
        mid:c.manufacturerId,x:c.x,y:c.y,rot:c.rotation,layer:c.layer,
        unique:c.uniqueId,fp:c.footprint&&c.footprint.name,
        pads:(ps||[]).map(p=>({id:p.primitiveId,n:String(p.padNumber),
          x:p.x,y:p.y,net:p.net,layer:p.layer,pad:p.pad}))});
    }
    return {count:(cs||[]).length,parts:out};
    """
    return execute(js, 120)


def old_u1(data):
    found = [c for c in data["parts"] if c["des"] == "U1"]
    if len(found) != 1:
        raise SystemExit(f"wanted one PCB U1, found {found}")
    old = found[0]
    if old["sid"] == NEW_LCSC:
        raise SystemExit("PCB U1 is already C179171")
    if (old["sid"], old["mid"], old["unique"], old["fp"]) != (
            OLD_LCSC, "W25Q64JVXGIQ", "gge2",
            "XSON-8_L4.0-W4.0-P0.80-TL-EP"):
        raise SystemExit(f"unexpected old PCB U1: {old}")
    stale = [c for c in data["parts"] if c["des"] != "U1"]
    print(f"old PCB U1 {old['sid']} {old['fp']} at "
          f"({old['x']:.3f}, {old['y']:.3f}); stale={len(stale)}")
    return old, stale


def apply(old, stale):
    js = f"""
    const before=await eda.pcb_PrimitivePad.getAll();
    const known=new Set((before||[]).map(p=>p.primitiveId));
    const dev={{libraryUuid:{json.dumps(LIBRARY_UUID)},
               uuid:{json.dumps(DEVICE_UUID)}}};
    const c=await eda.pcb_PrimitiveComponent.create(dev,{BOTTOM},
      {TARGET[0]},{TARGET[1]},{TARGET[2]},false);
    if(!c) throw new Error("C179171 PCB create returned nothing");
    const id=c.primitiveId||c;
    const pins=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(id);
    const numbers=(pins||[]).map(p=>String(p.padNumber)).sort();
    if(JSON.stringify(numbers)!==JSON.stringify(["1","2","3","4","5","6","7","8"])) {{
      await eda.pcb_PrimitiveComponent.delete([id]);
      throw new Error("replacement pad set mismatch: "+JSON.stringify(numbers));
    }}
    const nets={json.dumps(PAD_NETS)};
    for(const p of pins) {{
      const num=String(p.padNumber);
      const got=await eda.pcb_PrimitivePad.modify(p.primitiveId,{{net:nets[num]}});
      if(!got) throw new Error("pad net failed "+num);
    }}
    await eda.pcb_PrimitiveComponent.delete([{json.dumps(old['id'])}]);
    const stale={json.dumps([c['id'] for c in stale])};
    if(stale.length) await eda.pcb_PrimitiveComponent.delete(stale);
    const modified=await eda.pcb_PrimitiveComponent.modify(id,{{
      designator:"U1",uniqueId:"gge2"}});
    if(!modified) throw new Error("replacement identity modify failed");
    if(!await eda.pcb_Document.save()) throw new Error("PCB save failed");
    const after=await eda.pcb_PrimitivePad.getAll();
    const fresh=(after||[]).filter(p=>!known.has(p.primitiveId));
    return {{id,removedStale:stale.length,pads:(pins||[]).map(p=>({{
      n:String(p.padNumber),x:p.x,y:p.y,net:p.net,pad:p.pad}})),
      freshPads:fresh.length}};
    """
    return execute(js, 180)


def verify(data):
    parts = [c for c in data["parts"] if c["des"] == "U1"]
    if len(parts) != 1:
        raise SystemExit(f"wanted one replacement U1: {data['parts']}")
    u1 = parts[0]
    if (u1["sid"], u1["mid"], u1["unique"], u1["fp"], u1["layer"]) != (
            NEW_LCSC, NEW_MPN, "gge2", FOOTPRINT, BOTTOM):
        raise SystemExit(f"wrong replacement PCB identity: {u1}")
    pads = {p["n"]: p for p in u1["pads"]}
    if set(pads) != set(PAD_NETS):
        raise SystemExit(f"wrong replacement pad set: {sorted(pads)}")
    bad = {number: (pads[number]["net"], net)
           for number, net in PAD_NETS.items()
           if pads[number]["net"] != net}
    if bad:
        raise SystemExit(f"replacement PCB pad nets wrong: {bad}")
    stale = [c for c in data["parts"] if c["des"] != "U1"]
    if stale:
        raise SystemExit(f"stale C179171 PCB parts remain: {stale}")
    print(f"verified PCB {NEW_LCSC} {FOOTPRINT}; 8/8 pad nets")
    return u1


def main():
    before = state()
    old, stale = old_u1(before)
    print(f"plan: replace at {TARGET[:2]} mil r{TARGET[2]}")
    if "--apply" not in sys.argv[1:]:
        print("report only; pass --apply to persist")
        return
    result = apply(old, stale)
    print(f"placed {result['id']}; removed {result['removedStale']} stale parts")
    verify(state())


if __name__ == "__main__":
    main()
