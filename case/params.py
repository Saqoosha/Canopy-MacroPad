"""Every dimension the case depends on, and where each number came from.

Nothing here is a guess unless it says so. Board figures were read out of
Adafruit's own STEP models in `ref/` and out of the Eagle `.brd` files;
the switch figures are the Cherry MX mounting spec. When a number is a
tolerance to be tuned on the printer, it says so and the coupon tests it.

Print target: Bambu A1 mini, 0.4 nozzle, 0.2 layer, PLA Basic.

Two layouts share this file, chosen with MPAD_LAYOUT:

  stacked  (default)  the QT Py lies under the keys, face down.
                      97.6 x 27.6 x 17.5 -- compact and tall.
  inline              the QT Py sits beside the keys, face up, USB-C out
                      the right edge. Long and low instead.

Everything above the "Derived" line is common to both; the split is only
in where the QT Py goes and what that does to the Z stack.
"""

import os

LAYOUT = os.environ.get("MPAD_LAYOUT", "stacked")
if LAYOUT not in ("stacked", "inline"):
    raise SystemExit(f"MPAD_LAYOUT must be 'stacked' or 'inline', got {LAYOUT!r}")
STACKED = LAYOUT == "stacked"

# --- NeoKey 1x4 QT (ADA-4980) -------------------------------------------
# Outline and hole positions: Adafruit-NeoKey-1x4-PCB Eagle .brd.
# Thickness: measured off ref/neokey-1x4.step (1.570, not the nominal 1.6).
NEOKEY_W = 76.20
NEOKEY_D = 21.59
NEOKEY_T = 1.57
NEOKEY_CORNER_R = 2.54

# M2.5 mounting holes, PCB-local, origin at the front-left corner.
NEOKEY_HOLES = [(19.05, 2.54), (57.15, 2.54), (19.05, 19.05), (57.15, 19.05)]

# Switch centres, PCB-local. Pitch is exactly 19.05 and the board is 4x that.
NEOKEY_SW_Y = 10.795
NEOKEY_SW_X = [9.525, 28.575, 47.625, 66.675]

# Kailh hot-swap sockets hang off the underside. The Adafruit STEP does not
# model them (its Z range is 0..4.53, all above the board), so this is the
# Kailh CPG151101S11 datasheet height, not a measurement of that file.
NEOKEY_SOCKET_DROP = 1.85

# --- QT Py RP2040 (ADA-4900) --------------------------------------------
# All measured off ref/qtpy-rp2040.step.
QTPY_W = 17.78
QTPY_D = 20.701
QTPY_T = 1.57
QTPY_CORNER_R = 2.54
QTPY_BOTTOM_DROP = 1.10  # tallest part below the board

# USB-C receptacle. X/Y/Z are PCB-local; the board's back edge is at
# y = QTPY_D, so the shell overhangs it by USB_OVERHANG.
USB_W = 8.94
USB_H = 4.20
USB_Z_FROM_PCB_BOTTOM = 0.57  # receptacle wraps the board edge
USB_OVERHANG = 0.969
USB_CENTER_X = 8.89  # dead centre of the board

# Tact switches, PCB-local centres and height above the PCB top face.
# Which one is BOOT and which is RESET is not settled here -- the .sch net
# names did not resolve -- so both get the same hole and the same ring.
QTPY_BTN_A = (12.510, 2.794)
QTPY_BTN_B = (5.156, 9.398)
QTPY_BTN_H = 1.94

# --- Cherry MX mounting spec --------------------------------------------
# wiki.ai03.com/books/case-and-plate-design -- plate hole 14 +/- 0.05 with
# a 0.3 max corner radius, plate 1.5 +/- 0.1, and 5.0 from plate top face
# to PCB top face. PLATE_T sits at the top of that band so it lands on a
# whole number of 0.2 layers.
SWITCH_PITCH = 19.05
PLATE_T = 1.60  # 8 layers at 0.2
PLATE_TOP_TO_PCB = 5.00
# The spec says 0.3 max, and 0.3 is what a sharp-cornered 14.0 switch
# body just barely fouls. The mock keeps its corners square on purpose --
# a real MX housing is kinder than that -- so the model gives way instead
# and the check stays worth reading.
PLATE_HOLE_R = 0.20

