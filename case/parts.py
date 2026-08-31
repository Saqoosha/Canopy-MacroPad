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
def _slide_tab(x, side):
    """One latch tab, to fuse into the plate: a post standing on the
    tongue's top rim, mostly inboard of the wall's face, with an
    **eave** off its top reaching outboard over the shell's ledge.

    The eave is the third shape this feature has worn and printed
    parts chose all three turns: v1's ledges were too small to print,
    and the +x nose that replaced them grew into a 1.5 mm free
    cantilever that drooped below its own model and rammed the shelf
    it was meant to ride. The eave overhangs 0.65 and is anchored
    along its whole 3.00 length; its droop-prone outer bottom edge
    carries the chamfer.
    """
    y_in = P.CASE_D / 2 - P.WALL
    post_out = y_in + P.SLIDE_POST_UNDER
    lo, hi = sorted((side * (y_in - P.SLIDE_POST_IN), side * post_out))
    part = _block(x - P.SLIDE_TAB_L / 2, x + P.SLIDE_TAB_L / 2, lo, hi,
                  P.BOTTOM_T - 0.10, P.BOTTOM_T + P.SLIDE_TAB_H)
    elo, ehi = sorted((side * (post_out - 0.10),
                       side * (post_out + P.SLIDE_NOSE_Y)))
    eave = _block(x - P.SLIDE_TAB_L / 2, x + P.SLIDE_TAB_L / 2, elo, ehi,
                  P.BOTTOM_T + P.SLIDE_TAB_H - P.SLIDE_NOSE_H,
                  P.BOTTOM_T + P.SLIDE_TAB_H)
    # The whole underside is the wedge: a 45-degree chamfer off the
    # outer bottom edge, leaving a 0.15 flat at the root and a 0.15
    # tip face. Printed upright this face steps outboard layer by
    # layer -- no free overhang, which the flat underside was and
    # which drooped shut on the fifth print.
    lead = eave.edges().filter_by(Axis.X).group_by(Axis.Z)[0]
    lead = lead.sort_by(Axis.Y)[-1 if side > 0 else 0]
    return part + chamfer(lead, length=P.SLIDE_WEDGE)


def _slide_pockets():
    """What the latch removes from the shell's wall underside, per tab:
    a full-height ENTRY the whole tab rises through at the drop
    offset; past its right edge, a full-height channel over the post's
    path; and outboard of the channel a cut that stops short of the
    underside, leaving the **ledge** the eave rides over. The ledge's
    top is the capture -- SLIDE_FIT below the eave's underside -- and
    it runs along x, which is what dissolves the x-clearance class the
    +x nose kept failing: nothing of the tab ends near anything in x.

    In the flipped print the ledge is a short bridge off the wall's
    outer skin. The skirt below z 2.40 is outboard of everything here
    and never touched: nothing of the latch shows on the seam.
    """
    y_in = P.CASE_D / 2 - P.WALL
    ch_out = y_in + P.SLIDE_POST_UNDER + 0.15
    cut = None
    for xt in P.SLIDE_TAB_X:
        # The entry opens toward +x and the ledge runs off to -x: the
        # slide is leftward, the drop offset rightward.
        x1e = xt + P.SLIDE_TAB_L / 2 + P.SLIDE_ENTRY_MAX + 0.10
        x_e = xt - P.SLIDE_TAB_L / 2 + P.SLIDE_CAPTURE
        x0 = xt - P.SLIDE_TAB_L / 2 - 0.30
        z_top = P.Z_FLOOR + P.SLIDE_TAB_H + P.SLIDE_ENTRY_HEAD
        # The gallery's floor is where the eave's wedge lands, so it is
        # a wedge too: the cut box's bottom outer edge is chamfered at
        # 45 degrees, and what the chamfer spares of the wall is the
        # sloped ledge. Both slopes rise outboard in parallel; z_ledge
        # places the ledge's plane SLIDE_FIT below the eave's,
        # vertically, over the whole face.
        eave_root = y_in + P.SLIDE_POST_UNDER - 0.10
        z_ledge = (P.Z_FLOOR + P.SLIDE_TAB_H - P.SLIDE_NOSE_H
                   - P.SLIDE_FIT
                   + ((y_in + P.SLIDE_POCKET_OUT - P.SLIDE_WEDGE)
                      - (eave_root + 0.15)))
        for side in (-1, 1):
            lo_a, hi_a = sorted((side * (y_in - P.SLIDE_POCKET_IN),
                                 side * (y_in + P.SLIDE_POCKET_OUT)))
            lo_c, hi_c = sorted((side * (y_in - P.SLIDE_POCKET_IN),
                                 side * ch_out))
            lo_l, hi_l = sorted((side * (ch_out - 0.10),
                                 side * (y_in + P.SLIDE_POCKET_OUT)))
            one = _block(x_e, x1e, lo_a, hi_a, P.Z_FLOOR - 0.10, z_top)
            one += _block(x0, x_e + 0.10, lo_c, hi_c,
                          P.Z_FLOOR - 0.10, z_top)
            gal = _block(x0, x_e + 0.10, lo_l, hi_l, z_ledge, z_top)
            edge = gal.edges().filter_by(Axis.X).group_by(Axis.Z)[0]
            edge = edge.sort_by(Axis.Y)[-1 if side > 0 else 0]
            one += chamfer(edge, length=P.SLIDE_WEDGE)
            cut = one if cut is None else cut + one
    return cut


