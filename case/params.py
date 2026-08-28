"""Every dimension the case depends on, and where each number came from.

The PCB owns the key field now. This file imports it and carries the
printed parts around it: plate, shell, bottom, fasteners, the USB port.
One switch -- Choc v2 -- and every number below is a constant, not a
branch. MX and Choc hot-swap holes cannot share a position, so there is
no switch axis and no MPAD_SWITCH.

Print target: Bambu A1 mini, 0.4 nozzle, 0.2 layer, PLA Basic.
"""

import importlib.util
import os
import sys

# Load pcb/params.py by path under a unique module name. A plain
# `import params as pcb` would re-enter this file: case/params is already
# registered as `params` in sys.modules by the time we get here.
_pcb_path = os.path.join(os.path.dirname(__file__), "..", "pcb", "params.py")
_spec = importlib.util.spec_from_file_location("pcb_params", _pcb_path)
pcb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pcb)

SWITCH_PITCH = pcb.SWITCH_PITCH
KEY_FIELD_W = pcb.KEY_FIELD_W
KEY_FIELD_D = pcb.KEY_FIELD_D
BOARD_W = pcb.BOARD_W
BOARD_D = pcb.BOARD_D
BOARD_T = pcb.BOARD_T
USB_TAB_W = pcb.USB_TAB_W
SWITCH_X = [x for x, _ in pcb.switch_centres_mm()]
SWITCH_Y = pcb.SWITCH_Y

# Single output tree. There is no layout axis and no switch axis.
OUT_NAME = "choc"

# --- Choc v2 plate ------------------------------------------------------
# **Settled on a real Choc v2.** All three swept holes take the switch;
# 14.00 is the one that is tight enough to hold it, and 14.10 and 14.20
# only snap. It won at the **bottom** of the sweep, so how much tighter
# still works was never found -- and is deliberately not being looked
# for. The direction of better here is tighter, tighter than 14.00 was
# not printed, and a hole that grips is the whole requirement. If a
# reprint ever comes out loose the sweep runs downward from here.
#
# It is also **not where the arithmetic pointed.** 14.10 was 13.95 off
# Kailh's CPG135301D01 drawing plus the 0.15 this machine pulls a hole
# in -- the constant `SWITCH_HOLE` measured on MX, where 14.15 seats a
# 14.00 switch. Here the same reasoning wants 14.10 and 14.00 is what
# grips, so the correction is 0.05 rather than 0.15. **The shrink is not
# one number across features**, which is exactly why the sweep exists and
# why the coupon outranks the tables.
SWITCH_HOLE = 14.00
PLATE_TOP_TO_PCB = 2.20
PLATE_T = 1.30          # Choc's clips need 1.30; there is no fallback now
SOCKET_DROP = 1.90
HOLE_SWEEP = (14.00, 14.10, 14.20)
# 0.10, and the arithmetic that chose it no longer clears. It was
# written for a 14.10 hole: a 14.0 *square* switch put its corner 0.212
# from the arc centre against a 0.20 radius, so 0.20 fouled and 0.10 did
# not. At 14.00 the same sum says 0.10 fouls too, by 0.041.
#
# The printed coupon disagrees and it outranks the sum. A Choc v2 goes
# into the 14.00 hole and grips. The model's switch is a square with
# PLATE_HOLE_R corners and a real one is not square -- its corners are
# radiused -- so the calculation is pessimistic about a shape it does not
# have. Left at 0.10 on that evidence, and the sum is recorded here as
# the thing that stopped being true rather than deleted.
#
# `build.py` cannot referee this: mock.py draws the switch body from
# SWITCH_HOLE with the same PLATE_HOLE_R, so its boolean agrees with
# itself at any value.
PLATE_HOLE_R = 0.10

# Board outline corner comes from the PCB. Two sources for the same edge
# produced two different cases before; the pocket must follow the board.
BOARD_CORNER_R = pcb.BOARD_CORNER_RADIUS