# Settled on the coupon, not calculated: a Durock Ice King seats in this
# with the right amount of push on an A1 mini in PLA Basic at 0.4/0.2.
# The 0.15 over nominal is the printer pulling the hole in, and it is now
# a measurement rather than the guess it started as. Re-run the coupon if
# the filament or the nozzle changes -- the number is about the machine,
# not about the switch.
SWITCH_HOLE = 14.15

# --- Fasteners ----------------------------------------------------------
# M3 button head, self-tapping into printed posts. No heat-set inserts,
# and the PCB is not screwed at all: shell standoffs drop locating pegs
# into its M2.5 holes and the bottom plate presses it up against them. The
# only screws in the design hold the two printed halves together.
#
# Note the two thread sizes are unrelated. M3 is the case fastener; the
# 2.5 below is the NeoKey's own mounting hole, which the peg sits in and
# no screw ever enters.
#
# Settled on the coupon against a real M3, like SWITCH_HOLE and for the
# same reason: 2.50 was the arithmetic answer and the printed shell said
# otherwise, hard enough that it was the first thing anyone noticed about
# the part. Four posts, 2.50 through 2.95, same screw minutes apart --
# 2.95 is the one that bites without a fight.
#
# It is worth being clear that this is not where the arithmetic pointed.
# This machine pulls a hole in by about 0.15, which is what SWITCH_HOLE's
# 14.15 measures, so 2.95 arrives as ~2.80 -- 0.93x major, well above the
# 0.83x the tables want for M3 into PLA. The tables do not know this
# screw or this plastic and the coupon does, so the coupon wins. Re-run
# it when the filament or the nozzle changes, exactly as for SWITCH_HOLE.
#
# What is NOT known: 2.95 won at the top of the sweep, so nothing above it
# was tried and the diameter where the thread starts stripping is still
# unmeasured. That is the failure this number has -- it does not split a
# post, it lets go on the second or third time the case is opened -- so
# if a post ever strips, the answer is below 2.95 and the sweep needs
# re-running downward rather than up.
PILOT_DIA = 2.95
POST_DIA = 5.60  # 1.33 of wall around the pilot

# One post per entry on the coupon, each engraved with its own diameter.
# This is the range that was actually driven, kept as the record of it --
# a future re-run wants to move it, not repeat it, since 2.50 is now known
# tight and the open question sits above the top end.
PILOT_SWEEP = (2.50, 2.65, 2.80, 2.95)

# What the hole-only coupon drills, one hole per entry per row. 3.40 is
# kept as the first entry deliberately -- it is the one on the built
# plate, so it is the known-tight reference the others are felt against,
# exactly as 2.50 was for the pilot. A screw dropped through the right
# one falls through under its own weight and still has its head fully
# caught by the counterbore.
#
# Worth knowing on a re-run: this reads as a diameter sweep and is really
# a ring-width sweep, since the ring narrows as the hole grows. That is
# why it needed a second row before it meant anything.
CLEAR_SWEEP = (3.40, 3.55, 3.70, 3.85)

# The counterbore is a void Ø6.10 across and the hole above it is smaller,
# so the layer that closes the counterbore is a ring printed over air,
# all the way round. It sags, and what it sags into is the top of the
# bore. That is what put filament in every hole of the first clearance
# coupon, and the built bottom plate has the same feature -- so it was
# always a better candidate than hole shrink for why the screws were
# guided rather than cleared.
#
# A chamfer trades bearing area for printability: c of 45-degree cone
# above the counterbore shortens the unsupported ring by c and lets the
# rest of the transition climb at an angle the printer can hold. It
# cannot be taken all the way -- the ring *is* the seat the head bears
# on, so at c = (SCREW_HEAD_DIA - dia) / 2 there is nothing left to bear
# on at all. This is the one number here that is squeezed from both ends.
#
# 0.60 is what the two-row coupon settled on: the C0.60 row ran clean at
# 3.70 and 3.85 where the C0.00 row had filament in all four holes.
# CLEAR_CHAMFER_SWEEP is kept as the record of that comparison, and it is
# the shape a re-run wants -- one row per transition, identical diameters
# across them. A single row cannot tell a diameter answer from a sag
# answer, and will confidently give one of them.
CLEAR_CHAMFER = 0.60
CLEAR_CHAMFER_SWEEP = (0.00, 0.60)

