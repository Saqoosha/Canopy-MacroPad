# Canopy MacroPad — case

A two-part printed enclosure for the **custom MacroPad PCB** — one board,
six Choc sockets on 19.05, its own RP2040 and USB-C. Parametric, in
`build123d`; the way to change it is to change a number in `params.py` and
rebuild.
**One layout**, `choc`, and no switch to select it. `params.py` loads
`pcb/params.py` by path, so the board's width, corner radius, switch pitch
and pad positions are read rather than restated — the two files cannot
drift into disagreeing. It is printed, both halves, its
column heights settled on the printed parts, and the bottom that
`COLUMN_SLACK` asked for has been reprinted and fits. The model has since
grown the **slide latch** — ten small hooks along the long sides that
close the middle of the seam, the end hook multiplied — and the latched
case is **printed and working** at `SLIDE_FIT` 0.30 ("perfect" is the
word that came back from the desk). Six prints shaped it, and *The
slide latch* under *How it holds together* carries every turn and why.
The screws are gone -- the latch carries the case alone -- and with
them went the left bay that existed to hold their posts: the case is
**145.27 long now, 5.73 shorter**, and what remains of the bay is a
looks number -- 1.27 that makes the cap margin equal on the three
non-USB sides (3.795 from cap edge to case edge; the fourth side is
the electronics'). **The corners are the corner cap's, grown.** `OUTER_CORNER_R` is
7.995 -- the 3.795 cap margin plus the cap's own 4.2 -- so the case's
corner arc is concentric with the corner keycap's and the border wraps
it at a constant 3.795, straights and arc alike; the shell's top edge
carries `SHELL_TOP_CHAMFER` 1.20, which also serves as the flipped
print's first-layer relief (a 0.50 chamfer applied later inside a
try/except had silently failed at 1.20 -- the bed-inset probe reading
0.35 instead of ~1.2 is what told). The radius has a price paid at the
diagonals: the board's own corner and the case's arc fight over the
same space, and the corner wall is **0.65** -- all the material the
two leave between them, with `CAVITY_CORNER_R` 2.70 the most the board
permits. Less than that and the cavity pokes a slit hole through the
outer face (0.07 at the old 1.00 -- invisible to every interference
boolean, a hole shares volume with nothing); a four-corner leak probe
owns that class now, watched failing at 4/4 on the reproduced fault.

