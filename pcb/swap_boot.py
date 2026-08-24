"""Replace the BOOT switch with a much smaller one.

Same shape of operation as swap_flash.py, and the same care: the device
cannot be changed in place, so the old one is deleted and a new one built
at the same origin with short stubs to the wires that are already there.

Why this part. Three candidates were measured rather than chosen:

    TS-1187A   (current)  5.1 x 5.1 = 26.0 mm^2   1.5 mm tall   1.6 N
    TS263065A            3.0 x 2.6 =  7.8 mm^2   0.65 mm tall  3.4 N
    SKRPACE010           4.2 x 3.2 = 13.4 mm^2   2.5 mm tall

All three fit the 3.30 mm the case leaves under the board (SOCKET_DROP
1.90 + UNDER_BOARD_AIR 1.40), so height did not eliminate anything --
TS263065A simply wins on both axes. 3.4 N is stiff for a fingertip and
this is a BOOT button: on a blank flash the RP2040 enters the USB
bootloader by itself, so the button exists only for reflashing a board
that already works, with the case open, twice in its life.

THE THING THAT COULD HAVE BRICKED IT. A four-pin tact has two pins per
pole, shorted inside the part. Wire BOOT and GND to the same pole and
QSPI_SS is tied low forever: the board comes up in the bootloader every
time and never runs. Nothing in the library says which pins pair -- the
symbol calls them 1, 2, 3, 4 and the description says only "SPST".

It was settled by measuring the footprints instead. In the name
`...-P1.80-LS3.4-`, P is the spacing of the two pads on one side and LS is
the span across, so the pole direction is whichever axis matches LS:

    TS-1187A   pads 1,3 at x -3.0 and 2,4 at x +3.0   (LS6.5 -> x)
    TS263065A  pads 1,4 at x -1.5 and 2,3 at x +1.5   (LS3.4 -> x)

Pins 1 and 2 are on opposite sides in both, and the live board wires
1 = BOOT, 2 = GND. So the same two pin numbers stay correct. Pins 3 and 4
are left floating exactly as they are now.

    python3 swap_boot.py            report what it would do
    python3 swap_boot.py --apply    do it, then check every pin
"""

import json
import sys

import schematic as sch
import snapshot
from bridge import execute

NEW = {
    "libraryUuid": None,     # filled from the library search
    "uuid": None,
    "name": "TS263065A 340gf SX BD SMD Tactile Switch",
    "lcsc": "C49023761",
    "footprint": "SW-SMD_4P-L3.0-W2.6-P1.80-LS3.4-TL",
}
OLD_LCSC = "C318884"
OLD_ORIGIN = (200, 700)

# New symbol pins are 50 units apart where the old one's are 40, so both
# connected pins land 5 units outboard of the wire that is waiting there.
NEW_ORIGIN = OLD_ORIGIN
STUBS = [
    ((175, 710), (180, 710), "BOOT"),
    ((225, 710), (220, 710), "GND"),
]
EXPECTED_NETS = {"1": "BOOT", "2": "GND"}
EXPECTED_PINS = {"1": (175, 710), "2": (225, 710),
                 "3": (225, 690), "4": (175, 690)}


def find_device():
    js = """
    const sys = await eda.lib_LibrariesList.getSystemLibraryUuid();
    const r = await eda.lib_Device.search("TS263065A", sys, undefined,
                                          undefined, 40, 1);
    const d = (Array.isArray(r) ? r : []).find(x => x.supplierId === %s);
    if (!d) return {err: "device not in the library"};
    return {uuid: d.uuid, lib: d.libraryUuid, name: d.name,
            fp: d.footprintName, mfr: d.manufacturer, mfrId: d.manufacturerId};
    """ % json.dumps(NEW["lcsc"])
    got = execute(js)
    if got.get("err"):
        raise SystemExit(got["err"])
    if got["fp"] != NEW["footprint"]:
        raise SystemExit(f"library gives footprint {got['fp']}, not the "
                         f"{NEW['footprint']} this file measured")
    NEW["uuid"], NEW["libraryUuid"] = got["uuid"], got["lib"]
    NEW["mfr"], NEW["mfrId"] = got.get("mfr") or "", got.get("mfrId") or ""
    return got


def _state():
    js = """
    const cs = await eda.sch_PrimitiveComponent.getAll();
    const sw = (cs||[]).find(c => c.designator === "SW1");
    if (!sw) return {err: "no SW1 on the schematic"};
    return {id: sw.primitiveId, x: sw.x, y: sw.y, rot: sw.rotation,
            unique: sw.uniqueId, supId: sw.supplierId, mfrId: sw.manufacturerId};
    """
    got = execute(js)
    if got.get("err"):
        raise SystemExit(got["err"])
    return got


