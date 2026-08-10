"""The three printed parts.

Print orientation is baked into the geometry, so it is worth stating:

  shell   -- plate face DOWN on the bed. The most-seen surface comes off
             the textured PEI matte, and every wall, post and rib grows
             upward from it. Nothing overhangs. The USB opening ends up
             as one ~10 mm bridge, which an A1 mini does not notice.
  bottom  -- flat, features up. Also support-free.
  coupon  -- flat. The whole point of it is to be cheap.

The division of labour changed when the QT Py went underneath the NeoKey:
the shell carries the NeoKey and the bottom plate carries the QT Py. They
have to be wired together before they are closed, which is the price of
losing 25 mm of depth.
"""

from build123d import (
    Axis,
    Box,
    Circle,
    Cylinder,
    Plane,
    Pos,
    Rectangle,
    RectangleRounded,
    chamfer,
    extrude,
)

import params as P


# --- small helpers ------------------------------------------------------
def _tube(x, y, z0, z1, dia):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(radius=dia / 2, height=z1 - z0)


def _block(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
        x1 - x0, y1 - y0, z1 - z0
    )


def _slab(w, d, r, z0, z1):
    return Pos(0, 0, z0) * extrude(RectangleRounded(w, d, r), amount=z1 - z0)


def _stadium(across, w, h, axis, a0, a1):
    """A rounded-end opening swept along `axis` from a0 to a1.

    `across` is (other-axis centre, z centre). Ends are fully rounded --
    a USB-C shell has no corners, and neither should the hole it goes
    through. (The same helper exists in the other module; they are six
    lines and independent on purpose, since the two shapes differ.)
    """
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


def _qtpy_rect():
    """The QT Py's footprint in case space, whichever way it is turned."""
    xs, ys = [], []
    for lx in (0.0, P.QTPY_W):
        for ly in (0.0, P.QTPY_D):
            x, y = P.qtpy_xy((lx, ly))
            xs.append(x)
            ys.append(y)
    return min(xs), max(xs), min(ys), max(ys)


def _clear_rects():
    """The board's two component-free margins, as case-space rectangles.

    Both faces are clear along these strips -- USB shell, both buttons,
    the STEMMA socket and every underside part sit between them -- so the
    same pair carries rails from below and whatever holds the board down
    from above. Returned as rectangles rather than as bands on a named
    axis, because which axis they land on depends on the layout and no
    caller should have to know.
    """
    for a0, a1 in P.QTPY_CLEAR_X:
        xs, ys = [], []
        for lx in (a0, a1):
            for ly in (0.0, P.QTPY_D):
                x, y = P.qtpy_xy((lx, ly))
                xs.append(x)
                ys.append(y)
        yield min(xs), max(xs), min(ys), max(ys)


def _stemma_rect():
    """Where the Qwiic plug needs a wall not to be."""
    sx0, sx1, sy0, sy1 = P.QTPY_STEMMA
    xs, ys = [], []
    for lx in (sx0, sx1):
        for ly in (sy0 - P.QWIIC_PLUG_L, sy1):
            x, y = P.qtpy_xy((lx, ly))
            xs.append(x)
            ys.append(y)
    return min(xs), max(xs), min(ys), max(ys)


