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
  live in `case/params.py` with their source named. The key field is
  three boards now -- two 4978 breakouts then the NeoKey, left to right
  -- and `firmware/code.py`'s key numbering follows the case's layout
  rather than the other way round.

## Patching files with a script

**Assert every substitution.** A bare `str.replace()` that misses returns
the string unchanged, so the edit silently does nothing and the next
command reports success on code that was never modified. `assert old in s`
before every replace, and check the assert actually fired by watching for
the confirmation print. This has bitten in `firmware/code.py` and again in
`case/webgl.py` — the second time over two spaces of indentation, which is
exactly the kind of mismatch eyes skip. Once it produced a "test passed"
for a fault that had never been injected.

**Never chain the resolution to `git add`.** A script that resolves
conflicts and a command that stages the result belong in separate calls
with a `grep -c '<<<<<<<'` between them. Joined with `;`, a script that
died on its own assertion still let `git add` and `git rebase --continue`
run, and conflict markers went into four commits of a rebase before
anyone looked. The tree at the end was correct, which is what makes it
easy to miss -- only the intermediate commits carried them.

**`git add -A` stages whoever else is in the worktree.** Two sessions
work in this one at the same time, and `git add -A && git commit` swept
up a peer's four in-progress files -- 100 lines of `firmware/code.py`
among them -- under a message describing only the case fix it was
written for. The commit was not wrong about its content, it was wrong
about *whose* content, which no diff of that commit can show you.
**Stage by explicit path, and read `git status` for files you did not
touch before committing.** The recovery is `git reset --soft HEAD~1`
followed by `git reset`, which keeps every change and hands the split
back; do it before anything is pushed and it costs one round.

**Restore from a copy, never from git.** `git checkout -- <file>` after
an injection restores the *committed* file, so any uncommitted work in it
is gone -- which is how a session lost a finished `case/params.py` while
tidying up a fault it had just proved. Either commit before injecting, so
git really is the backup, or copy the file aside and copy it back. The
reverse substitution works too and has the advantage of asserting.

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
- **A green check is not evidence.** Everything below was green in
  `build.py` while the fault was real, and they are one lesson wearing
  five faces: what the check could not see. Each carries the number it
  was watched failing at, because a guard nobody has seen go red is not
  a guard.

  **1 — The stand-in was told the wrong thing.** All three boards had a
  component face invented rather than read. The hot-swap socket was one
  10.9 x 5.9 box and is a body *plus a solder wing off each end*, 15.9
  across, and the wings are what a column runs into. The NeoKey had its
  sockets and receptacles and nothing else -- 52 parts missing. The QT
  Py's underside was one hand-written box with **24 of its 40 solids
  outside it**. Two more shapes of the same thing: parts placed on the
  wrong face (the STEP draws the switch on -z, the case puts it up, so
  the component face mirrors left to right), and orientation decided
  *per feature* instead of per board, which contradicted itself for six
  rounds until `BOARD_FLIP_X`/`BOARD_FLIP_Y` became the single fact.
  And the deepest part is never the one you remember: `SOCKET_CLEARANCE`
  reasoned from the socket's 1.85 while a STEMMA receptacle hangs 2.96,
  and the printed case closed on a NeoKey pressed 0.16 into the plate.

  So every board's face is now a table generated from its STEP --
  `BREAKOUT_BACK_PARTS`, `NEOKEY_BACK_PARTS`, `QTPY_UNDER_PARTS` --
  mirrored once through `_face_flip` on the way into case space, and
  written as the file writes them so they can be checked against it.
  Watched to fail: the old supports against the real socket 15.659 mm³,
  a pad left on the pre-mirror side 1.672 mm³, and a rail moved onto a
  QT Py component 0.014 mm³ where the old box stayed at 0.000.

  **2 — Nothing was measuring it.** An M3 post landed on a Qwiic plug
  while the margin meant to prevent that read green, because it measured
  to the board edge and the plug stands past it. Worse, a *sentence* can
  stand in for a check: "a mated plug stands 2.50 proud and a butted
  breakout's switch body starts 2.525 -- 0.025, the tolerance" held in
  three files for weeks. The plug hangs below the board and the switch
  stands above it, so that pair was never in the same space. **A number
  borrowed from a sentence that is true does not bring the truth with
  it** -- 0.025 is right where it was written, about a standoff and a
  switch, and it was carried across a Z boundary it does not cross.
  Booleaned, that plug clears everything at 0.000 mm³; moved +10.03 in y
  onto the socket wing the same probe reports 1.198. Arithmetic guards
  are worth having and are not evidence; prose is not even a guard.

  **3 — The question has a shape the check cannot take.** Interference
  asks what two solids *share*, so a cut is invisible to it in both
  directions: a feature standing over a trench and a membrane left under
  one both report 0.000 forever. The wire channel ran across both screw
  positions, leaving 0.20 of plate spanning the counterbore -- one layer,
  over the bore, under the seat the screw head bears on -- with 0.45 of
  the shell's post on air beside it.

  The twin of an interference check is a **subtraction against the volume
  the part is required to fill**: `_head_seat_probe()` builds the ring the
  head bears on and subtracts the plate from it, watched failing at
  0.790 mm³. Plan-view floors sit beside it for the distance a boolean
  cannot report (-0.455 to the screws, 0.005 to the columns).

  **And the subtraction has its own blind spot**, which is the next place
  to get this wrong: material that is present but *thin*. The feet's
  recesses come up 0.50 under a channel going down 1.20, so 0.70 of plate
  spans an Ø8.00 pocket -- the required-volume probe reports 0.000 and
  means nothing, and only a thickness says anything (watched failing at
  0.200 with `FOOT_RECESS` doubled). Reaching for the check that worked
  last time is the same disease as trusting the arithmetic one, a level
  up.

  **4 — The feature is not in the part.** A cut placed inside a void does
  nothing: a chamfer written below the counterbore top would have printed
  two identical coupon rows while the experiment concluded that
  chamfering does not help. And a feature added before a trim is deleted
  by it: a skirt below `Z_FLOOR` was removed on every build for three
  rounds by `shell()`'s closing `part = part & outer`. Both times the
  part was valid, the checks passed and the render looked right. A check
  asks whether the part is valid; it cannot ask whether it is the part
  you meant. **When a feature is meant to change a shape, measure the
  shape** -- a probe asking two rows to disagree at a stated height, or a
  volume before and after (the pad pocket removes 27.80 mm³, the sliver
  beside it 2.76).

  **5 — The check drifted off the geometry.** Two shapes. Positioned
  *from the thing it measures*: the coupon's clearance label sits 1.00
  from the counterbore rim, so a margin on that gap read 1.000 forever
  and could never go red; what replaced it measures whether the label
  still lands on the pad, failing at -4.327 with `LABEL_SIZE` at 12.0.
  And measuring a feature *that no longer exists*: "board columns inside
  the cavity" used `COLUMN_DIA` for every column after the field pads got
  their own smaller one. **Whenever a constant stops being the only one
  of its kind, grep the checks for it.**