The **detent** pins home in x, and its second
shape is the one that works on a printer: a vertical round ridge on
the mid tab's pocket skin, parking in a notch cut into that eave's
outboard tip -- vertical features in both halves' print orientations,
immune to the slicing that smeared the first cut (a 0.40 bump raised
on the stair-stepped ledge slope, whose spring was also only the
plate's own weight: "theres no bit change"). The spring now is the
skin panel bending 0.15 -- ~1.5% strain, the barb arithmetic passed,
and the same felt force that expanded the shell at the 0.20 fit.
Slide home: drag, click in. Slide back: the same click in reverse, no
special gesture. Home pinned to +-0.30.

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

| | `stacked` | `inline` (default) |
|---|---|---|
| QT Py | under the keys, **face down** | right of the keys, **face up** |
| USB-C | back wall, low | right end |
| size | **135.7 × 27.6 × 17.49** | **158.6 × 25.99 × 13.33** |
| footprint | 37.5 cm² | 41.2 cm² |
| to the top of a keycap | 31.9 mm | **27.7 mm** |
| BOOT / RESET | open the case: they face you | open the case: unclip the board |
| who holds the QT Py | bottom plate, alone | shell from above, plate below |
| Qwiic cable | **100 mm**, down an end bay | **50 mm**, but with 35 mm of slack to fold into a 12 mm gap |
| handedness | either end takes the cable | **right-handed**: the cable can only come off the right socket |

One plate spans all three boards, which is why they are one field and not
three pockets: `KEY_FIELD_W` is `2 × 19.05 + 76.20 = 114.30`, the boards
are the same 21.59 deep and the same 1.570 thick, and the switch pitch
carries straight across the seams with nothing to tune.

`stacked` was the compact one and `inline` the low one. Neither was
strictly better — a shorter pad sits closer to keyboard height, a smaller
one takes less desk.

![The four-key inline case, closed with keycaps on, and open with the
NeoKey and the QT Py seated in the shell above the bottom
plate](images/inline-built.jpg)
`inline` is the layout that exists as a physical object, and it has been
printed twice: **the four-key case in the photograph, and the six-key one
that replaced it** — printed, wired, closing, and the pad in use. The
photograph is the older one; the picture of the six-key unit is the
wiring shot in the main README, shell turned over.

The four-key print took four numbers out of the guess column. It printed
flat, without supports, and closed on the first attempt: `SWITCH_HOLE` at
14.15 (a Durock Ice King seats correctly), `PEG_DIA` at 2.30 (the NeoKey
drops onto the pegs free, with a little play), `QTPY_SLOP` at 0.40, and
the USB-C opening, where a real cable seats fully with about 1 mm around
its housing — worth knowing, because `USB_PLUG_W/H` were never measured
off anything.

One thing the part says that the model does not. The M3 has now been
driven into a post: it goes, but hard enough to be the first thing
anyone says about the part. That
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
That is the last *printed fit* on this case to stop being a prediction —
every hole, post and pocket has now been felt against the real part.

**Then the six-key unit was wired, and three things came back that no
check could have asked for.** Each one is a fact about assembly rather
than about geometry, which is exactly the class the boolean cannot see:

- **The wires would not lie down.** `UNDER_BOARD_AIR` went 0.40 → 1.40 on
  that evidence, so the gap under the boards is 4.36 and the case 13.33
  instead of 12.33. It bought a shape rather than a size — see *The wires
  have a trench* below.
- **A breakout wants no locating peg.** A plate-mount switch clips into
  the top plate and its pins go into the board's socket, so the switch is
  what ties the board to the plate; the supports set its height and the
  shell presses it down. Removing the pegs also removed the only feature
  that made a breakout look like it had a wrong way round.
- **The field's outer left edge had nothing pressing on it.** A seam is
  between two boards, so the leftmost breakout was held on one side only.
  `EDGE_RIB_W` at 1.50 is the plate reaching down along that edge —
  more bearing area than the 4.20 circle that will not fit there anyway.

And one that was arithmetic all along: the first six-key unit closed with
0.2 of gap at the centre of the seam, because the board stack was holding
the halves apart. `BOARD_CLAMP_SLACK` at 0.20 stops the standoffs acting
as jacks; the rest is the parts not being flat off the bed, which is what
the seam step is for.

**One entry came off this list by being done again.**
`QTPY_STEMMA_NOTCH` at 1.00 was written up as tight — "the plug goes in,
but a reprint would want 1.5–2.0" — on one impression from one print.
Several builds later the plug goes in every time and nothing about it is
a problem, so 1.00 is settled and the reprint knob is not needed. Worth
keeping as a shape rather than a number: **a fit is a claim about a
distribution, and one assembly is one sample.** The numbers on this case
that held up were all felt more than once, side by side or minutes
apart; this one was not, and it read worse than it was. Nothing checks
it either way — `mock.py` builds the mated plug at the receptacle's own
6.00 width, so the plug's width is assumed rather than measured and no
boolean has an opinion.

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
| a printed cross socket onto a real stem | `STEM_CLEAR` | **settled at 0.00**, across two sweeps and then on the caps themselves. `out/<layout>/coupon-stem.stl` asks it alone, four tokens at 0.00 to 0.10; what the number is really against is the arm's retention ribs, and *Dummy keycaps* carries why 0.00 is a floor rather than an untested edge |
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
plate is 1.6 mm and the post is whatever that layout's post is, 9.3 mm
inline and 13.5 mm stacked — so a fit that works here works in the case.

## Dummy keycaps

The wrk. MX Pure set is ordered and is not here, so `out/choc/keycap.stl`
is a blank 1U to press in the meantime — 0.65 cm³ each, about 0.8 g in
PLA, and six are printed and on the switches.
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

**The tube is closed on a 0.4 nozzle at boss 5.40, and the number was
found by two failed prints.** At 4.90 the tip walls are 0.30 and
slicing drops them (the six early caps are tip-less and still grip --
the ribs do that); at 5.20 the tips printed but **floated,
connected to nothing**, because the thin spot is not the tip's centre
but the arm's corners, where a cross meets a circle at 0.37. The rule
that fell out is now a margin -- `tube wall at the arm corners`,
anything under ~0.44 is a slicing casualty -- and 5.40 clears it all
round: 0.468 at the corners, 0.55 at the tips, with the mouth gone
width-only (0.15) so its own corners clear too at 0.447. The price is
the ring bore: 0.05 a side, virtually a press. It is an assembly-only
joint (the ring travels with the cap), the boss's tip carries a 0.25
lead-in, and the rib squeeze is untouched -- but **print one cap and
seat it before printing six**; if it fights the ring, the walk-back
is the tip-less 4.90 that six caps already validated.

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

## The keyboard mount

`mount.py` builds two stands that perch the case behind a **Nuphy Air75
v2.1**, at the keyboard's own tilt, and writes them to `out/choc/`:

```bash
.venv/bin/python mount.py      # must say all checks passed; also draws mount.png
```

**The keyboard is a tilted rectangle, and that decides the arithmetic.**
Three numbers were measured on the desk with the feet as used: top
plate 13.0 above the desk at the near edge, 25.8 at the far edge, body
133.2 deep. The body is a slab whose near bottom corner stands on the
desk and whose far end the rear feet hold up, so the 12.8 rise over the
133.2 is a **sine** (`KB_TILT` 5.51°), not a tangent (5.49°), and every
face of the slab is square to its plate. The near height then fixes the
slab's thickness: `KB_T` = 13.0 / cos = 13.06. The first drawing of this
had the body as a slab with slanted front and back faces, which put the
mount's front on a lean the keyboard does not have; the first
correction went the other way and leaned the faces *in*. Both were
guesses standing in for one sentence from the person holding the
keyboard.

**Both mounts are the case's own plan outline pushed down to the
desk.** Same 145.47 x 25.99, same R 7.995 corners, drawn in
slab-local coordinates (x along the keyboard, y toward the far end, z
off the plate), tilted about x by `KB_TILT`, and cut flat at z 0. The
front is a plane at the keyboard's rear face, square to the plate, so
the mount butts against the keyboard with no gap; its foot lands 1.24
behind the keyboard's bottom corner, which is where that plane meets
the desk. The two differ in two numbers:

- **`mount-raised`** -- the case bottom on the keyboard's plate plane
  (`KB_T`), slid `MOUNT_OVER` 10.0 toward the user. The case's front
  rests on the keyboard's rear strip and its back on the mount, which
  is only the 16 mm behind the keyboard. The case's plate stands 9.5
  above the keyboard's. 10 is a knob, up to the width of the plain
  strip behind the F row; the strip was never measured with a rule,
  and the print measured it instead -- at 10 the case clears the
  F-row caps.
- **`mount-flush`** -- the case's plate top on the keyboard's plate
  plane (`KB_T` - `CASE_H`), so the two read as one continued slab and
  the whole case sits on the mount. The case bottom is 3.56 above the
  keyboard's underside plane.

**Location is pegs into the foot recesses, not walls.** The rubber
pads come off, and Ø7.50 x 0.40 pegs (`MOUNT_PEG_DIA`, `MOUNT_PEG_H`)
stand into the Ø8 x 0.5 recesses at `FOOT_XY` -- the rear two on the
raised mount, whose front pair hangs over the keyboard, all four on the
flush one. 0.40 leaves 0.10 so the case bottom carries the load rather
than the peg tops. Nothing in the x direction depends on the keyboard:
the case is narrower than it, so centred is a choice rather than a
fit.

**Both mounts are printed and fit** -- Saqoosha's word on the first
print of each, pegs and seating together, which is why the peg coupon
that was planned never had to happen. Read it for what it is: two
assemblies, one apiece. 7.50 into Ø8.00 is a value that works, not a
range whose ends have been felt, and the same goes for `MOUNT_OVER`
10.0 against the F-row caps. If either is ever reprinted and fights,
that is a second sample rather than a contradiction.

**Print with the desk face down.** It is the one flat face; the
cradle is then a 5.5° top surface and nothing overhangs. The block is
modelled solid (61 cm³ raised, 66 flush) and the slicer's infill is the
weight reduction. The desk edge gets `ELEPHANT_CHAMFER`.

**What the checks watch** -- all in `mount.py`, against a keyboard
stand-in (the slab, 320 wide), a case stand-in with its foot recesses,
and a plug in the case's USB-C port: the desk face at z 0 and nothing
below it; mount, case and keyboard pairwise at 0.000 with the pegs in
their recesses; the pegs catching a case shifted 1.0 in each of ±x, ±y
(3.9 mm³ raised, 7.9 flush); the case's plate top at its near edge
against the arithmetic (34.295 raised, 25.800 flush); a probe just
ahead of the front face lying wholly inside the keyboard, so the two
faces touch; a probe under the overhang lying wholly inside the
keyboard, so the raised case rests on it with no step; and a probe
under the rest of the case lying wholly inside the mount, so the
cradle is solid to the surface. Watched to fail: pegs moved 2.0 in y,
9.926 / 19.853 mm³ against the case; tilt sign flipped, the keyboard's
far corner reading 0.200 for 25.800 before the desk chamfer failed on a
part that had none of its edges where it expected.

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

- a **100 mm STEMMA QT / Qwiic cable**, or
- **soldered wires** to the NeoKey's `JP1`/`JP5` headers. Nothing in the
  case needs changing for this: wire takes less room than a plug, and the
  channel is sized for the plug.

The old argument for the cable — that it keeps the pad solder-free — is
gone either way. The six-key field needs five soldered wires, and the
`JP1`/`JP5` header is where two of them already land.

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

**Run all five after every geometry change.** `build.py`
rewrites only the STLs and STEPs, so a partial sweep leaves the renders
and the viewer describing the previous shape, which reads as verified
rather than stale. Note that the shell's exports come out byte-different
on every run even when nothing changed — see `AGENTS.md`; compare the
geometry, not the bytes.
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
in ortho a height is a height, and the plan view puts all six keys on
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
pad can be looked at. The keys wear the status colours from the main
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
out 13.33 tall against 17.49. Z is measured from the outside of the bottom
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
this plate is 2.40 thick, so no hook in this geometry can work. A third
screw at mid-span is out for a different reason: the boards fill the case
wall to wall there, 0.200 between the field and the cavity against the
5.60 a post needs. The magnet pair this paragraph used to name as the
next thing to try was never printed; the **slide latch** below is what
answered the lifted centre, and it captures where a magnet would only
pull.

**The end hook is retired, and the printed case is what retired it.**
It was a raised wall at the right end whose horizontal boss dropped into
a slot cut through the shell's outer face, engaged by the swing-era
motion -- and it held that end well through every print that carried it.
The slide latch adopted its rightward engagement precisely to keep it.
Then the full latched case would not slide home: Saqoosha cut the boss
off the printed plate, found the eight noses hold the bottom fine
without it, and the slide *still* stopped 0.1 short -- the hook's
remaining geometry was the stop. Its wall's outer face kept 0.10 to the
shell's C lip and the tongue's right corners ~0.14 to the skirt's, both
sized for a part that came down vertically and both inside the
~0.15..0.20 this machine shrinks a hole. Not printer error: designed-in
stops, of exactly the class the first coupon sweep had already convicted
at the latch's own pockets -- the latch got its clearances widened, the
hook never did.

So it is gone whole -- wall, boss, C-back recess, the shell's band
reliefs and through slots -- the right wall closes up with no slit in
it, and the tongue now ends at `SLIDE_RIGHT_TRIM_X`, corners and all,
before its own arcs begin: 2.10 to the right skirt where the wall had
0.10. Home in x belongs to the screws alone (Ø3.70 over M3, ±0.35).
`build.py` guards the trim as a shape, not a formula -- a probe asserts
the tongue is *gone* past the trim plane, because a 0.1 stop is
invisible to every boolean at nominal and only exists once the shrink
has eaten it. The hook's numbers, in case it is ever wanted back: wall
3.00 plus a 1.60 rib, boss 1.60 tall reaching 0.90, slot clearance 0.40
settled on its own coupon (0.10..0.30 would not go on), seam climbed to
4.40 in two 3.00 bands, a 1.60 C-back across the whole depth.

**`COLUMN_SLACK` is 0.40.** The first bottom closed with a hair under
1 mm of seam until you pressed: the columns ran to the board and the
shell's 0.20 slack sits above it, which does not help. The reprint at
0.40 closes, and on the seam Saqoosha's words were *"i still can see
tiny gaps but its ok"* — an acceptance that has since expired, and the
slide latch is its answer. The two numbers stay different questions:
0.40 is why the seam *closes*, the latch is what *holds* it closed, and
reopening `COLUMN_SLACK` because the middle lifted would be fixing the
wrong constant.

**The slide latch: the end hook multiplied.** The tiny gap at the middle
of the plate was Saqoosha's complaint and the slide was his answer, and
its final shape is his three calls made geometry: the first cut hid
0.50-tall ledges inside the seam step's 1.20 and he said they were too
tiny and too thin to print; he said neither half may touch the other at
either end of the slide; and he said keep the boss. All three point the
same way -- **so the latch is ten small end hooks.** Each is a post
standing on the tongue's top rim, mostly inboard of the wall's face,
with an **eave** off its top reaching 0.90 outboard, and the shell's
wall takes a pocket up into its 2.00 x 5.80 underside: a full-height
entry for the drop, a channel the post runs along, and a **ledge
running along x** that the eave rides over. A sagging middle is an
eave landing on its ledge -- shell material under a plate feature, the
same capture the boss got from its slot's bottom edge, at ten points
spanning 133 mm. Five pairs, `SLIDE_TAB_X`, mirrored across both long
sides -- the fifth, at -66, is the screws' understudy for the day the
latch proves it can carry the case alone.

The eave is this feature's third shape, and printed parts chose every
turn. It began as the +x **nose** -- the boss at half scale -- which
the first sweep lengthened 0.80 to 1.50 for x clearance, and at 1.50
it was a free cantilever on the upright plate print: Saqoosha saw it
drooping, and a drooped tip hangs below its modelled 3.40, under the
shelf top at 3.10, so it rammed the shelf's edge instead of riding
over it -- the slide's next 0.1..0.2 stop after the hook's. Slicer
support under eight bearing undersides is the wrong fix (scars where
the capture bears, on parts that print support-free by contract), so
the overhang turned 90 degrees: 0.65 instead of 1.50, carried along
its whole 3.00 length instead of free at a tip. And because the ledge
runs along x, the x-clearance class the nose kept losing to hole
shrink has no members left -- nothing of the tab ends near anything
in x.

The motion becomes one flat translation, and **it runs leftward now**:
push the plate right until the trimmed tongue touches the right skirt
(the entry pockets are cut to cover that touch, so the stop *is* the
drop zone), drop it flat, slide left ~2 to home. **The screws are
gone** -- removed once the printed case proved the latch -- so the
underside closes with no counterbores, and home in x is held by seam
friction and the pocket-end over-travel stop until the detent takes it
over: a desk shove can in principle walk the lid rightward 2 mm and
free it, carrying cannot (the hanging plate loads the wedges). At rest
in either position nothing on one half touches the other; the
transient right touch is the only face contact and it is how the hand
finds the drop.

The fourth print is what flipped the direction and grew the tab.
Saqoosha's verdict on the third coupon was "eave is too tiny. slide
length is too short" -- and the rightward travel could never grow: it
was capped at 1.25 by the left trim against the screw seats. Leftward
has no such cap (the drop is opened by the *right* trim, which has
nothing to its right but the corner radius), so the travel is 2.0 with
a 0.90 drop window, and the post grew to 4.00 x 2.20 with the eave at
0.90 x 1.00 -- roughly three times the bearing. The direction was
rightward only for the boss; the boss is gone; this is the leftward
fact that finally argued for the re-flip. Both trims are the skirt's
own inner outline, shifted and intersected -- the corridor probe
caught the straight right trim's corners in the skirt's arcs at
1.488 mm³, the mirror of the left's 1.681, and the shaped cut answers
both ends the same way.

Three facts carry the design:

- **Leftward, at the fourth print's insistence.** The direction began
  rightward for the boss, survived the boss's retirement on inertia,
  and flipped when "slide length is too short" met the arithmetic: the
  rightward drop was capped at 1.25 by the left trim against the screw
  heads' seat rings at x -73.05, and the leftward drop is capped only
  by how far right the tongue is trimmed. Both tongue ends are cut
  with the skirt's own inner outline -- shifted right 1.25 for home
  clearance on the left, swept left by `SLIDE_ENTRY_MAX` for the drop
  on the right, intersected -- because straight faces leave tongue
  corners standing in the skirt's corner arcs (watched at 1.681 mm³
  left, 1.488 mm³ right) and box reliefs wide enough to fix that cut
  1.122 mm³ out of the screw seats. The outline's arcs pass between.
