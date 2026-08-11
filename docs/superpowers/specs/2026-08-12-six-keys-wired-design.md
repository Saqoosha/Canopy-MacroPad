# Six keys, wired

Take the pad from four keys to six over USB, without touching the
protocol and without asking anything new of the macOS half — Canopy
already reads the key count out of `HELLO`.

## Hardware

Keep the NeoKey 1x4 at `0x30` for keys 0-3. Add two Adafruit 4978
NeoKey Socket Breakouts for keys 4-5, read on GPIO. The QT Py RP2040
does not change.

The alternatives, and why not:

- **A second NeoKey 1x4** gives eight keys, not six, and is 152.4 wide.
- **NeoKey Snap-Apart 5x6 snapped to 1x6** is one uniform board with
  guaranteed LED consistency, but it carries no seesaw: I2C disappears,
  `boot.py`'s drive gate is rewritten, and every error path proven by
  fault injection has to be proven again. ¥5,088 against ¥858.

If the LEDs turn out not to match (see Open), the Snap-Apart is the
fallback and this decision is the cheap way to find out.

### Why the pitch lands

Read out of the Eagle `.brd` files, not the product pages.

| | NeoKey 1x4 (4980) | Breakout (4978) |
|---|---|---|
| outline | 76.200 x 21.590 | 19.050 x 21.590 |
| switch centre, y | 10.795 | 10.795 |
| switch centre, x | 9.525 + n x 19.05 | 9.525, the board's centre |
| LED | `NEO3535_REVERSE`, y = 5.715 | `NEO3535_REVERSE`, y = 6.096 |
| mounting holes | 4 x M2.5 plated | 2 x 2.54 drill, diagonal |

The breakout is exactly one pitch wide, its switch is centred in that
width, and its depth is the NeoKey's to three decimals. Butt two of
them against the NeoKey's right edge and the switches land at 85.725
and 104.775 — 19.05 apart, same as every other pair. Key field
**114.30 x 21.59**, six switches at `9.525 + n x 19.05`.

Two mismatches, both accepted rather than worked around:

- The breakout's LED sits 0.381 closer to its switch centre. Whether
  that changes how the keycap lights is a thing to look at, not to
  calculate.
- Its holes are 2.54 against the NeoKey's 2.5, so `PEG_DIA` 2.30 has
  0.24 of play instead of 0.20. The peg locates, it does not grip.

### Electrical

From the schematics:

- NeoKey 1x4: the pixels' `VDD` is `VCC`, the incoming STEMMA QT rail,
  and `IC3` level-shifts the seesaw's 3.3 V data up to it. **The status
  colours in `README.md` were therefore tuned on 3535 pixels running at
  the Qwiic rail voltage.**
- Breakout: `SW1` to `SWITCHA` on one side and through `D1` (SOD-323,
  1N4148) to `SWITCHC` on the other. `VDD`, `GND`, `NEO_IN`, `NEO_OUT`,
  `SWITCHA`, `SWITCHC` come out on both 1x05 headers;
  `NEO_IN`/`NEO_OUT`/`SWITCHC` are duplicated on the side pads so
  adjacent boards bridge to each other directly.

Five wires reach the QT Py:

| QT Py | to |
|---|---|
| `3V` | both boards' `VDD` |
| `GND` | both boards' `GND`, and `SWITCHC` |
| one GPIO | breakout A `NEO_IN`; A `NEO_OUT` to B `NEO_IN` on the side pads |
| one GPIO | breakout A `SWITCHA`, `Pull.UP` |
| one GPIO | breakout B `SWITCHA`, `Pull.UP` |

The diode points `SWITCHA` to `SWITCHC`, so `SWITCHC` goes to ground
and a pressed key pulls its input low. The 1N4148 drops about 0.45 V at
the ~55 µA an RP2040 internal pull-up supplies, which clears the 0.8 V
`V_IL` with room but not with margin to spare — if a key ever reads
stuck-pressed, this is the first number to measure.

Three GPIO of the eleven broken out. The STEMMA QT connector is on its
own pair (GPIO 24/25) and is untouched.

**The one measurement before wiring**: `VCC` on the NeoKey. STEMMA QT
is a 3.3 V rail, so powering the breakouts from the QT Py's `3V` should
put their pixels on the same voltage as the existing four — which is
the whole argument for the colours carrying over. Meter it rather than
assume it.

## Firmware

### Key sources replace pad addresses

`PAD_ADDRESSES` and `KEYS_PER_PAD` currently derive the key count, the
pixel routing and the scan. Replace them with an explicit list of
sources, each carrying its pixel object, its read function, its base
index and its count:

- seesaw source — `pad.pixels`, `pad.get_keys()`, base 0, count 4
- gpio source — `neopixel.NeoPixel(pin, 2, auto_write=False)`,
  `[not p.value for p in pins]`, base 4, count 2

