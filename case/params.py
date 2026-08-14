"""Every dimension the case depends on, and where each number came from.

Nothing here is a guess unless it says so. Board figures were read out of
Adafruit's own STEP models in `ref/` and out of the Eagle `.brd` files;
the switch figures are the Cherry MX mounting spec. When a number is a
tolerance to be tuned on the printer, it says so and the coupon tests it.

Print target: Bambu A1 mini, 0.4 nozzle, 0.2 layer, PLA Basic.

Two layouts share this file, chosen with MPAD_LAYOUT:

  stacked             the QT Py lies under the keys, face down.
                      135.7 x 27.6 x 17.49 -- compact and tall.
  inline   (default)  the QT Py sits beside the keys, face up, USB-C out
                      the right edge. 158.6 x 25.99 x 13.33 -- long and
                      low instead, and the only one ever printed.

Everything above the "Derived" line is common to both; the split is only
in where the QT Py goes and what that does to the Z stack.
"""

import os

LAYOUT = os.environ.get("MPAD_LAYOUT", "inline")
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

# M2.5 mounting holes, PCB-local, origin at the front-left corner. The
# diameter lives here rather than in the mock that draws them: the peg
# fit is checked against these holes, and a number the check depends on
# should not be the only copy of itself.
NEOKEY_HOLES = [(19.05, 2.54), (57.15, 2.54), (19.05, 19.05), (57.15, 19.05)]
NEOKEY_HOLE_DIA = 2.50  # MOUNTINGHOLE_2.5_PLATED in the .brd

# Switch centres, PCB-local. Pitch is exactly 19.05 and the board is 4x that.
NEOKEY_SW_Y = 10.795
NEOKEY_SW_X = [9.525, 28.575, 47.625, 66.675]

# The STEP has the switch on -z and the case puts the switch side up, so
# the board is turned over to get there and its back face mirrors left to
# right. x only -- the sockets and everything else on that face land
# correctly with this, checked against the assembled unit. Read the
# numbers as the file gives them and mirror once, here, rather than
# mirroring by hand into the table: a table of already-flipped numbers
# cannot be checked against the file it came from.
#
# The STEMMA receptacles are the exception and are placed separately in
# mock.py, on the far side of the board from where the file draws them.
# Which way round a board sits in the case is ONE fact about the board,
# not one fact per feature. Getting that wrong is the whole story of this
# section: the socket, the components and the STEMMA receptacles were
# each turned separately, each time to satisfy the last thing someone had
# pointed at, and the answers contradicted each other because they were
# describing one rigid object with three different orientations.
#
# So: one flag, applied to everything on the board at once. The photograph
# that settles it shows both white receptacles on the far long edge and
# the hot-swap sockets on the near one, which is the file's y reversed.
BOARD_FLIP_X = True    # the switch side goes up, so the back face mirrors
BOARD_FLIP_Y = False   # y is the file's y; only x mirrors


def _flip_y(y0, y1, depth):
    return (depth - y1, depth - y0) if BOARD_FLIP_Y else (y0, y1)


def _face_flip(part, w, d):
    """A component-face box, as the file draws it, into case space.

    Both boards are turned over to put their switch side up, so the face
    that carries everything mirrors left to right. Written once and
    applied per board width, because the NeoKey needs it too now and a
    second copy of this arithmetic is a second chance to get the
    orientation wrong -- which this file has a section about.
    """
    x0, x1, y0, y1, proud = part
    fx0, fx1 = (w - x1, w - x0) if BOARD_FLIP_X else (x0, x1)
    fy0, fy1 = _flip_y(y0, y1, d)
    return (fx0, fx1, fy0, fy1, proud)


def _back_flip(part):
    return _face_flip(part, BREAKOUT_W, BREAKOUT_D)


def _socket_flip(part):
    dx0, dx1, dy0, dy1 = part
    fx0, fx1 = (-dx1, -dx0) if BOARD_FLIP_X else (dx0, dx1)
    fy0, fy1 = (-dy1, -dy0) if BOARD_FLIP_Y else (dy0, dy1)
    return (fx0, fx1, fy0, fy1)


# Everything on the 4978's back face, board-local, as (x0, x1, y0, y1,
# how far it stands proud). Read straight out of ref/neokey-breakout.step
# rather than summarised: the hot-swap socket is a body *plus two solder
# wings*, and a hand-made box around the body alone said a column at the
# back-left corner cleared by 0.586 when the built plate put it through
# the left wing. Anything that decides where a column may stand gets the
# shape the model has, not the shape it is convenient to describe.
_BACK_PARTS_AS_DRAWN = [
    (4.741, 15.641, 11.680, 17.580, 1.830),   # socket body
    (2.241, 4.741, 14.650, 17.150, 1.830),    # socket wing, left
    (15.641, 18.141, 12.110, 14.610, 1.830),  # socket wing, right
    (7.925, 11.125, 4.696, 7.496, 0.930),     # NeoPixel, reverse mount
    (5.802, 7.152, 8.429, 11.129, 1.100),     # 1N4148
    (13.932, 15.532, 6.408, 7.308, 0.800),
    (11.125, 12.465, 6.562, 7.242, 0.244),
    (11.125, 12.465, 4.950, 5.630, 0.244),
    (6.585, 7.925, 6.562, 7.242, 0.244),
    (6.585, 7.925, 4.950, 5.630, 0.244),
]