# --- Fasteners ----------------------------------------------------------
# M3 button head, self-tapping into printed posts. Settled on the coupon
# against a real M3; re-run when the filament or nozzle changes.
PILOT_DIA = 2.95
POST_DIA = 5.60
PILOT_SWEEP = (2.50, 2.65, 2.80, 2.95)
CLEAR_SWEEP = (3.40, 3.55, 3.70, 3.85)
CLEAR_CHAMFER = 0.60
CLEAR_CHAMFER_SWEEP = (0.00, 0.60)
CLEAR_RING_MAX = 0.60
COLUMN_DIA = 4.50
SCREW_CLEAR_DIA = 3.70
PILOT_MOUTH_DIA = 3.40
PILOT_MOUTH_H = 0.60
SCREW_HEAD_DIA = 6.10
SCREW_HEAD_H = 1.65
SCREW_SINK = 1.00

# Between two keys at 19.05 there is 5.05 of air; 4.20 leaves real
# clearance rather than the 0.025 that reads as a fit and is not one.
STANDOFF_DIA = 4.20

# --- Case ---------------------------------------------------------------
WALL = 2.00
BOTTOM_T = 2.40
OUTER_CORNER_R = 3.00
PCB_SLOP = 0.40

# How much shorter the shell's standoffs are than the space they sit in.
# Without it the stack adds up exactly and the boards hold the halves
# apart. Same number, same reason as on the wired pad.
#
# It does not help the other side of the sandwich. The standoffs sit
# *above* the board; too-tall columns push the board into the switches,
# and the switches hold the shell up. The printed bottom closed with a
# hair under 1 mm of seam until you pressed. Columns stop this short of
# the board now.
BOARD_CLAMP_SLACK = 0.20
COLUMN_SLACK = 0.40

# Room past the left board end for an M3 post. The USB tab on the right
# sits against the wall (with PCB_SLOP), so there is no matching bay there
# -- a second pair of posts stands just inboard of the right wall past
# the board's own right edge once PCB_SLOP is spent.
END_BAY = 7.00

# Air under the board: socket plus the same 1.40 that opened the wire
# lane on the wired pad. No STEMMA receptacle here, so SOCKET_DROP is
# the deepest thing.
UNDER_BOARD_AIR = 1.40
SOCKET_CLEARANCE = SOCKET_DROP + UNDER_BOARD_AIR

# --- how the two printed halves close on each other --------------------
SEAM_STEP_W = 1.00
SEAM_STEP_H = 1.20

SEAM_FIT = 0.20        # total clearance between skirt and tongue

# --- the slide latch ----------------------------------------------------
# Two screws hold the left bay and the end hook holds the right end, and
# between them 145.50 mm of seam had nothing -- the printed case shows a
# tiny gap at the middle of the plate, the parts not being flat off the
# bed and nothing there to hold them down. The snap was killed by
# arithmetic (the skirt is not a spring: 19% strain against PLA's 2) and
# a third screw by the boards (0.200 of room against the 5.60 a post
# needs).
#
# This is Saqoosha's slide, and the whole plate goes on like a battery
# lid: eight small hooks along the long sides, drawn as **the end hook
# multiplied** back when the hook still existed (the printed case has
# since retired it -- see *where the end hook was* above). Each tab is
# a solid **post on the tongue's top rim with an eave off its top,
# reaching outboard** -- print-scale features, upright on the plate --
# and the shell's wall, 2.00 thick and 5.80 tall, takes a **pocket up
# into its underside**: a full-height entry for the drop, a channel
# the post runs along, and a **ledge running along x** that the eave
# rides over. The plate sagging is the eave landing on the ledge:
# shell material *under* a plate feature, at eight points spanning
# 116 mm. In the shell's flipped print the pockets open upward and the
# ledge prints as a short bridge off the wall's outer skin.
#
# The first cut put 0.50-tall ledges inside the seam step's 1.20 and
# Saqoosha called it -- too tiny and too thin to print -- which is why
# the latch lives up in the wall.
#
# The motion: drop the plate flat at a small leftward offset (push left
# until the trimmed tongue touches the left skirt -- the entry pockets
# are cut to cover that touch, so the stop *is* the drop zone), then
# slide right until the screw holes line up. At rest, in both
# positions, nothing on either half touches the other -- the fits are
# all clearances, and the only face contact is that transient left
# touch.
#
# Why rightward and why the slide is small: the direction was chosen
# so the end hook's boss could engage off the same translation, and it
# outlives the hook -- every trim and entry is built on it and no
# leftward fact argues for a re-flip. Rightward means the *left*
# tongue end is trimmed to open the drop offset, and the trim is
# capped by the screw heads' seat rings at x -73.05 -- it stops 0.30
# short, which caps the drop at 1.25 and the capture at what a ~1 mm
# slide covers.
#
# The columns are what make the corridor legal: they dodge the hot-swap
# sockets in **y**, not in x (sockets case y 2.2..7.4, front columns
# -8.29, back row 9.16 with its 0.26), so the plate can translate in x
# with every column staying in its lane.
# 66, not 68: the entry pockets open toward +x now and the rightmost
# one has to stay clear of the shell's corner radius at 72.5. The
# fifth pair at -66 is the screws' understudy: Saqoosha wants the
# latch to carry the case alone if it proves itself, and without the
# screws the left bay needs its own hold-down. It costs nothing while
# they coexist. (What the screws still do that no tab does: register x
# and stop the slide walking back open. A detent can take that over --
# a ~0.25 bump on a ledge, riding inside SLIDE_FIT, engaged by the
# plate's own hang, no material ever bent -- but it is a coupon
# question for after this geometry settles, not a free rider on it.)
SLIDE_TAB_X = (-66.0, -40.0, -8.0, 30.0, 66.0)

