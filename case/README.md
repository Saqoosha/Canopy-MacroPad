# Canopy MacroPad — case

A two-part printed enclosure for the NeoKey 1x4 and the QT Py that drives
it. Parametric, in `build123d`; the way to change it is to change a number
in `params.py` and rebuild.

**Two layouts**, from the same source, chosen with `MPAD_LAYOUT`. They
differ only in where the QT Py goes, and that one decision moves every
dimension in the case:

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

`stacked` is the compact one and `inline` is the low one. Neither is
strictly better — a shorter pad sits closer to keyboard height, a smaller
one takes less desk.

## The `inline` case, printed

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

There are two, and the small one exists so that re-asking one question
does not cost a reprint of the answers already settled:
`out/<layout>/coupon-clear.stl` is the clearance-hole row on its own.

`out/<layout>/coupon.stl` is 68 × 46 mm and takes about twenty minutes.
It exists because a few numbers in `params.py` are things only a printer
can settle, and getting them wrong costs a two-hour reprint:

| Test | What it settles | Status |
|---|---|---|
| switch into the 14.15 square hole | `SWITCH_HOLE` | **settled** — a Durock Ice King seats correctly on an A1 mini in PLA Basic |
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

## Cable, per layout

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
    .venv/bin/python build.py                    # stacked
    MPAD_LAYOUT=inline .venv/bin/python build.py  # inline

Each writes into `out/<layout>/`, so both sets of STLs exist side by side.
The other scripts take the same variable.

    .venv/bin/python section.py    # sections.png -- cut through the stack
    .venv/bin/python render.py     # *.png -- shaded views
    .venv/bin/python product.py    # product.png -- assembled and exploded

    .venv/bin/python webgl.py dump                    # per layout, then once:
    MPAD_LAYOUT=inline .venv/bin/python webgl.py dump
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