# The same Kailh socket sits on the NeoKey, whose own STEP does not model
# it, so its three boxes are given relative to a switch centre and reused
# there. Taken from the three 1.830-proud entries above.
_SOCKET_PARTS_AS_DRAWN = [
    (-4.784, 6.116, 0.885, 6.785),
    (-7.284, -4.784, 3.855, 6.355),
    (6.116, 8.616, 1.315, 3.815),
]


# Every solid on the NeoKey's component face, board-local, out of
# ref/neokey-1x4.step and not summarised: 66 of them, deepest first.
# Generated rather than typed, and the file is the check -- re-run the
# enumeration in ref/fetch.sh's docstring and the numbers have to come
# back the same.
#
# The two 2.960 rows are the STEMMA receptacles and the twelve 1.830 rows
# are the hot-swap sockets; mock.py places both of those itself, the
# receptacles because a mated plug is a fact about the cable rather than
# the board, and the sockets because the same three boxes serve the
# breakout. Everything below 1.830 had no representation at all, and one
# of those -- a 0.300-proud part at board-local x 1.048..2.636 -- is the
# closest thing in the whole model to a plate column, at 0.141.
_NEOKEY_FACE_AS_DRAWN = [
    (   0.065,    5.015,   4.620,  10.620, 2.960),
    (  71.185,   76.135,   4.620,  10.620, 2.960),
    (   2.233,    4.733,  14.623,  17.123, 1.830),
    (   4.733,   15.633,  11.653,  17.553, 1.830),
    (  15.633,   18.133,  12.083,  14.583, 1.830),
    (  21.283,   23.783,  14.623,  17.123, 1.830),
    (  23.783,   34.683,  11.653,  17.553, 1.830),
    (  34.683,   37.183,  12.083,  14.583, 1.830),
    (  40.333,   42.833,  14.623,  17.123, 1.830),
    (  42.833,   53.733,  11.653,  17.553, 1.830),
    (  53.733,   56.233,  12.083,  14.583, 1.830),
    (  59.383,   61.883,  14.623,  17.123, 1.830),
    (  61.883,   72.783,  11.653,  17.553, 1.830),
    (  72.783,   75.283,  12.083,  14.583, 1.830),
    (  55.840,   58.840,   7.200,  10.200, 1.400),
    (  59.841,   62.841,   3.136,   6.136, 1.400),
    (  13.936,   16.036,   7.255,   9.255, 1.100),
    (  37.499,   41.498,   6.127,  10.126, 1.000),
    (   8.052,   11.252,   4.315,   7.115, 0.950),
    (  26.975,   30.175,   4.315,   7.115, 0.950),
    (  46.152,   49.352,   4.315,   7.115, 0.950),
    (  65.075,   68.275,   4.315,   7.115, 0.950),
    (   6.154,    7.054,   7.963,   9.563, 0.800),
    (  19.393,   20.993,   6.281,   7.181, 0.800),
    (  23.870,   24.770,   4.978,   6.578, 0.800),
    (  49.556,   51.156,   7.742,   8.642, 0.800),
    (  57.176,   58.776,   5.392,   6.292, 0.800),
    (  57.302,   58.902,  10.980,  11.880, 0.800),
    (  63.368,   64.268,   8.026,   9.626, 0.800),
    (  73.558,   75.158,  15.171,  16.071, 0.800),
    (  73.812,   74.904,  16.688,  17.476, 0.709),
    (  13.334,   16.384,   3.264,   4.864, 0.500),
    (  73.558,   74.002,  16.701,  17.463, 0.306),
    (  74.714,   75.158,  16.701,  17.463, 0.306),
    (  73.564,   75.152,  16.688,  17.476, 0.300),
    (   6.712,    8.052,   4.569,   5.249, 0.264),
    (   6.712,    8.052,   6.181,   6.861, 0.264),
    (  11.252,   12.592,   6.181,   6.861, 0.264),
    (  11.252,   12.592,   4.569,   5.249, 0.264),
    (  25.635,   26.975,   4.569,   5.249, 0.264),
    (  25.635,   26.975,   6.181,   6.861, 0.264),
    (  30.175,   31.515,   6.181,   6.861, 0.264),
    (  30.175,   31.515,   4.569,   5.249, 0.264),
    (  44.812,   46.152,   4.569,   5.249, 0.264),
    (  44.812,   46.152,   6.181,   6.861, 0.264),
    (  49.352,   50.692,   6.181,   6.861, 0.264),
    (  49.352,   50.692,   4.569,   5.249, 0.264),
    (  63.735,   65.075,   4.569,   5.249, 0.264),
    (  63.735,   65.075,   6.181,   6.861, 0.264),
    (  68.275,   69.615,   6.181,   6.861, 0.264),
    (  68.275,   69.615,   4.569,   5.249, 0.264),
    (  37.496,   37.997,   8.728,   9.028, 0.200),
    (  37.496,   37.997,   8.228,   8.528, 0.200),
    (  37.496,   37.997,   7.728,   8.028, 0.200),
    (  37.496,   37.997,   7.228,   7.528, 0.200),
    (  37.496,   37.997,   6.728,   7.028, 0.200),
    (  37.496,   37.997,   9.228,   9.528, 0.200),
    (  38.097,   38.397,   9.628,  10.129, 0.200),
    (  38.597,   38.897,   9.628,  10.129, 0.200),
    (  39.097,   39.397,   9.628,  10.129, 0.200),
    (  39.597,   39.897,   9.628,  10.129, 0.200),
    (  40.097,   40.397,   9.628,  10.129, 0.200),
    (  40.597,   40.897,   9.628,  10.129, 0.200),
    (  53.822,   55.272,   7.276,   9.474, 0.100),
    (  59.868,   62.066,   7.404,   8.854, 0.100),
    (  74.104,   74.612,  16.789,  17.375, 0.008),
]
NEOKEY_BACK_PARTS = [_face_flip(p, NEOKEY_W, NEOKEY_D)
                     for p in _NEOKEY_FACE_AS_DRAWN]