# The post. Third print's verdict was "eave is too tiny. slide length
# is too short", so everything here grew: the post from 3.00 x 1.80 to
# 4.00 x 2.20, the eave from 0.65 x 0.80 to 0.90 x 1.00, the capture
# from 0.80 to 2.00 of the eave's length -- roughly 3x the bearing.
SLIDE_TAB_L = 4.00        # the post, along the wall
SLIDE_TAB_H = 2.20        # above the tongue top; board underside is 3.30 up
# **The eave points outboard (+y), not along the slide (+x), and each
# direction change was bought by a print.** First sweep: the x nose at
# 0.80 kept 0.10 post-to-shelf and 0.20 tip-to-end, both inside the
# ~0.15..0.20 this machine shrinks a hole -- lengthened to 1.50. Case
# print: at 1.50 the nose is a free cantilever on the upright plate
# and Saqoosha saw it drooping; a drooped tip hangs below the modelled
# 3.40, under the shelf top at 3.10, and rams the shelf's edge instead
# of riding over it -- the slide's next 0.1..0.2 stop after the hook's.
# Slicer support under eight bearing faces is the wrong fix (scarred
# undersides, and these parts print support-free by contract), so the
# geometry turned 90 degrees: an eave reaching outboard, anchored
# along the post's whole length, riding a **ledge that runs along x**
# in the wall's underside -- a fraction of the overhang, carried the
# whole way, and the x-clearance class that kept failing stops
# existing, because nothing of the tab ends near anything in x.
SLIDE_NOSE_Y = 0.90       # eave reach outboard, past the post's face
SLIDE_NOSE_H = 1.00       # the eave's height, top-aligned with the post

# **Both bearing faces are 45-degree wedges, and the fifth print is
# why.** The flat-bottomed eave and the flat-topped ledge are a pair
# of opposed horizontal overhangs -- the eave droops down off the
# upright plate, the ledge droops up off the flipped shell -- and at
# 0.90/0.85 wide they ate the 0.30 between them from both sides:
# every coupon of that sweep jammed ("both eaves on shell and bottom
# are 垂れる a bit, so it cannot slide in"). So neither face is
# horizontal any more: the eave's underside and the ledge's top are
# parallel 45-degree slopes rising outboard, SLIDE_FIT apart measured
# vertically. At 45 degrees both surfaces print supported in their own
# orientation -- the eave's underside steps outboard layer by layer,
# the ledge grows off the wall's outer skin -- so there is no free
# overhang left anywhere in the latch, at any size. A sagging plate
# lands slope on slope, full-face; the wedge's inboard push is met by
# the opposite wall's wedge through the plate.
SLIDE_WEDGE = 0.85        # the 45-degree leg on both faces