# What the coupon actually measured, and the reason both rows behaved the
# way they did. The unsupported ring is what is left of the counterbore's
# ceiling once the chamfer has eaten into it:
#
#     ring = (SCREW_HEAD_DIA - dia) / 2 - chamfer
#
# and the eight holes sort by it perfectly, in an order neither diameter
# nor chamfer alone produces:
#
#     0.525, 0.600  clean          (3.85 and 3.70 at C0.60)
#     0.675         a little sag   (3.55 at C0.60)
#     0.750 and up  filament in the bore  (3.40 at C0.60, all of C0.00)
#
# So 0.60 is this machine's limit for an annular ceiling printed over
# air, the same kind of constant as SWITCH_HOLE's 0.15 shrink and it
# re-measures with it. CLEAR_RING_MAX is that number and build.py holds
# the design to it -- note it is an upper bound, unlike every other
# clearance here, because the ring is also the seat the screw head bears
# on and shrinking it is not free.
CLEAR_RING_MAX = 0.60

# The columns that hold the NeoKey up are spacers, not fasteners, and
# sizing them off POST_DIA quietly grew them with the screws until they
# pushed through the shell's front wall. They have nothing to do with
# each other -- keep them apart.
# 4.50, not 5.00: the NeoKey's front mounting holes sit 9.06 off centre
# in a cavity that is 11.80 deep, so a wider column leaves 0.24 to the
# wall -- not a collision, and not clearance either once the printer
# has had its say.
COLUMN_DIA = 4.50
# Settled on the coupon, and it took two goes to ask the right question.
#
# 3.40 was tight on the built plate. The first answer was 3.55, on the
# arithmetic that this machine pulls a hole in by ~0.15 so 3.40 arrives
# as ~3.25 against an M3's 3.00. That reasoning is not wrong and it was
# not the cause. The printed coupon came back with filament hanging in
# every bore, which sent the question to CLEAR_CHAMFER below -- and the
# real variable turned out to be neither diameter nor chamfer but what
# they leave between them.
#
# 3.70 is the smallest hole that came out clean AND free with the 0.60
# chamfer under it. 3.85 also passes and was not taken: it buys nothing
# and costs 0.075 more of the seat the screw head sits on.
SCREW_CLEAR_DIA = 3.70

# A lead-in at the mouth of every pilot hole, so the screw has somewhere
# to sit before it starts cutting. A self-tapper meeting a sharp-edged
# hole either wanders or has to be held straight while it bites, which is
# the other half of what "hard to screw in" was -- the diameter above is
# only the first half.
#
# This used to read SCREW_CLEAR_DIA, on the argument that a mouth wider
# than the plate's own hole only opens space the plate already covers.
# That was true while the two numbers agreed and it stopped being true the
# moment the clearance hole moved for a reason of its own -- following it
# to 3.55 would thin the post mouth to 1.03 to chase a screw that is 3.00
# across. What the funnel actually has to catch is the screw's tip, so the
# number belongs to the screw, and 3.40 is the 0.40 of margin around it
# that has always been here. Pinned, and no longer derived from a
# neighbour that turned out to be unrelated.
PILOT_MOUTH_DIA = 3.40

# The depth is the only free number in the funnel: 0.60 puts the flank 21
# degrees off the axis, where a plain 45-degree chamfer would need only
# 0.225, so it is the longer and gentler of the two and still leaves
# engagement above 2x the M3 major. build.py reports what is left.
PILOT_MOUTH_H = 0.60
SCREW_HEAD_DIA = 6.10  # ISO 7380 M3 button head is 5.70
SCREW_HEAD_H = 1.65