- **Prove a check fires before trusting it**, and **inject the fault by
  moving geometry, not by shrinking it to nothing.** A zero-width `Box`
  makes OCCT throw, so the build dies before the check runs and the test
  proves nothing. Injections also have to isolate one thing: growing
  `QTPY_LIP` to reach a button grew its height too and tripped a
  different check. Moving a feature 60 mm sideways, or setting one
  diameter past its limit, keeps the fault where it was aimed. Restore
  from a copy, never from git.

  This rule exists because of the standoff: its diameter was cut on the
  stated grounds that the check had flagged it, and it never had -- the
  0.009 mm³ came from the plate-hole corner. **A credited catch that
  never happened is worse than no catch**, because it launders the
  reasoning that came with it.

  Watched-to-fail so far: cable notch 28.4 mm³, rail over a button
  68.9 mm³, standoff at Ø6.0 1.016 mm³, USB opening narrowed 3.8 mm³, a
  breakout support column back onto its second hole 5.675 mm³, seam
  standoffs shifted half a pitch onto the switches 26.260 mm³, breakout
  pegs grown to `COLUMN_DIA` 64.796 mm³, the wire channel over the screws
  -0.455 and the columns 0.005, the head seat 0.790 mm³, the plate under
  the channel 0.200, and a column against a board's components 0.141 at
  `FIELD_SUPPORT_DIA` 3.50 and 0.191 at 3.40.
