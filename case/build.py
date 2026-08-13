"""Build every part, export it, and print the numbers worth checking.

    .venv/bin/python build.py

Writes out/*.stl (for the slicer) and out/*.step (for Fusion, if the thing
ever wants finishing by hand). The report at the end is not decoration --
it is the only way to catch a parameter edit that quietly moved a hole,
since nothing here is dimensioned on a drawing anyone reads.
"""

import re
import sys
from pathlib import Path

from build123d import Cylinder, Pos, Rotation, export_step, export_stl

import mock
import params as P
import parts

OUT = Path(__file__).parent / "out" / P.LAYOUT


def export_step_stable(part, path):
    """Write STEP with the clock taken out of the header.

    OCCT stamps the moment of export into FILE_NAME, so a model that did
    not change still produces a changed file on every build -- six of
    them here, which reads in a diff as though geometry moved. The
    geometry is the artefact; when it was written is not.
    """
    export_step(part, path)
    f = Path(path)
    f.write_text(re.sub(r"(FILE_NAME\('[^']*',')[^']*(')",
                        r"\g<1>1970-01-01T00:00:00\g<2>",
                        f.read_text(), count=1))


def _head_seat_probe():
    """The plate that has to be there above each counterbore.

    An interference check asks what two solids share, so it can only ever
    find material that should not exist. The channel's failure was the
    opposite -- material that should exist and did not, 0.20 of plate
    spanning the bore under the screw head's seat -- and no boolean run
    against a mock can see that, because the missing part is a void.

    So the polarity flips: build the volume the plate is required to fill
    and subtract the plate from it. Anything left over is plate that is
    not there. Starts above the lead-in cone, which is a void on purpose.
    """
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