def check_pins():
    """SW1 pins whose expected net does not end on them."""
    js = """
    const cs = await eda.sch_PrimitiveComponent.getAll();
    const sw = (cs||[]).find(c => c.designator === "SW1");
    const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(
      sw.primitiveId);
    const ws = await eda.sch_PrimitiveWire.getAll();
    const ends = [];
    for (const w of ws||[]) {
      const nums = [];
      const walk = v => { if (Array.isArray(v)) v.forEach(walk);
                          else if (typeof v === "number") nums.push(v); };
      walk(w.line||[]);
      for (let i = 0; i < nums.length; i += 2)
        ends.push({x: nums[i], y: nums[i+1], net: w.net});
    }
    return (pins||[]).map(p => [p.pinNumber, p.x, p.y,
      ends.filter(e => e.x === p.x && e.y === p.y).map(e => e.net || "-")]);
    """
    bad = {}
    for num, x, y, nets in execute(js):
        n = str(num)
        if EXPECTED_PINS.get(n) != (x, y):
            bad[n] = f"landed at ({x}, {y}), expected {EXPECTED_PINS.get(n)}"
        elif n in EXPECTED_NETS and EXPECTED_NETS[n] not in nets:
            bad[n] = f"wanted {EXPECTED_NETS[n]}, found {nets or 'nothing'}"
    return bad


def report(sw):
    print(f"  SW1 is {sw['mfrId']} ({sw['supId']}) at ({sw['x']}, {sw['y']})")
    if sw["supId"] == NEW["lcsc"]:
        raise SystemExit("SW1 is already the small part -- nothing to do")
    if sw["supId"] != OLD_LCSC:
        raise SystemExit(f"SW1 is {sw['supId']}, not the {OLD_LCSC} this "
                         f"script measured its pin pairing against.")
    if (sw["x"], sw["y"]) != OLD_ORIGIN:
        raise SystemExit(f"SW1 has moved to ({sw['x']}, {sw['y']}); the stub "
                         f"coordinates were derived from {OLD_ORIGIN}.")
    print(f"  -> {NEW['lcsc']} {NEW['footprint']}")
    print(f"  26.0 mm2 and 1.5 mm tall -> 7.8 mm2 and 0.65 mm")
    print(f"  pins 1=BOOT 2=GND keep their numbers; {len(STUBS)} stubs")


def apply(sw):
    js = """
    const oldId = %s;
    const dev = {libraryUuid: %s, uuid: %s};
    const stubs = %s;
    await eda.sch_PrimitiveComponent.delete([oldId]);
    const c = await eda.sch_PrimitiveComponent.create(
      dev, %d, %d, "", 0, false, true, true);
    if (!c) return {err: "create returned nothing -- SW1 is now DELETED"};
    const id = c.primitiveId || c;
    await eda.sch_PrimitiveComponent.modify(id, {
      designator: "SW1", uniqueId: %s,
      supplier: "LCSC", supplierId: %s,
      manufacturer: %s, manufacturerId: %s});
    let made = 0;
    for (const s of stubs) {
      const w = await eda.sch_PrimitiveWire.create(
        [s.x1, s.y1, s.x2, s.y2], s.net);
      if (w) made += 1;
    }
    return {newId: id, stubs: made};
    """ % (
        json.dumps(sw["id"]), json.dumps(NEW["libraryUuid"]),
        json.dumps(NEW["uuid"]),
        json.dumps([{"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1], "net": n}
                    for a, b, n in STUBS]),
        NEW_ORIGIN[0], NEW_ORIGIN[1],
        json.dumps(sw["unique"]), json.dumps(NEW["lcsc"]),
        json.dumps(NEW["mfr"]), json.dumps(NEW["mfrId"]),
    )
    got = execute(js, timeout=180.0)
    if got.get("err"):
        raise SystemExit(got["err"])
    print(f"  placed {NEW['lcsc']}, {got['stubs']}/{len(STUBS)} stubs")


def main():
    sch.open_project_schematic()
    find_device()
    before = snapshot.census(execute(snapshot.SCHEMATIC, timeout=120.0))
    sw = _state()
    print("\nplan:")
    report(sw)

    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to change the schematic)")
        return

    print("\napply:")
    apply(sw)

    print("\nverify:")
    bad = check_pins()
    if bad:
        raise SystemExit(f"pins wrong: {bad}")
    print("  pins 1-4 landed where planned; BOOT on 1 and GND on 2")
    after = snapshot.census(execute(snapshot.SCHEMATIC, timeout=120.0))
    lost = {n: (before["nets"][n], after["nets"].get(n, 0))
            for n in before["nets"] if after["nets"].get(n, 0) < before["nets"][n]}
    if lost:
        raise SystemExit(f"nets lost wires: {lost}")
    print(f"  wires {before['schWires']} -> {after['schWires']}, "
          f"components {before['schComponents']} -> {after['schComponents']}")
    print("\nswapped")


if __name__ == "__main__":
    main()
