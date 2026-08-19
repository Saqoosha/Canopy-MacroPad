"""Reserve explicit 3V3 paths between RP2040 supply islands.

U3.22/C8 and U3.26/C9 each fan out safely to an external via.  If signals
route first, XOUT and KEY3 close the only ordinary-copper path between
those vias and EasyEDA leaves a 3V3 ratline even though the Top pour joins
them physically.  U3.44 also has no direct fanout site; joining it to
U3.48's existing fanout at this stage prevents that path being boxed in.
Route both power bridges first so signal A* chooses legal alternate
corridors.
"""

import os
import sys

import audit
import center_ties
import plane_ratlines
import route


def plan(data, section="all"):
    named = center_ties._named_pads(data)
    anchors = plane_ratlines._island_anchors(data)
    pads = [named[name] for name in ("U3.22", "U3.26")]
    upper = [anchors.get(pad["id"]) for pad in pads]
    if any(endpoint is None for endpoint in upper):
        raise SystemExit("U3.22/U3.26 does not have both external fanout vias")
    lower = [dict(named["U3.44"], kind="pad"),
             anchors.get(named["U3.48"]["id"])]
    if lower[1] is None:
        raise SystemExit("U3.48 does not have an external fanout via")
    grid = route.build_grid(data)
    out = []
    jobs = [("U3.22-U3.26", upper), ("U3.44-U3.48", lower)]
    if section == "upper":
        jobs = jobs[:1]
    elif section == "lower":
        jobs = jobs[1:]
    for label, endpoints in jobs:
        why = route.route_net(
            grid, "3V3",
            [(f"{label} endpoint {index}", plane_ratlines._endpoint(endpoint))
             for index, endpoint in enumerate(endpoints, 1)],
            out,
        )
        if why:
            raise SystemExit(f"{label} 3V3 bridge: {why}")
    return out, jobs


def main():
    import build

    build.open_project_pcb()
    items, jobs = plan(audit._fetch(), os.environ.get("MPAD_U3_BRIDGES", "all"))
    for label, endpoints in jobs:
        print(f"  {label}: " + " -> ".join(
            f"({endpoint['x'] * audit.MIL:.3f},"
            f"{endpoint['y'] * audit.MIL:.3f}) mm" for endpoint in endpoints))
    print(f"  {sum(item['kind'] == 'line' for item in items)} traces, "
          f"{sum(item['kind'] == 'via' for item in items)} vias")
    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to draw it)")
        return
    route.apply(items)
    findings = audit.findings(audit._fetch())
    if findings:
        for kind, distance, message in findings[:15]:
            print(f"    {distance:+8.3f} mm  {kind:12} {message}")
        raise SystemExit(f"{len(findings)} overlaps after U3 3V3 bridge")
    print("  bridge created; no overlaps")


if __name__ == "__main__":
    main()