def _usb_opening():
    """The whole port: a stadium through the wall, flaring to plug size.

    The receptacle sits 1.2 mm behind the wall's outer face -- the board
    stops short of the wall and the shell only overhangs it by 0.969 --
    so the plug's overmold has to come *into* the case to seat. Sizing
    the flare to the connector instead of to the plug leaves a port that
    looks right and cannot be plugged in.
    """
    zc = (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
    wall = (P.CASE_D if P.USB_AXIS == "y" else P.CASE_W) / 2
    across = ((P.USB_CX if P.USB_AXIS == "y" else P.USB_CY), zc)
    edge = P.USB_CY if P.USB_AXIS == "y" else P.USB_CX
    cut = _stadium(across, P.USB_W + P.USB_CLEAR_W, P.USB_H + P.USB_CLEAR_H,
                   P.USB_AXIS, wall - P.WALL - 1.0, wall + 0.1)
    cut += _stadium(across, P.USB_PLUG_W + P.USB_PLUG_CLEAR,
                    P.USB_PLUG_H + P.USB_PLUG_CLEAR, P.USB_AXIS,
                    edge + P.USB_OVERHANG - 0.05, wall + 0.1)
    return cut


# --- shell --------------------------------------------------------------
def shell():
    """Top shell: the switch plate, its walls, and the NeoKey's mount."""
    outer = _slab(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R, P.Z_FLOOR, P.CASE_H)
    cavity = _slab(
        P.CASE_W - 2 * P.WALL,
        P.CASE_D - 2 * P.WALL,
        max(P.OUTER_CORNER_R - P.WALL, 0.5),
        P.Z_FLOOR,
        P.Z_PLATE_BOTTOM,
    )
    part = outer - cavity

    # Standoffs that set the board height, each ending in a locating peg.
    # These two features are the entire NeoKey mount -- there is no screw.
    for x, y in P.MOUNT_XY:
        part += _tube(x, y, P.Z_NEOKEY_TOP, P.Z_PLATE_BOTTOM, P.STANDOFF_DIA)
        part += _tube(x, y, P.Z_NEOKEY_TOP - P.PEG_H, P.Z_NEOKEY_TOP, P.PEG_DIA)

    # Corner posts for the bottom plate's screws, full interior height.
    for x, y in P.POST_XY:
        part += _tube(x, y, P.Z_FLOOR, P.Z_PLATE_BOTTOM, P.POST_DIA)
        part -= _tube(x, y, P.Z_FLOOR - 0.1, P.Z_PLATE_BOTTOM - 1.0, P.PILOT_DIA)

    # Switch holes.
    for x, y in P.SWITCH_XY:
        part -= Pos(x, y, P.Z_PLATE_BOTTOM - 0.1) * extrude(
            RectangleRounded(P.SWITCH_HOLE, P.SWITCH_HOLE, P.PLATE_HOLE_R),
            amount=P.PLATE_T + 0.2,
        )

    if not P.STACKED:
        # Beside the keys, the shell can reach the QT Py -- the plate runs
        # over it too -- so the board is held from above here rather than
        # by the bottom plate. Pocket walls locate it, bars come down onto
        # its clear margins, and the bottom plate only has to push up.
        qx0, qx1, qy0, qy1 = _qtpy_rect()
        s_ = P.QTPY_SLOP / 2
        f = P.QTPY_FRAME_W
        frame = _block(qx0 - s_ - f, qx1 + s_ + f, qy0 - s_ - f, qy1 + s_ + f,
                       P.Z_FLOOR, P.Z_PLATE_BOTTOM)
        frame -= _block(qx0 - s_, qx1 + s_, qy0 - s_, qy1 + s_,
                        P.Z_FLOOR, P.Z_PLATE_BOTTOM)
        # ...with the wall in front of the STEMMA socket opened up. Third
        # time this design has had to learn that a wall can fit the board
        # and still make the case impossible to wire.
        ex0, ex1, ey0, ey1 = _stemma_rect()
        n = P.QTPY_STEMMA_NOTCH
        frame -= _block(qx0 - s_ - f - 0.1, qx0 - s_ + 0.1,
                        ey0 - n, ey1 + n,
                        P.Z_STEMMA_LOW - 0.4, P.Z_PLATE_BOTTOM)
        part += frame

        for cx0, cx1, cy0, cy1 in _clear_rects():
            part += _block(cx0, cx1, cy0, cy1,
                           P.Z_QTPY_LOW + P.QTPY_T, P.Z_PLATE_BOTTOM)

    # USB-C leaves through whichever wall the board points it at: the
    # back when the QT Py is stacked face down under the keys, the right
    # end when it lies face up beside them.
    part -= _usb_opening()

    part = part & outer

    # The plate face is the bed face, so its perimeter is where elephant
    # foot shows up. Chamfering it means the squash lands on a slope that
    # was going to be there anyway instead of on the visible top edge.
    try:
        top = part.faces().sort_by(Axis.Z)[-1]
        part = chamfer(top.outer_wire().edges(), 0.5)
    except Exception:  # geometry moved; a sharp edge still prints fine
        pass
    return part


def _stacked_qtpy_mount():
    """The QT Py's pocket, for the stacked layout only.

    Nothing above can reach the board there -- the NeoKey covers the case
    wall to wall -- so the bottom plate does the whole job. It rides on
    two rails under its clear margins and slides forward under two lips,
    entering through the same back-wall opening its USB-C ends up in.
    """
    qx0, qx1, qy0, qy1 = _qtpy_rect()
    s_ = P.QTPY_SLOP / 2
    f = P.QTPY_FRAME_W
    pocket_top = P.Z_QTPY_LOW + P.QTPY_T + P.QTPY_LIP
    px0, px1 = qx0 - s_, qx1 + s_

    # Side walls stop at the cavity, not past it: the pocket's back *is*
    # the shell's back wall, and running 1.6 mm of pocket into it is a
    # case that will not shut.
    cav_back = P.CASE_D / 2 - P.WALL
    part = None
    for x0, x1 in ((px0 - f, px0), (px1, px1 + f)):
        blk = _block(x0, x1, qy0 - f, cav_back, P.BOTTOM_T, pocket_top)
        part = blk if part is None else part + blk

    # The front stop, with a window under it. What it has to stop is the
    # board's front edge, up at rail height; what passes through below is
    # the Qwiic plug, hanging off a socket that now faces the floor.
    stop = _block(px0 - f, px1 + f, qy0 - f, qy0, P.BOTTOM_T, pocket_top)
    ex0, ex1, _, _ = _stemma_rect()
    n = P.QTPY_STEMMA_NOTCH
    stop -= _block(ex0 - n, ex1 + n, qy0 - f - 0.1, qy0 + 0.1,
                   P.BOTTOM_T - 0.1, P.Z_QTPY_LOW)
    part += stop

    for cx0, cx1, cy0, cy1 in _clear_rects():
        part += _block(cx0, cx1, cy0, cy1, P.BOTTOM_T, P.Z_QTPY_LOW)

    # Lips reach in 1.0 from the pocket walls and no further: any deeper
    # and they land on the buttons, which stand 1.94 proud on this face.
    for lx0, lx1 in ((px0, px0 + P.QTPY_LIP), (px1 - P.QTPY_LIP, px1)):
        part += _block(lx0, lx1, qy0, qy1,
                       P.Z_QTPY_LOW + P.QTPY_T, pocket_top)
    return part


# --- bottom plate -------------------------------------------------------
def bottom():
    """Bottom plate, and the QT Py's whole mount.

    Nothing above can reach the QT Py -- the NeoKey covers the case from
    wall to wall -- so retention has to come entirely from below. It rides
    on two rails under its component-free margins and slides in under two
    lips, entering through the same wall opening its USB-C comes out of.
    """
    part = _slab(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R, 0.0, P.BOTTOM_T)

    # Columns that push the NeoKey up against the shell's standoffs.
    for x, y in P.MOUNT_XY:
        part += _tube(x, y, P.BOTTOM_T, P.Z_NEOKEY_BOTTOM, P.COLUMN_DIA)

    if P.STACKED:
        part += _stacked_qtpy_mount()
    else:
        # Inline, the shell holds the board down. All the bottom plate has
        # to do is hold it up, on the same two clear margins.
        for cx0, cx1, cy0, cy1 in _clear_rects():
            part += _block(cx0, cx1, cy0, cy1, P.BOTTOM_T, P.Z_QTPY_LOW)

    for x, y in P.POST_XY:
        part -= _tube(x, y, -0.1, P.BOTTOM_T + 0.1, P.SCREW_CLEAR_DIA)
        part -= _tube(x, y, -0.1, P.SCREW_SINK, P.SCREW_HEAD_DIA)

    for x, y in P.FOOT_XY:
        part -= _tube(x, y, -0.1, P.FOOT_RECESS, P.FOOT_DIA)

    # The plug reaches past the seam between the two halves, so the plate
    # gets the same relief the shell does. Stacked it takes a real bite
    # out of the back edge; inline the connector rides high enough that
    # this removes nothing.
    part -= _usb_opening()

    return part


# --- coupon -------------------------------------------------------------
def coupon():
    """The 10-minute print that decides SWITCH_HOLE and PILOT_DIA.

    Three fits, nothing else:
      1. a switch into the plate hole, at the real plate thickness
      2. an M2.5 self-tapper into the real post
      3. a standoff and peg against a real NeoKey mounting hole
    """
    w, d = 36.0, 24.0
    part = _slab(w, d, 2.0, 0.0, P.PLATE_T)

    part -= Pos(-8.0, 0.0, -0.1) * extrude(
        RectangleRounded(P.SWITCH_HOLE, P.SWITCH_HOLE, P.PLATE_HOLE_R),
        amount=P.PLATE_T + 0.2,
    )

    post_h = P.Z_PLATE_BOTTOM - P.Z_FLOOR
    part += _tube(10.0, -6.0, P.PLATE_T, P.PLATE_T + post_h, P.POST_DIA)
    part -= _tube(10.0, -6.0, P.PLATE_T + 0.5, P.PLATE_T + post_h + 0.1, P.PILOT_DIA)

    so_h = P.Z_PLATE_BOTTOM - P.Z_NEOKEY_TOP
    part += _tube(10.0, 6.0, P.PLATE_T, P.PLATE_T + so_h, P.STANDOFF_DIA)
    part += _tube(
        10.0, 6.0, P.PLATE_T + so_h, P.PLATE_T + so_h + P.PEG_H, P.PEG_DIA
    )
    return part
