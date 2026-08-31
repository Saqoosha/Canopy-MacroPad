#!/usr/bin/env python3
"""Check the firmware's LED quantisation without a board.

Stdlib only, like `tools/mpad.py`, and it does not import
`firmware/code.py` -- that file is the whole program and running it needs
a device. It pulls `paint()`, `write_pixel()`, `lerp_rgb()` and the render
loop's `for` body out of the source with `ast` and executes those exact
bytes against stub globals. So this cannot quietly go on passing about
code that has moved: rename or reshape any of them and the extraction
asserts instead of reporting a green run about a copy.

What it is for. Temporal dithering is the one thing here that cannot be
judged by reading, because it is correct only on average and only above a
rate. Nine checks, and four of them exist because the obvious version of
this test passes on code that does nothing:

  1  the dithered mean lands on the ideal        -- the whole mechanism
  2  no channel carries into the one above it    -- a rounding error that
                                                    would look like the
                                                    wrong colour
  3  the floor freeze shortens above the floor,
     and below it the two builds agree exactly   -- the claim, and the
                                                    deliberate half that
                                                    gives up
  4  the same code undithered at 200 Hz does not -- so the win is the
                                                    dithering and not the
                                                    paint rate
  5  a settled key rounds, clears its residue,
     and stops writing                           -- or a solid key
                                                    shimmers for ever
  6  a settled key repaints after `B`, and does
     not without the invalidation                -- the skip that pays for
                                                    `.brightness` moving
                                                    into `paint()`
  7  under DITHER_FLOOR a channel is rounded and
     its residue cleared; over it, it dithers    -- the second half of the
                                                    threshold, the half
                                                    that gives up
  8  the floor is tested per channel, not by key -- ff8000 is routinely
                                                    over it in red and
                                                    under it in blue
  9  a key that FADES into settlement lands on
     round-to-nearest and stays there            -- check 6 starts its key
                                                    already settled, and
                                                    missed a real bug in
                                                    the one frame it skips

Every check here has been watched going red, by injecting the fault into
`firmware/code.py` and re-running:

    residue dropped in R / G / B     -> 1, at -0.455/-0.518/-0.533 LSB
    control sweep dithered after all -> 4
    settled branch keeps its residue -> 5
    skip written `settled` alone     -> 6
    green never consults the floor   -> 3, and 7 once 3 is muted
    floor decided per key            -> 3, and 7 once 3 is muted
    floor comparison inverted        -> 3, and 8 once 3 is muted
    `settled` read before the assign -> 9, at 2 of 7 tick rates

Check 3's "below the floor the two builds agree exactly" fires first on all
three floor faults, so 7 and 8 were watched with that one assertion muted --
and **that isolation run was confirmed green on unmodified firmware before
any of its reds were believed.** The first attempt was not, and it is the
sharpest version of this file's whole lesson: the muted copy was run from a
scratch directory, where its own relative path to `firmware/code.py` does
not resolve, so all three faults "failed" with a FileNotFoundError that had
nothing to do with them. Three reds, no catches, and it reads exactly like
success.

**A guard can also stop working without being touched.** Check 4 swept the
whole breath, and the day `DITHER_FLOOR` landed most of that breath stopped
being dithered at all -- so the difference it watches for no longer existed
and its injection came back green. It measures only above the floor now,
like check 3. A guard that used to fail and quietly cannot any more is
worse than one that never could, because its history is why it is trusted.

Three more lessons are baked into the shape above. **The fault has to leave
the extraction asserts' text alone.** Deleting `settled or not DITHER`
turned the whole run red at the top of this file, which reads as a catch and
is not one -- the drift guard fired, the checks never ran. **Checks 1 and 3
used to sweep 0xFFFFFF and read `& 0xFF`**, which is the blue channel tested
three times: red's accumulator was deleted and the run came back green.
`COLOR` differs per channel now and each is asserted on its own. And **a
probe that starts in the state it means to test proves nothing about
reaching it** -- check 6 seeds an already-settled key, so eight green checks
sat on top of a bug living in the single frame a fade completes on, until an
outside reviewer read the ordering. Check 9 is that frame.

The harness has also been wrong twice in the other direction --
`write_pixel()` elides an unchanged value, so reading the last write instead
of the cache reported "no output" for code that was working.

Photometry is not in scope. Every number here is arithmetic against the
integer scaling in CircuitPython's `PixelBuf.c`; whether the result looks
right on SK6812MINI-E at 3V3 is a board-and-eyes question.

    tools/dither_check.py        must end in `all checks passed`
"""

