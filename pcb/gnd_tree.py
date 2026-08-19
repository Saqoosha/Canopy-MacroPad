"""Build an explicit Bottom/Top GND tree before signal routing.

EasyEDA's ratline calculator does not count the API-created Bottom pour as
a connection. Routing this tree after signals leaves several GND pads
boxed in; routing it first reserves only legal copper and lets the signal
router choose around it. The Bottom pour remains the low-impedance return.
"""

import sys

import audit
import route


def plan(data):
    owned, _ = audit.component_pads(data)
    pads = [(pad["id"], pad) for component_pads in owned.values()
            for pad in component_pads if pad["net"] == "GND"]
    grid = route.build_grid(data)
    out = []
    why = route.route_net(grid, "GND", pads, out)
    if why:
        raise SystemExit(f"explicit GND tree: {why}")
    return out, len(pads)


def main():
    import build

    build.open_project_pcb()
    items, pads = plan(audit._fetch())
    print(f"  {pads} GND pads -> "
          f"{sum(item['kind'] == 'line' for item in items)} traces, "
          f"{sum(item['kind'] == 'via' for item in items)} vias")
    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to draw it)")
        return
    route.apply(items)
    findings = audit.findings(audit._fetch())
    if findings:
        for kind, distance, message in findings[:15]:
            print(f"    {distance:+8.3f} mm  {kind:12} {message}")
        raise SystemExit(f"{len(findings)} overlaps after GND tree")
    print("  explicit GND tree created; no overlaps")


if __name__ == "__main__":
    main()
