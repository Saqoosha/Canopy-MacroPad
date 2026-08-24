# pcb/ — bringing the fabricated board up

`README.md` next to this file is the design half: how to drive EasyEDA
from Python and every way that API has bitten. This file is the other
half — what to do when the boards arrive from JLCPCB, in what order, and
which of those steps prove less than they look like they prove.

The root `README.md` and `AGENTS.md` describe the **QT Py** build's
firmware and its bring-up console. This board does not run that firmware
yet: `firmware/code.py` uses QT Py pin names and half its code is an I2C
NeoKey that does not exist here.

## The boards are a revision the EasyEDA document no longer is

Check this before reordering. The fabricated boards carry **88 vias**; the
live document has **97**, and the nine extra are a 3x3 grid on 1.0 mm
pitch at x 119.5/120.5/121.5, y 10/11/12 — dead centre on U3, all on GND.
That is the RP2040's **stock exposed-pad via array**, which
`thermal_fanout.py` exists to remove: the board uses no via-in-pad
process, so the exposed pad is fanned out to ordinary vias *outside* pad
57's paste area instead. Reordering from the document as it stands would
either need filled-and-capped via processing or wick solder off the
thermal pad during reflow.

**The boards are the correct revision. The document is the regressed
one.** Nothing here was designed to change; it came back on its own,
after the Gerber was exported (the drill file is stamped 2026-08-17
17:50:17 and matches the 88).

The project's own guard says so without ambiguity — `python3
via_in_pad.py` against the live document reports all nine as
`U3.57 GND ... centre`, and its docstring is explicit that every annular
overlap here "is unexpected and remains a build failure". Two commands
settle the question at any time:

```
unzip -p out/manufacturing/canopy_macropad-gerber.zip \
  Drill_PTH_Through_Via.DRL | grep -c '^X'     # what was fabricated
