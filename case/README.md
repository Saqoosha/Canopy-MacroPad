# Canopy MacroPad — case

A two-part printed enclosure for the **custom MacroPad PCB** — one board,
six Choc sockets on 19.05, its own RP2040 and USB-C. Parametric, in
`build123d`; the way to change it is to change a number in `params.py` and
rebuild.

**One layout**, `choc`, and no switch to select it. `params.py` loads
`pcb/params.py` by path, so the board's width, corner radius, switch pitch
and pad positions are read rather than restated — the two files cannot
drift into disagreeing. It is printed, both halves: its end hook and its
column heights are settled on the printed parts, and the bottom that
`COLUMN_SLACK` asked for has been reprinted and fits.

Three sections here are about the **earlier device** rather than this one
— *The earlier device*, *Cable, per layout*, and *Stack, in `stacked`* —
kept because that device is still assembled and in use. Its two layouts
are gone from the source, so those sections are a record rather than a
menu: nothing in them can be rebuilt, and the STLs under `out/inline/` and
`out/stacked/` are the only form of them left. *What the checks have
actually caught* is that device's model too — the lessons carry, the parts
do not, and this case's own catches are in the repository's `AGENTS.md`.

## The earlier device: two layouts, and the `inline` one printed

The device before this one was three boards — a NeoKey 1x4 on I2C and two
single-key breakouts on GPIO — driven by a QT Py, and the case came in two
layouts from one source, chosen with `MPAD_LAYOUT`. They differed only in
where the QT Py went, and that one decision moved every dimension:

| | `stacked` (default) | `inline` |
|---|---|---|
| QT Py | under the keys, **face down** | right of the keys, **face up** |
| USB-C | back wall, low | right end |
| size | **97.6 × 27.6 × 17.5** | **120.5 × 26.0 × 11.8** |
| footprint | 26.9 cm² | 31.3 cm² |
| to the top of a keycap | 31.9 mm | **26.2 mm** |
| BOOT / RESET | open the case: they face you | open the case: unclip the board |
| who holds the QT Py | bottom plate, alone | shell from above, plate below |
| Qwiic cable | **100 mm**, down an end bay | **50 mm**, but with 35 mm of slack to fold into a 12 mm gap |
| handedness | either end takes the cable | **right-handed**: the cable can only come off the right socket |

`stacked` was the compact one and `inline` the low one. Neither was
strictly better — a shorter pad sits closer to keyboard height, a smaller
one takes less desk.

![The inline case, closed with keycaps on, and open with the NeoKey and
the QT Py seated in the shell above the bottom plate](images/inline-built.jpg)

`inline` is the layout that exists as a physical object. It printed flat,
without supports, and closed on the first attempt. Four numbers stopped
being guesses when it did: `SWITCH_HOLE` at 14.15 (a Durock Ice King
seats correctly), `PEG_DIA` at 2.30 (the NeoKey drops onto the pegs free,
with a little play), `QTPY_SLOP` at 0.40, and the USB-C opening, where a
real cable seats fully with about 1 mm around its housing — worth knowing,
because `USB_PLUG_W/H` were never measured off anything.

Two things the part says that the model does not. `QTPY_STEMMA_NOTCH` at
1.00 takes some working at — the Qwiic plug does go in, but a reprint
would want 1.5–2.0. And the M3 has now been driven into a post: it goes,
but hard enough to be the first thing anyone says about the part. That
sent `PILOT_DIA` to the coupon, which settled it at 2.95 — the how is
under "Print the coupon first" — and put a Ø3.40 × 0.60 lead-in at every
mouth. The reprinted shell has both and the screw goes in clean.

Then the part nobody was looking at: the bottom plate's screw holes are
tight. They pass a screw, but they guide it, and a clearance hole is
supposed to be free. The obvious answer was the same 0.15 shrink a third
time, and it was wrong — see "Print the coupon first", where two rows of
holes found the real cause under the counterbore. **A plate has been
printed at Ø3.70 with the 0.60 chamfer and it is right**: the bores come
out clean, with no filament hanging in them, and the screws go in easily.
That is the last number on this case to stop being a prediction.
`stacked` has never been printed at all.

Print target is a **Bambu A1 mini**, 0.4 nozzle, 0.2 layer, PLA Basic.
Both parts print flat and **neither needs supports**. If the slicer wants
supports, something changed — find out what before printing.

## Print the coupon first

There are four, and the small ones exist so that re-asking one question
does not cost a reprint of the answers already settled:
`out/<layout>/coupon-stem.stl` is the keycap mount's slot sweep, which
*Dummy keycaps* covers;
`out/<layout>/coupon-clear.stl` is the clearance-hole row on its own and
`out/<layout>/coupon-hole.stl` is the switch-hole row, three diameters
engraved, on a plate at the real `PLATE_T` -- a Choc v2 clips into that
thickness, so a thicker test piece would answer neither half.

`out/<layout>/coupon.stl` is 68 × 46 mm and takes about twenty minutes.
It exists because a few numbers in `params.py` are things only a printer
can settle, and getting them wrong costs a two-hour reprint:

| Test | What it settles | Status |
|---|---|---|
| switch into the square hole | `SWITCH_HOLE` | **settled at 14.00 on a Choc v2** — all three swept holes take the switch and 14.00 is the one that grips. It won at the bottom of the sweep, so tighter was never printed; the direction of better is tighter and a hole that grips is the whole requirement. `out/<layout>/coupon-hole.stl` asks this on its own, at the real `PLATE_T`, since the plate's thickness has to hold the clips too. The 14.15 above it is the **MX** answer from the three-board case and does not carry over: 13.95 nominal plus this machine's 0.15 hole shrink predicted 14.10, and 14.00 is what grips, so the shrink is not one number across features |
| M3 self-tapper into four pilots, Ø2.50 to Ø2.95 | `PILOT_DIA` | **settled** — 2.95 bites without a fight; 2.50 is the tight one the built case has |
| M3 dropped through four clearance holes, Ø3.40 to Ø3.85, over two transitions | `SCREW_CLEAR_DIA`, `CLEAR_CHAMFER` | **settled, and confirmed on a printed plate** — 3.70 with a 0.60 chamfer is the smallest that comes out clean and falls through |
| standoff + peg against a real NeoKey hole | `PEG_DIA`, standoff height | **settled** — the built `inline` case seats the board flat on Ø2.30 pegs |

`PILOT_DIA` was the last one open, and the only one the coupon could
still save a reprint on: it is the guess that fails destructively. So it
is the one test the coupon runs more than once. `PILOT_SWEEP` puts a post
down for every candidate, each engraved with its own diameter, because
the answer is a feel rather than a measurement — the screw that goes in
too easily and the one that needs a fight only separate side by side,
same screw, same plastic, minutes apart. Driving an M3 into all four
picked 2.95.

Two things about that answer are worth carrying. It is **not** where the
arithmetic pointed: 2.95 prints as ~2.80 here, or 0.93× major, against
the 0.83× the tables want. The tables do not know this screw or this
plastic. And it won at the **top** of the range, so the diameter that
strips was never found — **and is deliberately not being looked for**,
because finding it means driving screws into posts until they fail and
the answer changes nothing. 2.95 works. The failure mode is still real:
this number does not split a post on the first turn, it lets go on the
third time the case is opened. If one ever does, re-run the sweep
downward from 2.95.

`CLEAR_SWEEP` is the same idea pointed at the other end of the same
screw, and it took the longest to answer. Its row is a pad raised to the
bottom plate's real `BOTTOM_T`, not the 1.6 the rest of the coupon is:
how free a hole is depends on how many layers it passes through, and it
is the 12 that ships. The counterbore is on the **bed** face, where
`bottom()` puts it, so the through-hole starts 1.00 up and never meets
the squashed first layer — printed the other way up, the coupon would
read tighter than the plate it stands in for and the answer would be
wrong in the safe-looking direction. The labels are on that same face and
mirrored, so the side you read is the side the screw goes in. **Turn the
coupon over for this row.** The right hole is the smallest one a screw
falls through under its own weight while its head is still fully caught
by the counterbore.

When the clearance row is the *only* thing open — which is where this
sits today — print `out/<layout>/coupon-clear.stl` instead. Same holes,
same pitch, same relative positions, on a 57 × 28 × 2.4 pad of its own:
minutes rather than the full coupon's twenty, and no switch-sized hole
spent on a fit that was settled months ago. It shares the row with the
big coupon rather than restating it, so the two cannot drift.

It prints the row **twice**, and that is what settled the number. The
first one printed came back with filament hanging in every bore, and the
geometry says why: the counterbore is a Ø6.10 void and the hole above it
was Ø3.55 at the time, so the layer closing it is a ring 1.275 mm
wide printed over air, all the way round. It sags, and what it sags into
is the top of the hole. **The built bottom plate has exactly this
feature** — the coupon did not invent it, it made it visible — which
means it is a better candidate for why the screws are guided rather than
cleared than the 0.15 hole shrink is.

Sweeping the diameter alone cannot separate those two explanations: it
would find a diameter that works and leave the reason unknown, which is
the same answer a wrong theory gives. So the rows differ only in the
transition — `C0.00` is the plate as it shipped, `C0.60` puts a 45° cone
above the counterbore. **Do not add supports** — the plate prints without
them, so a supported coupon stands in for nothing.

**Both explanations were right, and neither was the variable.** The eight
holes sort perfectly by the width of the ring left unsupported over the
counterbore, which is `(SCREW_HEAD_DIA - dia) / 2 - chamfer` and which
neither the diameter nor the chamfer sets on its own:

| ring | holes | result |
|---|---|---|
| 0.525, 0.600 | 3.85 and 3.70 at `C0.60` | clean |
| 0.675 | 3.55 at `C0.60` | a little sag |
| 0.750 and up | 3.40 at `C0.60`, all of `C0.00` | filament in the bore |

So **0.60 is this machine's limit for an annular ceiling printed over
air** — `CLEAR_RING_MAX`, a constant about the printer in the same way
`SWITCH_HOLE`'s 0.15 shrink is, and it re-measures with it. The plate now
runs Ø3.70 with a 0.60 chamfer, which lands exactly on that limit. 3.85
also passes and was not taken: it buys nothing and costs 0.075 more of
the seat.

That ring is the one dimension in the case squeezed from both ends — it
is *also* the flat the screw head bears on — so `build.py` checks it
against a maximum as well as a minimum, the only clearance here that
gets both.

