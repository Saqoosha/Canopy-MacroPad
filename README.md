# ClaudeMicro — Canopy MacroPad firmware

Four keys next to the keyboard. Each key mirrors one Canopy pane: its
LED shows what that pane's Claude session is doing, and pressing it
focuses that pane and brings Canopy forward.

This repository holds the device half. The macOS half lives in the
[Canopy](https://github.com/saqoosha/Canopy) repository under
`Sources/Canopy/MacroPad/`.

## Why not HID

The device enumerates as USB serial only — `usb_hid.disable()` in
`boot.py`. It is never a keyboard. Consequences, all of them the reason:

- keystrokes cannot leak into whatever app is focused
- with Canopy not running, pressing a key does nothing at all
- macOS never asks for the Input Monitoring permission, because nothing
  reads HID. (OpenAI's Codex Micro does require it.)
- a serial port is plain file I/O on `/dev/cu.*` — no entitlement, no
  Hardened Runtime or notarization friction
- raw press/release edges, with no OS key-repeat logic in between

The one constraint: an App Sandbox process cannot open a serial port.
Canopy is not sandboxed (no `com.apple.security.app-sandbox` key in
`Canopy.entitlements`), so this holds. If that ever changes, this design
has to be revisited.

## Hardware

| Part | SKU | Role |
|---|---|---|
| Adafruit QT Py RP2040 | ssci 7211 / ADA-4900 | controller, CircuitPython |
| Adafruit NeoKey 1x4 QT | ssci 10048 / ADA-4980 | 4 keys + per-key NeoPixel |
| Qwiic cable 50mm | ssci 6896 / SFE-PRT-17260 | QT Py ↔ NeoKey |
| Durock Ice King Linear | — | MX compatible, clear housing |
| Clear ABS keycaps | — | placeholder for printed caps |

One STEMMA QT / Qwiic cable, no soldering. NeoKey defaults to I2C
address `0x30`; a second board needs its A0 jumper bridged for `0x31`.

Key count is never hardcoded on the host — the device reports it, so
going to six keys is a firmware constant and nothing else.

## Protocol

Line-delimited ASCII on the **data** CDC port. Human-typeable on
purpose: the whole thing can be driven from a serial monitor.

**host → device**

| Command | Meaning |
|---|---|
| `C <idx> <rrggbb>` | set key to a solid color, e.g. `C 0 ff8000` |
| `S <idx> <rrggbb> [ms] [floor]` | pulse that color, sine-eased |
| `B <0-100>` | global brightness |
| `P` | ping |
| `R` | all keys off |

`S` runs on the device, not the host. A square blink is one command per
half period and would sit on the host happily, but a sine fade is ~50
updates a second — silly to push down a wire, and it stutters on any host
hiccup. It is also already where it needs to be for BLE. `ms` is the full
period (default 2000); `floor` is the percentage the dip bottoms out at
(default 0). `C` on the same key cancels the pulse.

**Re-sending an identical `S` is a no-op, deliberately.** A pulse is timed
from the moment its command arrives, so a key entering a state fades up
from the floor and the transition is visible. That only works if a host
repainting its whole state — periodically, or after every `HELLO` — does
not restart the clock each time; otherwise the breath replays its first
moments forever. So the host never has to track which keys are already
pulsing: push the full picture whenever convenient, and only genuine
changes are acted on.

Phase is the device's business too. Keys whose states changed at
different moments drift apart on their own, and `PULSE_PHASE_SPREAD`
staggers the case that does not — several keys told to pulse in the same
instant, which is exactly what a full re-push looks like. In lockstep
every lit key dims together and the approval key's peak sinks into its
neighbours'.

**device → host**

| Message | Meaning |
|---|---|
| `HELLO <ver> <keys>` | a host opened the data port |
| `PONG <ver> <keys>` | reply to `P` |
| `K <idx> <0\|1>` | key pressed (1) / released (0) |
| `ERR <msg>` | command could not be handled |

`<ver>` is 1 for `C`/`B`/`P`/`R` and 2 once `S` exists. Accept anything
`>= 1`: the number says which verbs are available, it is not a
compatibility gate.

Three behaviours the host depends on:

- **`HELLO` is sent on host connect, not at power-on.** A banner printed
  at boot is lost whenever the host was not listening yet. Treat every
  `HELLO` as "the device just came up — re-push every color."
- **The device clears all LEDs when the host disconnects.** Stale status
  is worse than none; a frozen orange key claims a session still wants an
  answer. Sending `R` before closing is belt and braces, not required.
- **`C` with an out-of-range index is dropped in silence**, so the host
  may paint before it has learned the key count.

Anything outside the four verbs draws `ERR unknown <cmd>`. Debug output
goes to the *console* port via plain `print`, never to data.

Keep the protocol layer separate from the transport in the host code: on
BLE these same lines become a GATT characteristic payload.

## Status colors

Tuned on the assembled hardware — clear housings, clear keycaps, normal
desk lighting. Values picked on a screen do not survive that trip.

| Pane state | Color | Motion | Command |
|---|---|---|---|
| no pane, or launcher | off | — | `C n 000000` |
| idle | `303030` | static | `C n 303030` |
| running (`isThinking`, `.spawning`) | `0040ff` | breath | `S n 0040ff 2000 50` |
| background task (`isWaiting`) | `00ffa0` | breath | `S n 00ffa0 2000 40` |
| **awaiting approval (`isAsking`)** | `ff8000` | **pulse** | `S n ff8000 2000 10` |
| done, unread | `00ff00` | static | `C n 00ff00` |
| error (`.crashed`, `.reconnectFailed`) | `ff0000` | static | `C n ff0000` |

Global brightness 60. Every period is 2000 ms; only the floor changes,
and that is what separates "alive" from "answer me".

What the bench actually taught, none of which was predictable on paper:

- **Hue does all the state separation, amplitude does the ranking.** The
  colors are spaced by hue alone, as the design requires. Depth of pulse
  is a second, orthogonal axis: static → shallow breath → deep pulse
  reads as increasing urgency without ever competing with hue.
- **Cyan is boxed in between blue and green and cannot be fixed by moving
  it.** At 180° it is equidistant from both. The separation came from
  moving its *neighbours* — green off `00ff40` to pure `00ff00` — and
  from cutting cyan's blue channel so it reads green-dominant against a
  blue-dominant blue.
- **Dark colors are unstable, and it is quantisation, not the LED.**
  `101010` at 30% brightness is `(4,4,4)`; four steps above off, where
  WS2812 mixing is coarse enough to visibly flicker. Hence `303030` for
  idle, and 60% global brightness rather than 30.
- **The same shortage stalls a deep pulse.** At 30% brightness an orange
  pulse with a floor of 5 has a handful of distinct values in its lower
  half, so it freezes at the bottom. Raising global brightness buys steps;
  lowering `PULSE_GAMMA` to 1.0 stops the level crawling through them.
  Scaling the color value down instead does nothing — brightness and the
  color value multiply, so the headroom is unchanged.
- **Equal amplitude does not read as equal motion across hues.** Cyan sits
  near the eye's sensitivity peak and looks far brighter than blue, so the
  same modulation reads as less movement. Cyan's floor is 40 against
  blue's 50 to compensate.

## Bring-up

1. With USB connected, **hold BOOT, tap RST, release BOOT** → the
   `RPI-RP2` volume appears. Double-tapping RST is not a documented entry
   path on this board and does not reliably work. Drop the [CircuitPython
   UF2 for QT Py RP2040](https://circuitpython.org/board/adafruit_qtpy_rp2040/)
   on it; the board reboots as `CIRCUITPY`.
2. From the [CircuitPython Library
   Bundle](https://circuitpython.org/libraries), copy `adafruit_neokey/`
   and `adafruit_seesaw/` into `CIRCUITPY/lib/`. `adafruit_hid` is not
   needed and must not be used.
3. Copy `firmware/boot.py` to `CIRCUITPY/`, then **hard reset**. `boot.py`
   only re-runs on a hard reset, and only a hard reset re-enumerates USB,
   which is what actually applies the CDC interface change. Unplug and
   replug, or from the REPL on the console port:
   `import microcontroller` / `microcontroller.reset()`.
4. `ls /dev/cu.usbmodem*` — two ports must appear (console and data).
   One port means `boot.py` did not take effect; repeat step 3.
5. Copy `firmware/code.py` to `CIRCUITPY/`.
6. `tools/mpad.py --probe` — reports which port is data, plus the VID,
   PID and product string the macOS side matches on.
7. `tools/mpad.py --demo` — lights all four keys, then turns each key
   white while it is held. This is the whole loop: LED out, key in.
8. **Focus a text editor and press the keys. Nothing must be typed.**

Step 8 is the one that matters. If characters appear, `usb_hid.disable()`
is not in effect and the entire premise of the design is broken. The
objective version of the same check does not need a human:

```
ioreg -w0 -l -r -c IOHIDDevice | grep -c 'Canopy MacroPad'
```

Zero means macOS's HID subsystem cannot see the device at all, so no
keystroke can reach any app — a stronger result than "nothing appeared in
my editor".

### Measured on the bench

First bring-up, 2026-08-08, CircuitPython 10.2.1, board ID
`adafruit_qtpy_rp2040`:

| | |
|---|---|
| product string | `Canopy MacroPad` (set by `boot.py`, confirmed in the descriptor) |
| manufacturer | `Whatever` |
| VID / PID | `0x239A` / `0x80F8` |
| console port | `/dev/cu.usbmodem20101` |
| data port | `/dev/cu.usbmodem20103` |
| USB interfaces | CDC control (2), CDC data (10), mass storage (8). **No HID (3).** |
| `IOHIDDevice` entries | none |

The data port took the higher trailing number here, but do not select on
that. `P` → `PONG` is the only reliable discriminator: the console port
runs the REPL, which echoes `P` as typed text and never answers.

### When the keypad is missing

`board.STEMMA_I2C()` raises `RuntimeError: No pull up found on SDA or SCL`
when the Qwiic cable is not seated — the I2C pull-ups live on the NeoKey
board, not the QT Py. The firmware catches this and keeps the serial half
running rather than dying, so the host sees:

```
HELLO 1 0
ERR i2c No pull up found on SDA or SCL; check your wiring
```

`HELLO <ver> 0` is a valid state meaning "device present, keypad absent".
The host should hold the connection and paint nothing, not treat it as a
failure and reconnect in a loop.

### When nothing enumerates

No `RPI-RP2`, no `CIRCUITPY`, no `/dev/cu.usbmodem*`, and no VID `0x239A`
in `ioreg -p IOUSB -w0 -l`: the board is not on the bus at all. In
descending order of likelihood — a charge-only USB-C cable (most USB-C
cables sold with phones carry no data pairs), a hub or dock passing power
but not data, or a dead cable. Try a known-good data cable straight into
the Mac before suspecting the board.

## Phase 1 scope

Four keys, USB wired, status out and focus in. Later phases (six keys and
a printed enclosure, low-profile Choc switches, wireless on nice!nano with
a MagSafe dock) are documented in `canopy-macropad-handoff.md` and are
deliberately not built yet — the only requirement now is not to block
them.