- **A sweep can only answer a question the mechanism can answer.** The
  seam got a snap -- barbs on the shell's skirt into a groove round the
  plate's tongue -- and a coupon sweeping the barb 0.30 to 0.70. All four
  came back too weak, which reads as "sweep higher" and is not: the skirt
  is 0.90 thick over a 1.20 free length, so even the shallowest hook asks
  it for **19% surface strain where PLA yields near 2**. It never bent;
  it was forced, which is why it fought going on and held nothing after.
  A cantilever deflecting 0.40 inside 2% wants about 5 mm and the plate
  is 2.40 thick, so no hook works and a taller sweep only finds a stiffer
  press fit. **Two lines of beam arithmetic before the print would have
  said so.** The snap is gone; the step aligns the halves and hides the
  gap, which was the original complaint, and the next thing to try if the
  centre lifts is a magnet pair rather than a plastic spring. A third
  screw at mid-span is out for its own reason -- the boards fill the case
  wall to wall there, 0.200 against the 5.60 a post needs, which is why
  there are two screws and not three.
- **Measure before fixing, not after.** Two faults in one afternoon came
  from believing a diagnosis and acting on it. The viewer's elevation was
  clamped 0.0011 rad short of the pole with a comment saying the view
  matrix collapsed there; it does not, and running the old and new side
  by side gave *identical* numbers -- the residual in `Math.cos(PI/2)`
  carries the right direction and the normalise recovers a unit vector
  from it. Then the quaternion composition order was derived on paper and
  was wrong the other way. Both were caught by a measurement that took
  one call, after a rewrite that did not need to happen. **A comment
  saying something is broken is a claim, not a finding.**
- **Two places that derive the same edge will disagree.** The QT Py rail
  starts at a clamped 14.714 and the pocket cut into it was written as a
  fixed offset from the pad row, 14.910 -- 0.196 apart, under half an
  extrusion, a hair rather than a wall. Nothing related the two numbers.
  `_clear_strips()` is the one place the clamp happens now and the cut
  takes its edge from there, so the sliver cannot exist at any value.
- **A case-space constant describes one layout.** `WIRE_LANE_Y` was a
  pair of case-space numbers off an `inline` scan. `stacked` seats the
  field 0.805 further back, so the same trench went 0.400 into a NeoKey
  column there while `inline` stayed green -- the fault living in the
  layout nobody prints, which is how it would have kept. Anything
  positioned relative to the boards belongs board-local with
  `FIELD_ORIGIN` applied once; the tell is the margin coming out
  identical in both layouts.
- **A diff cannot show a contradiction**, because a contradiction is a
  relationship between two places and a diff shows one. This section once
  introduced the pilot mouth as derived from `SCREW_CLEAR_DIA` and, three
  paragraphs later, explained that the derivation had been broken; both
  sentences were correct in the commit that wrote them. It has since
  happened twice more -- `README.md` naming two different power taps a
  round apart, and the spec demanding a meter three sections above an
  entry saying the measurement was never needed. **When two commits a
  round apart touch the same section, review the section, not the
  diffs.** The reader who can see it is going end to end with no memory
  of which round wrote what, which is a position rather than a skill.

  The general form: **a reference is only as stable as the thing it
  points at is named.** Position is a property of the document, not of
  the fact. Every "see above" in here has been replaced by the name of
  what it means.
- **Look for the STEP before assuming there isn't one.** `BREAKOUT_T`
  sat as a documented guess -- "Adafruit publishes no STEP for this
  board" -- through a whole session, and they publish one, in the same
  `Adafruit_CAD_Parts` repository `ref/fetch.sh` already pulls the other
  two boards from. The 4978's model also turned out to be the only one of
  the three that includes its hot-swap socket, so the footprint the
  support columns dodge is measured now instead of carried over. The
  guess was right to three decimals, which is exactly why it survived:
  nothing downstream ever disagreed with it.
- **A wall can fit the board and still make the case impossible to
  wire.** Four times: both Qwiic sockets, the USB port, and the QT Py's
  pocket frame, which surrounded the board so a wire soldered to JP3 had
  nowhere to go. Every one was found by a person looking at the assembly
  or the section, never by a check -- the boards fit, so nothing was red.
  The way to ask is to lay a wire-sized box where a wire has to run and
  boolean it: 34.501 mm³ against the shell along one route, 10.240 along
  the one actually taken, 0.000 after the notch.
