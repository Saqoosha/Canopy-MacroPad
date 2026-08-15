"""Make the board's rules mean something, and name the pairs.

An earlier round spent an afternoon arguing about 48 DRC errors without
ever establishing what the rules being violated were. They turn out to
be a configuration called 自定义配置 whose track-to-track spacing is
0.102 mm -- and JLCPCB's own published four-layer capability is 0.0889,
so the board is already held to the stricter of the two. That settles
the argument in the direction nobody checked: the rules were fine.

The client also ships JLCPCB's capability as a preset, and the obvious
move is to load it. It does not work, silently: the preset and the live
configuration disagree about the shape of the same table, so the
overwrite returns undefined and changes nothing. Since the live rules are
the stricter pair anyway, this file leaves them alone and changes only
what actually needed changing.

Two more things the autorouter cannot know unless told:

  USB_DP/USB_DM is a differential pair. Unpaired, a router draws two
  unrelated wires that happen to end up near each other, and the first
  time anybody notices is when a host enumerates intermittently.


    python3 rules.py            report
    python3 rules.py --apply    set them
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
# it would buy nothing anyway: the board's track-to-track spacing is
# 0.102 mm where JLCPCB's published four-layer capability is 0.0889, so
# the rules already in force are the stricter pair. Being stricter than
# the fab is the safe direction to be wrong in.
#
# What DID need changing is the default track width. 0.254 mm cannot pass
# between the pads of a 0.4 mm-pitch QFN-56, which is the hardest escape
# on this board; 0.15 mm can, carries far more than any signal here needs
# at 1 oz, and leaves the 0.127 minimum untouched as the floor. Power does
# not depend on it -- GND and 3V3 ride the inner planes.
TRACK_DEFAULT_MM = 0.15

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
# GND and 3V3 ride the inner planes, so nothing here wants a wider track
# than the 0.15 mm default.


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
    out.trackBefore = trackOf(cur);
    for (const k of Object.keys(cur.config.Physics.Track)) {
      const f = cur.config.Physics.Track[k].form;
      if (f && f.data) for (const i of Object.keys(f.data))
        f.data[i].defaultValue = width;
    }
    out.returned = await eda.pcb_Drc.overwriteCurrentRuleConfiguration(
      cur.config);
    if (out.returned === undefined) out.returned = "undefined";
    out.trackAfter = trackOf(await eda.pcb_Drc.getCurrentRuleConfiguration());
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
    """ % (json.dumps(DIFF_PAIRS), TRACK_DEFAULT_MM)
    got = execute(js, timeout=240.0)
    if got.get("err"):
        raise SystemExit(got["err"])
    # overwriteCurrentRuleConfiguration returns undefined rather than the
    # documented boolean, and an undefined value disappears from the JSON
    # entirely -- so "did it work" has to be answered by reading a number
    # back out, not by believing the return.
    print(f"  track-to-track spacing {got['spacing']} mm "
          f"(JLCPCB four-layer capability is 0.0889, so this is stricter)")
    print(f"  default track width {got['trackBefore']} -> {got['trackAfter']} "
          f"mm (call returned {got['returned']})")
    if abs((got["trackAfter"] or 0) - TRACK_DEFAULT_MM) > 1e-6:
        raise SystemExit("the track width did not take")
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
    """Run DRC. Usually unreachable from here -- see below.

    The bridge enforces its own 30 s request timeout, and the `timeout`
    passed to execute() does not raise it. A DRC pass over this board runs
    longer than that, so this call comes back as a bridge timeout while
    the check is still running inside the client and finishes fine. Run
    DRC from the client's own UI and read the result there; this function
    is kept for small boards and to make the limitation findable.
    """
    js = """
    const ok = await eda.pcb_Drc.check(true, true, false);
    return {passed: !!ok};
    """
    got = execute(js, timeout=300.0)
    print(f"  DRC: {'passed' if got['passed'] else 'errors found'}")
    return got["passed"]


def main():
    build.open_project_pcb()
    s = state()
    print(f"\n  current rules: {s['current']}")
    print(f"  differential pairs: {s['pairs'] or 'none'}")
    print(f"  nets on the board: {len(s['nets'] or [])}")

    if "--apply" not in sys.argv:
        print("\n(report only -- pass --apply to set them)")
        return
    print("\napply:")
    apply()
    if "--drc" in sys.argv:
        print("\ndrc:")
        drc()
    else:
        print("\n(DRC not run -- it outlasts the bridge's 30 s request "
              "timeout on this board. Run it in the client.)")


if __name__ == "__main__":
    main()
