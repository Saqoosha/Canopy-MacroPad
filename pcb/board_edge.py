"""Create and verify the single rounded board outline.

The outline is deliberately one closed polyline. EasyEDA accepts four
touching lines as a picture of a rectangle but not as a board boundary.
The ``R`` polygon form carries the corner radius in the document itself,
so the plane boundary and the rendered check can derive from the same fact.
"""

import json
import sys

import params
from bridge import execute

MIL = 0.0254
OUTLINE = 11


def source(inset_mm=0.0):
    """Rounded-rectangle polygon source, in EasyEDA's 1 mil unit."""
    if inset_mm < 0:
        raise ValueError("inset must be non-negative")
    w = params.BOARD_W - 2 * inset_mm
    h = params.BOARD_D - 2 * inset_mm
    r = params.BOARD_CORNER_RADIUS - inset_mm
    if w <= 0 or h <= 0 or r < 0:
        raise ValueError("inset collapses the rounded outline")
    return [
        "R",
        inset_mm / MIL,
        (params.BOARD_D - inset_mm) / MIL,
        w / MIL,
        h / MIL,
        0,
        r / MIL,
    ]


def state():
    js = """
    const ps = await eda.pcb_PrimitivePolyline.getAll();
    const edge = (ps || []).filter(p => p.layer === 11);
    const ls = await eda.pcb_PrimitiveLine.getAll();
    const loose = (ls || []).filter(l => l.layer === 11);
    const bbox = edge.length === 1
      ? await eda.pcb_Primitive.getPrimitivesBBox([edge[0].primitiveId]) : null;
    return {
      loose: loose.length,
      bbox,
      edges: edge.map(p => ({
        id: p.primitiveId,
        source: p.polygon && p.polygon.polygon ? p.polygon.polygon : null,
      })),
    };
    """
    return execute(js)


def verify():
    got = state()
    if got["loose"]:
        raise SystemExit(f"board edge has {got['loose']} loose line(s)")
    if len(got["edges"]) != 1:
        raise SystemExit(f"board edge is {len(got['edges'])} polylines, wanted one")
    edge = got["edges"][0]
    src = edge["source"] or []
    want = source()
    if len(src) != len(want) or src[0] != "R":
        raise SystemExit(f"board edge is not one rounded rectangle: {src}")
    for actual, expected in zip(src[1:], want[1:]):
        if abs(actual - expected) > 0.01:
            raise SystemExit(f"board edge source differs: {src} != {want}")
    bbox = got.get("bbox")
    if not bbox:
        raise SystemExit("board edge has no measurable bounding box")
    # The 1 mil outline stroke extends 0.5 mil outside the mathematical
    # edge. Check all four coordinates; width/height alone did not catch a
    # rounded R source placed at y=-BOARD_D instead of y=0..BOARD_D.
    actual = (bbox["minX"] * MIL, bbox["minY"] * MIL,
              bbox["maxX"] * MIL, bbox["maxY"] * MIL)
    expected = (0.0, 0.0, params.BOARD_W, params.BOARD_D)
    if any(abs(a - e) > 0.02 for a, e in zip(actual, expected)):
        raise SystemExit(f"board edge bbox {actual} differs from {expected}")
    print(
        f"  board edge: one rounded polyline, {params.BOARD_W:.2f} x "
        f"{params.BOARD_D:.2f} mm, R{params.BOARD_CORNER_RADIUS:.2f} mm"
    )
    return edge


def apply():
    src = source()
    js = """
    const source = %s;
    const ps = await eda.pcb_PrimitivePolyline.getAll();
    const pids = (ps || []).filter(p => p.layer === 11).map(p => p.primitiveId);
    const ls = await eda.pcb_PrimitiveLine.getAll();
    const lids = (ls || []).filter(l => l.layer === 11).map(l => l.primitiveId);
    if (pids.length) await eda.pcb_PrimitivePolyline.delete(pids);
    if (lids.length) await eda.pcb_PrimitiveLine.delete(lids);
    const polygon = eda.pcb_MathPolygon.createPolygon(source);
    if (!polygon) return {error: "rounded polygon creation failed"};
    const made = await eda.pcb_PrimitivePolyline.create("", 11, polygon, 1, false);
    return {made: !!made, removedPolylines: pids.length, removedLines: lids.length};
    """ % json.dumps(src)
    got = execute(js, timeout=120.0)
    if got.get("error") or not got.get("made"):
        raise SystemExit(got.get("error", "rounded outline was not created"))
    print(
        f"  replaced {got['removedPolylines']} outline polyline(s) and "
        f"{got['removedLines']} loose line(s)"
    )
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