# Kailh hot-swap sockets hang off the underside -- every component on
# either board is on that one face, and the switch side carries nothing
# but the switch. Both STEPs model the sockets, contrary to what this
# comment claimed for a long time: they are there at z 0.400..3.400
# against a board of 0..1.570, so 1.830 proud, and the datasheet's 1.85
# used here is 0.02 conservative rather than the only figure available.
NEOKEY_SOCKET_DROP = 1.85

# --- NeoKey Socket Breakout (ADA-4978), keys 0 and 1 --------------------
# Outline, switch centre and hole positions: Adafruit-NeoKey-Breakout-PCB
# Eagle .brd. Three numbers do all the work and none of them were chosen
# by us: the board is exactly one SWITCH_PITCH wide, its switch sits in
# the middle of that width, and its depth is the NeoKey's to three
# decimals. Butt two onto the NeoKey and the pitch continues with nothing
# to tune.
BREAKOUT_W = 19.05
BREAKOUT_D = 21.59
BREAKOUT_CORNER_R = 2.54
BREAKOUT_SW = (9.525, 10.795)
# 2.54 drill against the NeoKey's 2.5 plated, so PEG_DIA has 0.24 of play
# here instead of 0.20. The peg locates, it does not grip.
BREAKOUT_HOLES = [(1.905, 5.080), (17.145, 16.510)]
# Mirrored here rather than in the tables, now that the width they are
# mirrored about exists.
BREAKOUT_BACK_PARTS = [_back_flip(p) for p in _BACK_PARTS_AS_DRAWN]
SOCKET_PARTS = [_socket_flip(p) for p in _SOCKET_PARTS_AS_DRAWN]
# Drill 2.540 in the .brd, and Ø2.540 again measured off the STEP's own
# board solid -- two independent sources, exact agreement.
BREAKOUT_HOLE_DIA = 2.54
BREAKOUT_COUNT = 2

# Measured off ref/neokey-breakout.step, and it comes out at exactly the
# NeoKey's 1.570 -- which matters, because one plate spans all three
# boards and every board is clamped between a column at Z_NEOKEY_BOTTOM
# and a standoff at Z_NEOKEY_TOP. A board of a different thickness either
# rattles in that gap or does not go into it.
#
# This was a guess for a while, on the grounds of the same fab and the
# same stackup, and the guess was right. It stopped being one when
# somebody looked for the model instead of taking the earlier "Adafruit
# publishes no STEP for this board" at face value: they publish one, in
# the same repository ref/fetch.sh already pulls the other two from.
BREAKOUT_T = 1.57

# They go to the *left* of the NeoKey, and it is the cable that forces
# it: on the right, the NeoKey's socket ends up 114 mm from the QT Py
# against a 50 mm cable.
#
# There used to be a second reason here and it was not true. It said a
# mated Qwiic plug stands 2.50 proud of its board edge while a butted
# breakout's switch body starts 2.525 from that edge, so the two miss by
# 0.025 -- "not clearance, the tolerance". That sentence is correct
# elsewhere in this file, about a standoff and a switch, and it does not
# survive being carried here: the plug hangs *below* the board and the
# switch body stands *above* it, so they were never in the same space to
# be 0.025 apart. A peer session replaced the switch body with the
# hot-swap socket's solder wing, which does share the plug's z band and
# does overlap it by 0.258 in x -- and misses it by 4.03 in y.
#
# Booleaned rather than argued: a mated plug built on the NeoKey's left
# socket reports 0.000 mm3 against the breakout boards and their back
# faces, against the switch bodies, and against both printed parts. It
# passes under the butted breakout in the strip its receptacles occupy,
# where the nearest thing hanging down is the diode, 3.302 away. Moving
# that plug +10.03 in y, onto the wing, turns the same probe red at
# 1.198 mm3, so the clean result is a measurement and not a blind spot.
#
# So the left socket is not blocked, and the only thing keeping the
# breakouts on this side is the cable length above.
#
# So keys 0-1 are the GPIO pair and 2-5 are the NeoKey, left to right,
# and firmware/code.py assigns its index bases the same way round.
BREAKOUT_ORIGINS_LOCAL = [(i * BREAKOUT_W, 0.0) for i in range(BREAKOUT_COUNT)]
NEOKEY_LOCAL = (BREAKOUT_COUNT * BREAKOUT_W, 0.0)

