"""Stand-ins for everything the case has to not touch.

These are not pretty models. They are the envelopes that matter, built at
nominal size from the STEP measurements in params, so that a boolean can
answer "does the shell hit this" instead of a render being squinted at.
An interference here is a part that cannot be assembled, which is the one
class of mistake a preview image will never show.

Everything QT Py is expressed in board-local coordinates and pushed
through `params.qtpy_xy`, so the rotate-and-flip is written down once. A
mock that reimplements that transform is a mock that will eventually
disagree with the part it is checking.
"""

from build123d import (
    Box, Circle, Cylinder, Plane, Pos, Rectangle,
    RectangleRounded, extrude,
)

import params as P


def _slab(w, d, r, x, y, z0, z1):
    return Pos(x, y, z0) * extrude(RectangleRounded(w, d, r), amount=z1 - z0)


def _block(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
        x1 - x0, y1 - y0, z1 - z0
    )


def _qt(x0, x1, y0, y1, z0, z1):
    """Board-local rectangle -> a case-space block."""
    a = P.qtpy_xy((x0, y0))
    b = P.qtpy_xy((x1, y1))
    return _block(min(a[0], b[0]), max(a[0], b[0]),
                  min(a[1], b[1]), max(a[1], b[1]), z0, z1)


def _stadium(across, w, h, axis, a0, a1):
    """A rounded-end volume swept along `axis`, matching the real shell."""
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


def _socket(sx, sy):
    """One Kailh hot-swap socket, hanging below the board.

    Three boxes, not one. The socket is a body with a solder wing off
    each end, and the wings are what a column runs into -- a box drawn
    round the body alone cleared the back-left column by 0.586 while the
    printed plate put it through the left wing. `params.SOCKET_PARTS`
    carries the shape as measured off ref/neokey-breakout.step.

    Shared by both board kinds because it is the same part fitted the
    same way up: `KAILH_SOCKET` at `MR0` in both Eagle files, at the same
    offset from its switch centre. The NeoKey's own STEP does not model
    its sockets at all, so this is where they come from for that board.
    """
    z0 = P.Z_NEOKEY_BOTTOM - P.NEOKEY_SOCKET_DROP
    out = None
    for dx0, dx1, dy0, dy1 in P.SOCKET_PARTS:
        b = _block(sx + dx0, sx + dx1, sy + dy0, sy + dy1,
                   z0, P.Z_NEOKEY_BOTTOM)
        out = b if out is None else out + b
    return out


def _back_parts(ox, oy):
    """Everything else on a breakout's back face, board-local.

    The sockets are the tall ones and get their own helper, but the
    reverse-mount NeoPixel and the diode hang down too, and a check that
    only knows about sockets is a check that has been told half the
    board.
    """
    out = None
    for x0, x1, y0, y1, proud in P.BREAKOUT_BACK_PARTS:
        if proud >= P.NEOKEY_SOCKET_DROP - 0.01:
            continue          # a socket; _socket() places those
        b = _block(ox + x0, ox + x1, oy + y0, oy + y1,
                   P.Z_NEOKEY_BOTTOM - proud, P.Z_NEOKEY_BOTTOM)
        out = b if out is None else out + b
    return out


def breakouts():
    """The two 4978 boards, their sockets, and their real mounting holes.

    They sit at the same height as the NeoKey and are the same depth, so
    they share Z_NEOKEY_BOTTOM and the plate above spans all three. That
    only holds while BREAKOUT_T equals NEOKEY_T, which params says out
    loud because it is the one board number still unmeasured.
    """
    part = None
    for cx, cy in P.BREAKOUT_CENTERS:
        slab = _slab(
            P.BREAKOUT_W, P.BREAKOUT_D, P.BREAKOUT_CORNER_R, cx, cy,
            P.Z_NEOKEY_BOTTOM, P.Z_NEOKEY_BOTTOM + P.BREAKOUT_T,
        )
        part = slab if part is None else part + slab
    for sx, sy in P.BREAKOUT_SWITCH_XY:
        part += _socket(sx, sy)
    for ox, oy in P.BREAKOUT_ORIGINS:
        part += _back_parts(ox, oy)
    # Both holes are modelled even though only one is used, so that a peg
    # moved onto the unused one would still read as a fit rather than as
    # a collision -- and so that a peg moved off *either* one starts
    # reading as the collision it would be.
    for x, y in P.BREAKOUT_HOLE_XY:
        part -= Pos(x, y, P.Z_NEOKEY_BOTTOM + P.BREAKOUT_T / 2) * Cylinder(
            radius=P.BREAKOUT_HOLE_DIA / 2, height=P.BREAKOUT_T + 0.2
        )
    return part


