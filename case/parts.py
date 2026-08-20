"""The three printed parts.

Print orientation is baked into the geometry:

  shell   -- plate face DOWN on the bed.
  bottom  -- flat, features up. Support-free.
  coupon  -- flat. The whole point of it is to be cheap.

One board, Choc v2. The shell carries the plate and presses the board
down; the bottom plate pushes it up. Locating pegs are gone -- a
plate-mount switch ties plate to board.
"""

from build123d import (
    Align,
    Axis,
    Box,
    Circle,
    Cone,
    Cylinder,
    Plane,
    Pos,
    Rectangle,
    RectangleRounded,
    Rotation,
    Text,
    chamfer,
    extrude,
    mirror,
)

import params as P


def _tube(x, y, z0, z1, dia):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(radius=dia / 2, height=z1 - z0)


def _lead_in(x, y, z_mouth, depth, d_mouth, d_tip):
    """The conical mouth of a pilot hole, as a solid to subtract."""
    over = 0.1
    slope = (d_mouth - d_tip) / 2 / abs(depth)
    r_mouth = (d_mouth + 2 * slope * over) / 2
    up = depth > 0
    return Pos(x, y, z_mouth - over if up else z_mouth + depth) * Cone(
        bottom_radius=r_mouth if up else d_tip / 2,
        top_radius=d_tip / 2 if up else r_mouth,
        height=abs(depth) + over,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )


def _block(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
        x1 - x0, y1 - y0, z1 - z0
    )


def _slab(w, d, r, z0, z1):
    return Pos(0, 0, z0) * extrude(RectangleRounded(w, d, r), amount=z1 - z0)


