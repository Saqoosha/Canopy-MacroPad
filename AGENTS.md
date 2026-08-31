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

**A restore is only as good as the copy is fresh, and a stale one is
worse than none.** The fault-injection harness took its backups once, by
hand, near the start of a session; six hours later its restore step put
those back and **silently reverted 241 lines of finished work in two
files**, one of them untracked so git had nothing to offer. The run
reported `restored: all checks passed` -- about the old file. Two things
make this hard to see: every injection had gone red first, which reads as
the harness working; and the reds after the clobber came from the
harness's own drift guards rather than from any check, so they looked
identical to real catches. **The snapshot has to be taken by the same
command that does the restoring, on every run**, and the run should end
by comparing hashes with what it started from. Recovery here came off
the CIRCUITPY drive, which happened to hold a newer build than the
repository did -- luck, not a plan.

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

**Merging a long-diverged branch here needs two different tests, because
the documents and the code fail differently.** 36 hunks over 9 files, from
two lines of work on the same object.

*Code is decided by a measurement, not a preference.* Ask whether one
side's `params.py` still defines the constants the other side's code
reads: 0 mentions of `NEOKEY`/`BREAKOUT`/`QTPY` against 119 settled five
files in one command, because the losing side would not have been a merge
but a build failure. `_circ_rect` and `_rect_gap` were called 7 times on
one side and 0 on the other -- dead code, not lost work. Check separately
that nothing *device-agnostic* rides along: the camera-as-a-quaternion
work looked like it was only on one side and was already on both (`qBasis`
6 occurrences either way).

*Documents usually keep both sides, and that is where the trap is.* If the
other branch **moved** a bullet as well as editing it, the same lesson
sits inside your hunk and outside it, and "keep both" silently duplicates
it. Two such pairs went opposite ways in one file -- one where this
branch's copy was current and the other side's was stale, one where the
reverse held -- so a strategy flag cannot settle it and reading can.

*Assert every splice, and expect the assertions to earn their keep.* Two
fired. One caught an assumption about **where** a section began: the other
side's taxonomy started above the conflict, so taking "its side" would
have duplicated the first entry. The other caught
`"A third screw at mid-span"` failing to match **because it wraps across a
line** -- `replace()` would have returned the string unchanged and dropped
a fact while reporting success.

*Finish on the build, not on the marker count.* Zero markers means the
text parses, not that the model holds together; `build.py` ending in `all
checks passed` is what says the resolved files still agree with each
other.

**`/merge-cleanup` cannot run from inside the worktree it is cleaning
up.** The branch is checked out there, so the worktree has to be removed
before the branch can be deleted, and every step after the merge belongs
in the primary checkout. Before removing it, confirm the primary repo has
its own `case/.venv` -- the worktree's is ~570 MB of build123d and goes
with it.

## Editing the case

Environment is a venv at `case/.venv`, Python 3.12 (`uv venv --python
3.12 .venv`, then `uv pip install build123d trimesh matplotlib`). The
system Python is 3.14 and has no build123d; whether that is a wheel gap
or just a missing install was never checked, so 3.12 is the known-good
one, not necessarily the only one.

- **One layout, `choc`, and no switch to select it.** `MPAD_LAYOUT` is
  gone with the two layouts it chose; `params.OUT_NAME` is the output
  directory's name, not an axis. The `out/inline/` and `out/stacked/`
  directories are the earlier device's, kept because that case is still
  assembled and its source is not — they cannot be rebuilt, so do not
  treat a stale figure in them as something a rerun will fix.
