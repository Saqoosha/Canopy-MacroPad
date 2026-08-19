"""The real PCB, as EasyEDA's own 3D preview draws it.

``mock.py`` builds the envelopes a boolean needs; this loads the board
EasyEDA exports, with every component's actual package shape on it. The
two answer different questions and both belong on screen: the envelope
says what was *checked*, this says what will arrive.

Written by ``pcb/export_3d.py``, which parks the export on ``globalThis``
and polls it because the bridge's request timeout is shorter than the
export takes. Re-run that after any board change -- nothing here can tell
a stale mesh from a current one.

Coordinates
-----------
EasyEDA writes the mesh board-local: the origin is the board's bottom-left
corner and ``z = 0`` is its **top** face, with every component hanging in
negative z because this board is assembled entirely on the bottom. So the
move into case space is a translation and nothing else::

    case = obj + (BOARD_ORIGIN.x, BOARD_ORIGIN.y, Z_BOARD_TOP)

The y direction was not assumed. Both hypotheses were counted against the
41 placed components' real positions, using only the 29 that sit more than
4 mm off the y centreline -- a y-symmetric part scores the same either way
and proves nothing. As-is drew 4939 nearby vertices, y-mirrored 1434.
``assert_orientation()`` re-runs that count on every load, so a mesh that
comes back flipped fails here instead of looking merely odd on screen.
"""

import zipfile
from pathlib import Path

import numpy as np

import params as P

OBJ_ZIP = Path(__file__).parent.parent / "pcb" / "out" / "3d" / "canopy_macropad_3d.obj"

# Board-local -> case. Aligning the board's *top* rather than its bottom is
# deliberate: PLATE_TOP_TO_PCB is measured from the top face, so that is the
# surface whose position the case actually depends on. The exported board is
# about 1.63 thick against BOARD_T's 1.60 -- copper and solder mask, which
# params does not model -- and that 0.03 shows up under the board, where
# UNDER_BOARD_AIR has room for it, rather than under the plate, where
# nothing does.
OFFSET = np.array([P.BOARD_ORIGIN[0], P.BOARD_ORIGIN[1], P.Z_BOARD_TOP])

# Anything thinner than this is copper, silkscreen or solder mask lying on
# a face. Drawn as its own part it z-fights the substrate it sits on, and
# it is also most of the triangle count for none of the shape.
FILM_Z = 0.05


def _read_zip():
    with zipfile.ZipFile(OBJ_ZIP) as archive:
        names = archive.namelist()
        obj = next(n for n in names if n.endswith(".obj"))
        mtl = next(n for n in names if n.endswith(".mtl"))
        return (archive.read(obj).decode("utf-8", "replace"),
                archive.read(mtl).decode("utf-8", "replace"))


def _colours(mtl_text):
    """newmtl name -> #rrggbb, off each material's diffuse term."""
    out = {}
    name = None
    for line in mtl_text.splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] == "newmtl":
            name = f[1]
        elif f[0] == "Kd" and name:
            r, g, b = (int(round(float(v) * 255)) for v in f[1:4])
            out[name] = f"#{r:02x}{g:02x}{b:02x}"
    return out


def load():
    """(name, triangles, colour) per material, already in case space."""
    obj_text, mtl_text = _read_zip()
    colours = _colours(mtl_text)

    verts = []
    faces = {}
    current = None
    for line in obj_text.splitlines():
        if line.startswith("v "):
            f = line.split()
            verts.append((float(f[1]), float(f[2]), float(f[3])))
        elif line.startswith("usemtl"):
            current = line.split()[1]
            faces.setdefault(current, [])
        elif line.startswith("f "):
            # "f v//vn v//vn v//vn"; OBJ indices are 1-based.
            faces[current].append([int(p.split("/")[0]) - 1
                                   for p in line.split()[1:4]])

    v = np.asarray(verts, dtype=np.float64)
    if not len(v):
        raise SystemExit(f"{OBJ_ZIP} carries no vertices")

    parts = []
    for name, idx in faces.items():
        if not idx:
            continue
        tris = v[np.asarray(idx)] + OFFSET
        parts.append((name, tris, colours.get(name, "#808080")))
    return parts


def solid_parts(parts):
    """Drop the films, keep the shapes.

    A part whose triangles span less than FILM_Z in z is copper, mask or
    silkscreen sitting on a face it cannot be separated from by a depth
    buffer. Keeping them costs most of the triangles and buys tearing.
    """
    keep = []
    for name, tris, colour in parts:
        z = tris[:, :, 2]
        if z.max() - z.min() >= FILM_Z:
            keep.append((name, tris, colour))
    return keep