import array, ast, io, math, os, textwrap

SRC = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   os.pardir, "firmware", "code.py"),
                      encoding="utf-8").read()
TREE = ast.parse(SRC)

def func_src(name):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(SRC, node)
    raise AssertionError("no function " + name)

def render_for_src():
    """The `for i in range(NUM_KEYS):` body of the render loop, dedented."""
    for node in ast.walk(TREE):
        if (isinstance(node, ast.For) and isinstance(node.target, ast.Name)
                and node.target.id == "i"
                and isinstance(node.iter, ast.Call)
                and getattr(node.iter.func, "id", "") == "range"
                and any("paint" in ast.dump(x) for x in node.body)):
            return textwrap.dedent(ast.get_source_segment(SRC, node))
    raise AssertionError("render loop not found")

PAINT, WRITE, RENDER = func_src("paint"), func_src("write_pixel"), render_for_src()


def phase_advance_src():
    """The lines that turn a frame delta into `_step_ms`, verbatim.

    They live in the paint-tick block rather than in a function, so they
    are found by walking to the `if now - last_pulse_at ...` statement and
    taking the assignments before the `for`. Pulled out rather than
    rewritten because the carry is the whole point: drop it and every
    breath runs slow, which is a rate error that never corrects itself and
    which no amount of reading the loop makes obvious.
    """
    for node in ast.walk(TREE):
        if not isinstance(node, ast.If):
            continue
        src = ast.get_source_segment(SRC, node) or ""
        if "last_pulse_at = now" not in src or "_phase_carry_ns" not in src:
            continue
        out = []
        for stmt in node.body:
            if isinstance(stmt, ast.For):
                break
            out.append(ast.get_source_segment(SRC, stmt))
        joined = textwrap.dedent("\n".join(out))
        for must in ("_phase_carry_ns", "_step_ms", "_phase_last_ns"):
            assert must in joined, "phase advance no longer assigns " + must
        return joined
    raise AssertionError("the paint-tick block that advances the phase is gone")


PHASE_SRC = phase_advance_src()

def const(name):
    """Read a module-level constant out of the firmware, so nothing here
    restates a number the firmware owns."""
    for node in TREE.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], "id", None) == name):
            return ast.literal_eval(node.value)
    raise AssertionError("no constant " + name)

FIRMWARE_FLOOR = const("DITHER_FLOOR")


def curve_src():
    """The module-level statements that build PULSE_CURVE, verbatim.

    Rebuilding the curve from its formula here would be a copy, and a copy
    is exactly what this file exists not to be: the shape could change in
    the firmware and every check would go on passing about the old one.

    Everything assigned between `_CURVE_STEPS` and `PULSE_CURVE` comes
    along, rather than a list of names spelled out here: the curve has
    already grown a helper (`_E`) once, and a name list would have to be
    edited every time it does. The three that must exist are asserted.
    """
    out, taking = [], False
    for node in TREE.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        name = getattr(node.targets[0], "id", None)
        if name == "PULSE_GAMMA":
            out.append(ast.get_source_segment(SRC, node))
        if name == "_CURVE_STEPS":
            taking = True
        if taking:
            out.append(ast.get_source_segment(SRC, node))
        if name == "PULSE_CURVE":
            taking = False
    for must in ("PULSE_GAMMA", "_CURVE_STEPS", "PULSE_CURVE"):
        assert any(l.startswith(must) for l in out), \
            "curve build no longer assigns " + must
    return "\n".join(out)