# A button head is meant to stand proud, and on the underside of a desk
# device that only works if the feet are taller than it is. Sinking 1.00
# leaves 0.65 of dome showing against 1.50 of foot -- clear by 0.85 --
# and still leaves 1.40 of plate under the head to bear on. Set this to
# 0 for the full domed look and taller feet.
SCREW_SINK = 1.00

# Into the PCB's 2.5 holes. Confirmed on the printed inline shell: the
# board drops on free with a little play, which is what a locating peg
# wants -- it is there to stop the board wandering, not to grip it.
PEG_DIA = 2.30
PEG_H = 1.40  # stops inside the 1.57 board rather than poking out the back

# A plate-mount switch is 14 wide below its flange, so between two keys at
# 19.05 pitch there is 5.05 of air and the standoff has to live inside it.
# 5.00 is not a collision -- it clears by 0.025 a side and the check calls
# it clean, which is exactly the trap: 0.025 is not clearance on a printed
# part, it is the same number as the tolerance. 4.20 is the judgement
# call, not something the check found. Above 5.05 it does become a real
# hit; 6.00 reports 1.016 mm3, which is how this check was proven to fire.
STANDOFF_DIA = 4.20

# --- Case ---------------------------------------------------------------
WALL = 2.00
# 12 layers at 0.2, and the counterbore for a button head eats 1.00 of
# it. What is left is what the head bears on when the screw is tightened.
BOTTOM_T = 2.40
OUTER_CORNER_R = 3.00

# Clearance past the PCB's short edge for the mated Qwiic plug and the
# bend behind it. The receptacle stops inside the board outline, so the
# whole plug body sits outside. Both sides get it, which is what centres
# the key field. 7.0 is deliberately loose: the 50 mm cable has to coil
# somewhere and this is the only place it can.
# Bigger screws had to come from somewhere. A corner post has to sit
# outboard of the *mated Qwiic plug*, not just of the NeoKey's edge, and
# an M3 post is wide enough that at 7.00 it fouled the plug. The bay was
# always the slack in this design.
CABLE_BAY = 8.50

# How far the rigid part of a mated Qwiic plug stands off the face of a
# STEMMA QT receptacle. Most of the JST-SH housing ends up inside the
# receptacle; only about 1.3 stays proud, and past that it is flat ribbon,
# which is allowed to lie across the NeoKey rather than counting as a
# collision. Used to keep walls off the connector, not just off the board.
QWIIC_PLUG_L = 2.50

PCB_SLOP = 0.40  # total, so 0.20 a side

# --- inline layout only -------------------------------------------------
# Beside the keys, the NeoKey fills the cavity front to back, so a screw
# post has nowhere to stand except off the ends of it. One bay at the left
# end, and one gap between the two boards wide enough for a post to sit
# between two mated plugs pointing at each other.
INLINE_LEFT_BAY = 7.00
INLINE_BOARD_GAP = 12.00

# The QT Py lives *under* the NeoKey rather than behind it, which is what
# gets the depth down to one board. Two consequences drive everything
# below:
#
#   It is flipped, component side down. Not for packing -- the envelope is
#   5.87 either way -- but for what you find when you open the case. Face
#   down, taking the bottom plate off puts BOOT and RESET facing you. Face
#   up they would point at the underside of the NeoKey across 2.2 mm of
#   air, and reaching them would mean getting the QT Py out first.
#
#   It sits centred and pushed to the back wall, USB-C pointing out of it
#   and the STEMMA socket facing forward into a 2.5 mm strip that the
#   Qwiic cable arrives along, having come down one of the end bays from
#   the NeoKey's connector 8 mm above.
QTPY_FLIPPED = STACKED
BOARD_CLEAR = 0.40  # air between board envelopes
USB_FLOOR_CLEAR = 0.40  # under the USB-C shell, which is now the low point

# The Adafruit STEP does not model the hot-swap sockets, so this is not a
# fit measured against the file -- it is the datasheet drop plus a margin,
# rounded up. The extra 0.6 over a snug 2.2 also buys wall above the USB
# opening, which is the tightest spot in the shell.
SOCKET_CLEARANCE = 2.80

