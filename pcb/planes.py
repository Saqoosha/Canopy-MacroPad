"""The two inner-layer planes, rebuilt from the board outline.

They existed once and vanished. They had been drawn for the 121.60 mm
board; widening it to 139.60 and redrawing the edge as a closed polyline
left their boundaries describing a board that no longer exists, and
rebuilding the copper regions removed them. Nothing said so -- the pour
list simply came back empty, and the only visible symptom was an
autorouter that did nothing and logged nothing.

So they are derived here from params, like everything else, instead of
being drawn once by hand and then quietly outliving the board.

Layer 15 is Inner1 and layer 16 is Inner2 in this stack; the client's own
layer list is what says so, and `assert_stack()` re-reads it rather than
trusting these two numbers.

    python3 planes.py            report
    python3 planes.py --apply    (re)create and rebuild them
    python3 planes.py --rebuild  rebuild the existing two pours
"""

import json
import sys

import board_edge
import build
import params
from bridge import execute

MIL = 0.0254

# net -> layer. GND goes on the layer nearer the components (all parts are
# on the bottom), so the return path under the RP2040 is one via away.
PLANES = [("GND", 16), ("3V3", 15)]

# How far the copper stops short of the board edge. JLCPCB wants copper
# 0.3 mm inside the outline; 0.5 is comfortable and costs nothing here.
EDGE_PULLBACK_MM = 0.50


def assert_stack():
    """The plane layers must be inner signal layers, and there must be 4."""
    js = """
    const n = await eda.pcb_Layer.getTheNumberOfCopperLayers();
    const all = await eda.pcb_Layer.getAllLayers();
    return {copper: n, layers: (all||[])
      .filter(l => [1, 2, 15, 16].indexOf(l.id) >= 0)
      .map(l => [l.id, l.name, l.type])};
    """
    got = execute(js)
    if got["copper"] != params.BOARD_LAYERS:
        raise SystemExit(f"the board has {got['copper']} copper layers, "
                         f"params says {params.BOARD_LAYERS}")
    named = {i: (n, t) for i, n, t in got["layers"]}
    for net, layer in PLANES:
        if layer not in named:
            raise SystemExit(f"layer {layer} is not in the stack")
        if named[layer][1] != "SIGNAL":
            raise SystemExit(f"layer {layer} is {named[layer][1]}, not SIGNAL")
    print("  stack: " + ", ".join(f"{i}={named[i][0]}" for i in sorted(named)))
    return named


def outline_rect():
    """The live rounded edge pulled inward by the copper-edge rule."""
    board_edge.verify()
    return board_edge.source(EDGE_PULLBACK_MM)


def apply(path):
    js = """
    const path = %s;
    const planes = %s;
    const out = {removed: 0, made: []};
    const olds = await eda.pcb_PrimitivePour.getAll();
    const kill = (olds||[]).filter(p => planes.some(q => q[1] === p.layer))
                           .map(p => p.primitiveId);
    if (kill.length) { await eda.pcb_PrimitivePour.delete(kill);
                       out.removed = kill.length; }
    for (const [net, layer] of planes) {
      const poly = eda.pcb_MathPolygon.createPolygon(path);
      if (!poly) { out.made.push([net, layer, "polygon failed"]); continue; }
      const p = await eda.pcb_PrimitivePour.create(net, layer, poly);
      out.made.push([net, layer, !!p]);
    }
    const now = await eda.pcb_PrimitivePour.getAll();
    out.pours = (now||[]).map(p => [p.net, p.layer]);
    return out;
    """ % (json.dumps(path), json.dumps(PLANES))
    got = execute(js, timeout=180.0)
    print(f"  removed {got['removed']}, created "
          f"{sum(1 for _, _, ok in got['made'] if ok is True)}")
    for net, layer, ok in got["made"]:
        print(f"    {net:5} on layer {layer}: {ok}")
    if any(ok is not True for _, _, ok in got["made"]):
        raise SystemExit("a plane was not created")
    if len(got["pours"]) != len(PLANES):
        raise SystemExit(f"the board now has {got['pours']} -- expected "
                         f"exactly {PLANES}")
    return got


def state():
    js = """
    const pr = await eda.pcb_PrimitivePour.getAll();
    const pd = await eda.pcb_PrimitivePoured.getAll();
    return {pours: (pr||[]).map(p => [p.net, p.layer]),
            poured: (pd||[]).length};
    """
    return execute(js)


def rebuild():
    """Turn the two pour boundaries into current copper.

    This used to throw while the board had no useful through connection to
    3V3.  With the power vias present, the documented instance method works
    and must be read back as a real poured primitive for both planes.
    """
    js = """
    const ps = await eda.pcb_PrimitivePour.getAll();
    const out = [];
    for (const p of ps || []) {
      try {
        const r = await p.rebuildCopperRegion();
        out.push({net: p.getState_Net(), layer: p.getState_Layer(), ok: !!r});
      } catch (e) {
        out.push({net: p.getState_Net(), layer: p.getState_Layer(), error: String(e)});
      }
    }
    const filled = await eda.pcb_PrimitivePoured.getAll();
    return {planes: out, filled: (filled || []).length};
    """
    got = execute(js, timeout=180.0)
    for p in got["planes"]:
        print(f"  rebuild {p['net']:5} layer {p['layer']}: "
              f"{'ok' if p.get('ok') else p.get('error', 'failed')}")
    if len(got["planes"]) != len(PLANES) or not all(
            p.get("ok") for p in got["planes"]):
        raise SystemExit(f"plane rebuild failed: {got}")
    if got["filled"] < len(PLANES):
        raise SystemExit(f"only {got['filled']} poured primitives after rebuild")
    print(f"  filled copper primitives: {got['filled']}")
    return got


def main():
    build.open_project_pcb()
    assert_stack()
    s = state()
    print(f"  pours now: {s['pours'] or 'none'}   filled: {s['poured']}")

    if "--rebuild" in sys.argv:
        print("\nrebuild:")
        rebuild()
        return

    if "--apply" not in sys.argv:
        print("\n(report only -- pass --apply to (re)create them)")
        return
    path = outline_rect()
    x0, y1 = path[1], path[2]
    x1, y0 = x0 + path[3], y1 - path[4]
    print(f"\n  inset outline: x {x0*MIL:.2f}..{x1*MIL:.2f}, "
          f"y {y0*MIL:.2f}..{y1*MIL:.2f} mm, "
          f"R{path[6]*MIL:.2f} ({EDGE_PULLBACK_MM} mm inside the edge)")
    print("\napply:")
    apply(path)
    print("\nrebuild:")
    rebuild()


if __name__ == "__main__":
    main()
