# What this board is derived from, and why it is licensed differently

`pcb/` is **CC BY-SA 3.0**, not MIT like the rest of this repository. The
licence text is in `LICENSE` beside this file. `firmware/` and `case/` are
unaffected and stay MIT.

## Why

This board's key cell is **cloned from the Adafruit NeoKey 1x4 QT I2C**
(product 4980), whose PCB files Adafruit publish under CC BY-SA 3.0:

- https://github.com/adafruit/Adafruit-NeoKey-1x4-PCB

The NeoKey is the board this project's six-key pad was built on. It works,
it has been assembled and used, and its arrangement is the reason the status
colours in `README.md` are calibrated the way they are. Redesigning that
from datasheets would mean re-deriving something already proven, and getting
it subtly wrong is the likely outcome rather than the unlikely one — the
first pass at this file's hole table, written from two switch drawings,
had the pin drills at 1.50 where the real board uses 3.0635, and omitted
the two plate-mount alignment posts entirely. A five-pin switch would not
have seated.

CC BY-SA's ShareAlike term applies to derivative works, so a board that
copies footprints and layout carries the licence forward. Attribution and
ShareAlike are a small price for a cell that is known to seat a switch and
light a keycap.

## What is cloned

Read out of `Adafruit NeoKey 1x4 QT I2C.brd`:

| | |
|---|---|
| switch pitch | 19.05 |
| switch centre, y | 10.795 |
| pixel centre, y | 5.715, i.e. **5.08 below its switch** |
| `KAILH_SOCKET` pads | (6.09, 5.08) and (-7.36, 2.50), 2.55 x 2.5, bottom |
| `KAILH_SOCKET` holes | Ø3.9 centre; Ø3.0635 at (2.54, 5.08) and (-3.81, 2.54); Ø1.8135 at (±5.08, 0) |
| `NEO3535_REVERSE` opening | 3.854 x 3.454 milled rectangle (Eagle layer 46) |
| `NEO3535_REVERSE` pads | (±2.65, ±0.75), 1.2 x 0.9, bottom |

## What is deliberately not cloned

- **The two pixels sitting 0.127 off their switch's x.** LED4 is at 9.652
  against SW1's 9.525 and LED2 at 47.752 against SW3's 47.625, while the
  other two are dead on. That is a routing nudge for the chain, not a
  requirement, and copying it would carry someone else's trace layout in as
  a dimension.
- **The seesaw, its I2C address jumpers, and the STEMMA QT connectors.**
  This board has an RP2040 and a USB-C receptacle instead.
- **Four keys.** This one has six.