CURVE_SRC = curve_src()
assert "dither_err" in PAINT and "settled or not DITHER" in PAINT
assert "paint(i, base, level, settled)" in RENDER
assert "last_rgb[i] is not None" in RENDER
print("extracted real source: paint()={} B, write_pixel()={} B, render for-loop={} B"
      .format(len(PAINT), len(WRITE), len(RENDER)))


class Rig:
    """Minimal globals the extracted code needs. Records what hits hardware."""
    def __init__(self, num_keys=6, dither=True, bright=0.6, gamma=1.0,
                 dfloor=None):
        self.frames = []
        g = {"NUM_KEYS": num_keys, "DITHER": dither, "brightness": bright,
             "math": math, "array": array,
             # None means "whatever the firmware says", so the checks below
             # measure the shipping number rather than one restated here.
             "DITHER_FLOOR": FIRMWARE_FLOOR if dfloor is None else dfloor,
             "dither_err": [0.0] * (num_keys * 3),
             "last_rgb": [None] * num_keys,
             "group_dirty": [False],
             "pixel_groups": [(self, 0, num_keys)]}
        exec(CURVE_SRC, g)          # the firmware's own curve, not a copy
        if gamma is not None:
            g["PULSE_GAMMA"] = gamma
        exec(WRITE, g); exec(PAINT, g)
        self.g = g
    # stand in for a pixelbuf
    def __setitem__(self, k, v): self.frames.append(v)
    def paint(self, *a): self.g["paint"](*a)
    def last(self, i): return self.g["last_rgb"][i]
    def err(self): return list(self.g["dither_err"])
    def set_brightness(self, b): self.g["brightness"] = b


def lvl(t, floor, g, T=2.0):
    return floor + (1 - floor) * ((1 - math.cos(2 * math.pi * t / T)) / 2) ** g

# Three channels that differ, so a residue dropped in one of them cannot
# hide behind the other two. A sweep of 0xFFFFFF and a `& 0xFF` read
# tested the blue channel three times and passed with red's accumulator
# deleted -- watched, and the reason this constant is not white.
COLOR = 0xC08040
CHANNELS = ((16, "R"), (8, "G"), (0, "B"))

def sweep(rate, b, floor, g, dither, cycles=2, color=COLOR):
    """Packed values for a whole breath, plus the float ideal per channel."""
    rig = Rig(dither=dither, bright=b, gamma=g)
    n = int(rate * 2.0 * cycles); out = []
    for k in range(n):
        rig.frames.clear()
        rig.paint(0, color, lvl(k / rate, floor, g), False)
        out.append(rig.frames[-1] if rig.frames else out[-1])
    ide = {sh: [((color >> sh) & 0xFF) * lvl(k / rate, floor, g) * b
                for k in range(n)] for sh, _ in CHANNELS}
    return out, ide, rig

def chan(packed, sh):
    return [(v >> sh) & 0xFF for v in packed]

def freeze_ms(seq, rate):
    best = run = 1
    for k in range(1, len(seq)):
        run = run + 1 if seq[k] == seq[k - 1] else 1
        best = max(best, run)
    return best * 1000.0 / rate