# What the plate spans and what the case is sized around. Derived from
# both boards rather than from a key count times a pitch, so a board that
# turns out not to be the width it should be cannot keep agreeing with
# itself.
KEY_FIELD_W = BREAKOUT_COUNT * BREAKOUT_W + NEOKEY_W
KEY_FIELD_D = max(NEOKEY_D, BREAKOUT_D)

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
# 2.95 won at the top of the sweep, so the diameter where the thread
# starts stripping was never found, and it is deliberately not being
# looked for. Finding it means driving screws into posts until they fail,
# which is a destructive test whose answer changes nothing: 2.95 works,
# and the response to a post that strips is to come down from 2.95, not
# to know how far up the cliff was. Recorded so nobody spends a print on
# it. That failure mode is still the real one -- it does not split a post,
# it lets go on the second or third time the case is opened -- so if one
# ever does, re-run the sweep downward.
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

# How much shorter the shell's standoffs are than the space they sit in.
# Without it the stack from the floor to the plate underside -- column,
# board, standoff -- adds up to exactly the height available, so the case
# closes only if every board is exactly NEOKEY_T and every layer prints
# exactly 0.20. FR4 is 1.6 nominal with a real tolerance, and the first
# printed six-key unit came out with a 0.2 gap at the centre of the seam,
# pressing down to 0.1: the two halves were being held apart by the boards
# themselves. The screws close it at both ends, and there is no screw
# within 60 mm of the middle.
#
# The columns still set the board's height from below; this only stops the
# standoff turning into a jack. The board gains this much vertical play,
# which costs nothing -- a plate-mount switch clips into the plate and
# holds the board through its socket, which is what actually locates it.
BOARD_CLAMP_SLACK = 0.20

# --- the wire route ----------------------------------------------------
# Five wires have to get from the QT Py at one end to the far breakout at
# the other: 3V, GND, MOSI for the pixel chain, and one switch line per
# breakout. Nothing in the case was ever shaped for them, and a scan of
# the space under the boards says why that nearly did not work.
#
# The plate's columns block outright; a board component blocks if it
# hangs lower than the wire is tall. That second rule is why raising
# UNDER_BOARD_AIR changed the shape of this and not just its size.
#
# At 3.36 of air there was exactly one lane. A hot-swap socket left 1.53
# and a 26AWG wire passed under it; a STEMMA receptacle left 0.40 and
# nothing did, so the receptacles walled off the near half of the board
# and the lane was y +0.55 to +5.35, four wires abreast. At 4.36 a
# receptacle leaves 1.40 and the scan opens to -5.35 .. +5.35, nine
# abreast.
#
# The channel is cut to that whole width rather than the old strip,
# because 1.40 against a 1.30 wire is 0.10 -- the sort of margin this
# repository has been burned by twice, and not something to lay a
# harness on. In the channel a receptacle leaves 2.60 instead, and the
# Qwiic cable, which hangs in that same near half, gets somewhere to sit
# for the first time.
#
# The limit is the columns, board-local because they are placed
# board-local: the y 2.54 row's Ø4.5 reaches in to 4.79 and the y 19.05
# row's to 16.80, so the band is those minus a 0.40 wall each side.
#
# So the plate carries a channel along it. Depth buys the second layer
# that headroom alone does not: 1.53 + WIRE_CHANNEL_D clears two 1.30
# wires stacked, which is what makes five fit with room to spare. It also
# gives the bundle somewhere to stay while the case is closed, which the
# design had no answer for at all.
#
# The top is pulled in off the free band to leave a wall between the
# trench and those columns; the untrimmed 16.795 would have left 0.005.
# What a trench takes away is not a collision, so nothing booleans this
# -- the margins in build.py are the whole guard, and they are why these
# numbers are here rather than inline in parts.py.
#
# Board-local, and that is the point. Written as a case-space pair it
# described one layout: stacked seats the field 0.805 further back to fit
# the QT Py underneath, and the same two numbers put the trench 0.400
# *into* a NeoKey column there while inline stayed green. Everything the
# lane is about -- the boards' own components, the columns that stand
# under them -- is fixed relative to the boards, so the lane is too.
# Only inline was scanned; stacked has never been printed, and it gets
# the same band by construction rather than by measurement.
WIRE_LANE_LOCAL = (5.195, 16.395)
WIRE_CHANNEL_D = 1.20   # leaves 1.20 of plate under it

# --- how the two printed halves close on each other --------------------
# A butt joint at Z_FLOOR was all there was, and it does not survive being
# 158 mm long with a screw only at each end: the first six-key unit came
# out with 0.2 of gap at the centre, and giving the board stack slack
# above only took it to 0.1. What is left is the parts themselves not
# being flat -- a 158 x 26 plate and a 158 mm shell both bow a little off
# the bed -- and a butt joint has nothing to pull them together with.
#
# Two features, and they are not alternatives. The step aligns the halves
# and hides whatever gap remains inside the joint; the snap is the only
# one that actually pulls. Together the step also gives the snap
# something to grab, so no tab has to pass through the plate and nothing
# shows on the underside.
#
# The plate's top SEAM_STEP_H becomes a tongue inset by SEAM_STEP_W, and
# the shell's walls come down beside it. 1.00 x 1.20 keeps 1.00 of wall
# outboard of the tongue at WALL 2.00.
SEAM_STEP_W = 1.00
SEAM_STEP_H = 1.20

SEAM_FIT = 0.20        # total clearance between skirt and tongue

