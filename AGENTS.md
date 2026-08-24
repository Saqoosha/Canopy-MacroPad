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
- `pcb/` — the custom board: EasyEDA-side scripting in its own
  `README.md`, and what to do with the fabricated article in `BRINGUP.md`.
- `case/` — the printed enclosure, parametric in `build123d`. Its own
  `README.md` carries the stack, the print settings and the assembly
  order. Nothing in `firmware/` depends on it and it depends on nothing
  in `firmware/`.

  Board dimensions are the shared fact, and `case/params.py` now **loads
  `pcb/params.py` by path** rather than restating them, so there is one
  source rather than two that agree until they do not. The key field is
  one board -- the custom PCB, six Choc sockets on 19.05 -- and both the
  case and `firmware/code.py`'s key numbering follow it. The older
  `stacked` and `inline` layouts are gone from the source; the
  directories of the same names under `case/out/` are their leftovers.

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

**In a worktree, use absolute paths for everything.** The shell's working
directory resets to the repository root between commands, so a relative
path written while "in" `.claude/worktrees/<name>/` silently addresses the
*other* checkout -- and because `firmware/code.py`, `tools/mpad.py` and
`AGENTS.md` all exist in both, nothing errors. It reads as success. One
session did it three times in an afternoon, each worse than the last: it
read the main checkout's `code.py` and designed a port against a file that
had already been ported; it then flashed that same wrong `code.py` to a
board and read the old firmware's console output as the new firmware's
test result; and it ran `py_compile` on the unedited copy and reported
"compiles" for a change that was somewhere else entirely. **The third one
is the shape to fear** -- not a broken command, a green one, standing in
for a check that never ran.

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
- **A stand-in is only as true as what it was told, and the boolean
  cannot tell you otherwise.** The first assembled six-key unit found
  four separate versions of this in one afternoon, every one of them
  green in `build.py` beforehand:
  - **Summarised by hand.** The hot-swap socket was drawn as one
    10.9 x 5.9 box. It is a body *plus a solder wing off each end*, 15.9
    across, and the wings are what a column runs into -- the summary took
    the biggest of three solids and dropped the rest. The reverse-mount
    NeoPixel and the diode were not in it at all.
  - **On the wrong face.** The STEP draws the switch on -z and the case
    puts the switch side up, so the board is turned over and its
    component face **mirrors left to right**. The z flip was implicit in
    placing parts below the board; the in-plane one was missing.
  - **Feature by feature instead of board by board.** Which way a board
    sits is *one* fact. It was decided separately for the socket, the
    components and the STEMMA receptacles, each time to satisfy the last
    thing someone had pointed at, and the three answers contradicted each
    other for six rounds. `BOARD_FLIP_X`/`BOARD_FLIP_Y` are that one fact
    now and everything derives from them.
  - **The deepest part is not the one you remember.** `SOCKET_CLEARANCE`
    was a hand-written 2.80 whose comment reasoned from the socket's
    1.85. The deepest thing under a board is the STEMMA receptacle at
    2.96 -- modelled on the far side, so nothing had to clear it. The
    printed case closes on a NeoKey pressed into the bottom plate by
    0.16, which is too little to feel and was enough to strain the boards.
    It is `UNDER_BOARD_MAX + 0.40` now.

  So: `BREAKOUT_BACK_PARTS` is every part on that face as boxes out of
  the STEP, mirrored once on the way into case space, and the tables
  still read as the file does so they can be checked against it. Watched
  to fail: the old supports against the real shape 15.659 mm³, the third
  pad left on the old side 1.672 mm³.
- **A margin check is not a boolean**, and neither is a sentence. The M3
  post landed on the Qwiic plug while the margin that existed to prevent
  exactly that read green, because it measured to the board edge and the
  plug sticks out past it. Worse, because nothing at all was measuring
  it: the reason the breakouts go left was written as "a mated plug
  stands 2.50 proud and a butted breakout's switch body starts 2.525 --
  0.025, which is the tolerance", and it stood in three files for weeks.
  The plug hangs *below* the board and the switch stands *above* it, so
  that pair was never in the same space. **A number borrowed from a
  sentence that is true does not bring the truth with it** — 0.025 is
  right where it was written, about a standoff and a switch, both above
  the board, and it was carried across a Z boundary it does not cross.
  A peer's replacement (the hot-swap socket's solder wing, which does
  share the plug's Z band and does overlap it 0.258 in x) was two thirds
  right and missed in y by 4.03. Booleaned, the plug clears everything at
  0.000 mm³; moved +10.03 in y onto the wing the same probe reports
  1.198. Arithmetic guards are worth having and are not evidence; prose
  is not even a guard.
