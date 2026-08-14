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
# A third source exists now, and it does not move this number: Adafruit's
# own Choc board (adafruit/Adafruit-NeoKey-CHOC-Breakout-PCB) places SW1 at
# (9.525, 9.525) and LED1 at (9.525, 4.826), which computes to a 4.699 mm
# offset -- close to 4.7 but not equal to crkbd's 4.737-4.749, and the gap
# is the LED package, not disagreement between sources. Adafruit's Choc
# board uses a 3535 part (NEO3535_REVERSE); crkbd uses the 3528 SK6812MINI-E.
# This board's DEV_PIXEL is the SK6812MINI-E (see LCSC_PIXEL below), the
# same package crkbd uses, not the one Adafruit's Choc board uses -- so
# crkbd's 4.737-4.749 is the source that matches this board's actual part,
# and marbastlib's 4.7 sits between the two because it's a hand-drawn
# alignment arrow, not a package-specific measurement. Do not "correct"
# this to 4.7 or to 4.699 -- both are the right number for a different LED
# package than the one this board actually places.
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

# The SK6812MINI-E's pad-number-to-signal mapping. Cited source: the
# datasheet for LCSC C5149201 (this board's own DEV_PIXEL part) --
# eda.lib_Symbol.get() does not carry pin data (its keys are name,
# libraryType, uuid, libraryUuid, classification, type, description,
# subPartNames, confirmed live; see pcb/README.md), so this cannot come
# from the library and has to come from the datasheet.
PIXEL_PAD_SIGNALS = {
    "1": "VDD",
    "2": "DOUT",
    "3": "GND",
    "4": "DIN",
}

# The orientation this board's pixels must be placed in, as a sign pair
# (x, y) per signal -- not a property of the part, a property of the
# chain. Two independent reference boards agree on it: Adafruit's own
# Choc board (adafruit/Adafruit-NeoKey-CHOC-Breakout-PCB) and crkbd both
# put DOUT on +x and DIN on -x, so a chain running switch 0 through
# switch 5 left to right feeds DOUT of one pixel straight into DIN of the
# next. The reverse -- DOUT on -x, DIN on +x, which is what this board had
# before this constant existed to check for it -- makes every hop double
# back past its own component, six times over.
PIXEL_SIGNAL_QUADRANT = {
    "VDD": (1, -1),
    "DOUT": (1, 1),
    "GND": (-1, 1),
    "DIN": (-1, -1),
}

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

# The EasyEDA CPG135001S30 device's own origin sits at the midpoint of its
# two solder pads, not at the switch centre -- confirmed live: placed with
# no offset, its pads read back at (+-5.78, +-1.10) mm from where it was
# asked to go, nowhere near either SOCKET_PADS entry. build.py's checks
# never caught this because they only verified the component's origin, not
# its pads. SOCKET_OFFSET_MM is that midpoint, derived from SOCKET_PADS
# rather than restated: ((8.1 + -3.1) / 2, (3.7 + 5.9) / 2) = (2.5, 4.8).
#
# Orientation differs too: crkbd's +x pad is the lower one (y 3.7); the
# EasyEDA device's +x pad is the upper one. Placing the device on
# EPCB_LayerId.BOTTOM with rotation 0 mirrors it in y (confirmed live --
# the only transform pcb_PrimitiveComponent.create() exposes besides a
# rotation angle is which copper layer it goes on, and a layer swap alone,
# with no rotation, produces exactly this y-mirror for this footprint).
# That also happens to match the design spec: everything but the switch
# pads lives on the board's back face, so BOTTOM is where the socket
# belongs regardless of the mirror.
SOCKET_OFFSET_MM = (
    (SOCKET_PADS[0][0][0] + SOCKET_PADS[1][0][0]) / 2,
    (SOCKET_PADS[0][0][1] + SOCKET_PADS[1][0][1]) / 2,
)

# --- RP2040 GPIO assignment -------------------------------------------------
# This board must run Adafruit's released CircuitPython UF2 for the QT Py
# RP2040 unmodified (see the design spec's "The firmware that is already
# written"), so the six key inputs and the pixel chain have to land on the
# exact GPIO numbers that build's `board` module already names -- otherwise
# `board.MOSI` and friends stop meaning the pin they've always meant. The
# mapping below is read off `ports/raspberrypi/boards/adafruit_qtpy_rp2040/
# pins.c`, not chosen freely: only these eleven GPIO are broken out to a
# name on that board, and only these are candidates at all.
QTPY_PIN_TO_GPIO = {
    "MOSI": 3, "MISO": 4, "RX": 5, "SCK": 6, "TX": 20,
    "SDA": 24, "SCL": 25, "A3": 26, "A2": 27, "A1": 28, "A0": 29,
}

