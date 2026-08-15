"""Is every net actually joined up? The twin of audit.py.

audit.py finds copper that should not be there. This finds copper that
should be there and is not -- a net whose pads the router left in two or
more islands. Nothing reports that on its own: the ratlines disappear from
the view as soon as a trace is drawn near them, DRC is a rule checker and
an unrouted net breaks no rule, and a board with one net split in half
looks exactly like a finished one.

The method is a graph. Pads, vias and trace endpoints are nodes; a trace
joins its two ends; a via joins every layer; and a pad or via on a net
that owns an inner plane is joined to every other pad on that net, because
the plane is the wire. Then each net has to come out as a single connected
component.

Two things it also asks, because a four-layer board can be ruined quietly:

  - traces on the plane layers, which cut the plane they cross
  - traces inside a keepout, which the keepouts exist to prevent

    python3 connect.py
"""

import audit
import geom
from bridge import execute

MIL = 0.0254

# Layers 15 and 16 carry the GND and 3V3 pours. A signal routed there is
# not a signal on a spare layer -- it is a slot cut through a plane, and
# the plane's job is to be uninterrupted.
PLANE_LAYERS = {15: None, 16: None}   # filled from the live pours

# How close two pieces of copper must be to count as joined. This is a
# measurement tolerance, not a design allowance: route.py works on a
# 0.1 mm grid and ends a trace on the nearest cell centre, which can sit
# half a cell outside the pad it is landing in. At 0.05 that boundary case
# read as "not connected" for thirteen nets whose traces were drawn and
# correct. Nothing is being excused -- audit.py independently guarantees
# no two nets touch, and this only decides when one net's own copper
# counts as joined to itself.
TOUCH_MM = 0.08


def _fetch():
    js = """
    const out = {};
    const cs = await eda.pcb_PrimitiveComponent.getAll();
    const byId = {};
    for (const c of cs||[]) byId[c.primitiveId] = c.designator;
    const ids = Object.keys(byId).sort((a, b) => b.length - a.length);
    const pads = await eda.pcb_PrimitivePad.getAll();
    out.pads = (pads||[]).map(p => {
      let owner = "(free)";
      for (const i of ids)
        if (p.primitiveId.startsWith(i) && p.primitiveId !== i) {
          owner = byId[i]; break;
        }
      return {id: p.primitiveId, des: owner, num: p.padNumber, x: p.x, y: p.y,
              layer: p.layer, net: p.net, hole: !!p.hole,
              pad: p.pad, r: p.rotation};
    });
    const ls = await eda.pcb_PrimitiveLine.getAll();
    out.lines = (ls||[]).map(l => ({id: l.primitiveId, net: l.net,
      layer: l.layer, x1: l.startX, y1: l.startY, x2: l.endX, y2: l.endY,
      w: l.lineWidth}));
    const vs = await eda.pcb_PrimitiveVia.getAll();
    out.vias = (vs||[]).map(v => ({id: v.primitiveId, net: v.net,
      x: v.x, y: v.y, dia: v.diameter}));
    const ps = await eda.pcb_PrimitivePour.getAll();
    out.pours = (ps||[]).map(p => ({net: p.net, layer: p.layer}));
    const rs = await eda.pcb_PrimitiveRegion.getAll();
    out.regions = (rs||[]).map(r => ({layer: r.layer, rules: r.ruleType,
      poly: r.complexPolygon ? "yes" : "no"}));
    return out;
    """
    return execute(js, timeout=120.0)


