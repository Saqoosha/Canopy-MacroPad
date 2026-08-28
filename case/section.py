"""Cut the assembled stack open and draw it.

    .venv/bin/python section.py

A shaded 3D view of a case is nearly useless -- the interesting geometry
is all inside, behind a wall. These are two slices through the assembly
with the board stand-ins dropped in, which is the only way to look at the
5.00 mm plate-to-PCB stack and the USB opening and believe them.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from build123d import export_stl  # noqa: E402

import mock  # noqa: E402
import params as P  # noqa: E402
import parts  # noqa: E402

OUT = Path(__file__).parent / "out" / P.OUT_NAME
TMP = OUT / "tmp"

STYLE = {
    "shell": ("#3d6ea8", 1.0),
    "bottom": ("#2f5583", 1.0),
    "board + sockets + USB": ("#1f7a4d", 0.75),
    "switch bodies": ("#b06a1f", 0.55),
}

# The third cut exists because the first two miss the slide latch
# entirely: one runs along the key row at y = 0 and the other across the
# middle of the case, and the latch lives at the tongue's rim. It goes
# through a nose standing over its shelf -- the x that cuts the capture,
# not the post. A feature nothing draws is a feature nobody checks.
_TAB_X = P.SLIDE_TAB_X[2] - P.SLIDE_TAB_L / 2 + P.SLIDE_CAPTURE / 2

CUTS = [
    ("through the key row  (looking back)", (0, P.SWITCH_XY[0][1], 0), (0, 1, 0), 0, 2),
    ("through the centreline  (looking right)", (0, 0, 0), (1, 0, 0), 1, 2),
    (f"through a latch nose at x = {_TAB_X:.2f}  (looking right)",
     (_TAB_X, 0, 0), (1, 0, 0), 1, 2),
]


def meshes():
    TMP.mkdir(parents=True, exist_ok=True)
    solids = {"shell": parts.shell(), "bottom": parts.bottom()}
    solids.update(mock.everything())
    out = {}
    for name, solid in solids.items():
        path = TMP / f"{name.replace(' ', '_').replace('+', '')}.stl"
        export_stl(solid, str(path), tolerance=0.01, angular_tolerance=0.2)
        out[name] = trimesh.load(str(path))
    return out


def main():
    loaded = meshes()
    fig, axes = plt.subplots(len(CUTS), 1, figsize=(15, 12), dpi=140)

    for ax, (title, origin, normal, ha, va) in zip(axes, CUTS):
        for name, mesh in loaded.items():
            color, alpha = STYLE[name]
            sec = mesh.section(plane_origin=origin, plane_normal=normal)
            if sec is None:
                continue
            for entity in sec.entities:
                pts = sec.vertices[entity.points]
                ax.fill(pts[:, ha], pts[:, va], color=color, alpha=alpha, lw=0)
                ax.plot(pts[:, ha], pts[:, va], color="#12203a", lw=0.5)
        ax.set_title(title, fontsize=10)
        ax.set_aspect("equal")
        ax.grid(True, lw=0.3, alpha=0.4)
        ax.set_yticks(np.arange(0, P.CASE_H + 2, 2))

    handles = [
        plt.Line2D([], [], color=c, lw=8, alpha=a, label=n)
        for n, (c, a) in STYLE.items()
    ]
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    png = OUT / "sections.png"
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    print(f"  {png}")


if __name__ == "__main__":
    main()