# Which six (of the eleven) go to keys, and which one to the pixel chain, is
# not this file's decision -- firmware/code.py already made it, independent
# of and before this schematic task existed:
#   KEY_PIN_NAMES = ("MOSI", "MISO", "SCK", "TX", "RX", "SDA")
#   PIXEL_PIN_NAME = "SCL"
# Restating the same six-plus-one here rather than importing firmware/code.py
# (CircuitPython, not importable outside a board) is a duplication this
# project already accepts elsewhere -- case/params.py restates board
# dimensions with their source named rather than reaching into firmware/.
# If firmware/code.py's tuple ever changes, this table has to change with it;
# nothing enforces that automatically.
KEY_PIN_NAMES = ("MOSI", "MISO", "SCK", "TX", "RX", "SDA")
PIXEL_PIN_NAME = "SCL"
KEY_GPIO = tuple(QTPY_PIN_TO_GPIO[name] for name in KEY_PIN_NAMES)   # (3,4,6,20,5,24)
PIXEL_GPIO = QTPY_PIN_TO_GPIO[PIXEL_PIN_NAME]                        # 25

# GPIO12 (`NEOPIXEL`) is deliberately not a candidate at all, let alone the
# chain: on a QT Py it is gated by `NEOPIXEL_POWER` (GPIO11), and a pixel
# line that needs a second pin driven high before it lights is a failure
# mode with no symptom -- it would look identical to a dead LED. The chain
# goes on GPIO25 (`SCL`), an ordinary GPIO with no such gate.

# --- RP2040 schematic parts --------------------------------------------------
# Every uuid below was found with lib_Device.search() / getByLcscIds() and
# confirmed live by placing it and reading the placement back -- see
# schematic.py and the task report. LIB_UUID (above) is the same local
# system library every other device in this file comes from.
DEV_RP2040 = "a550c651585f4e7a9cc06e26cce54f4f"   # QFN-56, confirmed by the
# task brief itself, not found by search here. Its own supplierId reads
# LCSC C2961140, not the C2040 that LCSC_RP2040 below names -- C2040 is a
# *different* device in this library (uuid 88b1c95c0db24581afa4abe322d74d5d,
# footprint "LQFN-56"), also a real RP2040, also QFN-56 7x7 P0.4mm. The task
# brief's uuid is the one actually placed; LCSC_RP2040 is a pre-existing
# constant this task did not write and did not resolve -- flagged in the
# task report, not silently fixed here.
DEV_FLASH = "e300585d7e454be69ca119a810fc9014"    # W25Q64JVSSIQ_C2904572,
# SOIC-8, matches LCSC_PIXEL-style sourcing: found with getByLcscIds("C2904572"),
# the exact LCSC number the design spec names for the 8 MB QSPI flash.
DEV_CRYSTAL = "1a1f6ba3e1b445e4a784383e06e56b40"  # ABM8-272-T3, 12 MHz,
# LCSC C9900091606 (read off the placed part's own netlist "Supplier Part",
# same reasoning as the netlist-matching note on DEV_RP2040 below).
# Confirmed by the task brief; this is also the crystal the RP2040 hardware
# design guide's minimal example uses and recommends by name.
DEV_LDO = "35815374a88d4f49879eb1dd7ad35185"      # XC6206P332MR-G_C5446,
# SOT-23-3, 3.3 V, confirmed by the task brief.
DEV_USB_C = "730e76758f9742ca9ca85c73f4ec0ecd"    # TYPE-C-31-M-12, LCSC
# C165948 -- exact name match against the task brief's "search
# TYPE-C-31-M-12", not a fuzzy pick off a longer results list.
DEV_ESD = "e931d537a1bc4fb7b633b601571c876a"      # USBLC6-2SC6, LCSC C323793,
# SOT-23-6 -- exact name match, same reasoning.
DEV_BOOT_SW = "38630614a58f4650bd5eefe9a5f79d9a"  # TS-1187A-B-A-B, LCSC
# C318884, a 4-pin SMD tactile switch (opposite pairs bridged) -- not named
# in the spec's BOM by part number, only as "BOOT button"; this is a
# commonly-stocked JLCPCB part in the size class the RP2040 hardware design
# guide's own BOOT header implies.

