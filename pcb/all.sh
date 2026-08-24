#!/bin/sh
# Build the board's copper, in the one order that works.
#
# The order is the whole content of this file, and every step of it was
# learned by getting it wrong:
#
#   1. Correct the two project-local footprints, strip the old copper, and
#      apply the functional placement. This is a
#      rebuild, not an incremental reroute.
#   2. Install the two-layer pours and reserve the Top 3V3 backbone.
#   3. Reserve constrained U3 power and signal exits in dependency order.
#   4. Route the remaining signals after those corridors are fixed.
#   5. Other 3V3 pads, through ordinary vias to the Top pour.
#   6. Enclosed power pads, routed around the signal escapes.
#   7. Same-net duplicate pads left as islands, joined to existing copper.
#   8. Cover every connected pad centre so EasyEDA retires its ratlines.
#   9. Rebuild fills, require Net-panel Ratlines (0), verify, then save.
#
# Run from pcb/. Each step verifies itself; audit.py must stay silent
# throughout and connect.py must end with nothing.
set -e
cd "$(dirname "$0")"

echo "=== 0. rounded board edge ==="
python3 footprint_fixes.py --apply
python3 board_edge.py --apply
python3 rules.py --apply
python3 stack.py --apply

echo "=== 1. clean placement and silk ==="
python3 layout.py --apply
python3 silk.py --apply

echo "=== 1a. outer-layer power pours and 3V3 backbone ==="
python3 planes.py --apply --defer-rebuild
python3 power_rail.py --apply

echo "=== 1b. assembly-safe RP2040 thermal fanout ==="
python3 thermal_fanout.py --apply

echo "=== 2. U3 power exits ==="
# Pre-stitching every U3 supply pin blocks the crystal and USB escape
# corridors. U3.48/U3.49 are the only pair that cannot be added later,
# and they share one via outside the QFN.
# C8.1 also needs a plane via before the signal fanout encloses it; the
# following local trace then brings U3.22 onto that same connected island.
MPAD_STITCH_ONLY_PADS=U3.48,U3.49,C8.1,C9.1 python3 stitch.py --apply
python3 power_local.py --apply
MPAD_CRITICAL_NETS=XIN,XOUT,DVDD python3 critical_signals.py --apply
MPAD_STITCH_ONLY_PADS=C7.1,C10.1,C11.1,C12.1,C13.1,U3.1,U3.10,U3.33,U3.42,U3.43,U3.44 python3 stitch.py --apply
MPAD_U3_BRIDGES=upper python3 u3_3v3_bridge.py --apply
MPAD_CRITICAL_NETS=USB_DP,USB_DM python3 critical_signals.py --apply
MPAD_U3_BRIDGES=lower python3 u3_3v3_bridge.py --apply
MPAD_CRITICAL_NETS=QSPI_SD0,QSPI_SCLK,QSPI_SD3,QSPI_SS,QSPI_SD1,QSPI_SD2,PIXEL,PIXEL1,PIXEL2,PIXEL3,PIXEL4,PIXEL5,KEY0,KEY1,KEY2,KEY3,KEY4,KEY5 python3 critical_signals.py --apply
python3 vcc_local_bridges.py --apply
python3 gnd_tree.py --apply

echo "=== 3. signals ==="
python3 route.py --apply

echo "=== 4. remaining Top-plane 3V3 pads ==="
MPAD_STITCH_SKIP=U3 python3 stitch.py --apply

echo "=== 5. the enclosed ones ==="
python3 stitch_hard.py --apply

echo "=== 6. anything still an island ==="
python3 stitch_last.py --apply

echo "=== 7. EasyEDA pad-centre ties ==="
python3 center_ties.py --apply

echo "=== verify ==="
python3 planes.py --rebuild
python3 plane_ratlines.py --apply
python3 audit.py --control
python3 audit.py
python3 thermal_fanout.py
python3 via_in_pad.py
python3 connect.py
python3 polish.py
python3 rules.py
python3 -c 'from bridge import execute; ok=execute("return await eda.pcb_Document.save();"); assert ok is True, ok; print("saved")'
echo "=== run Check DRC in the EasyEDA panel; the API call exceeds the bridge timeout ==="