# 0.20 a side, and confirmed on the printed inline shell: the board goes
# into the pocket without force and without slop.
QTPY_SLOP = 0.40
QTPY_FRAME_W = 1.60  # pocket wall around the QT Py, on the bottom plate
QTPY_RAIL_W = 3.00  # posts under the board's clear margins
QTPY_LIP = 1.00  # ledge the board slides in under, so it cannot lift

# The two strips of the QT Py with nothing on either face, board-local X.
# Everything -- USB shell, both buttons, the STEMMA socket on one side,
# and all four underside parts on the other -- sits between them.
QTPY_CLEAR_X = ((0.40, 3.30), (14.40, 17.40))

# STEMMA QT socket footprint, board-local, for the pocket to keep clear.
QTPY_STEMMA = (4.01, 10.01, -0.09, 4.87)
QTPY_STEMMA_H = 2.96

# How far past that footprint the wall in front of the socket opens up.
# It is the room a thumb and a plug share while mating a connector that
# is already boxed in on three sides. At 1.00 the plug goes in and takes
# some working at, on the printed `inline` shell -- fine, not comfortable.
# Widening it costs a little of the wall that stops the board sliding,
# and the wall below the notch is untouched either way, so 1.5-2.0 is
# the knob to turn if the pocket is ever reprinted.
QTPY_STEMMA_NOTCH = 1.00

USB_CLEAR_W = 1.10  # added to USB_W/USB_H for the back-wall opening
USB_CLEAR_H = 0.80
# Clearance around the plug's overmold inside the flare. The flare's
# depth is not a free choice: it has to start at the receptacle face,
# because that is how far in the plug must reach. What is left of the
# wall in front of it is the visible bezel, and it is whatever the
# recess leaves over -- reported by build.py, not picked here.
USB_PLUG_CLEAR = 0.40

# There is deliberately no hole over BOOT or RESET. They are needed once,
# to write a CircuitPython UF2, and after that a firmware update is a file
# copied to CIRCUITPY over USB. Four screws is a fine price for something
# done once, and an uninterrupted plate is worth more than a paperclip
# port. The buttons still exist as far as the checks are concerned --
# nothing is allowed to press on them.

FOOT_DIA = 8.00
FOOT_H = 2.00
FOOT_RECESS = 0.50  # so a 2.00 foot stands 1.50 proud

# --- Derived: the Z stack -----------------------------------------------
# Z datum is the outside of the bottom plate.
Z_FLOOR = BOTTOM_T

# How far the USB-C shell stands proud of the board face it is nearest.
USB_ABOVE_PCB = USB_Z_FROM_PCB_BOTTOM + USB_H - QTPY_T  # 3.20

if STACKED:
    # Face down under the keys, so the USB shell is the lowest thing in
    # the case and the whole stack is measured up from its clearance.
    Z_USB_BOTTOM = Z_FLOOR + USB_FLOOR_CLEAR
    Z_QTPY_LOW = Z_USB_BOTTOM + USB_ABOVE_PCB
    Z_QTPY_HIGH = Z_QTPY_LOW + QTPY_T + QTPY_BOTTOM_DROP
    Z_BTN_LOW = Z_QTPY_LOW - QTPY_BTN_H
    Z_BTN_HIGH = Z_QTPY_LOW
    Z_STEMMA_LOW = Z_QTPY_LOW - QTPY_STEMMA_H
    Z_STEMMA_HIGH = Z_QTPY_LOW
else:
    # Beside the keys and face up: nothing is stacked, so the board just
    # sits high enough to clear its own underside parts and everything
    # else -- USB shell, buttons, socket -- points at the plate.
    Z_QTPY_LOW = Z_FLOOR + QTPY_BOTTOM_DROP + 0.50
    Z_QTPY_HIGH = Z_QTPY_LOW + QTPY_T + USB_ABOVE_PCB
    Z_USB_BOTTOM = Z_QTPY_LOW + USB_Z_FROM_PCB_BOTTOM
    Z_BTN_LOW = Z_QTPY_LOW + QTPY_T
    Z_BTN_HIGH = Z_BTN_LOW + QTPY_BTN_H
    Z_STEMMA_LOW = Z_QTPY_LOW + QTPY_T
    Z_STEMMA_HIGH = Z_STEMMA_LOW + QTPY_STEMMA_H