# **The step is the whole joint. There was a snap and it is gone**, and
# the reason is arithmetic rather than a number that wanted tuning.
#
# Barbs on the inside of the skirt dropped into a groove round the
# tongue, swept 0.30 to 0.70 of reach on a coupon. All four came back too
# weak, 0.70 the best of them and still no lock, and both complaints --
# hard to fit, does not hold -- are the same fault: **the skirt is not a
# spring.** It is 0.90 thick over a 1.20 free length, so even the
# shallowest hook asks it for 19% surface strain where PLA yields near 2.
# It never bent. It was forced.
#
# A cantilever that deflects 0.40 at 2% wants roughly 5 mm of length and
# the plate is 2.40 thick, so no hook in this geometry can work and a
# sweep upward would only have found a stiffer press fit. A third screw
# at mid-span is out too: the boards fill the case wall to wall there,
# 0.200 between the field and the cavity, against the 5.60 a post needs.
#
# So the step does what the step already did -- align the halves and put
# the residual gap inside the joint instead of on the outside. If the
# centre ever lifts, the next thing to try is a magnet pair under the
# boards, not a plastic spring.

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

# How much air a board needs under it. Every component on either board is
# on the one face and the switch side carries nothing, so this is set by
# whatever hangs down furthest -- and that is not the hot-swap socket.
#
# The STEMMA QT receptacle is 2.96, against the socket's 1.85, and for a
# long time it was modelled on the wrong face and therefore not counted.
# At 2.80 the case closes on a NeoKey whose receptacles are pressing into
# the bottom plate: it shuts, and the boards inside are strained. That is
# what "the model says 0.000 mm3" is worth when the model has a part on
# the wrong side.
# The air on top of that used to be 0.40, which is a fit and nothing
# more. It is 1.40 now, on Saqoosha's call after wiring the first unit:
# five wires would not lie down under the plate, and a taller case is
# cheaper than a cleverer route. The whole case grows by the same 1.00,
# 12.33 -> 13.33 in inline.
#
# It buys more than height. A wire passes under something only if that
# thing leaves more room than the wire is thick, so the lane's width was
# set by what a 26AWG wire could get under -- and a STEMMA receptacle at
# 2.96 left 0.40, which is nothing. At 4.36 it leaves 1.40, so the
# receptacles stop being walls and the lane opens up rather than merely
# deepening. WIRE_LANE_LOCAL was re-scanned against this, not guessed.
UNDER_BOARD_MAX = 2.96   # STEMMA QT receptacle, the deepest of them
UNDER_BOARD_AIR = 1.40
SOCKET_CLEARANCE = UNDER_BOARD_MAX + UNDER_BOARD_AIR

# 0.20 a side, and confirmed on the printed inline shell: the board goes
# into the pocket without force and without slop.
QTPY_SLOP = 0.40
QTPY_FRAME_W = 1.60  # pocket wall around the QT Py, on the bottom plate
QTPY_RAIL_W = 3.00  # posts under the board's clear margins

# How far the rail holds off the components at its inner end. The clear
# strips are clear of components by eye, but the second one starts at
# 14.40 and the underside parts reach 14.414 -- 0.014 inside, which did
# not matter until a rail was pulled onto that boundary.
#
# There used to be a QTPY_RAIL_INSET here as well, holding the rail 1.80
# off the board's outer edge so it missed the castellated pads. It is
# gone: it narrowed the rail along its whole length to clear three pads,
# and QTPY_PADS_USED cuts it back only where those three are.
QTPY_RAIL_CLEAR = 0.30
QTPY_LIP = 1.00  # ledge the board slides in under, so it cannot lift

# The two strips of the QT Py with nothing on either face, board-local X.
# Everything -- USB shell, both buttons, the STEMMA socket on one side,
# and every underside part -- sits between them.
#
# QTPY_UNDER_X is where the underside parts really begin and end, read
# out of ref/qtpy-rp2040.step: 40 solids hang below the board face and
# they span 3.700 to 14.414. The strips below were written by hand and
# the second one starts at 14.40, which is 0.014 *inside* that -- a
# hand-drawn envelope that disagreed with the model by a hair, and did
# not matter until a rail was narrowed onto exactly that boundary.
QTPY_UNDER_X = (3.700, 14.414)
QTPY_CLEAR_X = ((0.40, 3.30), (14.40, 17.40))