def _below_45(y_ref, z_ref, side):
    """The half-space under the latch's 45-degree plane, as a solid.

    The plane is z = z_ref + (side*y - y_ref): the same family every
    wedge face in the latch lies on. A big box rotated 45 about X, its
    top face laid on the plane -- intersect to keep what is under a
    slope, subtract to keep what is above one.
    """
    r = 2 ** 0.5
    ny, nz = -side / r, 1 / r
    return (Pos(0, side * y_ref - 30 * ny, z_ref - 30 * nz)
            * Rotation(side * 45, 0, 0) * Box(400, 60, 60))


def _detent_ridges():
    """The detent's shell half, second cut: a vertical round ridge on
    the pocket's outer skin inside the mid tab's gallery, reaching
    SLIDE_DETY_PROUD inboard -- 0.15 of that into the eave's tip. The
    first cut raised a two-layer bump on the stair-stepped ledge slope
    and the slicer smeared it away; a vertical cylinder is the shape
    slicers cannot spoil, in either half's print orientation.
    """
    y_in = P.CASE_D / 2 - P.WALL
    y_skin = y_in + P.SLIDE_POCKET_OUT
    z_e0 = P.BOTTOM_T + P.SLIDE_TAB_H - P.SLIDE_NOSE_H
    z0 = z_e0 + 0.70              # the tip's underside at the overlap
    z1 = P.BOTTOM_T + P.SLIDE_TAB_H + 0.16
    out = None
    for side in (-1, 1):
        c = _tube(P.SLIDE_DETY_X,
                  side * (y_skin + P.SLIDE_DETY_R - P.SLIDE_DETY_PROUD),
                  z0, z1, P.SLIDE_DETY_R * 2)
        out = c if out is None else out + c
    return out


def _detent_notches():
    """The detent's plate half, second cut: the eave's outboard
    SLIDE_DETY_TRIM shortened over a window SLIDE_DETY_NOTCH either
    side of the ridge -- vertical walls in the upright print. The
    ridge parks between them at home; the click is the skin panel
    bending 0.15, not anything here deflecting.
    """
    y_in = P.CASE_D / 2 - P.WALL
    tip = y_in + P.SLIDE_POST_UNDER + P.SLIDE_NOSE_Y
    z_e0 = P.BOTTOM_T + P.SLIDE_TAB_H - P.SLIDE_NOSE_H
    out = None
    for side in (-1, 1):
        lo, hi = sorted((side * (tip - P.SLIDE_DETY_TRIM),
                         side * (tip + 0.30)))
        n = _block(P.SLIDE_DETY_X - P.SLIDE_DETY_NOTCH,
                   P.SLIDE_DETY_X + P.SLIDE_DETY_NOTCH,
                   lo, hi, z_e0 + 0.40,
                   P.BOTTOM_T + P.SLIDE_TAB_H + 0.10)
        out = n if out is None else out + n
    return out


