"""Dump the live schematic and board to a file, before touching either.

The project has already lost a schematic once: an agent was interrupted
mid-operation and the document came back with 30 of its 91 components and
5 of its 67 wires. It was recovered only because a script that rebuilds it
happened to exist in a commit -- which was luck dressed as architecture,
since the commit at HEAD could not rebuild it at all.

So before any operation that edits a live document, take one of these.
It is not a backup in the sense of something you can restore with a
click; it is a record complete enough to say exactly what changed, and
to rebuild by hand what did not survive. That is the difference between
"the schematic is broken" and "these eleven wires are missing".

    python3 snapshot.py            writes out/snapshot-<n>.json
    python3 snapshot.py --diff     compares the two most recent
"""

import glob
import json
import os
import sys

from bridge import execute

OUT = "out"


SCHEMATIC = """
    const out = {};
    const info = await eda.dmt_Project.getCurrentProjectInfo();
    out.project = {name: info && info.friendlyName, uuid: info && info.uuid};
    const pages = await eda.dmt_Schematic.getAllSchematicPagesInfo();
    out.pages = (pages||[]).map(p => ({uuid: p.uuid, name: p.name}));
    const sc = await eda.sch_PrimitiveComponent.getAll();
    out.schComponents = (sc||[]).map(c => ({
      id: c.primitiveId, des: c.designator, name: c.name,
      x: c.x, y: c.y, rot: c.rotation, mirror: c.mirror,
      device: c.device && {uuid: c.device.uuid, name: c.device.name},
      unique: c.uniqueId,
    }));
    const w = await eda.sch_PrimitiveWire.getAll();
    out.schWires = (w||[]).map(e => ({id: e.primitiveId, net: e.net,
                                      line: e.line}));
    return out;
"""

BOARD = """
    const out = {};
    const pc = await eda.pcb_PrimitiveComponent.getAll();
    out.pcbComponents = (pc||[]).map(c => ({
      id: c.primitiveId, des: c.designator, x: c.x, y: c.y,
      rot: c.rotation, layer: c.layer,
      fp: c.footprint && {uuid: c.footprint.uuid, name: c.footprint.name},
      unique: c.uniqueId,
    }));
    const pl = await eda.pcb_PrimitiveLine.getAll();
    out.pcbLines = (pl||[]).length;
    const pv = await eda.pcb_PrimitiveVia.getAll();
    out.pcbVias = (pv||[]).length;
    const pr = await eda.pcb_PrimitiveRegion.getAll();
    out.pcbRegions = (pr||[]).length;
    return out;
"""


def capture():
    """Read both documents, opening each first.

    `sch_PrimitiveComponent.getAll()` does not fail politely when a PCB is
    the active document -- it throws reading `page` off something
    undefined, which reads like a broken bridge rather than like the
    wrong document being open. Each half opens what it is about to read.
    """
    import build
    import schematic as sch

    sch.open_project_schematic()
    snap = execute(SCHEMATIC, timeout=120.0)
    build.open_project_pcb()
    snap.update(execute(BOARD, timeout=120.0))
    return snap


def census(snap):
    nets = {}
    for w in snap.get("schWires") or []:
        n = w.get("net") or "(none)"
        nets[n] = nets.get(n, 0) + 1
    return {
        "schComponents": len(snap.get("schComponents") or []),
        "schWires": len(snap.get("schWires") or []),
        "pcbComponents": len(snap.get("pcbComponents") or []),
        "pcbLines": snap.get("pcbLines"),
        "pcbVias": snap.get("pcbVias"),
        "pcbRegions": snap.get("pcbRegions"),
        "nets": nets,
    }


def _paths():
    return sorted(glob.glob(os.path.join(OUT, "snapshot-*.json")))


def write():
    os.makedirs(OUT, exist_ok=True)
    n = len(_paths()) + 1
    snap = capture()
    path = os.path.join(OUT, f"snapshot-{n:03d}.json")
    with open(path, "w") as f:
        json.dump(snap, f, indent=1)
    c = census(snap)
    print(f"wrote {path}")
    for k, v in c.items():
        if k == "nets":
            print(f"  {'nets':16} {len(v)} names, "
                  f"{sum(v.values())} wires")
        else:
            print(f"  {k:16} {v}")
    return path, snap


def diff():
    ps = _paths()
    if len(ps) < 2:
        raise SystemExit("need two snapshots to compare")
    a = census(json.load(open(ps[-2])))
    b = census(json.load(open(ps[-1])))
    print(f"{os.path.basename(ps[-2])} -> {os.path.basename(ps[-1])}")
    for k in a:
        if k == "nets":
            continue
        mark = "" if a[k] == b[k] else "   <-- CHANGED"
        print(f"  {k:16} {a[k]} -> {b[k]}{mark}")
    for n in sorted(set(a["nets"]) | set(b["nets"])):
        x, y = a["nets"].get(n, 0), b["nets"].get(n, 0)
        if x != y:
            print(f"  net {n:14} {x} -> {y}")


if __name__ == "__main__":
    if "--diff" in sys.argv:
        diff()
    else:
        write()
