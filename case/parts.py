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
    Text,
    chamfer,
    extrude,
    mirror,
)

import params as P


# --- small helpers ------------------------------------------------------
def _tube(x, y, z0, z1, dia):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(radius=dia / 2, height=z1 - z0)


def _lead_in(x, y, z_mouth, depth, d_mouth, d_tip):
    """The conical mouth of a pilot hole, as a solid to subtract.

    Opens at `z_mouth` and narrows `depth` into the part -- positive cuts
    upward, negative downward, so the same call serves the shell's posts
    (mouth on the floor, screw coming up) and the coupon's (mouth on top).
    The cone is run 0.1 past the mouth on its own slope rather than stopped
    flush, because a cut face coplanar with the face it opens onto is the
    kind of boolean OCCT is entitled to be unhappy about.
    """
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

    # The breakouts are pressed at the seams between boards rather than
    # at their own holes -- params/SEAM_XY carries the 1.48 mm of overlap
    # that rules the holes out. No peg on these: a seam is where two
    # boards meet, so there is nothing to locate into. Placing them is
    # the bottom plate's job.
    for x, y in P.SEAM_XY:
        part += _tube(x, y, P.Z_NEOKEY_TOP, P.Z_PLATE_BOTTOM, P.STANDOFF_DIA)

    # ...and a rib down the field's outer left edge, which has no seam to
    # stand on. It grows off the plate, so on a shell printed plate face
    # down it is not an overhang.
    _rx, _ry = P.FIELD_ORIGIN
    part += _block(_rx, _rx + P.EDGE_RIB_W, _ry, _ry + P.BREAKOUT_D,
                   P.Z_NEOKEY_TOP, P.Z_PLATE_BOTTOM)

    # Corner posts for the bottom plate's screws, full interior height.
    for x, y in P.POST_XY:
        part += _tube(x, y, P.Z_FLOOR, P.Z_PLATE_BOTTOM, P.POST_DIA)
        part -= _tube(x, y, P.Z_FLOOR - 0.1, P.Z_PLATE_BOTTOM - 1.0, P.PILOT_DIA)
        part -= _lead_in(
            x, y, P.Z_FLOOR, P.PILOT_MOUTH_H, P.PILOT_MOUTH_DIA, P.PILOT_DIA
        )

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

    # The same, for the breakouts, but their positions dodge the
    # hot-swap socket rather than following the mounting holes -- see
    # BREAKOUT_SUPPORT_LOCAL. The pegs point up into the board from
    # below, since there is no standoff overhead to hang one from, and
    # each one runs the whole way from the floor: at the second hole
    # there is no support under it to stand on, and one rule beats
    # "whichever ones happen to have a column beneath them".
    for x, y in P.BREAKOUT_SUPPORT_XY:
        part += _tube(x, y, P.BOTTOM_T, P.Z_NEOKEY_BOTTOM, P.FIELD_SUPPORT_DIA)
    # ...and one directly under each seam standoff, so the breakouts get
    # the sandwich the NeoKey has: the shell pushes down at these four
    # points and now something pushes back up along the same line, rather
    # than the pair being offset and leaving a moment. A seam straddles
    # two boards, so these are the only columns that have to clear two
    # back faces at once; they do, by 2.979 at the front row and 0.688 at
    # the back.
    for x, y in P.SEAM_XY:
        part += _tube(x, y, P.BOTTOM_T, P.Z_NEOKEY_BOTTOM, P.FIELD_SUPPORT_DIA)

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
        if P.CLEAR_CHAMFER > 0:
            part -= _lead_in(
                x, y, P.SCREW_SINK, P.CLEAR_CHAMFER,
                P.SCREW_CLEAR_DIA + 2 * P.CLEAR_CHAMFER, P.SCREW_CLEAR_DIA,
            )

    for x, y in P.FOOT_XY:
        part -= _tube(x, y, -0.1, P.FOOT_RECESS, P.FOOT_DIA)

    # The plug reaches past the seam between the two halves, so the plate
    # gets the same relief the shell does. Stacked it takes a real bite
    # out of the back edge; inline the connector rides high enough that
    # this removes nothing.
    part -= _usb_opening()

    return part