print()
print("--- 1. the mean must land on the ideal (that is the whole mechanism) ---")
# Only over the frames the firmware is allowed to dither. Below
# DITHER_FLOOR it rounds on purpose, so an exact mean is not promised
# there and averaging the two regions together would test neither.
for b in (0.60, 0.15, 0.10):
    o, i, _ = sweep(200, b, 0.15, 2.0, True)
    errs = []
    for sh, nm in CHANNELS:
        c = chan(o, sh)
        keep = [k for k in range(len(c)) if i[sh][k] >= FIRMWARE_FLOOR]
        if len(keep) < 20:
            errs.append("{} n/a".format(nm))
            continue
        e = (sum(c[k] for k in keep) - sum(i[sh][k] for k in keep)) / len(keep)
        errs.append("{} {:+.4f}".format(nm, e))
        assert abs(e) < 0.05, "dither is biased in {}: {:+.4f} LSB".format(nm, e)
    print("    b={:.2f}  mean error above the floor: {}".format(b, "  ".join(errs)))

print()
print("--- 2. no channel may carry into the one above it ---")
worst = 0
for b in (1.0, 0.99, 0.6):
    rig = Rig(dither=True, bright=b)
    v = 0
    for k in range(4000):
        rig.frames.clear()
        rig.paint(0, 0xFFFFFF, 1.0, False)
        if rig.frames:          # write_pixel elides an unchanged value
            v = rig.frames[-1]
        worst = max(worst, v)
        assert v <= 0xFFFFFF, "packed value overflowed: {:#x}".format(v)
        for sh in (16, 8, 0):
            assert 0 <= (v >> sh) & 0xFF <= 255
print("    4000 frames x 3 brightnesses, max packed {:#08x} -- no bleed".format(worst))

print()
print("--- 3. THE CLAIM: the floor freeze, gamma 2.0, measured on real paint() ---")
# The claim has two halves since DITHER_FLOOR exists, and both are
# requirements rather than one being a regrettable side effect. Above the
# floor the freeze must shorten -- that is what dithering is for. Below
# it the output must be *identical* to the undithered build, because
# giving up down there is the deliberate half of the design and a
# difference would mean the floor is leaking.
print("    measured only where the firmware is allowed to dither")
print("    {:>6} | {:>16} | {:>18}".format("b", "no dither @50Hz", "dither @200Hz"))
for b in (0.60, 0.30, 0.15, 0.10):
    o50, i50, _ = sweep(50, b, 0.15, 2.0, False)
    o200, i200, _ = sweep(200, b, 0.15, 2.0, True)
    row = []
    for sh, nm in CHANNELS:
        a = [chan(o50, sh)[k] for k in range(len(o50))
             if i50[sh][k] >= FIRMWARE_FLOOR]
        c = [chan(o200, sh)[k] for k in range(len(o200))
             if i200[sh][k] >= FIRMWARE_FLOOR]
        if len(a) < 10 or len(c) < 10:
            continue
        f50, f200 = freeze_ms(a, 50), freeze_ms(c, 200)
        row.append((nm, f50, f200))
        assert f200 < f50, \
            "channel {} did not improve above the floor: {:.0f} -> {:.0f} ms".format(
                nm, f50, f200)
    assert row, "no channel reached the floor -- the sweep tests nothing"
    print("    {:6.2f} | {:13.0f} ms | {:15.0f} ms   ({})".format(
        b, max(r[1] for r in row), max(r[2] for r in row),
        " ".join("{} {:.0f}->{:.0f}".format(*r) for r in row)))

print("    and below the floor the two builds must agree exactly:")
for b in (0.30, 0.10):
    o, i, _ = sweep(200, b, 0.15, 2.0, True)
    p, _, _ = sweep(200, b, 0.15, 2.0, False)
    diffs = 0
    n = 0
    for sh, nm in CHANNELS:
        for k in range(len(o)):
            if i[sh][k] < FIRMWARE_FLOOR:
                n += 1
                if chan(o, sh)[k] != chan(p, sh)[k]:
                    diffs += 1
    assert n > 30, "not enough samples under the floor to mean anything"
    assert diffs == 0, "{} of {} samples under the floor differ -- the floor leaks".format(
        diffs, n)
    print("      b={:.2f}: {} samples under the floor, all identical".format(b, n))