# Every solid that hangs off the QT Py's underside, board-local, out of
# ref/qtpy-rp2040.step. Forty of them, generated rather than typed.
#
# mock.py drew this as a single hand-written box, 4.900..12.700 by
# 3.400..20.000, and **24 of the forty fall outside it** -- so a rail
# could stand on a real part and the interference boolean would report
# zero, which is the same failure the NeoKey's face had and the breakout
# had before that. Third board, same shape: a stand-in summarised by hand
# is a check that agrees with you.
QTPY_UNDER_PARTS = [
    (  5.914,   8.614,  18.553,  19.903, 1.100),
    (  5.644,  12.644,   3.498,  10.498, 1.000),
    (  3.838,   4.738,   1.430,   3.030, 0.800),
    (  4.922,   5.822,  11.430,  13.030, 0.800),
    (  6.572,  10.572,  13.937,  17.939, 0.800),
    ( 12.814,  14.414,  11.755,  12.655, 0.800),
    (  9.253,  11.753,   0.613,   2.613, 0.700),
    (  3.700,   4.200,  11.248,  11.448, 0.500),
    (  3.700,   4.200,  11.448,  12.048, 0.500),
    (  3.700,   4.200,  12.048,  12.248, 0.500),
    (  5.596,   5.796,   1.630,   2.130, 0.500),
    (  5.605,   6.105,  17.178,  17.378, 0.500),
    (  5.605,   6.105,  16.578,  17.178, 0.500),
    (  5.605,   6.105,  16.378,  16.578, 0.500),
    (  5.796,   6.396,   1.630,   2.130, 0.500),
    (  6.396,   6.596,   1.630,   2.130, 0.500),
    (  6.519,   7.019,  12.162,  12.362, 0.500),
    (  6.519,   7.019,  11.562,  12.162, 0.500),
    (  6.519,   7.019,  11.362,  11.562, 0.500),
    (  6.676,   6.876,  13.047,  13.547, 0.500),
    (  6.876,   7.476,  13.047,  13.547, 0.500),
    (  7.476,   7.676,  13.047,  13.547, 0.500),
    (  8.450,   8.950,   1.024,   1.224, 0.500),
    (  8.450,   8.950,   1.224,   1.824, 0.500),
    (  8.450,   8.950,   1.824,   2.024, 0.500),
    (  9.635,   9.835,  19.079,  19.579, 0.500),
    (  9.835,  10.435,  19.079,  19.579, 0.500),
    ( 10.435,  10.635,  19.079,  19.579, 0.500),
    ( 12.390,  12.590,   2.036,   2.536, 0.500),
    ( 12.390,  12.590,   0.702,   1.202, 0.500),
    ( 12.590,  13.190,   2.036,   2.536, 0.500),
    ( 12.590,  13.190,   0.702,   1.202, 0.500),
    ( 13.190,  13.390,   2.036,   2.536, 0.500),
    ( 13.190,  13.390,   0.702,   1.202, 0.500),
    ( 13.428,  13.928,   9.876,  10.076, 0.500),
    ( 13.428,  13.928,  10.076,  10.676, 0.500),
    ( 13.428,  13.928,  10.676,  10.876, 0.500),
    ( 13.745,  14.245,   5.075,   5.275, 0.500),
    ( 13.745,  14.245,   4.475,   5.075, 0.500),
    ( 13.745,  14.245,   4.275,   4.475, 0.500),
]

# The pads this build actually solders to, board-local. All three are on
# JP3, the right-hand row, read out of Adafruit-QT-Py-RP2040-PCB's .brd
# with the through-hole row at x 16.510 and the castellated edge at
# 17.780. Power comes off the NeoKey, so these three are the whole list.
QTPY_PAD_X = 16.510
QTPY_PADS_USED = (
    ("SCK",   5.271),
    ("MISO",  7.811),
    ("MOSI", 10.351),
)
# How far the rail is cut back around them, for the pad, its fillet and
# the wire standing off it. The rail runs the full width of the clear
# strip again and gives way only here, which is Saqoosha's call: a rail
# narrowed everywhere buys clearance it does not need along most of its
# length and loses the support it exists for.
QTPY_PAD_RELIEF = 1.60

# ...and the wall those three wires then have to get through. The QT Py
# sits in a pocket whose frame runs all the way round, so a wire soldered
# to JP3 has the board's own edge to leave from and nowhere to go: the
# -x wall stands between the pocket and the key field.
#
# Fourth time this case has fitted a board and then made itself
# impossible to wire -- both Qwiic sockets, the USB port, and now this.
# Measured rather than guessed: a 1.30 bundle laid from the pads to the
# channel shares 10.240 mm3 with the shell and nothing with the plate,
# all of it in that one wall.
#
# It starts above the screw post at y -8.20, whose 5.60 diameter reaches
# -5.40 and is not going anywhere, and stops short of the plate above --
# so what is left is a bridge rather than a missing wall.
QTPY_WIRE_NOTCH_W = 6.00
QTPY_WIRE_NOTCH_H = 2.20

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
    CASE_W = KEY_FIELD_W + PCB_SLOP + 2 * (CABLE_BAY + WALL)
    CASE_D = WALL + max(
        KEY_FIELD_D + PCB_SLOP,
        QTPY_D + QTPY_SLOP + QWIIC_PLUG_L,
    ) + WALL
    FIELD_ORIGIN = (-KEY_FIELD_W / 2, -CASE_D / 2 + WALL + PCB_SLOP / 2)
    QTPY_PLAN_W, QTPY_PLAN_D = QTPY_W, QTPY_D
    # Not centred any more, and this is the one number the six-key field
    # forced. The NeoKey's mounting holes are 19.05 and 57.15 across its
    # own board; with two breakouts ahead of it the board no longer
    # starts at the field's left edge, and the first pair of holes lands
    # at case x = 0 -- which is where the QT Py used to sit. 116 mm3 of
    # column through the middle of it, found by the interference boolean
    # rather than by looking.
    #
    # 19.05 is the centre of the widest gap the columns leave (0 to
    # 38.10), and it is a pitch rather than a fudge: 19.05 of room each
    # side against the 11.14 a half-board plus a column radius needs. The
    # cost is that USB-C stops coming out of the middle of the back wall,
    # which is why the check that asserted that is now a clearance margin
    # instead. `stacked` has never been printed, so this trades a
    # cosmetic property of an unbuilt layout for one that closes.
    QTPY_CX = SWITCH_PITCH
    QTPY_CY = CASE_D / 2 - WALL - QTPY_SLOP / 2 - QTPY_D / 2