python3 via_in_pad.py                          # what the document is now
```

**And the export cannot catch this.** `all.sh` runs `thermal_fanout.py`
and `via_in_pad.py`; `export_manufacturing.py` runs neither. Its checks
are about file completeness — both copper layers present, U1 in the BOM
and the CPL — so it will happily produce a Gerber from a document
`all.sh` would reject. DRC will not catch it either: a same-net via in a
same-net pad is electrically legal, and it is a manufacturing decision
rather than a rule violation. **Run `./all.sh` before an export, not
after**, and treat a clean `export_manufacturing.py` as saying nothing
about the design.

## What JLCPCB populates, and what it leaves for you

Economic PCBA on the bottom side assembles only what the quote in
`README.md` marks as required — U3 (RP2040), U1 (flash), U2 (crystal), U4
(LDO), USBC1, D1 and every passive. **SW1, LED1-6 and SK1-6 come DNP**,
which is what that section asked for. A board with no BOOT button is the
expected delivery, not a fab error.

Everything is on the **bottom** face. The Gerber archive carries
`Gerber_BottomPasteMaskLayer.GBP` and no top paste layer at all, which is
the quickest confirmation of that.

## The order to test in

Each step exists because it can be done before the next one, and because
a failure at that step is cheaper to find there. **The value of the list
is as much in what each step cannot see as in what it checks.**

1. **Visual, against the render.** `out/board-final.png` and
   `out/board-large.png` are **stale**: both predate SW1 moving beside
   USB-C (`layout.py`'s own comment says "it lives beside USB-C *now*"),
   so SW1 is simply not drawn in them. The Gerbers come from the live
   EasyEDA document and are correct; only the figures are old. Read
   `out/manufacturing/canopy_macropad-cpl.xlsx` for where a part actually
   is — it is generated from the same export.
2. **Shorts, before any power.** VBUS-GND and 3V3-GND. A short here and a
   plugged-in board is a damaged host port.
3. **Power, ideally metered.** 3.30 V out of U4.
4. **Plug in and look for `RPI-RP2`.** This proves U4 and the 3V3 rail,
   the RP2040 itself, the crystal (the bootrom's USB needs the 12 MHz
   XOSC), and the whole USB path — connector, D+/D-, the 27 R series
   pair, the 5.1 k CC pair, the USBLC6.

   **It does not prove the flash.** An RP2040 falls into BOOTSEL when its
   flash is blank, when it is dead, and when it is absent, and all three
   look exactly like a healthy first boot. On a fresh board the flash *is*
   blank, so this step is guaranteed to succeed and tells you nothing
   about U1.
5. **Write a UF2.** This is the flash test, and it is the first step that
   can fail for a reason the previous ones could not see. `CIRCUITPY`
   appearing means the flash was erased, written and read back.
6. **KEY traces, with nothing soldered.** Pull each KEY GPIO up and
   bridge a hot-swap socket's two pads with tweezers — pad 1 is `KEYn`
   and pad 2 is GND (`place_mcu.py`'s net map), so a bridge is
   electrically what the switch does and needs no separate ground lead.
   Six traces, RP2040 ball to socket pad, before committing any solder.
7. **LED1 only.** It is the head of the chain (`GPIO25 -> LED1.DIN`);
   every later pixel is fed by the one before it, so no other LED can be
   tested alone.
8. **The rest, then the chase.** See "a chain diagnoses itself" below.

## Three ways into the UF2 bootloader

All three watched working on the built board. Worth knowing all of them,
because the first one does not exist until SW1 is soldered and the third
does not exist until the board runs CircuitPython.

- **Hold SW1 through a plug-in.** The normal way, once SW1 is on.
- **Bridge SW1's bare footprint.** The pads are live with no part on
  them: pad A goes through R1 (1 k) to `QSPI_SS`, pad B to GND. Bridge
  **across the 3.4 mm lead span**, not the 1.8 mm pitch — the two pads
  sharing a column are the same net and shorting them does nothing. Hold
  the bridge *while* plugging in; the RP2040 only samples `QSPI_SS` at
  power-on.
- **From the CircuitPython REPL.**
  ```python
  import microcontroller
  microcontroller.on_next_reset(microcontroller.RunMode.BOOTLOADER)
  microcontroller.reset()
  ```

There is no reset button on this board, so before flashing anything onto
a bare board it is worth knowing which of these is available.

## Measured on the board

Numbers from the first assembled unit, usable as a baseline for the next
one.

| Fact | Value |
|---|---|
| Board UID | `DF6590575F5D2026` |
| CPU | 125 MHz — the PLL locked to the 12 MHz XOSC, so CircuitPython running at all proves U2 |
| `CIRCUITPY` free | 7,308,288 bytes |
| Die temperature, idle | ~31.8 °C |
| KEY0-5 | GPIO 3, 4, 6, 20, 5, 24 — measured in order, no swaps, no shorts |
| PIXEL | GPIO25 |
| Debounce that holds | 3 samples at 5 ms; every press of a real Choc measured 142 ms or longer |
| Flash write, host over USB MSC | 53 kB/s — 7,086,080 bytes took 131 s |
| Flash read, device side | 1231 kB/s — the same bytes back in 5.8 s |

That 23x asymmetry is the number to remember when a deploy feels slow:
it is the flash's erase-and-program cost plus the mass-storage layer, not
a fault. Copying `code.py` is ~50 kB and lands inside a second; copying
something megabyte-sized will take minutes.

**7 MB means the flash *reported* 8 MB.** CircuitPython reads the JEDEC
capacity at runtime, which is why a build compiled for a 2 MB Pico
exposes 7 MB here. On its own that confirms U1 is the W25Q64 and that
QSPI works — it is not a surface test, because formatting writes
structures, not every block.

**The surface test was run separately and passed**: 7,086,080 bytes
(1730 x 4096, 98% of the free space) written from the host over USB mass
storage, then read back **by the RP2040 out of its own flash** and
compared block by block. Both halves of that arrangement matter. Reading
it back on the host would let macOS's page cache answer instead of the
flash, so the two directions deliberately take different paths. And each
block carries its own index in its first four bytes, because a fault that
returns the *wrong* block rather than corrupt bytes would pass a
body-only comparison — under a uniform pattern, address aliasing reads as
success. The body pattern is `bytes(range(256))` repeated, not zeros, so
a stuck-at value cannot hide in it either.

What that does and does not settle: the FAT-visible ~7 MB reads back what
was written, once. It says nothing about the ~1 MB the firmware occupies,
and nothing about retention or wear.

**SK6812MINI-E runs on the 3V3 rail**, which is below its 3.7 V datasheet
minimum. Red, green and blue all came up at full strength — and blue is
the one that would have died first, having the highest forward voltage, so
its survival is the meaningful half of that result. The rail was chosen on
the other side of the trade: at 3V3 the RP2040's 3.3 V output clears the
part's `0.7 * VDD` = 2.31 V input threshold with room, where a 5 V rail
would have put 3.3 V against 3.5 V.

**And that rail carries everything, which the QT Py's does not.** On the
QT Py the pixels hang off the incoming Qwiic rail, unregulated; here every
pixel's VDD and the RP2040 both sit behind U4, one XC6206 in SOT-23-3. So
the pixels' worst case is the regulator's worst case, and it was worth
asking about.

**It holds.** Six pixels at `ffffff` through a 10/25/50/75/100 brightness
ramp caused no reset at any step — and a reset is the signal that cannot
be missed, because the firmware announces a fresh `HELLO` on the same port
the test is listening to. Then an A/B with **load as the only variable**:
LED0 told `ffffff` at brightness 100 with only itself lit, against LED0
told the same thing with all six lit. No colour difference. That is the
sensitive form of the question — blue and green have the higher forward
voltage and starve first, so a sagging rail shows up as one white going
warm, which is the same reading that found LED4's dry supply pad. Staring
at a single 100% white and asking "is that reddish?" cannot answer it;
there is nothing to compare against and the eye adapts.

Not measured, and deliberately: **sustained** full white. 1.7 V times the
board's draw is not much thermal room in that package, and no host holds
that state — so the case that would need a heat measurement is one the
device never enters. That is a scope decision, not a gap.

**`neopixel_write` is a core module** on the RP2040 port, so the pixels
need nothing in `lib/`. Its argument is the whole chain's buffer, three
bytes per pixel, **GRB on the wire**.

## A chain diagnoses itself

LED4 came out a visibly different colour from the other five, and it was
fixed by reflowing without desoldering anything, on this reasoning:

**Data passed through LED4 and reached LED5, and LED5 was correct.** That
alone proves LED4's DIN, its internal IC and its DOUT are all healthy —
the digital path is not a suspect, by evidence rather than by probing.
What remains is VDD and GND. A half-wetted supply joint adds resistance,
and blue and green starve first, so the symptom of a bad supply pad on a
chained pixel is *one pixel gone warm*. Reflowing its supply pads fixed
it; the part was innocent.

This only works because the part sits in a chain. An isolated LED offers
no such evidence and has to be metered.

Which is also what the **chase** phase of a pad test is for: light one
pixel at a time, 0 through 5. It is the only test that *locates* a broken
hop — everything downstream of a dead link stays dark, so the index where
the walk stops names the break (stops after N ⇒ `N.DOUT -> (N+1).DIN`).
In every other pattern, a downstream failure just looks like "some LEDs
are off".

## Two things a host-side log cannot tell you

Both of these produced a confident-looking pass on this board before
someone noticed what they were actually reporting.

- **A console log proves the firmware sent the data, not that a pixel
  lit.** A chase printing `chase 0` through `chase 5` prints exactly the
  same lines on a board with no LEDs on it at all. Only the person
  looking at the board can answer that one, so ask them what they saw
  rather than reporting the log as a result.
- **Change-only logging cannot see a stuck input.** A KEY net shorted to
  GND on the board reads low from the very first sample and never
  produces an edge, so it is invisible in a log of transitions. Print the
  **initial** state, and repeat it in a heartbeat — all six reading high
  is itself a fab-defect check, and it costs nothing.

## Driving the board from the host

Once `firmware/boot.py` is on the board and it has had a **hard** reset,
`tools/mpad.py --probe` is the whole test:

```
usb: product='Canopy MacroPad' vid=9114 pid=33012 (0x239a / 0x80f4)
  /dev/cu.usbmodem2101  console/silent (no PONG (saw: nothing))
  /dev/cu.usbmodem2103  DATA   -> PONG 3 6