- **No free overhang anywhere, because the fifth print jammed on
  two.** The flat-bottomed eave and the flat-topped ledge were a pair
  of opposed horizontal overhangs -- the eave drooping down off the
  upright plate, the ledge drooping up off the flipped shell -- and
  they ate the 0.30 between them from both sides: every coupon of
  that sweep hit and would not slide. So **both bearing faces are
  parallel 45-degree wedges now**, rising outboard, `SLIDE_FIT` apart
  vertically. At 45 degrees each face prints supported in its own
  orientation -- the eave's underside steps outboard layer by layer,
  the ledge grows off the wall's outer skin -- and a sagging plate
  lands slope on slope, full-face, the two walls' inboard wedge
  pushes cancelling through the plate. Nothing of the latch shows on
  the seam -- the pockets stop 0.85 inside the wall's outer skin and
  never touch the skirt.
- **The corridor is legal because the columns dodge the sockets in
  y, not in x** (sockets case y 2.2..7.4, front columns -8.29, the back
  row's 0.26 at 9.16). A layout that dodged in x could never slide.
  `build.py` walks the drop, the descent and the mid-slide as booleans
  against the shell and the plugless board.

What the printer owns is one number: `SLIDE_FIT`, the clearance between
eave underside and ledge top, which is also exactly how far the seam can
open before the capture catches. `out/choc/coupon-slide.stl` sweeps it
0.20 to 0.50 -- full-depth slices of the real case at one tab pair, both
halves in their print orientations, so the touch, the drop, the slide
and the lift are felt on case geometry.

**Two printed sweeps settled it, and each earned its keep.** The first
(nose 0.80) said 0.30 reads best -- and stopped ~0.1 short of home on
every entry. The fit was innocent: the post's leading face had 0.10 to
the shelf's edge and the nose's tip 0.20 to the pocket's end, both x
clearances inside the ~0.15..0.20 this machine shrinks a hole, so the
post's foot landed on the shelf's printed edge. "We need more longer
hook" is the fix as Saqoosha said it: `SLIDE_NOSE_R` went 0.80 to 1.50,
moving the shelf's edge 0.70 from the post and putting 0.50 past the
nose's tip, without changing the drop or the slide. The 0.10 had sat
below the margin table's own 0.25 bar and was simply never written as a
margin -- `post clear of the shelf's edge` exists now so the class
cannot come back quietly.

The second sweep (nose 1.50) slid fully home in coupon form and put a
floor under the fit: **0.20 will not slide in, 0.30 and 0.40 both go
and hold, 0.30 is the answer** -- the smallest that works, with the
failure felt one step below rather than assumed. It is also a shrink
measurement: printed clearance at 0.20 is at or under zero, so the
pocket loses ~0.20 in the printing and the lift at 0.30 is ~0.10 of
printed plastic. The full case then failed where the coupon had not --
the hook's own 0.1 stops, and the 1.50 nose's droop -- which is what
retired the hook and turned the nose into the eave. The eave keeps the
0.30: the fit's meaning (vertical clearance onto shell material below)
is unchanged, and the coupon sweep exists to re-confirm it cheaply
before the case goes back on the printer.
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

**Nothing screws through any of the three PCBs**, and the three are not
held the same way.

The NeoKey is a sandwich. Four standoffs come down off the plate, each
ending in a Ø2.3 peg that drops into its M2.5 holes and fixes it in X and
Y; four Ø4.5 columns stand directly under those same holes and push it
up. Force path straight through the board, no moment anywhere.

**A breakout cannot have that, and the arithmetic is why.** Its mounting
hole sits 7.62 from its switch centre and a plate-mount switch is 14
wide, so the hole clears the body by 0.62 where `STANDOFF_DIA` needs
2.10 — a standoff there fouls the switch by 1.48. So the breakouts are
pressed at the **seams** between boards instead, which are switch-gap
centres by construction: 4.20 in the 5.05 that 19.05 pitch leaves, the
one figure this case already trusts. Nothing can stand above a breakout
except at those seams, so its push-down and its push-up are never
collinear, and that is paid for from below — Ø3.0 columns on the seams,
plus two pads at the field's outer left edge, where no seam reaches. That
same edge gets `EDGE_RIB_W`, because a seam only exists between two
boards and the leftmost breakout would otherwise be pressed on one side
only.

Two Ø2.3 pegs per breakout were in the model and are gone: the assembled
unit showed the switch already ties the board to the plate through its
socket. `BREAKOUT_HOLES` stays, because it is board data.

Four M3 button-head self-tappers into the corner posts hold the two
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

**The rails run full width and give way at three points.** They were
narrowed once, held 1.80 back off the board's edge so they missed the
castellated pads — which spent clearance along their whole length to
solve a problem in three places, and left 1.10 mm and 0.89 mm of ledge to
carry the board. They are 2.90 and 2.69 now, and `QTPY_PADS_USED` cuts a
pocket where `SCK`, `MISO` and `MOSI` are soldered, and that pocket runs
off the near end rather than stopping short of the first pad: stopping
left a 3.671 mm stub of rail between the pads and the notch the wires
leave through, and every wire had to bend round it. What carries the
board is the other rail full length and 8.750 of this one past the pads,
on the side nothing runs along. Which three pads
those are is a wiring fact, so it lives in `params.py` next to the wiring
rather than in the geometry.

And the pocket wall gives way too. The frame runs all the way round the
board, so a wire soldered to JP3 had the board's edge to leave from and
nowhere to go — the fourth time this case has fitted a board and then
made itself impossible to wire, after both Qwiic sockets and the USB
port. `QTPY_WIRE_NOTCH_W`/`_H` open the wall between the pocket and the
key field, just above the screw post the wires have to clear anyway and
stopping short of the plate, so what is left is a bridge rather than a
missing wall. Measured, not guessed: a bundle laid from the pads to the
channel shared 10.240 mm³ with that wall and nothing with the plate, and
shares nothing with either now.

Their inner ends are still trimmed to `QTPY_UNDER_X`. The clear strips
were read off the board by eye and the second one starts at 14.40 while
the first real component reaches 14.414 — 0.014 inside it, which only
matters once a rail is pulled onto that boundary, and which the mock
could not see at all until the QT Py's underside stopped being one
hand-drawn box.

Switches go in **from the top, through the plate**, after the case is
closed — the hot-swap sockets mean they stay removable without opening
anything, and the plate keeps them square while they seat.

## Assembly order

Different in each layout, because a different half carries the QT Py.
Both wire up before they close, which is the price of the depth.

**Solder the harness first, off the case.** Five wires, and the case has
no way to add one afterwards: `MOSI` to breakout 0's `NEO_IN` and its
`NEO_OUT` on to breakout 1, `MISO` and `SCK` to the two `SWITCHA` pads,
and `VDD`/`GND` for both boards off the NeoKey's `JP1`/`JP5` header —
which is also `SWITCHC`'s ground. The main README's table is the
authority on which pad is which, and its warning applies here: the boards
sit rotated in the case, so reading the silk off a photograph gets the
harness mirrored.

**`inline`** — the shell locates the QT Py and the NeoKey; the breakouts
are only laid in, and the bottom plate holds all three up. This is the
order the built unit was assembled in.

1. Drop the QT Py into the shell's pocket, **face up**, USB-C first into
   the right-end opening, so the pinch bars land on its two clear
   margins. Its three wires leave through the notch in the pocket wall,
   above the screw post.
2. Plug the Qwiic cable into its socket. It faces back toward the NeoKey
   across the 12 mm gap, and there is a second notch in the pocket wall
   for exactly this.
3. Drop the NeoKey onto the shell's four pegs and plug the other end into
   its **right** socket — inline is right-handed, the left one has a
   screw post in front of it.
4. Butt the two breakouts onto the NeoKey's left edge. Nothing locates
   them but the seam standoffs above and the edge rib at the far end; the
   switches are what will hold them once the plate is on.
5. Fold the cable's slack into the gap between the boards. It is 35 mm
   longer than the run; nothing is routed for you.
6. Dress the five wires into the bottom plate's channel — 11.20 wide and
   1.20 deep, running the length of the field — then close the halves,
   four M3 × 10 button-head self-tappers, four Ø8 feet.
7. Press the switches in through the plate. Keycaps.

**`stacked`** — the bottom plate carries the QT Py alone, because the
NeoKey covers the case wall to wall and nothing above can reach it.

1. Slide the QT Py into the bottom plate's pocket, **face down**, USB-C
   first through the back opening, under both lips.
2. Plug the Qwiic cable into its socket — it faces forward, into the
   2.5 mm strip ahead of the board.
3. Drop the NeoKey onto the shell's four pegs and plug the other end into
   either of its end sockets.
4. Butt the two breakouts onto the NeoKey's left edge, as `inline`.
5. Route the slack down whichever end bay the cable came from and lay it
   along the floor. Both bays are open.
6. Dress the five wires into the plate's channel, then close the halves,
   four M3 × 10 button-head self-tappers, four Ø8 feet.
7. Press the switches in through the plate. Keycaps.

That second list is derived from the model, not from having done it:
`stacked` has never been printed.

## BOM beyond the boards

| Part | Qty | Note |
|---|---|---|
| STEMMA QT / Qwiic cable | 1 | 100 mm for `stacked`; the existing 50 mm for `inline` |
| M3 × 10 self-tapping, button head | 4 | into Ø2.95 pilots with a Ø3.40 lead-in, through Ø3.70 clearance chamfered 0.60; counterbored 1.00 so the feet still clear the dome |
| Ø8 × 2 rubber feet | 4 | 0.5 recess, so they stand 1.5 proud |
| 26AWG stranded wire | 5 runs | the channel is sized for 1.30 mm of insulated wire |
| PLA Basic | ~23 g | `inline`: shell 14.30 cm³, bottom 8.21 cm³ |

Those two volumes come out of `build.py`, which is solid volume; the mass
is the four-key print's measured ~19 g scaled by it, at the same infill,
rather than anything weighed.

## Slicer

Everything default except:

- **no supports**, and if it suggests them, stop
- top/bottom solid layers ≥ 5, so the 1.6 mm plate comes out fully solid
  rather than hollow with a skin
- the shell's bed face is the *visible top surface* — on a textured PEI
  plate it comes out matte, which is the finish this is designed around

## Deliberately not here

- **No tilt.** A wedge means the bottom is no longer flat, which means
  supports or a second setup, to fix a problem one row of keys does not
  have.
- **No BOOT/RESET port.** Removed on request, and it holds up: the buttons
  are needed once, to write a UF2, and four screws is a fine price for
  that. An uninterrupted plate is worth more than a paperclip hole. (Which
  button is which was never settled either — the QT Py schematic's net
  names did not resolve to designators.)
- **No routed path for the *Qwiic cable*.** The harness has a trench,
  because five soldered wires have to cross the whole field and there is
  one place they can. The cable is the opposite case: it is 35 mm longer
  than its run and the floor beside the QT Py is open, so it lies where
  it likes. A channel sized for a plug that has not been fitted yet is a
  guess with walls around it.
- **No knockout for a daisy-chained board.** The end bays would take a
  cable out through one. Not built: the six-key field is the design, the
  main README rules out a second NeoKey on its own grounds (it gives
  eight keys, not six), and a knockout that has never been used is just a
  weak spot in a wall.