else:
    # Turned 90 degrees so USB-C faces the right wall, which puts its
    # STEMMA socket back toward the NeoKey's -- the two connectors end up
    # pointing at each other across the gap, and the cable is a short
    # straight hop with no drop and no detour.
    QTPY_PLAN_W, QTPY_PLAN_D = QTPY_D, QTPY_W
    CASE_W = (
        WALL + INLINE_LEFT_BAY + PCB_SLOP + KEY_FIELD_W
        + INLINE_BOARD_GAP + QTPY_PLAN_W + QTPY_SLOP / 2 + WALL
    )
    CASE_D = WALL + max(KEY_FIELD_D + PCB_SLOP, QTPY_PLAN_D + QTPY_SLOP) + WALL
    FIELD_ORIGIN = (
        -CASE_W / 2 + WALL + INLINE_LEFT_BAY + PCB_SLOP / 2,
        -CASE_D / 2 + WALL + PCB_SLOP / 2,
    )
    QTPY_CX = (
        FIELD_ORIGIN[0] + KEY_FIELD_W + INLINE_BOARD_GAP + QTPY_PLAN_W / 2
    )
    QTPY_CY = 0.0


def field_xy(local):
    """Key-field-local (x, y) -> case (x, y).

    The field's origin is the left edge of the leftmost breakout, so
    field-local x runs 0 .. KEY_FIELD_W across all three boards.
    """
    return (FIELD_ORIGIN[0] + local[0], FIELD_ORIGIN[1] + local[1])


NEOKEY_ORIGIN = field_xy(NEOKEY_LOCAL)


def neokey_y(y):
    """NeoKey board-local y, turned the way the board actually sits."""
    return NEOKEY_D - y if BOARD_FLIP_Y else y


def neokey_xy(local):
    """NeoKey board-local (x, y) -> case (x, y)."""
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

# The wire channel runs under the boards and stops there. It used to run
# from 2 mm left of the field to the QT Py's centre, which put it over
# both screw positions at y +8.2, and that is worse than it sounds: the
# counterbore's ceiling is at z 1.00 and the trench floor at 1.20, so
# 0.70 of y had 0.20 of plate spanning it -- one layer, printed over the
# bore, under the seat the screw head bears on. The same overlap left
# 0.45 of the shell's post standing on air. Neither is an interference
# and `build.py` was green throughout.
#
# Past the NeoKey's right edge there is no board overhead anyway, so the
# depth bought nothing there and the field is the honest extent.
WIRE_CHANNEL_X = (FIELD_ORIGIN[0], FIELD_ORIGIN[0] + KEY_FIELD_W)
WIRE_LANE_Y = (FIELD_ORIGIN[1] + WIRE_LANE_LOCAL[0],
               FIELD_ORIGIN[1] + WIRE_LANE_LOCAL[1])

BREAKOUT_ORIGINS = [field_xy(o) for o in BREAKOUT_ORIGINS_LOCAL]
BREAKOUT_CENTERS = [(ox + BREAKOUT_W / 2, oy + BREAKOUT_D / 2)
                    for ox, oy in BREAKOUT_ORIGINS]

# Left to right, which is also key order: the two breakouts, then the
# NeoKey's four. Built from each board's own switch centre rather than
# from a pitch times an index, so a board that is not the width it is
# supposed to be shows up as a failed pitch check instead of agreeing
# with itself.
BREAKOUT_SWITCH_XY = [(ox + BREAKOUT_SW[0], oy + BREAKOUT_SW[1])
                      for ox, oy in BREAKOUT_ORIGINS]
NEOKEY_SWITCH_XY = [neokey_xy((x, NEOKEY_SW_Y)) for x in NEOKEY_SW_X]
SWITCH_XY = BREAKOUT_SWITCH_XY + NEOKEY_SWITCH_XY

MOUNT_XY = [neokey_xy(h) for h in NEOKEY_HOLES]
# Mirrored like everything else on that face. Nothing enters these any
# more -- the pegs are gone -- but a mock that puts a board's holes on the
# wrong diagonal is a mock that would mislead the next person to try.
BREAKOUT_HOLE_XY = [(ox + BREAKOUT_W - hx, oy + hy)
                    for ox, oy in BREAKOUT_ORIGINS
                    for hx, hy in BREAKOUT_HOLES]

