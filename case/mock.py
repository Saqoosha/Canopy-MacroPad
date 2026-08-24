"""Stand-ins for everything the case has to not touch.

These are not pretty models. They are the envelopes that matter, built
at nominal size from params, so that a boolean can answer "does the
shell hit this" instead of a render being squinted at. An interference
here is a part that cannot be assembled.

One board now -- BOARD_W x BOARD_D x BOARD_T -- plus the mated USB-C
plug at the right-hand tab. Model the plug, not the receptacle: a wall
can clear a socket perfectly and still seal it off.
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
    """One Choc hot-swap socket hanging below the board."""
    x0, x1, y0, y1 = P.SOCKET_LOCAL
    return _block(sx + x0, sx + x1, sy + y0, sy + y1,
                  P.Z_BOARD_BOTTOM - P.SOCKET_DROP, P.Z_BOARD_BOTTOM)


def board():
    """The custom PCB, its sockets, and the mated USB-C plug."""
    part = _slab(
        P.BOARD_W, P.BOARD_D, P.BOARD_CORNER_R,
        P.BOARD_CENTER[0], P.BOARD_CENTER[1],
        P.Z_BOARD_BOTTOM, P.Z_BOARD_TOP,
    )
    for sx, sy in P.SWITCH_XY:
        part += _socket(sx, sy)

    # Receptacle shell overhanging the right edge, then the plug that has
    # to reach it. The receptacle fits an opening happily; what decides
    # whether the port works is whether the overmold can get to it.
    edge = P.USB_CX
    across = (P.USB_CY, (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2)
    part += _stadium(across, P.USB_W, P.USB_H, P.USB_AXIS,
                     edge - 4.0, edge + P.USB_OVERHANG)
    part += _stadium(across, P.USB_PLUG_W, P.USB_PLUG_H, P.USB_AXIS,
                     edge + P.USB_OVERHANG,
                     edge + P.USB_OVERHANG + P.USB_PLUG_L)
    return part


def switches():
    """Only the part that lives between the PCB and the plate top.

    A plate-mount switch drops in through the hole from above, so
    everything below the flange has to be SWITCH_HOLE or it could never
    have got there. That is what the standoffs have to dodge.
    """
    half = P.SWITCH_HOLE / 2
    part = None
    for sx, sy in P.SWITCH_XY:
        # Same outline as the plate hole, including PLATE_HOLE_R. A sharp
        # SWITCH_HOLE square clips the hole's corner arcs -- 0.067 mm³
        # through the plate, which is the square-vs-rounded remainder,
        # not a standoff.
        body = _slab(
            half * 2, half * 2, P.PLATE_HOLE_R,
            sx, sy, P.Z_BOARD_TOP, P.Z_PLATE_TOP,
        )
        part = body if part is None else part + body
    return part


def everything():
    return {
        "board + sockets + USB": board(),
        "switch bodies": switches(),
    }
