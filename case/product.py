"""Assembled and exploded views of the whole thing.

    .venv/bin/python product.py     ->  out/product.png

Presentation only. Nothing here is checked against anything and no
dimension in this file is load-bearing -- `mock.py` holds the envelopes
that matter and `build.py` is what decides whether the case is buildable.
The switch is koktoh's Choc V2 (`ref/choc-v2.step`, CC BY-NC-SA). The
keycap is wrk. MX Pure, read off the product photo -- Work Louder
publishes no CAD, and nothing here has been on a caliper. It exists so
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
    Box,
    Cylinder,
    Pos,
    RectangleRounded,
    export_stl,
    import_step,
)
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

import params as P  # noqa: E402
import parts  # noqa: E402

OUT = Path(__file__).parent / "out" / P.OUT_NAME
TMP = OUT / "tmp"

# From README.md "Status colors". Left to right: idle, running, awaiting
# approval, done-unread -- the three that matter plus a resting key.
KEY_COLORS = ["#273027", "#0040ff", "#ff8000", "#00ff00",
              "#00ffa0", "#ff0000"]

CASE_COLOR = "#858b95"
BOARD_COLOR = "#14171c"
SWITCH_COLOR = "#cdd7e4"

# wrk. MX Pure 1U, from https://worklouder.cc/wrk-mx-pure.
# Frosted PC, MX stem, 19.05 pitch. Outer size and corner against that
# pitch (the gaps in the photo are small). Height off the side wall
# against the 1U top -- about 0.3 of the width. 7.0 was too tall.
# A real cap skirts the housing rather than perching on it.
CAP_XY = 18.4
CAP_R = 4.2
CAP_H = 5.5
CAP_WALL = 1.20
CAP_TOP_T = 1.10
# Skirt above the plate through full travel. Seating the well on the
# stem put CAP_RIDE at 2.2, and a 3.2 press hit the shell 75.143 mm³.
CHOC_TRAVEL = 3.2  # Kailh CPG1353
CAP_BOTTOM_CLEAR = 0.4
CAP_RIDE = CHOC_TRAVEL + CAP_BOTTOM_CLEAR
STEM_BOSS_R = 3.9
STEM_PLUS_L = 4.2
STEM_PLUS_W = 1.35

CHOC_STEP = Path(__file__).parent / "ref" / "choc-v2.step"
_CHOC = None


def _choc_v2():
    """Housing + stem. Drops the coil spring (tiny volume, huge mesh)."""
    global _CHOC
    if _CHOC is None:
        if not CHOC_STEP.exists():
            raise SystemExit(f"missing {CHOC_STEP} -- run: sh ref/fetch.sh")
        imported = import_step(str(CHOC_STEP))
        keep = [s for s in imported.solids() if s.volume > 10]
        assert len(keep) == 3, \
            f"{CHOC_STEP} plastic parts: expected 3, got {len(keep)}"
        body = keep[0]
        for s in keep[1:]:
            body = body + s
        _CHOC = body
    return _CHOC


def switch_body(x, y):
    """Kailh Choc V2 from koktoh's STEP. z=0 in the file is the PCB top,
    and the 15 mm flange lands on Z_PLATE_TOP. Lifted a hair off the
    plate so coplanar faces do not fight for the same pixel --
    presentation only.
    """
    return Pos(x, y, P.Z_BOARD_TOP + 0.05) * _choc_v2()


def keycap(x, y):
    """wrk. MX Pure 1U. Shape only -- nothing depends on it.

    Rounded square, almost no taper, flat top, thin wall, MX plus in a
    circular well. A cup of plastic, so the mesh is closed and a section
    can fill the wall.
    """
    z0 = P.Z_PLATE_TOP + CAP_RIDE
    outer = Pos(x, y, z0) * extrude_rect(CAP_XY, CAP_XY, CAP_R, CAP_H)
    inner_xy = CAP_XY - 2 * CAP_WALL
    cavity = Pos(x, y, z0) * extrude_rect(
        inner_xy, inner_xy, max(CAP_R - CAP_WALL, 0.4), CAP_H - CAP_TOP_T)
    well_h = CAP_H - CAP_TOP_T
    boss = Pos(x, y, z0 + well_h / 2) * Cylinder(STEM_BOSS_R, well_h)
    plus_h = well_h + 0.4
    plus = Pos(x, y, z0 + plus_h / 2 - 0.2) * (
        Box(STEM_PLUS_L, STEM_PLUS_W, plus_h) +
        Box(STEM_PLUS_W, STEM_PLUS_L, plus_h))
    return (outer - cavity) + boss - plus


def extrude_rect(w, d, r, h):
    from build123d import extrude

    return extrude(RectangleRounded(w, d, r), amount=h)


def board(w, d, r, cx, cy, z0, t):
    return Pos(cx, cy, z0) * extrude_rect(w, d, r, t)


def scene():
    """Every piece, with the colour it should be drawn in."""
    sh = parts.shell()
    items = [
        ("bottom", parts.bottom(), CASE_COLOR, 1.0, 0.0),
        ("shell", sh, CASE_COLOR, 1.0, 38.0),
        (
            "board",
            board(P.BOARD_W, P.BOARD_D, P.BOARD_CORNER_R,
                  P.BOARD_CENTER[0], P.BOARD_CENTER[1],
                  P.Z_BOARD_BOTTOM, P.BOARD_T),
            BOARD_COLOR, 1.0, 20.0,
        ),
    ]
    for i, (sx, sy) in enumerate(P.SWITCH_XY):
        items.append((f"sw{i}", switch_body(sx, sy), SWITCH_COLOR, 1.0, 46.0))
        items.append((f"cap{i}", keycap(sx, sy), KEY_COLORS[i], 0.86, 56.0))
    cx, cy = P.BOARD_CENTER
    for sx, sy in P.SWITCH_XY:
        assert abs(sx - cx) <= P.BOARD_W / 2, \
            f"switch at x={sx:.2f} is off its board"
        assert abs(sy - cy) <= P.BOARD_D / 2, \
            f"switch at y={sy:.2f} is off its board"
    cap0 = next(s for n, s, *_ in items if n == "cap0")
    hit = (Pos(0, 0, -CHOC_TRAVEL) * cap0) & sh
    assert hit.volume < 1e-6, \
        f"keycap hits the shell at bottom-out: {hit.volume:.3f} mm3"
    return items


def mesh_of(name, solid):
    TMP.mkdir(parents=True, exist_ok=True)
    path = TMP / f"pv-{name}.stl"
    # The Choc STEP is a spring and fillets. 0.01 would be ~200 k
    # triangles a switch; 0.12 is the housing you can actually see.
    if name.startswith("sw"):
        export_stl(solid, str(path), tolerance=0.12, angular_tolerance=0.4)
    else:
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
    ("{} × keycap".format(len(P.SWITCH_XY)),
     "wrk. MX Pure, frosted PC", KEY_COLORS[2]),
    ("{} × Choc v2".format(len(P.SWITCH_XY)),
     "Kailh, MX stem", SWITCH_COLOR),
    ("shell", "printed, plate face down", CASE_COLOR),
    ("custom PCB", "six Choc hot-swap + reverse-mount pixels", BOARD_COLOR),
    ("bottom plate", "printed, pushes the board up", CASE_COLOR),
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

    fig.suptitle(f"Canopy MacroPad — {P.OUT_NAME}", fontsize=20, y=0.975,
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
