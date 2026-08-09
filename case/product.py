"""Assembled and exploded views of the whole thing.

    .venv/bin/python product.py     ->  out/product.png

Presentation only. Nothing here is checked against anything and no
dimension in this file is load-bearing -- `mock.py` holds the envelopes
that matter and `build.py` is what decides whether the case is buildable.
The switch and keycap shapes below are eyeballed from a Cherry-profile
1U cap because there is no keycap in the design to measure; they exist so
the pad can be looked at, not so it can be verified.

The four keys wear the status colours from the main README, because the
one thing a photograph of this device should say is what it is for.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from build123d import (  # noqa: E402
    Axis,
    Box,
    Plane,
    Pos,
    RectangleRounded,
    Sphere,
    export_stl,
    loft,
)
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

import params as P  # noqa: E402
import parts  # noqa: E402

OUT = Path(__file__).parent / "out" / P.LAYOUT
TMP = OUT / "tmp"

# From README.md "Status colors". Left to right: idle, running, awaiting
# approval, done-unread -- the three that matter plus a resting key.
KEY_COLORS = ["#273027", "#0040ff", "#ff8000", "#00ff00"]

CASE_COLOR = "#858b95"
BOARD_COLOR = "#14171c"
LED_COLOR = "#f4f7ff"
SWITCH_COLOR = "#cdd7e4"

# Eyeballed Cherry-profile 1U, not measured off anything.
SW_FLANGE = 15.6
SW_FLANGE_H = 1.2
SW_TOP = 11.0
SW_H = 5.9
# A real cap skirts down over the top housing rather than perching on
# it -- perched, the render reads as four loose lids. 5.0 above the
# plate puts the housing half-hidden, the way a keyboard looks.
CAP_RIDE = 5.0
CAP_BASE = 18.0
CAP_TOP = 13.4
CAP_H = 9.4


def switch_body(x, y):
    """The part of an MX switch that shows above the plate.

    Lifted a hair off the plate it actually rests on. Coplanar faces
    have no correct depth ordering, and at 0.00 the flange and the
    plate top fight for the same pixel. Presentation only -- the real
    switch sits flat and `mock.py` models it that way.
    """
    z0 = P.Z_PLATE_TOP + 0.05
    flange = Pos(x, y, z0) * extrude_rect(SW_FLANGE, SW_FLANGE, 0.8, SW_FLANGE_H)
    upper = Pos(x, y, z0 + SW_FLANGE_H) * loft([
        Plane.XY.offset(0) * RectangleRounded(SW_FLANGE - 0.6, SW_FLANGE - 0.6, 0.8),
        Plane.XY.offset(SW_H) * RectangleRounded(SW_TOP, SW_TOP, 1.2),
    ])
    return flange + upper


def keycap(x, y):
    """A 1U cap, tapered and dished. Shape only -- nothing depends on it."""
    z0 = P.Z_PLATE_TOP + CAP_RIDE
    body = Pos(x, y, z0) * loft([
        Plane.XY.offset(0) * RectangleRounded(CAP_BASE, CAP_BASE, 1.2),
        Plane.XY.offset(CAP_H) * RectangleRounded(CAP_TOP, CAP_TOP, 2.4),
    ])
    # Dish the top with a big sphere, the way a real cap is scooped.
    body -= Pos(x, y, z0 + CAP_H + 28.0) * Sphere(radius=28.6)
    return body


def extrude_rect(w, d, r, h):
    from build123d import extrude

    return extrude(RectangleRounded(w, d, r), amount=h)


def board(w, d, r, cx, cy, z0, t):
    return Pos(cx, cy, z0) * extrude_rect(w, d, r, t)


def scene():
    """Every piece, with the colour it should be drawn in."""
    items = [
        ("bottom", parts.bottom(), CASE_COLOR, 1.0, 0.0),
        ("shell", parts.shell(), CASE_COLOR, 1.0, 38.0),
        (
            "qtpy",
            board(P.QTPY_PLAN_W, P.QTPY_PLAN_D, P.QTPY_CORNER_R,
                  P.QTPY_CENTER[0], P.QTPY_CENTER[1],
                  P.Z_QTPY_LOW, P.QTPY_T),
            BOARD_COLOR, 1.0, 8.0,
        ),
        (
            "neokey",
            board(P.NEOKEY_W, P.NEOKEY_D, P.NEOKEY_CORNER_R,
                  P.NEOKEY_CENTER[0], P.NEOKEY_CENTER[1],
                  P.Z_NEOKEY_BOTTOM, P.NEOKEY_T),
            BOARD_COLOR, 1.0, 20.0,
        ),
    ]
    for i, (sx, sy) in enumerate(P.SWITCH_XY):
        items.append((
            f"led{i}",
            Pos(sx, sy, P.Z_NEOKEY_TOP + 0.6) * Box(3.5, 3.5, 1.2),
            KEY_COLORS[i], 1.0, 20.0,
        ))
        items.append((f"sw{i}", switch_body(sx, sy), SWITCH_COLOR, 0.45, 46.0))
        items.append((f"cap{i}", keycap(sx, sy), KEY_COLORS[i], 0.86, 56.0))
    # The LEDs sit at the switch centres, so any of them landing off the
    # board means a board was placed by hand instead of from its origin.
    # That is exactly how the NeoKey ended up 13 mm out in one layout.
    for sx, sy in P.SWITCH_XY:
        assert abs(sx - P.NEOKEY_CENTER[0]) <= P.NEOKEY_W / 2, \
            f"switch at x={sx:.2f} is off the NeoKey"
        assert abs(sy - P.NEOKEY_CENTER[1]) <= P.NEOKEY_D / 2, \
            f"switch at y={sy:.2f} is off the NeoKey"
    return items


def mesh_of(name, solid):
    TMP.mkdir(parents=True, exist_ok=True)
    path = TMP / f"pv-{name}.stl"
    export_stl(solid, str(path), tolerance=0.01, angular_tolerance=0.2)
    return trimesh.load(str(path))


def draw(ax, pieces, elev, azim, explode=0.0, title=""):
    """Painter's algorithm over every triangle in the scene at once.

    Sorting per part and drawing part by part is what makes these look
    wrong -- a keycap behind a wall gets painted over it. One sort across
    the whole scene is the entire trick, and it is also what lets the
    clear parts blend instead of just hiding what is behind them.
    """
    e, a = np.radians(elev), np.radians(azim)
    eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    light = np.array([0.3, -0.55, 0.78])

    tris, cols = [], []
    for name, mesh, color, alpha, lift in pieces:
        v = mesh.vertices + np.array([0.0, 0.0, lift * explode])
        t = v[mesh.faces]
        shade = 0.42 + 0.58 * np.clip(np.abs(mesh.face_normals @ light), 0, 1)
        rgb = np.array(matplotlib.colors.to_rgb(color))
        c = np.clip(shade[:, None] * rgb[None, :] + 0.10 * shade[:, None], 0, 1)
        tris.append(t)
        cols.append(np.concatenate([c, np.full((len(c), 1), alpha)], axis=1))

    tris = np.concatenate(tris)
    cols = np.concatenate(cols)
    order = np.argsort(tris.mean(axis=1) @ eye)

    ax.add_collection3d(
        Poly3DCollection(tris[order], facecolors=cols[order],
                         edgecolors="none", linewidths=0)
    )
    flat = tris.reshape(-1, 3)
    lo, hi = flat.min(0), flat.max(0)
    mid, span = (lo + hi) / 2, (hi - lo).max() / 2 * 0.56
    ax.set_xlim(mid[0] - span, mid[0] + span)
    ax.set_ylim(mid[1] - span, mid[1] + span)
    ax.set_zlim(mid[2] - span, mid[2] + span)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=11, color="#333", pad=0)


# Top to bottom, the order the exploded view stacks them in.
STACK = [
    ("4 × keycap", "1U, clear ABS", KEY_COLORS[2]),
    ("4 × Durock Ice King", "linear 52 gf, clear housing", SWITCH_COLOR),
    ("shell", "printed, plate face down", CASE_COLOR),
    ("NeoKey 1x4 QT", "ADA-4980, hot-swap + NeoPixel", BOARD_COLOR),
    ("QT Py RP2040", "ADA-4900, "
     + ("face down under the keys" if P.STACKED else "face up beside them"),
     BOARD_COLOR),
    ("bottom plate", "printed, "
     + ("carries the QT Py" if P.STACKED else "holds both boards up"),
     CASE_COLOR),
]

LEGEND = [
    ("idle", KEY_COLORS[0]),
    ("running", KEY_COLORS[1]),
    ("awaiting approval", KEY_COLORS[2]),
    ("done, unread", KEY_COLORS[3]),
]


def main():
    pieces = [(n, mesh_of(n, s), c, al, lf) for n, s, c, al, lf in scene()]
    top = max(m.bounds[1][2] for _, m, _, _, _ in pieces)

    fig = plt.figure(figsize=(17, 12), dpi=150, facecolor="white")
    gs = fig.add_gridspec(2, 3, height_ratios=[1.15, 1.0])

    draw(fig.add_subplot(gs[0, :], projection="3d"), pieces, 24, -58)
    draw(fig.add_subplot(gs[1, 0], projection="3d"), pieces, 5, -90, title="front")
    draw(fig.add_subplot(gs[1, 1], projection="3d"), pieces, 88, -90, title="top")
    draw(fig.add_subplot(gs[1, 2], projection="3d"), pieces, 18, -62,
         explode=1.0, title="exploded")

    fig.suptitle(f"Canopy MacroPad — {P.LAYOUT}", fontsize=20, y=0.975,
                 color="#1b1f26")
    fig.text(0.5, 0.945, f"{P.CASE_W:.1f} × {P.CASE_D:.1f} × {P.CASE_H:.1f} mm case"
             f"   ·   {top:.1f} mm to the top of a keycap",
             ha="center", fontsize=10.5, color="#5b626d")

    # The keys are wearing states, not decoration -- say which.
    for i, (label, color) in enumerate(LEGEND):
        x = 0.30 + i * 0.128
        fig.patches.append(plt.Rectangle(
            (x, 0.487), 0.016, 0.011, color=color, transform=fig.transFigure,
            ec="#aab", lw=0.6, zorder=5))
        fig.text(x + 0.022, 0.4885, label, fontsize=9, color="#444")

    # Into the dead space beside the hero shot. A 3D axis leaves a lot of
    # white either side of a part this long, and the parts list is exactly
    # the width of it.
    fig.text(0.045, 0.845, "components", fontsize=10.5, color="#1b1f26")
    for i, (name, note, color) in enumerate(STACK):
        y = 0.795 - i * 0.043
        fig.patches.append(plt.Rectangle(
            (0.045, y), 0.011, 0.017, color=color, transform=fig.transFigure,
            ec="#aab", lw=0.6, zorder=5))
        fig.text(0.064, y + 0.004, name, fontsize=9.5, color="#1b1f26")
        fig.text(0.064, y - 0.015, note, fontsize=8.0, color="#7a818c")

    png = OUT / "product.png"
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {png}")
    print(f"  keycap top sits {top:.2f} mm above the desk")


if __name__ == "__main__":
    main()