print()
print("--- 4. NEGATIVE CONTROL: same code with DITHER off must NOT improve ---")
for b in (0.15, 0.10):
    # Above the floor, like check 3. Measured over the whole breath this
    # control went inert the day DITHER_FLOOR landed: most of the sweep is
    # under the floor, both builds round there, and the difference the
    # assertion is watching for stopped existing. It passed either way,
    # which is the worst state a guard can be in.
    off50, i50, _ = sweep(50, b, 0.15, 2.0, False)
    off200, i200, _ = sweep(200, b, 0.15, 2.0, False)  # faster, not dithered
    def above(o, i, sh):
        return [chan(o, sh)[k] for k in range(len(o)) if i[sh][k] >= FIRMWARE_FLOOR]
    f50 = max(freeze_ms(above(off50, i50, sh), 50) for sh, _ in CHANNELS
              if len(above(off50, i50, sh)) >= 10)
    f200 = max(freeze_ms(above(off200, i200, sh), 200) for sh, _ in CHANNELS
               if len(above(off200, i200, sh)) >= 10)
    print("    b={:.2f}  dither off @50Hz {:.0f} ms  @200Hz {:.0f} ms  <- rate alone buys nothing"
          .format(b, f50, f200))
    assert f200 >= f50 * 0.9, \
        "rate alone improved it -- then the win is not the dithering"

print()
print("--- 5. a settled key rounds, clears its residue, and stops moving ---")
rig = Rig(dither=True, bright=0.15)
for k in range(50):
    rig.frames.clear(); rig.paint(0, 0x808080, 0.77, False)
assert any(x != 0.0 for x in rig.err()), "residue never accumulated -- test is inert"
rig.frames.clear(); rig.paint(0, 0x808080, 0.77, True)
assert rig.err()[:3] == [0.0, 0.0, 0.0], "settled key kept its residue"
want = int(0x80 * 0.77 * 0.15 + 0.5)
got = rig.last(0) & 0xFF   # may be elided as unchanged; the cache is the truth
assert got == want, "settled key not round-to-nearest: {} vs {}".format(got, want)
before = rig.last(0)
for k in range(20):
    rig.frames.clear(); rig.paint(0, 0x808080, 0.77, True)
    assert not rig.frames, "settled key kept writing to hardware"
assert rig.last(0) == before
print("    residue cleared, value = round-to-nearest ({}), 20 further frames elided"
      .format(want))

print()
print("--- 6. the render loop's settled-skip must let a B through ---")
env = {"NUM_KEYS": 1, "DITHER": True, "brightness": 0.6,
       "math": math, "array": array, "time": __import__("time"),
       "DITHER_FLOOR": FIRMWARE_FLOOR,
       "dither_err": [0.0] * 3, "last_rgb": [None], "group_dirty": [False],
       "from_rgb": [0x00FF00], "to_rgb": [0x00FF00],
       "from_floor": [1.0], "to_floor": [1.0],
       "phase_ms": [0], "period_ms": [2500], "_step_ms": 0, "now": 0,
       # The loop inlines the finished-fade test now, so these have to be
       # real even though `fade_progress` below is still stubbed.
       "fade_started": [0], "crossfade_ns": 0,
       "fade_progress": lambda i, now: 1.0}
rec = []
class Grp:
    def __setitem__(self, k, v): rec.append(v)
env["pixel_groups"] = [(Grp(), 0, 1)]
exec(CURVE_SRC, env)
exec(WRITE, env); exec(PAINT, env); exec(func_src("lerp_rgb"), env)
exec(RENDER, env); first = len(rec)
exec(RENDER, env)
assert len(rec) == first == 1, "settled key painted twice or never: {}".format(rec)
# now the host changes brightness the way set_brightness does
env["brightness"] = 0.20
env["last_rgb"][0] = None            # exactly what invalidate_pixels() does
exec(RENDER, env)
assert len(rec) == 2, "a settled key did not repaint after B -- the bug this guards"
assert (rec[1] >> 8 & 0xFF) == int(255 * 0.20 + 0.5), "repainted at the wrong brightness"
print("    settled key painted once ({:#08x}), skipped, then repainted after B ({:#08x})"
      .format(rec[0], rec[1]))
