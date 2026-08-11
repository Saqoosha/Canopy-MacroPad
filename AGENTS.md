# Canopy MacroPad — working notes

Device half of the Canopy MacroPad. The macOS half is in the `Canopy`
repo under `Sources/Canopy/MacroPad/`.

`README.md` is the reference and stays that way — protocol, status
colors, bring-up steps, and the bench measurements behind every constant.
Read it before changing anything in `firmware/`. This file only carries
what the README does not.

## Layout

- `firmware/boot.py` — USB config. Runs only on a **hard** reset, which
  is also the only thing that re-enumerates USB. Saving the file is a
  soft reset and does nothing.
- `firmware/code.py` — the whole program. CircuitPython runs it top-level;
  nothing imports it, and CPython idioms (dataclasses, typing, logging,
  pytest) are unavailable or too costly on an RP2040.
- `tools/mpad.py` — host-side bring-up console. Stdlib only, deliberately,
  so it runs on a fresh machine. `--probe` first, always.
- `docs/canopy-macropad-handoff.md` — the original design brief, vendored
  verbatim. Not edited here.
- `case/` — the printed enclosure, parametric in `build123d`. Its own
  `README.md` carries the stack, the print settings and the assembly
  order. Nothing in `firmware/` depends on it and it depends on nothing
  in `firmware/`; the only shared facts are board dimensions, and those
  live in `case/params.py` with their source named.

## Patching files with a script

**Assert every substitution.** A bare `str.replace()` that misses returns
the string unchanged, so the edit silently does nothing and the next
command reports success on code that was never modified. `assert old in s`
before every replace, and check the assert actually fired by watching for
the confirmation print. This has bitten in `firmware/code.py` and again in
`case/webgl.py` — the second time over two spaces of indentation, which is
exactly the kind of mismatch eyes skip. Once it produced a "test passed"
for a fault that had never been injected.

## Editing the case

Environment is a venv at `case/.venv`, Python 3.12 (`uv venv --python
3.12 .venv`, then `uv pip install build123d trimesh matplotlib`). The
system Python is 3.14 and has no build123d; whether that is a wheel gap
or just a missing install was never checked, so 3.12 is the known-good
one, not necessarily the only one.

- **Two layouts come out of the same source**, selected with
  `MPAD_LAYOUT=stacked|inline`, and each writes to `out/<layout>/`. A
  change is not done until **both** build clean — they share every part
  of the geometry except where the QT Py sits, so a "small" edit reaches
  further than it looks.
- **Change a number in `params.py`, never the geometry in `parts.py`.**
  Every dimension that matters is derived, so a hand-edit to a part is a
  number that stops agreeing with the rest of the model silently. Board
  centres in particular: hard-coding the NeoKey's at `x = 0` is right in
  one layout and 13 mm wrong in the other, and it was wrong in two files
  before `NEOKEY_CENTER` existed.
- **`build.py` must end in `all checks passed` before anything is
  printed.** It booleans both printed parts against stand-ins for the
  boards, the switches and every mated connector, and against each other.
  The full list of what it has caught lives in `case/README.md`; the one
  worth carrying around is that **a connector is not the thing that has
  to fit — the mated plug is.** A wall can clear a socket perfectly and
  still seal it off, or leave a port a millimetre short of seating. That
  same shape of mistake happened four times, on both Qwiic sockets and
  the USB-C port, and every stand-in models plugs because of it.
- **A margin check is not a boolean.** The M3 post landed on the Qwiic
  plug while the margin that existed to prevent exactly that read green,
  because it measured to the board edge and the plug sticks out past it.
  Arithmetic guards are worth having and are not evidence; the boolean
  is the evidence.
- **Prove a check fires before trusting it**, and **inject the fault by
  moving geometry, not by shrinking it to nothing.** A zero-width `Box`
  makes OCCT throw, so the build dies before the check ever runs and the
  test proves nothing. Injections also have to isolate one thing: growing
  `QTPY_LIP` to reach a button grew its height too and tripped a
  different check entirely. Moving the feature 60 mm sideways, or setting
  one diameter past its limit, keeps the fault where it was aimed.
  Watched-to-fail numbers so far: cable notch 28.4 mm³, rail over a
  button 68.9 mm³, standoff at Ø6.0 1.016 mm³, USB opening narrowed
  3.8 mm³.
