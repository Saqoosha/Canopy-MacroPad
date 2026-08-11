# Canopy MacroPad

Four keys next to the keyboard. Each key mirrors one Canopy pane: its
LED shows what that pane's Claude session is doing, and pressing it
focuses that pane and brings Canopy forward.

![The inline case, closed with keycaps on, and open with the NeoKey and
the QT Py seated in the shell above the bottom plate](case/images/inline-built.jpg)

The enclosure is the `inline` layout, printed on a Bambu A1 mini. It is
parametric — see [`case/README.md`](case/README.md).

This repository holds the device half. The macOS half lives in the
[Canopy](https://github.com/saqoosha/Canopy) repository under
`Sources/Canopy/MacroPad/`.

## Why not HID

The device enumerates as USB serial only — `usb_hid.disable()` in
`boot.py`. It is never a keyboard. Consequences, all of them the reason:

- keystrokes cannot leak into whatever app is focused
- with Canopy not running, pressing a key does nothing at all
- macOS never asks for the Input Monitoring permission, because nothing
  reads HID. (OpenAI's Codex Micro required it as of 2026-08.)
- a serial port is plain file I/O on `/dev/cu.*` — no entitlement, no
  Hardened Runtime or notarization friction
- raw press/release edges, with no OS key-repeat logic in between

Verifiable rather than asserted: `ioreg -w0 -l -r -c IOHIDDevice | grep
-c 'Canopy MacroPad'` returns 0, and the device's USB descriptor offers
CDC control, CDC data and mass storage — no HID class at all.

Two limits worth stating, since the argument above reads as exhaustive
and is not. **Mass storage stays enumerated**, so `CIRCUITPY` — and
therefore `code.py` itself — is writable by any process on the host.
That is a deliberate bring-up affordance, not an oversight, but it means
the threat model here is "no input injection", not "tamper-proof". And a
**sandboxed** app would need `com.apple.security.device.serial` to open
the port; Canopy sidesteps that by not being sandboxed at all (no
`com.apple.security.app-sandbox` key in `Canopy.entitlements`). If that
changes, this design has to be revisited.

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

Key count is never hardcoded in Canopy — the device reports it in
`HELLO`, so a second board is a firmware constant and nothing else on
that side. Two caveats: a second NeoKey 1x4 gives eight keys, not the six
the later phases talk about, which needs different hardware; and
`tools/mpad.py` does assume four, since its demo colours and palette
pages are written per key.

## Protocol

Line-delimited ASCII on the **data** CDC port. Human-typeable on
purpose: the whole thing can be driven from a serial monitor.

**host → device**

| Command | Meaning |
|---|---|
| `C <idx> <rrggbb>` | set key to a solid color, e.g. `C 0 ff8000` |
| `S <idx> <rrggbb> [ms] [floor]` | pulse that color, sine-eased. `ms` is clamped to ≥100, `floor` to 0-100 |
| `B <0-100>` | global brightness |
| `X <ms>` | crossfade duration for `C` and `S`, default 500 |
| `P` | ping |
| `R` | all keys off, immediately |

`S` runs on the device, not the host. A square blink is one command per
half period and would sit on the host happily, but a sine fade is ~50
updates a second — silly to push down a wire, and it stutters on any host
hiccup. It is also already where it needs to be for BLE. `ms` is the full
period (default 2000); `floor` is the percentage the dip bottoms out at
(default 0). `C` on the same key cancels the pulse.

**Every colour and floor change is crossfaded**, over `X` milliseconds.
An instant switch reads as "something just happened", but most
transitions are a session moving from one continuous state to the next,
so an abrupt change makes the pad overstate the event.

Internally there is only one appearance model: a colour and a floor,
where **solid is a pulse whose floor is 100%** and the sine term drops
out. One interpolation therefore covers all four transitions with no
special cases:

| Transition | What happens |
|---|---|
| solid → solid | colour crossfades |
| solid → pulsing | colour and floor crossfade; phase starts here |
| pulsing → solid | colour and floor crossfade; the breath flattens out |
| **pulsing → pulsing** | **phase is held**; only colour and floor move |

That last row is the one that matters. Going from running to awaiting
approval changes the floor from 50 to 10 — restarting the phase would
drop the breath to its trough, and "the heartbeat stopped" reads louder
than "the urgency changed", which is the opposite of what happened.
Phase restarts only when a solid key starts pulsing, or when the period
itself changes.

**Re-issuing the appearance a key is already heading for is a no-op.**
Not just an identical `S` — any `C` or `S` whose colour, floor and period
match the current target returns without restarting either the crossfade
or the breath. So the host never has to track which keys are already
doing what: push the full picture whenever convenient — after every
`HELLO`, on a timer — and only genuine changes are acted on.

Phase, then, is simply "when the key started breathing". Keys whose
states change at different moments drift apart on their own, with no
phase bookkeeping on either side.

An earlier revision also added a fixed per-key offset, to stagger keys
told to pulse in the same instant. It was removed: an offset that is
non-zero at t=0 is exactly a key that does not start at its floor, and
with four keys it put key 2 at full brightness on its first frame —
breaking the fade-up on whichever key held the approval state. The two
properties cannot both hold for simultaneous starts, and fading up won.

**device → host**

| Message | Meaning |
|---|---|
| `HELLO <ver> <keys>` | a host opened the data port |
| `PONG <ver> <keys>` | reply to `P` |
| `K <idx> <0\|1>` | key pressed (1) / released (0) |
| `ERR <msg>` | command could not be handled, or the firmware died |

`<ver>` is 1 for `C`/`B`/`P`/`R`, 2 once `S` exists, and 3 once `X`,
crossfading, and phase-held colour changes exist. Accept anything `>= 1`:
the number says which verbs and behaviours are available, it is not a
compatibility gate. A v3 device needs no `X` to behave correctly — the
default is already 500 ms.

Three behaviours the host depends on:

- **`HELLO` is sent on host connect, not at power-on.** A banner printed
  at boot is lost whenever the host was not listening yet. Treat every
  `HELLO` as "the device just came up — re-push every color."
- **The device clears all LEDs when the host disconnects.** Stale status
  is worse than none; a frozen orange key claims a session still wants an
  answer. Sending `R` before closing is belt and braces, not required.
- **`C` and `S` with an out-of-range index are dropped in silence**, so
  the host may paint before it has learned the key count.

`ERR unknown <cmd>` covers two cases, not one: a verb outside the six,
**and a known verb with the wrong argument count** — `C 0` reports as an
unknown `C`. Misleading, but stable; a host should not read it as "this
firmware lacks that verb".

### When the firmware itself dies

An uncaught exception is the worst failure here and the quietest one:
CircuitPython stops `code.py`, the data port goes silent, and the LEDs
freeze at whatever they last showed. From the host that is exactly what a
board that never booted looks like.

So the loop has a last line of defence. On any escaped exception the
device sends `ERR fatal <type>: <detail>`, paints every key red, and then:

- **after the first minute of uptime** — waits two seconds and resets,
  landing on the recovery path that already exists. The host sees a fresh
  `HELLO` and re-pushes everything; nothing new has to be wired up.
- **within the first minute** — stays halted and red instead. A fault
  that fires on every boot would otherwise reset-loop, and a board whose
  USB re-enumerates every few seconds is hard to write a new `code.py`
  to. Red-and-halted is both the louder signal and the state you can
  actually recover from.

Painting red is best effort: if the fault *was* the I2C bus, it cannot
work, which is precisely when the reset matters most.

A host that wants to notice silent self-healing can watch for `HELLO`
arriving repeatedly in a short window — that is a reset loop, and it is
detectable entirely host-side.

Debug output goes to the *console* port via plain `print`, never to data
— unless `boot.py` did not take effect, in which case there is no data
port and both share the console. The host is told: it gets
`ERR no-data-cdc-check-boot-py` right after `HELLO`.

Keep the protocol layer separate from the transport in the host code: on
BLE these same lines become a GATT characteristic payload.

## Status colors

Tuned on the assembled hardware — clear housings, clear keycaps, normal
desk lighting. Values picked on a screen do not survive that trip.

| Pane state | Color | Motion | Command |
|---|---|---|---|
| no pane, or launcher | off | — | `C n 000000` |
| idle | `273027` | static | `C n 273027` |
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
  WS2812 mixing is coarse enough to visibly flicker. Hence a lighter idle grey
  (white-balanced to `273027` below), and 60% global brightness rather than 30.
- **The same shortage stalls a deep pulse.** At 30% brightness an orange
  pulse with a floor of 5 has a handful of distinct values in its lower
  half, so it freezes at the bottom. Raising global brightness buys steps;
  lowering `PULSE_GAMMA` to 1.0 stops the level crawling through them.
  Dimming via the color value is the same multiply as global brightness,
  so trading one for the other buys no steps — and scaling the color down
  on its own makes the shortage worse.
- **Equal RGB is not neutral, and the correction is level-dependent.**
  The green channel is the weak one, so an equal-RGB value reads purple
  through a clear keycap. What is surprising is that the size of the fix
  is not constant: white needed red and blue trimmed ~6% (`ffffff` →
  `f0fff0`), while idle at the same global brightness needed ~18%
  (`303030` → `273027`). Per-channel efficiency diverges as drive drops,
  so **a single global white balance is wrong at one end or the other by
  construction** — the grey-axis values are corrected individually
  instead, by eye, like every other colour here. The five saturated status
  colours need none of this.
- **Some of the cast is per-LED, and that part is left alone.** With all
  four keys set to one value, key 1 reads neutral while 0, 2 and 3 do
  not. Correcting that needs a per-key gain table, which would be valid
  for this one assembled unit and wrong for the next — so only the
  systematic part is corrected, and the residual spread is accepted. Idle
  is the one colour carrying no hue meaning, so a little variation in it
  costs nothing.
- **Equal amplitude does not read as equal motion across hues.** Cyan sits
  near the eye's sensitivity peak and looks far brighter than blue, so the
  same modulation reads as less movement. Cyan's floor is 40 against
  blue's 50 to compensate.

## Bring-up

1. With USB connected, **hold BOOT, tap RST, release BOOT** → the
   `RPI-RP2` volume appears. Double-tapping RST did not work here on
   2026-08-08 with CircuitPython 10.2.1. Drop the [CircuitPython
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

| What | Measured |
|---|---|
| product string | `Canopy MacroPad` (set by `boot.py`, confirmed in the descriptor) |
| manufacturer | `Saqoosha` |
| VID / PID | `0x239A` / `0x80F8` |
| console port | `/dev/cu.usbmodem20101` |
| data port | `/dev/cu.usbmodem20103` |
| USB interfaces | CDC control (class 2), CDC data (class 10), mass storage (class 8). **No class 3 — no HID.** |
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
HELLO 3 0
ERR i2c bus RuntimeError: No pull up found on SDA or SCL; check your wiring (reset required after fixing)
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
a MagSafe dock) are documented in [docs/canopy-macropad-handoff.md](docs/canopy-macropad-handoff.md) and are
deliberately not built yet — the only requirement now is not to block
them.
