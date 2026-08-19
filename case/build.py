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
        check("key field mid-x",
              (P.SWITCH_XY[0][0] + P.SWITCH_XY[-1][0]) / 2,
              P.BOARD_ORIGIN[0] + P.KEY_FIELD_W / 2),
    ]
    bh = built["bottom"].bounding_box().max.Z
    ok.append(bh <= P.Z_PLATE_BOTTOM + 1e-6)
    print(f"  [{'ok ' if bh <= P.Z_PLATE_BOTTOM else 'BAD'}] "
          f"{'bottom plate fits under the shell':<38} {bh:8.3f}  "
          f"(limit {P.Z_PLATE_BOTTOM:.3f})")

    recess = P.SEAM_STEP_W - P.END_HOOK_REACH
    good = 0.05 <= recess <= 0.30
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] "
          f"{'boss recessed behind the outer face':<38} {recess:8.3f}  "
          f"(0.050 to 0.300)")

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
        # What is left of the shell's wall outboard of the hook pocket:
        # the skin the boss would burst through if it reached too far.
        # And what holds the boss down: the shell material above it.
        "shell above the hook pocket": (
            P.CASE_H - P.END_HOOK_SEAM_Z
        ),
        # The hook band has to clear the plug's opening on one side and
        # the case's corner radius on the other.
        "hook band clear of the plug opening": (
            P.END_HOOK_Y0 - P.USB_PLUG_W / 2
        ),
        # Two chamfers meeting on a SEAM_STEP_W wall leave a knife edge,
        # which prints as a wobble and locates nothing.
        "flat left on the hook wall's top": (
            P.WALL - P.SEAM_STEP_W
            - P.END_HOOK_CHAMFER_IN - P.END_HOOK_CHAMFER_OUT
        ),
        # The boss must stay clear of the wall's top band, or the outer
        # chamfer cuts down and the boss returns beside it and the top
        # reads as a V notch instead of a ridge. That was the shape until
        # Saqoosha drew what it should be.
        "boss below the wall's outer chamfer": (
            P.END_HOOK_TOP_GAP - P.END_HOOK_CHAMFER_OUT
        ),
        # And the nose cannot eat the whole boss.
        "boss left above its nose": (P.END_HOOK_H - P.END_HOOK_NOSE),
        "boss left behind its nose": (P.END_HOOK_REACH - P.END_HOOK_NOSE),
        "hook band clear of the corner radius": (
            P.CASE_D / 2 - P.OUTER_CORNER_R - P.END_HOOK_Y0 - P.END_HOOK_L
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

    # The lead-ins, measured as volume rather than believed from the
    # source. Three separate constructions of these cut nothing at all
    # while every other check passed, so the arithmetic they are supposed
    # to match is asserted here rather than trusted.
    L = P.END_HOOK_L
    prism = lambda c: 2 * L * c ** 2 / 2   # noqa: E731
    real_w, real_b = parts._hook_wall, parts._hook_boss
    parts._hook_wall = lambda *a: real_w(*a[:-2], 0.001, 0.001)
    flat_wall = parts.bottom().volume
    parts._hook_wall = real_w
    parts._hook_boss = lambda *a: real_b(*a[:-1], 0.001)
    flat_boss = parts.bottom().volume
    parts._hook_boss = real_b
    for label, got, want in (
        ("wall lead-ins", flat_wall - built["bottom"].volume,
         prism(P.END_HOOK_CHAMFER_IN) + prism(P.END_HOOK_CHAMFER_OUT)),
        ("boss nose", flat_boss - built["bottom"].volume, prism(P.END_HOOK_NOSE)),
    ):
        good = abs(got - want) < 0.02
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {'lead-in':<7} {label:<22}"
              f" {got:9.3f} mm3  (want {want:.3f})")

    # The wall's top band has to be empty of boss, measured rather than
    # inferred from the gap above: an arithmetic margin says the numbers
    # allow a ridge, this says the solid has one.
    x_seam = P.CASE_W / 2 - P.SEAM_STEP_W
    intrude = 0.0
    for y0, y1 in parts._end_hook_bands():
        lo, hi = sorted((y0, y1))
        # Sized from the chamfer, not from END_HOOK_TOP_GAP. Taking the
        # band's height from the very number under test shrank the probe
        # with the fault: at TOP_GAP 0.05 the box was 0.05 tall and the
        # boss's top face landed exactly on its floor, so it reported
        # 0.000 while the notch was back. Same disease as a label margin
        # measured from the label.
        band = Pos(x_seam + P.END_HOOK_REACH / 2, (lo + hi) / 2,
                   P.END_HOOK_SEAM_Z - P.END_HOOK_CHAMFER_OUT / 2) * Box(
            P.END_HOOK_REACH, hi - lo, P.END_HOOK_CHAMFER_OUT)
        intrude += (band & built["bottom"]).volume
    good = intrude < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'hook':<7} boss inside the wall's "
          f"top band {intrude:9.3f} mm3")

    # The hook, measured as a shape. A feature can be absent from a
    # perfectly valid part -- a cut placed inside a void, a boss trimmed
    # off by a closing intersection -- and every other check still passes.
    # So ask each band separately for a boss on the plate and a void in
    # the shell, at the height the two are supposed to meet.
    x_probe = P.CASE_W / 2 - P.SEAM_STEP_W + P.END_HOOK_REACH / 2
    # Follows the boss down. A probe left at the old height reported
    # 0/2 pockets the moment the boss moved, which is the check working
    # -- but a probe that had happened to still land in material would
    # have gone on reporting 2/2 about geometry that had changed.
    z_probe = P.END_HOOK_SEAM_Z - P.END_HOOK_TOP_GAP - P.END_HOOK_H / 2
    bosses = voids = 0
    for y0, y1 in parts._end_hook_bands():
        cy = (y0 + y1) / 2
        pr = Pos(x_probe, cy, z_probe) * Box(
            P.END_HOOK_REACH * 0.5, P.END_HOOK_L * 0.5, P.END_HOOK_H * 0.5)
        if (pr & built["bottom"]).volume > 1e-6:
            bosses += 1
        if (pr & built["shell"]).volume < 1e-6:
            voids += 1
    want = len(parts._end_hook_bands())
    good = bosses == want and voids == want
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'hook':<7} boss on the plate "
          f"{bosses}/{want}, pocket in the shell {voids}/{want}")

    print("\n" + ("all checks passed" if all(ok) else "SOMETHING IS WRONG"))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