# Where the post stands relative to the wall's inner face: mostly in
# the cavity (the board is 1.1 above its top), with 0.15 tucked under
# the wall inside a full-height channel -- shallower than it was, so
# the ledge starts closer in and the eave bears wider.
SLIDE_POST_IN = 0.70      # post inboard of the wall's inner face
SLIDE_POST_UNDER = 0.15   # post under the wall; the channel clears it

# Clearance between the nose's underside and the shelf's top, which is
# also how far the seam can open before the capture catches. The shelf
# lives in the shell, so the sweep rebuilds the shell and the plate is
# one geometry. This machine prints holes ~0.15..0.20 small; the end
# hook's slot measured 0.40 modelled as ~0.20 of printed lift, and the
# same discount should be expected here.
#
# **Settled at 0.30, on two printed sweeps** (2026-08-25). The first
# (nose 0.80) said 0.30 reads best and stopped ~0.1 short of home on
# every entry -- the x fault recorded above the eave's constants. The
# second (nose
# 1.50) slides fully home and put a floor under the answer: 0.20 will
# not slide in at all, 0.30 and 0.40 both go and hold. So 0.30 is the
# smallest that works with the failure *felt* one step below it -- a
# floor with a mechanism, not an untested edge -- and it doubles as a
# shrink measurement: printed clearance at 0.20 is at or under zero,
# so this pocket loses ~0.20 and the printed lift at 0.30 is ~0.10.
# **0.30, settled with a mechanism at both bounds.** On the wedge
# faces 0.20 slides and holds -- "good tight" -- but the shell slice
# comes out visibly expanded: at 0.20 the printed slopes are in light
# interference, and a 45-degree wedge converts that squeeze into an
# outboard load on the wall. The expansion IS the interference tell,
# so 0.20 is the felt floor, 0.40 the felt ceiling, and 0.30 the
# answer ("its good tight but expanded.. so the best is 0.3").
#
# The coupon overstates the expansion on purpose of its shape: a
# 22 mm slice has none of the case's stiffening -- no corners, no
# board-pocket frame (which doubles the wall above z 5.7), no second
# pocket end wall -- so if the *case* shows expansion at 0.30, that is
# new information, and the ready answers are a thicker pocket skin
# (0.85 -> 1.00, +63% panel stiffness, costs 0.15 of slope width) or
# gussets at the wall-ceiling corner. Not added now: every printed
# question so far was settled one variable at a time.
SLIDE_FIT = 0.30
SLIDE_FIT_SWEEP = (0.05, 0.10, 0.15, 0.20)

# **The slide runs leftward now, and the fourth print is why.** The
# rightward travel was capped at 1.25 by the left trim against the
# screw seats, and "slide length is too short" is Saqoosha's verdict
# on what 1.25 feels like. Leftward has no such cap: the drop offset
# is opened by the *right* trim, which has nothing to its right but
# the corner radius, so the travel is ~2 and the drop window ~1 --
# a slide a hand can feel. The direction was rightward only for the
# boss, the boss is gone, and this is the leftward fact that finally
# argued for the re-flip. Motion: push the plate right until the
# trimmed tongue touches the right skirt, drop flat, slide left until
# the screw holes line up.
#
# SLIDE_CAPTURE is how much of the eave's length rides over the ledge
# at home; ENTRY_MIN is the shallowest drop whose eave still clears
# the ledge's end; the deepest offset is the right touch, and
# SLIDE_ENTRY_MAX is derived from the right trim below so the entry
# always covers it.
SLIDE_CAPTURE = 2.00
SLIDE_ENTRY_MIN = SLIDE_CAPTURE + 0.10
SLIDE_ENTRY_HEAD = 0.60   # entry roof above the post top, for the drop

# The pocket's footprint across the wall: from just inboard of the
# wall's inner face (open to the cavity there anyway) to 1.15 outboard
# of it, leaving 0.85 of wall skin outside. The skirt below is never
# touched, so nothing of the latch shows on the seam.
SLIDE_POCKET_IN = 0.10    # inboard of the wall's inner face
SLIDE_POCKET_OUT = 1.15   # outboard of the wall's inner face