- **`params.py` loads `pcb/params.py` by path.** Board width, corner
  radius, switch pitch and pad positions are read from the PCB's own
  source rather than restated, so the two cannot drift into disagreeing.
  A change to the board reaches the case on the next build with nothing
  to keep in step by hand.
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

  **All of it is one animal: a probe whose question is well formed and
  whose sampling silently misses.** The boolean's sampling misses a cut,
  the required-volume probe's misses thinness, and a *grid* misses
  anything narrower than its step -- the Choc v2 stem's retention ribs
  are 0.10 wide and every probe of that arm returned 1.200, correctly,
  by landing either side of them. The tell is the same each time and it
  is not an error message: **a small residual nobody can attribute.**
  0.075 mm³ of interference with no explanation was the ribs. What turns
  a residual into a cause is refusing to sum it -- eight pieces listed
  individually said 8 x 0.00936 at x 1.15..1.25, y 0.60..0.65, which is
  a rib; the total said nothing. A sum hides the structure that names
  the cause, and `.solids()` is one call away.

  **The animal has an inverse: a probe whose sampling catches someone
  else's material cannot fail.** The latch's post-presence box was
  drawn 0.50 wide in y and two tab positions stand close enough to the
  back-press columns that the box caught a column's edge -- 0.072 mm³
  of it, measured -- so at those positions the check would have said
  "post present" with the post six millimetres away, and did, under
  injection. A presence probe earns trust the same way a guard does:
  move the feature and watch the count drop; if it does not, ask what
  the box is touching instead. The fix is a band the neighbour cannot
  reach, and the injection re-run (10/10 -> 8/10) is what said so.

  **A bounding box is a sum too, and it lies the same way.** A probe that
  catches two features reports one box spanning both, which reads as a
  single enormous feature: a 4.8-long strip across a cross arm crossed
  the ring either side of it and returned a 1.200 arm as **4.800**, and
  the same shape of read said a 0.10 rib was 3.600 long and put material
  where a plain min/max suggested a solid run. Three times in one
  afternoon. Any probe whose result might hold more than one piece gets
  `.solids()` and a length check before its `.size` is believed.

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

  Three: **the check stood still and the model gained detail under it.**
  "The bore must not touch the stem" was correct, was watched red, and
  stopped being true the moment the Choc v2's retention ribs were
  measured -- the bore is *supposed* to squeeze those, so contact became
  the intended behaviour and nothing about the check had changed. This
  one is the opposite direction from the first two and grepping cannot
  find it: there is no constant to follow, only a premise that quietly
  stopped holding. **When the geometry a check guards gets more
  detailed, re-read what the check assumes**, not just what it measures.
  What that check is now: the arm body is a wall and is checked at
  0.000, the squeeze on the ribs is printed as a reading with no
  pass/fail, because no value of it is wrong in the model and only a
  pressed token can say.
- **Prove a check fires before trusting it**, and **inject the fault by
  moving geometry, not by shrinking it to nothing.** A zero-width `Box`
  makes OCCT throw, so the build dies before the check runs and the test
  proves nothing. Injections also have to isolate one thing: growing
  `QTPY_LIP` to reach a button grew its height too and tripped a
  different check. Moving a feature 60 mm sideways, or setting one
  diameter past its limit, keeps the fault where it was aimed. Restore
  from a copy, never from git.

  injection separated the two. **Watch what a check fires on, not just
  that it fires.**

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
  the channel 0.200, a column against a board's components 0.141 at
  `FIELD_SUPPORT_DIA` 3.50 and 0.191 at 3.40, and the slide latch's
  five: posts 6/8 and everything downstream (free-play 8.672, corridor
  5.744/7.184/8.840) with a pair moved +4.0, shelves 0/8 with the
  capture cut through them -- the coupon differ check firing too, at
  steps 0.0, because a shelfless sweep tests nothing -- free-play
  0.168 mm³ **alone** with the shelf raised half a fit, corridor
  26.036 with the trim skipped, and 4.784/6.624 with the entries cut
  short while the mid-slide probe rightly stayed green. Two real
  faults were also caught before any injection: 1.681 mm³ of tongue
  corner in the skirt's corner arcs, and 1.122 mm³ cut from a screw
  seat by the box reliefs that first answered it.
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
- **A case-space constant describes one layout.** `WIRE_LANE_Y` was
  written as a pair of case-space numbers off an `inline` scan. `stacked`
  seats the field 0.805 further back, so the same trench went 0.400 into
  a NeoKey column there while `inline` stayed green — and the fault was
  in the layout nobody prints, which is how it would have kept. Anything
  positioned relative to the boards belongs board-local with
  `FIELD_ORIGIN` applied once. There is one layout now, so the tell that
  used to catch this — the margin coming out identical in both — is gone
  with it, and the rule is all that is left. That makes it *more*
  load-bearing than when it was written, not less: nothing measures it
  any more.
- **The C-back cut is the case's depth, not the hook's 3 mm.**
  `_end_hook_bands()` is where the bosses live. A cut that follows them
  leaves the inner slab standing between them, which is what the shell
  hits, so the boss never seats. Deepening `END_HOOK_BACK` in X does not
  fix a Y that never went through. `END_HOOK_BACK` is the painted
  square's X (1.60); the Y is `CASE_D`. Watched failing at 0.512 mm³
  with the cut limited to the bands.
