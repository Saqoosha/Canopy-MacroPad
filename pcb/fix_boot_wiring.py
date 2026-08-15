"""Move SW1 off the wire it landed on, and rewire it so no pin can be wrong.

WHAT HAPPENED. swap_boot.py replaced the BOOT switch with a smaller one at
the same origin and drew a stub to each of the two connected pins. It then
checked those two pins and reported success. The new symbol is 50 units
wide where the old one was 40, and its pin 3 came down at (225, 690) --
which is a point in the middle of an existing BOOT wire running from
(350, 690) to (180, 690). Touching a wire connects to it. Pin 3 joined
BOOT silently, and the board came back with pad 3 on BOOT.

WHY THAT IS FATAL. A four-pin tact has two pins per pole, shorted inside
the part. Pad 3 shares a pole with pad 2, which is GND. BOOT is the
RP2040's QSPI_SS: held low at boot, the chip enters the USB bootloader
every time and never runs the firmware. It would have assembled, enumerated
as a mass-storage device, and never worked -- with nothing in DRC, nothing
in the netlist and nothing in any render to say why.

THE CHECK THAT MISSED IT verified the two pins it had wired. The two it
had not wired were the ones that went wrong. So the rule this file follows
is: after touching a component, assert the net on EVERY pin, including
"nothing" for the ones that are meant to be floating.

THE WIRING, chosen so no datasheet is needed. The library does not say
which pins pair, and the footprint name's `-P1.80-LS3.4-` implies the two
pads at the same x are one pole -- implies, from a naming convention, which
is the kind of borrowed sentence this project has been burnt by before.
Pins 1 and 2 sit at the same y and different x, so they are on different
poles under BOTH readings, the side one and the diagonal one. Wiring only
those two and leaving 3 and 4 genuinely floating is correct without
knowing. It costs the redundant second contact per pole, which the
outgoing switch did not have either.

    python3 fix_boot_wiring.py            report
    python3 fix_boot_wiring.py --apply    move it and rewire
"""

import json
import sys

import schematic as sch
from bridge import execute

# Clear of every wire in the region: the nearest are the GND flag at
# (235, 710), R1 at (330, 650) and the DVDD rail at y 700.
NEW_ORIGIN = (200, 800)

# Pin offsets of the TS263065A symbol, measured by placing one.
PIN_OFFSET = {"1": (-25, 10), "2": (25, 10), "3": (25, -10), "4": (-25, -10)}

# Both routes leave the anchor sideways before turning, so that neither
# runs down a column occupied by pins 3 and 4. A stub that reaches its own
# pin by passing through another pin is how this went wrong the first time.
ROUTES = [
    ("BOOT", [175, 710, 150, 710, 150, 810, 175, 810]),
    ("GND",  [235, 710, 270, 710, 270, 810, 225, 810]),
]

WANT = {"1": "BOOT", "2": "GND", "3": None, "4": None}


def pin_state():
    """Every SW1 pin: number, position, and the nets whose wires touch it."""
    js = """
    const cs = await eda.sch_PrimitiveComponent.getAll();
    const sw = (cs||[]).find(c => c.designator === "SW1");
    if (!sw) return {err: "no SW1"};
    const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(
      sw.primitiveId);
    const ws = await eda.sch_PrimitiveWire.getAll();
    const ends = [];
    for (const w of ws||[]) {
      const n = [];
      const walk = v => { if (Array.isArray(v)) v.forEach(walk);
                          else if (typeof v === "number") n.push(v); };
      walk(w.line||[]);
      for (let i = 0; i + 3 < n.length; i += 4)
        ends.push({net: w.net || "-", x1: n[i], y1: n[i+1],
                   x2: n[i+2], y2: n[i+3]});
    }
    const on = (s, x, y) => {
      const dx = s.x2 - s.x1, dy = s.y2 - s.y1;
      const cross = (x - s.x1) * dy - (y - s.y1) * dx;
      if (cross !== 0) return false;
      const dot = (x - s.x1) * dx + (y - s.y1) * dy;
      return dot >= 0 && dot <= dx * dx + dy * dy;
    };
    return {id: sw.primitiveId, x: sw.x, y: sw.y,
      pins: (pins||[]).map(p => [p.pinNumber, p.x, p.y,
        Array.from(new Set(ends.filter(s => on(s, p.x, p.y))
                               .map(s => s.net))).sort()])};
    """
    got = execute(js)
    if got.get("err"):
        raise SystemExit(got["err"])
    return got


def show(state, label):
    print(f"  {label}: SW1 at ({state['x']}, {state['y']})")
    for num, x, y, nets in sorted(state["pins"], key=lambda p: int(p[0])):
        want = WANT.get(str(num))
        got = ",".join(nets) if nets else "nothing"
        ok = (want in nets) if want else (not nets)
        print(f"    pin {num} ({x:4}, {y:4})  {got:14}"
              f"{'' if ok else '   <-- WRONG, wanted ' + (want or 'nothing')}")


def wrong(state):
    bad = {}
    for num, x, y, nets in state["pins"]:
        n = str(num)
        want = WANT.get(n)
        if want and want not in nets:
            bad[n] = f"wanted {want}, has {nets or 'nothing'}"
        elif not want and nets:
            bad[n] = f"must float, is on {nets}"
    return bad


def apply(state):
    js = """
    const id = %s;
    const routes = %s;
    await eda.sch_PrimitiveComponent.modify(id, {x: %d, y: %d});
    let made = 0;
    for (const r of routes) {
      const w = await eda.sch_PrimitiveWire.create(r.line, r.net);
      if (w) made += 1;
    }
    return {routes: made};
    """ % (json.dumps(state["id"]),
           json.dumps([{"net": n, "line": l} for n, l in ROUTES]),
           NEW_ORIGIN[0], NEW_ORIGIN[1])
    got = execute(js, timeout=180.0)
    print(f"  moved to {NEW_ORIGIN}, drew {got['routes']}/{len(ROUTES)} routes")


def main():
    sch.open_project_schematic()
    before = pin_state()
    print("\nbefore:")
    show(before, "as found")
    bad = wrong(before)
    if not bad:
        raise SystemExit("SW1 is already wired correctly -- nothing to do")
    print(f"  {len(bad)} pin(s) wrong: {bad}")

    if "--apply" not in sys.argv:
        print("\n(report only -- pass --apply to fix it)")
        return

    print("\napply:")
    apply(before)

    print("\nafter:")
    after = pin_state()
    show(after, "now")
    bad = wrong(after)
    if bad:
        raise SystemExit(f"still wrong: {bad}")
    for num, x, y, nets in after["pins"]:
        if PIN_OFFSET[str(num)] != (x - NEW_ORIGIN[0], y - NEW_ORIGIN[1]):
            raise SystemExit(f"pin {num} is not where the symbol puts it")
    print("\n  every pin checked, including the two that must float")


if __name__ == "__main__":
    main()
