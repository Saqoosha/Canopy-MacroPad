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

Print target is a **Bambu A1 mini**, 0.4 nozzle, 0.2 layer, PLA Basic.
Both parts print flat and **neither needs supports**. If the slicer wants
supports, something changed — find out what before printing.

## Print the coupon first

`out/coupon.stl` is 36 × 24 mm and takes about fifteen minutes. It exists
because two numbers in `params.py` are guesses that only a printer can
settle, and getting them wrong costs a two-hour reprint:

| Test | What it settles | If wrong |
|---|---|---|
| switch into the 14.15 square hole | `SWITCH_HOLE` | tight splits the housing, loose lets the key rock |
| M3 self-tapper into the 2.50 pilot | `PILOT_DIA` | tight splits the post, loose strips on the second open |
| standoff + peg against a real NeoKey hole | `PEG_DIA`, standoff height | the board will not seat flat |

Edit the number, rerun `build.py`, print the real thing. The coupon's
plate is the real 1.6 mm and its post is the real 13.5 mm, so a fit that
works here works in the case.

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
The other three scripts take the same variable.
    .venv/bin/python section.py    # sections.png -- cut through the stack
    .venv/bin/python render.py     # *.png -- shaded views
    .venv/bin/python product.py    # product.png -- assembled and exploded

    .venv/bin/python webgl.py dump                    # per layout, then once:
    MPAD_LAYOUT=inline .venv/bin/python webgl.py dump
    .venv/bin/python webgl.py page                    # -> out/viewer.html

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
load-bearing. Its keycap
and switch shapes are eyeballed, nothing checks them, and no dimension in
it feeds anything else — it exists so the pad can be looked at. The four
keys wear the status colours from the main README, since what this device
is *for* is the one thing a picture of it should say.

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

## Stack

Z is measured from the outside of the bottom plate. Read it bottom-up —
the USB-C shell is the lowest thing in the case now, and everything above
is stacked on that one clearance.

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

**Nothing screws through either PCB.** Four standoffs come down off the
plate, each ending in a Ø2.3 peg that drops into the NeoKey's M2.5 holes
and fixes it in X and Y; the bottom plate's columns push it up against
them. Four M3 button-head self-tappers into the corner posts hold the two
halves together, and that is every fastener in the design. The 2.5 that
appears next to the NeoKey is that board's own mounting hole, which takes
a peg and never a screw — the two threads are unrelated.

The QT Py is carried entirely by the bottom plate, because nothing above
can reach it — the NeoKey covers the case wall to wall. It rides on two
rails under its component-free margins and slides forward under two lips,
entering through the same back-wall opening its USB-C ends up in.

It is **face down**, and that is the whole reason it is face down: take
the bottom plate off and BOOT and RESET are facing you. Face up they would
point at the underside of the NeoKey across 2.2 mm of air, and reaching
them would mean getting the QT Py out first.

Switches go in **from the top, through the plate**, after the case is
closed — the hot-swap sockets mean they stay removable without opening
anything, and the plate keeps them square while they seat.

## Assembly order

The two halves each carry a board, so they have to be wired together
before they are closed. That is the price of the depth.

1. Slide the QT Py into the bottom plate's pocket, face down, USB-C first
   through the back opening, under both lips.
2. Plug the Qwiic cable into the QT Py's socket — it faces forward, into
   the 2.5 mm strip ahead of the board.
3. Drop the NeoKey onto the shell's four pegs and plug the cable's other
   end into either of its end sockets.
4. Route the slack down whichever end bay the cable came from and lay it
   along the floor. Both bays are open and nothing is routed for you.
5. Close the halves, four M3 × 10 button-head self-tappers, four Ø8 feet.
6. Press the switches in through the plate. Keycaps.

## BOM beyond the boards

| Part | Qty | Note |
|---|---|---|
| STEMMA QT / Qwiic cable | 1 | 100 mm for `stacked`; the existing 50 mm for `inline` |
| M3 × 10 self-tapping, button head | 4 | into Ø2.50 pilots; counterbored 1.00 so the feet still clear the dome |
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