class _Union:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def analyse(data):
    plane_nets = {p["net"]: p["layer"] for p in data["pours"] if p["net"]}
    tol = TOUCH_MM / MIL

    # Everything that carries a net, as points.
    nodes = []
    for p in data["pads"]:
        if not p["net"]:
            continue
        nodes.append(("pad", f"{p['des']}.{p['num']}", p["net"], p["x"],
                      p["y"], p["layer"], p["layer"] == audit.MULTI,
                      geom.pad_polygon(p["x"], p["y"], p["r"], p["pad"])))
    for v in data["vias"]:
        if not v["net"]:
            continue
        nodes.append(("via", v["id"][:8], v["net"], v["x"], v["y"], 12, True,
                      geom.pad_polygon(v["x"], v["y"], 0,
                                       ["ROUND", v["dia"]])))

    u = _Union()
    for node in nodes:
        u.find((node[0], node[1]))

    def near(x, y, net, layer, half=0.0):
        """Everything of `net` that a trace ending at (x, y) touches.

        Against the pad's SHAPE, not its centre. A router ends a trace on
        a cell inside the pad, which is rarely the pad's centre point, and
        comparing to the centre reported thirty-two perfectly routed nets
        as broken -- each one split into "the pad", "the other pad" and
        "the wire between them". The board was right and the instrument
        was measuring the wrong thing.
        """
        hit = []
        for kind, name, n, px, py, pl, through, poly in nodes:
            if n != net:
                continue
            if not (through or layer == 12 or pl == layer):
                continue
            if geom.point_in_or_near(x, y, poly, tol + half):
                hit.append((kind, name))
        return hit

    # A trace joins whatever copper its whole swept shape touches, not only
    # what its centreline endpoints land on.  EasyEDA merges same-net work
    # freely: the final USB pass joined D1.4/D1.6 by running an existing
    # line through the middle of each pad, leaving neither line endpoint at
    # the pad centre.  Endpoint-only accounting called both pads islands on
    # copper that visibly crossed them.
    trace_nodes = []
    for l in data["lines"]:
        if l["layer"] not in (audit.TOP, audit.BOTTOM):
            continue
        a = ("pt", l["layer"], round(l["x1"], 1), round(l["y1"], 1), l["net"])
        b = ("pt", l["layer"], round(l["x2"], 1), round(l["y2"], 1), l["net"])
        u.join(a, b)
        copper = geom.segment(l["x1"], l["y1"], l["x2"], l["y2"], l["w"])
        trace_nodes.append((l, a, b, copper))
        # A trace has WIDTH. Its end cap reaches half a line-width past the
        # centre point, so a trace ending just outside a 0.25 mm pad still
        # lands copper on it -- which is connected, and reads as broken if
        # only the centre is tested. Every remaining failure was at a small
        # pad (the XSON-8 flash, the pixels) for exactly this reason.
        half = l["w"] / 2.0
        for end, (ex, ey) in ((a, (l["x1"], l["y1"])), (b, (l["x2"], l["y2"]))):
            for t in near(ex, ey, l["net"], l["layer"], half):
                u.join(end, t)
        for kind, name, net, px, py, pl, through, poly in nodes:
            if net != l["net"]:
                continue
            if not (through or pl == l["layer"]):
                continue
            if geom.distance(copper, poly) <= tol:
                u.join(a, (kind, name))

    # Same-net T junctions may also land in the middle of a trace rather
    # than on its endpoint.  Join the trace graphs by copper intersection.
    for i, (la, aa, ab, pa) in enumerate(trace_nodes):
        for lb, ba, bb, pb in trace_nodes[i + 1:]:
            if la["net"] != lb["net"] or la["layer"] != lb["layer"]:
                continue
            if geom.distance(pa, pb) <= tol:
                u.join(aa, ba)

    # A via whose copper overlaps a pad of its own net is connected to it.
    # Joins were only ever made through trace ENDPOINTS, so a via landing
    # inside a pad -- which is what the router does to bring a top-layer
    # route down onto a bottom-layer pad -- joined nothing, and ten fully
    # connected nets read as broken. Measuring one of them settled it: the
    # trace overlapped the pad by 0.274 mm but sat on layer 1 over a layer
    # 2 pad, and the via that bridged them was right there at the landing
    # point, unaccounted for.
    for ka, na, neta, xa, ya, la, ha, pa in nodes:
        if ka != "via":
            continue
        for kb, nb, netb, xb, yb, lb, hb, pb in nodes:
            if kb != "pad" or netb != neta:
                continue
            if geom.distance(pa, pb) <= 0:
                u.join((ka, na), (kb, nb))

    # A plane is a wire: everything on that net is joined by it, provided
    # it can reach the plane at all -- which means a via or a Multi-Layer
    # pad. A Bottom pad may contain a drill and still carry no inner-layer
    # copper; the USB VBUS pads prove that distinction.
    for net, layer in plane_nets.items():
        anchor = ("plane", net)
        for kind, name, n, x, y, pl, through, poly in nodes:
            if n == net and through:
                u.join((kind, name), anchor)

    # Now: one component per net?
    by_net = {}
    for kind, name, net, x, y, layer, through, poly in nodes:
        by_net.setdefault(net, []).append(((kind, name), (x, y)))
    broken = {}
    for net, members in by_net.items():
        groups = {}
        for key, xy in members:
            groups.setdefault(u.find(key), []).append((key, xy))
        if len(groups) > 1:
            broken[net] = [
                [f"{k[1]}" for k, _ in g] for g in groups.values()]
    return broken, plane_nets, by_net


def plane_cuts(data):
    """Traces sitting on a layer that carries a plane."""
    planes = {p["layer"] for p in data["pours"]}
    return [l for l in data["lines"] if l["layer"] in planes]


def main():
    data = _fetch()
    broken, plane_nets, by_net = analyse(data)

    traces = [l for l in data["lines"] if l["layer"] in (audit.TOP, audit.BOTTOM)]
    print(f"  traces {len(traces)}   vias {len(data['vias'])}   "
          f"nets {len(by_net)}")
    print(f"  planes: " + ", ".join(f"{n} on layer {l}"
                                    for n, l in plane_nets.items()))

    cuts = plane_cuts(data)
    if cuts:
        print(f"\n  {len(cuts)} traces are ON a plane layer -- these are not "
              f"routes, they are slots cut through the plane:")
        for l in cuts[:10]:
            print(f"    {l['net'] or '-':12} layer {l['layer']} "
                  f"({l['x1']*MIL:.1f},{l['y1']*MIL:.1f}) -> "
                  f"({l['x2']*MIL:.1f},{l['y2']*MIL:.1f})")

    if not broken:
        print(f"\n  every one of {len(by_net)} nets is a single connected "
              f"island")
        return
    print(f"\n  {len(broken)} nets are NOT fully connected:")
    for net in sorted(broken, key=lambda n: -len(broken[n])):
        groups = broken[net]
        print(f"    {net:12} {len(groups)} islands: " +
              " | ".join(",".join(g[:5]) + ("..." if len(g) > 5 else "")
                         for g in groups[:4]))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