- **The end hook is retired -- by the printed case, not by a model.**
  The full latched case would not slide home; Saqoosha cut the boss off
  the print, the eight noses held the bottom fine without it, and the
  slide still stopped 0.1 short: the hook's wall kept 0.10 to the
  shell's C lip and the tongue's right corners ~0.14 to the skirt's --
  swing-era clearances inside the hole shrink, never widened the way
  the latch's were. Gone whole (wall, boss, C-back, band reliefs,
  slots); the tongue now ends at `SLIDE_RIGHT_TRIM_X` before its corner
  arcs, 2.10 to the right skirt where the wall had 0.10, and home in x
  is the screws' alone. **A 0.1 stop is invisible to every boolean at
  nominal** -- it only exists once printing shrink eats it -- so the
  trim is guarded as a shape (tongue *gone* past the plane, watched at
  25.408 mm³ with the trim skipped, every other check green around it).
- **The slide latch is ten small end hooks, and every turn of its
  shape was bought by a print.** Posts (4.00 x 0.85 x 2.20) stand on
  the plate's tongue rim, each with an **eave** off its top reaching
  0.90 outboard; the shell's wall underside takes entry pockets, a
  channel per post, and a **ledge running along x** the eave rides
  over -- a sagging middle is an eave landing on its ledge. The shape
  history: v1's in-step ledges were unprintably small; the +x nose
  that followed became a 1.5 free cantilever whose printed droop
  rammed its shelf; the first eave (0.65, capture 0.80, slide 1.25)
  was "too tiny... too short"; and the grown eave-and-ledge pair
  jammed as two opposed drooping flats, which is why **both bearing
  faces are parallel 45-degree wedges now** -- no free overhang
  survives in the latch at any size. So the slide **flipped
  leftward** --
  rightward travel was capped at 1.25 by the left trim against the
  screw seats, leftward is capped only by the right trim -- giving
  2.00 of capture, a 0.90 drop window, and a fifth tab pair at -66 as
  the screws' understudy. Motion: push right to the touch, drop,
  slide left ~2 -- no screws; the latch carries the case alone. Both tongue ends are cut with the skirt's
  own inner outline (shifted for home clearance left, swept for the
  drop right, intersected) -- straight faces left corners standing in
  the skirt's arcs, watched at 1.681 mm³ left and 1.488 mm³ right,
  and box reliefs cut 1.122 mm³ from the screw seats; the arcs pass
  between. The corridor is legal because the columns dodge the
  sockets in **y**, not in x. `SLIDE_FIT` is **0.30, settled on two
  printed sweeps** (0.20 felt failing below it); its meaning survives
  every reshape unchanged -- vertical clearance onto shell material
  below -- and each reshape re-confirms it on the coupon before the
  case. Screwless is the stated goal if the latch proves itself: what
  the screws still do is x registration and slide-back retention, and
  the candidate replacement is a ~0.25 detent riding inside SLIDE_FIT,
  engaged by the plate's own hang -- no material bent, so the barb
  arithmetic never applies. Full
  reasoning: `case/README.md`, *The slide latch*.

- **The board's slop is split by axis, and the axis came from the
  symptom, not the words.** `PCB_SLOP` 0.80 is the *length* (a 139.60
  board between the frame's left wall and the right wall lost its
  whole 0.40 to shrink -- forcing it in buckled the board), and
  `PCB_SLOP_Y` 0.40 is the depth, which never complained. The first
  fix widened the depth because "long side" was read as the case's
  long walls; the buckling itself had named the axis -- a board bends
  along its pinched length, never across its stiff 21.59 width.
  Length position is not precision: switches tie board to plate, and
  the USB opening derives from the board's own edge.

- **Shell slack does not help too-tall columns.** `BOARD_CLAMP_SLACK`
  sits above the board. Columns that run to `Z_BOARD_BOTTOM` push the
  board into the switches, which hold the shell up. Printed: a hair
  under 1 mm of seam, closed if you pressed. `COLUMN_SLACK` is 0.40.
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