def assert_orientation(parts):
    """Prove the mesh is the way round this module says it is.

    Not a formality: EasyEDA mirrors bottom-layer components in y, and a
    whole board arriving mirrored would still look like a plausible board.
    Counting real component positions against the mesh is the only thing
    here that can tell the difference.
    """
    import json
    import urllib.error

    comps = _component_positions()
    under = np.concatenate([t.reshape(-1, 3) for _, t, _ in parts])
    under = under[under[:, 2] < P.Z_BOARD_BOTTOM - 0.05]

    # Only parts genuinely off the centreline can distinguish the two.
    probes = [c for c in comps if abs(c[1] - P.BOARD_D / 2) > 4.0]
    if len(probes) < 5:
        raise AssertionError(
            f"only {len(probes)} off-centre components; too few to orient by")

    def score(flip):
        total = 0
        for lx, ly in probes:
            cx, cy = P.board_xy((lx, P.BOARD_D - ly if flip else ly))
            total += int(np.count_nonzero(
                (np.abs(under[:, 0] - cx) < 1.2) & (np.abs(under[:, 1] - cy) < 1.2)))
        return total

    as_is, flipped = score(False), score(True)
    if as_is <= flipped * 1.5:
        raise AssertionError(
            f"PCB mesh orientation is not what pcb3d assumes: as-is scored "
            f"{as_is}, y-mirrored {flipped}. Re-export, or fix OFFSET.")
    return as_is, flipped, len(probes)


def _component_positions():
    """Board-local (x, y) mm for every placed component, from the CPL.

    The CPL is what JLCPCB is building from, so it is the one description
    of this board that cannot drift from the physical result. Columns are
    found by their header text rather than by position: a blank cell is
    simply absent from the XML, so counting cells across a row silently
    reads the wrong column the moment one is empty.
    """
    import re
    cpl = (Path(__file__).parent.parent / "pcb" / "out" / "manufacturing"
           / "canopy_macropad-cpl.xlsx")
    with zipfile.ZipFile(cpl) as archive:
        shared = re.findall(
            r"<t[^>]*>(.*?)</t>",
            archive.read("xl/sharedStrings.xml").decode("utf-8", "replace"), re.S)
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")

    def cells(row):
        out = {}
        for m in re.finditer(
                r'<c r="([A-Z]+)\d+"(?:\s+t="(\w+)")?[^>]*>(?:<v>(.*?)</v>)?', row):
            col, kind, value = m.group(1), m.group(2), m.group(3)
            if kind == "s" and value and value.isdigit():
                value = shared[int(value)]
            out[col] = value or ""
        return out

    rows = re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S)
    if not rows:
        raise AssertionError(f"{cpl.name} has no rows")

    header = {v: k for k, v in cells(rows[0]).items()}
    for wanted in ("Mid X", "Mid Y"):
        if wanted not in header:
            raise AssertionError(
                f"{cpl.name} has no {wanted!r} column; headers were "
                f"{sorted(header)}")
    cx, cy = header["Mid X"], header["Mid Y"]

    out = []
    for row in rows[1:]:
        c = cells(row)
        try:
            x = float(c.get(cx, "").replace("mm", "").strip())
            y = float(c.get(cy, "").replace("mm", "").strip())
        except ValueError:
            continue
        out.append((x, y))
    if not out:
        raise AssertionError(f"{cpl.name} yielded no component positions")
    return out


if __name__ == "__main__":
    all_parts = load()
    solids = solid_parts(all_parts)
    tri_all = sum(len(t) for _, t, _ in all_parts)
    tri_solid = sum(len(t) for _, t, _ in solids)
    print(f"{len(all_parts)} materials, {tri_all:,} triangles")
    print(f"{len(solids)} kept as shapes, {tri_solid:,} triangles "
          f"({tri_all - tri_solid:,} dropped as films thinner than {FILM_Z})")

    v = np.concatenate([t.reshape(-1, 3) for _, t, _ in all_parts])
    print(f"case-space bounds: "
          f"x {v[:,0].min():8.3f} .. {v[:,0].max():8.3f}   "
          f"y {v[:,1].min():7.3f} .. {v[:,1].max():7.3f}   "
          f"z {v[:,2].min():6.3f} .. {v[:,2].max():6.3f}")
    print(f"case is           "
          f"x {-P.CASE_W/2:8.3f} .. {P.CASE_W/2:8.3f}   "
          f"y {-P.CASE_D/2:7.3f} .. {P.CASE_D/2:7.3f}   "
          f"z {0.0:6.3f} .. {P.CASE_H:6.3f}")

    a, f, n = assert_orientation(all_parts)
    print(f"orientation: as-is {a}, y-mirrored {f}, over {n} off-centre parts")
