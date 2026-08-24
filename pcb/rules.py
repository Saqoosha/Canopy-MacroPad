"""Make the board's rules mean something, and name the pairs.

An earlier round spent an afternoon arguing about 48 DRC errors without
ever establishing what the rules being violated were. They turn out to
be a configuration called 自定义配置.  This file makes that configuration
match the geometry the independent audit actually measures: 0.13 mm for
copper, 0.20 mm from routed openings, and 0.25 mm from the USB-C shell
holes to the outline.

The client also ships JLCPCB's capability as a preset, and the obvious
move is to load it. It does not work, silently: the preset and the live
configuration disagree about the shape of the same table, so the
overwrite returns undefined and changes nothing.  The values are therefore
written to the live configuration directly and read back after every write.

Two more things the autorouter cannot know unless told:

  USB_DP/USB_DM is a differential pair. Unpaired, a router draws two
  unrelated wires that happen to end up near each other, and the first
  time anybody notices is when a host enumerates intermittently.


    python3 rules.py            report
    python3 rules.py --apply    set them
    python3 rules.py --drc      check them
"""

import json
import sys

import build
from bridge import execute

JLC_PRESET = "JLCPCB Capability(Multiple Layers Board)"

# The preset is NOT applied, and the reason is worth keeping: it and the
# board's own configuration use different shapes for the same table --
# `table` in the preset against `tables` keyed by status in the live one --
# so overwriting with it does nothing, silently, returning undefined. And
# it would buy nothing anyway: this board deliberately uses 0.13 mm,
# slightly more than the ordinary two-layer 5 mil process limit.
#
# What DID need changing is the default track width. 0.254 mm cannot pass
# between the pads of a 0.4 mm-pitch QFN-56, which is the hardest escape
# on this board; 0.15 mm can, carries far more than any signal here needs
# at 1 oz, and leaves the 0.127 minimum untouched as the floor. Power does
# not depend on it -- GND and 3V3 use the two outer-layer pours.
TRACK_DEFAULT_MM = 0.15

# One copper clearance everywhere, just over the cheap two-layer 5 mil
# process limit and identical to the router and geometric audit.
COPPER_CLEARANCE_MM = 0.13

# Routed board openings are held to the same 0.20 mm edge clearance that
# audit.py measures geometrically. The stock table's 0.30 mm contradicted the
# keepouts and rejected the deliberately centred KEY0/KEY3 gap routes.
SLOT_TO_TRACK_MM = 0.20

# The USB-C shell through-holes sit 0.277 mm from the routed board edge.
# They are mechanically fixed by the connector footprint and still exceed
# JLCPCB's 0.20 mm routed-edge capability.  Keep a little extra margin without
# carrying the stock 0.30 mm rule that this connector cannot satisfy.
BOARD_OUTLINE_TO_TH_MM = 0.25

# RP2040 is USB Full-Speed. The routed pair differs by 1.21 mm (47.8 mil),
# which is electrically negligible at 12 Mbit/s; 1.5 mm still catches an
# accidental large detour without pretending this is a high-speed link.
DIFF_PAIR_SKEW_MAX_MM = 1.5

# Ordinary-cost 0.30/0.45 mm via.  Keeping these in the live rule
# configuration makes hand-added vias agree with the router and avoids the
# advanced small-via process option in the fabrication quote.
VIA_OUTER_MM = 0.45
VIA_HOLE_MM = 0.30

DIFF_PAIRS = [
    # name, positive, negative -- the raw side, between the connector and
    # the series resistors, and the MCU side after them. RP2040 is full
    # speed, so this is not exotic; it is just the pair being a pair.
    ("USB_RAW", "USB_DP_RAW", "USB_DM_RAW"),
    ("USB_MCU", "USB_DP", "USB_DM"),
]

# Net classes were tried and are gone. `createNetClass` returns falsy and
# `addNetToNetClass` adds nothing -- `getAllNetClasses()` still reports an
# empty list afterwards -- and the first version of this file read that
# falsy return as "the class already existed" and printed a reassuring
# line about a class that did not exist. A feature that cannot work and
# reports success is worse than no feature. They are not needed anyway:
# GND and 3V3 use outer-layer pours, so signals retain the 0.15 mm default.


