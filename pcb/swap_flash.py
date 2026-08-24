"""Replace the SOIC-8 flash with the same die in an XSON-8 package.

Why: W25Q64JVSSIQ is a 5.3 x 5.3 mm body with a 9.29 mm pad span. The
pockets between adjacent keys are 11.8 mm wide and the RP2040 is 7.48, so
the two cannot share one and QSPI had to run ~19 mm across a key column.
W25Q64JVXGIQ is the same 64 Mbit Winbond part in a 4.0 x 4.0 mm package.

How, and this is the whole care of the thing: the two devices do NOT
share a symbol. The new one is narrower -- its pin rows are 110 units
apart where the old one's are 210 -- it is offset ten units in y, and it
has a ninth pin for the exposed pad. So every wire endpoint moves, and a
naive delete-and-replace would leave eight nets dangling in a schematic
whose damage is invisible until a board comes back unroutable.

The arrangement that makes it small: place the new symbol's origin at
(145, 610) rather than the old (200, 600), and pins 1-4 land exactly on
the four wire ends of the left side. Nothing on that side is touched at
all. The right side then lands uniformly 100 units -- one inch, one grid
step -- to the left of where its wires end, so four horizontal stubs
finish it. The exposed pad is the only genuinely new connection.

Idempotent by refusing: if U1 already carries the new part number it
stops rather than doing it twice.

    python3 swap_flash.py            report what it would do
    python3 swap_flash.py --apply    do it, then check the net census
"""

import json
import sys

import schematic as sch
import snapshot
from bridge import execute

NEW = {
    "libraryUuid": "0819f05c4eef4c71ace90d822a990e87",
    "uuid": "e1cca82e0a074b60b5a7e25ad5433b4e",
    "name": "W25Q64JVXGIQ",
    "lcsc": "C2940195",
    "mfr": "Winbond(华邦)",
    "footprint": "XSON-8_L4.0-W4.0-P0.80-TL-EP",
}
OLD_LCSC = "C2904572"

# Schematic units are 0.01 inch. The old symbol's origin, and the new
# origin chosen so the left-hand pins do not move.
OLD_ORIGIN = (200, 600)
NEW_ORIGIN = (145, 610)

# Pin -> the wire end it has to reach, in absolute schematic units. Only
# the right-hand pins need one; pins 1-4 already land on theirs.
STUBS = {
    "5": ((200, 590), (300, 590), "QSPI_SD0"),
    "6": ((200, 600), (300, 600), "QSPI_SCLK"),
    "7": ((200, 610), (300, 610), "QSPI_SD3"),
    "8": ((200, 620), (300, 620), "3V3"),
}
# The exposed pad. Winbond allows it floating; grounding it is better
# thermally and stops the PCB pad arriving with no net at all.
EP_PIN = "9"
EP_AT = (200, 630)
EP_FLAG_AT = (240, 630)


def _state():
    js = """
    const cs = await eda.sch_PrimitiveComponent.getAll();
    const u1 = (cs||[]).find(c => c.designator === "U1");
    if (!u1) return {err: "no U1 on the schematic"};
    const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(
      u1.primitiveId);
    return {id: u1.primitiveId, x: u1.x, y: u1.y, rot: u1.rotation,
            mirror: u1.mirror, unique: u1.uniqueId, supId: u1.supplierId,
            mfrId: u1.manufacturerId,
            pins: (pins||[]).map(p => [p.pinNumber, p.pinName, p.x, p.y])};
    """
    got = execute(js)
    if got.get("err"):
        raise SystemExit(got["err"])
    return got


def report(u1):
    print(f"  U1 is {u1['mfrId']} ({u1['supId']}) at "
          f"({u1['x']}, {u1['y']}) rot {u1['rot']}")
    if u1["supId"] == NEW["lcsc"]:
        raise SystemExit("U1 is already the XSON-8 part -- nothing to do")
    if u1["supId"] != OLD_LCSC:
        raise SystemExit(
            f"U1 is {u1['supId']}, not the {OLD_LCSC} this script was "
            f"written against. Re-derive the pin mapping before running it.")
    if (u1["x"], u1["y"]) != OLD_ORIGIN:
        raise SystemExit(
            f"U1 has moved to ({u1['x']}, {u1['y']}); NEW_ORIGIN was derived "
            f"from {OLD_ORIGIN} and is now wrong by the difference.")
    print(f"  -> {NEW['name']} ({NEW['lcsc']}) at {NEW_ORIGIN}, "
          f"{NEW['footprint']}")
    print(f"  left pins 1-4 keep their wires; {len(STUBS)} stubs on the "
          f"right; EP grounded")


