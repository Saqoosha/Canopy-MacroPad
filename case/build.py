"""Build every part, export it, and print the numbers worth checking.

    .venv/bin/python build.py

Writes out/choc/*.stl and out/choc/*.step. The report at the end is not
decoration -- it is the only way to catch a parameter edit that quietly
moved a hole.
"""

import re
import sys
from pathlib import Path

from build123d import (Box, Cylinder, Pos, Rotation, export_step,
                       export_stl, import_step)

import mock
import params as P
import parts

OUT = Path(__file__).parent / "out" / P.OUT_NAME
CHOC_STEP = Path(__file__).parent / "ref" / "choc-v2.step"
_CHOC = None


def _choc():
    """The real switch out of the STEP, in case space, on a switch at
    the origin. Returns (stem, housing): the stem is everything that
    travels with the cap, the housing everything that stays put.

    Read rather than trusted. The cap's mount is the one feature of this
    case fitted to somebody else's plastic, so the constants in
    `params.py` are checked back against the file they came from -- a
    swapped or re-exported STEP goes red here instead of quietly
    redefining what the cap mounts on.
    """
    global _CHOC
    if _CHOC is None:
        if not CHOC_STEP.exists():
            raise SystemExit(f"missing {CHOC_STEP} -- run: sh ref/fetch.sh")
        solids = [s for s in import_step(str(CHOC_STEP)).solids()
                  if s.volume > 10]
        assert len(solids) == 3, \
            f"{CHOC_STEP} plastic parts: expected 3, got {len(solids)}"
        stem = max(solids, key=lambda so: so.bounding_box().max.Z)
        housing = None
        for so in solids:
            if so is not stem:
                housing = so if housing is None else housing + so
        lift = Pos(0, 0, P.Z_BOARD_TOP)
        _CHOC = (lift * stem, lift * housing)
    return _CHOC


def _shared(a, b):
    """Volume two solids share, 0.0 when they share nothing.

    `&` raises `Cannot intersect shape with empty compound` rather than
    returning an empty result, so every clearance check written as a
    bare `&` is one clean part away from dying instead of passing.
    """
    try:
        hit = a & b
    except ValueError:
        return 0.0
    return 0.0 if hit is None else hit.volume