- **A boolean cannot see a trench, in either direction.** Interference
  asks what two solids share, and a cut removes material, so a feature
  standing *over* a channel and a membrane left *under* one both report
  0.000 forever. The wire channel ran across both screw positions: the
  counterbore's ceiling at z 1.00, the trench floor at 1.20, so 0.70 of
  y was spanned by 0.20 of plate — one layer, printed over the bore,
  under the seat the screw head bears on — and 0.45 of the shell's post
  stood on air beside it. `build.py` was green through all of it. **What
  an interference check can find is material that should not exist; its
  twin is material that should exist and does not, and that one is a
  subtraction against the volume the part is required to fill** —
  `_head_seat_probe()` builds the ring the screw head bears on and
  subtracts the plate from it, watched failing at 0.790 mm³. Plan-view
  floors sit beside it for the distance the boolean cannot report
  (-0.455 on the screws, 0.005 on the columns), but the subtraction is
  the evidence.

  **And the subtraction has a boundary, which is the next place to get
  this wrong.** A trench also meets things cut from the *other* face and
  leaves a membrane between them: the left +y foot's recess comes up 0.50
  under a channel going down 1.20, so 0.70 of plate spans an Ø8.00
  pocket. The material is *there* — it is thin — so the required-volume
  probe reports 0.000 and means nothing, and only a thickness says
  anything (watched failing at 0.200 with `FOOT_RECESS` doubled).
  Reaching for the shiny new check because it worked last time is the
  same disease as trusting the arithmetic one, moved up a level.
- **A case-space constant describes one layout.** `WIRE_LANE_Y` was
  written as a pair of case-space numbers off an `inline` scan. `stacked`
  seats the field 0.805 further back, so the same trench went 0.400 into
  a NeoKey column there while `inline` stayed green — and the fault was
  in the layout nobody prints, which is how it would have kept. Anything
  positioned relative to the boards belongs board-local with
  `FIELD_ORIGIN` applied once; the tell that it worked is the margin
  coming out identical in both layouts.
- **The C-back cut is the case's depth, not the hook's 3 mm.**
  `_end_hook_bands()` is where the bosses live. A cut that follows them
  leaves the inner slab standing between them, which is what the shell
  hits, so the boss never seats. Deepening `END_HOOK_BACK` in X does not
  fix a Y that never went through. `END_HOOK_BACK` is the painted
  square's X (1.60); the Y is `CASE_D`. Watched failing at 0.512 mm³
  with the cut limited to the bands.
- **Shell slack does not help too-tall columns.** `BOARD_CLAMP_SLACK`
  sits above the board. Columns that run to `Z_BOARD_BOTTOM` push the
  board into the switches, which hold the shell up. Printed: a hair
  under 1 mm of seam, closed if you pressed. `COLUMN_SLACK` is 0.40.
- **Prove a check fires before trusting it**, and **inject the fault by
  moving geometry, not by shrinking it to nothing.** A zero-width `Box`
  makes OCCT throw, so the build dies before the check ever runs and the
  test proves nothing. Injections also have to isolate one thing: growing
  `QTPY_LIP` to reach a button grew its height too and tripped a
  different check entirely. Moving the feature 60 mm sideways, or setting
  one diameter past its limit, keeps the fault where it was aimed.
  Watched-to-fail numbers so far: cable notch 28.4 mm³, rail over a
  button 68.9 mm³, standoff at Ø6.0 1.016 mm³, USB opening narrowed
  3.8 mm³, a breakout support column moved back onto its second
  mounting hole 5.675 mm³, the seam standoffs shifted half a pitch onto
  the switches 26.260 mm³, the breakout pegs grown from PEG_DIA to
  COLUMN_DIA 64.796 mm³, and the C-back leftover between the bosses
  0.512 mm³ with the cut limited to `_end_hook_bands()`, and columns
  to the board 0.731 mm³ with `COLUMN_SLACK` at 0.