To re-settle any of it after a filament or nozzle change: print the
coupon, drive a screw into each post, drop one through each hole, set the
numbers to the smallest ones that pass, rerun `build.py`, print the real
thing. The coupon carries the real features at their real sizes — the
plate is 1.6 mm and the post is whatever that layout's post is, 7.8 mm
inline and 13.5 mm stacked — so a fit that works here works in the case.

## Dummy keycaps

The wrk. MX Pure set is ordered and is not here, so `out/choc/keycap.stl`
is a blank 1U to press in the meantime — 0.64 cm³ each, six of them.
It carries the photographed cap's envelope, 18.40 square on a 4.20
corner, so the swap when the real ones land changes the plastic and
nothing else.

**The mount is measured rather than looked up.** Choc v2 is sold as
MX-compatible and its stem is not a bare cross: it is an MX cross
standing *inside* a ring, and the cross does not stand proud of it, so
the only way onto it is a boss that goes down the bore. Every number
below was read off `ref/choc-v2.step` with a boolean probe, and
`build.py` reads all twelve back out of that file on every run — a
re-exported or swapped switch model goes red there instead of quietly
redefining what the cap mounts on.

That dependency is **hard**: `build.py` exits if `ref/choc-v2.step` is
not there rather than falling back to the constants, so a fresh clone
runs `sh ref/fetch.sh` before it can build anything. `product.py` has
always needed the same file, but only for a picture — the difference now
is that a missing reference is a case that will not build.

| | size | switch-local z, 0 at the PCB top |
|---|---|---|
| cross, tip to tip | 4.00 | 0.20 → 8.60 |
| cross arm, body | 1.20 thick | the top 0.10 is chamfered off |
| eight retention ribs | 1.30 over them | 4.10 → 8.39, at 1.20 out the arm |
| ring | Ø6.50 outer, Ø5.50 bore | 3.60 → 8.60 |
| fixed housing, top face | — | 5.30 |
| mouth the ring travels through | Ø6.60 | at 5.30 |

Two things follow from the cross tip and the ring rim being the **same
plane**. The cap seats on the *ring*: a Ø6.50 rim resists rocking that
8.6 mm² of cross tip cannot, so the bore is sunk `CAP_SOCKET_OVER` 0.10
past that plane and the cross never carries the press. And the pad that
lands on it has 1.10 of window to live in — wider than the ring's bore
so it bears on something, narrower than the housing's mouth so it can
never come down on the lip. Ø6.00 leaves 0.25 and 0.30, and neither
clears the 0.25 the margin table asks of everything else, so that pair
is checked on its own terms rather than by loosening the table.

**The arms are not 1.20 and that is the whole fit.** Each carries a rib
on each flat — eight of them, 0.05 proud, about 0.10 wide, running
nearly the stem's full height — so what a slot actually meets is 1.30.
They were found by a boolean and not by reading: every probe of the arm
returned 1.200, because a 0.10-wide feature fits between probes, and the
first version of the cap fouled the switch by 0.075 mm³ with no
explanation until the eight pieces of that interference were listed
individually.

`STEM_CLEAR` is measured from the arm **body**, so the number doubles as
how much rib is left alone: 1.20 + `STEM_CLEAR` against 1.30 is the
squeeze, 0.05 per side at 0.00 and none at 0.10.

**Settled at 0.00, on two printed sweeps and then on the caps
themselves** — six printed at 0.00 go onto the switches and fit really
well, which is the claim the tokens could only stand in for.

The sweeps that got there. The first — 0.10, 0.15, 0.20, 0.25 — came
back *0.10 grips, the other three are loose*, and that
is the ribs answering: 0.10 puts the slot exactly on them and every
looser entry clears them by 0.025 or more, which is a cap held by
nothing. So that whole sweep sat at or above the ribs and could only
find the top of its range. The second ran downward — 0.00, 0.04, 0.07,
0.10, the last kept in as the control, because a feel only separates
from another feel side by side, same plastic, minutes apart — and 0.00
is tight enough.

That is the fourth number in this case to win at the **bottom** of what
was printed, after `SWITCH_HOLE`, `PILOT_DIA` and its own first sweep,
**and it is the first one where the bottom is not an untested edge.**
Those three ran off the end of what had been printed, and each carries a
note saying re-run downward from here if it ever disappoints. This one
has a mechanism under it: 0.00 puts the slot on the arm body, so it
squeezes the ribs flat and nothing else, and below it the bore stops
squeezing ribs and starts eating the arm — a different thing to be
doing, and one `build.py` refuses. There is no third sweep to run.

Print shrink sits underneath all of it — this machine pulls a hole in by
0.05 to 0.15 — so the slot arrives narrower than 1.20 and the ribs give
the difference. That is also the failure mode left: a cap that comes
loose after a few pulls means the ribs were shaved rather than
deflected, and the answer is to come **up** from 0.00, because down is
not available.

`out/choc/coupon-stem.stl` is four tokens, engraved, each with the pad
and boss at the heights the cap has them so the slot prints in the same
air. It stays in the tree for the next filament or nozzle: press each
onto a switch, keep the one that grips, set `STEM_CLEAR`, rebuild. They
are four separate tokens on purpose — at 19.05 a single bar would engage
every switch it spans at once, and the question is one slot on one
stem.

