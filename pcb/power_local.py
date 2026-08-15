"""Reserve U3.22's local 3V3 decoupling connection before signals."""

import json
import sys

import audit
import geom
import stitch
from bridge import execute

MIL = 0.0254
WIDTH_MM = 0.15


def plan(data):
    owned, _ = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    pads = {f"{by_id[cid]['des']}.{p['num']}": p
            for cid, ps in owned.items() for p in ps}
    a, b = pads["C8.1"], pads["U3.22"]
    if a["net"] != "3V3" or b["net"] != "3V3":
        raise SystemExit("C8.1/U3.22 are no longer both 3V3")
    poly = geom.segment(a["x"], a["y"], b["x"], b["y"], WIDTH_MM / MIL)
    if not stitch._clear(poly, stitch._obstacles(data), "3V3",
                         stitch.CLEAR_MM / MIL):
        raise SystemExit("C8.1-U3.22 local decoupling segment is blocked")
    return {"net": "3V3", "layer": 2, "x1": a["x"], "y1": a["y"],
            "x2": b["x"], "y2": b["y"], "w": WIDTH_MM / MIL}


def main():
    import build
    build.open_project_pcb()
    item = plan(audit._fetch())
    print(f"\nplan:\n  C8.1 -> U3.22  {WIDTH_MM:.2f} mm")
    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to draw it)")
        return
    js = """
    const it = %s;
    return !!(await eda.pcb_PrimitiveLine.create(
      it.net, it.layer, it.x1, it.y1, it.x2, it.y2, it.w, false));
    """ % json.dumps(item)
    if execute(js) is not True:
        raise SystemExit("local decoupling trace was not created")
    findings = audit.findings(audit._fetch())
    if findings:
        raise SystemExit(f"local decoupling trace caused {len(findings)} overlaps")
    print("\napply:\n  1/1 local trace\n  no overlaps")


if __name__ == "__main__":
    main()
