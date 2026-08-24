#!/bin/sh
# Adafruit's own STEP models for the three boards. Every board dimension in
# params.py was read out of these, so this is where those numbers came
# from -- not a datasheet, not a product page. The files themselves are
# not committed (3.5 MB of third-party CAD the build does not need) and
# nothing here imports them at build time; they exist so a claimed
# measurement can be re-taken.
#
#   sh ref/fetch.sh
#   .venv/bin/python -c "from build123d import import_step; \
#       c = import_step('ref/qtpy-rp2040.step'); print(c.bounding_box())"
set -eu
cd "$(dirname "$0")"
base=https://raw.githubusercontent.com/adafruit/Adafruit_CAD_Parts/main

curl -fsSL -o qtpy-rp2040.step "$base/4900%20QTPy%20RP2040/4900%20QTPY-RP2040.step"
curl -fsSL -o neokey-1x4.step  "$base/4980%20NeoKey%201x4%20QT/4980%20NeoKey%201x4%20QT.step"
# The breakout's model is the only one of the three that includes its
# hot-swap socket, which is why BREAKOUT_T and the socket footprint could
# be measured rather than assumed.
curl -fsSL -o neokey-breakout.step "$base/4978%20NeoKey%20Breakout/4978%20NeoKey%20Breakout.step"
# koktoh/keyswitch_model, CC BY-NC-SA 4.0. KiCad frame: z=0 is the PCB
# top. product.py loads this for the viewer; the build does not.
curl -fsSL -o choc-v2.step \
    https://raw.githubusercontent.com/koktoh/keyswitch_model/master/choc/v2/step/red.step
ls -la ./*.step