**So the interference check had to be split**, because "the bore must
not touch the stem" stopped being true the moment the ribs were known —
the bore is *supposed* to squeeze them. The arm body is a wall and is
checked at 0.000; the squeeze is printed as a **reading rather than a
guard**, since no value of it is wrong in the model and only a pressed
token can say. The envelope that separates the two is built from
the ribs' own measured extent, and what keeps it *on* them is the
read-back, not the envelope: moved 0.50 out the arm it still caught
0.174 mm³ of the cross's flare and looked healthy, the squeeze silently
read 0.000, and the only thing that went red was `arm over a retention
rib` at 1.200 against 1.300. An envelope that misses reads exactly like
a slot that clears.

The cavity's corner radius is **2.00 and deliberately not**
`CAP_R - CAP_WALL`. Rounding a corner pulls the boundary inward along
the diagonal, and the diagonal is where the switch is widest — its
15 × 15 base stands 1.50 proud of the plate, so the skirt passes it at
bottom-out. At 3.00 the cavity reached 10.071 against the base's
measured 10.200 and the two fouled by 0.082 mm³; 2.00 reaches 10.485.
The cost is a corner wall of 0.79 instead of 1.20, which is two
perimeters on a blank.

Watched failing, because a guard nobody has seen go red is not a guard:
the bore against the real cross 3.032 mm³ at `STEM_CLEAR` −0.20, the cap
into the shell 70.851 mm³ with the ride cut to 2.20, into its neighbour
22.725 mm³ at `CAP_XY` 19.50, into the housing the 0.082 above, the
missing seat 0.532 mm³ with the pad at Ø5.00, the bore itself 7.474 of a
wanted 31.409 mm³ when it was cut in the wrong direction — that one was
a real bug, and the volume is what found it — the sweep's four tokens
identical, and the STEP read-back at `STEM_TOP` 8.50.

It prints top face **down**, like the shell: the cavity opens upward,
the pad and boss stand up out of it, the bore opens up, and there is no
overhang anywhere in it. No supports, and the bed face is the visible
top.

## Cable, per layout

**The earlier device.** Both layouts here are gone from the source, and
this case has no Qwiic cable at all — one board, with the keys, the
pixels and the MCU on it — so nothing below applies to it. The whole
question went away with the boards rather than being answered somewhere
else.

**`inline` uses the 50 mm cable you already have.** The two sockets end up
facing each other 12 mm apart, so the run is trivial — but 50 mm is the
shortest Qwiic cable anyone sells, and the other 35 mm has to be folded
into the gap. It fits; it is not tidy.

**`stacked` does not.** Stacking puts the sockets about 8 mm apart
vertically and at opposite ends of the case; the run is roughly 60 mm
before bends. Either:

- a **100 mm STEMMA QT / Qwiic cable** — keeps the device's no-soldering
  property, which the main README argues for at length, or
- **soldered wires** to the NeoKey's `JP1`/`JP5` headers. Nothing in the
  case needs changing for this: wire takes less room than a plug, and the
  channel is sized for the plug.

## Build

    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python build123d trimesh matplotlib
    .venv/bin/python build.py      # must end in "all checks passed"

There is **one layout now**, `choc`, and it writes into `out/choc/`.
`MPAD_LAYOUT` is gone with the two it used to select: `params.OUT_NAME` is
the name, and it is not a switch. The `inline` and `stacked` directories
under `out/` are the older device's, kept because they are the only
remaining form of a case that is physically in use — the source that
produced them was removed with the layouts.

    .venv/bin/python section.py    # sections.png -- cut through the stack
    .venv/bin/python render.py     # *.png -- shaded views
    .venv/bin/python product.py    # product.png -- assembled and exploded

    .venv/bin/python webgl.py dump
    .venv/bin/python webgl.py page                    # -> out/viewer.html

**The viewer is live at <https://saqoosha.github.io/Canopy-MacroPad/>**,
served off the `gh-pages` branch, which holds nothing but this one file
as `index.html` plus an empty `.nojekyll`. It is a copy, so it goes stale
on its own — regenerate `out/viewer.html`, then republish it:

    blob=$(git hash-object -w case/out/viewer.html)
    empty=$(printf '' | git hash-object -w --stdin)
    tree=$(printf '100644 blob %s\tindex.html\n100644 blob %s\t.nojekyll\n' \
             $blob $empty | git mktree)
    git branch -f gh-pages $(git commit-tree $tree -m 'Publish the case viewer')
    git push -f origin gh-pages

Plumbing rather than a checkout on purpose: nothing here touches the
working tree, so there is no orphan branch to get stranded on and no
chance of committing the rest of the repo onto a branch that should
carry one page.

`out/viewer.html` is the one to actually look at. `product.py` sorts
triangles by distance and paints them back to front, which is the only
depth test matplotlib offers and is wrong wherever two surfaces
interpenetrate or one is concave — most of this case. The viewer hands
that to a GPU depth buffer and the artefacts disappear. Both layouts,
orbit, explode, per-part visibility, one self-contained file with the
geometry embedded as int16.

