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
DEV_CHOC_SOCKET = "f3e2517f939147fe98be0c77b26c4c09"  # Kailh CPG135001S30,
# the Choc v1 hot-swap socket, shared by v2 -- no separate v2 part exists.
# Footprint CONN-SMD_HOTPLUGPAKAGE__C9900010116, LCSC C9900010116.
DEV_PIXEL = "d9e1e1a9f4bb4f1e8bb56ab67689f9e6"        # SK6812MINI-E_C5149201,
# matched on lib_Device.search("SK6812MINI-E") against LCSC_PIXEL below.

# LCSC numbers for the BOM, from the spec.
LCSC_RP2040 = "C2040"
LCSC_PIXEL = "C5149201"          # SK6812MINI-E, reverse mount

# --- the pixel ---------------------------------------------------------
# Reverse-mount pixel under the board, shining up through an opening into the
# switch's own window. Every number here is off foostan/crkbd's
# keyswitch_choc12_hotswap_1u + YS-SK6812MINI-E, not derived -- see the
# design spec's "The cell, borrowed rather than derived" -- because the MX
# cell this board used to clone from Adafruit's NeoKey 1x4 does not fit a
# Choc switch and there is no Choc board in hand to measure directly. The
# offset has two independent witnesses: 46 switch/pixel pairs on Corne's own
# Choc board measure 4.737-4.749 along the key axis, and marbastlib's Choc
# add-on carries an alignment arrow its author drew at 4.7.
#
# The opening is a RECTANGLE, not a round hole, same shape choice as the MX
# cell it replaces -- Corne cuts 3.6 x 3.1 for this same SK6812MINI-E part.
PIXEL_OFFSET_MM = (0.0, -4.74)      # switch y 10.795 -> pixel y 6.055
PIXEL_OPENING_MM = (3.6, 3.1)       # milled opening, crkbd choc12_hotswap_1u
PIXEL_PADS = [                      # bottom side, 1.7 x 0.825 each
    ((2.8, -0.7), (1.7, 0.825)),
    ((2.8, 0.7), (1.7, 0.825)),
    ((-2.8, -0.7), (1.7, 0.825)),
    ((-2.8, 0.7), (1.7, 0.825)),
]
# All six pixels here share their switch's x exactly -- crkbd's own layout
# has no chain-routing nudge to avoid copying, unlike the NeoKey's -- so
# PIXEL_OFFSET_MM's x stays 0.0.

# --- switch holes ----------------------------------------------------------
# Offsets are from the switch centre, in mm, +y towards the board's back.
#
# MX and Choc hot-swap holes do not fit in one position -- the alignment
# posts alone sit 0.42 mm apart where they need 1.86 -- so this board is
# Choc v2 only and there is no combo footprint. Every row below is off
# foostan/crkbd's keyswitch_choc12_hotswap_1u, not derived, because this
# project has neither a Choc v2 board nor a Choc v2 switch in hand to
# measure, and four separate figures read from drawings elsewhere in this
# design turned out to be wrong in ways no arithmetic would have caught.
#
# A round hole's size is its diameter (mm). The v2 mount is not round: it
# is an oblong slot, (width, height) in mm. EPCB_PrimitivePadHoleType has
# exactly two shapes, ROUND and SLOT (see pcb/README.md) -- there is no
# OVAL hole type, only an OVAL *pad* shape paired with a SLOT hole. So a
# non-plated oblong hole is pad=["OVAL", w, h], hole=["SLOT", w, h], and
# SLOT's length argument cannot go below its diameter argument (h >= w
# here, so that never binds).
#
# The centre is Choc v2's Ø5.00, sized to its switch's mounting boss --
# a fatter centre pin than a plain switch pin, which is what the combo
# footprint used to have to carry when this board still meant to take MX
# too.
SWITCH_HOLES = [
    ("centre", (0.00, 0.00), 5.00),           # switch mounting boss
    ("pin_a", (0.00, 5.90), 3.00),            # switch pin
    ("pin_b", (5.00, 3.70), 3.00),            # switch pin
    ("post_l", (-5.50, 0.00), 1.90),          # alignment post
    ("post_r", (5.50, 0.00), 1.90),           # alignment post
    ("v2_mount", (-5.00, -5.15), (1.50, 2.00)),  # v2 mount, OVAL not round
]

# The Kailh socket's own solder pads, bottom side. These are what the socket
# is hand-soldered to after assembly.
SOCKET_PADS = [
    ((8.1, 3.7), (2.3, 2.6)),
    ((-3.1, 5.9), (2.3, 2.6)),
]
