# What this board borrowed, and from whom

`pcb/` is **MIT**, like the rest of this repository. There is no separate
licence file here any more — an earlier revision carried CC BY-SA 3.0 and
the reason for it is gone. That story is at the bottom, because it is the
useful part.

## Attribution

The key cell — every hole, every pad offset, the pixel's position and its
milled opening — is taken from **[foostan/crkbd](https://github.com/foostan/crkbd)**,
the Corne keyboard, which publishes its PCB files under **CC BY-4.0**.
Specifically from `pcbs/corne-chocolate/hotswap/corne-chocolate.kicad_pcb`
and `pcbs/common/kbd/kicad-footprints/kbd.pretty/`.

CC BY-4.0 asks for attribution and does not impose ShareAlike, so this
directory can be MIT. The attribution is not a formality: **this geometry
is on a board that ships, and that is the only reason to trust it.**

Cross-checked against [ebastler/marbastlib](https://github.com/ebastler/marbastlib),
which arrives at the same pixel offset independently.

## What was taken

| | value | source |
|---|---|---|
| switch centre (boss) | (0, 0) Ø5.0 | `keyswitch_choc12_hotswap_1u` |
| switch pins | (0, 5.9) and (5, 3.7), Ø3.0 | same |
| alignment posts | (±5.5, 0) Ø1.9 | same |
| v2 mount | (-5, -5.15), **oval** 1.5 x 2 | same |
| socket pads | (8.1, 3.7), (-3.1, 5.9), 2.3 x 2.6 | same |
| pixel offset | **(0, -4.74)** | measured across 46 switch/pixel pairs on the Choc Corne |
| pixel opening | 3.6 x 3.1 | `YS-SK6812MINI-E`, Edge.Cuts |
| pixel pads | (±2.8, ±0.7), 1.7 x 0.825 | same |

The pixel offset is the one number with two witnesses. Corne's board
measures 4.737-4.749 along each key's own axis across all 46 keys;
marbastlib's Choc add-on carries an alignment arrow its author drew at
4.7. Two designs with no shared author agreeing is the strongest evidence
available short of a fabricated part.

## What is not from crkbd

`SWITCH_PITCH` 19.05, `FIRST_SWITCH_X` 9.525, `SWITCH_Y` 10.795 and
`KEY_FIELD_D` 21.59 are inherited from this project's own earlier pad,
which was built on the Adafruit NeoKey 1x4. 19.05 is 0.75 inch and is the
Cherry MX industry pitch rather than anyone's invention; 9.525 is half of
it; the other two are measurements of a physical board. They are kept
because the keycaps and the printed plate already work against them.

## Why this file exists at all

The first version of this cell was derived from switch drawings rather
than borrowed, and it was wrong four times over. Two of those would have
reached the fabricator:

- The MX pin drills were sized for a switch pin at 1.50, where the real
  board uses **3.0635** — the hot-swap socket's barrel passes through the
  hole, not just the pin.
- The two plate-mount alignment posts at ±5.08 were **omitted entirely**.
  Every five-pin switch would have refused to seat.
- The MX pin positions were read out of the package and used without
  applying the board's **`MR0` mirror**, so they were flipped in x.
- The pixel opening was guessed as a Ø3.00 round hole; it is a milled
  rectangle.

None of those is a mistake arithmetic would have caught, and all four
disappear the moment the numbers come off something that works. That is
the whole argument for borrowing, and this file is where the borrowing is
declared.