```

That PID is **not** the one the root `README.md` records, and neither
reading is wrong: `boot.py` sets only the manufacturer and product
strings, so the VID and PID come from the CircuitPython build. The QT Py
build answers `0x80F8`, the stock Pico build this board runs answers
`0x80F4`. Match on `Canopy MacroPad`, never on the PID — which is what
both halves already do. `tools/mpad.py` never looks at it, and Canopy's
`MacroPadDevice.swift` leaves it out of the match on purpose, because
pinning a number that belongs to the build would fail closed and look
like a bad cable. So this board needs nothing on the host side.

Before `boot.py` is on the board there is one console port only, and
`code.py` falls back to it — `HELLO`, `PONG` and `K` lines arrive mixed in
with `print` output, which is enough to test the whole protocol. Two
things about reading it, the second of which is the fix for the first:

- **`code.py`'s startup prints are emitted before a host can reattach**
  after a reset, so they are dropped. Watching the console for a
  boot-time line is not a test.
- **Attach first, then force a reload.** `\x03` stops `code.py` and
  prints *"Press any key to enter the REPL"* — and that next key is
  consumed opening the prompt, so send it alone and wait to actually see
  `>>>`. Then `\x04` re-runs `code.py` with the host already listening,
  and the startup lines arrive.

Copying `code.py` to `/Volumes/CIRCUITPY/` triggers auto-reload, which is
a **soft** reset — enough for `code.py`, never enough for `boot.py`. And
`rm` the `._*` AppleDouble files macOS leaves behind.

## Where this stands

Nothing on the electrical side is open any more. What is left is one
requirement and one piece of paperwork.

- **`lib/neopixel.mpy` has to be on the board.** `adafruit_pixelbuf` is a
  core module on this build, so that one file is the whole dependency;
  `adafruit_neokey` is not needed, because the `pcb` profile never touches
  I2C. Without it the keys still report presses and the host is told `ERR
  gpio pixels ImportError`.

`firmware/` now runs on both boards from one source, selected by the
`PROFILES` table at the top of `firmware/code.py` (and a deliberately
smaller copy of it in `firmware/boot.py`, which cannot import `code.py`).
That table and the comment above it are the explanation; `AGENTS.md`'s
"Editing the firmware" section still describes the QT Py build alone and
has not caught up.

Verified on this board: `HELLO 3 6`, `PONG 3 6` on the data port, all six
keys reporting edges through the protocol, both branches of `boot.py`'s
drive gate, and no `ERR` of any kind.