def state():
    js = """
    return {
      current: await eda.pcb_Drc.getCurrentRuleConfigurationName(),
      available: await eda.pcb_Drc.getAllRuleConfigurations(),
      pairs: await eda.pcb_Drc.getAllDifferentialPairs(),
      classes: await eda.pcb_Drc.getAllNetClasses(),
      nets: await eda.pcb_Net.getAllNetsName(),
    };
    """
    return execute(js, timeout=120.0)


def apply():
    js = """
    const pairs = %s;
    const out = {};
    const width = %f;
    const viaOuter = %f, viaHole = %f;
    const copperClearance = %f, slotToTrack = %f, boardToTh = %f;
    const diffSkewMax = %f;
    const cur = await eda.pcb_Drc.getCurrentRuleConfiguration();
    const spacing = c => {
      try { return c.config.Spacing["Safe Spacing"].copperThickness1oz
                    .tables["1"].content[0][0]; } catch (e) { return null; }
    };
    const trackOf = c => {
      try { return c.config.Physics.Track.copperThickness1oz.form.data["1"]
                    .defaultValue; } catch (e) { return null; }
    };
    out.spacing = spacing(cur);
    const safe = cur.config.Spacing["Safe Spacing"].copperThickness1oz
                    .tables["1"].content;
    out.copperBefore = safe.slice(0, 7).map((r, i) => r.slice(0, i + 1));
    for (let r = 0; r <= 6; r++)
      for (let c = 0; c <= r; c++) safe[r][c] = copperClearance;
    for (let c = 0; c <= 6; c++) safe[8][c] = slotToTrack;
    safe[11][2] = boardToTh;
    const diffForm = cur.config.Physics["Differential Pair"]
                        .differentialPair.form;
    out.diffSkewBefore = diffForm.differentailPairLenTolerMax;
    diffForm.differentailPairLenTolerMax = diffSkewMax;
    out.trackBefore = trackOf(cur);
    const viaForm = cur.config.Physics["Via Size"].viaSize.form;
    out.viaBefore = [viaForm.viaOuterdiameterDefault,
                     viaForm.viaInnerdiameterDefault,
                     viaForm.viaOuterdiameterMin,
                     viaForm.viaInnerdiameterMin];
    for (const k of Object.keys(cur.config.Physics.Track)) {
      const f = cur.config.Physics.Track[k].form;
      if (f && f.data) for (const i of Object.keys(f.data))
        f.data[i].defaultValue = width;
    }
    viaForm.viaOuterdiameterDefault = viaOuter;
    viaForm.viaInnerdiameterDefault = viaHole;
    viaForm.viaOuterdiameterMin = viaOuter;
    viaForm.viaInnerdiameterMin = viaHole;
    out.returned = await eda.pcb_Drc.overwriteCurrentRuleConfiguration(
      cur.config);
    if (out.returned === undefined) out.returned = "undefined";
    out.trackAfter = trackOf(await eda.pcb_Drc.getCurrentRuleConfiguration());
    const after = await eda.pcb_Drc.getCurrentRuleConfiguration();
    const afterVia = after.config.Physics["Via Size"].viaSize.form;
    const afterSafe = after.config.Spacing["Safe Spacing"].copperThickness1oz
                         .tables["1"].content;
    out.copperAfter = afterSafe.slice(0, 7)
                               .map((r, i) => r.slice(0, i + 1));
    out.slotCopperAfter = afterSafe[8].slice(0, 7);
    out.boardThAfter = afterSafe[11][2];
    out.diffSkewAfter = after.config.Physics["Differential Pair"]
                              .differentialPair.form
                              .differentailPairLenTolerMax;
    out.viaAfter = [afterVia.viaOuterdiameterDefault,
                    afterVia.viaInnerdiameterDefault,
                    afterVia.viaOuterdiameterMin,
                    afterVia.viaInnerdiameterMin];
    const known = new Set(await eda.pcb_Net.getAllNetsName() || []);
    out.pairs = []; out.missingNets = [];
    for (const p of pairs) {
      if (!known.has(p[1]) || !known.has(p[2])) {
        out.missingNets.push(p[0] + ": " + p[1] + "/" + p[2]);
        continue;
      }
      const ok = await eda.pcb_Drc.createDifferentialPair(p[0], p[1], p[2]);
      out.pairs.push([p[0], !!ok]);
    }
    out.now = await eda.pcb_Drc.getCurrentRuleConfigurationName();
    return out;
    """ % (json.dumps(DIFF_PAIRS), TRACK_DEFAULT_MM,
             VIA_OUTER_MM, VIA_HOLE_MM, COPPER_CLEARANCE_MM,
             SLOT_TO_TRACK_MM, BOARD_OUTLINE_TO_TH_MM,
             DIFF_PAIR_SKEW_MAX_MM)
    got = execute(js, timeout=240.0)
    if got.get("err"):
        raise SystemExit(got["err"])
    # overwriteCurrentRuleConfiguration returns undefined rather than the
    # documented boolean, and an undefined value disappears from the JSON
    # entirely -- so "did it work" has to be answered by reading a number
    # back out, not by believing the return.
    print(f"  track-to-track spacing {got['spacing']} mm "
          f"(two-layer target {COPPER_CLEARANCE_MM} mm)")
    flat_copper = [v for row in got["copperAfter"] for v in row]
    if any(abs(v - COPPER_CLEARANCE_MM) > 1e-5 for v in flat_copper):
        raise SystemExit("the copper clearance matrix did not take")
    if any(abs(v - SLOT_TO_TRACK_MM) > 1e-5
           for v in got["slotCopperAfter"]):
        raise SystemExit("the slot-to-copper clearance row did not take")
    if abs(got["boardThAfter"] - BOARD_OUTLINE_TO_TH_MM) > 1e-5:
        raise SystemExit("the board-outline-to-TH clearance did not take")
    if abs(got["diffSkewAfter"] - DIFF_PAIR_SKEW_MAX_MM) > 1e-5:
        raise SystemExit("the differential-pair skew tolerance did not take")
    print(f"  general copper clearance -> {COPPER_CLEARANCE_MM} mm")
    print(f"  slot-to-copper clearance -> {SLOT_TO_TRACK_MM} mm")
    print(f"  board-outline-to-TH clearance -> {BOARD_OUTLINE_TO_TH_MM} mm")
    print(f"  differential skew {got['diffSkewBefore']} -> "
          f"{got['diffSkewAfter']} mm")
    print(f"  default track width {got['trackBefore']} -> {got['trackAfter']} "
          f"mm (call returned {got['returned']})")
    if abs((got["trackAfter"] or 0) - TRACK_DEFAULT_MM) > 1e-6:
        raise SystemExit("the track width did not take")
    print(f"  default via {got['viaBefore']} -> {got['viaAfter']} mm")
    # EasyEDA stores these in mil and returns the converted decimal; the
    # round-trip differs by about 0.000002 mm at 0.45 mm.
    if any(abs(a - b) > 1e-5 for a, b in zip(
            got["viaAfter"],
            (VIA_OUTER_MM, VIA_HOLE_MM, VIA_OUTER_MM, VIA_HOLE_MM))):
        raise SystemExit("the via dimensions did not take")
    for name, ok in got["pairs"]:
        print(f"  differential pair {name}: {'set' if ok else 'REFUSED'}")
    if got["missingNets"]:
        # A net named here that the board does not have is a rule that
        # will never fire, which is indistinguishable from a rule that
        # passes. Say it out loud.
        raise SystemExit("these nets are not on the board, so their rule "
                         "would be silently inert: " +
                         ", ".join(got["missingNets"]))
    return got


def drc():
    """Run non-interactive DRC when the bridge request can remain open."""
    js = """
    const ok = await eda.pcb_Drc.check(true, false, false);
    return {passed: !!ok};
    """
    got = execute(js, timeout=300.0)
    print(f"  DRC: {'passed' if got['passed'] else 'errors found'}")
    if not got["passed"]:
        raise SystemExit("EasyEDA DRC found errors; read the DRC panel")
    return got["passed"]


def main():
    build.open_project_pcb()
    s = state()
    print(f"\n  current rules: {s['current']}")
    print(f"  differential pairs: {s['pairs'] or 'none'}")
    print(f"  nets on the board: {len(s['nets'] or [])}")

    changed = "--apply" in sys.argv
    if changed:
        print("\napply:")
        apply()
    if "--drc" in sys.argv:
        print("\ndrc:")
        drc()
    elif changed:
        print("\n(DRC not run -- pass --drc after the board is complete.)")
    else:
        print("\n(report only -- pass --apply to set rules or --drc to check)")


if __name__ == "__main__":
    main()