- **A hole above a counterbore is a ring printed over air.** Ø6.10 of
  counterbore under the Ø3.55 hole of the day leaves 1.275 mm unsupported
  all the way round; it sags into the top of the bore, and the printed
  coupon has filament in every hole. The built bottom plate has the same
  feature, so this is a better candidate than hole shrink for why the
  clearance holes guide the screw instead of clearing it. `coupon-clear`
  prints the row twice, `C0.00` and `C0.60`, identical diameters
  differing only in the transition, because a diameter sweep alone would
  have found a number that works and left the reason unknown -- the same
  answer a wrong theory gives. **Both explanations were right and neither
  was the variable.** The eight holes sort by the ring left unsupported,
  `(SCREW_HEAD_DIA - dia) / 2 - chamfer`: clean at 0.600 and below, a
  little sag at 0.675, filament in the bore at 0.750 and up. So 0.60 is
  this machine's limit for an annular ceiling printed over air --
  `CLEAR_RING_MAX`, the same kind of constant as the 0.15 shrink -- and
  the plate is now Ø3.70 chamfered 0.60, landing exactly on it. That ring
  is also the screw head's seat, so it is the one dimension here with a
  maximum as well as a minimum, and `build.py` checks it outside the
  margins table because that table can only express floors.
- **A feature can be absent from a valid part, and nothing says so.**
  Twice, by two different mechanisms. A chamfer written *below* the
  counterbore top cut into space the counterbore had already removed, so
  the two coupon rows would have printed identical while the experiment
  concluded that chamfering does not help. And a skirt built below
  `Z_FLOOR` was deleted on every build for three rounds by `shell()`'s
  closing `part = part & outer`, because `outer` starts at `Z_FLOOR`.
  Both times: no error, `all checks passed`, a render that looked right,
  and the part simply did not have the thing in it. A check asks whether
  the part is *valid*; it cannot ask whether it is the part you meant.
  **When a feature is meant to change a shape, measure the shape** -- a
  probe asking two rows to disagree at a stated height, or a bounding
  box. One line either way, and it is the only thing that catches this.
- **A check drifts away from the geometry it was written for, and goes
  on reporting.** Two shapes of it. One: a check *positioned from the
  thing it measures* -- the coupon's clearance label sits 1.00 from the
  counterbore's rim, so a margin on that gap reported 1.000 forever and
  would have through any change. It was added and deleted, because a
  guard that cannot go red reads as coverage; what replaced it measures
  the part that is not derived, whether the label still lands on the pad,
  watched failing at -4.327 with `LABEL_SIZE` at 12.0. Two: a check
  measuring a feature *that no longer exists* -- "board columns inside
  the cavity" used `COLUMN_DIA` for every column after the field pads had
  been given their own smaller one, and put a pad 0.06 outside the cavity
  that is really 0.44 inside it. Whenever a constant stops being the only
  one of its kind, grep the checks for it. Same disease as the standoff
  story, caught one step earlier.
- **The standoff story is the reason for "prove a check fires".** Named
  rather than pointed at: this bullet used to say "the rule above", and
  the list has grown three times since, each insertion quietly moving
  what "above" meant. Its diameter was cut on the stated grounds that
  the check had flagged it, and it never had -- the 0.009 mm³ came from
  the plate-hole corner instead. A check nobody has watched fail proves
  nothing, and a *credited* catch that never happened is worse, because
  it launders the reasoning that came with it.
- **A diff cannot show a contradiction**, because a contradiction is a
  relationship between two places and a diff only ever shows one of them.
  This section introduced the pilot mouth as derived from
  `SCREW_CLEAR_DIA` and, three paragraphs later, explained that the
  derivation had been broken and the number pinned. Both sentences were
  correct in the commit that wrote them; they landed a round apart, and
  neither commit's diff contained the other. So: **when two commits a
  round apart touch the same section, review the section, not the
  diffs.** The reader who can see it is one going end to end with no
  memory of which round wrote what -- which is not a skill but a
  position, and the author never has it. Worth deliberately taking, or
  handing to someone who already has it.

  The general form, which is the useful half: **a reference is only as
  stable as the thing it points at is named.** Position is a property of
  the document, not of the fact. Every "see above", "the rule below" and
  "the bullet after this one" in here has been replaced with the name of
  what it means -- four of them, all correct on the day they were
  written, none of them robust to the next insertion.
