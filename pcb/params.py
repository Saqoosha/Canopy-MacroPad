# pcb/params.py
"""The key field's numbers, and the only place they are written.

This file used to be case/params.py's job, derived from the NeoKey and the
4978 breakout. The boards are gone and the copper is ours now, so the PCB
owns the field and the case imports it. Changing the pitch here moves the
sockets, the pixels and the plate holes together, which is the whole point
of the inversion.

Stdlib only, deliberately: case/.venv must be able to import it without
installing anything, and so must a fresh machine.
"""

# --- units -----------------------------------------------------------------
# EasyEDA's PCB editor works in 1 mil. 1 mm = 1/0.0254 mil.
MIL_PER_MM = 1.0 / 0.0254


def mm_to_mil(v):
    """Millimetres to whole mils.

    Rounds, and every number this design uses is exact at 1 mil: 19.05 is
    0.75 inch (750), 9.525 is 375, 10.795 is 425.
    """
    return round(v * MIL_PER_MM)


# --- the key field ---------------------------------------------------------
# Pitch and depth are inherited from the NeoKey 1x4 the pad was built on, so
# every keycap and every printed plate hole that already works still does.
SWITCH_PITCH = 19.05
KEY_COUNT = 6
FIRST_SWITCH_X = 9.525          # half a pitch in from the field's left edge
SWITCH_Y = 10.795               # NeoKey 4980's switch centre, read off its .brd

KEY_FIELD_W = KEY_COUNT * SWITCH_PITCH      # 114.30
KEY_FIELD_D = 21.59                         # the NeoKey's depth, kept


def switch_centres_mm():
    """Board-local switch centres, left to right, key 0 first."""
    return [(FIRST_SWITCH_X + n * SWITCH_PITCH, SWITCH_Y) for n in range(KEY_COUNT)]


# --- the board -------------------------------------------------------------
# The USB-C receptacle is the one part that does not fit under the plate, so
# it gets a tab off the right end rather than growing the whole outline.
USB_TAB_W = 7.30
BOARD_W = KEY_FIELD_W + USB_TAB_W           # 121.60
BOARD_D = KEY_FIELD_D                       # 21.59
BOARD_T = 1.60
BOARD_LAYERS = 4

# --- parts -----------------------------------------------------------------
# EasyEDA library identifiers, found with lib_Device.search() and confirmed by
# placing them. The library UUID is the local system library.
LIB_UUID = "0819f05c4eef4c71ace90d822a990e87"
DEV_MX_SOCKET = "96b68765c94c47e5851d5c1124075178"   # Kailh CPG151101S11
DEV_PIXEL = "d9e1e1a9f4bb4f1e8bb56ab67689f9e6"        # SK6812MINI-E_C5149201,
# matched on lib_Device.search("SK6812MINI-E") against LCSC_PIXEL below.

# LCSC numbers for the BOM, from the spec.
LCSC_RP2040 = "C2040"
LCSC_PIXEL = "C5149201"          # SK6812MINI-E, reverse mount

# --- the pixel ---------------------------------------------------------
# Reverse-mount pixel under the board, shining up through an opening into the
# switch's own window. Every number here is cloned from Adafruit's NeoKey 1x4
# board file rather than chosen -- see pcb/NOTICE.md -- because that board
# lights these exact switches today and Saqoosha has confirmed the fit on the
# part.
#
# The opening is a RECTANGLE, not a round hole. That was the first thing a
# guess got wrong here: Eagle layer 46 is milling, and NEO3535_REVERSE draws
# a rectangle there spanning x -1.927..1.927 and y -1.727..1.727.
PIXEL_OFFSET_MM = (0.0, -5.08)      # switch y 10.795 -> pixel y 5.715
PIXEL_OPENING_MM = (3.854, 3.454)   # milled slot, from Eagle layer 46
PIXEL_PADS = [                      # bottom side, 1.2 x 0.9 each
    ((2.65, -0.75), (1.2, 0.9)),
    ((2.65, 0.75), (1.2, 0.9)),
    ((-2.65, -0.75), (1.2, 0.9)),
    ((-2.65, 0.75), (1.2, 0.9)),
]
# Do not copy the NeoKey's x nudge: two of its four pixels sit 0.127 off
# their switch's x (chain routing, not a dimension). All six pixels here
# share their switch's x exactly, so PIXEL_OFFSET_MM's x stays 0.0.

# --- switch holes ----------------------------------------------------------
# Offsets are from the switch centre, in mm, +y towards the board's back.
#
# The MX rows are MEASURED, out of Adafruit's own "NeoKey 1x4 QT I2C.brd" --
# the board this project's working pad is built on. They are not derived from
# a switch drawing, and the difference is not academic: a first pass written
# from drawings had the pin drills at 1.50 (forgetting that the hot-swap
# socket's barrel passes through, not just the switch pin) and omitted the
# two plate-mount alignment posts entirely, which would have refused every
# five-pin switch this pad uses.
#
# The Choc v2 rows are READ OFF Kailh's CPG135301D01 figure and have not been
# checked against a part or a board. They are the weaker half of this table.
#
# The centre is Choc v2's Ø5.00 rather than MX's Ø3.9, because the hole only
# has to clear a centre post -- the plate locates the switch -- so the larger
# swallows the smaller and the reverse would not.
SWITCH_HOLES = [
    ("centre", (0.00, 0.00), 5.00),        # choc v2 drawing; MX board has 3.9
    ("mx_pin_a", (-3.81, 2.54), 3.0635),   # measured
    ("mx_pin_b", (2.54, 5.08), 3.0635),    # measured
    ("mx_post_l", (-5.08, 0.00), 1.8135),  # measured, plate-mount alignment
    ("mx_post_r", (5.08, 0.00), 1.8135),   # measured, plate-mount alignment
    ("choc_a", (-5.00, 3.80), 1.20),       # drawing, unverified
    ("choc_b", (5.00, 3.80), 1.20),        # drawing, unverified
    ("choc_c", (0.00, 5.90), 1.60),        # drawing, unverified
]

# The Kailh socket's own solder pads, bottom side, measured off the same
# board. These are what the socket is hand-soldered to after assembly.
SOCKET_PADS = [
    ((6.09, 5.08), (2.55, 2.50)),
    ((-7.36, 2.50), (2.55, 2.50)),
]