- **A part added to `mock.everything()` reaches four files, and three of
  them fail loudly only if you run them.** `build.py` picks the new part
  up on its own; `section.py` has its own colour table keyed by the mock's
  names and dies `KeyError`; `product.py` asserts every switch sits on the
  NeoKey and cannot survive a second board kind; `webgl.py` carries a
  hardcoded group regex and a `lift_of` dict, and a name missing from
  either shows up as a raw mesh name in the viewer's legend rather than as
  an error. Run all five after touching the mock, not just `build.py`.
- **`build.py` only rewrites the STLs and STEPs.** Every PNG in `out/`
  comes from `product.py`, `render.py` and `section.py`, so a geometry
  change leaves the figures showing the old design -- which is the worst
  kind of stale, because a finished-looking render reads as a verified
  one. The full sweep, per layout:

  ```
  MPAD_LAYOUT=<layout> .venv/bin/python build.py     # must say all checks passed
  MPAD_LAYOUT=<layout> .venv/bin/python product.py
  MPAD_LAYOUT=<layout> .venv/bin/python render.py
  MPAD_LAYOUT=<layout> .venv/bin/python section.py
  MPAD_LAYOUT=<layout> .venv/bin/python webgl.py dump
  .venv/bin/python webgl.py page                     # once, after both dumps
  ```

  **A dirty `shell.stl` after a rebuild is not evidence of anything.**
  The shell's exports are not byte-reproducible: two runs of unchanged
  source give two different files, because OCCT emits its solids in a
  different order each time. `shell.stl`, `shell.step`, `shell.png` and
  `viewer.html` all churn; `bottom.*`, `sections.png` and the coupons do
  not, which is what makes the shell look guilty. Sorting the triangle
  table shows the two meshes agreeing to 0.0, same count, same volume,
  same bounds -- that is the check to run before believing a geometry
  changed. This was first read the other way round, as a commit that had
  half-run the sweep, and written up as one; **`git status` said
  "modified" and the reasoning went downhill from there.** Rebuild,
  compare the geometry rather than the bytes, and `git checkout --
  case/out/` when it matches.

  **Run the whole sweep after every geometry fix, not at the end of a
  batch of them.** Saqoosha reads the viewer, not the diff, and a fix he
  cannot see is a fix he has to take on trust -- which during a
  back-and-forth about where a part sits is exactly the thing there is
  none of. Finish with `open -a "Google Chrome" out/viewer.html`, and say
  that the tab needs a reload.
- Print `out/<layout>/coupon.stl` before the case. `SWITCH_HOLE` is
  settled at 14.15 — a Durock Ice King seats right in it on the A1 mini
  in PLA Basic, so the 0.15 over nominal is this machine's hole shrink
  and holds until the filament or nozzle changes. Every other number it
  tests is settled too, and when the clearance row is the only question
  `out/<layout>/coupon-clear.stl` asks it in a few minutes instead.

## Checking the viewer

`out/viewer.html` is generated by `webgl.py dump` (once per layout) then
`webgl.py page`. Two ways to verify it, and both are worth doing because
they cover different halves:

- **The data half, without a browser.** Decode `geom.json`'s base64 in
  Python and check it against the parts table beside it. `count` is a
  **vertex** count, not a number of int16, so the payload holds three
  int16 per count -- getting that backwards makes a healthy page look
  like a 3x mismatch. Parts are concatenated with no offsets, so each
  `count` has to be divisible by 3 or one part draws another's triangles.
  Confirm the same payload is embedded in `viewer.html`. Quantisation is
  `max(span) / 65534`, about 0.0021-0.0025 mm here, and that is the whole
  round-trip error.
- **Regenerating the page does not refresh an open tab.** `webgl.py page`
  writes the file and nothing else; a Chrome window already showing it
  keeps the old geometry, and it looks entirely convincing. Reload after
  every regeneration -- `mcp__chrome-devtools__navigate_page` with
  `type: reload`.
- **The rendered half, in Chrome.** `mcp__chrome-devtools__*` attaches to
  a running Chrome — it needs one actually open, or it fails with
  `Could not find DevToolsActivePort`. Drive the rail with
  `evaluate_script` (`document.querySelector('#preset button[data-v=
  "top"]').click()`), screenshot, and check `list_console_messages` for
  errors. Four real rendering bugs were found this way and none of them
  raised an error, so the screenshot is the test, not the console.
  The console is not decoration either: it caught the whole viewer
  throwing before it drew anything, because the state block sets the
  opening camera and sat above helpers declared as `const` arrows -- a
  temporal dead zone. They are function declarations for that reason.