- **The standoff story is the reason for the rule above.** Its diameter
  was cut on the stated grounds that the check had flagged it, and it
  never had — the 0.009 mm³ came from the plate-hole corner instead. A
  check nobody has watched fail proves nothing, and a *credited* catch
  that never happened is worse, because it launders the reasoning that
  came with it.
- Print `out/<layout>/coupon.stl` before the case. `SWITCH_HOLE` is
  settled at 14.15 — a Durock Ice King seats right in it on the A1 mini
  in PLA Basic, so the 0.15 over nominal is this machine's hole shrink
  and holds until the filament or nozzle changes. `PILOT_DIA` (2.50) is
  still a guess until an M3 has actually been driven into a post.

## Checking the viewer

`out/viewer.html` is generated by `webgl.py dump` (once per layout) then
`webgl.py page`. Two ways to verify it, and both are worth doing because
they cover different halves:

- **The data half, without a browser.** Decode the base64 back out of the
  page in Python and compare bounds, vertex count and part offsets
  against `out/<layout>/geom.json`. Round-trip error should be 0.0000 mm
  and every part offset divisible by 3, or a part draws another's
  triangles.
- **The rendered half, in Chrome.** `mcp__chrome-devtools__*` attaches to
  a running Chrome — it needs one actually open, or it fails with
  `Could not find DevToolsActivePort`. Drive the rail with
  `evaluate_script` (`document.querySelector('#preset button[data-v=
  "top"]').click()`), screenshot, and check `list_console_messages` for
  errors. Four real rendering bugs were found this way and none of them
  raised an error, so the screenshot is the test, not the console.

## Remaining on the case

The `inline` case is printed and mostly proven on the real part. Settled
by assembly: `SWITCH_HOLE` at 14.15 (a Durock Ice King seats right),
`PEG_DIA` at 2.30 (the NeoKey drops on free with a little play),
`QTPY_SLOP` at 0.40, and the USB-C port -- a real cable seats fully with
about 1 mm around its housing, which matters because `USB_PLUG_W/H` were
never measured off anything, just chosen generously.

Still open: **`PILOT_DIA` (2.50) has never had an M3 driven into it.**
That is the last guess in the file, and the one that fails destructively
-- too small splits a post, too large strips on the second open. Also
noted: the Qwiic plug goes into the `inline` pocket but takes some
working at, which is `QTPY_STEMMA_NOTCH` at 1.00 and would want 1.5-2.0
on a reprint. `stacked` has not been printed at all.

## Editing the firmware

- **The device is dumb on purpose.** It reports key edges and paints what
  it is told. Which pane, which status, when to pulse — all host-side.
  Resist moving policy down here; the split is what keeps the protocol
  portable to BLE.
- **An uncaught exception is indistinguishable from a dead board.**
  CircuitPython drops to the REPL, the data port goes silent, and the
  LEDs freeze at their last value. Every I2C touch in the main loop is
  inside a guard for exactly this reason. Keep it that way.
- **Never touch `time.monotonic()`.** It is a float whose precision
  decays with uptime, and this device lives plugged in for weeks. All
  timing is integer `monotonic_ns`.
- **`/Volumes/CIRCUITPY` is not there by default.** `boot.py` disables
  the USB drive unless a key is held while the device boots, because a
  mounted volume yanked off the bus is a macOS "Disk Not Ejected
  Properly" every single unplug. Hold any key while plugging in and the
  drive comes back; the deploy is otherwise unchanged. Every failure of
  that check — no cable, no lib, no answer — leaves the drive enabled, so
  a board too broken to read its own keypad is still one you can copy
  files to. `boot_out.txt` records which branch ran.
- Deploy by copying to `/Volumes/CIRCUITPY/`, then `rm` the `._*`
  AppleDouble files macOS leaves behind.

## Verifying a change

```
python3 -m py_compile firmware/*.py tools/mpad.py
# hold any key while plugging in, or CIRCUITPY will not be mounted
cp firmware/code.py /Volumes/CIRCUITPY/ && rm -f /Volumes/CIRCUITPY/._code.py
tools/mpad.py --probe          # expect: PONG 3 4 on the data port
tools/mpad.py --demo           # LEDs out, key edges in
```