It has **orthographic projection and Top / Front / Left presets**, which
is what makes it usable for reading the design rather than admiring it —
in ortho a height is a height, and the plan view puts the four keys on
one line with no foreshortening to argue with.

Four things in it were not obvious:

- **The canvas's own antialiasing does nothing here.** `antialias: true`
  only covers what is drawn straight to the canvas, and every pass goes
  into an offscreen framebuffer first. The targets are supersampled and
  box-resolved in the composite instead — simpler than multisampled
  renderbuffers with a blit per attachment, exact rather than pattern-
  based, and it antialiases the transparent edges too. It costs real
  fill, so the frame is only redrawn when something actually moved.

- **The case has a glass mode**, which is the whole reason the viewer is
  worth having: the pad is only ever *used* shut, and exploding it to see
  the inside answers a different question. Turning the two printed parts
  translucent needs nothing special once transparency is
  order-independent — their near walls blend over the boards and their
  far walls fail the depth test against those same boards and drop out.

- **Transparency is order-independent** (weighted-blended, McGuire &
  Bavoil), not sorted. Sorting by object cannot be right here — a
  keycap's skirt and the switch housing inside it interpenetrate, so no
  ordering of that pair is correct from every angle. The canonical weight
  function had to be replaced: it is tuned for many nearly-transparent
  fragments, and at these alphas every fragment pinned to its clamp and
  the accumulation degenerated into a flat average — four keycaps
  rendered as one fog.
- **The boards are bare slabs, and that is a trap**, so there is a
  *Clearance envelopes* toggle that draws what `build.py` actually
  booleans against: hot-swap sockets, both STEMMA receptacles with a plug
  mated, the USB shell and its overhang, the tact buttons. What you look
  at and what was verified are otherwise two different models, which is
  the same gap that produced most of the bugs listed above. The envelope
  has the **board subtracted out of it** — the check's stand-in and the
  viewer's slab are the same board, same outline, same Z, and drawn
  together they were coplanar everywhere and tore at each other. What is
  left is exactly what the check claims *beyond* the board, which is the
  more useful picture regardless.

`product.py` and `webgl.py` are the only files here that are not
load-bearing. Their keycap and switch shapes are eyeballed, nothing checks
them, and no dimension in either feeds anything else — they exist so the
pad can be looked at. The four keys wear the status colours from the main
README, since what this device is *for* is the one thing a picture of it
should say.

There is no hole over BOOT or RESET in either layout. They are needed
once, to write a CircuitPython UF2; after that a firmware update is a
file copied to CIRCUITPY. Four screws is a fine price for something done
once. The buttons are still modelled, and nothing is allowed to press on
them — widen a rail over one and the interference check reports 68.9 mm³
and fails.

`build.py` ends in a report, and the report is the point. It re-derives
the stack, prints every clearance that is not implied by something else,
then booleans both printed parts against stand-ins for the boards, the
switches and a mated Qwiic plug — and against each other. Anything left
over is a case that cannot be assembled. **Do not print on a run that
says `SOMETHING IS WRONG`.**

`out/*.stl` are already lying the way they print — the shell comes out
plate-face down. Do not rotate them.

## What the checks have actually caught

Every one of these is from the **earlier device's** model — the QT Py, the
NeoKey and the two breakouts — because that is where the checks were built
and where they earned their keep. The parts are gone; the lessons are the
reason the checks exist at all, and they are why this case's stand-ins
model mated plugs and real component faces rather than boxes. What this
case's own checks have caught since is recorded in the repository's
`AGENTS.md`, under "Editing the case".

Not a hypothetical list. Every one of these was in the model and none was
visible in a render. Three of them are the *same* mistake in three
different places — a wall that fits the board and seals off the socket
its cable plugs into — which is why every stand-in here models mated
connectors and not bare receptacles:

- a QT Py pocket wall standing 1.6 mm inside the NeoKey.
- **that pocket's front wall sealing off the socket the Qwiic cable plugs
  into.** The board fitted; the cable could never have reached it. This is
  why the stand-in includes a *mated plug* rather than just a receptacle —
  the receptacle alone fits fine.
- **the same thing again after the redesign**, in the bottom plate's front
  stop, with the socket now facing down instead of forward.
- retaining lips landing on the BOOT and RESET buttons, which stand 1.94
  proud of the face they are on and clear the rails by 0.2.
- the pocket's side walls running 1.4 mm into the shell's back wall —
  caught by the shell-versus-bottom-plate check on the first run after it
  was added.
- an M3 screw post landing on the mated Qwiic plug — **while the margin
  check that was supposed to prevent exactly that read green**, because it
  measured to the NeoKey's board edge and the plug sticks out past it. The
  boolean caught what the arithmetic missed; the arithmetic was corrected
  afterwards.
- the NeoKey's support columns growing with the screws, because they were
  sized off `POST_DIA` and are not screws at all. They have their own
  `COLUMN_DIA` now.
- **two bottom-plate columns standing through a breakout's hot-swap
  socket** — and this one the checks did *not* find, the assembled part
  did. The stand-in drew the socket as one box around its body, so it
  missed the solder wing off each end; and the back face was never
  mirrored for the fact that the board is turned over to put its switch
  side up, so the whole of it sat on the wrong side. Both are fixed at
  the source: `BREAKOUT_BACK_PARTS` is every part on that face as the
  STEP has them, mirrored once on the way into case space.
