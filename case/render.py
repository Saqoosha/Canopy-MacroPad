"""Render out/*.stl to PNGs so a change can be looked at, not just trusted.

    .venv/bin/python render.py

Headless on purpose -- matplotlib's Agg backend, no viewer, no Fusion. The
images are coarse, which is the right amount: they catch a hole in the
wrong wall or a rib growing the wrong way, and they are not meant to catch
a tenth of a millimetre. That is what build.py's checks are for.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

import params as P  # noqa: E402

OUT = Path(__file__).parent / "out" / P.LAYOUT
VIEWS = {"iso": (28, -60), "top": (89, -90), "bottom": (-70, -90), "back": (6, 90)}


def render(stl, view, elev, azim, ax):
    mesh = trimesh.load(stl)
    tris = mesh.vertices[mesh.faces]

    # Flip for the underside views so the part is seen from below rather
    # than through itself.
    if view == "bottom":
        tris = tris * np.array([1.0, 1.0, -1.0])

    normals = mesh.face_normals.copy()
    if view == "bottom":
        normals = normals * np.array([1.0, 1.0, -1.0])

    # Painter's algorithm by hand. Poly3DCollection sorts by its own idea
    # of depth and gets interior walls wrong often enough that a cavity
    # can look solid, which is exactly what these images exist to show.
    e, a = np.radians(elev), np.radians(azim)
    eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    order = np.argsort(tris.mean(axis=1) @ eye)
    tris, normals = tris[order], normals[order]

    light = np.array([0.35, -0.5, 0.79])
    shade = 0.35 + 0.65 * np.clip(np.abs(normals @ light), 0, 1)
    colors = np.stack([shade * 0.55, shade * 0.72, shade * 0.95, np.ones_like(shade)], 1)

    ax.add_collection3d(
        Poly3DCollection(tris, facecolors=colors, edgecolors="none", linewidths=0)
    )
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    mid, span = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(mid[0] - span, mid[0] + span)
    ax.set_ylim(mid[1] - span, mid[1] + span)
    ax.set_zlim(mid[2] - span, mid[2] + span)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(f"{Path(stl).stem} / {view}", fontsize=9)


def main():
    for stl in sorted(OUT.glob("*.stl")):
        fig = plt.figure(figsize=(14, 3.6), dpi=130)
        for i, (view, (elev, azim)) in enumerate(VIEWS.items(), 1):
            ax = fig.add_subplot(1, len(VIEWS), i, projection="3d")
            render(str(stl), view, elev, azim, ax)
        fig.tight_layout()
        png = OUT / f"{stl.stem}.png"
        fig.savefig(png, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"  {png}")


if __name__ == "__main__":
    main()