def _stadium(across, w, h, axis, a0, a1):
    """A rounded-end opening swept along `axis` from a0 to a1."""
    r = min(w, h) / 2
    flat = max(w, h) - 2 * r
    prof = Circle(r) if flat < 1e-6 else (
        Rectangle(flat, 2 * r) if w >= h else Rectangle(2 * r, flat)
    )
    if flat >= 1e-6:
        d = flat / 2
        prof += Pos(-d, 0) * Circle(r) if w >= h else Pos(0, -d) * Circle(r)
        prof += Pos(d, 0) * Circle(r) if w >= h else Pos(0, d) * Circle(r)
    if axis == "y":
        pl = Plane(origin=(across[0], a0, across[1]),
                   x_dir=(1, 0, 0), z_dir=(0, 1, 0))
    else:
        pl = Plane(origin=(a0, across[0], across[1]),
                   x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    return extrude(pl * prof, amount=a1 - a0)


def _usb_opening():
    """The whole port: a stadium through the wall, flaring to plug size."""
    zc = (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
    wall = P.CASE_W / 2
    across = (P.USB_CY, zc)
    edge = P.USB_CX
    # One shape, twice. The relief is the plug's envelope and the throat
    # is that same outline inset by USB_LEDGE, so the border between them
    # is USB_LEDGE the whole way round rather than something that has to
    # be measured afterwards and turns out to pinch.
    rw = P.USB_PLUG_W + P.USB_PLUG_CLEAR
    rh = P.USB_PLUG_H + P.USB_PLUG_CLEAR
    cut = _stadium(across, rw - 2 * P.USB_LEDGE, rh - 2 * P.USB_LEDGE,
                   P.USB_AXIS, wall - P.WALL - 1.0, wall + 0.1)
    cut += _stadium(across, rw, rh, P.USB_AXIS,
                    edge + P.USB_OVERHANG - 0.05, wall + 0.1)
    return cut


def _board_pocket(z0, z1):
    """Walls that locate the board in plan, open at the USB end."""
    s_ = P.PCB_SLOP / 2
    ox, oy = P.BOARD_ORIGIN
    bx0, bx1 = ox - s_, ox + P.BOARD_W + s_
    by0, by1 = oy - s_, oy + P.BOARD_D + s_
    f = P.WALL
    # Frame around the board, then open the right wall for USB.
    frame = _block(bx0 - f, bx1 + f, by0 - f, by1 + f, z0, z1)
    frame -= _block(bx0, bx1 + f + 0.1, by0, by1, z0 - 0.1, z1 + 0.1)
    return frame


# --- shell --------------------------------------------------------------
def _hook_wall(x0, x1, y0, y1, z0, z1, c_in):
    """The raised wall with a lead-in chamfered off each top edge.

    Chamfered as an isolated box, before it is fused into the plate.
    Three attempts at doing it with a subtracted wedge each failed in a
    different silent way -- the face placed on the corner removed nothing
    (0.000 against an expected 0.270), the half-space unclamped ate the
    plate below it (27.833 against 0.367), and the clamp put on the
    normal's side removed nothing again. None of them raised, and
    `build.py` was green through all three.

    On a lone box there is exactly one top face and exactly two edges on
    it running along y, so selecting them cannot pick the wrong thing.
    """
    w = _block(x0, x1, y0, y1, z0, z1)
    # Re-select between the two cuts. `chamfer(edge, ...)` works on the
    # solid that edge belongs to, so an edge picked before the first cut
    # still points at the original box -- the second call then returns
    # that box with only its own chamfer and the first one is gone. The
    # volume said 0.120 where 0.390 was wanted, which is the outer
    # chamfer alone; nothing raised.
    edge = w.edges().filter_by(Axis.Y).group_by(Axis.Z)[-1].sort_by(Axis.X)[0]
    return chamfer(edge, length=c_in)


def _hook_boss(x0, x1, y0, y1, z0, z1, nose):
    """The boss, with a lead-in off its leading **top** edge.

    This was on the bottom edge first, reasoned from where the slack is:
    the slot is taller than the boss and all of that play sits underneath,
    so nose-first along x the bottom edge is the one with somewhere to go.
    That reasoning is about a purely horizontal insertion and the case is
    not assembled that way -- the shell comes **down** over the plate, so
    the corner that meets the shell's slot roof is the top one. Saqoosha
    read it off the section and said so.
    """
    b = _block(x0, x1, y0, y1, z0, z1)
    lead = b.edges().filter_by(Axis.Y).group_by(Axis.Z)[-1].sort_by(Axis.X)[-1]
    return chamfer(lead, length=nose)


def _end_hook_bands():
    """(y0, y1) for each hook, at the right wall, both sides of the port.

    Derived once and used by the boss, the pocket and the raised seam, so
    the three cannot drift apart. The band is bounded by the USB plug's
    opening on the inboard side and the case's corner radius outboard;
    everything is measured from those two rather than placed by eye.
    """
    return [
        (sign * P.END_HOOK_Y0, sign * (P.END_HOOK_Y0 + P.END_HOOK_L))
        for sign in (-1, 1)
    ]


def shell():
    """Top shell: the switch plate, its walls, and the board clamp."""
    outer = _slab(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R, P.Z_FLOOR, P.CASE_H)
    cavity = _slab(
        P.CASE_W - 2 * P.WALL,
        P.CASE_D - 2 * P.WALL,
        max(P.OUTER_CORNER_R - P.WALL, 0.5),
        P.Z_FLOOR,
        P.Z_PLATE_BOTTOM,
    )
    part = outer - cavity

    skirt_z0 = P.Z_FLOOR - P.SEAM_STEP_H
    part += (
        _slab(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R, skirt_z0, P.Z_FLOOR)
        - _slab(P.CASE_W - 2 * P.SEAM_STEP_W + P.SEAM_FIT,
                P.CASE_D - 2 * P.SEAM_STEP_W + P.SEAM_FIT,
                max(P.OUTER_CORNER_R - P.SEAM_STEP_W, 0.5),
                skirt_z0 - 0.1, P.Z_FLOOR + 0.1)
    )

    # The seam climbs at the right end. In the two bands beside the USB
    # port the shell gives up its inner SEAM_STEP_W all the way to
    # END_HOOK_SEAM_Z, so the plate's wall can carry on up inside it, and
    # takes a pocket in what is left for the boss to drop into.
    x_in = P.CASE_W / 2 - P.WALL
    x_seam = P.CASE_W / 2 - P.SEAM_STEP_W
    for y0, y1 in _end_hook_bands():
        lo, hi = sorted((y0, y1))
        part -= _block(x_in - 0.1, x_seam + P.SEAM_FIT / 2,
                       lo - P.SEAM_FIT / 2, hi + P.SEAM_FIT / 2,
                       P.Z_FLOOR - P.SEAM_STEP_H - 0.1, P.END_HOOK_SEAM_Z)
        # Through the outer face, deliberately: it is what lets the reach
        # use the whole wall, and it is the only way to see from outside
        # whether the hook actually went in.
        f = P.END_HOOK_FIT
        part -= _block(
            x_seam - 0.1, P.CASE_W / 2 + 0.1,
            lo - f / 2, hi + f / 2,
            P.END_HOOK_SEAM_Z - P.END_HOOK_H - f, P.END_HOOK_SEAM_Z,
        )

    # Standoffs that set the board height. No pegs -- the switch locates.
    for x, y in P.PRESS_XY:
        part += _tube(x, y, P.Z_BOARD_TOP + P.BOARD_CLAMP_SLACK,
                      P.Z_PLATE_BOTTOM, P.STANDOFF_DIA)

    for x, y in P.POST_XY:
        part += _tube(x, y, P.Z_FLOOR, P.Z_PLATE_BOTTOM, P.POST_DIA)
        part -= _tube(x, y, P.Z_FLOOR - 0.1, P.Z_PLATE_BOTTOM - 1.0, P.PILOT_DIA)
        part -= _lead_in(
            x, y, P.Z_FLOOR, P.PILOT_MOUTH_H, P.PILOT_MOUTH_DIA, P.PILOT_DIA
        )

    for x, y in P.SWITCH_XY:
        part -= Pos(x, y, P.Z_PLATE_BOTTOM - 0.1) * extrude(
            RectangleRounded(P.SWITCH_HOLE, P.SWITCH_HOLE, P.PLATE_HOLE_R),
            amount=P.PLATE_T + 0.2,
        )

    # Walls that locate the board in plan. Open on the USB end so the
    # plug can seat; the other three sides hold PCB_SLOP.
    part += _board_pocket(P.Z_BOARD_BOTTOM, P.Z_PLATE_BOTTOM)

    part -= _usb_opening()

    part = part & _slab(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R,
                        P.Z_FLOOR - P.SEAM_STEP_H, P.CASE_H)

    try:
        top = part.faces().sort_by(Axis.Z)[-1]
        part = chamfer(top.outer_wire().edges(), 0.5)
    except Exception:
        pass
    return part


# --- bottom plate -------------------------------------------------------
def bottom():
    """Bottom plate: columns under the board, USB pocket, screw seats."""
    part = _slab(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R,
                 0.0, P.BOTTOM_T - P.SEAM_STEP_H)
    part += _slab(P.CASE_W - 2 * P.SEAM_STEP_W, P.CASE_D - 2 * P.SEAM_STEP_W,
                  max(P.OUTER_CORNER_R - P.SEAM_STEP_W, 0.5),
                  P.BOTTOM_T - P.SEAM_STEP_H, P.BOTTOM_T)

    # The other half of the raised seam: the plate's wall carries on up
    # inside the shell in the same two bands, and the boss stands off its
    # outer face. The boss is what stops this end lifting -- it is
    # captured by the shell's material above the pocket, not gripped.
    x_in = P.CASE_W / 2 - P.WALL
    x_seam = P.CASE_W / 2 - P.SEAM_STEP_W
    for y0, y1 in _end_hook_bands():
        lo, hi = sorted((y0, y1))
        part += _hook_wall(x_in, x_seam, lo, hi, P.BOTTOM_T,
                           P.END_HOOK_SEAM_Z, P.END_HOOK_CHAMFER_IN)
        part += _hook_boss(
            x_seam, x_seam + P.END_HOOK_REACH, lo, hi,
            P.END_HOOK_SEAM_Z - P.END_HOOK_H, P.END_HOOK_SEAM_Z,
            P.END_HOOK_NOSE,
        )

    # Columns under the press points, so the clamp is a sandwich.
    for x, y in P.PRESS_XY:
        part += _tube(x, y, P.BOTTOM_T, P.Z_BOARD_BOTTOM, P.COLUMN_DIA)

    # Local pocket for the USB-C receptacle. Its floor is the port's own
    # lower edge, not a round number: at 1.00 deep it reached z 1.40 and
    # took away the tongue that backs the plug relief, so the relief --
    # which already cuts through the shell's 1.00 skirt -- came out the
    # other side. Two unrelated cuts lining up, and the port had a second
    # thin opening under the throat because of it.
    #
    # The receptacle needed none of that depth. It hangs to z 2.54 over a
    # plate top of 2.40, so 0.14 was the gap being widened; taking the
    # floor to the throat's lower edge instead leaves 0.42 and puts the
    # tongue back.
    _zc = (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
    _throat_h = P.USB_PLUG_H + P.USB_PLUG_CLEAR - 2 * P.USB_LEDGE
    pocket_d = P.BOTTOM_T - (_zc - _throat_h / 2)
    ox, oy = P.BOARD_ORIGIN
    part -= _block(
        ox + P.BOARD_W - P.USB_TAB_W - 1.0, ox + P.BOARD_W + 2.0,
        oy + P.BOARD_D / 2 - P.USB_W / 2 - 1.0,
        oy + P.BOARD_D / 2 + P.USB_W / 2 + 1.0,
        P.BOTTOM_T - pocket_d, P.BOTTOM_T + 0.1,
    )

    for x, y in P.POST_XY:
        part -= _tube(x, y, -0.1, P.BOTTOM_T + 0.1, P.SCREW_CLEAR_DIA)
        part -= _tube(x, y, -0.1, P.SCREW_SINK, P.SCREW_HEAD_DIA)
        if P.CLEAR_CHAMFER > 0:
            part -= _lead_in(
                x, y, P.SCREW_SINK, P.CLEAR_CHAMFER,
                P.SCREW_CLEAR_DIA + 2 * P.CLEAR_CHAMFER, P.SCREW_CLEAR_DIA,
            )

    for x, y in P.FOOT_XY:
        part -= _tube(x, y, -0.1, P.FOOT_RECESS, P.FOOT_DIA)

    part -= _usb_opening()
    return part


# --- coupon -------------------------------------------------------------
def _clear_row(xs, hole_y, label_y, chamfer):
    """The clearance sweep, as one solid to subtract from a pad."""
    cut = None
    for x, dia in zip(xs, P.CLEAR_SWEEP):
        one = _tube(x, hole_y, -0.1, P.BOTTOM_T + 0.1, dia)
        one += _tube(x, hole_y, -0.1, P.SCREW_SINK, P.SCREW_HEAD_DIA)
        if chamfer > 0:
            one += _lead_in(
                x, hole_y, P.SCREW_SINK, chamfer, dia + 2 * chamfer, dia,
            )
        one += Pos(x, label_y, -0.1) * extrude(
            _label(f"{dia:.2f}", flip=True), amount=0.5
        )
        cut = one if cut is None else cut + one
    return cut


LABEL_SIZE = 4.0


def _label(txt, flip=False):
    t = Text(txt, font_size=LABEL_SIZE, align=(Align.CENTER, Align.CENTER))
    return mirror(t, about=Plane.YZ) if flip else t


def coupon_layout():
    """Where everything on the coupon sits."""
    pitch = P.POST_DIA + 5.4
    n = len(P.PILOT_SWEEP)
    margin = 3.0
    # HOLE_SWEEP row: one hole per entry at the real PLATE_T.
    n_hole = len(P.HOLE_SWEEP)
    hole_pitch = P.SWITCH_HOLE + 4.0
    hole_block_w = (n_hole - 1) * hole_pitch + P.SWITCH_HOLE + 2 * margin
    block_w = max(P.SWITCH_HOLE + 2 * margin, hole_block_w)
    w = block_w + margin + (n - 1) * pitch + P.POST_DIA + 2 * margin
    x0 = -w / 2
    post_x = [
        x0 + block_w + margin + P.POST_DIA / 2 + i * pitch for i in range(n)
    ]
    hole_xs = [
        x0 + margin + P.SWITCH_HOLE / 2 + i * hole_pitch
        for i in range(n_hole)
    ]
    lift = 10.0
    pad_y0, pad_y1 = -20.0, -6.0
    hole_y = pad_y1 - 5.5
    label_h = max(
        _label(f"{d:.2f}").bounding_box().size.Y for d in P.CLEAR_SWEEP
    )
    clear_label_y = hole_y - P.SCREW_HEAD_DIA / 2 - label_h / 2 - 1.0
    return {
        "label_h": label_h,
        "clear_label_gap": (
            (hole_y - P.SCREW_HEAD_DIA / 2) - (clear_label_y + label_h / 2)
        ),
        "clear_label_edge": (clear_label_y - label_h / 2) - pad_y0,
        "w": w,
        "d": 46.0,
        "hole_xs": hole_xs,
        "hole_row_y": lift,
        "post_x": post_x,
        "post_y": -6.0 + lift,
        "label_y": 2.0 + lift,
        "standoff_y": 8.0 + lift,
        "post_top": P.PLATE_T + (P.Z_PLATE_BOTTOM - P.Z_FLOOR),
        "pad_x0": post_x[0] - P.POST_DIA / 2 - margin,
        "pad_x1": post_x[-1] + P.POST_DIA / 2 + margin,
        "pad_y0": pad_y0,
        "pad_y1": pad_y1,
        "pitch": pitch,
        "hole_y": hole_y,
        "clear_label_y": clear_label_y,
    }


def coupon():
    """The print that decides the numbers a printer owns.

    Asks, among other things:
      1. each HOLE_SWEEP diameter into a plate at the real PLATE_T 1.30
         -- does 1.30 hold a Choc v2's clips, and which hole seats
      2. an M3 into each PILOT_SWEEP post
      3. an M3 dropped through each CLEAR_SWEEP hole
    """
    L = coupon_layout()
    w, d = L["w"], L["d"]
    post_x = L["post_x"]
    post_y, label_y = L["post_y"], L["label_y"]
    post_top, hole_y = L["post_top"], L["hole_y"]

    part = _slab(w, d, 2.0, 0.0, P.PLATE_T)

    for x, dia in zip(L["hole_xs"], P.HOLE_SWEEP):
        part -= Pos(x, L["hole_row_y"], -0.1) * extrude(
            RectangleRounded(dia, dia, P.PLATE_HOLE_R),
            amount=P.PLATE_T + 0.2,
        )
        part -= Pos(x, L["hole_row_y"] + P.SWITCH_HOLE / 2 + 2.5,
                    P.PLATE_T - 0.4) * extrude(
            _label(f"{dia:.2f}"), amount=0.5
        )

    for x, dia in zip(post_x, P.PILOT_SWEEP):
        part += _tube(x, post_y, P.PLATE_T, post_top, P.POST_DIA)
        part -= _tube(x, post_y, P.PLATE_T + 0.5, post_top + 0.1, dia)
        part -= _lead_in(
            x, post_y, post_top, -P.PILOT_MOUTH_H, P.PILOT_MOUTH_DIA, dia
        )
        part -= Pos(x, label_y, P.PLATE_T - 0.4) * extrude(
            _label(f"{dia:.2f}"), amount=0.5
        )

    part += _block(
        L["pad_x0"], L["pad_x1"], L["pad_y0"], L["pad_y1"], 0.0, P.BOTTOM_T
    )
    part -= _clear_row(post_x, hole_y, L["clear_label_y"], P.CLEAR_CHAMFER)

    so_h = P.Z_PLATE_BOTTOM - P.Z_BOARD_TOP
    sy = L["standoff_y"]
    part += _tube(post_x[0], sy, P.PLATE_T, P.PLATE_T + so_h, P.STANDOFF_DIA)
    return part


END_TEST_REACH = 25.0     # how far inboard of the end wall to cut


def end_test():
    """The case's right end, both halves, cut and not otherwise touched.

    The coupon this follows is **not** the case end and Saqoosha said so:
    its wall runs the whole side beside the port where the case gives it
    END_HOOK_L, because the first coupon broke in the hand. That widening
    is the one place the coupon and the part disagree, and it is on the
    wall -- which is what you push on.

    So this is the other kind of test piece. Nothing is added, nothing is
    widened; `shell()` and `bottom()` are sliced END_TEST_REACH inboard of
    the end wall and laid out in the orientation each is printed in. If
    the hook seats here it seats in the case, and if the wall breaks here
    it will break in the case.

    There are no screws at this end -- both are in the left bay -- so the
    hook is the whole joint in this piece, which is exactly the thing
    being asked about.
    """
    x0 = P.CASE_W / 2 - END_TEST_REACH
    x1 = P.CASE_W / 2 + 0.5
    y0, y1 = -P.CASE_D / 2 - 0.1, P.CASE_D / 2 + 0.1

    plate = bottom() & _block(x0, x1, y0, y1, -0.1, P.CASE_H + 0.1)
    shell_piece = shell() & _block(x0, x1, y0, y1,
                                   P.Z_FLOOR - P.SEAM_STEP_H - 0.1,
                                   P.CASE_H + 0.1)
    flipped = Rotation(180, 0, 0) * shell_piece
    flipped = Pos(0, 0, -flipped.bounding_box().min.Z) * flipped
    return plate + Pos(END_TEST_REACH + 6.0, 0, 0) * flipped


def hook_coupon_layout():
    """Where each swept pair sits, and how big a bite is taken.

    The bite is the case's **whole end**: the USB opening in the middle
    and a hook on each side of it. One hook on its own answers whether a
    boss fits a slot; two, 24 mm apart with the port between them, answer
    whether the end actually goes together -- which is the question, and
    not one a single fragment can be asked.
    """
    return {
        "n": len(P.END_HOOK_FIT_SWEEP),
        "y0": -P.CASE_D / 2 - 0.1,
        "y1": P.CASE_D / 2 + 0.1,
        # How far inboard of the wall each fragment reaches. 6.0 gave a
        # piece you pinch; this gives one you hold with two fingers while
        # pushing the other half on, which is the motion being felt.
        # Inboard of the wall both halves are flat and empty -- the
        # plate's floor on one, the switch plate over the cavity on the
        # other -- so it costs nothing but bed.
        "grip": 16.0,
        "pitch": P.CASE_D + 5.0,
        "gap": 8.0,
    }


def _coupon_wall_runs():
    """The two straight runs of end wall, one each side of the port.

    The case gives the wall END_HOOK_L, the same 3.00 as the boss. The
    coupon gives it the whole side, plug opening to corner, because
    Saqoosha printed the first one and it broke in the hand: a 1.00 x
    2.00 wall three long with a 0.90 boss on the far side is a cantilever
    loaded at the tip, and a coupon has none of the case around it.

    The boss and the slot keep their real length. They are what is being
    measured and the fit is a clearance between those two; the wall's
    length has no part in it.
    """
    plug = P.USB_PLUG_W / 2 + 0.30
    corner = P.CASE_D / 2 - P.OUTER_CORNER_R - 0.10
    return [(-corner, -plug), (plug, corner)]


def hook_coupon():
    """One plate end and one shell end per END_HOOK_FIT_SWEEP entry.

    **Cut out of the real parts, not modelled again.** A coupon drawn by
    hand answers a question about the coupon; this one is the geometry
    `shell()` and `bottom()` build, so a number settled here is settled
    about the case.

    Only the shell reads END_HOOK_FIT -- it is the slot's clearance and
    the boss does not know about it -- so the plate is built once and its
    fragment repeated, and the shell is rebuilt per swept value.

    Both halves are laid out in the orientation each is printed in: the
    plate on its underside, the shell turned over onto its plate face.
    That is not decoration. The fit being swept is between two printed
    faces, and each takes its tolerance from the direction it was grown.
    """
    L = hook_coupon_layout()
    x_in = P.CASE_W / 2 - P.WALL
    x_seam = P.CASE_W / 2 - P.SEAM_STEP_W

    plate_box = _block(x_in - L["grip"], P.CASE_W / 2 + 0.5,
                       L["y0"], L["y1"], -0.1, P.END_HOOK_SEAM_Z + 0.1)
    shell_box = _block(x_in - L["grip"], P.CASE_W / 2 + 0.5,
                       L["y0"], L["y1"],
                       P.Z_FLOOR - P.SEAM_STEP_H - 0.1, P.CASE_H + 0.1)

    plate_piece = bottom() & plate_box
    for wy0, wy1 in _coupon_wall_runs():
        plate_piece += _hook_wall(x_in, x_seam, wy0, wy1, P.BOTTOM_T,
                                  P.END_HOOK_SEAM_Z, P.END_HOOK_CHAMFER_IN)

    was = P.END_HOOK_FIT
    part = None
    try:
        for i, fit in enumerate(P.END_HOOK_FIT_SWEEP):
            P.END_HOOK_FIT = fit
            shell_piece = shell() & shell_box
            # The shell's relief widened to match, or the two foul along
            # the wall the coupon just lengthened.
            for wy0, wy1 in _coupon_wall_runs():
                shell_piece -= _block(
                    x_in - 0.1, x_seam + P.SEAM_FIT / 2,
                    wy0 - P.SEAM_FIT / 2, wy1 + P.SEAM_FIT / 2,
                    P.Z_FLOOR - P.SEAM_STEP_H - 0.1, P.END_HOOK_SEAM_Z,
                )

            dy = (i - (L["n"] - 1) / 2) * L["pitch"]
            one = Pos(0, dy, 0) * plate_piece
            flipped = Rotation(180, 0, 0) * shell_piece
            flipped = Pos(0, 0, -flipped.bounding_box().min.Z) * flipped
            one += Pos(L["grip"] + P.WALL + L["gap"], dy, 0) * flipped

            # Engraved on the flat inboard of the wall, clear of the port.
            one -= Pos(x_in - L["grip"] / 2, dy, P.BOTTOM_T - 0.4) * extrude(
                _label("%.2f" % fit), amount=0.5)
            part = one if part is None else part + one
    finally:
        P.END_HOOK_FIT = was
    return part


def clear_coupon_layout():
    L = coupon_layout()
    n = len(P.CLEAR_SWEEP)
    rows = len(P.CLEAR_CHAMFER_SWEEP)
    pitch = L["pitch"]
    margin = 3.0
    row_d = L["pad_y1"] - L["pad_y0"]
    tag_w = 12.0
    w = tag_w + (n - 1) * pitch + P.SCREW_HEAD_DIA + 2 * margin
    d = rows * row_d
    x_left = -w / 2
    xs = [
        x_left + tag_w + margin + P.SCREW_HEAD_DIA / 2 + i * pitch
        for i in range(n)
    ]
    hole_off = L["hole_y"] - L["pad_y0"]
    label_off = L["clear_label_y"] - L["pad_y0"]
    rows_y = []
    for r in range(rows):
        y0 = d / 2 - (r + 1) * row_d
        rows_y.append({
            "chamfer": P.CLEAR_CHAMFER_SWEEP[r],
            "hole_y": y0 + hole_off,
            "label_y": y0 + label_off,
            "tag_x": x_left + tag_w / 2 + margin / 2,
        })
    return {"w": w, "d": d, "xs": xs, "rows": rows_y}


def clear_coupon():
    """The clearance sweep on its own, once per transition shape."""
    L = clear_coupon_layout()
    part = _slab(L["w"], L["d"], 2.0, 0.0, P.BOTTOM_T)
    for row in L["rows"]:
        part -= _clear_row(
            L["xs"], row["hole_y"], row["label_y"], row["chamfer"]
        )
        part -= Pos(row["tag_x"], row["hole_y"], -0.1) * extrude(
            _label(f"C{row['chamfer']:.2f}", flip=True), amount=0.5
        )
    return part