Known-good answers, for telling a healthy board from a sick one:

| State | The device says |
|---|---|
| healthy | `HELLO 3 4` on connect, `PONG 3 4` to `P` |
| keypad or `lib/` missing | `HELLO 3 0` + `ERR i2c setup ...`, connection held |
| bus lost while running | `HELLO 3 4` + `ERR i2c lost at runtime: ...` |
| firmware died past 60 s uptime | `ERR fatal ...`, all keys red, port drops, fresh `HELLO` |
| firmware died inside 60 s | `ERR fatal-halted ...` on every later connect, stays red |

USB identity: VID `0x239A`, PID `0x80F8`, product `Canopy MacroPad`,
manufacturer `Saqoosha`. Two ports enumerate; **never pick by trailing
number** — only `P` → `PONG` identifies the data port, because the
console echoes `P` as REPL input and never answers.

Tracebacks land on the **console** port, never the data port. Read them
by interrupting the REPL there (`\x03`) and reloading (`\x04`).

`\x03` alone does not reach a prompt. It stops `code.py` and prints
*"Press any key to enter the REPL"*, and that next key is consumed
opening the prompt — so a command written immediately after the
interrupt has its first character eaten and the rest goes nowhere,
silently. A script driving the REPL must send a newline and **wait to
actually see `>>>`** before sending anything that has to run. This cost
one wasted reset that reported success on a board that had never
rebooted.

Canopy holds the data port whenever it is running. Only one process can
usefully own it — release yours before asking Canopy to connect, and
`lsof` beats `log show` for finding out who has it. Flashing while it is
held works (the copy is mass storage, not serial), but the soft reset
that follows drops Canopy's connection.

## Error paths are only real once you have broken them

Every hardening path in this firmware was wrong the first time, and none
of the mistakes were visible by reading. The method that found them:
copy `firmware/code.py`, inject a `raise` where the fault belongs, flash
the copy, watch, restore. Three separate guards were proven this way —
the fatal handler (both sides of its 60 s brake), the setup guard (by
`mv`-ing `lib/adafruit_neokey` aside), and the runtime I2C latch.

Two of those tests failed *as tests* before they failed as code: one
patched nothing because a `replace()` missed, and one landed on the
boundary of its own fault window. **A passing error-path test that was
never actually triggered is the default outcome, not the exception.**
Make the injected fault prove itself — print from inside it, or assert
the symptom appears — before believing a clean run.

For a receive-path change, the decisive check is a burst larger than
`MAX_LINE_BYTES` ending in `P`: if the buffer bound is wrong, the `P`
is eaten with it and no `PONG` comes back. 441 and 881 bytes both work.

## Diagnostics that were deliberately not added

Reviewers keep proposing the same six, and they were declined on the
same grounds each time: each buys a rare diagnosis by making the device
say more all the time, and this pad works because it says very little —
the same reasoning that keeps exactly one status pulsing.

- `ERR i2c lost` / `ERR i2c ok` mid-session — a one-second cable wobble
  would announce the keypad as gone when it is not. (The *stale* half of
  this was a real bug and is fixed: `i2c_error` is live, so a reconnect
  after a bus loss reports the truth.)
- `ERR argc <cmd>` split from `ERR unknown <cmd>` — hosts read any
  `ERR unknown` as "verb unsupported"; a new code changes what they parse.
- `ERR line-too-long` on the receive bound — every pre-`HELLO` overrun
  would draw an error the host is told to ignore.
- A reset counter in `microcontroller.nvm` to brake a slow reset loop —
  wears NVM on every fault, and Canopy already detects `HELLO` storms.
- Placeholder pads to keep key indices aligned when one of two boards
  fails — changes what `HELLO`'s key count means, and no host implements
  the distinction.
- `usb_midi.disable()` in `boot.py` — builds without the module raise
  `AttributeError` there and break USB entirely, to defend against an
  interface the measured descriptor already lacks.

If one of these is proposed again, the question to answer first is what
state the new behaviour would be *wrong* in. Every one of them has one.