# The parts on the board's underside point up when it is turned over and
# down when it is not -- the one thing that genuinely inverts between the
# two layouts, and the one a mock will get silently wrong.
if STACKED:
    Z_UNDER_LOW = Z_QTPY_LOW + QTPY_T
    Z_UNDER_HIGH = Z_UNDER_LOW + QTPY_BOTTOM_DROP
else:
    Z_UNDER_HIGH = Z_QTPY_LOW
    Z_UNDER_LOW = Z_UNDER_HIGH - QTPY_BOTTOM_DROP

Z_USB_TOP = Z_USB_BOTTOM + USB_H

# The NeoKey clears whichever is worse: its own sockets over a bare floor,
# or, when stacked, the QT Py underneath.
Z_NEOKEY_BOTTOM = Z_FLOOR + max(
    SOCKET_CLEARANCE,
    ((Z_QTPY_HIGH - Z_FLOOR) + BOARD_CLEAR + NEOKEY_SOCKET_DROP) if STACKED else 0.0,
)
Z_NEOKEY_TOP = Z_NEOKEY_BOTTOM + NEOKEY_T
Z_PLATE_BOTTOM = Z_NEOKEY_TOP + (PLATE_TOP_TO_PCB - PLATE_T)
Z_PLATE_TOP = Z_PLATE_BOTTOM + PLATE_T
CASE_H = Z_PLATE_TOP

# --- Derived: the plan --------------------------------------------------
# X/Y datum is the centre of the case.
if STACKED:
    # Depth is set by the QT Py, not the NeoKey: it has to leave a mated
    # Qwiic plug room ahead of its socket. Packing tighter -- turning the
    # board 90 degrees into a corner -- is unbuildable, because a screw
    # post has to miss the NeoKey above it and the bottom plate's own
    # columns, which leaves only the end bays, and an end-mounted QT Py
    # fills one of them.
    CASE_W = NEOKEY_W + PCB_SLOP + 2 * (CABLE_BAY + WALL)
    CASE_D = WALL + max(
        NEOKEY_D + PCB_SLOP,
        QTPY_D + QTPY_SLOP + QWIIC_PLUG_L,
    ) + WALL
    NEOKEY_ORIGIN = (-NEOKEY_W / 2, -CASE_D / 2 + WALL + PCB_SLOP / 2)
    QTPY_PLAN_W, QTPY_PLAN_D = QTPY_W, QTPY_D
    QTPY_CX = 0.0
    QTPY_CY = CASE_D / 2 - WALL - QTPY_SLOP / 2 - QTPY_D / 2
else:
    # Turned 90 degrees so USB-C faces the right wall, which puts its
    # STEMMA socket back toward the NeoKey's -- the two connectors end up
    # pointing at each other across the gap, and the cable is a short
    # straight hop with no drop and no detour.
    QTPY_PLAN_W, QTPY_PLAN_D = QTPY_D, QTPY_W
    CASE_W = (
        WALL + INLINE_LEFT_BAY + PCB_SLOP + NEOKEY_W
        + INLINE_BOARD_GAP + QTPY_PLAN_W + QTPY_SLOP / 2 + WALL
    )
    CASE_D = WALL + max(NEOKEY_D + PCB_SLOP, QTPY_PLAN_D + QTPY_SLOP) + WALL
    NEOKEY_ORIGIN = (
        -CASE_W / 2 + WALL + INLINE_LEFT_BAY + PCB_SLOP / 2,
        -CASE_D / 2 + WALL + PCB_SLOP / 2,
    )
    QTPY_CX = (
        NEOKEY_ORIGIN[0] + NEOKEY_W + INLINE_BOARD_GAP + QTPY_PLAN_W / 2
    )
    QTPY_CY = 0.0


def neokey_xy(local):
    """PCB-local (x, y) -> case (x, y)."""
    return (NEOKEY_ORIGIN[0] + local[0], NEOKEY_ORIGIN[1] + local[1])