# negative control: without the invalidation it must stay skipped
env["brightness"] = 0.90
exec(RENDER, env)
assert len(rec) == 2, "skip is not actually skipping -- test 6 proves nothing"
print("    negative control: brightness moved with no invalidation -> still skipped")

print()
print("--- 7. below DITHER_FLOOR a channel is rounded, above it dithers ---")
print("    firmware value: DITHER_FLOOR = {}".format(FIRMWARE_FLOOR))
_saw_round = _saw_dither = False
for target in (0.4, 1.4, 2.4, 3.4, 4.4, 5.4, 6.4, 9.4, 19.4):
    rig = Rig(dither=True, bright=1.0)
    vals, last = [], 0
    for _ in range(200):
        rig.frames.clear()
        rig.paint(0, 0x000100, target, False)      # green channel = 1 * target
        if rig.frames:
            last = rig.frames[-1]
        vals.append((last >> 8) & 0xFF)
    span = max(vals) - min(vals)
    mean = sum(vals) / len(vals)
    below = target < FIRMWARE_FLOOR
    if below:
        _saw_round = True
        assert span == 0, \
            "value {} is under the floor and still moved {}..{}".format(
                target, min(vals), max(vals))
        assert vals[0] == int(target + 0.5), \
            "value {} under the floor is not round-to-nearest".format(target)
        assert rig.err()[1] == 0.0, "residue kept below the floor"
    else:
        _saw_dither = True
        assert span == 1, \
            "value {} is over the floor and swung {} levels".format(target, span)
        assert abs(mean - target) < 0.05, \
            "value {} over the floor tracked to {:.3f}".format(target, mean)
    print("    {:5.1f}  ->  {}  {}".format(
        target, "held at {}".format(vals[0]) if below
        else "swings {}..{}, mean {:.3f}".format(min(vals), max(vals), mean),
        "(rounded)" if below else "(dithered)"))
assert _saw_round and _saw_dither, "the sweep did not straddle the floor -- inert"

print()
print("--- 8. the floor is per channel, not per key ---")
# one colour whose channels land either side of the floor at once. A per-key
# test would have to get one of them wrong, and which one it got wrong is
# what the assertions below pin down.
# One colour whose two channels land either side of the floor in the same
# call. The fraction has to come from the brightness: whole channel values
# times a whole level are integers, and an integer never dithers, so a
# probe built that way reports "did not dither" about code that is fine.
BR = 0.51
R_CH, G_CH = 40, 4                       # -> 20.40 and 2.04
assert G_CH * BR < FIRMWARE_FLOOR <= R_CH * BR, "the probe does not straddle the floor"
rig = Rig(dither=True, bright=BR)
red, green, last = [], [], 0
for _ in range(200):
    rig.frames.clear()
    rig.paint(0, (R_CH << 16) | (G_CH << 8), 1.0, False)
    if rig.frames:
        last = rig.frames[-1]
    red.append((last >> 16) & 0xFF)
    green.append((last >> 8) & 0xFF)
assert max(red) - min(red) == 1, \
    "the high channel did not dither: {}..{} (a per-key floor would do this)".format(
        min(red), max(red))
assert abs(sum(red) / len(red) - R_CH * BR) < 0.05, "the high channel drifted"
assert max(green) - min(green) == 0, \
    "the low channel dithered: {}..{} (a per-key floor would do this)".format(
        min(green), max(green))
assert green[0] == int(G_CH * BR + 0.5), "the low channel is not round-to-nearest"
print("    one call: red {:.2f} swings {}..{} (dithered), "
      "green {:.2f} held at {} (rounded)".format(
          R_CH * BR, min(red), max(red), G_CH * BR, green[0]))

