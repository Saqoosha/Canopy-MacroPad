"""Reserve a continuous Top-layer 3V3 backbone on the two-layer board.

The Top 3V3 pour widens this rail wherever signal copper leaves room. The
explicit rail is still required: a pour split into two pad-connected regions
can look healthy while the regions are electrically separate.
"""

import sys

import audit
import params
from bridge import execute

MIL = 0.0254
TOP = 1
NET = "3V3"
WIDTH_MM = 0.30
Y_MM = 1.00
END_INSET_MM = params.BOARD_CORNER_RADIUS + 0.50


def item():
    return {
        "net": NET,
        "layer": TOP,
        "x1": END_INSET_MM / MIL,
        "y1": Y_MM / MIL,
        "x2": (params.BOARD_W - END_INSET_MM) / MIL,
        "y2": Y_MM / MIL,
        "w": WIDTH_MM / MIL,
    }


def main():
    import build

    build.open_project_pcb()
    rail = item()
    print(
        f"  Top {NET} rail: x {END_INSET_MM:.2f}.."
        f"{params.BOARD_W - END_INSET_MM:.2f} mm, y {Y_MM:.2f} mm, "
        f"width {WIDTH_MM:.2f} mm"
    )
    if "--apply" not in sys.argv:
        print("  plan only -- pass --apply")
        return
    js = """
    const r=%s;
    const line=await eda.pcb_PrimitiveLine.create(
      r.net,r.layer,r.x1,r.y1,r.x2,r.y2,r.w,false);
    return !!line;
    """ % __import__("json").dumps(rail)
    if execute(js) is not True:
        raise SystemExit("3V3 rail was not created")
    findings = audit.findings(audit._fetch())
    if findings:
        for kind, distance, message in findings[:12]:
            print(f"  {distance:+.3f} mm {kind}: {message}")
        raise SystemExit(f"3V3 rail caused {len(findings)} overlaps")
    print("  rail created; no overlaps")


if __name__ == "__main__":
    main()