- **the whole board stack sitting 0.16 too low**, the same disease one
  level up. The deepest thing under a board is not the hot-swap socket at
  1.85 but the STEMMA receptacle at 2.96, and that was modelled on the
  other face where nothing had to clear it. `SOCKET_CLEARANCE` had been a
  hand-written 2.80 reasoned from the socket; it comes from
  `UNDER_BOARD_MAX` now. The printed case closes on a NeoKey pressed into
  the bottom plate — too little to feel, enough to strain the boards, and
  invisible to every check because the model had the part on the far
  side. The case grows 0.56 to fix it.
- **a NeoKey support column standing through the middle of the QT Py** in
  `stacked`, 116 mm³ of it, the moment the key field grew to three
  boards. The NeoKey stopped starting at the field's left edge, so its
  first pair of mounting holes landed at case `x = 0` — where the QT Py
  had always sat. Nothing about the change looked like it was near the
  QT Py; the boolean is the only reason it was not printed that way. The
  QT Py now sits at `x = 19.05`, the centre of the widest gap the columns
  leave, and USB-C is no longer centred on the back wall as a result.
- **the bottom plate blocking the USB plug** — and this one the checks
  did *not* find, a person looking at the render did. The opening's lower
  edge lands exactly on the seam between the two printed halves, and the
  plug's overmold hangs below it, so the plate stopped the plug about a
  millimetre short of seating. Nothing flagged it because the stand-in
  modelled the *receptacle* and not the plug that has to reach it — the
  same omission the Qwiic sockets had already taught three times. The
  plug is modelled now, both halves are relieved to plug size, and the
  check fails without either relief.
- the USB-C opening and its envelope both drawn as rectangles. A USB-C
  shell is a stadium — fully rounded ends, radius half its height — so
  the square envelope was claiming four corners that do not exist, and
  the square hole was the wrong shape to put it through. Both are
  stadiums now, built from two circles and a rectangle rather than a
  rounded rectangle, which cannot express a radius of exactly half the
  height.
- a sharp-cornered switch fouling a 0.3 mm plate-hole corner. The spec
  allows 0.3 max; the model gives way to 0.2 rather than the mock being
  softened, so the check keeps meaning something.

And one thing the checks did **not** catch, recorded because the mistake
was in believing they had. A Ø5.0 standoff between two keys was reduced to
Ø4.2 on the stated grounds that the check flagged it. It never did: 5.0
clears a 14 mm switch body by 0.025 mm a side, and the 0.009 mm³ that was
blamed on it came from the plate-hole corner instead. 4.2 is still right —
0.025 is not clearance on a printed part, it is the tolerance — but it is
a judgement call, not a finding. Fault injection is what settled it: at
Ø6.0 the check reports 1.016 mm³ and fails, so it does fire, just not
where it was credited.

## Stack, in `stacked`

**The earlier device.** This layout is gone from the source; the numbers
below describe a case that can no longer be rebuilt. Kept because the Z
argument is the same argument this case has, one board fewer.

This one is the `stacked` layout, which is where the Z fight is —
`inline` puts the QT Py beside the keys instead of under them and comes
out 11.8 tall against 17.5. Z is measured from the outside of the bottom
plate. Read it bottom-up — the USB-C shell is the lowest thing in the
case now, and everything above is stacked on that one clearance.

```
 0.00  ├── bottom plate                    2.40   12 layers; the M3 button
 2.40  ├── floor                                   head's bore eats 1.0
 2.80  ├── USB-C shell                     4.20   hanging off a board that
 6.00  ├── QT Py PCB                       1.57    is lying face down
 7.57  ├──   its underside parts           1.10   now pointing up
 8.67  ├──   air                           0.40
 9.07  ├── hot-swap sockets                1.85
10.92  ├── NeoKey PCB                      1.57
12.49  ├──   gap                           3.40
15.89  ├── plate underside
       │   plate                           1.60   8 layers at 0.2
17.49  └── plate top                              → 5.00 above the PCB, per spec
```

Depth is set by the QT Py, not the NeoKey: 20.70 of board plus 2.50 for
the mated Qwiic plug ahead of its socket, plus two walls. Packing it
tighter is possible on paper — 25.99 with the board turned 90° into a
corner — and unbuildable. A screw post has to miss the NeoKey above it
*and* the bottom plate's own columns, which leaves only the two end bays,
and an end-mounted QT Py fills one of them. 1.6 mm of depth was the
cheaper thing to spend.

## How it holds together

**The two halves overlap rather than butting.** The plate's top 1.20 is a
tongue inset 1.00 a side and the shell's walls carry on down beside it.
It aligns the halves and puts whatever gap is left **inside** the joint
instead of on the outside, which is what the complaint was: a butt joint
158 mm long with screws only at the ends closed 0.2 proud at the centre,
and slack above the boards took that to 0.1 and no further -- the rest is
the parts not being flat off the bed.

