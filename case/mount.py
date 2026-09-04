#!/usr/bin/env python
"""Mounts that perch the macropad behind a tilted keyboard.

Four shapes, two keyboards, one builder. Every mount is the case's own
plan outline pushed down to the desk at the keyboard's tilt, its front
face square to the plate and butted against the keyboard's rear face,
with pegs into the case's foot recesses for location.

**The two keyboards are different solids and only their numbers differ
here.** The Nuphy Air75 is a tilted rectangle -- bottom parallel to the
plate, near bottom corner on the desk. The Keychron K11 Max is a wedge
-- bottom flat on the desk, plate tilted 3.33 off it. What the mount
needs from either is just two numbers: the plate's tilt, and how high
the pad's bottom sits above the desk where it meets the rear face. So
`_build` takes exactly those, and each keyboard has a thin function
that works them out its own way.

`_build` works in **plate-local** coordinates: the origin sits on the
keyboard's rear face at the pad's bottom, +y runs rearward along the
plate, +z off it. The pad spans y in [-over, CASE_D - over], so the
prism's own front face is the plane y = 0 and nothing has to be
trimmed unless the pad overhangs the keyboard.
"""
import math
import sys
from pathlib import Path

from build123d import (Axis, Box, Cylinder, Pos, RectangleRounded, Rotation,
                       chamfer, extrude)

import params as P
from build import OUT, _shared, check, export_step_stable
from build123d import export_stl

TILT = P.KB_TILT       # the Air75's, kept as a module constant for its stand-ins
DEEP = 60.0            # how far below the cradle the prism is drawn before the desk cuts it


def _tilt(shape, tilt=None):
    """Rotate about x so +y climbs at the keyboard's tilt."""
    return Rotation(TILT if tilt is None else tilt, 0, 0) * shape


def _desk_cut(shape):
    """Keep what is above the desk."""
    keep = Pos(0, 0, 100.0) * Box(400, 400, 200)
    return shape & keep


def _case_y0(over):
    """Slab-local y of the case's near face: the keyboard's rear face, less the overhang."""
    return P.KB_D - over


def _pegs(over, near_h=None):
    """Pegs standing off the cradle into the pad's foot recesses.

    Plate-local, so the pad's centre is at y = CASE_D/2 - over and the
    mount's front face is y = 0. A recess whose peg would be mostly out
    over the keyboard gets no peg at all: what survives the front-face
    cut there is a fin, not a locator.
    """
    out = None
    for x, y in P.FOOT_XY:
        yc = P.CASE_D / 2 - over + y
        if yc < P.MOUNT_PEG_DIA / 4:
            continue
        peg = Pos(x, yc, P.MOUNT_PEG_H / 2) * Cylinder(
            P.MOUNT_PEG_DIA / 2, P.MOUNT_PEG_H)
        out = peg if out is None else out + peg
    return out


def _plan(inset, z0, depth, over):
    """The pad's plan outline, inset by `inset`, extruded down from z0."""
    return Pos(0, P.CASE_D / 2 - over, z0 - depth) * extrude(
        RectangleRounded(P.CASE_W - 2 * inset, P.CASE_D - 2 * inset,
                         max(P.OUTER_CORNER_R - inset, 0.5)), amount=depth)