# --- USB-C --------------------------------------------------------------
# Receptacle class figure from the design spec (3.16). Overhang and plug
# overmold are the numbers the wired pad already settled with a real
# cable -- generous rather than measured off this board's part.
USB_W = 8.94
USB_H = 3.16
USB_OVERHANG = 0.969
# **One shape makes both openings.** They used to be two, each sized from
# its own pair of numbers -- 10.04 x 3.96 for the throat and 12.40 x 5.40
# for the plug's relief -- and two stadiums of different proportions do
# not have parallel outlines: the ledge between them ran 1.180 to 1.520
# and pinched at the ends, which is what read as a corner. Saqoosha said
# it should just be the same shape twice, and he is right; it is the same
# fault this file already names, two places deriving one edge.
#
# So the relief is the plug's envelope, the throat is that inset by one
# number, and the ledge is that number everywhere by construction. What
# used to be USB_CLEAR_W/H is now a consequence rather than an input, and
# `build.py` checks the throat still clears the receptacle instead of
# taking it on trust.
USB_LEDGE = 0.70
USB_PLUG_CLEAR = 0.40
USB_PLUG_W = 12.00
# 6.60 was chosen generously and never measured, and it is what made the
# port's shape wrong: the relief it sizes reached z 0.62, below the
# shell's own lowest material at 1.20, so the opening's outline ran off
# the bottom edge instead of closing, and it cut the bottom plate's lip
# down to a 0.62 shelf spanning the port.
#
# 5.00 is Saqoosha's, off the assembled part -- the plug does not touch
# the shell, so the envelope had room to come down. **The boolean cannot
# check this one**: mock.py draws the mated plug from this same constant,
# so shrinking it shrinks the stand-in too and the interference check
# agrees with itself no matter what. The evidence is the handled part.
USB_PLUG_H = 5.00
USB_PLUG_L = 8.00
USB_R = USB_H / 2

# --- where the end hook was --------------------------------------------
# Retired 2026-08-25, on the printed case, by the person holding it.
# The hook was a raised wall and boss at the right end, engaged by the
# swing-era assembly motion; the slide latch adopted its rightward
# engagement precisely to keep it, and then the printed case ruled the
# other way. The full case would not slide home; Saqoosha cut the boss
# off the print and the latch held the bottom fine without it -- "boss
# isnt required. it holds bottom well." What still stopped the slide
# 0.1 short afterwards was the hook's remaining geometry: the raised
# wall's outer face had 0.10 to the shell's C lip, and the tongue's
# right corners ~0.14 diagonal to the skirt's -- clearances sized for a
# part that came down vertically, sitting inside the ~0.15..0.20 this
# machine shrinks a hole, and never widened the way the latch's were
# after its first sweep. Not printing error: designed-in stops.
#
# So the hook is gone whole -- wall, boss, C-back, the shell's band
# reliefs and through slots -- the right wall closes up again, and the
# tongue's right end is trimmed at SLIDE_RIGHT_TRIM_X below, corners
# and all, so nothing at that end can touch during or after the slide.
# Home in x is the screws' job alone (Ø3.70 over M3, ±0.35).
# The hook's numbers, in case it is ever wanted back: wall 3.00 thick
# plus a 1.60 rib, boss 1.60 tall reaching 0.90 into a through slot,
# slot clearance 0.40 settled on its own coupon (0.10..0.30 would not
# go on), seam climbed to 4.40 in two 3.00 bands beside the USB port,
# and a 1.60 C-back recess across the plate's whole depth.

# The tongue ends here on the right, before its own corner arcs begin,
# so the slide's last millimetre has nothing to meet: the gap to the
# right skirt at home is 2.10 where the hook's wall had 0.10.
SLIDE_RIGHT_TRIM_X = None  # derived below, needs CASE_W
# Elephant foot: the first layer is squashed and bulges past the outline,
# so the edge that lands on the bed gets a chamfer to give it somewhere
# to go. **Both halves need it and on different faces** -- the plate
# prints on its underside at z 0, the shell prints flipped so its bed
# face is the switch plate's top at CASE_H. Neither is the seam, which
# stands away from the bed on both.
ELEPHANT_CHAMFER = 0.40