def _rect_gap(xs, ys, cx, cy, r):
    """Plan-view clearance between an axis-aligned rect and a circle.

    Separated on any one axis is separated, so the largest of the four
    one-axis gaps is the answer; negative means the footprints overlap.
    Used for features a boolean cannot see -- a trench takes material
    away, so nothing standing over one ever reports interference.
    """
    return max(xs[0] - (cx + r), (cx - r) - xs[1],
               ys[0] - (cy + r), (cy - r) - ys[1])


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
        # The clearance row on its own. Three of the coupon's four fits
        # are settled, so re-asking the fourth should not cost a reprint
        # of the other three.
        "coupon-clear": parts.clear_coupon(),
        # The seam joint on its own. It is the one feature here that has
        # to spring, and springiness is not calculable at this wall
        # thickness -- so it gets asked the same way every other fit in
        # this case was, on a part that costs two minutes instead of
        # twenty.
        "coupon-seam": parts.seam_coupon(),
    }

    print("exported")
    for name, part in built.items():
        # STEP keeps assembly coordinates -- that is what makes it useful
        # to open alongside the boards. STL is what gets sliced, so it
        # comes out already lying the way it prints. The shell is the one
        # that differs: its plate face has to be on the bed, and "remember
        # to flip it" is a step that eventually gets skipped.
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

    print(f"\nassembled case  [{P.LAYOUT}]")
    print(f"  outer            {P.CASE_W:.2f} x {P.CASE_D:.2f} x {P.CASE_H:.2f} mm")
    print(f"  plate top at z   {P.Z_PLATE_TOP:.2f}")
    print(f"  key field        {P.SWITCH_XY[0][0]:.3f} .. {P.SWITCH_XY[-1][0]:.3f}"
          f"  (pitch {P.SWITCH_XY[1][0] - P.SWITCH_XY[0][0]:.3f})")

    print("\nchecks")
    ok = [
        check("plate top to PCB top face", P.Z_PLATE_TOP - P.Z_NEOKEY_TOP,
              P.PLATE_TOP_TO_PCB),
        check("switch pitch", P.SWITCH_XY[1][0] - P.SWITCH_XY[0][0], P.SWITCH_PITCH),
        check("switch row centred in the cavity",
              (P.SWITCH_XY[0][1] + P.SWITCH_XY[-1][1]) / 2,
              P.NEOKEY_ORIGIN[1] + P.NEOKEY_SW_Y),
        check("plate thickness", P.Z_PLATE_TOP - P.Z_PLATE_BOTTOM, P.PLATE_T),
        # From the top of the plate down to the bottom of the skirt, which
        # reaches below the seam so the two halves overlap rather than
        # butting. The skirt is why this is not simply CASE_H - Z_FLOOR.
        check("shell height", built["shell"].bounding_box().size.Z,
              P.CASE_H - P.Z_FLOOR + P.SEAM_STEP_H),
    ]
    if P.STACKED:
        ok += [
            check("key field centred on x=0",
                  (P.SWITCH_XY[0][0] + P.SWITCH_XY[-1][0]) / 2, 0.0),
            # USB-C used to be asserted centred across the case. The
            # six-key field moved the QT Py off centre to get it out of a
            # support column -- see QTPY_CX -- so the property worth
            # asserting is the one that displaced it, and it lives in the
            # margins below as "QT Py clear of the board columns".
            check("depth is set by the QT Py, not the NeoKey", P.CASE_D,
                  P.WALL + P.QTPY_D + P.QTPY_SLOP + P.QWIIC_PLUG_L + P.WALL),
        ]
    else:
        ok += [
            check("USB-C centred in the cavity depth", P.USB_CY, 0.0),
        ]
    # Everything the bottom plate carries has to fit under the shell's
    # plate, or the case does not close.
    bh = built["bottom"].bounding_box().max.Z
    ok.append(bh <= P.Z_PLATE_BOTTOM + 1e-6)
    print(f"  [{'ok ' if bh <= P.Z_PLATE_BOTTOM else 'BAD'}] "
          f"{'bottom plate fits under the shell':<38} {bh:8.3f}  "
          f"(limit {P.Z_PLATE_BOTTOM:.3f})")

    # The one clearance in the design with a ceiling as well as a floor.
    # The ring left over the counterbore is both the screw head's seat and
    # a piece of unsupported printing, so it has to stay wide enough to
    # bear on and narrow enough not to sag into the bore. The margins
    # below are all minimums and cannot express the second half.
    ring = (P.SCREW_HEAD_DIA - P.SCREW_CLEAR_DIA) / 2 - P.CLEAR_CHAMFER
    good = 0.25 <= ring <= P.CLEAR_RING_MAX + 1e-6
    ok.append(good)
    print(f"\n  [{'ok ' if good else 'BAD'}] "
          f"{'ring over the counterbore':<38} {ring:8.3f}  "
          f"(0.250 to {P.CLEAR_RING_MAX:.3f})")

    # Clearances that are not derived from anything, so nothing else fails
    # first if they go negative.
    margins = {
        "USB-C shell to floor": P.Z_USB_BOTTOM - P.Z_FLOOR,
        "buttons to floor": P.Z_BTN_LOW - P.Z_FLOOR,
        "Qwiic plug to floor": P.Z_STEMMA_LOW - P.Z_FLOOR,
        "QT Py sideways in the cavity": (
            (P.CASE_D - 2 * P.WALL - P.QTPY_PLAN_D) / 2
        ),
        "QT Py to the plate underside": P.Z_PLATE_BOTTOM - P.Z_QTPY_HIGH,
        # How far the receptacle sits behind the outer face of its wall.
        # Negative would mean the connector sticking out of the case; much
        # more than the wall thickness and a plug stops reaching it.
        # What is left of the wall in front of the plug flare. Purely the
        # ring you see around the port; it is a leftover, not a choice.
        "USB port bezel left in the wall": (
            P.WALL - ((P.CASE_D / 2 if P.STACKED else P.CASE_W / 2)
                      - ((P.USB_CY if P.STACKED else P.USB_CX) + P.USB_OVERHANG))
        ),
        "USB-C recessed behind the wall face": (
            (P.CASE_D / 2 if P.STACKED else P.CASE_W / 2)
            - ((P.USB_CY if P.STACKED else P.USB_CX) + P.USB_OVERHANG)
        ),
        "plate web between switches": P.SWITCH_PITCH - P.SWITCH_HOLE,
        # Thread only. The 1.0 is the blind end the hole stops short of,
        # and the mouth is a funnel that does not hold anything, so both
        # come off or this reports engagement the screw never gets.
        "screw post bite depth": (
            P.Z_PLATE_BOTTOM - P.Z_FLOOR - 1.0 - P.PILOT_MOUTH_H
        ),
        # At the mouth, which is where the post is thinnest -- measuring
        # the wall around the pilot instead would report 1.48 for a ring
        # that is really 1.10.
        "post wall at the pilot mouth": (P.POST_DIA - P.PILOT_MOUTH_DIA) / 2,
        "plate left under the screw head": P.BOTTOM_T - P.SCREW_SINK,
        # The counterbore floor the head actually sits on is a ring, and
        # widening the clearance hole eats it from the inside. Nothing
        # else notices if it goes to nothing -- the plate keeps its
        # thickness and the head keeps its diameter, and the screw just
        # pulls through.
        "counterbore ring under the head": (
            (P.SCREW_HEAD_DIA - P.SCREW_CLEAR_DIA) / 2
        ),
        # The coupon drills wider than the case does, and a swept hole
        # that eats its own counterbore tests nothing -- the screw falls
        # straight through and the entry reads as "free" for the wrong
        # reason.
        "counterbore ring at the widest swept hole": (
            (P.SCREW_HEAD_DIA - max(P.CLEAR_SWEEP)) / 2
        ),
        # The plate's own ring is checked above instead, where it can be
        # held to a maximum as well. This is the coupon's worst row, and
        # it gets the minimum only on purpose: the coupon exists to print
        # rings outside the limit -- its C0.00 row is at 1.200 and that
        # row is the control.
        "seat left on the coupon's worst row": (
            (P.SCREW_HEAD_DIA - max(P.CLEAR_SWEEP)) / 2
            - max(P.CLEAR_CHAMFER_SWEEP)
        ),
        # A swept hole nobody can name is not a test, and the counterbore
        # is the widest thing on the pad -- it reached the top of the
        # digits once already, which reads as a clean part right up until
        # the label comes out with its head cut off. The gap to the
        # counterbore is not checked here on purpose: the label is now
        # positioned from that edge, so a check on it would report the
        # constant it was built from and could never fail. What is left
        # over, and can, is whether the label still lands on the pad.
        "coupon label inside the pad": (
            parts.coupon_layout()["clear_label_edge"]
        ),
        # A proud button head on the underside is only fine while the feet
        # are taller than it is.
        "feet clear the screw heads": (
            (P.FOOT_H - P.FOOT_RECESS) - (P.SCREW_HEAD_H - P.SCREW_SINK)
        ),
        # Against the plug, not the board. Measuring to the board edge is
        # what let an M3 post land on the Qwiic connector with this check
        # still reading green.
        # Measured from the plug's own outer face, and to the *nearest*
        # post rather than to a post picked by index. The field stopped
        # being centred in the case when the breakouts went on one end,
        # so a half-width from the middle no longer points at the board
        # edge the plug is on.
        "screw post clears the mated plug": (
            min(abs(px - (P.NEOKEY_CENTER[0] + P.NEOKEY_W / 2
                          + P.QWIIC_PLUG_L))
                for px, _ in P.POST_XY)
            - P.POST_DIA / 2
        ),
        # Per column, because they are not all one diameter any more: the
        # field pads are FIELD_SUPPORT_DIA because they have to clear the
        # board's own components in y, where a seam column escapes in x.
        # Measuring both against COLUMN_DIA reported a pad 0.06 outside
        # the cavity that is really 0.44 inside it -- a check describing a
        # column that no longer exists.
        "board columns inside the cavity": min(
            [P.CASE_D / 2 - P.WALL - abs(y) - P.COLUMN_DIA / 2
             for _, y in P.MOUNT_XY]
            + [P.CASE_D / 2 - P.WALL - abs(y) - P.FIELD_SUPPORT_DIA / 2
               for _, y in P.BREAKOUT_SUPPORT_XY + P.SEAM_XY]
        ),
        # Nothing booleans a trench: what it removes is material, so a
        # feature standing over one still reports zero interference and a
        # membrane left under one is a valid solid. These are the only
        # guard the wire channel has, and they are floors on the plan
        # view -- the channel's rectangle against every circle that
        # matters, separated on any one axis being enough.
        #
        # Against the screw features first, because that is the pair that
        # was wrong: the channel ran over both counterbores and left
        # 0.20 of plate spanning them, one layer over the bore. Measured
        # to the larger of the counterbore and the shell's post, since
        # the post's foot has to land on plate that is still there.
        "wire channel clear of the screws": min(
            _rect_gap(P.WIRE_CHANNEL_X, P.WIRE_LANE_Y, x, y,
                      max(P.SCREW_HEAD_DIA, P.POST_DIA) / 2)
            for x, y in P.POST_XY
        ),
        # ...and against the columns that stand up out of the plate, per
        # column because they are not one diameter.
        "wire channel clear of the columns": min(
            [_rect_gap(P.WIRE_CHANNEL_X, P.WIRE_LANE_Y, x, y,
                       P.COLUMN_DIA / 2) for x, y in P.MOUNT_XY]
            + [_rect_gap(P.WIRE_CHANNEL_X, P.WIRE_LANE_Y, x, y,
                         P.FIELD_SUPPORT_DIA / 2)
               for x, y in P.BREAKOUT_SUPPORT_XY + P.SEAM_XY]
        ),
        # A USB-C plug's overmold is roughly 6.5 tall. Sitting this low in
        # the case, the question stops being whether it fits the opening
        # and becomes whether it fouls the desk.
        "USB plug overmold above the desk": (
            (P.Z_USB_BOTTOM + P.Z_USB_TOP) / 2 - 3.25
        ),
    }
    if P.STACKED:
        # Only meaningful with one board over the other.
        margins["QT Py to the NeoKey's sockets"] = (
            P.Z_NEOKEY_BOTTOM - P.NEOKEY_SOCKET_DROP - P.Z_QTPY_HIGH
        )
        # Sideways, against the columns that hold the boards above it.
        # This is the arithmetic guard for the collision that moved the
        # QT Py off centre; the interference boolean below is still the
        # evidence.
        margins["QT Py clear of the board columns"] = (
            min(abs(P.QTPY_CX - cx)
                for cx, _ in P.MOUNT_XY + P.BREAKOUT_SUPPORT_XY)
            - P.QTPY_PLAN_W / 2 - P.COLUMN_DIA / 2
        )
    print("\nmargins")
    for label, v in margins.items():
        flag = "ok " if v > 0.25 else "BAD"
        ok.append(v > 0.25)
        print(f"  [{flag}] {label:<38} {v:8.3f}")

    # The check a render cannot do. Boolean the printed parts against
    # stand-ins for every board and switch and see whether anything is
    # left over. A non-zero volume here is a case that will not close.
    print("\ninterference")
    for pname in ("shell", "bottom"):
        for mname, solid in mock.everything().items():
            hit = (built[pname] & solid).volume
            good = hit < 1e-6
            ok.append(good)
            print(f"  [{'ok ' if good else 'BAD'}] {pname:<7} vs {mname:<18}"
                  f" {hit:9.3f} mm3")

    # And the two printed parts against each other. Neither is a mock, so
    # nothing above covers this pair -- and they are the pair most likely
    # to fight, since the shell's screw posts and the bottom plate's
    # columns and pocket walls all reach into the same cavity from
    # opposite ends.
    hit = (built["shell"] & built["bottom"]).volume
    good = hit < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'shell':<7} vs {'bottom plate':<18}"
          f" {hit:9.3f} mm3")

    # And the one that runs the other way: material required, not
    # material shared. Nothing above could have found the wire channel
    # eating the screw head's seat, because what it left was a void.
    missing = (_head_seat_probe() - built["bottom"]).volume
    good = missing < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'plate':<7} missing under the "
          f"head {missing:9.3f} mm3")

    print("\n" + ("all checks passed" if all(ok) else "SOMETHING IS WRONG"))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