print()
print("--- 9. a key that fades into settlement lands on round-to-nearest ---")
# Check 6 seeds a key that is *already* settled, so it never crosses the one
# frame where a fade completes -- and that frame is where the bug was. The
# `settled` flag was read before `from_rgb = to_rgb`, so the completing
# frame still saw `from != to`, painted through the dithering branch, and
# the skip then froze whichever of the two bytes the dither happened to
# emit. Permanently, because the rounding branch was never reached again.
CROSS = 500_000_000


def fade_to(step_ns, target, bright, cross=CROSS):
    """Drive one key from black to `target` through a real crossfade."""
    seen = []

    class Grp:
        def __setitem__(self, k, v):
            seen.append(v)

    env = {"NUM_KEYS": 1, "DITHER": True, "brightness": bright,
           "math": math, "array": array, "time": __import__("time"),
           "DITHER_FLOOR": FIRMWARE_FLOOR,
           "dither_err": [0.0] * 3, "last_rgb": [None], "group_dirty": [False],
           "from_rgb": [0x000000], "to_rgb": [target],
           "from_floor": [1.0], "to_floor": [1.0],
           "phase_ms": [0], "period_ms": [2500], "_step_ms": 5, "now": 0,
           "crossfade_ns": cross, "fade_started": [0],
           "pixel_groups": [(Grp(), 0, 1)]}
    exec(CURVE_SRC, env)
    exec(WRITE, env); exec(PAINT, env); exec(func_src("lerp_rgb"), env)
    env["fade_progress"] = lambda i, now: min(1.0, max(0.0, now / cross))
    t = 0
    while t <= cross + 30 * step_ns:
        env["now"] = t
        exec(RENDER, env)
        t += step_ns
    return env["last_rgb"][0], len(seen)


TARGET, BRIGHT = 0x734D26, 0.6      # every channel lands on a fraction at 0.6
want = 0
for _sh in (16, 8, 0):
    want |= int(((TARGET >> _sh) & 0xFF) * BRIGHT + 0.5) << _sh
assert any(((TARGET >> sh) & 0xFF) * BRIGHT % 1 for sh, _ in CHANNELS), \
    "the probe colour has no fractional channel -- nothing to dither, inert"
# Seven rates, because the fault only shows where the completing frame's
# phase lands: two of these caught it and five did not. One rate would have
# reported the broken code healthy five times out of seven.
RATES = (5_100_000, 5_250_000, 5_333_333, 4_900_000,
         6_760_000, 5_000_000, 6_500_000)
off = []
for step in RATES:
    got, writes = fade_to(step, TARGET, BRIGHT)
    assert writes > 5, "the fade never painted -- the probe is inert"
    if got != want:
        off.append((step, got))
assert not off, "settled on the wrong value at {} of {} tick rates: {}".format(
    len(off), len(RATES), ["{}ns->0x{:06x}".format(s, g) for s, g in off])
print("    {} tick rates, all settling on round-to-nearest 0x{:06x} "
      "(channels {:.1f}/{:.1f}/{:.1f})".format(
          len(RATES), want,
          *[((TARGET >> sh) & 0xFF) * BRIGHT for sh, _ in CHANNELS]))