FOOT_DIA = 8.00
FOOT_H = 2.00
FOOT_RECESS = 0.50

# --- Derived: the Z stack -----------------------------------------------
# 2.40 floor + (1.90 socket + 1.40 air) + 1.60 board + 2.20 = 9.50
Z_FLOOR = BOTTOM_T
Z_BOARD_BOTTOM = Z_FLOOR + SOCKET_CLEARANCE
Z_BOARD_TOP = Z_BOARD_BOTTOM + BOARD_T
Z_COLUMN_TOP = Z_BOARD_BOTTOM - COLUMN_SLACK
Z_PLATE_BOTTOM = Z_BOARD_TOP + (PLATE_TOP_TO_PCB - PLATE_T)
Z_PLATE_TOP = Z_PLATE_BOTTOM + PLATE_T
CASE_H = Z_PLATE_TOP

# USB-C hangs under the board at the right-hand tab. The receptacle is
# 3.16 and the under-board air is 3.30, so it almost clears the floor;
# the bottom plate still gets a local pocket for the last of it.
Z_USB_TOP = Z_BOARD_BOTTOM
Z_USB_BOTTOM = Z_BOARD_BOTTOM - USB_H

# --- Derived: the plan --------------------------------------------------
# Left bay for posts; right edge of the board against the wall so the
# USB-C port is reachable. Same shape as the old inline layout without
# the QT Py gap. Four posts sit in the left bay -- two is a hinge on a
# 130 mm case, and the right wall has no room beside a full-depth board
# that ends in a USB plug.
CASE_W = WALL + END_BAY + PCB_SLOP + BOARD_W + WALL
CASE_D = WALL + BOARD_D + PCB_SLOP + WALL

# The left trim: the tongue and the plate's top half end here on the
# left, so the plate can shift left for the drop at all. Capped by the
# screw heads' seat rings -- their outboard edge is POST_X + HEAD/2 at
# x -73.05 -- with 0.30 of margin; the deepest reachable offset (the
# trimmed face touching the left skirt) and the entry pockets' length
# both follow from it rather than being chosen.
SLIDE_TRIM_X = (
    -CASE_W / 2 + WALL + END_BAY / 2 - SCREW_HEAD_DIA / 2 - 0.30
)
# The right trim opens the drop offset for the leftward slide (its face
# against the right skirt IS the drop position) and still deletes the
# tongue's corner arcs; the pocket entries stop 1.25 short of the
# corner radius above it.
SLIDE_RIGHT_TRIM_X = CASE_W / 2 - OUTER_CORNER_R - 0.90
# Where the right trim face touches the right skirt's inner face: the
# deepest drop offset a hand can reach, which the entries must cover.
SLIDE_ENTRY_MAX = (
    (CASE_W / 2 - SEAM_STEP_W + SEAM_FIT / 2) - SLIDE_RIGHT_TRIM_X
)

BOARD_ORIGIN = (
    -CASE_W / 2 + WALL + END_BAY + PCB_SLOP / 2,
    -BOARD_D / 2,
)
BOARD_CENTER = (BOARD_ORIGIN[0] + BOARD_W / 2, BOARD_ORIGIN[1] + BOARD_D / 2)


def board_xy(local):
    """Board-local (x, y) -> case (x, y)."""
    return (BOARD_ORIGIN[0] + local[0], BOARD_ORIGIN[1] + local[1])


SWITCH_XY = [board_xy((x, SWITCH_Y)) for x in SWITCH_X]

# USB-C faces out the right wall off the tab.
USB_CX, USB_CY = board_xy((BOARD_W, BOARD_D / 2))
USB_AXIS = "x"

# Shell presses the board down, bottom plate pushes it up, at the same
# points. One row per long edge is the clamp; a third row between them
# (7.50, in front of the sockets) was there when both rows had to live
# on the front half, and it does nothing once the back edge is held.
# 2.50 also clears COLUMN_DIA of the cavity wall (2.20 left only 0.15).
#
# Between switches, not under them: the same x serves the back row too.
PRESS_X = [SWITCH_X[i] + SWITCH_PITCH / 2 for i in range(len(SWITCH_X) - 1)]
PRESS_Y = (2.50,)
PRESS_XY = [board_xy((x, y)) for x in PRESS_X for y in PRESS_Y]

