"""Reserve the crystal and DVDD escape corridors before the GND tree."""

import os
import sys

import audit
import route


NETS = ("QSPI_SD0", "QSPI_SCLK", "QSPI_SD3", "QSPI_SS",
        "QSPI_SD1", "QSPI_SD2", "USB_DP", "USB_DM",
        "PIXEL", "PIXEL1", "PIXEL2", "PIXEL3", "PIXEL4", "PIXEL5",
        "KEY0", "KEY1", "KEY2", "KEY3", "KEY4", "KEY5",
        "XIN", "XOUT", "DVDD")


def selected_nets():
    requested = [net for net in os.environ.get("MPAD_CRITICAL_NETS", "").split(",")
                 if net]
    return tuple(requested) if requested else NETS


def plan(data, selected):
    owned, _ = audit.component_pads(data)
    by_id = {component["id"]: component for component in data["comps"]}
    nets = {}
    for component_id, pads in owned.items():
        for pad in pads:
            if pad["net"] in selected:
                nets.setdefault(pad["net"], []).append(
                    (f"{by_id[component_id]['des']}.{pad['num']}", pad))
    grid = route.build_grid(data)
    out = []
    for net in selected:
        why = route.route_net(grid, net, nets[net], out)
        if why:
            raise SystemExit(f"critical {net}: {why}")
    return out


def main():
    import build

    build.open_project_pcb()
    selected = selected_nets()
    items = plan(audit._fetch(), selected)
    print(f"  {', '.join(selected)} -> "
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
        raise SystemExit(f"{len(findings)} overlaps after critical signals")
    print("  critical corridors reserved; no overlaps")


if __name__ == "__main__":
    main()
