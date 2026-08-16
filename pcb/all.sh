#!/bin/sh
# Build the board's copper, in the one order that works.
#
# The order is the whole content of this file, and every step of it was
# learned by getting it wrong:
#
#   1. Correct the two project-local footprints, strip the old copper, and
#      apply the functional placement. This is a
#      rebuild, not an incremental reroute.
#   2. Reserve the one constrained shared U3 power exit.
#   3. Signals. They own every remaining QFN escape corridor.
#   4. Other power pads, straight to the inner planes where a via fits.
#   5. Enclosed power pads, routed around the signal escapes.
#   6. Same-net duplicate pads left as islands, joined to existing copper.
#   7. Cover every connected pad centre so EasyEDA retires its ratlines.
#   8. Rebuild the plane fills, verify geometry/connectivity, then save.
#
# Run from pcb/. Each step verifies itself; audit.py must stay silent
# throughout and connect.py must end with nothing.
set -e
cd "$(dirname "$0")"

echo "=== 0. rounded board edge ==="
python3 footprint_fixes.py --apply
python3 board_edge.py --apply
python3 rules.py --apply

echo "=== 1. clean placement and silk ==="
python3 layout.py --apply
python3 silk.py --apply

echo "=== 2. U3 power exits ==="
# Pre-stitching every U3 supply pin blocks the crystal and USB escape
# corridors. U3.48/U3.49 are the only pair that cannot be added later,
# and they share one via outside the QFN.
# C8.1 also needs a plane via before the signal fanout encloses it; the
# following local trace then brings U3.22 onto that same connected island.
MPAD_STITCH_ONLY_PADS=U3.48,U3.49,C8.1,C9.1 python3 stitch.py --apply
python3 power_local.py --apply

echo "=== 3. signals ==="
python3 route.py --apply

echo "=== 4. remaining power pads ==="
MPAD_STITCH_SKIP=U3 python3 stitch.py --apply

echo "=== 5. the enclosed ones ==="
python3 stitch_hard.py --apply

echo "=== 6. anything still an island ==="
python3 stitch_last.py --apply

echo "=== 7. EasyEDA pad-centre ties ==="
python3 center_ties.py --apply

echo "=== verify ==="
python3 planes.py --rebuild
python3 audit.py --control
python3 audit.py
python3 via_in_pad.py
python3 connect.py
python3 polish.py
python3 rules.py --drc
python3 -c 'from bridge import execute; ok=execute("return await eda.pcb_Document.save();"); assert ok is True, ok; print("saved")'