# Choc hot-swap socket envelope under the board, relative to a switch
# centre. Pad extents from pcb.SOCKET_PADS, grown a hair for the plastic
# body around them -- the boolean needs the shape a column would hit,
# not a summary of the pads alone.
SOCKET_LOCAL = (-4.5, 9.5, 2.2, 7.4)  # x0, x1, y0, y1

# The other long edge. SOCKET_LOCAL's back is SWITCH_Y + 7.4 = 18.195,
# leaving 3.395 to BOARD_D. COLUMN_DIA 4.50 needs 4.50 plus wall
# clearance and does not fit; 3.00 does, with 0.26 to the socket box
# (the collision) and 0.135 to the board edge. Same x as the front
# row -- between switches, which is also where the real socket mesh
# stops at y 15.33, so the 0.26 is to the envelope, not the part.
BACK_COLUMN_DIA = 3.00
BACK_PRESS_Y = SWITCH_Y + SOCKET_LOCAL[3] + 0.26 + BACK_COLUMN_DIA / 2
BACK_PRESS_XY = [board_xy((x, BACK_PRESS_Y)) for x in PRESS_X]

FOOT_XY = [
    (x, y)
    for x in (-CASE_W / 2 + 14.0, CASE_W / 2 - 14.0)
    for y in (-CASE_D / 2 + 7.0, CASE_D / 2 - 7.0)
]

_POST_Y = (
    -CASE_D / 2 + WALL + POST_DIA / 2,
    CASE_D / 2 - WALL - POST_DIA / 2,
)
# Two posts on the left-bay centreline, front and back. A 7.00 bay
# cannot take two posts side by side (POST_DIA is 5.60), and the right
# wall has no room beside a full-depth board that ends in a USB plug.
_POST_X = (
    -CASE_W / 2 + WALL + END_BAY / 2,
)
POST_XY = [(x, y) for x in _POST_X for y in _POST_Y]


# --- Dummy keycap -------------------------------------------------------
# Placeholder caps, printed, until the wrk. MX Pure set arrives. The
# mount is **measured off `ref/choc-v2.step`**, not taken from an MX
# table, because the Choc v2's mount is not a bare cross: it is an MX
# cross standing inside a ring, and the cross does not stand proud of
# it. Every number here was read with a boolean probe against the STEP
# (`build.py` re-reads them, so a different STEP goes red rather than
# quiet). Switch-local z, where 0 is the PCB top face:
STEM_TOP = 8.60           # cross tip and ring rim, the same plane
STEM_CROSS_L = 4.00       # tip to tip, both arms
STEM_CROSS_W = 1.20       # arm *body* thickness -- not what the slot meets
# **The arms carry eight retention ribs and they are the whole fit.** One
# on each flat of each arm, standing 0.05 proud of the body, ~0.10 wide
# along the arm and running nearly the stem's full height. A slot sized
# on STEM_CROSS_W alone would be sized on the wrong number: what a cap
# grips is 1.30, and everything between 1.20 and 1.30 is rib to squeeze.
# Found by a boolean, not by reading -- the arm probes all said 1.200
# because they landed either side of a 0.10-wide feature.
STEM_RIB_W = 1.30         # across the arm, over the ribs
STEM_RIB_AT = 1.20        # rib centre, out along the arm from the axis
# The rib's top is rounded, so how high it reads depends on the band it
# is read in. This pair and `build.py`'s probe name the same band --
# 0.03 deep, starting 0.01 inside STEM_RIB_W -- and the number is what
# that probe returns, not an independent measurement of the plastic.
STEM_RIB_Z = (4.10, 8.39)
STEM_RING_OD = 6.50
STEM_RING_ID = 5.50
STEM_RING_BOTTOM = 3.60
HOUSING_TOP = 5.30        # the fixed housing's top face
HOUSING_MOUTH_DIA = 6.60  # the hole the ring travels through
CHOC_TRAVEL = 3.20        # Kailh CPG1353