- **An observation with no timestamp on it gets quoted as a fact.** A
  peer was told its `pcb/` files were uncommitted, on a `git status` that
  was real when it ran and an hour stale when it was repeated -- the
  files had been committed in between. Same shape as the worktree cwd
  mistakes: the measurement was true, and what was missing was *when* and
  *where* it came from. Re-measure before asserting somebody else's tree,
  and say when you measured. It cost a round to settle something both
  sides could have checked in one command.

- **The case corner is the cap corner grown concentric, and its price
  is written at the diagonals.** `OUTER_CORNER_R` 7.995 = cap margin
  3.795 + `CAP_R` 4.2, checked against that equation in `build.py`
  (the CAP constants live below it in `params.py`, so a check referees
  instead of file order). The cavity corner cannot follow (the board
  closes the window: `CAVITY_CORNER_R` 2.70 is the most its corner
  permits) and cannot stay square either -- at 1.00 it poked a 0.07
  slit THROUGH the 7.995 outer face at every corner, a hole no
  interference boolean can see. A diagonal leak probe owns the class
  (watched at 4/4 on the reproduced fault; its first march was 2.0
  long against an outer face 3.3 in and reported leaks about a wall it
  never reached -- overshoot the range, again). Corner wall: 0.65, the
  whole budget between board corner and concentric arc. The shell's
  top chamfer (`SHELL_TOP_CHAMFER` 1.20) is cut on the bare slab and
  doubles as first-layer relief; its try/except-wrapped predecessor
  swallowed its own failure at 1.20 and the bed-inset probe (0.35 for
  an expected ~1.2) was what confessed.

