"""Build every part, export it, and print the numbers worth checking.

    .venv/bin/python build.py

Writes out/choc/*.stl and out/choc/*.step. The report at the end is not
decoration -- it is the only way to catch a parameter edit that quietly
moved a hole.
"""

import re
import sys
from pathlib import Path

from build123d import Box, Cylinder, Pos, Rotation, export_step, export_stl

import mock
import params as P
import parts

OUT = Path(__file__).parent / "out" / P.OUT_NAME


def export_step_stable(part, path):
    """Write STEP with the clock taken out of the header."""
    export_step(part, path)
    f = Path(path)
    f.write_text(re.sub(r"(FILE_NAME\('[^']*',')[^']*(')",
                        r"\g<1>1970-01-01T00:00:00\g<2>",
                        f.read_text(), count=1))


def _head_seat_probe():
    """The plate that has to be there above each counterbore."""
    z0 = P.SCREW_SINK + P.CLEAR_CHAMFER
    part = None
    for x, y in P.POST_XY:
        ring = (Pos(x, y, (z0 + P.BOTTOM_T) / 2)
                * Cylinder(radius=P.SCREW_HEAD_DIA / 2,
                           height=P.BOTTOM_T - z0))
        ring -= (Pos(x, y, (z0 + P.BOTTOM_T) / 2)
                 * Cylinder(radius=P.SCREW_CLEAR_DIA / 2,
                            height=P.BOTTOM_T - z0 + 0.2))
        part = ring if part is None else part + ring
    return part


def _rib_probes():
    """One small box per rib the coupon is supposed to have.

    The first version of this counted lumps in one wide slab, and a rib
    moved 60 mm off its pair still gave 4 of 4 -- it could see a rib that
    was *missing* and not one that was in the wrong place, which is most
    of what can actually go wrong. Asking each expected position for
    material separately catches both. A check nobody has watched fail
    proves nothing, and this one had to be watched twice.
    """
    L = rib_coupon_layout_cached()
    z = P.BOTTOM_T + P.SEAM_RIB_H - 0.20
    y = L["gap"] / 2 + P.SEAM_RIB_INSET
    return [
        Pos(x, y, z + 0.05) * Box(P.SEAM_RIB_L * 0.5, P.SEAM_RIB_W * 0.5, 0.10)
        for x in L["xs"]
    ]


def rib_coupon_layout_cached():
    return parts.rib_coupon_layout()