def qtpy_xy(local):
    """QT Py board-local (x, y) -> case (x, y).

    Stacked, the board is turned over: a mirror about its own Y axis, not
    a rotation, which keeps USB-C at the back and swaps left for right.
    Inline, it is rotated 90 degrees clockwise and left face up, which
    swings USB-C to the right wall. Getting either wrong puts BOOT where
    RESET should be, and nothing downstream would notice.
    """
    dx = local[0] - QTPY_W / 2
    dy = local[1] - QTPY_D / 2
    if STACKED:
        return (QTPY_CX - dx, QTPY_CY + dy)
    return (QTPY_CX + dy, QTPY_CY - dx)


# Board centres, so nothing downstream has to re-derive them. Hard-coding
# the NeoKey's at x=0 is right in one layout and 13 mm wrong in the other,
# and it was wrong in two separate files before this existed.
NEOKEY_CENTER = (NEOKEY_ORIGIN[0] + NEOKEY_W / 2,
                 NEOKEY_ORIGIN[1] + NEOKEY_D / 2)
QTPY_CENTER = (QTPY_CX, QTPY_CY)

SWITCH_XY = [neokey_xy((x, NEOKEY_SW_Y)) for x in NEOKEY_SW_X]
MOUNT_XY = [neokey_xy(h) for h in NEOKEY_HOLES]
BTN_XY = [qtpy_xy(QTPY_BTN_A), qtpy_xy(QTPY_BTN_B)]
# Taken at the board edge the connector actually sits on. Passing y=0
# here happens to be harmless when the board is only mirrored and puts
# the opening on the wrong wall the moment it is rotated.
USB_CX, USB_CY = qtpy_xy((USB_CENTER_X, QTPY_D))

# Which way the connector faces out. The board edge coordinate on that
# axis is the matching member of the pair above.
USB_AXIS = "y" if STACKED else "x"

# A USB-C shell is a stadium, not a rectangle: fully rounded ends, radius
# half its height. Modelling it square made the envelope over-conservative
# at four corners that do not exist, and made the opening the wrong shape.
USB_R = USB_H / 2

# The mated plug's overmold, which is the part that actually decides
# whether the port is usable. Not measured off anything -- cables vary a
# lot -- so it is a common, generous figure: change it if the cable in
# hand is slimmer. The receptacle sits recessed behind the wall face, so
# the overmold has to come *into* the case by that much to seat, and both
# printed parts are in its way, not just the shell.
# Confirmed on the printed inline shell with a real cable: it seats fully
# and leaves about 1 mm around the plug's housing, so the guess was
# generous rather than wrong. Tighten it for a closer-looking port; the
# slack is also what lets a fatter cable work.
USB_PLUG_W = 12.00
USB_PLUG_H = 6.60
USB_PLUG_L = 8.00  # how far it stands off the wall once seated

# Feet are pulled inboard along X until their footprint clears the screw
# heads outright: a foot you have to peel off to reach a screw stops being
# a foot the second time you open the case.
FOOT_XY = [
    (x, y)
    for x in (-CASE_W / 2 + 14.0, CASE_W / 2 - 14.0)
    for y in (-CASE_D / 2 + 7.0, CASE_D / 2 - 7.0)
]
_POST_Y = (
    -CASE_D / 2 + WALL + POST_DIA / 2,
    CASE_D / 2 - WALL - POST_DIA / 2,
)
if STACKED:
    _POST_X = (
        -CASE_W / 2 + WALL + POST_DIA / 2,
        CASE_W / 2 - WALL - POST_DIA / 2,
    )
else:
    # Not the corners. Inline, the NeoKey fills the cavity front to back
    # and the QT Py owns the right end, so the only standing room is the
    # left bay and the gap between the boards -- where a post has to fit
    # between two mated plugs aimed at each other.
    _POST_X = (
        -CASE_W / 2 + WALL + INLINE_LEFT_BAY / 2,
        NEOKEY_ORIGIN[0] + NEOKEY_W + INLINE_BOARD_GAP / 2,
    )
POST_XY = [(x, y) for x in _POST_X for y in _POST_Y]