def apply(u1):
    js = """
    const oldId = %s;
    const dev = %s;
    const stubs = %s;
    const out = {};
    await eda.sch_PrimitiveComponent.delete([oldId]);
    const c = await eda.sch_PrimitiveComponent.create(
      dev, %d, %d, "", 0, false, true, true);
    if (!c) return {err: "create returned nothing -- U1 is now DELETED"};
    const id = c.primitiveId || c;
    out.newId = id;
    await eda.sch_PrimitiveComponent.modify(id, {
      designator: "U1", uniqueId: %s,
      supplier: "LCSC", supplierId: %s,
      manufacturer: %s, manufacturerId: %s});
    const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(id);
    out.pins = (pins||[]).map(p => [p.pinNumber, p.x, p.y]);
    out.stubs = 0;
    for (const s of stubs) {
      const w = await eda.sch_PrimitiveWire.create(
        [s.x1, s.y1, s.x2, s.y2], s.net);
      if (w) out.stubs += 1;
    }
    const ep = await eda.sch_PrimitiveWire.create([%d, %d, %d, %d], "GND");
    out.epWire = !!ep;
    const flag = await eda.sch_PrimitiveComponent.createNetFlag(
      "Ground", "GND", %d, %d);
    out.epFlag = !!flag;
    return out;
    """ % (
        json.dumps(u1["id"]), json.dumps(NEW),
        json.dumps([{"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1], "net": n}
                    for a, b, n in STUBS.values()]),
        NEW_ORIGIN[0], NEW_ORIGIN[1],
        json.dumps(u1["unique"]), json.dumps(NEW["lcsc"]),
        json.dumps(NEW["mfr"]), json.dumps(NEW["name"]),
        EP_AT[0], EP_AT[1], EP_FLAG_AT[0], EP_FLAG_AT[1],
        EP_FLAG_AT[0], EP_FLAG_AT[1],
    )
    got = execute(js, timeout=180.0)
    if got.get("err"):
        raise SystemExit(got["err"])
    print(f"  placed {NEW['name']}, {got['stubs']}/{len(STUBS)} stubs, "
          f"EP wire {got['epWire']}, EP flag {got['epFlag']}")

    # The pins have to have landed where the arrangement says, or the
    # stubs just drawn connect to empty space and the schematic is wrong
    # in a way that only shows up as a net that has quietly lost a member.
    want = {"1": (90, 620), "2": (90, 610), "3": (90, 600), "4": (90, 590),
            "5": (200, 590), "6": (200, 600), "7": (200, 610),
            "8": (200, 620), EP_PIN: EP_AT}
    landed = {str(n): (x, y) for n, x, y in got["pins"]}
    bad = {n: (landed.get(n), w) for n, w in want.items()
           if landed.get(n) != w}
    if bad:
        raise SystemExit(f"pins did not land where planned: {bad}")
    print(f"  all {len(want)} pins landed on their wire ends")
    if got["stubs"] != len(STUBS) or not got["epWire"] or not got["epFlag"]:
        raise SystemExit("some wiring was not created")


EXPECTED_NETS = {
    "1": "QSPI_SS", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": "GND",
    "5": "QSPI_SD0", "6": "QSPI_SCLK", "7": "QSPI_SD3", "8": "3V3",
    "9": "GND",
}


def check_pins():
    """Pins of U1 with no wire of the expected net ending on them."""
    js = """
    const cs = await eda.sch_PrimitiveComponent.getAll();
    const u1 = (cs||[]).find(c => c.designator === "U1");
    const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(
      u1.primitiveId);
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
    return (pins||[]).map(p => [p.pinNumber,
      ends.filter(e => e.x === p.x && e.y === p.y).map(e => e.net || "-")]);
    """
    bad = {}
    for num, nets in execute(js):
        want = EXPECTED_NETS.get(str(num))
        if want and want not in nets:
            bad[str(num)] = f"wanted {want}, found {nets or 'nothing'}"
    return bad


def main():
    sch.open_project_schematic()
    before = snapshot.census(execute(snapshot.SCHEMATIC, timeout=120.0))
    u1 = _state()
    print("\nplan:")
    report(u1)

    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to change the schematic)")
        return

    print("\napply:")
    apply(u1)

    print("\nverify:")
    after = snapshot.census(execute(snapshot.SCHEMATIC, timeout=120.0))
    # Every net that existed must still exist, with at least as many wires:
    # the swap adds five and removes none.
    lost = {n: (before["nets"][n], after["nets"].get(n, 0))
            for n in before["nets"] if after["nets"].get(n, 0)
            < before["nets"][n]}
    if lost:
        raise SystemExit(f"nets lost wires: {lost}")
    # Counting wires proves nothing here. A stub drawn onto the end of an
    # existing wire of the same net is MERGED into it, so four stubs plus
    # one new GND segment showed up as +1 -- which reads like four
    # failures and was four successes. What settles it is asking each pin
    # whether a wire of the right net ends on it.
    dangling = check_pins()
    if dangling:
        raise SystemExit(f"pins with no wire on them: {dangling}")
    print(f"  all 9 pins carry a wire (stubs merge into the wire they "
          f"meet, so the wire count moves by less than the stubs drawn)")
    gained = sum(after["nets"].values()) - sum(before["nets"].values())
    print(f"  wires {before['schWires']} -> {after['schWires']} (+{gained})")
    print(f"  components {before['schComponents']} -> "
          f"{after['schComponents']} (net flag added)")
    for n in sorted(set(before["nets"]) | set(after["nets"])):
        a, b = before["nets"].get(n, 0), after["nets"].get(n, 0)
        if a != b:
            print(f"    {n:12} {a} -> {b}")
    print("\nswapped")


if __name__ == "__main__":
    main()
