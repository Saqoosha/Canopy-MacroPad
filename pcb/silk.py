"""Keep the four crowded lower-edge designators on the board.

Component movement preserves a library label's large, historical offset.
That put SW1 and U1 below y=0 and left R1/C14 touching the edge. These are
absolute board positions because the four parts have a deliberate placement
block and the labels describe that block, not a reusable footprint.
"""

import json
import sys

import params
from bridge import execute

MIL = 0.0254
BOTTOM_SILK = 4
CENTER = 5

TARGETS_MM = {
    "U1": (116.30, 1.15),
    "C14": (123.00, 1.15),
    "R1": (127.80, 1.15),
    "SW1": (132.00, 1.15),
}


def state():
    js = """
    const wanted = %s;
    const cs = await eda.pcb_PrimitiveComponent.getAll();
    const out = [];
    for (const c of cs || []) {
      if (!wanted.includes(c.designator)) continue;
      const attrs = await eda.pcb_PrimitiveAttribute.getAll(c.primitiveId);
      const a = (attrs || []).find(v => v.key === "Designator");
      out.push({
        des: c.designator,
        component: [c.x, c.y],
        attr: a && {id: a.primitiveId, x: a.x, y: a.y, layer: a.layer,
                    value: a.value, fontSize: a.fontSize,
                    valueVisible: a.valueVisible, alignMode: a.alignMode},
      });
    }
    return out;
    """ % json.dumps(sorted(TARGETS_MM))
    return execute(js)


def verify():
    got = {x["des"]: x for x in state()}
    missing = sorted(set(TARGETS_MM) - set(got))
    if missing:
        raise SystemExit(f"missing components for silk labels: {missing}")
    for des, (x_mm, y_mm) in TARGETS_MM.items():
        a = got[des].get("attr")
        if not a:
            raise SystemExit(f"{des} has no Designator attribute")
        if a["layer"] != BOTTOM_SILK or not a["valueVisible"]:
            raise SystemExit(f"{des} designator is not visible on bottom silk")
        if abs(a["x"] * MIL - x_mm) > 0.01 or abs(a["y"] * MIL - y_mm) > 0.01:
            raise SystemExit(
                f"{des} label at ({a['x']*MIL:.2f},{a['y']*MIL:.2f}), "
                f"wanted ({x_mm:.2f},{y_mm:.2f})"
            )
        # Conservative text bounds: 0.8 font-height per character wide.
        half_w = len(a["value"]) * a["fontSize"] * 0.4
        half_h = a["fontSize"] * 0.55
        if (a["x"] - half_w < 0 or a["x"] + half_w > params.BOARD_W / MIL
                or a["y"] - half_h < 0
                or a["y"] + half_h > params.BOARD_D / MIL):
            raise SystemExit(f"{des} silk text bounds cross the board edge")
        print(f"  {des:4} label ({a['x']*MIL:.2f}, {a['y']*MIL:.2f}) mm")
    return got


def apply():
    targets = {k: [x / MIL, y / MIL] for k, (x, y) in TARGETS_MM.items()}
    js = """
    const targets = %s;
    const cs = await eda.pcb_PrimitiveComponent.getAll();
    let moved = 0;
    for (const c of cs || []) {
      const xy = targets[c.designator];
      if (!xy) continue;
      const attrs = await eda.pcb_PrimitiveAttribute.getAll(c.primitiveId);
      const a = (attrs || []).find(v => v.key === "Designator");
      if (!a) continue;
      const r = await eda.pcb_PrimitiveAttribute.modify(a.primitiveId, {
        x: xy[0], y: xy[1], layer: 4, alignMode: 5,
        rotation: 180, valueVisible: true,
      });
      if (r) moved += 1;
    }
    return {asked: Object.keys(targets).length, moved};
    """ % json.dumps(targets)
    got = execute(js, timeout=120.0)
    if got["moved"] != got["asked"]:
        raise SystemExit(f"moved {got['moved']} of {got['asked']} silk labels")
    print(f"  moved {got['moved']} designators onto the board")
    return verify()


def main():
    import build

    build.open_project_pcb()
    if "--apply" in sys.argv:
        apply()
    else:
        verify()


if __name__ == "__main__":
    main()
