"""A small z-buffer renderer, because sorting triangles is not depth.

`render.py` and `mount.py` both used to hand triangles to matplotlib's
`Poly3DCollection` after sorting them by the projection of their centroid.
That is the painter's algorithm, and it is wrong for exactly the shapes
this project draws: a mount is concave, its walls pass in front of and
behind each other within one part, and no ordering of whole triangles can
express that. Faces from inside a cavity surface through the wall in front
of them, and the picture reads as a different solid.

So: orthographic projection, one depth per pixel, painted 2x and boxed
down for the edges. Numpy only, no display, deterministic.
"""

import numpy as np


def _basis(elev, azim):
    e, a = np.radians(elev), np.radians(azim)
    eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    up = np.array([0.0, 0.0, 1.0])
    if abs(eye[2]) > 0.995:
        up = np.array([0.0, 1.0, 0.0])
    right = np.cross(up, eye)
    right /= np.linalg.norm(right)
    return right, np.cross(eye, right), eye


def render(meshes, elev, azim, size=(900, 620), bg=(1.0, 1.0, 1.0),
           light=(0.35, -0.5, 0.79), pad=0.07, ss=2, bounds=None):
    """meshes: [(tris (N,3,3), normals (N,3), rgb)] -> an (H, W, 3) float image."""
    W, H = size[0] * ss, size[1] * ss
    right, up, eye = _basis(elev, azim)
    light = np.asarray(light, float)
    light = light / np.linalg.norm(light)

    allv = np.concatenate([m[0].reshape(-1, 3) for m in meshes])
    box = np.stack([allv.min(0), allv.max(0)]) if bounds is None else np.asarray(bounds)
    corners = np.array([[x, y, z] for x in box[:, 0] for y in box[:, 1] for z in box[:, 2]])
    cu, cv = corners @ right, corners @ up
    span = max(cu.max() - cu.min(), cv.max() - cv.min()) * (1 + 2 * pad)
    scale = min(W, H) / span
    u0, v0 = (cu.min() + cu.max()) / 2, (cv.min() + cv.max()) / 2

    img = np.repeat(np.array(bg, float)[None, None, :], H, 0).repeat(W, 1)
    zbuf = np.full((H, W), -np.inf)

    for tris, norms, rgb in meshes:
        rgb = np.asarray(rgb, float)
        px = (tris @ right - u0) * scale + W / 2
        py = H / 2 - (tris @ up - v0) * scale
        pz = tris @ eye
        shade = 0.40 + 0.60 * np.clip(np.abs(norms @ light), 0, 1)
        for i in range(len(tris)):
            x, y, z = px[i], py[i], pz[i]
            x0, x1 = int(np.floor(x.min())), int(np.ceil(x.max())) + 1
            y0, y1 = int(np.floor(y.min())), int(np.ceil(y.max())) + 1
            x0, y0 = max(x0, 0), max(y0, 0)
            x1, y1 = min(x1, W), min(y1, H)
            if x1 <= x0 or y1 <= y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
            d = ((y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2]))
            if abs(d) < 1e-12:
                continue
            w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
            w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
            w2 = 1.0 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not inside.any():
                continue
            zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
            sub = zbuf[y0:y1, x0:x1]
            hit = inside & (zz > sub)
            if not hit.any():
                continue
            sub[hit] = zz[hit]
            img[y0:y1, x0:x1][hit] = rgb * shade[i]

    if ss > 1:
        img = img.reshape(H // ss, ss, W // ss, ss, 3).mean(axis=(1, 3))
    return np.clip(img, 0, 1)
