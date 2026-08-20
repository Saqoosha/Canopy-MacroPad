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
# 13.95 cutout off Kailh CPG135301D01, plus this machine's 0.15 shrink.
# Has never been checked against a Choc v2 -- none has been on this desk
# -- so HOLE_SWEEP brackets it rather than trusting it.
SWITCH_HOLE = 14.10
PLATE_TOP_TO_PCB = 2.20
PLATE_T = 1.30          # Choc's clips need 1.30; there is no fallback now
SOCKET_DROP = 1.90
HOLE_SWEEP = (14.00, 14.10, 14.20)
# 0.20 left a 14.0 square switch fouling the corner arcs of a 14.10 hole
# (corner centre at 6.85, switch corner at 7.0, dist 0.212 > 0.20). 0.10
# clears; the MX spec's 0.3 is a maximum, not a target.
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
BOARD_CLAMP_SLACK = 0.20

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

# --- the end hook -------------------------------------------------------
# Two screws hold this case and both sit in the left bay, so 145.50 mm of
# a 151.00 mm case has nothing on it. The step aligns the halves and hides
# the gap; since the snap went, nothing pulls them together.
#
# Saqoosha's answer, and it is a better one than a rib: at the right end
# the seam climbs, the plate's wall carries on up inside the shell's, and
# a **horizontal** boss off that wall drops into a pocket in the shell.
# It is not friction. The boss is captured, so the halves cannot lift
# there at all.
#
# **Ends only, and the reason is the assembly motion.** The boss points
# outward, so it is engaged by moving the plate along x -- put the right
# end in, swing the left end down, then the screws. On a long side the
# same boss would need the plate to move in y at the same time, which the
# other end's boss forbids. That is Saqoosha's constraint, felt before it
# was drawn: an end goes in, the middle of a long side does not.
#
# The band it lives in is cut from both sides: the USB plug's opening ends
# at y 6.00 and the outer corner radius starts at 9.99, leaving 3.99 mm of
# straight wall each side of the port. Everything below is sized inside
# that, not chosen.
END_HOOK_Y0 = USB_PLUG_W / 2 + 0.50      # clear of the plug opening
END_HOOK_L = 3.00                        # along the wall, inside the 3.99
END_HOOK_H = 1.60                        # the boss's own height

# The wall's top is the boss's top. Nothing is bought by going higher:
# the hook's grip is the shell material above the *slot*, whose roof is
# the boss, so 4.40, 5.00 and 5.50 all leave the same 5.10 of it. What a
# taller wall costs is the shell's own wall -- 5.10 left at 4.40, 4.00 at
# 5.50 -- and what it buys is only more tongue before the boss engages.
# 5.50 would also come within 0.20 of the board's underside, which is the
# same number this design already calls too tight everywhere else.
END_HOOK_SEAM_Z = 4.40                   # how high the seam climbs here

# **The pocket goes right through the shell's wall**, which is Saqoosha's
# call and it buys two things. The skirt is only 1.00 thick, so a blind
# pocket had to share that with the skin left outside it -- 0.70 of reach
# plus the fit read -0.100 and burst through anyway, which is how this
# ended up being asked rather than assumed. Through, the reach is bounded
# by the wall instead of by the wall minus a skin. And the second thing
# matters more on the bench: **you can see whether the hook engaged.**
# There is no other way to know, since the joint is buried once shut.
#
# The boss stops 0.10 short of the outer face so it sits recessed rather
# than proud -- a bump would be felt, a shadow line will not.
END_HOOK_REACH = SEAM_STEP_W - 0.10

# Clearance in y and z, so the boss can drop into the slot. This is the
# unknown now that the reach is settled by the wall: too tight and the
# end will not go together, too loose and the end lifts by exactly this
# before the boss catches. Not a press fit -- the boss is held by the
# shell's material above it, not gripped by its flanks.
END_HOOK_FIT_SWEEP = (0.10, 0.20, 0.30, 0.40)
# Settled on the coupon: 0.10, 0.20 and 0.30 would not go on and 0.40
# did. That is the top of the sweep, so where it stops being tight was
# never found -- but the direction of better here is *tighter*, and
# tighter is what did not fit, so 0.40 is the best value available rather
# than merely the surviving one.
#
# The reason three of four failed is this machine's hole shrink, the same
# ~0.15 the constant SWITCH_HOLE measures. The slot is a hole and arrives
# 0.15 small; the boss is an outside feature and arrives a little over.
# So the printed clearance is roughly the modelled figure minus 0.20, and
# **the lift is the printed one**: 0.40 modelled is about 0.20 of lift at
# that end, not 0.40.
END_HOOK_FIT = 0.40

# Both top edges of that raised wall are chamfered, and each one is a
# lead-in for a different thing going past it.
#
# **Inboard, for the board.** Its right edge sits 0.200 from the wall's
# inner face and the wall stands 3.30 above the plate at that point, so
# closing the case asks a 139.60 mm board to find a 0.200 slot blind. A
# chamfer turns that into a funnel; it does not add clearance further
# down and does not need to.
#
# **Outboard, for the shell.** The wall enters the shell's slot with
# SEAM_FIT/2 = 0.100 a side, same problem one layer out.
#
# They are not equal because the wall is only SEAM_STEP_W wide and two
# large chamfers would meet: at 0.50 each the top is a knife edge, which
# prints as a wobble and locates nothing. The flat left between them is
# checked, not assumed.
# One chamfer on the wall, inboard, for the board. There is no outboard
# one any more: the wall's top and the boss's top are the same plane now,
# so an outer chamfer would cut down and the boss would return beside it
# -- the V notch this design has already been through once. The boss's
# nose is the lead-in on that side.
END_HOOK_CHAMFER_IN = 0.30

# And a third, on the boss's leading **top** edge.
#
# It was on the bottom edge first, and the reasoning was about the wrong
# motion. The slot is taller than the boss with both tops flush, so all
# the play is underneath, and along a purely horizontal insertion the
# bottom edge is the one with room to move -- true, and not how this case
# goes together. The shell comes **down** over the plate, so the corner
# that meets the slot's roof is the top one. Saqoosha read it off the
# section drawing.
END_HOOK_NOSE = 0.35

FOOT_DIA = 8.00
FOOT_H = 2.00
FOOT_RECESS = 0.50

# --- Derived: the Z stack -----------------------------------------------
# 2.40 floor + (1.90 socket + 1.40 air) + 1.60 board + 2.20 = 9.50
Z_FLOOR = BOTTOM_T
Z_BOARD_BOTTOM = Z_FLOOR + SOCKET_CLEARANCE
Z_BOARD_TOP = Z_BOARD_BOTTOM + BOARD_T
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
# points. The Choc socket sits on the back half of each switch
# (board-local y ~13..18), so both press rows stay in front of it.
# 2.50 also clears COLUMN_DIA of the cavity wall (2.20 left only 0.15).
PRESS_Y = (2.50, 7.50)
PRESS_XY = [
    board_xy((SWITCH_X[i] + SWITCH_PITCH / 2, y))
    for i in range(len(SWITCH_X) - 1)
    for y in PRESS_Y
]

# Choc hot-swap socket envelope under the board, relative to a switch
# centre. Pad extents from pcb.SOCKET_PADS, grown a hair for the plastic
# body around them -- the boolean needs the shape a column would hit,
# not a summary of the pads alone.
SOCKET_LOCAL = (-4.5, 9.5, 2.2, 7.4)  # x0, x1, y0, y1

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