**There were barbs too, and they are gone.** A snap on the inside of the
skirt, dropping into a groove round the tongue, swept 0.30 to 0.70 of
reach on its own coupon. All four printed too weak; 0.70 was the best of
them and still did not lock. Both complaints -- hard to fit, does not
hold -- are one fault, and it is arithmetic rather than a number wanting
another round: **the skirt is not a spring.** At 0.90 thick over a 1.20
free length, even the shallowest hook asks it for 19% surface strain
where PLA yields near 2. It never bent; it was forced.

A cantilever that deflects 0.40 within 2% wants about 5 mm of length and
this plate is 2.40 thick, so no hook in this geometry can work. **If the
centre ever lifts, the next thing to try is a magnet pair under the
boards, not a plastic spring.**

**And the far end is hooked.** Both screws sit in the left bay, so 145.50
of a 151.00 case had nothing on it. At the right end the seam climbs to
`END_HOOK_SEAM_Z`, the plate's wall carries on up inside the shell's, and
a horizontal boss off that wall drops into a slot cut right through. It
is not friction: the boss is captured, so that end cannot lift. **Ends
only, and the reason is the assembly motion rather than strength** -- the
boss is engaged by moving the plate along x, right end in and left end
swung down, and on a long side the same boss would need the plate to move
in y at the same time, which the other end forbids.

The slot goes through the outer face on purpose. A blind pocket had to
share the skirt's 1.00 with the skin outside it and burst through anyway,
and through you can see from outside whether the hook engaged -- which is
otherwise unknowable once the case is shut.

`END_HOOK_FIT` is 0.40, from the coupon. The full 151 mm plate at that
number still had to be forced -- the boss would not go fully in, and
forcing it bowed the plate.
**`END_HOOK_BACK` is 1.60**, the square on the back of the C -- under
the boss, above the notch -- and it runs the **whole depth**, not just
the 3.00 hook bands. A band-only cut left the slab standing between the
bosses; the shell hits that and the boss never seats. That includes
under the USB opening. The outer lip below the seam stays; looking into
the port you see the C, not a second slit through the bottom.
**`END_HOOK_RIB` is 1.60** inboard, so the boss is still held.

**`COLUMN_SLACK` is 0.40.** The first bottom with the C seated closed
with a hair under 1 mm of seam until you pressed: the columns ran to
the board and the shell's 0.20 slack sits above it, which does not
help. The reprint at 0.40 closes, and on the seam Saqoosha's words are
*"i still can see tiny gaps but its ok"* — gaps, plural, visible, no
number given and none invented here, and **acceptable**, which is what
settles 0.40 rather than leaving it open. Reasoning rather than report,
and worth separating: that says 0.40 fixed the *failure* — the ~1 mm
that needed pressing — and did not close the seam to invisible. If an
invisible seam is ever wanted, this record says 0.40 is not the number
that gets there, and it is a different question from the one that was
being asked.
`out/<layout>/coupon-hook.stl` is the sweep that asked the fit (0.10 to
0.40, four pairs of whole case ends so both hooks have to find both
slots at once).

**Open: a fillet where that wall meets the plate.** The first coupon
printed and broke in the hand -- 1.00 thick, 2.00 tall, with a 0.90 boss
on the far side, a cantilever loaded at the tip, and nothing in the model
had an opinion about that. The coupon's wall was widened to survive
handling; the case's is still `END_HOOK_L` long. A fillet can only go
inboard: outboard the shell's skirt fills the root to 2.40 and its own
material carries on to the slot at 2.60, so there is 0.20 there and the
shell is in it. Inboard is empty cavity, with the board's edge stopping
at 73.30 and its underside at 5.70. Ø1.00 takes the root section from
1.00 to 3.00 mm2.

**Deliberately after the fit, not before.** The fillet is inboard of the
wall and the fit is a clearance between boss and slot, so the two do not
touch -- but changing the case mid-sweep would mean the coupon and the
part had stopped being the same thing, which is the one property that
makes this coupon worth more than a drawn one.

**The wires have a trench, and the case grew for them.** Five have to
cross the whole field, and the first wired unit would not lie down: the
space under the boards was 3.36 mm, of which a hot-swap socket took 1.83
and a STEMMA receptacle 2.96, leaving one usable lane 5.70 mm wide.
`UNDER_BOARD_AIR` went from 0.40 to 1.40 on that evidence, so the gap is
**4.36** and the whole case 13.33 instead of 12.33.

The extra millimetre changed the shape of the problem rather than its
size. **A wire passes under something only if that thing leaves more
room than the wire is thick**, so at 0.40 under a receptacle the
receptacles were walls and the near half of the board was unreachable.
At 1.40 they are not, and the lane opens from four wires abreast to
nine. The channel is cut to that whole width — 11.20 mm — because 1.40
against a 1.30 wire is 0.10 and no harness should be laid on that; sunk
`WIRE_CHANNEL_D`, a receptacle leaves 2.60 instead. The Qwiic cable
hangs in that same near half and now has somewhere to sit for the first
time.

It runs under the boards and stops there, because that is the only place
the depth buys anything and because past the boards are the screws. A
trench is invisible to the interference check: over a counterbore it left
0.20 mm of plate spanning the bore, and beside it 0.45 mm of the shell's
post stood on air, both with every boolean at zero. What catches it is a
boolean run the other way — the ring the screw head bears on, built as a
solid and with the plate subtracted from it, so what is left is plate
that is not there. Two plan-view margins sit beside it for the distance
that measurement cannot report.

