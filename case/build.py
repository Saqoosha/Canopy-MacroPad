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
        "coupon-slide": parts.slide_coupon(),
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
        # Three equal cap margins is what END_BAY buys now; measure it
        # on the placed switches rather than trusting the derivation.
        check("cap margin, left equals front",
              (P.SWITCH_XY[0][0] - P.CAP_XY / 2) - (-P.CASE_W / 2),
              P.CASE_D / 2 - P.CAP_XY / 2),
        # The case corner is concentric with the corner cap's corner
        # and 3.795 larger -- OUTER_CORNER_R is written as a number
        # because CAP_XY/CAP_R are defined below it in params.py, and
        # this pair of checks is what stops the two drifting apart.
        check("case corner radius is margin + cap R", P.OUTER_CORNER_R,
              P.CASE_D / 2 - P.CAP_XY / 2 + P.CAP_R),
        check("corner centres concentric, x",
              -P.CASE_W / 2 + P.OUTER_CORNER_R,
              P.SWITCH_XY[0][0] - P.CAP_XY / 2 + P.CAP_R),
    ]
    bh = built["bottom"].bounding_box().max.Z
    ok.append(bh <= P.Z_PLATE_BOTTOM + 1e-6)
    print(f"  [{'ok ' if bh <= P.Z_PLATE_BOTTOM else 'BAD'}] "
          f"{'bottom plate fits under the shell':<38} {bh:8.3f}  "
          f"(limit {P.Z_PLATE_BOTTOM:.3f})")

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
        # --- the slide latch. Arithmetic guards are worth having and are
        # not evidence; the booleans further down watch the geometry.
        # What carries the plate's sag: ledge under the eave, and the
        # ledge still printable at the sweep's deepest fit.
        "ledge under the eave": (
            P.SLIDE_TAB_H - P.SLIDE_NOSE_H + 0.10 - P.SLIDE_FIT
        ),
        "ledge at the sweep's deepest fit": (
            P.SLIDE_TAB_H - P.SLIDE_NOSE_H + 0.10 - max(P.SLIDE_FIT_SWEEP)
        ),
        # Both bearing faces are parallel 45-degree wedges now (the
        # fifth print jammed on two opposed drooping flats), so the
        # bearing is the slope pair itself and SLIDE_FIT is their
        # vertical offset by construction -- the capture probe below
        # is what verifies the solid agrees.
        # The tab's only x neighbour is the pocket's own end -- the
        # ledge runs along x, so the x-clearance class the +x nose kept
        # losing to hole shrink has no members left. The 0.30 here is a
        # deliberate over-travel: on the printed screwless case it
        # measures ~0.1 and Saqoosha accepted it ("i can slide 0.1mm
        # deeper but ok"); the detent will pin home exactly if it ever
        # stops being ok.
        "tab clear of the pocket's end": 0.30,
        "entry clear of the corner radius": (
            (P.CASE_W / 2 - P.OUTER_CORNER_R)
            - (max(P.SLIDE_TAB_X) + P.SLIDE_TAB_L / 2
               + P.SLIDE_ENTRY_MAX + 0.10)
        ),
        # The left pair moved toward the corner when the screws' bay
        # went and the case shrank 7.00 around it.
        "pocket clear of the left corner radius": (
            (min(P.SLIDE_TAB_X) - P.SLIDE_TAB_L / 2 - 0.30)
            - (-P.CASE_W / 2 + P.OUTER_CORNER_R)
        ),
        "post clear of the left trim": (
            (min(P.SLIDE_TAB_X) - P.SLIDE_TAB_L / 2) - P.SLIDE_TRIM_X
        ),
        "post top under the board": (
            P.Z_BOARD_BOTTOM - (P.BOTTOM_T + P.SLIDE_TAB_H)
        ),
        "wall skin outboard of the pocket": P.WALL - P.SLIDE_POCKET_OUT,
        "wall above the entry roof": (
            P.Z_PLATE_BOTTOM
            - (P.Z_FLOOR + P.SLIDE_TAB_H + P.SLIDE_ENTRY_HEAD)
        ),
        "drop window the entry accepts": (
            P.SLIDE_ENTRY_MAX - P.SLIDE_ENTRY_MIN
        ),

        # The two clearances the right end owns now that the hook is
        # gone: the rightmost pocket to the tongue's right trim, and the
        # trimmed tongue to the right skirt at home -- the face the
        # hook's wall used to stop 0.10 from.

        "tongue clear of the right skirt at home": (
            (P.CASE_W / 2 - P.SEAM_STEP_W + P.SEAM_FIT / 2)
            - P.SLIDE_RIGHT_TRIM_X
        ),
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

        "boss wall beside the bore": (
            (P.CAP_BOSS_DIA - (P.STEM_CROSS_L + P.STEM_LEN_CLEAR)) / 2
        ),
        # The tube's thin spot is where a cross meets a circle: the
        # arm's corners, ~15.6 degrees off-axis. Two prints found this
        # the hard way (0.30 tips sliced away; 0.45 tips floated on
        # 0.37 corners); anything under ~0.44 here is a slicing
        # casualty.
        "tube wall at the arm corners": (
            P.CAP_BOSS_DIA / 2 - (
                ((P.STEM_CROSS_L + P.STEM_LEN_CLEAR) / 2) ** 2
                + ((P.STEM_CROSS_W + P.STEM_CLEAR) / 2) ** 2) ** 0.5
        ),
        # The flats live where the wall is fat: the nearest bore
        # feature to a 45-degree flat is the cross's concave corner.
        "flat clear of the bore's corner": (
            P.CAP_BOSS_FLATS / 2
            - ((P.STEM_CROSS_L + P.STEM_LEN_CLEAR) / 2
               + (P.STEM_CROSS_W + P.STEM_CLEAR) / 2) / 2 ** 0.5
        ),
        "mouth wall at the arm corners": (
            P.CAP_BOSS_DIA / 2 - (
                ((P.STEM_CROSS_L + P.STEM_LEN_CLEAR) / 2) ** 2
                + ((P.STEM_CROSS_W + P.STEM_CLEAR + P.STEM_MOUTH) / 2) ** 2
            ) ** 0.5
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

    # The four corners, probed for the hole class the concentric radius
    # introduced: a near-square cavity corner against the 7.995 outer
    # face left a 0.07 slit through the wall on each diagonal, and an
    # interference boolean cannot see a hole. Rays march the diagonal
    # at wall height; any that get through are a leak, and the first
    # blocked step is the wall's thickness, printed as a reading.
    # Watched failing at 4 leaks / 4 with the cavity corner back at
    # 1.00 -- the original fault, reproduced on purpose.
    import math as _m
    leaks2 = 0
    thin_w = 99.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx0 = sx * (P.CASE_W / 2)
            cy0 = sy * (P.CASE_D / 2)
            got = 0.0
            through = True
            # The march has to overshoot both faces: the outer face
            # sits R*(sqrt(2)-1) ~ 3.3 inboard of the square corner on
            # the diagonal, and the first cut of this probe walked only
            # 2.0 -- 40 steps of air, "4 leaks" about a wall it never
            # reached.
            for i in range(130):
                t = i * 0.05
                x = cx0 - sx * t / _m.sqrt(2)
                y = cy0 - sy * t / _m.sqrt(2)
                pr = Pos(x, y, 5.0) * Box(0.06, 0.06, 0.6)
                if (pr & built["shell"]).volume > 1e-12:
                    if through:
                        start = t
                        through = False
                elif not through:
                    got = t - start
                    break
            leaks2 += through
            if not through:
                thin_w = min(thin_w, got)
    good = leaks2 == 0 and thin_w >= 0.45
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'corner':<7} wall through the "
          f"diagonal {thin_w:5.2f} mm, {leaks2} leaks / 4")

    # The outer lip below the USB opening has to stop you: nothing may
    # read as a second slit through the bottom of the port. Written for
    # the end hook's C-back cut and kept past its retirement -- the lip
    # is still the only material there. Watched failing at 12 leaks with
    # that cut dropped to z 0 and run out to the outer face.
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

    # --- the slide latch ------------------------------------------------
    # The latch, measured as a shape. A feature can be absent from a
    # perfectly valid part, so ask each position separately for a post
    # on the plate, a channel void in the shell over the post's path,
    # and a ledge left in the shell. Watched failing at post 8/10 with
    # one pair moved +6.0 and at ledge 0/10 with the outboard cut run
    # down to the underside.
    y_in = P.CASE_D / 2 - P.WALL
    # The post probe's band sits in the post's *outboard* half, because
    # the back-press columns reach y 10.66 and two tab positions stand
    # close enough in x that a wider band catches a column's edge --
    # 0.072 mm3 of it, measured -- and a probe that finds someone
    # else's material cannot fail. Watched: with a pair moved +6.0 the
    # wide band still said 10/10; this band says 8/10.
    y_post = y_in - 0.05
    y_chan = y_in + (P.SLIDE_POST_UNDER + 0.15) / 2
    y_ledge = y_in + (P.SLIDE_POST_UNDER + 0.15 + P.SLIDE_POCKET_OUT) / 2
    y_bear = y_in + (P.SLIDE_POST_UNDER + 0.15
                     + P.SLIDE_POST_UNDER + P.SLIDE_NOSE_Y) / 2
    # 3.7 - FIT: the gallery floor's inner corner, from which both
    # 45-degree slopes are laid out -- see _slide_pockets.
    z_ledge = (P.Z_FLOOR + P.SLIDE_TAB_H - P.SLIDE_NOSE_H + 0.10
               - P.SLIDE_FIT)
    tab_spots = [(xt, side) for xt in P.SLIDE_TAB_X for side in (-1, 1)]
    posts = channels = ledges = 0
    for xt, side in tab_spots:
        x_e = xt - P.SLIDE_TAB_L / 2 + P.SLIDE_CAPTURE
        pr = Pos(xt, side * y_post, P.BOTTOM_T + P.SLIDE_TAB_H / 2) * Box(
            P.SLIDE_TAB_L * 0.5, 0.30, P.SLIDE_TAB_H * 0.5)
        if (pr & built["bottom"]).volume > 1e-6:
            posts += 1
        pr = Pos(xt, side * y_chan, P.BOTTOM_T + P.SLIDE_TAB_H / 2) * Box(
            P.SLIDE_TAB_L * 0.5, 0.25, P.SLIDE_TAB_H * 0.5)
        if (pr & built["shell"]).volume < 1e-6:
            channels += 1
        pr = Pos(x_e - 0.40, side * y_ledge,
                 (P.Z_FLOOR + z_ledge) / 2) * Box(
            0.50, 0.35, (z_ledge - P.Z_FLOOR) * 0.5)
        if (pr & built["shell"]).volume > 1e-6:
            ledges += 1
    want = len(tab_spots)
    good = posts == want and channels == want and ledges == want
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'slide':<7} post {posts}/{want}, "
          f"channel void {channels}/{want}, ledge {ledges}/{want}")

    # The right trim, measured on the solid rather than read from its
    # constant. This class already cost a case print: a 0.1 stop is
    # invisible to every boolean at nominal -- the parts only collide
    # once the printer's shrink has eaten the clearance -- so the guard
    # is that the material is *gone*, not that a formula says so.
    # Watched failing at 25.408 mm3 with the trim skipped -- every
    # other check green around it, which is the class demonstrating
    # itself.
    pr = Pos((P.SLIDE_RIGHT_TRIM_X + P.CASE_W / 2 - P.SEAM_STEP_W) / 2, 0,
             P.BOTTOM_T - P.SEAM_STEP_H / 2) * Box(
        (P.CASE_W / 2 - P.SEAM_STEP_W) - P.SLIDE_RIGHT_TRIM_X - 0.2,
        P.CASE_D - 2 * P.SEAM_STEP_W - 0.2, P.SEAM_STEP_H * 0.5)
    leftover = (pr & built["bottom"]).volume
    good = leftover < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'slide':<7} tongue gone past the "
          f"right trim {leftover:9.3f} mm3")

    # The capture is a claim about a *shifted* plate, so shift it. Down
    # by more than SLIDE_FIT every eave must be in contact with its
    # ledge -- that is the sagging seam being held -- and down by less
    # than SLIDE_FIT nothing may touch at all, or the fit is not a fit.
    # The plate moving down opens every other gap in the stack, so any
    # contact is the latch's. Watched failing both ways: catch 0/10
    # with the ledges cut away, and free-play 0.750 mm3 (wedge faces;
    # 0.575 on the flats they replaced) with the ledge plane raised
    # half a fit -- the one injection that fires this check alone,
    # which is what proves it is not measuring some other collision.
    drop = Pos(0, 0, -(P.SLIDE_FIT + 0.15)) * built["bottom"]
    contact = built["shell"] & drop
    caught = 0
    for xt, side in tab_spots:
        x_e = xt - P.SLIDE_TAB_L / 2 + P.SLIDE_CAPTURE
        pr = Pos(x_e - P.SLIDE_CAPTURE / 2, side * y_bear,
                 z_ledge + 0.30) * Box(
            P.SLIDE_CAPTURE + 0.4, 0.80, 1.00)
        if _shared(contact, pr) > 1e-3:
            caught += 1
    free = (built["shell"] & (Pos(0, 0, -(P.SLIDE_FIT - 0.10))
                              * built["bottom"])).volume
    good = caught == want and free < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'slide':<7} ledges catch a "
          f"dropped plate {caught}/{want}, free below the fit {free:9.3f} mm3")

    # The assembly corridor: the plate at the deep end of the drop
    # window, coming down, and mid-slide, against the shell and the
    # board. dz is negative -- the plate approaches from **below** in
    # case space (the first slide latch wrote this probe with +dz and
    # reported 4207 mm3 of plate rammed up into the board; the probe
    # was wrong, not the part). The board's mock is used **without the
    # mated plug** -- nothing is plugged in while the case is open --
    # and the switch bodies are skipped: the plate's tallest feature
    # stops 1.5 under the board itself. The first slide latch watched
    # a real fault here on this probe's first honest run -- 1.681 mm3
    # of tongue corner standing in the skirt's corner arcs -- which is
    # why both trims are the skirt's own shifted outline -- the
    # straight right trim repeated the fault at 1.488 on the leftward
    # flip's first run. Watched failing since: 9.080 / 9.680 / 9.438
    # with a tab pair moved off its entries (earlier geometries:
    # 4.855-class on the first eave, 5.7-8.8 on the nose, 26.036 with
    # the left trim skipped, 4.784 / 6.624 with entries cut short).
    bare_board = mock.board() - parts._block(
        P.USB_CX + P.USB_OVERHANG, P.CASE_W / 2 + 20.0,
        -P.CASE_D / 2, P.CASE_D / 2, 0.0, P.CASE_H)
    # The corridor runs against the shell **without the detent's
    # bumps**: camming over them at seam-closed is the detent working,
    # not a corridor fault, and it gets its own checks below.
    shell_less = built["shell"] - parts._detent_ridges()
    deep = P.SLIDE_ENTRY_MAX - 0.05
    for dx, dz in ((deep, -4.0), (deep, -0.5), (deep, 0.0), (1.0, 0.0)):
        moved = Pos(dx, 0, dz) * built["bottom"]
        hit = (moved & shell_less).volume + _shared(moved, bare_board)
        good = hit < 1e-6
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {'slide':<7} corridor at "
              f"dx {dx:+.2f} dz {dz:+.2f}         {hit:9.3f} mm3")

    # --- the detent -----------------------------------------------------
    # Shape first: the ridge stands where the gallery was void, the
    # notch opens where the eave's tip was solid. Watched failing at
    # ridge 0/2 + all contacts 0.000 with the ridges never added, and
    # at notch 0/2 with the notches never cut -- that one also firing
    # the global interference at 0.031 (the ridge standing in an
    # un-notched tip at home IS the notch's necessity).
    X = P.SLIDE_DETY_X
    y_in2 = P.CASE_D / 2 - P.WALL
    ridges = voids_n = 0
    for side in (-1, 1):
        pr = Pos(X, side * (y_in2 + 1.02), 4.50) * Box(0.6, 0.18, 0.3)
        if (pr & built["shell"]).volume > 1e-6:
            ridges += 1
        pr = Pos(X, side * (y_in2 + 0.95), 4.45) * Box(0.6, 0.18, 0.2)
        if (pr & built["bottom"]).volume < 1e-6:
            voids_n += 1
    good = ridges == 2 and voids_n == 2
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'detent':<7} ridge on the skin "
          f"{ridges}/2, notch in the tip {voids_n}/2")

    # Function second. Slid back past the notch's play, the notch's
    # west wall must meet the ridge -- that is the click's catch, in
    # any orientation, because it acts in y. Mid-slide the un-notched
    # tip must overlap the ridge (that is the drag the skin's bending
    # absorbs; ~1.5% strain, the arithmetic is at the constants). No
    # rigid probe can show the flexed pass, so what is checked is that
    # both contacts exist and everything else stays clear -- the
    # corridor above already runs without the ridges.
    det_win = Pos(X, 0, 4.4) * Box(4.0, 2 * P.CASE_D, 1.4)
    lock = _shared(built["shell"] & (Pos(0.80, 0, 0) * built["bottom"]),
                   det_win)
    cam = _shared(built["shell"] & (Pos(1.50, 0, 0) * built["bottom"]),
                  det_win)
    home = _shared(built["shell"] & built["bottom"], det_win)
    good = lock > 1e-3 and cam > 1e-3 and home < 1e-6
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'detent':<7} catches slid-back "
          f"{lock:6.3f} mm3, drags mid-slide {cam:6.3f}, free at home "
          f"{home:6.3f}")

    # A sweep whose entries come out identical tests nothing. Only the
    # shell reads SLIDE_FIT    # A sweep whose entries come out identical tests nothing. Only the
    # shell reads SLIDE_FIT -- it is the shelf's height under the nose
    # -- so its four slices must differ and the plate's four must not,
    # except by the ink in the labels.
    slide_solids = built["coupon-slide"].solids()
    sxs = sorted(so.center().X for so in slide_solids)
    split = (sxs[0] + sxs[-1]) / 2
    plate_v = sorted(so.volume for so in slide_solids if so.center().X < split)
    shell_v = sorted(so.volume for so in slide_solids if so.center().X >= split)
    want_n = len(P.SLIDE_FIT_SWEEP)
    steps = [round(shell_v[i + 1] - shell_v[i], 4)
             for i in range(len(shell_v) - 1)]
    good = (len(plate_v) == want_n and len(shell_v) == want_n
            and min(steps) > 0.01 and (plate_v[-1] - plate_v[0]) < 1.0)
    ok.append(good)
    print(f"  [{'ok ' if good else 'BAD'}] {'coupon':<7} slide fits differ "
          f"{len(shell_v)}/{want_n}, steps {steps}")

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
    for label, got, bound in (
        ("pad over the ring's inner edge",
         (P.CAP_BEAR_DIA - P.STEM_RING_ID) / 2, 0.20),
        ("pad inside the housing mouth",
         (P.HOUSING_MOUTH_DIA - P.CAP_BEAR_DIA) / 2, 0.20),
        # Virtually a press, chosen: 5.40 is the only boss that closes
        # the tube on a 0.4 nozzle, and the ring joint is static.
        ("cap boss inside the ring bore",
         (P.STEM_RING_ID - P.CAP_BOSS_DIA) / 2, 0.03),
        ("flat clearance in the ring",
         (P.STEM_RING_ID - P.CAP_BOSS_FLATS) / 2, 0.15),
    ):
        good = got >= bound
        ok.append(good)
        print(f"  [{'ok ' if good else 'BAD'}] {label:<38} {got:8.3f}  "
              f"(want {bound:.3f})")

    # The bore is a cut inside a boss, and a cut that lands in air
    # removes nothing while every check above still passes. Measure the
    # shape: build the cap with the cut moved away and diff the volumes.
    real_cut = parts._socket_cut
    parts._socket_cut = lambda *a: Pos(0, 200, 0) * Box(0.1, 0.1, 0.1)
    solid_cap = parts.dummy_cap().volume
    parts._socket_cut = real_cut
    w = P.STEM_CROSS_W + P.STEM_CLEAR
    ln = P.STEM_CROSS_L + P.STEM_LEN_CLEAR
    mw, ml = w + P.STEM_MOUTH, ln
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
