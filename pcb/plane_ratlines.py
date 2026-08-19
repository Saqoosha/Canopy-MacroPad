"""Route the plane connections that EasyEDA still presents as ratlines.

The outer copper pours are electrically continuous, but EasyEDA Pro does
not retire the ratlines for API-created pours.  Hiding the Ratline layer is
not a fix: read the Net panel's exact endpoint pairs and give each one an
ordinary copper path.  The pours remain as current-carrying reinforcement.

The Net panel is the only public surface that exposes ratline endpoints.
Its rows select the two real pad/via primitives, so the gateway reads those
selections and the same obstacle-aware grid used for signals routes them.

    python3 plane_ratlines.py            report and plan
    python3 plane_ratlines.py --apply    route, rebuild pours, require zero
"""

import re
import sys

import audit
import connect
import planes
import route
from bridge import execute


def ratline_pairs():
    """Return (label, endpoint primitive ids) from the live Net panel."""
    js = r"""
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    const root = document.querySelector('[data-itemid="NetTab|_|Ratlines"]');
    if (!root) return {error: 'Ratlines row is not available'};

    const expand = element => {
      const icon = element && element.parentElement
        .querySelector('.tree-extends-icon_KtVQh');
      if (icon && !icon.className.includes('active')) icon.click();
    };
    expand(root);
    await sleep(150);
    for (const net of ['3V3', 'GND']) {
      expand(document.querySelector(
        `[data-itemid="NetTab|_|Ratlines|_|${net}"]`));
    }
    await sleep(150);

    const leaves = [...document.querySelectorAll(
      '[data-itemid^="NetTab|_|Ratlines|_|"]')]
      .filter(element => element.getAttribute('data-itemid')
        .split('|_|').length === 4)
      .map(element => element.getAttribute('data-itemid'));
    const out = [];
    for (const itemId of leaves) {
      // Selecting one row re-renders the virtual tree. Re-query every row;
      // references captured before the first click become detached nodes.
      const element = document.querySelector(`[data-itemid="${itemId}"]`);
      const row = element.parentElement;
      const key = Object.keys(row).find(key => key.startsWith('__reactProps'));
      const click = key && row[key] && row[key].onClick;
      if (typeof click !== 'function') {
        out.push({label: element.textContent, error: 'row has no onClick'});
        continue;
      }
      await click({
        stopPropagation() {}, preventDefault() {},
        currentTarget: row, target: element, button: 0,
      });
      await sleep(60);
      const selected = await eda.pcb_SelectControl.getAllSelectedPrimitives();
      out.push({
        label: element.textContent,
        endpoints: (selected || []).map(primitive => primitive.primitiveId),
      });
    }
    await eda.pcb_SelectControl.clearSelected();
    return {count: root.textContent, pairs: out};
    """
    got = execute(js, timeout=120.0)
    if got.get("error"):
        raise SystemExit(got["error"])
    bad = [pair for pair in got["pairs"]
           if pair.get("error") or len(pair.get("endpoints") or []) != 2]
    if bad:
        raise SystemExit(f"could not read ratline endpoints: {bad}")
    return got


def _endpoint(item):
    """Make pads and existing vias both consumable by route.pad_cells."""
    if item["kind"] == "pad":
        return item
    if item["kind"] == "via":
        return {
            "x": item["x"], "y": item["y"], "r": 0,
            "layer": audit.MULTI, "pad": ["ROUND", item["dia"]],
            "net": item["net"], "hole": ["ROUND", item["hole"]],
        }
    raise SystemExit(f"ratline selected unsupported {item['kind']}")


def _island_anchors(data):
    """Pad primitive id -> an existing via in its explicit copper island."""
    explicit = connect._fetch()
    explicit["pours"] = []
    broken, _, _ = connect.analyse(explicit)
    name_by_id = {
        pad["id"]: f"{pad['des']}.{pad['num']}" for pad in explicit["pads"]
    }
    name_by_id.update({via["id"]: via["id"][:8]
                       for via in explicit["vias"]})
    via_by_name = {via["id"][:8]: via["id"] for via in explicit["vias"]}
    by_id = {via["id"]: dict(via, kind="via") for via in data["vias"]}
    anchors = {}
    for groups in broken.values():
        for group in groups:
            via_names = [name for name in group if name in via_by_name]
            if not via_names:
                continue
            anchor = by_id[via_by_name[via_names[0]]]
            for primitive_id, name in name_by_id.items():
                if name in group:
                    anchors[primitive_id] = anchor
    return anchors