Where the channel meets something coming the other way it has nowhere
better to be: both left feet's recesses rise 0.50 under a channel going
down 1.20, leaving **0.70 mm** of plate over an Ø8 pocket. Ø8 feet at
y ±5.99 in a 25.99 mm case cannot clear a channel reaching ±5.60, and
the feet are where they are so the case does not rock. It is a thickness
rather than a hole, so no boolean sees it and `plate left under the wire
channel` is what holds it.

**Nothing screws through either PCB.** Four standoffs come down off the
plate, each ending in a Ø2.3 peg that drops into the NeoKey's M2.5 holes
and fixes it in X and Y; the bottom plate's columns push it up against
them. Four M3 button-head self-tappers into the corner posts hold the two
halves together, and that is every fastener in the design. The 2.5 that
appears next to the NeoKey is that board's own mounting hole, which takes
a peg and never a screw — the two threads are unrelated.

That much is both layouts. **Who carries the QT Py is not**, and it is
the only thing the two disagree about.

In `stacked` the bottom plate carries it alone, because nothing above can
reach it — the NeoKey covers the case wall to wall. It rides on two rails
under its component-free margins and slides forward under two lips,
entering through the same back-wall opening its USB-C ends up in. It is
**face down**, and that is the whole reason it is face down: take the
bottom plate off and BOOT and RESET are facing you. Face up they would
point at the underside of the NeoKey across 2.2 mm of air, and reaching
them would mean getting the QT Py out first.

In `inline` it sits beside the keys in a shell pocket, **face up**, held
down by two pinch bars on its clear margins with the plate closing
underneath. There is nothing above it to hide from, so face up costs
nothing and puts the USB-C out the right end.

Switches go in **from the top, through the plate**, after the case is
closed — the hot-swap sockets mean they stay removable without opening
anything, and the plate keeps them square while they seat.

## Assembly order

Different in each layout, because a different half carries the QT Py.
Both wire up before they close, which is the price of the depth.

**`inline`** — the shell carries both boards; the bottom plate only holds
them up.

1. Drop the QT Py into the shell's pocket, **face up**, USB-C first into
   the right-end opening, so the pinch bars land on its two clear
   margins.
2. Plug the Qwiic cable into its socket. It faces back toward the NeoKey
   across the 12 mm gap, and there is a notch in the pocket wall for
   exactly this.
3. Drop the NeoKey onto the shell's four pegs and plug the other end into
   its **right** socket — inline is right-handed, the left one has a
   screw post in front of it.
4. Fold the cable's slack into the gap between the boards. It is 35 mm
   longer than the run; nothing is routed for you.
5. Close the halves, four M3 × 10 button-head self-tappers, four Ø8 feet.
6. Press the switches in through the plate. Keycaps.

**`stacked`** — the bottom plate carries the QT Py alone, because the
NeoKey covers the case wall to wall and nothing above can reach it.

1. Slide the QT Py into the bottom plate's pocket, **face down**, USB-C
   first through the back opening, under both lips.
2. Plug the Qwiic cable into its socket — it faces forward, into the
   2.5 mm strip ahead of the board.
3. Drop the NeoKey onto the shell's four pegs and plug the other end into
   either of its end sockets.
4. Route the slack down whichever end bay the cable came from and lay it
   along the floor. Both bays are open.
5. Close the halves, four M3 × 10 button-head self-tappers, four Ø8 feet.
6. Press the switches in through the plate. Keycaps.

## BOM beyond the boards

| Part | Qty | Note |
|---|---|---|
| STEMMA QT / Qwiic cable | 1 | 100 mm for `stacked`; the existing 50 mm for `inline` |
| M3 × 10 self-tapping, button head | 4 | into Ø2.95 pilots with a Ø3.40 lead-in, through Ø3.70 clearance chamfered 0.60; counterbored 1.00 so the feet still clear the dome |
| Ø8 × 2 rubber feet | 4 | 0.5 recess, so they stand 1.5 proud |
| PLA Basic | ~19 g | shell 10.6 cm³, bottom 7.9 cm³ |

## Slicer

Everything default except:

- **no supports**, and if it suggests them, stop
- top/bottom solid layers ≥ 5, so the 1.6 mm plate comes out fully solid
  rather than hollow with a skin
- the shell's bed face is the *visible top surface* — on a textured PEI
  plate it comes out matte, which is the finish this is designed around

## Deliberately not here

- **No tilt.** A wedge means the bottom is no longer flat, which means
  supports or a second setup, to fix a problem four keys do not have.
- **No BOOT/RESET port.** Removed on request, and it holds up: the buttons
  are needed once, to write a UF2, and four screws is a fine price for
  that. An uninterrupted plate is worth more than a paperclip hole. (Which
  button is which was never settled either — the QT Py schematic's net
  names did not resolve to designators.)
- **No routed cable channel.** The floor beside the QT Py is open and the
  cable can lie where it likes. A channel sized for a plug that has not
  been fitted yet is a guess with walls around it.
- **No second-board provision.** The end bays would take a daisy-chain
  cable out through a knockout, and a second NeoKey is a real item in the
  main README's future. Not built, because nothing needs it yet and a
  knockout that has never been used is just a weak spot in a wall.