# --- coupon -------------------------------------------------------------
def _clear_row(xs, hole_y, label_y, chamfer):
    """The clearance sweep, as one solid to subtract from a pad.

    Shared by both coupons rather than written twice, because the two
    exist to answer the same question and a row that drifts on one of
    them answers it differently depending on which one got printed.

    The counterbore goes on the bed side, where bottom() puts it, and
    that is not cosmetic: with it down, the through-hole starts 1.00 up
    and never meets the squashed first layer; with it up, the hole would
    begin at the bed and read tighter than the plate it stands in for.
    A coupon that prints the feature the other way up measures a
    different hole. Labels sit on that same face and are mirrored, since
    a face is seen from the other direction once the part is in a hand.
    """
    cut = None
    for x, dia in zip(xs, P.CLEAR_SWEEP):
        one = _tube(x, hole_y, -0.1, P.BOTTOM_T + 0.1, dia)
        one += _tube(x, hole_y, -0.1, P.SCREW_SINK, P.SCREW_HEAD_DIA)
        if chamfer > 0:
            # Same cone the pilot mouths get, turned to a different job:
            # here it is not guiding a screw, it is giving the layer that
            # closes the counterbore something to climb rather than a
            # 1.275 mm ledge to hang off.
            #
            # It sits ABOVE the counterbore, not inside it. Put below, it
            # lands in space the counterbore has already removed and does
            # nothing at all -- which is how it was written first, and the
            # two rows would have printed identical while reporting that
            # the chamfer does not help. The flat the head seats on is
            # what is left outside the cone at this height: 1.275 - c.
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
    """An engraved number, as a sketch. `flip` for a face seen from below."""
    t = Text(txt, font_size=LABEL_SIZE, align=(Align.CENTER, Align.CENTER))
    return mirror(t, about=Plane.YZ) if flip else t


def coupon_layout():
    """Where everything on the coupon sits.

    Split out of coupon() so that anything measuring the printed solid
    reads the same numbers the solid was built from. It is a test part, so
    the only thing checking it is a script holding coordinates of its own,
    and a second copy of a y value is a check that quietly moves to empty
    air when the layout shifts. That happened: the posts were raised to
    make room for the clearance pad, a probe kept looking at the old row,
    and every "this hole is open" assertion passed by finding nothing at
    all.
    """
    pitch = P.POST_DIA + 5.4  # the labels are what sets this, not the posts
    n = len(P.PILOT_SWEEP)
    margin = 3.0
    block_w = P.SWITCH_HOLE + 2 * margin  # the switch's share of the plate
    w = block_w + margin + (n - 1) * pitch + P.POST_DIA + 2 * margin
    x0 = -w / 2
    post_x = [
        x0 + block_w + margin + P.POST_DIA / 2 + i * pitch for i in range(n)
    ]
    # Two bands. The upper one is the original coupon, moved up bodily to
    # make room; the lower one is the clearance pad, which is a second
    # thickness and so cannot share a surface with anything above it.
    lift = 10.0
    pad_y0, pad_y1 = -20.0, -6.0
    hole_y = pad_y1 - 5.5
    # Measured off the glyphs rather than assumed, because the counterbore
    # is Ø6.10 and reaches further across the pad than anything else on
    # it. Placing the label a fixed distance from the pad edge instead put
    # the top of the digits exactly on the counterbore's rim -- a label
    # with its head cut off, on a part whose only job is to be read.
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
        "switch_x": x0 + block_w / 2,
        "switch_y": lift,
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
    """The 20-minute print that decides the numbers a printer owns.

    Four fits, nothing else:
      1. a switch into the plate hole, at the real plate thickness
      2. an M3 self-tapper into the real post -- one post per PILOT_SWEEP
         entry, at the real post height, each engraved with its diameter
      3. an M3 dropped through a clearance hole -- one per CLEAR_SWEEP
         entry, through a pad at the real BOTTOM_T with the real
         counterbore, because a hole's fit is a property of how many
         layers it passes through and the plate is not the bottom
      4. a standoff and peg against a real NeoKey mounting hole

    Two of those are sweeps rather than single holes because the answer is
    a feel, not a measurement: the screw that goes in too easily and the
    one that needs a fight are only distinguishable side by side, with the
    same screw, in the same plastic, minutes apart. Both sweeps keep their
    known-bad entry as the first one -- 2.50 and 3.40, the two on the
    built case -- so there is something to feel the others against.

    The two rows face opposite ways on purpose. The posts are driven into
    from the top; the clearance pad is what a screw is dropped through,
    counterbore up, so the head lands where it would on the real plate.
    """
    L = coupon_layout()
    w, d = L["w"], L["d"]
    switch_x, post_x = L["switch_x"], L["post_x"]
    post_y, label_y = L["post_y"], L["label_y"]
    post_top, hole_y = L["post_top"], L["hole_y"]

    part = _slab(w, d, 2.0, 0.0, P.PLATE_T)

    part -= Pos(switch_x, L["switch_y"], -0.1) * extrude(
        RectangleRounded(P.SWITCH_HOLE, P.SWITCH_HOLE, P.PLATE_HOLE_R),
        amount=P.PLATE_T + 0.2,
    )

    for x, dia in zip(post_x, P.PILOT_SWEEP):
        part += _tube(x, post_y, P.PLATE_T, post_top, P.POST_DIA)
        # Blind at 0.5 above the plate, open at the top, so the screw goes
        # in from the labelled face and the mouth is the one being tested.
        part -= _tube(x, post_y, P.PLATE_T + 0.5, post_top + 0.1, dia)
        part -= _lead_in(
            x, post_y, post_top, -P.PILOT_MOUTH_H, P.PILOT_MOUTH_DIA, dia
        )
        part -= Pos(x, label_y, P.PLATE_T - 0.4) * extrude(
            _label(f"{dia:.2f}"), amount=0.5
        )

    # The clearance pad, brought up from the plate's 1.60 to the bottom
    # plate's real BOTTOM_T. A clearance hole that is free through 8 layers
    # is not necessarily free through 12, and it is the 12 that ships.
    part += _block(
        L["pad_x0"], L["pad_x1"], L["pad_y0"], L["pad_y1"], 0.0, P.BOTTOM_T
    )
    part -= _clear_row(post_x, hole_y, L["clear_label_y"], P.CLEAR_CHAMFER)

    so_h = P.Z_PLATE_BOTTOM - P.Z_NEOKEY_TOP
    sy = L["standoff_y"]
    part += _tube(post_x[0], sy, P.PLATE_T, P.PLATE_T + so_h, P.STANDOFF_DIA)
    part += _tube(
        post_x[0], sy, P.PLATE_T + so_h,
        P.PLATE_T + so_h + P.PEG_H, P.PEG_DIA,
    )
    return part


