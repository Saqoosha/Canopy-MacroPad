"""Reserve local 3V3 decoupling connections before signal routing."""

import json
import sys

import audit
import grid
import route
from bridge import execute

MIL = 0.0254
WIDTH_MM = 0.15

PAIRS = (
    ("C8.1", "U3.22"),
    ("C9.1", "U3.26"),
)


def plan(data):
    owned, _ = audit.component_pads(data)
    by_id = {c["id"]: c for c in data["comps"]}
    pads = {f"{by_id[cid]['des']}.{p['num']}": p
            for cid, ps in owned.items() for p in ps}
    items = []
    for a_name, b_name in PAIRS:
        a, b = pads[a_name], pads[b_name]
        if a["net"] != "3V3" or b["net"] != "3V3":
            raise SystemExit(f"{a_name}/{b_name} are no longer both 3V3")
        board_grid = route.build_grid(data)
        starts = [cell for cell in route.pad_cells(board_grid, a, "3V3")
                  if cell[0] == route.BOTTOM]
        goals = [cell for cell in route.pad_cells(board_grid, b, "3V3")
                 if cell[0] == route.BOTTOM]
        path = board_grid.search(starts, goals, "3V3", via_cost=1e9)
        if path is None or any(cell[0] != route.BOTTOM for cell in path):
            raise SystemExit(
                f"{a_name}-{b_name} has no bottom-layer local path"
            )

        ax, ay = board_grid.xy_of(path[0][1], path[0][2])
        bx, by = board_grid.xy_of(path[-1][1], path[-1][2])
        points = [(a["x"], a["y"]), (ax, ay)]
        for kind, p, q in grid.simplify(path):
            if kind != "line":
                raise SystemExit(
                    f"{a_name}-{b_name} unexpectedly needs a via"
                )
            points.append(board_grid.xy_of(q[1], q[2]))
        points.append((b["x"], b["y"]))

        for index, ((x1, y1), (x2, y2)) in enumerate(
                zip(points, points[1:]), start=1):
            if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
                continue
            items.append({
                "name": f"{a_name} -> {b_name} [{index}]",
                "net": "3V3", "layer": route.BOTTOM,
                "x1": x1, "y1": y1,
                "x2": x2, "y2": y2, "w": WIDTH_MM / MIL,
            })
    return items


def main():
    import build
    build.open_project_pcb()
    items = plan(audit._fetch())
    print("\nplan:")
    for item in items:
        print(f"  {item['name']}  {WIDTH_MM:.2f} mm")
    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to draw it)")
        return
    js = """
    const items = %s;
    let made = 0;
    for (const it of items) {
      const line = await eda.pcb_PrimitiveLine.create(
        it.net, it.layer, it.x1, it.y1, it.x2, it.y2, it.w, false);
      if (line) made += 1;
    }
    return {made, asked: items.length};
    """ % json.dumps(items)
    got = execute(js)
    if got["made"] != got["asked"]:
        raise SystemExit(
            f"created {got['made']} of {got['asked']} local decoupling traces"
        )
    findings = audit.findings(audit._fetch())
    if findings:
        raise SystemExit(f"local decoupling trace caused {len(findings)} overlaps")
    print(f"\napply:\n  {got['made']}/{got['asked']} local traces\n  no overlaps")


if __name__ == "__main__":
    main()