def _probe(solid, cx, cy, cz, w, d, h):
    """Bounding box of what `solid` has inside a thin box, or None."""
    hit = solid & (Pos(cx, cy, cz) * Box(w, d, h))
    if hit is None or hit.volume < 1e-9:
        return None
    return hit.bounding_box()


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
        "coupon-hole": parts.hole_coupon(),
        "coupon-hook": parts.hook_coupon(),
        "end-test": parts.end_test(),
        "keycap": parts.dummy_cap(),
        "coupon-stem": parts.stem_coupon(),
    }

    print("exported")
    for name, part in built.items():
        printable = part
        if name in ("shell", "keycap"):
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
        # The 1.00 that used to be here was the rectangular pocket's depth,
        # and it outlived the pocket -- the clearance is cut with the
        # throat's profile now, so the floor is the throat's floor. A
        # check reading a constant nothing builds from any more reports
        # forever and cannot go red.
        "USB-C shell to the clearance floor": (
            P.Z_USB_BOTTOM
            - ((P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2
               - (P.USB_PLUG_H + P.USB_PLUG_CLEAR - 2 * P.USB_LEDGE) / 2)
        ),
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
        # The fillet can only grow inboard, and what it must not reach is
        # the receptacle's clearance cut, which is the nearest thing to
        # the band in y.
        # The probe below compares the wall against END_HOOK_WALL_T, so it
        # confirms the geometry follows the constant and says nothing
        # about the constant being big enough. This is the other half:
        # the wall has to be thicker than the seam that used to set it,
        # which is the whole point of the change.
        "hook wall thicker than the seam": (
            P.END_HOOK_WALL_T - P.SEAM_STEP_W
        ),
        "hook wall clear of the receptacle cut": (
            P.END_HOOK_Y0
            - (P.USB_PLUG_W + P.USB_PLUG_CLEAR - 2 * P.USB_LEDGE) / 2
        ),
        # The wall's top must stay under the board rather than reaching
        # its plane. It has 1.30 and the board never passes it -- the
        # chamfer on its inboard top edge was justified as a lead-in for
        # a board squeezing by, and that was wrong: the two do not share
        # a height at all. The chamfer stays as a printing lead-in; the
        # reason it was given does not.
        "hook wall below the board": (
            P.Z_BOARD_BOTTOM - P.END_HOOK_SEAM_Z
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
            P.END_HOOK_WALL_T + P.END_HOOK_RIB + P.END_HOOK_REACH
            - P.END_HOOK_CHAMFER_IN - P.END_HOOK_NOSE
        ),
        # The nose cannot eat the whole boss.
        "boss left above its nose": (P.END_HOOK_H - P.END_HOOK_NOSE),
        "boss left behind its nose": (P.END_HOOK_REACH - P.END_HOOK_NOSE),
        "hook band clear of the corner radius": (
            P.CASE_D / 2 - P.OUTER_CORNER_R - P.END_HOOK_Y0 - P.END_HOOK_L
        ),
        "hook rib still under the USB tab": (
            (P.CASE_W / 2 - P.SEAM_STEP_W - P.END_HOOK_WALL_T - P.END_HOOK_RIB)
            - (P.BOARD_ORIGIN[0] + P.BOARD_W - P.USB_TAB_W)
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
            P.CASE_D / 2 - P.WALL - abs(y) - dia / 2
            for y, dia in (
                *[(y, P.COLUMN_DIA) for _, y in P.PRESS_XY],
                *[(y, P.BACK_COLUMN_DIA) for _, y in P.BACK_PRESS_XY],
            )
        ),
        # BACK_PRESS_Y is derived to leave 0.26 here. Kept as a measurement
        # of the placed columns, not of that formula, so a hand-edit of
        # the y (or a second diameter) still has somewhere to go red.
        "back columns clear the socket": min(
            (y - P.BOARD_ORIGIN[1]) - P.BACK_COLUMN_DIA / 2
            - (P.SWITCH_Y + P.SOCKET_LOCAL[3])
            for _, y in P.BACK_PRESS_XY
        ),
        "USB plug overmold above the desk": (
            (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2 - 3.25
        ),
        # --- the dummy cap. CHOC_TRAVEL of the ride is spent pressing.
        "cap skirt above the plate, pressed": P.CAP_RIDE - P.CHOC_TRAVEL,
        "cap ceiling above the housing, pressed": (
            P.CAP_CEIL_RELIEF + (P.STEM_TOP - P.CHOC_TRAVEL - P.HOUSING_TOP)
        ),
        "cap boss inside the ring bore": (
            (P.STEM_RING_ID - P.CAP_BOSS_DIA) / 2
        ),
        "boss wall beside the bore": (
            (P.CAP_BOSS_DIA - (P.STEM_CROSS_L + P.STEM_LEN_CLEAR)) / 2
        ),
        "cap left above the bore": (
            P.CAP_CEIL_RELIEF + P.CAP_TOP_T - P.CAP_SOCKET_OVER
        ),
        "cap to its neighbour": (P.SWITCH_PITCH - P.CAP_XY) / 2,
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

    # The C-back cut opens the inner slab under the USB opening on
    # purpose -- that leftover was what the shell hit. The outer lip
    # below the seam still has to stop you. Watched failing at 12 leaks
    # with the C cut dropped to z 0 and run out to the outer face.
    band = [0.20, 0.60, 1.00]
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
    print(f"  [{'ok ' if good else 'BAD'}] {'port':<7} second opening through the "
          f"lip {leaks:5d} leaks / {len(band) * 4} probed")

    # The hole coupon asks two things at once and the plate's thickness
    # is the second: a Choc v2 clips into it, so a test plate at anything
    # but the real PLATE_T answers neither question. And the three holes
    # have to actually differ -- a sweep whose entries come out the same
    # tests nothing and looks exactly like one that works.
    hc = built["coupon-hole"]
    bb = hc.bounding_box()
    t = bb.size.Z
    n_want = len(P.HOLE_SWEEP)
    # Slice the plate and count what is missing -- but only the openings
    # big enough to be switch holes. Counting every void made it 19, the
    # engraved digits included, and "at least 3" is then true however
    # many holes there are.
    # The slab is *inside* the coupon's outline. Oversizing it by 1 mm
    # made the surrounding frame a void too, and counting that gave 4 of
    # 3 -- which is not a failure of the part.
    slab = Pos(0, 0, t / 2) * Box(bb.size.X - 1, bb.size.Y - 1, t * 0.5)
    voids = [v for v in (slab - hc).solids()
             if v.bounding_box().size.X > min(P.HOLE_SWEEP) - 0.5]
    good = abs(t - P.PLATE_T) < 1e-6 and len(voids) == n_want
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'coupon':<7} hole plate {t:.2f} / "
          f"{P.PLATE_T:.2f} mm, {len(voids)} switch openings / {n_want}")

    # The wall's thickness, measured on the solid. A margin can say the
    # constant is 3.00; this says the part is. The fillet it replaces was
    # 3.00 at the root and 1.00 at the top, so the height it is probed at
    # is deliberately the top half.
    x_seam = P.CASE_W / 2 - P.SEAM_STEP_W
    thin = 99.0
    for y0b, y1b in parts._end_hook_bands():
        cy = (y0b + y1b) / 2
        for z in (P.END_HOOK_SEAM_Z - 0.25, (P.BOTTOM_T + P.END_HOOK_SEAM_Z) / 2):
            # The range has to overshoot the wall. At 60 steps of 0.05
            # it stopped 0.05 short of a 3.00 wall's far face, never
            # found a void, and left the sentinel -- reporting 99.00
            # forever and passing at any thickness.
            for i in range(int((P.END_HOOK_WALL_T + P.END_HOOK_RIB + 2.0) / 0.05)):
                x = x_seam - i * 0.05
                pr = Pos(x, cy, z) * Box(0.04, 0.04, 0.04)
                if (pr & built["bottom"]).volume < 1e-12:
                    thin = min(thin, x_seam - x)
                    break
    want_thin = P.END_HOOK_WALL_T + P.END_HOOK_RIB
    good = thin >= want_thin - 0.10
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'hook':<7} wall thinnest section "
          f"{thin:8.2f} / {want_thin:.2f} mm")

    # The bed chamfers, measured as an inset rather than believed from
    # the source. Each half prints on a different face and a chamfer is
    # exactly the kind of feature that can be built and then trimmed off
    # by a later operation without anything raising.
    for name, part, zbed, inward in (("shell", built["shell"], P.CASE_H, -1),
                                     ("bottom", built["bottom"], 0.0, +1)):
        inset = None
        for i in range(40):
            x = P.CASE_W / 2 + 0.4 - i * 0.05
            pr = Pos(x, 0, zbed + inward * 0.02) * Box(0.04, 0.04, 0.04)
            if (pr & part).volume > 1e-12:
                inset = P.CASE_W / 2 - x
                break
        good = inset is not None and inset >= P.ELEPHANT_CHAMFER * 0.5
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {'bed':<7} {name} outline inset at "
              f"the bed face {inset if inset is not None else float('nan'):8.2f} mm")

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

    # The cut has to run the whole depth, not just the hook bands.
    # Material between the bosses is what the shell hits. Probe sits
    # in y between the USB throat and the hook. Watched failing at
    # 0.512 mm³ with the cut limited to _end_hook_bands().
    x_seam = P.CASE_W / 2 - P.SEAM_STEP_W
    x_back = x_seam - P.END_HOOK_BACK / 2
    z_back = (
        (P.BOTTOM_T - P.SEAM_STEP_H)
        + (P.END_HOOK_SEAM_Z - P.END_HOOK_H)
    ) / 2
    throat = (P.USB_PLUG_W + P.USB_PLUG_CLEAR - 2 * P.USB_LEDGE) / 2
    y_mid = (throat + P.END_HOOK_Y0) / 2
    leftover = 0.0
    for y in (y_mid, -y_mid):
        pr = Pos(x_back, y, z_back) * Box(
            P.END_HOOK_BACK * 0.5, 0.40, 0.80)
        leftover += (pr & built["bottom"]).volume
    good = leftover < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'hook':<7} back-cut through the depth "
          f"{leftover:9.3f} mm3")

    # The rib is a feature. Empty here means it never grew. Probe is
    # above the through-cut, inboard of WALL_T, pinned not sized from
    # RIB. Watched failing at 0.000 mm³ with END_HOOK_RIB at 0.
    x_rib = x_seam - P.END_HOOK_WALL_T - 0.80
    z_rib = (P.BOTTOM_T + P.END_HOOK_SEAM_Z) / 2
    got = 0.0
    for y0, y1 in parts._end_hook_bands():
        cy = (y0 + y1) / 2
        pr = Pos(x_rib, cy, z_rib) * Box(0.80, P.END_HOOK_L * 0.5, 0.80)
        got += (pr & built["bottom"]).volume
    good = got > 0.5
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'hook':<7} rib present "
          f"{got:9.3f} mm3")

    # Columns that run to the board hold the seam open: they push the
    # board into the switches, which hold the shell. Probe sits at the
    # board's underside, on a column. Watched failing at 0.731 mm³
    # with COLUMN_SLACK at 0.
    leftover = 0.0
    present = 0.0
    for (x, y), dia in (
        (P.PRESS_XY[0], P.COLUMN_DIA),
        (P.BACK_PRESS_XY[0], P.BACK_COLUMN_DIA),
    ):
        pr = Pos(x, y, P.Z_BOARD_BOTTOM) * Box(dia * 0.5, dia * 0.5, 0.20)
        leftover += (pr & built["bottom"]).volume
        pr = Pos(x, y, P.Z_COLUMN_TOP - 0.15) * Box(dia * 0.5, dia * 0.5, 0.20)
        present += (pr & built["bottom"]).volume
    good = leftover < 1e-6 and present > 0.5
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'column':<7} short of the board "
          f"{leftover:9.3f} mm3 leftover, {present:9.3f} mm3 still there")

    # --- the dummy caps -------------------------------------------------
    # Everything the cap mounts on belongs to somebody else's plastic, so
    # the constants in params.py are read back out of the STEP they came
    # from rather than trusted. A re-exported or swapped switch model
    # goes red here instead of quietly redefining the mount.
    stem, housing = _choc()
    z_ring = P.Z_BOARD_TOP + (P.STEM_TOP + P.STEM_RING_BOTTOM) / 2
    z_lid = P.Z_BOARD_TOP + P.HOUSING_TOP - 0.02
    arm = _probe(stem, 0, 0, z_ring, P.STEM_RING_ID - 0.2, 0.02, 0.02)
    # 2.0 deep, not 4.8: a strip that long crosses the ring wall either
    # side of the arm and the bounding box then spans all three.
    web = _probe(stem, P.STEM_CROSS_L * 0.4, 0, z_ring, 0.02, 2.0, 0.02)
    ring_in = _probe(stem, (P.STEM_CROSS_L / 2 + P.STEM_RING_OD / 2) / 2, 0,
                     z_ring, P.STEM_RING_OD / 2 - P.STEM_CROSS_L / 2, 0.02, 0.02)
    wall = _probe(stem, (P.STEM_RING_OD + P.STEM_RING_ID) / 4, 0,
                  P.Z_BOARD_TOP + P.STEM_TOP - 0.1, 0.02, 0.02, 20.0)
    mouth = _probe(housing, P.STEM_RING_OD / 2, 0, z_lid,
                   P.STEM_RING_OD, 0.02, 0.02)
    # The ribs. Probed one at a time: a strip long enough to hold two
    # features reports a bounding box spanning both, which read as a
    # 4.80 arm and a 3.60 rib on the way here.
    rib = _probe(stem, P.STEM_RIB_AT, 0, z_ring, 0.02, 2.0, 0.02)
    body = _probe(stem, P.STEM_RIB_AT + 0.15, 0, z_ring, 0.02, 2.0, 0.02)
    rib_z = _probe(stem, P.STEM_RIB_AT, P.STEM_RIB_W / 2 - 0.01,
                   P.Z_BOARD_TOP + 5.0, 0.06, 0.03, 20.0)

    print("\nswitch, read back off ref/choc-v2.step")
    ok += [
        check("stem top", stem.bounding_box().max.Z - P.Z_BOARD_TOP, P.STEM_TOP),
        check("cross arm, tip to tip", arm.size.X, P.STEM_CROSS_L),
        check("cross arm thickness", web.size.Y, P.STEM_CROSS_W),
        check("ring outer", 2 * abs(ring_in.max.X), P.STEM_RING_OD),
        check("ring inner", 2 * abs(ring_in.min.X), P.STEM_RING_ID),
        check("ring bottom", wall.min.Z - P.Z_BOARD_TOP, P.STEM_RING_BOTTOM),
        check("housing top", housing.bounding_box().max.Z - P.Z_BOARD_TOP,
              P.HOUSING_TOP),
        check("housing mouth", 2 * mouth.min.X, P.HOUSING_MOUTH_DIA),
        check("arm over a retention rib", rib.size.Y, P.STEM_RIB_W),
        check("arm between the ribs", body.size.Y, P.STEM_CROSS_W),
        check("rib bottom", rib_z.min.Z - P.Z_BOARD_TOP, P.STEM_RIB_Z[0]),
        check("rib top", rib_z.max.Z - P.Z_BOARD_TOP, P.STEM_RIB_Z[1]),
    ]

    print("\nkeycap")
    cap = built["keycap"]
    pressed = Pos(0, 0, -P.CHOC_TRAVEL) * cap
    # **The bore is supposed to interfere with the ribs** -- that is what
    # holds the cap on -- so one boolean against the whole stem cannot
    # say whether the model is right. Split it: the arm *body* is a wall
    # and must be clear, the ribs are the fit and the squeeze is a
    # number to read. Sized on the ribs' own measured extent, not on
    # CAP_BOSS_DIA or STEM_CLEAR, so it cannot move with the thing it
    # measures.
    ribs = None
    for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for side in (1, -1):
            cx, cy = P.STEM_RIB_AT * sx, P.STEM_RIB_AT * sy
            oy = side * (P.STEM_CROSS_W / 2 + 0.12)
            box = Pos(cx + oy * sy, cy + oy * sx,
                      P.Z_BOARD_TOP + (P.STEM_RIB_Z[0] + P.STEM_RIB_Z[1]) / 2) * Box(
                0.40 if sx else 0.24, 0.24 if sx else 0.40,
                P.STEM_RIB_Z[1] - P.STEM_RIB_Z[0] + 0.6)
            ribs = box if ribs is None else ribs + box
    # What keeps this envelope on the ribs is the read-back above, not
    # anything here. An assert that it "holds ribs" was written first and
    # was worthless: moved to STEM_RIB_AT 1.70 it still caught 0.174 mm3
    # -- the cross's flare down at the ring -- and passed, while the
    # squeeze quietly read 0.000. `arm over a retention rib` went red on
    # that same run, at 1.200 against 1.300.
    rib_solid = stem & ribs
    squeeze = _shared(cap, rib_solid)
    # A **reading, not a guard**, and printed as one: there is no value of
    # it the model can call wrong. Zero squeeze is a cap that falls off
    # and full squeeze is a cap that splits, and which is which is
    # settled by pressing a printed token onto a switch. What guards this
    # is the line under it -- past the ribs the bore is into the arm.
    print(f"  [ -- ] {'bore squeezing the retention ribs':<37} {squeeze:8.3f} mm3"
          f"  ({(P.STEM_RIB_W - (P.STEM_CROSS_W + P.STEM_CLEAR)) / 2:+.3f} per side)")
    for label, hit in (
        ("bore vs the cross body", _shared(cap, stem - ribs)),
        ("cap vs the housing, pressed", (pressed & housing).volume),
        ("cap vs the shell, pressed", (pressed & built["shell"]).volume),
        ("cap vs its neighbour",
         (cap & (Pos(P.SWITCH_PITCH, 0, 0) * cap)).volume),
    ):
        good = hit < 1e-6
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {label:<38} {hit:8.3f} mm3")

    # Interference cannot see an absent seat: a cap with no bearing pad
    # clears the ring by CAP_CEIL_RELIEF and reports 0.000 forever. So
    # subtract the cap from the rim it has to land on.
    #
    # The band is the ring's own inner edge outward, **not** the pad --
    # a probe sized from CAP_BEAR_DIA measures whatever that constant
    # happens to be and can never go red. Written the first way it also
    # could not: at CAP_BEAR_DIA 5.00 the annulus came out empty, OCCT
    # returned nothing, and the run died before the check printed.
    # Watched failing at 0.532 mm3 with CAP_BEAR_DIA at 5.00.
    z0 = P.Z_BOARD_TOP + P.STEM_TOP
    # +0.15 on the *radius*. Written +0.40 the band stood 3.15 out
    # against a pad reaching 3.00 and reported 0.580 mm3 missing on a
    # cap that was fine -- a check measuring its own arithmetic.
    band = (Pos(0, 0, z0 + 0.10)
            * Cylinder(radius=P.STEM_RING_ID / 2 + 0.15, height=0.20))
    band -= (Pos(0, 0, z0 + 0.10)
             * Cylinder(radius=P.STEM_RING_ID / 2, height=0.30))
    missing = (band - cap).volume
    good = missing < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'cap missing over the ring rim':<38}"
          f" {missing:8.3f} mm3")

    # The pad has to overhang the ring's inner edge to bear on it and
    # stay inside the housing's mouth so it can never land on the lip.
    # Both are under the 0.25 the margin table asks for -- the window
    # between STEM_RING_ID and HOUSING_MOUTH_DIA is 1.10 wide and no
    # diameter clears 0.25 at both ends -- so they are checked here with
    # the bound they can actually hold.
    for label, got in (
        ("pad over the ring's inner edge",
         (P.CAP_BEAR_DIA - P.STEM_RING_ID) / 2),
        ("pad inside the housing mouth",
         (P.HOUSING_MOUTH_DIA - P.CAP_BEAR_DIA) / 2),
    ):
        good = got >= 0.20
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {label:<38} {got:8.3f}  "
              f"(want 0.200)")

    # The bore is a cut inside a boss, and a cut that lands in air
    # removes nothing while every check above still passes. Measure the
    # shape: build the cap with the cut moved away and diff the volumes.
    real_cut = parts._socket_cut
    parts._socket_cut = lambda *a: Pos(0, 200, 0) * Box(0.1, 0.1, 0.1)
    solid_cap = parts.dummy_cap().volume
    parts._socket_cut = real_cut
    w = P.STEM_CROSS_W + P.STEM_CLEAR
    ln = P.STEM_CROSS_L + P.STEM_LEN_CLEAR
    mw, ml = w + P.STEM_MOUTH, ln + P.STEM_MOUTH
    want = ((2 * w * ln - w * w) * (P.CAP_ENGAGE + P.CAP_SOCKET_OVER)
            + ((2 * mw * ml - mw * mw) - (2 * w * ln - w * w)) * 0.40)
    got = solid_cap - cap.volume
    good = abs(got - want) < 0.05
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'bore removed from the boss':<38}"
          f" {got:8.3f} mm3  (want {want:.3f})")

    # A sweep whose entries come out identical tests nothing and looks
    # exactly like one that works.
    toks = sorted(built["coupon-stem"].solids(), key=lambda so: so.center().X)
    vols = [so.volume for so in toks]
    steps = [round(vols[i] - vols[i + 1], 4) for i in range(len(vols) - 1)]
    good = (len(toks) == len(P.STEM_CLEAR_SWEEP) and min(steps) > 0.01)
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'coupon slots differ':<38} "
          f"{len(toks)}/{len(P.STEM_CLEAR_SWEEP)}, steps {steps}")

    print("\n" + ("all checks passed" if all(ok) else "SOMETHING IS WRONG"))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
