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
        "coupon-hook": parts.hook_coupon(),
        "end-test": parts.end_test(),
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
        # The port's relief has to stay inside each half's own material,
        # or its outline runs off an edge instead of closing -- which is
        # what the printed part looked like, and neither the interference
        # check nor any margin had an opinion about it. Both floors are
        # measured from the relief because that is the shape that moves.
        # The throat is derived from the relief now, so what used to be
        # set by hand -- whether it clears the receptacle -- has to be
        # checked instead of assumed.
        "throat clears the receptacle across": (
            ((P.USB_PLUG_W + P.USB_PLUG_CLEAR - 2 * P.USB_LEDGE) - P.USB_W) / 2
        ),
        "throat clears the receptacle in height": (
            ((P.USB_PLUG_H + P.USB_PLUG_CLEAR - 2 * P.USB_LEDGE) - P.USB_H) / 2
        ),
        "relief floor above the shell's lowest face": (
            ((P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
             - (P.USB_PLUG_H + P.USB_PLUG_CLEAR) / 2)
            - (P.Z_FLOOR - P.SEAM_STEP_H) + 0.05
        ),
        "relief floor above the plate's outer lip": (
            ((P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
             - (P.USB_PLUG_H + P.USB_PLUG_CLEAR) / 2)
            - (P.BOTTOM_T - P.SEAM_STEP_H) + 0.05
        ),
        "hook band clear of the plug opening": (
            P.END_HOOK_Y0 - P.USB_PLUG_W / 2
        ),
        # Two chamfers meeting on a SEAM_STEP_W wall leave a knife edge,
        # which prints as a wobble and locates nothing.
        # The wall's top and the boss's top are one plane, chamfered at
        # each end -- inboard by the wall for the board, outboard by the
        # boss's nose for the shell. What has to be left is the flat
        # between them.
        "flat left across the hook's top": (
            P.WALL - P.SEAM_STEP_W + P.END_HOOK_REACH
            - P.END_HOOK_CHAMFER_IN - P.END_HOOK_NOSE
        ),
        # The nose cannot eat the whole boss.
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
    parts._hook_wall = lambda *a: real_w(*a[:-1], 0.001)
    flat_wall = parts.bottom().volume
    parts._hook_wall = real_w
    parts._hook_boss = lambda *a: real_b(*a[:-1], 0.001)
    flat_boss = parts.bottom().volume
    parts._hook_boss = real_b
    for label, got, want in (
        ("wall lead-in", flat_wall - built["bottom"].volume,
         prism(P.END_HOOK_CHAMFER_IN)),
        ("boss nose", flat_boss - built["bottom"].volume, prism(P.END_HOOK_NOSE)),
    ):
        good = abs(got - want) < 0.02
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {'lead-in':<7} {label:<22}"
              f" {got:9.3f} mm3  (want {want:.3f})")

    # The wall's top and the boss's top have to be the same plane. A
    # margin can say the two constants are equal; this says the solid
    # agrees, which is a different claim -- the notch this replaces was
    # arithmetically fine and geometrically a V.
    x_seam = P.CASE_W / 2 - P.SEAM_STEP_W
    step = 0.0
    for y0, y1 in parts._end_hook_bands():
        lo, hi = sorted((y0, y1))
        band = Pos(x_seam + P.END_HOOK_REACH / 2, (lo + hi) / 2,
                   P.END_HOOK_SEAM_Z + 0.15) * Box(
            P.END_HOOK_REACH, hi - lo, 0.30)
        step += (band & built["bottom"]).volume
    good = step < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'hook':<7} anything above the "
          f"hook's top plane {step:9.3f} mm3")

    # A sweep whose entries come out identical tests nothing, and looks
    # exactly like one that works. Only the shell reads END_HOOK_FIT, so
    # its four fragments must differ and the plate's four must not --
    # except by the ink in their labels, which is why the plate side is
    # asserted as a bound rather than as equality.
    hook_solids = built["coupon-hook"].solids()
    xs = sorted(so.center().X for so in hook_solids)
    split = (xs[0] + xs[-1]) / 2
    plate_v = sorted(so.volume for so in hook_solids if so.center().X < split)
    shell_v = sorted(so.volume for so in hook_solids if so.center().X >= split)
    want = len(P.END_HOOK_FIT_SWEEP)
    steps = [round(shell_v[i + 1] - shell_v[i], 4) for i in range(len(shell_v) - 1)]
    good = (len(plate_v) == want and len(shell_v) == want
            and min(steps) > 0.01 and (plate_v[-1] - plate_v[0]) < 1.0)
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'coupon':<7} hook fits differ "
          f"{len(shell_v)}/{want}, steps {steps}")

    # The end test has to be the case and nothing else. The coupon is
    # deliberately not -- its wall is widened so the piece survives being
    # pushed on -- and that is the one place the two disagree, so it is
    # the one thing worth asserting about this piece: its wall is the
    # case's END_HOOK_L, not the coupon's whole side.
    x_in = P.CASE_W / 2 - P.WALL
    x_seam = P.CASE_W / 2 - P.SEAM_STEP_W
    z_wall = (P.BOTTOM_T + P.END_HOOK_SEAM_Z) / 2
    plate_half = min(parts.end_test().solids(), key=lambda so: so.center().X)
    wall_len = 0.0
    for y in [i * 0.1 for i in range(-130, 131)]:
        pr = Pos((x_in + x_seam) / 2, y, z_wall) * Box(
            P.SEAM_STEP_W * 0.5, 0.08, 0.5)
        if (pr & plate_half).volume > 1e-9:
            wall_len += 0.1
    want = 2 * P.END_HOOK_L
    good = abs(wall_len - want) < 0.35
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'end':<7} test wall is the case's "
          f"{wall_len:5.2f} / {want:.2f} mm")

    # The port must have exactly one opening. Below the throat there was
    # a second, thin one: the relief cuts through the shell's 1.00 skirt
    # and the plate's receptacle pocket had removed the tongue behind it,
    # two unrelated cuts lining up. Neither an interference check nor any
    # margin can see that -- it is a hole, and a hole is what both of
    # them are blind to. So walk in from the outer face and require the
    # wall to stop you.
    zc = (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
    rh = P.USB_PLUG_H + P.USB_PLUG_CLEAR
    th = rh - 2 * P.USB_LEDGE
    band = [zc - rh / 2 + 0.10, zc - (rh / 2 + th / 2) / 2, zc - th / 2 - 0.10]
    leaks = 0
    for z in band:
        for y in (0.0, 2.0, 4.0, 5.0):
            through = True
            for i in range(22):
                x = P.CASE_W / 2 - i * 0.1
                pr = Pos(x, y, z) * Box(0.09, 0.09, 0.09)
                if ((pr & built["shell"]).volume > 1e-12
                        or (pr & built["bottom"]).volume > 1e-12):
                    through = False
                    break
            leaks += through
    good = leaks == 0
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'port':<7} second opening under the "
          f"throat {leaks:5d} leaks / {len(band) * 4} probed")

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
    z_probe = P.END_HOOK_SEAM_Z - P.END_HOOK_H / 2
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