print()
print("--- 10. the breath keeps its period, frame rate notwithstanding ---")
# `phase_ms` is advanced by a whole number of milliseconds each frame, so
# without the carry every breath would run slow by the truncation -- about
# 0.6% at a 7 ms frame, for ever, with nothing to notice it. The frame
# periods below are deliberately not divisors of a millisecond.
PERIOD_MS = 2500
for frame_us, label in ((6_760, "148 Hz"), (5_882, "170 Hz"),
                        (7_042, "142 Hz"), (5_208, "192 Hz")):
    env = {"_phase_carry_ns": 0, "_phase_last_ns": 0, "now": 0,
           "last_pulse_at": 0, "PULSE_STEP_NS": 0,
           "phase_ms": [0], "period_ms": [PERIOD_MS], "NUM_KEYS": 1}
    total_ms = 0
    frames = 0
    # run twenty breaths, so a per-frame truncation would show up twenty
    # times over rather than hiding inside one period
    while total_ms < PERIOD_MS * 20:
        env["now"] += frame_us * 1000
        exec(PHASE_SRC, env)
        total_ms += env["_step_ms"]
        frames += 1
    wall_ms = env["now"] / 1_000_000.0
    drift = (total_ms - wall_ms) / wall_ms
    assert abs(drift) < 0.001, \
        "the breath drifts {:+.3f}% at a {} frame ({} ms of phase over {:.0f} ms of wall)".format(
            drift * 100, label, total_ms, wall_ms)
    print("    {:>6} frame: {} frames, {} ms of phase over {:.0f} ms of wall, drift {:+.4f}%"
          .format(label, frames, total_ms, wall_ms, drift * 100))
# The wrap has to survive a frame LONGER THAN THE PERIOD, and this half of
# the check exists because the first version could not fail: it swept 4000
# frames of a 6.76 ms step against a 2500 ms period, never came within two
# orders of magnitude of the boundary, and passed just as happily on the
# single-subtract wrap that breaks there. A guard that cannot reach the
# condition it guards is not a guard.
#
# The condition is reachable in service: `serial.write_timeout` is 0.05 s
# per write, several key edges can be reported in one pass against a host
# that has stopped draining, and `set_pulse` clamps the period no higher
# than 100 ms. Driven through the real render loop, so what is asserted is
# the actual IndexError rather than a reimplementation of the arithmetic.
STALL_PERIOD_MS = 100          # the clamped minimum a host may ask for


def render_one_frame(step_ms, period_ms, phase_ms, rgb=0x00FF80):
    seen = []

    class Grp:
        def __setitem__(self, k, v):
            seen.append(v)

    env = {"NUM_KEYS": 1, "DITHER": True, "brightness": 0.6,
           "math": math, "array": array, "time": __import__("time"),
           "DITHER_FLOOR": FIRMWARE_FLOOR,
           "dither_err": [0.0] * 3, "last_rgb": [None], "group_dirty": [False],
           "from_rgb": [rgb], "to_rgb": [rgb],
           "from_floor": [0.1], "to_floor": [0.1],
           "phase_ms": [phase_ms], "period_ms": [period_ms],
           "_step_ms": step_ms, "now": 0,
           "crossfade_ns": 0, "fade_started": [0],
           "fade_progress": lambda i, now: 1.0,
           "pixel_groups": [(Grp(), 0, 1)]}
    exec(CURVE_SRC, env)
    exec(WRITE, env); exec(PAINT, env); exec(func_src("lerp_rgb"), env)
    exec(RENDER, env)
    return env["phase_ms"][0], len(seen)


worst = 0
for step in (7, 50, 99, 100, 101, 150, 260, 300, 1000, 25_000):
    for start in (0, 1, 60, STALL_PERIOD_MS - 1):
        try:
            p, writes = render_one_frame(step, STALL_PERIOD_MS, start)
        except IndexError as err:
            raise AssertionError(
                "a {} ms frame on a {} ms period ran the curve index off the "
                "end: {} -- in service that is caught as a tick error and "
                "counted as an I2C failure".format(
                    step, STALL_PERIOD_MS, err)) from None
        assert 0 <= p < STALL_PERIOD_MS, \
            "phase left its period: start {} + step {} -> {}".format(start, step, p)
        worst = max(worst, step)
print("    frames from 7 ms to {} ms on a {} ms period, from four starting "
      "phases: no index ran off the curve and the phase stayed in range"
      .format(worst, STALL_PERIOD_MS))

print("\nall checks passed")
