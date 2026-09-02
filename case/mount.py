#!/usr/bin/env python
"""Mounts that perch the macropad behind a tilted keyboard.

Two shapes from one function: `raised` (case bottom on the keyboard's
plate plane, slid MOUNT_OVER toward the user) and `flush` (case plate
top on the keyboard's plate plane). Both are the case's own plan
outline pushed down to the desk at the keyboard's tilt, with pegs into
the case's foot recesses for location.

Everything is built in **slab-local** coordinates -- x along the
keyboard's width, y toward the far end, z up off the plate -- with the
origin at the keyboard's near bottom corner, then tilted about x by
KB_TILT and cut off flat at the desk. The keyboard is the box
[0, KB_D] x [0, KB_T] in (y, z), and the case sits with its bottom at
z = raise, its near face at y = KB_D - over.
"""
import math
import sys
from pathlib import Path

from build123d import (Axis, Box, Cylinder, Pos, RectangleRounded, Rotation,
                       chamfer, extrude)

import params as P
from build import OUT, _shared, check, export_step_stable
from build123d import export_stl

TILT = P.KB_TILT
DEEP = 60.0            # how far below the cradle the prism is drawn before the desk cuts it


def _tilt(shape):
    """Slab-local to world: rotate about x so +y climbs at the keyboard's tilt."""
    return Rotation(TILT, 0, 0) * shape


def _desk_cut(shape):
    """Keep what is above the desk."""
    keep = Pos(0, 0, 100.0) * Box(400, 400, 200)
    return shape & keep


def _case_y0(over):
    """Slab-local y of the case's near face: the keyboard's rear face, less the overhang."""
    return P.KB_D - over


def _pegs(raise_, over):
    """Pegs on the cradle, at the foot recesses that land over the mount."""
    y0 = _case_y0(over)
    out = None
    for x, y in P.FOOT_XY:
        yc = y0 + P.CASE_D / 2 + y
        if yc - P.MOUNT_PEG_DIA / 2 < P.KB_D:
            continue          # this recess hangs over the keyboard
        peg = Pos(x, yc, raise_ + P.MOUNT_PEG_H / 2) * Cylinder(
            P.MOUNT_PEG_DIA / 2, P.MOUNT_PEG_H)
        out = peg if out is None else out + peg
    return out


def mount(raise_, over):
    """The mount in world coordinates, desk face at z 0."""
    y0 = _case_y0(over)
    plan = Pos(0, y0 + P.CASE_D / 2, raise_ - DEEP) * extrude(
        RectangleRounded(P.CASE_W, P.CASE_D, P.OUTER_CORNER_R), amount=DEEP)
    # Nothing forward of the keyboard's rear face: the front is a flat
    # cut at y = KB_D, square to the plate, that the keyboard's own face
    # lands on.
    behind = Pos(0, P.KB_D + 100.0, raise_ - DEEP / 2) * Box(400, 200, DEEP + 1)
    part = plan & behind
    part += _pegs(raise_, over)
    part = _desk_cut(_tilt(part))
    # The desk face is the bed. One planar face at z 0, one loop of edges.
    face = part.faces().filter_by_position(Axis.Z, -1e-6, 1e-6)
    part = chamfer(face.edges(), length=P.ELEPHANT_CHAMFER)
    return part


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
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    def tris_of(shape):
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            path = Path(f.name)
        try:
            export_stl(shape, str(path), tolerance=0.02, angular_tolerance=0.2)
            m = trimesh.load(path)
        finally:
            path.unlink(missing_ok=True)
        return m.vertices[m.faces], m.face_normals

    fig, axes = plt.subplots(len(built), 2, figsize=(14, 4.2 * len(built)),
                             subplot_kw={"projection": "3d"})
    for row, (name, (raise_, over, part)) in zip(axes, built.items()):
        parts = [(part, (0.85, 0.33, 0.12)),
                 (case(raise_, over), (0.17, 0.17, 0.16)),
                 (Pos(0, 0, 0) * keyboard(), (0.80, 0.78, 0.72))]
        for ax, (view, elev, azim) in zip(row, (("side", 0, 0), ("iso", 24, -55))):
            tris, cols = [], []
            for shape, rgb in parts:
                t, n = tris_of(shape)
                e, a = np.radians(elev), np.radians(azim)
                light = np.array([0.35, -0.5, 0.79])
                shade = 0.45 + 0.55 * np.clip(np.abs(n @ light), 0, 1)
                tris.append(t)
                cols.append(np.stack([shade * rgb[0], shade * rgb[1], shade * rgb[2],
                                      np.ones_like(shade)], 1))
            tris, cols = np.concatenate(tris), np.concatenate(cols)
            eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
            order = np.argsort(tris.mean(axis=1) @ eye)
            ax.add_collection3d(Poly3DCollection(tris[order], facecolors=cols[order],
                                                 edgecolors="none"))
            lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
            if view == "side":
                lo, hi = np.array([-20, 95, -3]), np.array([20, 175, 45])
            mid, span = (lo + hi) / 2, (hi - lo).max() / 2
            ax.set_xlim(mid[0] - span, mid[0] + span)
            ax.set_ylim(mid[1] - span, mid[1] + span)
            ax.set_zlim(mid[2] - span, mid[2] + span)
            ax.set_box_aspect((1, 1, 1))
            ax.view_init(elev=elev, azim=azim)
            ax.set_axis_off()
            ax.set_title(f"{name}  ({view})", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "mount.png", dpi=110)
    print(f"  mount.png")


def main():
    """Build both mounts once, export them, draw them, check them."""
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
    print("\nexported")
    for name, (_, _, part) in built.items():
        export_stl(part, str(OUT / f"{name}.stl"), tolerance=0.005, angular_tolerance=0.1)
        export_step_stable(part, str(OUT / f"{name}.step"))
        print(f"  {name}")
    figure(built)
    print()
    for name, (raise_, over, part) in built.items():
        ok += checks(name, raise_, over, part)
    print("\n" + ("all checks passed" if all(ok) else "SOMETHING IS WRONG"))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