- **The page had no doctype and rendered in quirks mode from the day it
  was written.** Every dimension tuned in that rail was tuned against the
  old box model. `document.compatMode` reads `CSS1Compat` now; check it
  after any change to the head.
- **The camera is a quaternion, not two angles**, because two angles lose
  a degree of freedom at the poles. Drags rotate it about the camera's
  own axes and the increment goes on the **right** of the product --
  `qBasis` returns the world-to-camera rows, which is its transpose, so
  composing on the left applies the drag in world space and a horizontal
  drag from the front turns the model about the wrong axis. Both were
  settled by measuring which world axis the model turns about and
  comparing against the turntable this replaced: right-drag [0,0,1],
  down-drag [1,0,0]. A thousand steps over the pole leave the basis unit
  to 8.9e-16, and the view direction moves at least 0.0364 every step --
  against the old clamp it was exactly 0.

## Remaining on the case

`inline` is the layout that exists as a physical object; `stacked` has
never been printed. **The reasoning behind every settled number is in
`case/README.md`** -- this is the state, not the story.

Settled on real parts: `SWITCH_HOLE` 14.15, `PEG_DIA` 2.30, `QTPY_SLOP`
0.40, the USB-C opening, `PILOT_DIA` 2.95 with a Ø3.40 x 0.60 lead-in,
and `SCREW_CLEAR_DIA` 3.70 with `CLEAR_CHAMFER` 0.60. The assembled
six-key unit added two the model could not have: a breakout needs no
locating peg (a plate-mount switch clips to the top plate and its pins
go into the board's socket, so the switch ties the two together), and
the field's outer edge has no seam to press on, which is what
`EDGE_RIB_W` is for.

**The six-key `inline` case is printed, assembled and closing**, at
13.33 with 4.36 under the boards, an 11.20 wire channel, 3.00 field pads
and the QT Py's pad pockets and wire notch. The wires have room. The one
change since that print is the pad pocket running off the near end, which
removes a rail stub the wires were bending round; it needs no reprint.

Open:

- `QTPY_STEMMA_NOTCH` at 1.00 works but the Qwiic plug takes some
  working at; a reprint would want 1.5-2.0.
- The Ø8 feet sit under the wire channel and leave 0.70 of plate over
  their recesses. Nothing moves -- a Ø8 foot at y ±5.99 in a 25.99 case
  cannot clear a channel reaching ±5.60, and the feet are where they are
  so it does not rock -- so the number is the answer and
  `plate left under the wire channel` holds it.


## Editing the firmware

- **The keypad is two halves and the index space is one.** Keys 0-1 are
  two 4978 breakouts on GPIO, keys 2-5 a NeoKey on I2C, and `GPIO_BASE`
  / `SEESAW_BASE` are the only two constants that know which way round.
  Indices are static: key 2 stays key 2 when the NeoKey is silent,
  because the host maps index to pane and a silent renumbering focuses
  the wrong session. That is also why `NUM_KEYS` is a constant 6 and
  `HELLO <ver> 0` can no longer happen.
- **One line is the whole four-key build.** Empty `GPIO_KEY_PIN_NAMES`
  and `SEESAW_BASE` falls to 0, `NUM_KEYS` to 4, and the GPIO setup is
  skipped whole -- the NeoKey goes back to being keys 0-3. There is
  deliberately no autodetection: an absent breakout is electrically
  identical to a present one nobody is pressing, pulled high either way,
  with no readback on the pixel line and no capacitive sense on an
  RP2040. Any automatic answer would be a guess, and a wrong guess
  renumbers every key silently -- the one failure this file is built to
  prevent. Flashing is one file copy, so the person doing the copy is
  the only honest source of truth. The guard around the setup is not
  cosmetic: `NeoPixel(pin, 0)` would either raise, giving a four-key
  board an `ERR gpio pixels` on every connect forever about hardware it
  never had, or leave an empty group nobody writes to.
- **A dead NeoKey costs exactly four keys. A dead *cable* costs all
  six.** The GPIO reads sit outside every guard and each pad's
  `get_keys()` and each pixel group's `show()` is guarded separately, so
  every I2C fault that leaves the cable plugged in -- a missing library,
  a wrong address, a seesaw that stops answering -- costs only the four
  keys behind it, and collapsing those back into one `try` would take
  the other two down with it. The cable is the exception, and it is a
  wiring fact rather than a firmware one: the built unit takes the
  breakouts' `VDD` and `GND` off the NeoKey's `JP1`/`JP5` header, which
  is the incoming Qwiic rail, so unplugging it removes their power *and*
  their ground reference. The pixels go dark, `SWITCHA` floats high
  through its pull-up, and keys 0 and 1 report as never pressed. The
  device stays up and still says `HELLO 3 6`. That was traded knowingly,
  for two fewer wires through the one 4.8 mm lane under the boards, and
  it is the single place where the wiring promises less than the
  firmware does.
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
  the USB drive unless one of the six keys is held through a
  hard reset, because a mounted volume yanked off the bus is a macOS
  "Disk Not Ejected Properly" every single unplug. Hold a key and the
  drive comes back — and stays for the rest of the session, so an
  edit-and-copy loop needs the finger only once. `disable_usb_drive()`
  sits on exactly one path, a completed read that saw no key held, so
  every other outcome leaves the drive enabled and a board too broken to
  read its own keypad is still one you can copy files to. Read
  `boot_out.txt` **from the REPL**, not off the drive: mounting the
  drive is what makes the gate take the other branch and overwrite the
  line you came for.
- `boot.py` depends on `adafruit_neokey` in `lib/`, which used to be
  `code.py`'s alone, and holds its own copy of the `0x30` from
  `PAD_ADDRESSES` **and of the GPIO pin names** — it cannot import
  `code.py` without running the whole program. The address and the
  library fail in the harmless direction: the drive stays enabled. The
  pin names have a second failure mode worth naming, because it is
  silent: a name that still exists but points at the wrong pin reads
  high through its pull-up, so keys 0-1 quietly stop opening the drive
  while the NeoKey's four still do.

  That copy is also why **"one line switches the build" is true of
  `code.py` and not of `boot.py`.** Emptying `GPIO_KEY_PIN_NAMES` gives
  a four-key firmware; `boot.py` goes on reading `MISO` and `SCK`
  regardless, and on a board with no breakouts they read high through
  their pull-ups, so the gate falls through to the I2C path and behaves
  correctly. Left alone on purpose: deriving one file's constants from
  the other is the import that cannot happen, and the cost of the
  asymmetry is two pin reads that always say "not held".
- `lib/` needs `neopixel.mpy` as well now, for the breakouts' chain.
  Missing, keys 0-1 report presses and never light, and the host is told
  `ERR gpio pixels ...`.
- Deploy by copying to `/Volumes/CIRCUITPY/`, then `rm` the `._*`
  AppleDouble files macOS leaves behind.

## Verifying a change

```
python3 -m py_compile firmware/*.py tools/mpad.py
# CIRCUITPY is not mounted unless a key was held through the last hard
# reset. Hold one and replug before the copy.
cp firmware/code.py /Volumes/CIRCUITPY/ && rm -f /Volumes/CIRCUITPY/._code.py
tools/mpad.py --probe          # expect: PONG 3 6 on the data port
tools/mpad.py --demo           # LEDs out, key edges in
```

A `boot.py` change needs more than that, and the shape of the mistake is
that it looks like it does not: copying `code.py` triggers auto-reload,
which is a **soft** reset, so an edited `boot.py` sitting on the drive
never runs and the probe above reports a healthy board that is still on
the old USB config.

```
cp firmware/boot.py /Volumes/CIRCUITPY/ && rm -f /Volumes/CIRCUITPY/._boot.py
# hard reset -- replug, or from the REPL on the console port:
#   import microcontroller; microcontroller.reset()
tools/mpad.py --probe          # expect: PONG 3 6, and CIRCUITPY now gone
```

Known-good answers, for telling a healthy board from a sick one:

| State | The device says |
|---|---|
| healthy | `HELLO 3 6` on connect, `PONG 3 6` to `P` |
| NeoKey or `adafruit_neokey` missing | `HELLO 3 6` + `ERR i2c setup ...`, keys 2-5 dark, connection held, and `CIRCUITPY` back (the gate failed open on the same fault) |
| `neopixel` missing | `HELLO 3 6` + `ERR gpio pixels ...`, keys 0-1 dark but still reporting presses |
| bus lost while running, cable still in | `HELLO 3 6` + `ERR i2c lost at runtime: ...`, keys 0-1 unaffected |
| Qwiic cable unplugged | `HELLO 3 6` + `ERR i2c lost at runtime: ...`, and keys 0-1 dark and stuck unpressed — they draw `VDD` and `GND` off the NeoKey, so the cable carries their power too |
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

Two more things the REPL will not give you. `code.py`'s globals are
**gone** by the time the prompt appears — `print(len(pads))` after an
interrupt is a `NameError`, not a peek at the running program, so the
REPL cannot be used to inspect state the firmware built. And anything
`code.py` prints at startup is emitted before a host can reattach after
a reset, so it is simply dropped: watching the console for a boot-time
message is not a test, it is a coin flip that lands tails every time.
Read the state off the **data** port instead, where `HELLO`'s key count
answers the same questions and is there whenever you connect.

With the drive disabled, `storage.remount("/", readonly=False)` from the
REPL is the only way to change a file. Do it the paranoid way, because
a truncated `boot.py` costs you USB itself: write the new content to a
*second* name, read it back and check it, then `os.rename` the original
aside and the new one into place. The original is then one rename from
being restored, which beats every other recovery path on this device.

Canopy holds the data port whenever it is running, and takes it back on
its own after a reset — a probe that answered a minute ago can come back
`console/silent (no PONG)` on **both** ports with nothing wrong at all.
`lsof /dev/cu.usbmodem*` is the first thing to check, before suspecting
the firmware; `log show` is not worth the trouble. Only one process can
usefully own the port, so release yours before asking Canopy to connect.
Flashing while it is held works — the copy is mass storage, not serial,
assuming a key was held for that boot — but the soft reset that follows
drops Canopy's connection.

## Error paths are only real once you have broken them

Every hardening path in this firmware was wrong the first time, and none
of the mistakes were visible by reading. The method that found them:
copy `firmware/code.py`, inject a `raise` where the fault belongs, flash
the copy, watch, restore. Four separate guards were proven this way —
the fatal handler (both sides of its 60 s brake), the setup guard (by
`mv`-ing `lib/adafruit_neokey` aside), the runtime I2C latch, and
`boot.py`'s drive gate.

The drive gate's watched-to-fire faults, both read out of `boot_out.txt`
with the drive confirmed mounted afterwards:

```
addr=0x30 -> 0x31   usb drive: enabled (gate failed: ValueError: No I2C device at address: 0x31)
mv lib/adafruit_neokey aside   usb drive: enabled (gate failed: ImportError: no module named 'adafruit_neokey')
```

Three of those tests failed *as tests* before they failed as code: one
patched nothing because a `replace()` missed, one landed on the boundary
of its own fault window, and one asked a question the harness could not
answer. **A passing error-path test that was never actually triggered is
the default outcome, not the exception.** Make the injected fault prove
itself — print from inside it, or assert the symptom appears — before
believing a clean run.

**Run the negative control or the test is worth nothing.** Proving the
gate did not strand the I2C bus meant showing `code.py` still answered
`HELLO 3 4` with the fault active — four keys, at the time. The first
harness watched the console for `code.py`'s `WARNING: no keypad on I2C`
line and reported it absent —
which looked like a pass, and was not: with the library actually moved
aside, so that the warning *had* to appear, it stayed absent too. The
harness was reattaching after the print had already been emitted and
dropped. Every "the bad thing did not happen" result needs its twin run
where the bad thing is forced to happen. Here that meant reading the key
count off the data port instead, where the count was observable in both
directions and so a healthy answer meant something. **That trick no
longer works.** The count is a constant 6 now, because the GPIO half
cannot fail to enumerate, so the observable signal is the `ERR i2c ...`
line itself rather than the number beside `HELLO`.

Canopy holding the data port defeats a probe, which reads exactly like a
dead board. Beat it by resetting through the console REPL, waiting for
the console device node to actually **disappear**, then hammering both
ports until one answers `HELLO`/`PONG` — Canopy reconnects fast, but not
instantly.

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

One diagnostic *was* added, and the grounds matter because they are the
inverse of the list above: `ERR gpio <detail>` on connect, when the
breakouts' pins or `neopixel` failed to come up. It is not a new class of
noise -- it is the exact twin of `ERR i2c ...`, emitted once at the same
moment, for the half of the keypad that had no way to report anything.
Without it a missing `neopixel.mpy` is two dark keys and no explanation.
There is no runtime twin of it: a bus can be unplugged mid-session, a
soldered pin cannot.

If one of these is proposed again, the question to answer first is what
state the new behaviour would be *wrong* in. Every one of them has one.