- **The dummy caps mount on a ring, not on a cross.**
  `out/choc/keycap.stl` is a blank 1U to press while the wrk. MX Pure
  set is in the post, and its mount is **read off `ref/choc-v2.step` by
  `build.py` on every run** rather than taken from an MX table: Choc v2's
  stem is a cross standing *inside* a Ø6.50/Ø5.50 ring, both topping out
  on the same plane, so the cap seats on the rim and the bore clears the
  cross tip by 0.10. `STEM_CLEAR` is the only number here a printer owns
  and it is **settled at 0.00 on two printed sweeps**: 0.10, 0.15, 0.20,
  0.25 said 0.10 grips and the rest are loose, and the downward sweep
  that followed -- 0.00, 0.04, 0.07, 0.10, the last kept as the control
  -- said 0.00 is tight enough. Unlike this case's other bottom-of-range
  answers it is a floor with a mechanism, not an untested edge: 0.00 is
  the slot on the arm body, and past it the bore eats the arm rather
  than the ribs. The reasoning is `case/README.md`'s *Dummy keycaps*.

  **The tube round the bore closes only at boss Ø5.40 on a 0.4
  nozzle, and the rule is a margin now.** The thin spot is where a
  cross meets a circle: the arm's *corners*, ~15.6° off-axis -- 0.30
  tips sliced away entirely (the six early caps are tip-less and
  grip fine), 0.45 tips printed but *floated* on 0.37 corners. `tube
  wall at the arm corners` guards the class: under ~0.44 is a slicing
  casualty. 5.40 into the Ø5.50 ring is a near-press, relieved by
  four diagonal flats (5.10 across, where the wall is fat) that cut
  the contact to eight arcs -- printed verdict "still tight but ok".
  The mouth is width-only 0.15 for the same corner reason, and
  STEM_LEN_CLEAR must never shrink to buy wall: the length fit goes
  interference after shrink.

  **The arm is 1.20 and the fit is 1.30**, because eight retention ribs
  stand 0.05 proud of the arm flats, ~0.10 wide, running z 4.10 to 8.39.
  They are what holds a cap on, so a slot sized on the arm body is sized
  on the wrong number -- and the printed result is exactly the geometry:
  0.10 lands the slot flush on the ribs, every looser entry clears them
  by 0.025 or more. `STEM_CLEAR` is measured from the body, so it doubles
  as how much rib is left alone, and 0.00 is a floor rather than a round
  number -- past it the bore is into the arm.

  Finding them and re-checking around them are two general lessons
  rather than keycap ones, and they live with their own kind: the probe
  that missed a 0.10 feature is under *a boolean cannot see a trench*,
  and the check whose premise expired when contact became intended is
  the third shape under *a check drifts away from the geometry it was
  written for*.

  Two of this file's older rules earned another instance while it was
  built. The bore was cut in the **wrong direction** for a round: a valid
  cap, every interference check green, and the feature simply not in the
  part -- found only by the volume the cut was supposed to remove
  (7.474 of a wanted 31.409 mm³). And the check written to prove the seat
  exists put +0.40 on a *radius* where 0.40 of diameter was meant, so it
  reported 0.580 mm³ missing from a cap that was fine: **a check
  measuring its own arithmetic**, the same disease as one positioned from
  the thing it measures, wearing the other face.

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
  one. The full sweep:

  ```
  .venv/bin/python build.py       # must say all checks passed
  .venv/bin/python product.py
  .venv/bin/python render.py
  .venv/bin/python section.py
  .venv/bin/python webgl.py dump
  .venv/bin/python webgl.py page  # -> out/viewer.html
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

`out/viewer.html` is generated by `webgl.py dump` then `webgl.py page`.
Two ways to verify it, and both are worth doing because they cover
different halves:

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

- **The section cap is a volume test.** It counts front faces against
  back faces and fills where they do not cancel, which is defined for a
  body that has an interior. The PCB and its packages have no volume --
  they are surfaces EasyEDA exported -- so the stencil never cancels and
  the cap paints every remaining face with the cut colour. `dump()` marks
  each part `closed`, and the cap loop skips the ones that are not.
  Clipping them is still right; filling a surface is the bug.

## Where the case stands

Both halves of the `choc` case are printed and fitting, but the model
has since grown the **slide latch** -- eight small end hooks along the
long sides, answering the tiny gap at the middle of the seam -- and the
printed pair predates it, and the printed iterations keep deciding it:
the first latched case retired the end hook (its 0.1-class swing-era
clearances were the slide's last stops), and the third coupon grew the
tab and flipped the slide leftward ("eave is too tiny. slide length is
too short"). Current state: **printed and perfect** -- Saqoosha's
word, on the full case at `SLIDE_FIT` 0.30: ten tabs, capture 2.00,
leftward slide, 45-degree wedge bearing faces, both tongue ends
outline-trimmed. The fit is settled with a mechanism at both bounds
(0.20 puts the printed slopes in interference and visibly expands the
shell -- the wedge turns squeeze into outboard wall load -- and 0.40
is loose). The screws are gone -- posts, pilots, counterbores
and their checks, removed once the printed case proved the latch --
so the underside is unbroken, and the bay that held the posts shrank
the case to 145.27: `END_BAY` is 1.27 now, derived so the cap margin
is equal on the three non-USB sides (3.795, measured by a check on
the placed switches). The screwless case is printed and working at
145.27, and **the detent holds x** -- its second shape, printed:
Saqoosha's read is "good tight", no discrete カチッ (the ~2 of drag
before the notch smears the click into friction), and accepted,
because retention was the requirement and tight is retention. The
pocket-end over-travel stop backs it up at ~0.1 printed. The first
detent shape -- a 0.40
bump raised on the ledge's 45° slope, sprung by the plate's own weight
-- printed to nothing ("i dont think detent is working... theres no
bit change"): a two-layer feature on a stair-stepped slope smears away
in slicing, the cap's tip walls again, and a gravity spring has no
click. The second is vertical in both print orientations and sprung by
elasticity: a round ridge (r 0.50, 0.25 proud) on the mid tab's pocket
skin, parking in a 1.60 window cut 0.30 into that eave's outboard tip.
The spring is the skin panel bending 0.15 (~1.5% strain -- the barb
arithmetic passed for once), the same measured force that visibly
expanded the shell at the 0.20 fit. No opening gesture: the click is
symmetric, home pinned ±0.30. Probed (catch 0.016 / drag 0.016 / free
at home 0.000) and injections watched: ridges gone → 0.000s; notches
gone → global interference 0.031, the ridge standing in an un-notched
tip being the notch's necessity. `SLIDE_DETY_PROUD` up is the knob if
a felt click is ever wanted. The fastener constants stay in `params.py` for the coupons that
settled them. Every other number is settled on a part. **The
reasoning behind each one is in `case/README.md`** -- that is the story,
this is only the state. The
earlier device's `inline` case is likewise finished, assembled and in
use; its numbers are in the same file, under the sections marked as that
device's.

Nothing on either case is open. The one item that reads like an open
question is not one: the Ø8 feet leave 0.70 of plate over their recesses
under the wire channel, and nothing moves -- a Ø8 foot at y ±5.99 in a
25.99 case cannot clear a channel reaching ±5.60, and the feet are placed
so it does not rock. The number is the answer, and
`plate left under the wire channel` holds it.

**A fit is a claim about a distribution, and one assembly is one
sample.** The Qwiic notch sat on the open list for rounds as "the plug
goes in but takes some working at, a reprint would want 1.5-2.0", off a
single impression from a single print; several builds later the plug goes
in every time at 1.00. Every number that held up was felt more than once
-- `PILOT_DIA` and `CLEAR_SWEEP` side by side on a coupon, `SWITCH_HOLE`
and `PEG_DIA` across two prints, `STEM_CLEAR` across two sweeps and then
the caps themselves -- and the one that was not was also the one that
read wrong. When a fit is written up from one handling, say that is what
it is, and do not let it name a replacement number it has not earned.


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
- **The breath is `exp(sin)` at 2500 ms, and every number in it was picked
  by carrying the whole comparison on the six keys at once.** That method is
  the transferable part: one build, six curves (or six gammas, six periods,
  six values), everything else -- colour, floor, brightness, phase -- held
  identical, and the answer arrives in one look instead of one flash per
  candidate. Four questions were settled that way in an evening. A single
  candidate shown alone answers almost nothing, because the eye is a
  comparator and not a meter.

  What it settled: a raw sine reads as "the bottom is short and the top is
  long" (it lingers where the eye is least able to see a change); gamma 2.0
  reads as a pause at the bottom (level-minus-floor goes as t^4 there
  against t^2); 1.5 was the best of that family; and `exp(sin)` beat it,
  along with a plain triangle, FastLED's `quadwave`/`cubicwave` and the
  Gaussian fitted to a real MacBook sleep light. Then 2500 ms out of
  2/3/4/5/6/8 s -- 2000 was 30 breaths a minute, outside the 12-20 a resting
  adult does. The curve is a 512-entry table built at boot; 512 is the
  smallest power of two whose step is finer than a frame, and `PULSE_CURVE`
  carries the arithmetic.

  Ladyada found the same thing scoping a MacBook sleep light in 2006 and a
  2016 photodiode capture of one confirmed it. `research/2026-08-31-led-breathing-curve.md`
  is the full survey; two things in it are worth knowing before reading any
  of the folklore. The `exp(sin)` formula is **not** Sean Voisen's and does
  **not** model breathing -- it is a 2010 comment by Adam Shea correcting
  the log response of the eye, and it is exactly time-symmetric, so the
  widely repeated "2 s in, 3 s out" story about it is arithmetically
  impossible. And most published CIE-L* code carries a transcription bug
  (119 where CIE says 116).

- **Temporal dithering is in above `DITHER_FLOOR` on boards that paint at
  200 Hz, and the honest summary is that it is insurance rather than a
  fix.** The measurements are worth keeping because each one killed a
  plausible idea.

  **200 Hz is a threshold, not a preference.** Error diffusion at 50 Hz is
  *worse* than not dithering -- its own alternation lands inside the band
  the eye reads as flicker. Visible-band error, LSB rms, at brightness 0.15:
  today 0.237, dithered 0.378 at 50 Hz, 0.237 at 100, 0.075 at 200. So a
  board that cannot afford 200 Hz must not dither, which is why `PAINT_HZ`
  is per profile: the PCB's six pixels are one bit-banged chain, but four of
  the QT Py's live behind seesaw and a paint there competes with the key
  scan for the same bus.

  **Raising the rate cannot save the bottom, and no rate can.** Error
  diffusion holds one value for 1/fraction frames, so a fraction of 0.1
  alternates at 20 Hz however fast the paint is, and fractions get
  arbitrarily small. Measured on the board with static ladders where nothing
  but the dither could move: at a fixed 50/50 split (100 Hz) every depth
  from 67% down was invisible; at 20 Hz, depth 100% and 50% flickered, 33%
  was faint, and 20% and below were calm. Hence `DITHER_FLOOR` -- above
  value 5 the worst rate stops being visible.

  **Then the board contradicted the arithmetic that produced that 5.** It
  was derived from "one level as a share of the light", which assumes the
  LED is linear. Keys held at 0/1/2/3/4/5 side by side say otherwise: 0 to 1
  is a different world, 1 to 2 is plainly visible, and 2/3/4/5 cannot be
  told apart. Only the first two steps are visible at all, so 5 is
  conservative rather than correct.

  **And none of it happens in service.** The deepest breath Canopy sends
  bottoms out at 7.7 of 255 in its faintest lit channel. Every measurement
  above was taken at brightness 15 with a floor of 0 -- a condition invented
  to make the fault visible, and outside the envelope the pad is driven in.
  Say that before quoting any of these numbers as a problem.

  Two structural changes paid for the dithering and outlive it. The
  brightness multiply moved out of pixelbuf into `paint()`: pixelbuf scales
  with `(v * int(b*256)) // 256`, an integer floor *after* this file has
  already rounded, so at brightness 0.30 seventy per cent of expressible
  values collapse and dithering upstream is a provable no-op. The price is
  that `B` no longer re-renders for free, so `set_brightness()` invalidates
  and the render loop's settled-solid skip tests `last_rgb`. And a settled
  key rounds rather than dithering, or it would never stop writing.