# Where the bottom plate holds a breakout up, beyond the seam columns.
#
# The NeoKey is held in a sandwich -- a column under every hole and a
# standoff directly above it -- so its force path is a straight line
# through the board and there is no moment anywhere. A breakout cannot
# have that: nothing can stand above it except at the seams (see
# SEAM_XY), so its push down and its push up are never collinear.
#
# Two pads, both on the field's outer left edge -- the one end no seam
# reaches. Everywhere else the breakouts are carried from below by the
# seam columns, and adding pads per board on top of those would put five
# columns inside 5.3 mm around each seam.
#
# The board's mounting holes do not come into it any more. This used to
# be three pads on three of the four corners, with the back-right one
# left to a slim peg because the hot-swap socket -- 4.733 .. 15.633
# across the board, 11.653 .. 17.553 up it -- crosses a COLUMN_DIA pad
# there by 0.738. Watched to fail then, and still true of a pad on that
# hole: 5.675 mm3 against the breakout mock. All of it went with the
# pegs, for the reason recorded after BREAKOUT_SUPPORT_XY below.
#
# There was one pad here for a round, on the front row only, because the
# back row looked impossible: a socket body spans y 11.680 .. 17.580
# across most of the board, and at COLUMN_DIA 4.50 nothing fits beside it
# -- hard against the board edge it still fouls by 0.378. What changed is
# the pad, not the socket. FIELD_SUPPORT_DIA came down to 3.00 for an
# unrelated reason and the back row opened up.
#
# The two are not symmetric because the free board is not: the near one
# has 4.696 to sit in and the far one 4.010. 19.600 is where the far pad
# clears the last component by 0.486 and the cavity wall by 0.440, with
# about 0.4 of room to move either way before one of those goes.
FIELD_SUPPORT_LOCAL = [(2.45, 2.450), (2.45, 19.600)]
# Thinner than COLUMN_DIA, and it has to be. A seam column clears the
# back face in x, by sitting on the outermost strip of two boards at
# once; this one is in the middle of a board and has to clear in y
# instead, where there is 4.896 between the cavity wall at -0.200 and the
# first component at 4.696. A 4.50 pad leaves 0.198 a side, which is what
# "board columns inside the cavity" is for. 3.50 leaves 0.698.
#
# 3.50 was settled against the *breakouts*, and it stopped being enough
# the moment the NeoKey's component face went into the mock. The back-row
# seam column straddles a breakout and the NeoKey, and on the NeoKey side
# it comes 0.141 from a 0.300-proud part at board-local x 1.048..2.636 --
# under this file's own 0.25 floor, and measured for the first time by
# "column to a board's components", which could not exist while the mock
# had nothing there. 3.00 puts it at 0.391.
#
# 3.20 also clears the floor, at 0.291, and was not taken: this machine
# prints a post fat by about the 0.15 it pulls a hole in, so 3.20 arrives
# at roughly 0.24 and lands back on the line. 3.00 arrives at about 0.34.
# The pad only has to push a board up and a peg did that job at 2.30.
FIELD_SUPPORT_DIA = 3.00
BREAKOUT_SUPPORT_XY = [field_xy(p) for p in FIELD_SUPPORT_LOCAL]
# No pegs. The first assembled unit settled it: a plate-mount switch
# clips into the top plate and its pins go into the socket on the board,
# so the switch is what ties a breakout to the plate -- the supports set
# its height, the shell presses it down, and a locating peg carries
# nothing. Removing them also removes the two things they cost: 0.362 to
# the socket at the back-right hole, and an orientation trap, since a
# peg pair is the only feature that made it look like the board had a
# wrong way round. BREAKOUT_HOLES stays because it is board data.

# Where the shell presses the boards down. The NeoKey gets standoffs in
# its own four holes; the breakouts cannot, and the arithmetic is worth
# keeping because it is the whole reason this looks different. A breakout
# hole sits 7.62 from its switch centre, a plate-mount switch is 14 wide,
# so the hole clears the switch body by 0.62 -- and STANDOFF_DIA is 4.20,
# which needs 2.10. It fouls the switch by 1.48.
#
# So the breakouts are pressed at the seams between boards instead. A
# seam is a switch-gap centre by construction, which is exactly where
# STANDOFF_DIA is already known to fit: 4.20 in the 5.05 that 19.05 pitch
# leaves between two 14 mm bodies. Same y values as the NeoKey's holes,
# so the whole field is pressed along two lines rather than at scattered
# points.
# The front row sits 0.34 ahead of the NeoKey's own, which is the one
# place the two press-lines do not agree. A STEMMA QT receptacle starts
# 4.620 up the board and stands 2.96 proud, so at the NeoKey's 2.540 a
# STANDOFF_DIA circle reaches 4.640 and grazes it -- 0.011 mm3, which
# only appeared once both receptacles were modelled rather than just the
# one with a cable in it. 2.200 clears by 0.320 and still lands on the
# board, whose front edge is at 0.
# The NeoKey's own hole rows, and nothing cleverer. A row of these was
# shifted 0.34 for a while to dodge a STEMMA receptacle, back when the
# receptacle was modelled above the board; it is below it with every
# other component now, so a standoff coming down from the plate cannot
# reach it and the shift was a workaround for a condition that had
# stopped existing.
SEAM_Y = (NEOKEY_HOLES[0][1], NEOKEY_HOLES[2][1])
SEAM_XY = [field_xy((i * BREAKOUT_W, y))
           for i in range(1, BREAKOUT_COUNT + 1)
           for y in SEAM_Y]

# A seam is between two boards, so the field's outer left edge has none
# and the leftmost breakout was pressed on one side only -- which is what
# the first assembled unit showed. A standoff cannot go there either: the
# board runs 2.525 from its own left edge to its switch body against the
# 5.05 a seam has, and STANDOFF_DIA needs 4.20. So the plate reaches down
# as a rib along that edge instead. 1.50 keeps it 1.025 clear of the
# switch body in x, which holds whichever way PCB_SLOP lets the board
# sit, and 1.50 x 21.59 is more bearing area than a 4.20 circle anyway.
EDGE_RIB_W = 1.50
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
        FIELD_ORIGIN[0] + KEY_FIELD_W + INLINE_BOARD_GAP / 2,
    )
POST_XY = [(x, y) for x in _POST_X for y in _POST_Y]