- **Look for the STEP before assuming there isn't one.** `BREAKOUT_T`
  sat as a documented guess -- "Adafruit publishes no STEP for this
  board" -- through a whole session, and they publish one, in the same
  `Adafruit_CAD_Parts` repository `ref/fetch.sh` already pulls the other
  two boards from. The 4978's model also turned out to be the only one of
  the three that includes its hot-swap socket, so the footprint the
  support columns dodge is measured now instead of carried over. The
  guess was right to three decimals, which is exactly why it survived:
  nothing downstream ever disagreed with it.
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
- **The section cap is a volume test.** It counts front faces against
  back faces and fills where they do not cancel, which is defined for a
  body that has an interior. The PCB and its packages have no volume --
  they are surfaces EasyEDA exported -- so the stencil never cancels and
  the cap paints every remaining face with the cut colour. `dump()` marks
  each part `closed`, and the cap loop skips the ones that are not.
  Clipping them is still right; filling a surface is the bug.

## Remaining on the case

The `inline` case is printed and mostly proven on the real part. Settled
by assembly: `SWITCH_HOLE` at 14.15 (a Durock Ice King seats right),
`PEG_DIA` at 2.30 (the NeoKey drops on free with a little play),
`QTPY_SLOP` at 0.40, and the USB-C port -- a real cable seats fully with
about 1 mm around its housing, which matters because `USB_PLUG_W/H` were
never measured off anything, just chosen generously.

`PILOT_DIA` is settled at **2.95**, on a coupon that carries one post per
`PILOT_SWEEP` entry, engraved, driven with the same M3 minutes apart --
2.50 is the tight one the built shell has, 2.95 is the one that bites
without a fight. Every mouth also got a Ø3.40 x 0.60 lead-in so the screw
has somewhere to start. That 3.40 was derived from `SCREW_CLEAR_DIA` when
it was written and is a pinned number now -- the clearance hole moved
and the derivation did not survive it, which the bottom plate's own
paragraph covers.

Two things about 2.95 are worth keeping. It is **not** where the
arithmetic pointed -- this machine pulls a hole in by ~0.15, the constant
`SWITCH_HOLE` measures, so 2.95 arrives as ~2.80, which is 0.93x major
against the 0.83x the tables want. The coupon outranks the tables here
and that is the whole point of having one. And it won at the **top** of
the sweep, so the stripping diameter was never found -- and is
**deliberately not being looked for**, because finding it means driving
screws into posts until they fail and the answer changes nothing. 2.95
works, and the response to a strip is to come down from it, not to know
where the cliff was. The failure mode is still real: this number lets go
on the third opening rather than splitting a post on the first, and if
that happens the sweep re-runs downward. The reprinted shell has 2.95 in
it and the screw goes in clean.

The 0.15 shrink then turned up a third time in the part nobody was
looking at. **The bottom plate's screw holes are tight** -- Ø3.40 arrives
as ~3.25 against an M3's 3.00, so they pass a screw while guiding it,
which is not what a clearance hole is for. The first answer was 3.55 on
the shrink arithmetic, and it was wrong -- see "a hole above a
counterbore is a ring printed over air" -- and
`SCREW_CLEAR_DIA` is now 3.70 with `CLEAR_CHAMFER` at 0.60. The built
plate has since been reprinted at 3.70 with the chamfer and it is
right -- clean bores, no filament in them, screws going in easily -- so
this is proven on a part and not only on a coupon. Widening it also
broke a derivation: `PILOT_MOUTH_DIA` used to read `SCREW_CLEAR_DIA`,
on an argument that only held while the two happened
to agree, and it is now pinned at 3.40 because what the funnel has to
catch is the screw tip, not the plate's hole. `build.py` gained
"counterbore ring under the head" at the same time, since widening the
clearance hole eats the ring the head bears on and nothing else would
have noticed.

The coupon now settles that one too: `CLEAR_SWEEP` is a second row, on a
pad raised to the real `BOTTOM_T` with the counterbore on the **bed**
face where `bottom()` puts it. Both details are load-bearing -- a hole is
as free as the number of layers it passes through, and printed
counterbore-up the through-hole would start at the squashed first layer
and read tighter than the plate it stands in for. Its labels are on that
same face and mirrored, because a face is seen from the other side once
the part is in your hand. Two things this cost, both worth remembering:
the label position is derived from the counterbore's rim rather than the
pad edge, after a fixed offset put the top of the digits exactly on it;
and `coupon_layout()` exists because a probe holding its own copy of the
row positions kept measuring where the posts used to be, passing every
"this hole is open" assertion by finding nothing at all.