def _slide_trim():
    """The left-end trim: the plate's top half ends 1.25 short of the
    left skirt, cut with the skirt's own inner outline -- the same
    rounded rect the shell is built from -- shifted right, so the
    corners go with the face. It opened the drop offset back when the
    slide ran rightward; since the flip it is what guarantees the
    leftward slide's home has nothing to hit, the exact 0.1-stop class
    that cost a case print at the other end.

    Shaped, not boxed, because both box versions failed: a straight
    face left the tongue's corners standing in the skirt's corner arcs
    (the first slide latch watched 1.681 mm3 in the corridor probe),
    and box corner reliefs wide enough to fix that cut 1.122 mm3 out of
    the screw heads' seat rings. The arcs of the real outline pass
    between the two: corners cleared, rings whole.

    Only the left end loses material -- the shift moves the outline's
    right boundary past the plate -- and the trim face touching the
    left skirt is the deepest reachable offset, which the entry
    pockets are cut to cover.
    """
    z0 = P.BOTTOM_T - P.SEAM_STEP_H
    top = P.BOTTOM_T + P.SLIDE_TAB_H + 0.2
    shift = P.SLIDE_TRIM_X - (-P.CASE_W / 2 + P.SEAM_STEP_W
                              - P.SEAM_FIT / 2)

    def outline(dx):
        return Pos(dx, 0, 0) * _slab(
            P.CASE_W - 2 * P.SEAM_STEP_W + P.SEAM_FIT,
            P.CASE_D - 2 * P.SEAM_STEP_W + P.SEAM_FIT,
            max(P.OUTER_CORNER_R - P.SEAM_STEP_W, 0.5),
            z0, top)

    # The right half of the intersection is the leftward slide's drop
    # clearance: the plate must fit inside the skirt's outline at every
    # offset up to the right touch, and the intersection of the outline
    # swept left by SLIDE_ENTRY_MAX is exactly that. Its corner arcs
    # are what a straight right trim lacked -- the corridor probe read
    # 1.488 mm3 of tongue corner standing in the right skirt's arcs at
    # the deep offset, the mirror of the 1.681 the left trim was shaped
    # for.
    allowed = outline(shift) & outline(-P.SLIDE_ENTRY_MAX)
    return _block(-P.CASE_W / 2 - 5.0, P.CASE_W / 2 + 5.0,
                  -P.CASE_D / 2 - 5.0, P.CASE_D / 2 + 5.0,
                  z0, top) - allowed


def _bed_chamfer(solid, z, size):
    """Chamfer the outline that lands on the print bed.

    Taken on the base slab, before anything is cut into it: there is one
    face at that height and one loop of edges round it, so the selection
    cannot pick something else. After the holes, feet and counterbores go
    in there are dozens of edges at z and no honest way to name the right
    ones.
    """
    face = solid.faces().filter_by_position(Axis.Z, z - 1e-6, z + 1e-6)
    return chamfer(face.edges(), length=size)