def clear_coupon_layout():
    """Where the hole-only coupon puts its rows.

    Exposed for the same reason coupon_layout() is: the only thing that
    checks a test part is a script, and a script holding its own copy of
    these numbers is a check that silently relocates when a row moves.
    """
    L = coupon_layout()
    n = len(P.CLEAR_SWEEP)
    rows = len(P.CLEAR_CHAMFER_SWEEP)
    pitch = L["pitch"]
    margin = 3.0
    row_d = L["pad_y1"] - L["pad_y0"]
    # A column down the left for the row's own label, so the rows are told
    # apart by what is written on them and not by which way up the part
    # was picked up.
    tag_w = 12.0
    w = tag_w + (n - 1) * pitch + P.SCREW_HEAD_DIA + 2 * margin
    d = rows * row_d
    x_left = -w / 2
    xs = [
        x_left + tag_w + margin + P.SCREW_HEAD_DIA / 2 + i * pitch
        for i in range(n)
    ]
    # Rows keep the big coupon's internal spacing exactly; only the pad
    # around them is new.
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
    """The clearance sweep on its own, once per transition shape.

    The full coupon answers four questions and three of them are settled,
    so reprinting it to re-ask the fourth spends twenty minutes and a
    switch-sized hole on nothing. This is the same row, at the same pitch
    and the same relative positions, on a pad of its own.

    It is printed twice, once per CLEAR_CHAMFER_SWEEP entry, because the
    first one printed came out with filament hanging in every bore and
    there are two candidate explanations -- the hole is simply too small,
    or the layer that closes the counterbore sags into it. Sweeping the
    diameter alone cannot separate them: it would find a diameter that
    works and leave the reason unknown, which is the same answer a wrong
    theory gives. Two rows at identical diameters, differing only in the
    transition, does separate them. If the chamfered row runs clean at a
    diameter the flat row does not, the sag was the cause.

    Same handling as the row on the big coupon, because it *is* that row:
    counterbore and labels on the bed face, so this prints features-down
    and is read and used from underneath. Each row carries its own chamfer
    engraved at the left, `C0.00` and `C0.60`.
    """
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