- **The paint rate is bounded by the Python interpreter, not by the LEDs,
  and the largest single cost was arithmetic nobody looked at.** Per loop
  with six keys pulsing, before any of this: paint 5015 us, show 967, key
  scan 541, other 516 -- **the bit-banged LED chain is 14% of it and the
  pulse arithmetic is 71%**, at 142 Hz against a `PAINT_HZ` of 200.

  **`monotonic_ns()` is past MicroPython's 30-bit small-integer boundary
  within a second of boot**, so every expression touching it allocates. The
  curve index was `(now - pulse_started[i]) % period_ns[i] * _CURVE_STEPS
  // period_ns[i]` -- four big-integer operations per key per frame.
  Replacing just that expression with a small-integer counter, semantics
  broken on purpose to price it, took the loop from **142 Hz to 180**:
  236 us a key.

  What shipped keeps the semantics and reaches 170 of that 180. The period
  is stored in **milliseconds**, which is what the wire already sends, and
  the phase is a **position inside the period** advanced once per frame
  rather than a difference of two growing timestamps. Two more: the wrap is
  a compare and a subtract rather than `%` (the step is one frame, the
  period is clamped at 100 ms, so it can fire at most once), and the
  finished-fade case skips the `fade_progress` and `lerp_rgb` calls, which
  is almost every frame of a steady pulse.

  **Milliseconds counted from boot would have been the wrong fix**, and it
  is the trap worth remembering: `now // 1_000_000` crosses the same
  boundary after about twelve days. A bench build measured 192 Hz that way
  and would have silently reverted to big-integer arithmetic in service,
  on a device this file elsewhere describes as living plugged in for weeks.
  A position bounded by the period never grows.

  The price of a position is that it is advanced by a whole number of
  milliseconds, so the sub-millisecond remainder has to be carried --
  dropping it runs **every breath up to 11% slow** -- that is the worst of
  the four frame rates check 10 tests, 6.76 ms truncating to 6; a 7.042 ms
  frame loses 0.6% -- for ever, with nothing in the pulse to notice. `_phase_carry_ns` is that carry and check 10 in
  `tools/dither_check.py` is what watches it.

  What was measured and does **not** help: fixed-point, because a float
  multiply costs only 8% more than an integer one; and
  `@micropython.native` / `viper`, which **CircuitPython does not have** --
  both raise SyntaxError. An empty loop iteration is 3198 ns, so what is
  left is the interpreter itself. Going meaningfully faster means leaving
  CircuitPython, and the only thing that buys is dithering below
  `DITHER_FLOOR`, which does not occur in service.

- **Never write a large table as source literals.** 1536 float literals in
  `code.py` -- a 75 KB file -- **hard-faulted CircuitPython into safe mode**,
  which is not a `MemoryError` and not recoverable by a soft reload. It was
  the parser: the same tables built at boot cost ~2 KB of a free 162 KB and
  a lookup measured 21 us. Recovery needs `microcontroller.reset()` from the
  REPL, which runs `boot.py` with no key held and takes the drive with it.
  Prove a risky module-level construction in the REPL first -- pass it as
  one `exec(repr(src))` line, because a multi-line paste puts the REPL into
  continuation mode and silently swallows everything after it.

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
python3 -m py_compile firmware/*.py tools/*.py
tools/dither_check.py          # expect: all checks passed
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