def plan(data, pairs):
    by_id = {pad["id"]: dict(pad, kind="pad") for pad in data["pads"]}
    by_id.update({via["id"]: dict(via, kind="via") for via in data["vias"]})
    anchors = _island_anchors(data)
    three_pairs = []
    has_ground_pairs = False
    for pair in pairs:
        endpoints = [by_id[primitive_id] for primitive_id in pair["endpoints"]]
        if endpoints[0]["net"] == "3V3":
            three_pairs.append(pair)
        elif endpoints[0]["net"] == "GND":
            has_ground_pairs = True

    owned, _ = audit.component_pads(data)
    ground = [(pad["id"], pad) for pads in owned.values() for pad in pads
              if pad["net"] == "GND"]

    stages = (["3V3"] if three_pairs else []) + (["GND"]
                                                  if has_ground_pairs else [])
    orders = [tuple(stages)]
    if len(stages) == 2:
        orders.append(tuple(reversed(stages)))
    best = None
    for attempt, order in enumerate(orders, 1):
        grid = route.build_grid(data)
        out, failed = [], []
        for net in order:
            if net == "GND":
                why = route.route_net(grid, "GND", ground, out)
                if why:
                    failed.append(("all GND pads", why))
                continue
            for pair in three_pairs:
                a, b = (by_id[primitive_id]
                        for primitive_id in pair["endpoints"])
                a = anchors.get(pair["endpoints"][0], a)
                b = anchors.get(pair["endpoints"][1], b)
                why = route.route_net(
                    grid, "3V3",
                    [(pair["endpoints"][0], _endpoint(a)),
                     (pair["endpoints"][1], _endpoint(b))],
                    out,
                )
                if why:
                    failed.append((pair["label"], why))
        print(f"  round {attempt} ({' then '.join(order)}): "
              f"{'complete' if not failed else 'stuck: ' + ', '.join(label for label, _ in failed)}",
              flush=True)
        if best is None or len(failed) < len(best[1]):
            best = (out, failed)
        if not failed:
            return out, []
    return best


def recalculate_count():
    """Recalculate, refresh the panel, and return its displayed count."""
    js = r"""
    try { await eda.pcb_Document.stopCalculatingRatline(); } catch (e) {}
    await eda.pcb_Document.startCalculatingRatline();
    const row = document.querySelector('[data-itemid="NetTab|_|Ratlines"]');
    const refresh = row && row.querySelector('.smallIcon_sN5et');
    if (refresh) refresh.click();
    await new Promise(resolve => setTimeout(resolve, 1000));
    return row ? row.textContent : '';
    """
    text = execute(js, timeout=30.0)
    match = re.fullmatch(r"Ratlines \((\d+)\)", text or "")
    if not match:
        raise SystemExit(f"could not read Ratlines count: {text!r}")
    return int(match.group(1))


def main():
    import build

    build.open_project_pcb()
    current = ratline_pairs()
    pairs = current["pairs"]
    print(f"  panel: {current['count']}; {len(pairs)} endpoint pairs")
    if not pairs:
        print("  no plane ratlines")
        return

    print("\nplan:")
    items, failed = plan(audit._fetch(), pairs)
    print(f"\n  {sum(item['kind'] == 'line' for item in items)} traces, "
          f"{sum(item['kind'] == 'via' for item in items)} vias")
    if failed:
        for label, why in failed:
            print(f"    FAILED {label}: {why}")
        raise SystemExit("not every displayed plane ratline has a route")
    if "--apply" not in sys.argv:
        print("\n(plan only -- pass --apply to draw it)")
        return

    print("\napply:")
    route.apply(items)
    findings = audit.findings(audit._fetch())
    if findings:
        for kind, distance, message in findings[:15]:
            print(f"    {distance:+8.3f} mm  {kind:12} {message}")
        raise SystemExit(f"{len(findings)} overlaps after plane routing")
    print("  no overlaps")

    print("\nrebuild:")
    planes.rebuild()
    remaining = recalculate_count()
    print(f"  Net panel Ratlines ({remaining})")
    if remaining:
        raise SystemExit(f"{remaining} ratline nets remain")


if __name__ == "__main__":
    main()