def neokey():
    """Board, plus the hot-swap sockets hanging off its underside."""
    part = _slab(
        P.NEOKEY_W, P.NEOKEY_D, P.NEOKEY_CORNER_R,
        P.NEOKEY_CENTER[0], P.NEOKEY_CENTER[1],
        P.Z_NEOKEY_BOTTOM, P.Z_NEOKEY_TOP,
    )
    # Socket footprint read off the STEP, relative to its switch centre:
    # 10.9 x 5.9 and offset in both axes, not centred on the switch.
    for sx, sy in P.NEOKEY_SWITCH_XY:
        part += _socket(sx, sy)
    # STEMMA QT receptacles with a mated Qwiic plug standing off each.
    # Stacked, either end may carry the cable, so both are claimed. Inline
    # the QT Py is at the right end and the cable can only come from the
    # right socket -- claiming the left one too would put an imaginary
    # plug through the left screw post, and that layout is handed anyway.
    # Only the right one now, in both layouts. The NeoKey's left socket
    # has a breakout butted against it, so nothing can be plugged in
    # there -- which is also the reason the breakouts are on that side:
    # see BREAKOUT_ORIGINS_LOCAL, where the right-hand alternative leaves
    # the mated plug 0.025 from the first breakout's switch.
    # Both of them. The board has a receptacle at each end -- the STEP
    # puts them at x 0.065..5.015 and 71.185..76.135 -- and only the right
    # one was modelled for a while, on the grounds that nothing can be
    # plugged into the left one with a breakout butted against it. True,
    # and beside the point: the receptacle is there whether a cable is or
    # not, and the case has to not sit on it.
    #
    # The mated plug is a different claim and stays one-ended, because it
    # reaches QWIIC_PLUG_L past the board edge and on the left that is
    # into the breakout. That is a fact about the cable, not the case.
    for sign, plug in ((1, P.QWIIC_PLUG_L), (-1, 0.0)):
        inner = P.NEOKEY_CENTER[0] + sign * (P.NEOKEY_W / 2 - 5.0)
        outer = P.NEOKEY_CENTER[0] + sign * (P.NEOKEY_W / 2 + plug)
        part += _block(
            min(inner, outer), max(inner, outer),
            P.NEOKEY_ORIGIN[1] + 4.62, P.NEOKEY_ORIGIN[1] + 10.62,
            P.Z_NEOKEY_TOP, P.Z_NEOKEY_TOP + 2.96,
        )
    # The M2.5 holes are real holes. Without them the shell's locating
    # pegs read as a 23 mm3 collision, which is the check crying wolf
    # about the one thing it is supposed to let through.
    for x, y in P.MOUNT_XY:
        part -= Pos(x, y, (P.Z_NEOKEY_BOTTOM + P.Z_NEOKEY_TOP) / 2) * Cylinder(
            radius=P.NEOKEY_HOLE_DIA / 2, height=P.NEOKEY_T + 0.2
        )
    return part


def switches():
    """Only the part that lives between the PCB and the plate top.

    A plate-mount MX switch drops in through the 14 mm hole from above, so
    everything below the top housing's flange has to be 14 mm or it could
    never have got there. That 14 is what the standoffs have to dodge, and
    the gap it leaves between neighbours is 19.05 - 14 = 5.05 mm total.
    """
    part = None
    for sx, sy in P.SWITCH_XY:
        body = _block(
            sx - 7.0, sx + 7.0, sy - 7.0, sy + 7.0,
            P.Z_NEOKEY_TOP, P.Z_PLATE_TOP,
        )
        part = body if part is None else part + body
    return part


def qtpy():
    """The QT Py, wherever and whichever way up the layout puts it.

    Which side of the board each part ends up on is the whole point here.
    Stacked, the board is face down: USB shell, buttons and STEMMA socket
    all hang below, and the underside parts stick up at the NeoKey.
    Inline it is face up and every one of those inverts. The Z values come
    from params so the two descriptions cannot drift apart.
    """
    part = _slab(
        P.QTPY_PLAN_W, P.QTPY_PLAN_D, P.QTPY_CORNER_R,
        P.QTPY_CX, P.QTPY_CY,
        P.Z_QTPY_LOW, P.Z_QTPY_LOW + P.QTPY_T,
    )
    # Underside parts -- up at the NeoKey's sockets when stacked, down at
    # the bottom plate when not.
    part += _qt(4.9, 12.7, 3.4, 20.0, P.Z_UNDER_LOW, P.Z_UNDER_HIGH)
    # USB-C shell, overhanging the board's edge. A stadium, not a box:
    # the real shell has fully rounded ends, and squaring it invented four
    # corners for the opening to have to clear.
    edge = P.USB_CY if P.USB_AXIS == "y" else P.USB_CX
    across = ((P.USB_CX if P.USB_AXIS == "y" else P.USB_CY),
              (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2)
    part += _stadium(across, P.USB_W, P.USB_H, P.USB_AXIS,
                     edge - 4.0, edge + P.USB_OVERHANG)
    # ...and the plug that has to reach it. The receptacle fits the
    # opening happily; what decides whether the port works is whether the
    # overmold can get to it, and it has to pass BOTH printed parts. The
    # same lesson the Qwiic sockets taught three times over.
    part += _stadium(across, P.USB_PLUG_W, P.USB_PLUG_H, P.USB_AXIS,
                     edge + P.USB_OVERHANG, edge + P.USB_OVERHANG + P.USB_PLUG_L)
    # STEMMA QT socket with a mated Qwiic plug standing off it.
    sx0, sx1, sy0, sy1 = P.QTPY_STEMMA
    part += _qt(sx0, sx1, sy0 - P.QWIIC_PLUG_L, sy1,
                P.Z_STEMMA_LOW, P.Z_STEMMA_HIGH)
    # Both tact buttons. The STEP gives 2.80 across the board's X and 4.60
    # along its Y; writing that pair the wrong way round puts 0.9 mm of
    # imaginary clearance where there is 0.2 mm of real one.
    for bl in (P.QTPY_BTN_A, P.QTPY_BTN_B):
        part += _qt(bl[0] - 1.4, bl[0] + 1.4, bl[1] - 2.3, bl[1] + 2.3,
                    P.Z_BTN_LOW, P.Z_BTN_HIGH)
    return part


def everything():
    return {
        "NeoKey + sockets": neokey(),
        "breakouts + sockets": breakouts(),
        "switch bodies": switches(),
        "QT Py + parts": qtpy(),
    }