# The cap seats on the **ring**, not on the cross tip: both top out at
# STEM_TOP, and a Ø6.50 rim resists rocking that 8.6 mm² of cross tip
# cannot. So the bore is sunk CAP_SOCKET_OVER past that plane and the
# cross never carries the press.
CAP_BEAR_DIA = 6.00       # flat that lands on the ring, inside the mouth
CAP_BOSS_DIA = 4.90       # into the ring bore (ID 5.50), cross does the aligning
CAP_ENGAGE = 3.00         # how much of the cross the bore holds
CAP_SOCKET_OVER = 0.10
CAP_CEIL_RELIEF = 0.50    # ceiling stepped up off the bearing pad

# The slot, measured from the arm **body**, so the number is also how
# much rib is left alone: `STEM_CROSS_W + STEM_CLEAR` against
# STEM_RIB_W's 1.30 is the squeeze, 0.05 per side at 0.00 and none at
# 0.10.
#
# **Settled at 0.00**, on two printed sweeps and then on six printed
# caps, which go onto the switches and fit really well. The first sweep
# -- 0.10, 0.15,
# 0.20, 0.25 -- came back 0.10 grips and the rest are loose, which is
# the ribs answering: 0.10 lands the slot exactly on them and every
# looser entry clears them by 0.025 or more, so that whole sweep sat at
# or above the ribs and could only find the top of the range. The second
# ran downward with 0.10 kept in as the control, and 0.00 is tight
# enough.
#
# So it won at the bottom for the fourth time in this case, after
# SWITCH_HOLE, PILOT_DIA and its own first sweep -- **and this bottom is
# different from those, which is the whole reason to write it down.**
# Theirs were untested edges: the direction of better ran off the end of
# what had been printed, and the note each carries is "re-run downward
# from here". This one is a floor with a mechanism under it. 0.00 puts
# the slot on the arm body, so it squeezes the ribs flat and nothing
# else; below it the bore stops squeezing ribs and starts eating the
# arm, which is a different thing to be doing and which `build.py`
# refuses. There is no third sweep to run.
#
# Print shrink sits under all of it -- this machine pulls a hole in by
# 0.05 to 0.15 -- so the printed slot is narrower than 1.20 and the ribs
# give the difference. That is the fit, and it is also the failure mode
# left: if a cap ever comes loose after a few pulls, the ribs have been
# shaved rather than deflected, and the answer is to come **up** from
# 0.00. Down is not available.
STEM_CLEAR = 0.00
STEM_CLEAR_SWEEP = (0.00, 0.04, 0.07, 0.10)
STEM_LEN_CLEAR = 0.30     # on the arm length; the flats are what grips
STEM_MOUTH = 0.30         # a wider first 0.40 of bore, to start it

# Outer shape: the wrk. MX Pure's envelope, so the swap changes nothing
# but the plastic. Read off the product photo in `product.py` and not
# from a caliper -- it decides how the pad looks, and nothing else.
CAP_XY = 18.40
CAP_R = 4.20
CAP_WALL = 1.20           # 3 x 0.4
# The cavity's corner is **squarer than the outer one on purpose**, and
# is not CAP_R - CAP_WALL. Rounding a corner pulls the boundary *in*
# along the diagonal, and the diagonal is exactly where the switch is
# widest: its 15 x 15 base stands 1.50 proud of the plate, so the skirt
# passes it at bottom-out. At 3.00 the cavity reached 10.071 against the
# base's measured 10.200 and the two fouled by 0.082 mm3; at 2.00 it
# reaches 10.485, which is 0.285 clear. The cost is a corner wall of
# 0.79 rather than CAP_WALL -- two perimeters, on a blank.
CAP_CAVITY_R = 2.00
CAP_TOP_T = 1.20
CAP_TOP_CHAMFER = 0.60
# Skirt above the plate at rest. CHOC_TRAVEL of that is spent pressing,
# so what is left is the clearance at bottom-out.
CAP_RIDE = CHOC_TRAVEL + 0.50

# One test token per sweep entry, printed the way the cap is.
TOKEN_W = 16.0
TOKEN_D = 20.0
TOKEN_T = 1.20
TOKEN_GAP = 4.0