# Passives. All 0402, all found by cross-checking lib_Device.search()'s
# fuzzy results against lib_Device.getByLcscIds()'s authoritative
# `otherProperty.Value` for the exact same code -- search() here does not
# reliably filter by value (confirmed live: distinct value queries returned
# the same result set), so every uuid below is the one whose *value* was
# read back and matched, not the one search ranked first.
DEV_R_27R = "9323f3adb93843ac85e5d4c603a03bbc"   # 27 Ohm, LCSC C25100 (Extended
# Part -- no Basic-Part 27R 0402 turned up). USB_DP/USB_DM series termination,
# the value the RP2040 datasheet's pin table states outright ("A 27Ohm series
# termination resistor is required on each pin").
DEV_R_5K1 = "3614094eae9e47dbbbde1f877b2c30ef"   # 5.1 kOhm, LCSC C25905, Basic
# Part. CC1/CC2 pull-downs -- not an RP2040 value at all, it is the USB
# Type-C specification's Rd for a UFP device advertising default current;
# sourced here because the RP2040 hardware design guide's own minimal
# example uses micro-USB and has no CC resistors to copy.
DEV_R_1K = "17aa4e57569d4d22adc28d945ba5559d"    # 1 kOhm, LCSC C11702, Basic
# Part. Two uses, both from the RP2040 hardware design guide by name: R5,
# the crystal's XOUT-side series damping resistor ("along with a 1kOhm
# series resistor (R5), is a good value to prevent the crystal being
# over-driven"), and the BOOT button's own series resistor (called R1 in
# the guide, in series between QSPI_SS and the button-to-ground path).
DEV_C_100N = "2eaf9ba597d94b93917d2b625402739a"  # 100 nF, LCSC C1525, Basic
# Part. Per-power-pin decoupling, the guide's own general rule ("we
# recommend the use of a 100nF capacitor per power pin").
DEV_C_15P = "5a5ba8db3efe4a4faf8328cf031b538f"   # 15 pF, LCSC C1548, Basic
# Part. Crystal load caps -- the guide's own worked example value (15 pF
# each side gives a 7.5 pF series combination, plus ~3 pF of parasitic
# capacitance, landing close to the ABM8-272-T3's specified 10 pF load).
DEV_C_1U = "115c3169541a48b3ba9c88523dfbcdee"    # 1 uF, LCSC C52923, Basic
# Part. Four uses: VREG_IN and VREG_VOUT (the guide: "place 1uF capacitors
# close to both the input (VREG_IN) and the output (VREG_VOUT)"), and the
# LDO's own input/output caps (the XC6206 datasheet's typical application
# circuit, LCSC C479053: 1 uF ceramic on both VIN and VOUT).

# LCSC ("Supplier Part") numbers for every DEV_* above, keyed the same way.
# schematic.py's assert_nets() matches netlist components against these
# rather than against the DEV_* uuid directly, because a placed component's
# own getState_Component().uuid -- and the netlist's "Device" field -- is
# NOT the uuid passed to create(). Confirmed live: DEV_RP2040 is
# "a550c651...", but the placed RP2040's own reported component uuid reads
# "a67eb1f3155fc4f9" -- 16 hex characters, not 32, and unrelated-looking.
# EasyEDA clones the library device into the project's own local library on
# placement and hands back *that* copy's uuid from then on; the LCSC number
# survives the clone unchanged and is what actually matches.
LCSC_OF = {
    DEV_RP2040: "C2961140",
    DEV_FLASH: "C2904572",
    DEV_CRYSTAL: "C9900091606",
    DEV_LDO: "C5446",
    DEV_USB_C: "C165948",
    DEV_ESD: "C323793",
    DEV_BOOT_SW: "C318884",
    DEV_R_27R: "C25100",
    DEV_R_5K1: "C25905",
    DEV_R_1K: "C11702",
    DEV_C_100N: "C1525",
    DEV_C_15P: "C1548",
    DEV_C_1U: "C52923",
}
