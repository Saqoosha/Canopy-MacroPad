"""Reserve the two boxed-in local 3V3 joins before the GND tree."""

import sys

import audit
import center_ties
import plane_ratlines
import route


PAIRS = (("C12.1", "C13.1"), ("U3.33", "C10.1"))


def plan(data):
    named = center_ties._named_pads(data)
    anchors = plane_ratlines._island_anchors(data)
    grid = route.build_grid(data)
    out = []
    for first, second in PAIRS:
        first_pad, second_pad = named[first], named[second]
        first_via = anchors.get(first_pad["id"])
        second_via = anchors.get(second_pad["id"])
        # Prefer a Top-layer join between fanout vias. C10 can be boxed in
        # by the pre-routed USB pair; its U3.33 partner is immediately next
        # to it, so that one pair safely falls back to a short Bottom join.
        first_endpoint = (plane_ratlines._endpoint(first_via)
                          if first_via is not None else first_pad)
        second_endpoint = (plane_ratlines._endpoint(second_via)
                           if second_via is not None else second_pad)
        why = route.route_net(
            grid, "3V3",
            [(first, first_endpoint), (second, second_endpoint)], out)
        if why:
            raise SystemExit(f"local 3V3 {first}-{second}: {why}")
    return out


def main():
    import build

    build.open_project_pcb()
    items = plan(audit._fetch())
    print(f"  {', '.join(f'{a}-{b}' for a, b in PAIRS)} -> "
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
        raise SystemExit(f"{len(findings)} overlaps after local 3V3 bridges")
    print("  local 3V3 bridges created; no overlaps")


if __name__ == "__main__":
    main()
