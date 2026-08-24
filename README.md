# Canopy MacroPad

Six keys next to the keyboard. Each key mirrors one Canopy pane: its
LED shows what that pane's Claude session is doing, and pressing it
focuses that pane and brings Canopy forward.

The six are not one board. Keys 2-5 are a NeoKey 1x4 on I2C, keys 0-1
are two single-key breakouts read straight off GPIO, and they butt
together into one 19.05 mm pitch because the breakout happens to be
exactly one pitch wide with its switch centred in it. Which board a key
sits on is invisible to the host: the protocol has one index space and
the device reports its size.

![The inline case, closed with keycaps on, and open with the NeoKey and
the QT Py seated in the shell above the bottom plate](case/images/inline-built.jpg)

The enclosure is the `inline` layout, printed on a Bambu A1 mini. It is
parametric, and it is also **[a model you can turn in a
browser](https://saqoosha.github.io/Canopy-MacroPad/)** — both layouts,
orbit, explode, cutaway. How it is built: [`case/README.md`](case/README.md).

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
CDC control and CDC data, plus mass storage in the states described
under [The CIRCUITPY drive](#the-circuitpy-drive) — no HID class at all,
in any of them.

Two limits worth stating, since the argument above reads as exhaustive
and is not. **The filesystem is still writable from the host**, and the
drive gate below does not change that: any process that can open the
console port has the REPL, and `storage.remount("/", readonly=False)`
from there rewrites `code.py` with no finger going near the device. A
plain `/dev/cu.*` open needs no entitlement, which is exactly the
property this section advertises three paragraphs up. So the threat
model here is "no input injection", not "tamper-proof" — the gate is a
convenience, not a boundary. And a **sandboxed** app would
need `com.apple.security.device.serial` to open the port; Canopy
sidesteps that by not being sandboxed at all (no
`com.apple.security.app-sandbox` key in `Canopy.entitlements`). If that
changes, this design has to be revisited.

## The CIRCUITPY drive

`boot.py` calls `storage.disable_usb_drive()` unless a key is held while
the device boots. The reason is mundane: this pad is unplugged the way
any desk toy is, and a mounted volume disappearing makes macOS say
*"Disk Not Ejected Properly"* every single time, about a disk nobody was
using. Ejecting first works and nobody does it.

**Hold any of the six keys through a boot and `CIRCUITPY` mounts as
before.** Any hard reset counts — replug, `RST`, or
`microcontroller.reset()` — since that is when `boot.py` runs. The GPIO
pair is read first, because two pin reads cost nothing against the
seesaw's 0.5 s software reset, and a key held there skips the bus
entirely. On the I2C side only `0x30` is probed, so a second NeoKey's
keys would not work as the gate. The drive then stays mounted for the
rest of the session, so an edit-and-copy loop needs the finger only
once.

Rather than enumerate the ways the read can fail, state the property
that holds by inspection: **`disable_usb_drive()` is reachable on
exactly one path — a completed read that saw no key held.** Every other
outcome leaves the drive enabled, whether it raises inside the guard,
escapes it, or never returns at all. That direction is deliberate: the
filesystem is how a broken board is recovered, and hiding it exactly
when the board is broken would be the worst possible time. The cost of
failing this way is that the macOS warning comes back, which is merely
the annoyance this whole thing exists to remove.

Which way the gate went is recorded in `boot_out.txt` — transcripts, not
examples; every line below was captured from a real boot:

```
usb drive: disabled; hold a key while plugging in for CIRCUITPY
usb drive: enabled (key held at boot)
usb drive: enabled (gate failed: ImportError: no module named 'adafruit_neokey')
```

Read that file **from the REPL** on the console port — `print(open(
"/boot_out.txt").read())`. Reading it off the mounted drive can only
ever show you the two `enabled` lines, because mounting the drive is
what makes the gate take the other branch and overwrite the line you
came for.

Two other ways back to the files, for when a key cannot be held. From
the REPL, `import storage` / `storage.remount("/", readonly=False)`
gives *the device* write access — the drive stays gone, so a new
`code.py` has to be pasted through serial; `os.remove("/boot.py")` and a
reset is the shorter version of the same idea. Or unseat the Qwiic
cable **and then hard reset** — the gate fails open on the next boot and
hands the drive back. Unseating alone changes nothing; `boot.py` does
not run again until the board does.

## Hardware

| Part | SKU | Role |
|---|---|---|
| Adafruit QT Py RP2040 | ssci 7211 / ADA-4900 | controller, CircuitPython |
| Adafruit NeoKey 1x4 QT | ssci 10048 / ADA-4980 | keys 2-5, on I2C `0x30` |
| Adafruit NeoKey Socket Breakout ×2 | ssci 10047 / ADA-4978 | keys 0-1, on GPIO |
| Qwiic cable 50mm | ssci 6896 / SFE-PRT-17260 | QT Py ↔ NeoKey |
| Durock Ice King Linear ×6 | — | MX compatible, clear housing |
| Clear ABS keycaps ×6 | — | placeholder for printed caps |

**Why not a second NeoKey 1x4**: it gives eight keys, not six, and is
152 mm of board. **Why not the Snap-Apart 5x6 broken to 1x6**: one
uniform board with guaranteed LED consistency, but it carries no seesaw,
so I2C disappears, the drive gate is rewritten, and every error path
proven by injection has to be proven again — for ¥5,088 against ¥858.

The 4978s go to the **left** of the NeoKey, and the cable is what forces
it: on the right they strand the NeoKey's socket 114 mm from the QT Py
against a 50 mm cable. This used to give a second reason — that a mated
Qwiic plug stands 2.50 mm proud of its board edge while a butted
breakout's switch body starts 2.525 mm from that edge, so the two miss
by the tolerance — and it was not a reason at all. The plug hangs below
the board and the switch stands above it, so that pair was never in the
same space. Booleaned since, and then assembled: a plug in the NeoKey's
left socket clears the breakouts, the switches and both printed parts,
and there is a photograph of one sitting in there with both breakouts
butted on. The socket is not blocked; the built unit simply leaves it
empty, because power ended up coming off the headers instead.

Five wires and no per-key soldering — the breakouts ship with Kailh
sockets and their NeoPixels already fitted:

| from | to |
|---|---|
| QT Py `MOSI` | breakout 0 `NEO_IN`; its `NEO_OUT` to breakout 1 `NEO_IN` |
| QT Py `MISO` | breakout 0 `SWITCHA`, pulled up |
| QT Py `SCK` | breakout 1 `SWITCHA`, pulled up |
| NeoKey `JP1`/`JP5` `VIN` | both breakouts' `VDD` |
| NeoKey `JP1`/`JP5` `G` | both breakouts' `GND`, and `SWITCHC` |

Power comes off the NeoKey rather than the QT Py, so only three wires
cross the case. `JP1` and `JP5` are the headers on the NeoKey's long
edges, `INT D C - 3 VIN`, and that `VIN` is the `VCC` net — the one the
STEMMA receptacles' `V+` lands on. The pin marked `3` is the `AP2112K`'s
output and feeds no pixel anywhere.

The NeoKey's spare STEMMA socket carries the same net and sits closer to
the boards, and it was the plan for a while. The schematic has both
receptacles fully parallel — `V+`, `GND`, `SDA` and `SCL` all common —
so the left one is the same node as the right, and a plug goes into it
with both breakouts butted on, which there is a photograph of. It is a
real option and it is not the one taken. A header wins on parts: a
solder joint instead of a connector, and the second cable's other pair
would have been `SDA`/`SCL`, live and terminated in nothing — 50 mm of
unterminated stub on a 100 kHz bus, harmless, but better decided on than
discovered.

Neither tap relaxes the wire channel. Both sit at or beyond the NeoKey's
left edge and the narrowest point in the case is immediately left of
that, so all five wires are still abreast where it matters. What the tap
buys is length, not width.

**Taking power off the NeoKey means the Qwiic cable carries it.** Pull
that cable and keys 0 and 1 lose their supply and their ground reference
together: the pixels go dark, `SWITCHA` floats high through its pull-up,
and they report as never pressed. The device stays up and still says
`HELLO 3 6`. Every *other* I2C fault — a missing library, a wrong
address, a seesaw that stops answering — still costs exactly the four
keys behind it, which is what the firmware's separate guards are for. So
the promise is narrower than it reads elsewhere: **a dead NeoKey costs
four keys, a dead cable costs six.** Running `3V` and `GND` from the QT
Py instead buys the wider promise back, for two more wires through that
lane.

Each breakout carries a 1N4148 from `SWITCHA` to `SWITCHC`, so grounding
`SWITCHC` makes a press read low. The forward drop at the ~55 µA an
internal pull-up supplies is about 0.45 V, under the RP2040's 0.8 V
V<sub>IL</sub> but not by much: a key stuck reading pressed is the
symptom of that being wrong, and an external pull-up is the fix.

Both boards carry the same pixel — the schematics name it `_SK6812E`,
same device on both — and on the NeoKey it runs off `VCC`, the incoming
Qwiic rail, *ahead* of the `AP2112K-3.3` that feeds the seesaw. A
`74*1G125` shifts the seesaw's data up to that same rail. So the pixels
see whatever the cable brings, and the status colours below were tuned at
whatever that is.

That is the argument for the colours carrying over: identical part, and
one net. Traced through both schematics rather than assumed — the QT Py's
`3V` pad, its STEMMA `V+` and its regulator output are all `+3V3`; the
cable carries that to the NeoKey's `VCC`, which is what its four pixels'
`VDD` and its `JP1`/`JP5` `VIN` sit on. Wherever the breakouts are
tapped, they are on the same node as the pixels the colours were tuned
against.

Which settles the topology and not the question. What the colours
actually depend on is the **voltage under load**, and six SK6812s at full
white pull it down through a connector, a cable and however much wire
this case makes them share. Same net says nothing about the drop across
it.

The tap point does matter, and not for the reason it first looks. One net
does not mean one potential: taking the breakouts off the QT Py leaves
the NeoKey carrying the Qwiic cable's drop alone, so the two halves land
at different voltages and drift apart in colour. Taking them off the
NeoKey puts that drop in front of all six at once. It does not make the
difference vanish — the breakouts still sit behind their own wire — it
removes the cable's share of it. Whether any of this is visible is a
different question again, since the rail is already about 200 mV below an
SK6812's datasheet floor before a single wire is counted.

**The rail has still not been metered, and it no longer needs to be.**
The voltage was only ever a proxy for a question that can be looked at
directly: on the assembled unit, all six set to `ffffff` at `B 100` —
the worst case, three dies lit on every pixel, the breakouts' current
crossing the cable too — the two halves are the same white. So the
argument above was right, and the tap point stopped being a colour
decision. If a number is ever wanted anyway, `tools/mpad.py --load`
produces that same worst case; probe at an LED's `VDD`, not at the QT
Py.

**The pixels are not identical to each other, though.** One of the six
sits slightly purple against the other five under that test, and it does
not follow the supply — it is on the same node as its neighbours, and
they agree. It is part-to-part variation in the LED. Worth writing down
because the alternative explanation is the rail, and the rail is now
exonerated: a small mismatch found later is a pixel, not a wire.

One consequence worth knowing before anyone "fixes" it. An SK6812's
datasheet floor is 3.5 V and its green and blue dies drop out first, so a
3.3 V rail shows up as a warm shift rather than as darkness. If that is
what this is, all six keys are equally under it and equally warm, which
is the outcome that makes them match — so **do not feed the breakouts 5 V
on their own.** That would fix two keys, break the match, and leave the
breakouts needing a level shifter the NeoKey already has. Both rails or
neither.

Key count is never hardcoded in Canopy — the device reports it in
`HELLO` — and `tools/mpad.py` now reads it from `PONG` rather than
assuming.

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

**These values are tuned against a supply voltage nobody has written
down.** The pixels sit on the incoming Qwiic rail rather than behind the
NeoKey's regulator, so the number that produced this table is whatever
the QT Py hands the cable, minus whatever 50 mm of thin Qwiic conductor
drops under load. Until it is measured the whole table rests on a
variable. Measuring it:

```
tools/mpad.py --load       # every key full white at brightness 100
```

Three things about that reading, each of which changes what it means:

- **Probe at an LED's `VDD`, not at the QT Py.** The two differ by
  exactly the cable drop being looked for.
- **Under full white, not at idle.** Idle is the flattering case and it
  is not the case that browns out. `--load` exists to produce the other
  one; the shipped brightness of 60 is not what the supply has to
  survive.
- **Take it at four keys and again at six.** One number cannot separate a
  cable drop from a regulator giving up; two can, because they fail
  differently — a regulator at its limit lets go all at once, a cable
  sags gradually and shifts colour on the way. If six reads much below
  four, suspect the cable first: it is the cheapest thing in the stack to
  replace, and a shorter or thicker one needs no redesign.

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
   Bundle](https://circuitpython.org/libraries), copy `adafruit_neokey/`,
   `adafruit_seesaw/` **and `neopixel.mpy`** into `CIRCUITPY/lib/`.
   `neopixel` is the one the breakouts need; without it keys 0-1 still
   report presses and simply never light, and the host is told
   `ERR gpio pixels ...`. `adafruit_hid` is not needed and must not be
   used.
3. Copy `firmware/boot.py` **and** `firmware/code.py` to `CIRCUITPY/`,
   then **hard reset**. `boot.py` only re-runs on a hard reset, and only
   a hard reset re-enumerates USB, which is what actually applies the CDC
   interface change. Unplug and replug, or from the REPL on the console
   port: `import microcontroller` / `microcontroller.reset()`.
4. `ls /dev/cu.usbmodem*` — two ports must appear (console and data).
   Give it a second or two: the keypad gate runs before USB enumerates
   and costs about half of one. One port after that means `boot.py` did
   not take effect; repeat step 3, and note that in *that* failure the
   gate never ran either, so `CIRCUITPY` is still mounted to repeat it
   with.
5. `CIRCUITPY` is now gone, which is `boot.py` working as intended — see
   [The CIRCUITPY drive](#the-circuitpy-drive). Hold a key through the
   next hard reset to get it back for the next copy.
6. `tools/mpad.py --probe` — reports which port is data, plus the VID,
   PID and product string the macOS side matches on.
7. `tools/mpad.py --demo` — reads the key count off `PONG`, lights that
   many keys, then turns each one white while it is held. This is the
   whole loop: LED out, key in. Six keys lit means both halves of the
   keypad came up; four means the breakouts did not.
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

That table is what the instrument said on that date, and the drive gate
did not exist yet — mass storage was unconditional then. It is not any
more; see [The CIRCUITPY drive](#the-circuitpy-drive) for which boots
carry it. The port names shift with it, since macOS derives the
`usbmodem` suffix from the interface layout, which is one more reason
for the paragraph below.

The data port took the higher trailing number here, but do not select on
that. `P` → `PONG` is the only reliable discriminator: the console port
runs the REPL, which echoes `P` as typed text and never answers.

**And do not select on the PID either.** `boot.py` sets the manufacturer
and product strings and nothing else, so the VID and PID are whatever the
CircuitPython build carries — a property of the binary, not of this
firmware and not of the product. The same `boot.py` on the custom PCB,
running a stock `raspberry_pi_pico` build, measures `0x239A` / **`0x80F4`**
against the QT Py's `0x80F8` above. Both readings are correct; neither is
the device's identity.

So **`Canopy MacroPad` is the identifier**, and `P` → `PONG` is the port
test. `tools/mpad.py` was already written that way — it matches the VID
and the product string and never looks at the PID, which is why it found
the PCB unchanged. A host that matches on the PID will not.

Setting a fixed VID/PID in `boot.py` would make the identity independent
of the build, and is deliberately not done — **and the host agrees.**
Canopy matches on the product string plus the vendor id (accepting a
missing vendor), and `MacroPadDevice.swift` says why the product id is
left out: it belongs to the board and the CircuitPython build rather than
to this project, so pinning it would *fail closed*, and a device that
never connects looks exactly like a bad cable. So the PCB's `0x80F4` costs
nothing on that side, and pinning a PID here would only reintroduce the
coupling both halves went out of their way to avoid.

### When the keypad is missing

`board.STEMMA_I2C()` raises `RuntimeError: No pull up found on SDA or SCL`
when the Qwiic cable is not seated — the I2C pull-ups live on the NeoKey
board, not the QT Py. The firmware catches this and keeps the serial half
running rather than dying, so the host sees:

```
HELLO 3 6
ERR i2c setup RuntimeError: No pull up found on SDA or SCL; check your wiring (reset required after fixing)
```

The verb is `setup`, not `bus` — this document said `bus` until the
`ImportError` half of it was captured off a real board, which arrives on
the same path and reads `ERR i2c setup ImportError: no module named
'adafruit_neokey' (reset required after fixing)`. `code.py` builds both
from one `"setup {}: {}"`.

**The key count does not drop.** It used to: `HELLO <ver> 0` meant
"device present, keypad absent". It cannot any more, because the GPIO
half cannot fail to enumerate and key 2 has to stay key 2 whether or not
the NeoKey answered — the host maps index to pane, and letting the
boards renumber when a cable is out would quietly focus the wrong
session. So the count is always 6 and the `ERR` is what says which half
is missing. The host should hold the connection and paint normally; the
four keys behind the missing board simply do not light, and writes to
them are dropped in silence exactly like an out-of-range index.

`CIRCUITPY` comes back in this state, because the same missing keypad
fails the drive gate open. That is a useful tell rather than a second
fault: drive present *and* two ports means the gate could not read the
keypad, and the keypad is what to go and look at.

### When nothing enumerates

No `RPI-RP2`, no `/dev/cu.usbmodem*`, and no VID `0x239A` in `ioreg -p
IOUSB -w0 -l`: the board is not on the bus at all. A missing `CIRCUITPY`
is *not* part of this symptom — that is the normal state now, and says
nothing either way; go by the ports. In
descending order of likelihood — a charge-only USB-C cable (most USB-C
cables sold with phones carry no data pairs), a hub or dock passing power
but not data, or a dead cable. Try a known-good data cable straight into
the Mac before suspecting the board.

## Phase 1 scope

Six keys, USB wired, status out and focus in. The enclosure was a later
phase and arrived early: `inline` is printed and in use, `stacked` exists
only as geometry. See [case/](case/).

The six-key half of what used to be Phase 2 is built in software and
geometry and **has never been assembled** — the two 4978 boards are not
bought yet, so nothing below the protocol has been seen working. The
`inline` case in the photo above is the four-key one.

The rest of the later phases — low-profile Choc switches, and wireless on
a MagSafe charger — are sketched in
[docs/canopy-macropad-handoff.md](docs/canopy-macropad-handoff.md) and are
deliberately not built yet. The only requirement now is not to block
them.

The wireless one has since been costed properly, without anything being
built:
[docs/wireless-and-magsafe-findings.md](docs/wireless-and-magsafe-findings.md)
carries Apple's own magnet-ring dimensions, why the Qi coil rather than
the magnets is what decides the case depth, why Qi is pointless without
BLE, and why the board to move to is a XIAO nRF52840 rather than the
nice!nano the handoff names.

## License

MIT — see [LICENSE](LICENSE). The case geometry is covered by it too;
print it, change a number, sell one.