The first assembled six-key unit settled two things the model could not.
**A breakout needs no locating peg**: a plate-mount switch clips into the
top plate and its pins go into the socket on the board, so the switch is
what ties the two together -- the supports set the height and the shell
presses down, and a peg carries nothing. They are gone, and with them the
0.362 to the socket at the back-right hole and the only feature that made
the board look like it had a wrong way round. **And the leftmost breakout
was pressed on one side only**, because a seam is between two boards and
the field's outer edge has none; `EDGE_RIB_W` is the plate reaching down
along that edge, since a 4.20 standoff does not fit in the 2.525 a board
has from its edge to its own switch body.

Also noted: the Qwiic plug goes into the `inline` pocket but takes some
working at, which is `QTPY_STEMMA_NOTCH` at 1.00 and would want 1.5-2.0
on a reprint. `stacked` has not been printed at all.

## Editing the firmware

- **Two devices, one file, and `PROFILES` is the whole difference.** The
  QT Py build is two 4978 breakouts on GPIO (keys 0-1) plus a NeoKey on
  I2C (keys 2-5); the custom PCB is six switches straight to GPIO and one
  six-pixel chain. They cannot share a pin table even though they share
  pin *numbers* -- the PCB was laid out against the QT Py's broken-out
  GPIO on purpose, so GPIO3 is the breakouts' pixel line on one board and
  KEY0 on the other. `GPIO_BASE` / `SEESAW_BASE` still know which way
  round the halves go; the profile decides what the halves are.

  Indices stay static within a profile: key 2 is key 2 when the NeoKey is
  silent, because the host maps index to pane and a silent renumbering
  focuses the wrong session. Both real profiles come to `NUM_KEYS` 6, by
  different sums -- 2 + 4 and 6 + 0.
- **Pins are GPIO numbers through `microcontroller.pin`, never names
  through `board`.** `board` carries a per-build name table: all seven of
  `MOSI`/`MISO`/`SCK`/`TX`/`RX`/`SDA`/`SCL` exist on the QT Py build and
  **none** of them on the generic `raspberry_pi_pico` build the PCB runs.
  Both halves of that were read off the two devices, not assumed. Resolve
  them inside the setup guard, not at module scope, or a wrong-board flash
  is a silent brick instead of a board that still talks.
- **The profile is chosen by which CircuitPython *binary* is running, and
  that is not the detection this file forbids.** Whether a breakout is
  *wired* is electrically unknowable -- an absent one and a present one
  nobody is pressing are both pulled high, with no readback on the pixel
  line and no capacitive sense on an RP2040 -- so that question was always
  a human's to answer. `sys.implementation._build` is a compile-time
  string with no guess in it: `adafruit_qtpy_rp2040` and
  `raspberry_pi_pico`, both read off their own board's REPL.
  `MPAD_BOARD` in `settings.toml` overrides the table, per device and
  without editing this file.

  **An unrecognised answer gets no fallback profile.** It claims no pins
  and no addresses and reports `ERR board ...`, because a wrong guess
  renumbers every key silently -- the one failure this file is built to
  prevent. So `HELLO <ver> 0` is reachable again and now means exactly
  "this firmware does not know what board it is on". Claiming six keys
  that resolve to no pins would be a positive claim of health, which is
  worse than silence.
- **Each half is skipped whole when its profile entry is empty**, and
  neither skip is cosmetic. `NeoPixel(pin, 0)` is a zero-length strip --
  either an exception, and then that board reports `ERR gpio pixels` on
  every connect forever about hardware it never had, or an empty group
  nothing writes to. The I2C skip is the mirror: running it on the PCB
  would import `adafruit_neokey` and call `board.STEMMA_I2C()` on a device
  with neither, putting `ERR i2c setup ...` on every connect about a bus
  that cannot be fixed because it was never there. Both would teach a host
  to ignore the real error.