def _hollow(over, front_wall=True):
    """What to take out of the block: the bays between the ribs. The cradle
    stays solid and bridges each bay, so printing it desk-face-down leaves
    nothing overhanging; `_build` trims these off the floor."""
    cav = _plan(P.MOUNT_WALL, -P.MOUNT_WALL, DEEP, over)
    # The cavity is inset from the **pad's** outline, whose front edge stands
    # `over` forward of the mount's front cut -- so inset alone leaves the
    # cavity poking through that cut and the mount with no front wall at
    # all. Hold it back MOUNT_WALL behind the cut as well. The front-post
    # probe is what found this: 28.3 of a 36 mm3 box that should have been
    # solid, because behind the face there was nothing.
    if front_wall:
        cav &= Pos(0, 200.0 + P.MOUNT_WALL, -DEEP / 2) * Box(500, 400, DEEP + 4)
    n = int(P.CASE_W // P.MOUNT_RIB_PITCH)
    ribs = None
    for i in range(-n, n + 1):
        x = i * P.MOUNT_RIB_PITCH
        if abs(x) > P.CASE_W / 2:
            continue
        r = Pos(x, P.CASE_D / 2 - over, -DEEP / 2) * Box(P.MOUNT_RIB_W, P.CASE_D, DEEP + 2)
        ribs = r if ribs is None else ribs + r
    return cav if ribs is None else cav - ribs


def _cable_slot(tilt, face_y0, dx, x_from, w, depth, lo_h, top_h):
    """The slot the cable runs right through, **in world coordinates**:
    between `lo_h` and `top_h` above the desk, cut `depth` back from the
    keyboard's rear face.

    World, not plate-local, because the cable is horizontal and the mount
    is not. Cut plate-parallel, the slot's floor climbs 0.815 across its
    own 14 mm depth and shaves the cable at the back -- 1.744 mm3 of it,
    which is what the stand-in caught.

    A slot rather than a step to the desk: the cable floats at about the
    middle of the keyboard's base height, so the floor and the lower front
    wall both stay and the section stays closed. What roofs it is cradle,
    bridging `depth` -- short enough to print flat, desk face on the bed.
    """
    y0 = face_y0 - top_h * math.tan(math.radians(tilt)) - 1.0
    return Pos(dx + x_from + w / 2, y0 + (depth + 1.0) / 2, (lo_h + top_h) / 2) * Box(
        w, depth + 1.0, top_h - lo_h)


def _notch(near_h, tilt, x, w, depth, floor_h):
    """The cable relief, cut back from the front face. `floor_h` is a height
    above the desk; the mount is built plate-local, so it converts through
    the same cosine the rest of the frame uses. Open at the top, which is
    what keeps it free of overhangs."""
    z_floor = (floor_h - near_h) / math.cos(math.radians(tilt))
    return Pos(x, depth / 2 - 1.0, (z_floor + 1.0) / 2) * Box(
        w, depth + 2.0, 1.0 - z_floor)


def _build(tilt, near_h, face_y0, over, notch=None, cable=None, hollow=False, dx=0.0):
    """A mount, in world coordinates, desk face at z 0.

    `tilt` is the plate's angle to the desk, `near_h` is how high the pad's
    bottom sits where it meets the keyboard's rear face, and `face_y0` is
    where that face -- extended if it has to be -- meets the desk. Those
    three are everything the shape needs; which keyboard they came from,
    and whether it is a tilted rectangle or a wedge, does not reach here.
    """
    near_y = face_y0 - near_h * math.tan(math.radians(tilt))
    to_world = lambda sh: Pos(dx, near_y, near_h) * _tilt(sh, tilt)
    front = Pos(0, 100.0, -DEEP / 2) * Box(400, 200, DEEP + 2)

    # The bed chamfer is taken on the bare block, before anything is cut
    # into it: there is one planar face at z 0 then and one loop of edges
    # round it. Hollow it first and that face is a ring threaded by every
    # rib, which is dozens of edges and an OCCT failure -- the same reason
    # `parts._bed_chamfer` insists on the base slab.
    part = _desk_cut(to_world((_plan(0.0, 0.0, DEEP, over) + _pegs(over)) & front))
    face = part.faces().filter_by_position(Axis.Z, -1e-6, 1e-6)
    part = chamfer(face.edges(), length=P.ELEPHANT_CHAMFER)

    if hollow:
        # The bays stop MOUNT_FLOOR above the desk, so the part keeps a
        # floor. That has to be trimmed in **world** coordinates: the desk
        # is a tilted plane in the plate-local frame the bays are built in,
        # so there is no constant z there that means "this far off the desk".
        above = Pos(0, 0, 200.0 + P.MOUNT_FLOOR) * Box(600, 600, 400)
        part -= to_world(_hollow(over) & front) & above
    if notch is not None:
        part -= to_world(_notch(near_h, tilt, *notch))
    if cable is not None:
        part -= _cable_slot(tilt, face_y0, dx, *cable)
    return part


def mount(raise_, over):
    """The Air75's mounts. It is a tilted rectangle standing on its near
    bottom corner, so the pad's bottom at the rear face is the slab's depth
    times the sine plus the raise, and the rear face reaches the desk one
    secant beyond the slab's depth."""
    t = math.radians(TILT)
    near_h = P.KB_D * math.sin(t) + raise_ * math.cos(t)
    return _build(TILT, near_h, P.KB_D / math.cos(t), over)


def k11_mount():
    """The K11 Max's. It is a wedge lying flat on the desk, so the pad's
    bottom at the rear face is simply the plate's height there."""
    nx = P.K11_PORT_X - P.K11_PAD_DX
    notch = (nx, P.K11_NOTCH_W, P.K11_NOTCH_D, P.K11_NOTCH_FLOOR)
    # everything right of the pocket, out to the pad's own right edge
    # The channel starts at the pocket's **left** edge, not its right. The
    # pocket's floor stands at K11_NOTCH_FLOOR so it leaves the mount's own
    # floor intact underneath, and the cable lies on the desk -- so without
    # this overlap the first stretch of cable out of the plug sits on 2 mm
    # of floor. Caught at 68.6 mm3 the moment the floor went in.
    x_from = nx - P.K11_NOTCH_W / 2
    # right through the end: the cable has to be able to leave
    x_to = P.CASE_W / 2 + P.K11_SLOT_OUT
    cable = (x_from, x_to - x_from, P.K11_CABLE_D, P.K11_CABLE_LO, P.K11_CABLE_H)
    return _build(P.K11_TILT, P.K11_PLATE_REAR, P.K11_D, P.K11_OVER,
                  notch=notch, cable=cable, hollow=True, dx=P.K11_PAD_DX)


# --- stand-ins -----------------------------------------------------------
def keyboard():
    """The Air75 as a slab, wider than anything here."""
    return _tilt(Pos(0, P.KB_D / 2, P.KB_T / 2) * Box(320.0, P.KB_D, P.KB_T))


def case(raise_, over, dx=0.0, dy=0.0):
    """The case as a slab with its foot recesses, on the cradle; dx/dy
    shift it in the plate plane for the peg probes."""
    y0 = _case_y0(over)
    slab = Pos(0, y0 + P.CASE_D / 2, raise_) * extrude(
        RectangleRounded(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R), amount=P.CASE_H)
    for x, y in P.FOOT_XY:
        slab -= Pos(x, y0 + P.CASE_D / 2 + y, raise_ + P.FOOT_RECESS / 2 - 0.05) * Cylinder(
            P.FOOT_DIA / 2, P.FOOT_RECESS + 0.1)
    return _tilt(Pos(dx, dy, 0) * slab)


def usb_plug(raise_, over):
    """A plug in the case's port, hanging off the +x end."""
    y0 = _case_y0(over)
    zc = raise_ + (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
    return _tilt(Pos(P.CASE_W / 2 + P.USB_PLUG_L / 2, y0 + P.CASE_D / 2 + P.USB_CY, zc)
                 * Box(P.USB_PLUG_L, P.USB_PLUG_W, P.USB_PLUG_H))


def _world(y, z):
    """Slab-local (y, z) to world (y, z), the same rotation `_tilt` applies."""
    a = math.radians(TILT)
    return (y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))


def _vol(a, b):
    """Shared volume, 0.0 for an empty intersection -- and only for that.

    `build._shared` catches the one ValueError OCCT raises for "nothing
    in common". Anything else propagates, because a probe that reads
    0.0 on a failed boolean reads as "no collision" and the run ends in
    `all checks passed` about a mount nobody checked.
    """
    return _shared(a, b)


def checks(name, raise_, over, part):
    """Every check for one mount; returns the list of booleans."""
    ok = []
    kb = keyboard()
    cs = case(raise_, over)
    bb = part.bounding_box()

    ok.append(check(f"{name}: bottom on the desk", bb.min.Z, 0.0, 1e-3))
    below = Pos(0, 0, -5.0) * Box(400, 400, 10)
    ok.append(check(f"{name}: nothing below the desk", _vol(part, below), 0.0, 1e-3))
    ok.append(check(f"{name}: mount vs keyboard", _vol(part, kb), 0.0, 1e-3))
    ok.append(check(f"{name}: case vs keyboard", _vol(cs, kb), 0.0, 1e-3))
    ok.append(check(f"{name}: mount vs case (pegs in recesses)", _vol(part, cs), 0.0, 1e-3))
    ok.append(check(f"{name}: mount vs USB plug", _vol(part, usb_plug(raise_, over)), 0.0, 1e-3))

    # The pegs must catch: a case shifted less than a recess's radius in
    # any plate direction has to hit them.
    for lab, dx, dy in (("+x", 1.0, 0.0), ("-x", -1.0, 0.0), ("+y", 0.0, 1.0), ("-y", 0.0, -1.0)):
        v = _vol(part, case(raise_, over, dx, dy))
        good = v > 0.05
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {name + ': pegs catch a case shifted ' + lab:<38} {v:8.3f}  (want > 0.05)")

    # Plate height at the case's near edge, against the arithmetic.
    want = _world(P.KB_D - over, raise_ + P.CASE_H)[1]
    cbb = cs.bounding_box()
    # the near top edge of the case is its lowest top point; read the
    # case's max Z minus the rise over its depth
    a = math.radians(TILT)
    near_top = cbb.max.Z - P.CASE_D * math.sin(a)
    ok.append(check(f"{name}: case plate top at its near edge", near_top, want, 0.02))

    # The front face is on the keyboard's rear face: a thin probe just
    # ahead of the mount, over the height they share, lies wholly in
    # the keyboard.
    z_lo, z_hi = 0.5, min(raise_, P.KB_T) - 0.5
    probe = _tilt(Pos(0, P.KB_D - 0.25, (z_lo + z_hi) / 2)
                  * Box(P.CASE_W - 2 * P.OUTER_CORNER_R, 0.5, z_hi - z_lo))
    ok.append(check(f"{name}: front face on the keyboard's rear face",
                    _vol(probe, kb), probe.volume, 0.01))
    ok.append(check(f"{name}: front probe clear of the mount", _vol(probe, part), 0.0, 1e-3))

    # The cradle is one plane with whatever else carries the case. For
    # the raised mount that is the keyboard's plate: a probe under the
    # overhang lies wholly in the keyboard.
    if over > 0:
        probe = _tilt(Pos(0, P.KB_D - over / 2, raise_ - 0.25)
                      * Box(P.CASE_W - 2 * P.OUTER_CORNER_R, over - 0.5, 0.5))
        ok.append(check(f"{name}: overhang rests on the keyboard's plate",
                        _vol(probe, kb), probe.volume, 0.01))
    # And under the rest of the case the mount is there, right up to the
    # surface: a probe just below the cradle is wholly mount, pegs aside.
    y_a, y_b = P.KB_D + 1.0, P.KB_D - over + P.CASE_D - P.OUTER_CORNER_R
    probe = _tilt(Pos(0, (y_a + y_b) / 2, raise_ - 0.25)
                  * Box(P.CASE_W - 2 * P.OUTER_CORNER_R, y_b - y_a, 0.5))
    ok.append(check(f"{name}: cradle is solid up to the case bottom",
                    _vol(probe, part), probe.volume, 0.01))

    foot_x = P.KB_D / math.cos(a) - _world(P.KB_D, 0)[0]
    print(f"        {name}: mount's foot lands {foot_x:.2f} behind the keyboard's bottom corner, "
          f"{bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f}, {part.volume / 1000:.1f} cm3")
    return ok


def figure(built):
    """out/<layout>/mount.png: the two mounts with the keyboard and case
    stand-ins, side and iso, so a change can be looked at."""
    import tempfile

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import trimesh

    import shade

    def tris_of(shape):
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            path = Path(f.name)
        try:
            export_stl(shape, str(path), tolerance=0.02, angular_tolerance=0.2)
            m = trimesh.load(path)
        finally:
            path.unlink(missing_ok=True)
        return m.vertices[m.faces], m.face_normals

    fig, axes = plt.subplots(len(built), 2, figsize=(15, 3.0 * len(built)))
    if len(built) == 1:
        axes = np.array([axes])
    for row, (name, entry) in zip(axes, built.items()):
        if name.startswith("mount-k11"):
            parts = [(entry, (0.85, 0.33, 0.12)),
                     (k11_case(), (0.17, 0.17, 0.16)),
                     (k11_keyboard(), (0.80, 0.78, 0.72)),
                     (k11_plug(), (0.70, 0.15, 0.12)),
                     (k11_cable(), (0.70, 0.15, 0.12))]
            bounds = np.array([[-98.0, 96.0, -1.0], [70.0, 148.0, 26.0]])
        else:
            raise_, over, part = entry
            parts = [(part, (0.85, 0.33, 0.12)),
                     (case(raise_, over), (0.17, 0.17, 0.16)),
                     (keyboard(), (0.80, 0.78, 0.72))]
            bounds = np.array([[-98.0, 100.0, -1.0], [70.0, 172.0, 42.0]])
        meshes = [(*tris_of(shape), rgb) for shape, rgb in parts]
        # The iso looks from **behind**: the mount is what is being designed
        # and from the front the macropad hides all of it.
        for ax, (view, elev, azim) in zip(row, (("side", 0, 0), ("iso, from behind", 26, 118))):
            img = shade.render(meshes, elev, azim, size=(820, 300), bounds=bounds)
            ax.imshow(img)
            ax.set_axis_off()
            ax.set_title(f"{name}  ({view})", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "mount.png", dpi=110)
    print(f"  mount.png")


# --- the K11 Max, and what has to clear it -------------------------------
def k11_keyboard():
    """The keyboard as a wedge: bottom flat on the desk, plate tilted, front
    and rear faces square to the plate. Not a guess -- its bottom is one
    33,000 mm2 planar face in Keychron's STEP, 3.33 off the plate's normal.

    Built as a block cut by the plate plane: the plane passes through the
    rear face at K11_PLATE_REAR and falls forward at the typing angle, and
    the rear face itself is square to it, so the block's own rear wall has
    to lean with it rather than stand upright.
    """
    t = math.radians(P.K11_TILT)
    # Both planes pivot on the rear face's **bottom** edge, where it meets
    # the desk -- not on the plate. Pivoting at plate height instead leans
    # the face 0.85 too far back, and the mount then reads as interfering
    # by 338 mm3 with a keyboard that was drawn wrong.
    h = P.K11_PLATE_REAR / math.cos(t)          # plate height measured up the face
    under = Pos(0, P.K11_D, 0) * _tilt(
        Pos(0, 0, h - 200.0) * Box(P.K11_W + 40, 400.0, 400.0), P.K11_TILT)
    ahead = Pos(0, P.K11_D, 0) * _tilt(
        Pos(0, -200.0, 0) * Box(P.K11_W + 40, 400.0, 400.0), P.K11_TILT)
    block = Pos(0, P.K11_D / 2, 15.0) * Box(P.K11_W, P.K11_D + 40, 30.0)
    return block & under & ahead


def k11_plug(grow=0.0):
    """The L-plug in the rear port: the body standing back off the face,
    drawn `grow` larger all round to ask the notch for margin."""
    t = math.radians(P.K11_TILT)
    w = P.K11_PORT_W + 8.0 + 2 * grow            # the shell is wider than the opening
    lo, hi = P.K11_PORT_LO - grow, P.K11_PORT_HI + grow
    depth = 12.0 + grow
    zc = (lo + hi) / 2
    y0 = P.K11_D - zc * math.tan(t)
    return Pos(P.K11_PORT_X, y0 + depth / 2, zc) * Box(w, depth, hi - lo)


def k11_cable(dia=6.0):
    """The cable leaving the plug, running **straight right** hard against
    the keyboard's rear face -- the worst case for the slot.

    It does not lie on the desk: it **floats at about the middle of the
    keyboard's base height**, which is what lets the mount keep its floor
    and its lower front wall. It runs out past the pad's right edge,
    because leaving is the part that has to work: a slot the cable cannot
    get out of is a slot it never got into.
    """
    x0 = P.K11_PORT_X + (P.K11_PORT_W + 8.0) / 2
    x1 = P.K11_PAD_DX + P.CASE_W / 2 + 12.0     # out past the right edge
    zc = P.K11_PLATE_REAR / 2
    return Pos((x0 + x1) / 2, P.K11_D + dia / 2, zc) * Box(x1 - x0, dia, dia)


def k11_case(dx=0.0, dy=0.0):
    """The macropad on the K11's mount, with its foot recesses."""
    t = math.radians(P.K11_TILT)
    near_h = P.K11_PLATE_REAR
    near_y = P.K11_D - near_h * math.tan(t)
    slab = Pos(0, P.CASE_D / 2 - P.K11_OVER, P.CASE_H / 2) * Box(P.CASE_W, P.CASE_D, P.CASE_H)
    slab = Pos(0, P.CASE_D / 2 - P.K11_OVER, 0) * extrude(
        RectangleRounded(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R), amount=P.CASE_H)
    for x, y in P.FOOT_XY:
        slab -= Pos(x, P.CASE_D / 2 - P.K11_OVER + y, P.FOOT_RECESS / 2 - 0.05) * Cylinder(
            P.FOOT_DIA / 2, P.FOOT_RECESS + 0.1)
    # dx/dy shift the pad **along the plate**, inside the tilt. Shifting it
    # horizontally instead slides it into a cradle that rises at 3.33, and
    # the probe then measures the whole underside sinking rather than the
    # pegs catching -- 129.5 mm3 of the wrong thing, and a check that could
    # not have gone red for the reason it claims.
    return Pos(P.K11_PAD_DX, near_y, near_h) * _tilt(Pos(dx, dy, 0) * slab, P.K11_TILT)


def k11_checks(part):
    ok = []
    kb, cs = k11_keyboard(), k11_case()
    bb = part.bounding_box()
    ok.append(check("k11: bottom on the desk", bb.min.Z, 0.0, 1e-3))
    ok.append(check("k11: nothing below the desk",
                    _vol(part, Pos(0, 0, -5.0) * Box(500, 500, 10)), 0.0, 1e-3))
    ok.append(check("k11: mount vs keyboard", _vol(part, kb), 0.0, 1e-3))
    ok.append(check("k11: mount vs case", _vol(part, cs), 0.0, 1e-3))

    # The plug is the reason the mount is this height and has a notch at all.
    ok.append(check("k11: mount vs the L-plug", _vol(part, k11_plug()), 0.0, 1e-3))
    ok.append(check("k11: case vs the L-plug", _vol(cs, k11_plug()), 0.0, 1e-3))
    ok.append(check("k11: notch keeps 4.0 round the plug", _vol(part, k11_plug(4.0)), 0.0, 1e-3))
    # The plug is only half of it: the cable runs right out of the L and
    # back across the desk, straight through where the mount stands.
    ok.append(check("k11: mount vs the cable", _vol(part, k11_cable()), 0.0, 1e-3))
    ok.append(check("k11: slot keeps an 8 mm cable", _vol(part, k11_cable(8.0)), 0.0, 1e-3))

    # The notch has to be a hole, not a claim: a solid mount would fill it.
    solid = _build(P.K11_TILT, P.K11_PLATE_REAR, P.K11_D, P.K11_OVER, dx=P.K11_PAD_DX)
    cut = solid.volume - _build(P.K11_TILT, P.K11_PLATE_REAR, P.K11_D, P.K11_OVER,
                                notch=(P.K11_PORT_X - P.K11_PAD_DX, P.K11_NOTCH_W,
                                       P.K11_NOTCH_D, P.K11_NOTCH_FLOOR),
                                dx=P.K11_PAD_DX).volume
    good = cut > 500.0
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'k11: the notch removes material':<38} {cut:8.3f}  (want > 500)")

    # And the shell has to be hollow, or `thin` was only ever a comment.
    frac = part.volume / solid.volume
    good = frac < 0.75
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'k11: shell is hollow, vol fraction':<38} {frac:8.3f}  (want < 0.75)")

    # Pegs still catch the pad in every direction.
    for lab, dx, dy in (("+x", 1.0, 0.0), ("-x", -1.0, 0.0), ("+y", 0.0, 1.0), ("-y", 0.0, -1.0)):
        v = _vol(part, k11_case(dx, dy))
        good = v > 0.05
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {'k11: pegs catch a case shifted ' + lab:<38} {v:8.3f}  (want > 0.05)")

    # The cradle must be there under each peg that survived the front cut.
    t = math.radians(P.K11_TILT)
    near_y = P.K11_D - P.K11_PLATE_REAR * math.tan(t)
    for i, (x, y) in enumerate(P.FOOT_XY):
        yc = P.CASE_D / 2 - P.K11_OVER + y
        probe = Pos(P.K11_PAD_DX + x, near_y, P.K11_PLATE_REAR) * _tilt(
            Pos(0, yc, -0.3) * Box(P.MOUNT_PEG_DIA, P.MOUNT_PEG_DIA, 0.5), P.K11_TILT)
        got, want = _vol(part, probe), probe.volume
        good = got > want * 0.45
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {'k11: cradle under peg ' + str(i):<38} "
              f"{got:8.3f}  (want > {want*0.45:.3f} of {want:.3f})")

    # The slot has to run out of the right end, or the cable cannot leave.
    # A post there would have closed it -- and a post with a hole for the
    # cable is the same solid as this, which is why there is none.
    t = math.radians(P.K11_TILT)
    x_edge = P.K11_PAD_DX + P.CASE_W / 2
    for lab, x in (("inboard", x_edge - 6.0), ("at the edge", x_edge - 1.0)):
        y_face = P.K11_D - (P.K11_PLATE_REAR / 2) * math.tan(t)
        probe = Pos(x, y_face + 5.0, P.K11_PLATE_REAR / 2) * Box(2.0, 8.0, 4.0)
        got = _vol(part, probe)
        good = got < 1e-3
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {'k11: slot open at the right, ' + lab:<38} "
              f"{got:8.3f}  (want 0.000)")

    print(f"        k11: {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f}, "
          f"{part.volume/1000:.1f} cm3 hollow against {solid.volume/1000:.1f} solid; "
          f"pad {P.K11_PAD_DX:+.2f} across, {P.K11_OVER:.2f} forward")
    return ok