def check(label, got, want, tol=0.01):
    ok = abs(got - want) <= tol
    print(f"  [{'ok ' if ok else 'BAD'}] {label:<38} {got:8.3f}  (want {want:.3f})")
    return ok


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    built = {
        "shell": parts.shell(),
        "bottom": parts.bottom(),
        "coupon": parts.coupon(),
        "coupon-clear": parts.clear_coupon(),
        "coupon-rib": parts.rib_coupon(),
    }

    print("exported")
    for name, part in built.items():
        printable = part
        if name == "shell":
            printable = Rotation(180, 0, 0) * part
            printable = Pos(0, 0, -printable.bounding_box().min.Z) * printable
        export_stl(
            printable, str(OUT / f"{name}.stl"), tolerance=0.005, angular_tolerance=0.1
        )
        export_step_stable(part, str(OUT / f"{name}.step"))
        bb = part.bounding_box()
        print(
            f"  {name:<7} {bb.size.X:6.2f} x {bb.size.Y:6.2f} x {bb.size.Z:6.2f} mm"
            f"   {part.volume / 1000:6.2f} cm3"
        )

    print(f"\nassembled case  [{P.OUT_NAME}]")
    print(f"  outer            {P.CASE_W:.2f} x {P.CASE_D:.2f} x {P.CASE_H:.2f} mm")
    print(f"  plate top at z   {P.Z_PLATE_TOP:.2f}")
    print(f"  key field        {P.SWITCH_XY[0][0]:.3f} .. {P.SWITCH_XY[-1][0]:.3f}"
          f"  (pitch {P.SWITCH_XY[1][0] - P.SWITCH_XY[0][0]:.3f})")

    print("\nchecks")
    ok = [
        check("CASE_H", P.CASE_H, 9.50),
        check("plate top to PCB top face", P.Z_PLATE_TOP - P.Z_BOARD_TOP,
              P.PLATE_TOP_TO_PCB),
        check("switch pitch", P.SWITCH_XY[1][0] - P.SWITCH_XY[0][0], P.SWITCH_PITCH),
        check("switch row centred in the cavity",
              (P.SWITCH_XY[0][1] + P.SWITCH_XY[-1][1]) / 2, 0.0),
        check("plate thickness", P.Z_PLATE_TOP - P.Z_PLATE_BOTTOM, P.PLATE_T),
        check("shell height", built["shell"].bounding_box().size.Z,
              P.CASE_H - P.Z_FLOOR + P.SEAM_STEP_H),
        check("USB-C centred in the cavity depth", P.USB_CY, 0.0),
        # The rib sits hard against the skirt line by construction. Stated
        # as an equality because that is what it is -- as a margin it
        # would read its own threshold forever and never go red.
        check("rib's outboard edge on the skirt line",
              P.SEAM_RIB_INSET - P.SEAM_RIB_W / 2, P.SEAM_STEP_W),
        check("key field mid-x",
              (P.SWITCH_XY[0][0] + P.SWITCH_XY[-1][0]) / 2,
              P.BOARD_ORIGIN[0] + P.KEY_FIELD_W / 2),
    ]
    bh = built["bottom"].bounding_box().max.Z
    ok.append(bh <= P.Z_PLATE_BOTTOM + 1e-6)
    print(f"  [{'ok ' if bh <= P.Z_PLATE_BOTTOM else 'BAD'}] "
          f"{'bottom plate fits under the shell':<38} {bh:8.3f}  "
          f"(limit {P.Z_PLATE_BOTTOM:.3f})")

    ring = (P.SCREW_HEAD_DIA - P.SCREW_CLEAR_DIA) / 2 - P.CLEAR_CHAMFER
    good = 0.25 <= ring <= P.CLEAR_RING_MAX + 1e-6
    ok.append(good)
    print(f"\n  [{'ok ' if good else 'BAD'}] "
          f"{'ring over the counterbore':<38} {ring:8.3f}  "
          f"(0.250 to {P.CLEAR_RING_MAX:.3f})")

    margins = {
        # Receptacle sits in a 1.00 pocket cut into the plate top, so the
        # floor it cares about is that pocket's floor, not Z_FLOOR.
        "USB-C shell to pocket floor": P.Z_USB_BOTTOM - (P.BOTTOM_T - 1.00),
        "USB port bezel left in the wall": (
            P.WALL - (P.CASE_W / 2 - (P.USB_CX + P.USB_OVERHANG))
        ),
        "USB-C recessed behind the wall face": (
            P.CASE_W / 2 - (P.USB_CX + P.USB_OVERHANG)
        ),
        "plate web between switches": P.SWITCH_PITCH - P.SWITCH_HOLE,
        "shell wall above the deepest rib pocket": (
            parts.rib_coupon_layout()["wall_h"]
            - P.SEAM_RIB_H - P.SEAM_RIB_ROOF
        ),
        # The one that went red first, at -0.125: the pocket cut clean
        # through the wall into the cavity at the top of the old sweep.
        "wall inboard of the widest rib pocket": (
            P.WALL - P.SEAM_RIB_INSET
            - (P.SEAM_RIB_W + max(P.SEAM_RIB_FIT_SWEEP)) / 2
        ),
        "wall outboard of the widest rib pocket": (
            P.SEAM_RIB_INSET
            - (P.SEAM_RIB_W + max(P.SEAM_RIB_FIT_SWEEP)) / 2
        ),
        "screw post bite depth": (
            P.Z_PLATE_BOTTOM - P.Z_FLOOR - 1.0 - P.PILOT_MOUTH_H
        ),
        "post wall at the pilot mouth": (P.POST_DIA - P.PILOT_MOUTH_DIA) / 2,
        "plate left under the screw head": P.BOTTOM_T - P.SCREW_SINK,
        "counterbore ring under the head": (
            (P.SCREW_HEAD_DIA - P.SCREW_CLEAR_DIA) / 2
        ),
        "counterbore ring at the widest swept hole": (
            (P.SCREW_HEAD_DIA - max(P.CLEAR_SWEEP)) / 2
        ),
        "seat left on the coupon's worst row": (
            (P.SCREW_HEAD_DIA - max(P.CLEAR_SWEEP)) / 2
            - max(P.CLEAR_CHAMFER_SWEEP)
        ),
        "coupon label inside the pad": (
            parts.coupon_layout()["clear_label_edge"]
        ),
        "feet clear the screw heads": (
            (P.FOOT_H - P.FOOT_RECESS) - (P.SCREW_HEAD_H - P.SCREW_SINK)
        ),
        "screw post clears the board": (
            min(abs(px - (P.BOARD_ORIGIN[0] + P.BOARD_W))
                if px > 0 else abs(px - P.BOARD_ORIGIN[0])
                for px, _ in P.POST_XY)
            - P.POST_DIA / 2
        ),
        "board columns inside the cavity": min(
            P.CASE_D / 2 - P.WALL - abs(y) - P.COLUMN_DIA / 2
            for _, y in P.PRESS_XY
        ),
        "USB plug overmold above the desk": (
            (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2 - 3.25
        ),
    }
    print("\nmargins")
    for label, v in margins.items():
        flag = "ok " if v > 0.25 else "BAD"
        ok.append(v > 0.25)
        print(f"  [{flag}] {label:<38} {v:8.3f}")

    print("\ninterference")
    for pname in ("shell", "bottom"):
        for mname, solid in mock.everything().items():
            hit = (built[pname] & solid).volume
            good = hit < 1e-6
            ok.append(good)
            print(f"  [{'ok ' if good else 'BAD'}] {pname:<7} vs {mname:<22}"
                  f" {hit:9.3f} mm3")

    hit = (built["shell"] & built["bottom"]).volume
    good = hit < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'shell':<7} vs {'bottom plate':<22}"
          f" {hit:9.3f} mm3")

    missing = (_head_seat_probe() - built["bottom"]).volume
    good = missing < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'plate':<7} missing under the "
          f"head {missing:9.3f} mm3")

    # The ribs, measured where each one is supposed to be rather than
    # believed from the source that draws them.
    probes = _rib_probes()
    found = sum(1 for pr in probes if (pr & built["coupon-rib"]).volume > 1e-6)
    good = found == len(probes)
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'coupon':<7} ribs at their swept "
          f"positions {found:5d} / {len(probes)}")

    print("\n" + ("all checks passed" if all(ok) else "SOMETHING IS WRONG"))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