- **On the QT Py, a dead NeoKey costs exactly four keys and a dead
  *cable* costs all six.** None of this applies to the PCB, which has no
  bus and no cable: everything there is soldered, so the only faults it
  can have are setup ones. The GPIO reads sit outside every guard and each
  pad's
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
- **Low-brightness smoothing is the known open improvement.**
  `PULSE_GAMMA` is 1.0 because a deep pulse at low global brightness runs
  out of 8-bit levels near its floor, and the perceptual curve was spent
  to keep the levels rather than the other way round. Temporal dithering
  is the actual answer and is cheap here -- the pulse already repaints at
  50 Hz. It was investigated once on the QT Py, on scratch scripts that
  only ever lived on that board's `CIRCUITPY`; **their conclusions do not
  carry to the PCB**, whose pixels are a different part on a regulated
  3V3 rail rather than the QT Py's unregulated Qwiic one. The constant's
  own comment carries the detail.
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
- **`boot.py` carries its own copy of the profile table**, deliberately
  the smallest one that answers its two questions -- which pins to read,
  and whether there is a bus worth probing. It cannot import `code.py`
  without running the whole program, so the duplication is the import
  that cannot happen rather than an oversight; keeping the copy minimal is
  what keeps it from drifting.

  Every way it can be wrong fails in the harmless direction, which is the
  property to preserve. A profile that will not resolve raises out of the
  gate's `try`, and the handler leaves the drive **enabled** -- a board
  this file does not recognise is exactly a board someone needs to copy a
  new `code.py` to. A missing library or a wrong address does the same.
  The one failure worth naming because it is silent: a GPIO number that
  exists but is wrong reads high through its pull-up, so that key quietly
  stops opening the drive while the others still do.

  The gate opens on any of the profile's GPIO keys -- two on the QT Py,
  six on the PCB -- and the seesaw probe with its 0.5 s is skipped
  entirely when the profile has no addresses.
- `lib/` needs `neopixel.mpy` on both boards; missing, keys report
  presses and never light and the host is told `ERR gpio pixels ...`.
  `adafruit_pixelbuf` is a **core** module, so that one file is the whole
  pixel dependency. `adafruit_neokey` and `adafruit_seesaw` are needed
  only by the `qtpy` profile -- the PCB never touches I2C, so their
  absence there costs nothing and is never reported.
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

| State | Board | The device says |
|---|---|---|
| healthy | both | `HELLO 3 6` on connect, `PONG 3 6` to `P` |
| unknown build, no `MPAD_BOARD` | both | `HELLO 3 0` + `ERR board <build> is not one of pcb/qtpy`, no keypad claimed at all. Not a wiring fault |
| `neopixel` missing | both | `HELLO 3 6` + `ERR gpio pixels ...`, the GPIO keys dark but still reporting presses |
| NeoKey or `adafruit_neokey` missing | qtpy | `HELLO 3 6` + `ERR i2c setup ...`, keys 2-5 dark, connection held, and `CIRCUITPY` back (the gate failed open on the same fault) |
| bus lost while running, cable still in | qtpy | `HELLO 3 6` + `ERR i2c lost at runtime: ...`, keys 0-1 unaffected |
| Qwiic cable unplugged | qtpy | `HELLO 3 6` + `ERR i2c lost at runtime: ...`, and keys 0-1 dark and stuck unpressed — they draw `VDD` and `GND` off the NeoKey, so the cable carries their power too |
| firmware died past 60 s uptime | both | `ERR fatal ...`, all keys red, port drops, fresh `HELLO` |
| firmware died inside 60 s | both | `ERR fatal-halted ...` on every later connect, stays red |

No `ERR i2c` of any kind can appear on the PCB: the profile has no
addresses, so that half is never built and has nothing to report.

USB identity: product `Canopy MacroPad`, manufacturer `Saqoosha`, VID
`0x239A`. **The PID is not part of the identity** — `boot.py` sets only
the strings, so the VID and PID come from the CircuitPython build, and the
same firmware measures `0x80F8` on the QT Py build against `0x80F4` on the
PCB's stock Pico build. Both host-side matchers already ignore it, and
Canopy's `MacroPadDevice.swift` says why it must: pinning a build-owned
number fails *closed*, and a device that never connects looks exactly like
a bad cable. Match on the product string.

Two ports enumerate; **never pick by trailing number** — only `P` →
`PONG` identifies the data port, because the console echoes `P` as REPL
input and never answers. The suffix is not even stable across ports on one
machine: the same board read `usbmodem21101` and `usbmodem2101` an hour
apart.

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
