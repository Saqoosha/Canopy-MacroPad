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

# Board outline corner, same radius the NeoKey and the breakouts used.
BOARD_CORNER_R = 2.54

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
SEAM_SNAP_W = 4.00
SEAM_SNAP_HOOK = 0.40
SEAM_SNAP_H = 0.60
SEAM_FIT = 0.20
SEAM_SNAP_SWEEP = (0.30, 0.40, 0.55, 0.70)

# --- USB-C --------------------------------------------------------------
# Receptacle class figure from the design spec (3.16). Overhang and plug
# overmold are the numbers the wired pad already settled with a real
# cable -- generous rather than measured off this board's part.
USB_W = 8.94
USB_H = 3.16
USB_OVERHANG = 0.969
USB_CLEAR_W = 1.10
USB_CLEAR_H = 0.80
USB_PLUG_CLEAR = 0.40
USB_PLUG_W = 12.00
USB_PLUG_H = 6.60
USB_PLUG_L = 8.00
USB_R = USB_H / 2

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

# Snap barbs where the posts leave room -- either side of mid-span.
SEAM_SNAP_X = (
    BOARD_ORIGIN[0] + SWITCH_X[1],
    BOARD_ORIGIN[0] + SWITCH_X[4],
)

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