`pad.pixels` and `neopixel.NeoPixel` are both `adafruit_pixelbuf.PixelBuf`
subclasses: same `[i] = rgb`, `.show()`, `.brightness`, `.fill()`,
`.auto_write`. So `write_pixel`, `flush_pixels` and `invalidate_pixels`
change from `idx // KEYS_PER_PAD` arithmetic to a source lookup, and
nothing else about the appearance model moves.

### Indices are static, not enumerated

Key 4 is always index 4. If the I2C half fails to come up, the
breakouts must not slide down into 0 and 1 — the host maps index to
pane, and a silent renumbering focuses the wrong one.

That forces `NUM_KEYS` to be 6 unconditionally, because the GPIO half
cannot fail to enumerate. `HELLO <ver> 0`, documented today as "device
present, keypad absent", becomes `HELLO <ver> 6` alongside the existing
`ERR i2c setup ...`. Writes aimed at an absent source are dropped in
silence, the way an out-of-range index already is.

This is the one host-visible change in the whole design, and `README.md`
has to say so.

### The I2C guard gets smaller

GPIO reads move outside it. A Qwiic cable knocked loose should not take
down the two keys that do not use the cable; on I2C failure the loop
still reports edges for 4 and 5.

### boot.py

The drive gate reads the GPIO keys as well. Without that, "hold any key
while plugging in" is false for two of the six and the README lies. Read
GPIO first — it cannot raise the way `board.STEMMA_I2C()` does — then
fall through to the existing I2C path with its fail-open behaviour
exactly as it is.

### Untouched

Protocol verbs, status colours, crossfade, pulse, phase handling, the
fatal handler and its 60 s brake, debounce. `PROTOCOL_VERSION` stays 3:
no verb changes and no behaviour a host has to negotiate.

## Case

`NEOKEY_W` stops being the key field. Add the breakout as its own set of
numbers and derive the field from both:

- `BREAKOUT_W = 19.05`, `BREAKOUT_D = 21.59`, both out of the `.brd`.
  `BREAKOUT_T` is not in the `.brd` and Adafruit publishes no STEP for
  this board: start at the NeoKey's measured 1.57 on the grounds of the
  same fab and stackup, and put calipers on it when it arrives. It is
  the one board number here that is a guess, and `params.py` has to say
  so.
- `BREAKOUT_HOLES = [(1.905, 5.080), (17.145, 16.510)]`
- key field width `76.20 + 2 x 19.05 = 114.30`
- switch centres `9.525 + n x 19.05`, n = 0..5

`inline` grows from 120.50 to **158.60** wide. Depth and height do not
change. Two pegs per breakout, diagonally opposite, so rotation is
constrained by the same mechanism the NeoKey already uses.

`build.py` must end in `all checks passed` for **both** layouts before
anything is printed.

## Host tools

`tools/mpad.py` writes its demo colours and palette pages per key for
four keys. Extend to six.

## Documentation

The drive gate is documented as reading "a key on the first NeoKey
board" in two places, and this change makes that wrong — it becomes any
of the six:

- `README.md`, the CIRCUITPY drive section
- `AGENTS.md`, the same claim in the editing notes. `CLAUDE.md` is a
  symlink to it, so it is one edit, not two.

`README.md` also carries the key count in its opening sentence and its
hardware table, and the `HELLO <ver> 0` row of the known-good table —
which becomes `HELLO <ver> 6` alongside the I2C error, per Indices are
static above.

## Verification

1. `python3 -m py_compile firmware/*.py tools/mpad.py`
2. `MPAD_LAYOUT=inline python build.py` and again for `stacked`, both
   ending in `all checks passed`
3. meter `VCC` on the NeoKey before wiring anything
4. `tools/mpad.py --probe` reports `PONG 3 6`
5. `tools/mpad.py --demo` lights six keys; each goes white while held
6. unplug the Qwiic cable while running: keys 4 and 5 keep reporting,
   and the host gets the I2C error
7. hold a **breakout** key while plugging in: `CIRCUITPY` mounts. Two
   traps here, both of which make a broken gate look like a working
   one. A `boot.py` change needs a **hard** reset — copying `code.py`
   triggers auto-reload, which is a soft reset, so the edited `boot.py`
   never runs and the probe reports a healthy board still on the old USB
   config. And read `boot_out.txt` **from the REPL on the console
   port**, not off the drive: mounting the drive is what makes the gate
   take the other branch and overwrite the line you came to read.
8. focus a text editor and press all six. Nothing is typed.

## Open, deliberately

- **The colour match is argued, not measured.** Both boards carry
  `NEO3535_REVERSE` and both will run off the same rail, which is why
  this is the cheap option to try first. If keys 4-5 read differently,
  the fix is per-source tuning, and the Snap-Apart 1x6 is the fallback
  that removes the question entirely.
- `PILOT_DIA` at 2.50 has still never had an M3 driven into it. That
  predates this work and is not in its scope.