def shell():
    """Top shell: the switch plate, its walls, and the board clamp."""
    outer = _slab(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R, P.Z_FLOOR, P.CASE_H)
    # This half prints flipped, so CASE_H is the face on the bed, and
    # one chamfer serves two masters: SHELL_TOP_CHAMFER is the look of
    # the top edge and, being larger than ELEPHANT_CHAMFER, it is also
    # the first layer's relief. It is cut here on the bare slab -- a
    # later version chamfered the finished part's top wire inside a
    # try/except, and at 1.20 that chamfer quietly failed (its downhill
    # leg overran the 0.40 elephant face) while the except swallowed
    # it; the bed-inset probe reading 0.35 instead of ~1.2 is what told.
    outer = _bed_chamfer(outer, P.CASE_H, P.SHELL_TOP_CHAMFER)
    cavity = _slab(
        P.CASE_W - 2 * P.WALL,
        P.CASE_D - 2 * P.WALL,
        P.CAVITY_CORNER_R,
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

    # The slide latch's half of the wall: entry pockets and shelves.
    # The right wall is unbroken -- the end hook's band reliefs and
    # through slots retired with it, on the printed case's evidence.
    part -= _slide_pockets()
    # The detent's ridges go in after the pockets open the galleries
    # they stand in.
    part += _detent_ridges()

    # Standoffs that set the board height. No pegs -- the switch locates.
    for x, y in P.PRESS_XY:
        part += _tube(x, y, P.Z_BOARD_TOP + P.BOARD_CLAMP_SLACK,
                      P.Z_PLATE_BOTTOM, P.STANDOFF_DIA)
    for x, y in P.BACK_PRESS_XY:
        part += _tube(x, y, P.Z_BOARD_TOP + P.BOARD_CLAMP_SLACK,
                      P.Z_PLATE_BOTTOM, P.BACK_COLUMN_DIA)

    # The screw posts stood here until the latch proved itself on the
    # printed case; the ten tabs hold the plate now (the -66 pair is
    # the left bay's), and the underside closes up with no counterbores.
    # What the screws still did -- x registration and slide-back
    # retention -- is the detent's job, which is the latch's one open
    # design.

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

    return part


# --- bottom plate -------------------------------------------------------
def bottom():
    """Bottom plate: columns under the board, USB pocket, screw seats."""
    part = _slab(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R,
                 0.0, P.BOTTOM_T - P.SEAM_STEP_H)
    # This half prints the right way up, so z 0 is the face on the bed.
    part = _bed_chamfer(part, 0.0, P.ELEPHANT_CHAMFER)
    part += _slab(P.CASE_W - 2 * P.SEAM_STEP_W, P.CASE_D - 2 * P.SEAM_STEP_W,
                  max(P.OUTER_CORNER_R - P.SEAM_STEP_W, 0.5),
                  P.BOTTOM_T - P.SEAM_STEP_H, P.BOTTOM_T)

    # Both tongue ends -- and their corner arcs -- go with _slide_trim's
    # shaped cut: the left end 1.25 short of its skirt, the right end at
    # SLIDE_RIGHT_TRIM_X so the plate can shift right for the drop. The
    # end hook that used to stand at the right is retired on the printed
    # case's evidence; the 0.10 its wall kept to the shell's C lip was
    # the slide's final stop.

    # The slide latch's half of the plate: eight posts with noses, and
    # the left-end trim that opens the drop offset.
    for xt in P.SLIDE_TAB_X:
        for side in (-1, 1):
            part += _slide_tab(xt, side)
    part -= _detent_notches()
    part -= _slide_trim()

    # Columns under the press points, so the clamp is a sandwich.
    # They stop COLUMN_SLACK short of the board -- exact height is what
    # held the printed seam open.
    for x, y in P.PRESS_XY:
        part += _tube(x, y, P.BOTTOM_T, P.Z_COLUMN_TOP, P.COLUMN_DIA)
    for x, y in P.BACK_PRESS_XY:
        part += _tube(x, y, P.BOTTOM_T, P.Z_COLUMN_TOP, P.BACK_COLUMN_DIA)

    # Clearance under the receptacle, cut with the **port's own profile**
    # rather than a box. It was a rectangle, and a rectangle is what you
    # saw from outside: the port's lower edge was that pocket's flat floor
    # running out to y +-5.47, not the throat's curve. The shape that
    # opens the wall and the shape that clears the receptacle are one
    # shape now, so the outline is a single continuous stadium.
    #
    # The depth is not free either. With no pocket at all the plate's top
    # at BOTTOM_T leaves the receptacle 0.14 -- under one printed layer --
    # so this is the throat carried inward, and it gives 0.42 for the same
    # reason it gives the plug 0.70: it is the same profile.
    _zc = (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
    _tw = P.USB_PLUG_W + P.USB_PLUG_CLEAR - 2 * P.USB_LEDGE
    _th = P.USB_PLUG_H + P.USB_PLUG_CLEAR - 2 * P.USB_LEDGE
    _ox = P.BOARD_ORIGIN[0]
    part -= _stadium((P.USB_CY, _zc), _tw, _th, P.USB_AXIS,
                     _ox + P.BOARD_W - P.USB_TAB_W - 1.0, P.CASE_W / 2 + 0.1)

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


# --- slide coupon -------------------------------------------------------
SLIDE_COUPON_TAB = 32.0   # which tab pair the slice is cut around
SLIDE_COUPON_X = (
    SLIDE_COUPON_TAB - 10.0,   # room for the entry pocket and a finger
    SLIDE_COUPON_TAB + 12.0,
)


def slide_coupon():
    """One full-depth slice of the case per SLIDE_FIT_SWEEP entry.

    **Cut out of the real parts, not modelled again**, for the same
    reason the hook's coupon is: a number settled here is settled about
    the case. The slice spans both walls at one tab pair, so what is
    felt is the real two-sided engagement -- push left to the touch,
    drop, slide right, lift the middle -- not one tab in a fragment
    free to twist.

    Only the shell reads SLIDE_FIT (it is the shelf's height under the
    nose; the tab does not know about it), so the plate's slice is
    built once and repeated, and the shell's is rebuilt per swept
    value -- the same split as the hook coupon, for the same reason.

    Both halves are laid out in the orientation each is printed in:
    the fit being swept is between two printed faces, and each takes
    its tolerance from the direction it was grown.
    """
    x0, x1 = SLIDE_COUPON_X
    cx = (x0 + x1) / 2
    y0, y1 = -P.CASE_D / 2 - 0.1, P.CASE_D / 2 + 0.1
    plate_box = _block(x0, x1, y0, y1, -0.1, P.CASE_H)
    shell_box = _block(x0, x1, y0, y1,
                       P.Z_FLOOR - P.SEAM_STEP_H - 0.1, P.CASE_H + 0.1)
    plate_piece = bottom() & plate_box

    pitch = P.CASE_D + 6.0
    gap = 8.0
    was = P.SLIDE_FIT
    part = None
    try:
        for i, fit in enumerate(P.SLIDE_FIT_SWEEP):
            P.SLIDE_FIT = fit
            shell_piece = shell() & shell_box
            flipped = Rotation(180, 0, 0) * shell_piece
            flipped = Pos(0, 0, -flipped.bounding_box().min.Z) * flipped
            dy = (i - (len(P.SLIDE_FIT_SWEEP) - 1) / 2) * pitch
            one = Pos(-cx, dy, 0) * plate_piece
            # Engraved on the plate's flat top at the key row's y, clear
            # of the posts and the columns in every slice.
            one -= Pos(0, dy, P.BOTTOM_T - 0.4) * extrude(
                _label(f"{fit:.2f}"), amount=0.5)
            one += Pos((x1 - x0) + gap - cx, dy, 0) * flipped
            part = one if part is None else part + one
    finally:
        P.SLIDE_FIT = was
    return part


def hole_coupon():
    """The switch-hole row on its own, at the real PLATE_T.

    `coupon()` asks four questions and three of them are answered --
    PILOT_DIA at 2.95, SCREW_CLEAR_DIA at 3.70, CLEAR_CHAMFER at 0.60,
    all settled on this machine with this filament. Only HOLE_SWEEP is
    open, because no Choc v2 had been on the desk. Reprinting the whole
    thing costs 6.36 cm3 to re-ask three settled questions; this is the
    row alone, the same reason `clear_coupon()` exists.

    The plate is the real 1.30 -- **that is half of what is being
    asked.** A Choc v2 clips into the plate, so the hole has to seat the
    switch *and* the thickness has to hold its clips. A thicker test
    plate would answer neither.
    """
    L = coupon_layout()
    margin = 3.0
    hole_pitch = P.SWITCH_HOLE + 4.0
    n = len(P.HOLE_SWEEP)
    w = (n - 1) * hole_pitch + P.SWITCH_HOLE + 2 * margin
    d = P.SWITCH_HOLE + 2 * margin + 6.0
    xs = [-w / 2 + margin + P.SWITCH_HOLE / 2 + i * hole_pitch for i in range(n)]

    part = _slab(w, d, 2.0, 0.0, P.PLATE_T)
    for x, dia in zip(xs, P.HOLE_SWEEP):
        part -= Pos(x, 0.0, -0.1) * extrude(
            RectangleRounded(dia, dia, P.PLATE_HOLE_R), amount=P.PLATE_T + 0.2)
        part -= Pos(x, P.SWITCH_HOLE / 2 + 2.5, P.PLATE_T - 0.4) * extrude(
            _label(f"{dia:.2f}"), amount=0.5)
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


# --- dummy keycap -------------------------------------------------------
# Prints top face DOWN on the bed, like the shell: the cavity opens
# upward, the bearing pad and the boss stand up out of it, and the bore
# opens up. Nothing overhangs, so there is no support anywhere in it.
def _cross(w, length, z0, z1):
    """An MX cross, centred on the origin."""
    return (_block(-length / 2, length / 2, -w / 2, w / 2, z0, z1)
            + _block(-w / 2, w / 2, -length / 2, length / 2, z0, z1))


def _socket_cut(z_mouth, sign, clear):
    """The bore, as a solid to subtract.

    `z_mouth` is the boss's free end and `sign` says which way the bore
    runs into the part from it: +1 up (the cap, drawn the way it is
    used, so its mouth faces down) and -1 down (the coupon, drawn the
    way it prints, mouth up). The
    first STEM_MOUTH of it is wider so the cross can find its way in --
    a step rather than a taper, because a cross-shaped taper is four
    more faces to get wrong and this one is 0.40 tall.
    """
    depth = P.CAP_ENGAGE + P.CAP_SOCKET_OVER
    w = P.STEM_CROSS_W + clear
    length = P.STEM_CROSS_L + P.STEM_LEN_CLEAR
    over = 0.6                       # past the mouth, into air
    z0, z1 = sorted((z_mouth - sign * over, z_mouth + sign * depth))
    cut = _cross(w, length, z0, z1)
    m0, m1 = sorted((z_mouth - sign * over, z_mouth + sign * 0.40))
    # Width-only: a mouth on the length as well thinned the closed
    # tube's arm corners below the nozzle for its first 0.40.
    return cut + _cross(w + P.STEM_MOUTH, length, m0, m1)


def dummy_cap():
    """One blank 1U cap. Case space, on a switch at the origin, at rest.

    The seat is the ring's rim, not the cross tip -- CAP_SOCKET_OVER of
    empty bore above the cross keeps the press off it.
    """
    z_seat = P.Z_BOARD_TOP + P.STEM_TOP
    z_ceil = z_seat + P.CAP_CEIL_RELIEF
    z_top = z_ceil + P.CAP_TOP_T
    z_skirt = P.Z_PLATE_TOP + P.CAP_RIDE

    part = _slab(P.CAP_XY, P.CAP_XY, P.CAP_R, z_skirt, z_top)
    part = _bed_chamfer(part, z_top, P.CAP_TOP_CHAMFER)
    inner = P.CAP_XY - 2 * P.CAP_WALL
    part -= _slab(inner, inner, P.CAP_CAVITY_R, z_skirt - 0.1, z_ceil)
    part += _tube(0, 0, z_seat, z_ceil, P.CAP_BEAR_DIA)
    boss = _tube(0, 0, z_seat - P.CAP_ENGAGE, z_seat, P.CAP_BOSS_DIA)
    # The boss is nearly a press in the ring; its leading edge gets a
    # lead-in, chamfered on the lone tube where the selection cannot
    # miss, and THEN four diagonal flats trim the contact down to the
    # arcs near the arms -- order matters, the chamfer needs the
    # unbroken circle edge.
    lead = boss.edges().group_by(Axis.Z)[0]
    boss = chamfer(lead, length=0.25)
    boss = boss & (Rotation(0, 0, 45) * Pos(0, 0, z_seat - P.CAP_ENGAGE / 2)
                   * Box(P.CAP_BOSS_FLATS, P.CAP_BOSS_FLATS,
                         P.CAP_ENGAGE + 2.0))
    part += boss
    part -= _socket_cut(z_seat - P.CAP_ENGAGE, +1, P.STEM_CLEAR)
    return part


def stem_coupon():
    """One token per STEM_CLEAR_SWEEP entry, pressed onto a real switch.

    The mount only -- pad, boss, bore -- at the heights the cap has
    them, so the slot prints in the same air the cap's does. Separate
    tokens rather than one bar: at SWITCH_PITCH a bar would engage every
    switch it spans at once, and the answer wanted here is one slot on
    one stem.
    """
    pitch = P.TOKEN_W + P.TOKEN_GAP
    n = len(P.STEM_CLEAR_SWEEP)
    z_seat = P.TOKEN_T + P.CAP_CEIL_RELIEF
    z_free = z_seat + P.CAP_ENGAGE
    part = None
    for i, clear in enumerate(P.STEM_CLEAR_SWEEP):
        x = (i - (n - 1) / 2) * pitch
        one = Pos(x, 0, 0) * extrude(
            RectangleRounded(P.TOKEN_W, P.TOKEN_D, 2.0), amount=P.TOKEN_T)
        one += _tube(x, 2.0, P.TOKEN_T, z_seat, P.CAP_BEAR_DIA)
        one += _tube(x, 2.0, z_seat, z_free, P.CAP_BOSS_DIA)
        one -= Pos(x, 2.0, 0) * _socket_cut(z_free, -1, clear)
        one -= Pos(x, -P.TOKEN_D / 2 + 4.0, -0.1) * extrude(
            _label(f"{clear:.2f}", flip=True), amount=0.6
        )
        part = one if part is None else part + one
    return part