def main():
    """Build every mount once, export them, draw them, check them."""
    OUT.mkdir(parents=True, exist_ok=True)
    ok = []
    # The frame: +y must climb, or the whole thing is mirrored about the desk.
    probe = _tilt(Pos(0, 10.0, 0) * Box(1, 1, 1)).center()
    ok.append(check("frame: +y climbs at the tilt", probe.Z, 10.0 * math.sin(math.radians(TILT)), 1e-3))
    ok.append(check("keyboard far corner height", _world(P.KB_D, P.KB_T)[1], P.KB_FAR, 1e-3))
    ok.append(check("keyboard near corner height", _world(0, P.KB_T)[1], P.KB_NEAR, 1e-3))

    variants = {
        "mount-raised": (P.KB_T, P.MOUNT_OVER),
        "mount-flush": (P.KB_T - P.CASE_H, 0.0),
    }
    built = {name: (raise_, over, mount(raise_, over))
             for name, (raise_, over) in variants.items()}
    k11 = k11_mount()
    print("\nexported")
    export_stl(k11, str(OUT / "mount-k11.stl"), tolerance=0.005, angular_tolerance=0.1)
    export_step_stable(k11, str(OUT / "mount-k11.step"))
    print("  mount-k11")
    for name, (_, _, part) in built.items():
        export_stl(part, str(OUT / f"{name}.stl"), tolerance=0.005, angular_tolerance=0.1)
        export_step_stable(part, str(OUT / f"{name}.step"))
        print(f"  {name}")
    figure({**built, "mount-k11": k11})
    print()
    for name, (raise_, over, part) in built.items():
        ok += checks(name, raise_, over, part)
    ok += k11_checks(k11)
    print("\n" + ("all checks passed" if all(ok) else "SOMETHING IS WRONG"))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
