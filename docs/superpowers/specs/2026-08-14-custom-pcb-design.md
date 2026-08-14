# One board, six keys

Replace the three Adafruit boards and the QT Py with a single custom PCB,
assembled by JLCPCB. Smaller footprint, and a low-profile switch option
that the current stack cannot express.

Nothing above the device changes. `PROTOCOL_VERSION` stays 3, `HELLO 3 6`
stays, and the macOS half is not touched.

## What this is measured against

The six-key wired pad, built and working:

| | today |
|---|---|
| boards | NeoKey 1x4 + 2 x 4978 breakout + QT Py RP2040 |
| case (`inline`) | 158.60 x 26.00 x 13.33 |
| key field | 114.30 x 21.59, six switches at `9.525 + n x 19.05` |
| wiring | five hand-soldered wires plus a 50 mm Qwiic cable |
| key reads | four on I2C seesaw, two on GPIO, one index space |

## Three switches, one footprint

The pad has to take three switches off the same board. Read out of the
manufacturers' drawings, not product pages:

| | full MX (Durock Ice King) | Outemu GTMX | Kailh Choc v1 |
|---|---|---|---|
| drawing | -- | GaoTe `PG618B65` | Kailh `CPG135001D01` |
| plate cutout | 14.00 | **14.00** | 13.80 |
| PCB to plate top | 5.00 | **5.00** | 2.20 |
| plate thickness | 1.50 | **1.50** | 1.20 - 1.30 |
| body above plate | ~10.0 | **7.00** | ~8.8 |
| PCB pattern | Ø4.00 + 2 x Ø1.50 | **same** | Ø3.40 + 2 x Ø1.90 |
| hot-swap socket | Kailh MX | **Kailh MX** | Kailh PG1350 |
| LED window | 3535 | **2835** | 5.00 x 3.15 |

**GTMX is MX below the plate and short above it.** Its cutout, its PCB
pattern, its socket and its 5.00 are the numbers this case already has --
so it changes the case by nothing at all, and takes 3 mm off the top of
the keycap. That is the whole reason it is the primary switch here.

Choc is the only one that moves the stack, and it moves it by 2.80.

So the board carries a **combo footprint**: the MX pattern and the Choc
pattern on the same pads, an arrangement that is standard practice and
has existing KiCad libraries (`kiswitch/keyswitch-kicad-library`,
`50an6xy06r6n/keyboard_reversible.pretty`). One PCB, three switches, and
the switch is chosen when the sockets are soldered rather than when the
board is ordered.

Both patterns sit on the same 19.05 pitch. Choc keycaps are 18.00, so
they leave 1.05 of gap where MX leaves nothing -- accepted, because the
alternative is two board revisions.

## The board

**121.60 x 21.59 mm**: the key field at 114.30, plus 7.30 at the right
end for the USB-C receptacle. 1.60 thick, four layers -- the RP2040 wants
a ground plane under it and a two-layer board would have to buy that
plane with routing space this outline does not have.

### Everything is on the back face

The back of a keyboard PCB is not empty -- the hot-swap socket already
forces 1.85 mm of clearance under it, and this case already carries that
clearance as `SOCKET_CLEARANCE`. Everything on the board fits inside it:

| part | height under board |
|---|---|
| Kailh MX hot-swap socket | 1.85 |
| RP2040, QFN-56 | 0.90 |
| QSPI flash, SOIC-8 | 1.75 |
| 12 MHz crystal, 3225 | 0.80 |
| LDO, SOT-23 | 1.10 |
| 0402 passives | 0.50 |

And there is room in plan as well as in Z. The socket occupies
y 11.65 - 17.55 of the field's 21.59 depth (measured off
`ref/neokey-breakout.step`, the one Adafruit model that includes its
socket), which leaves a band roughly 114 x 11 running the whole length of
the board under the switches.

The one part that does not fit is the USB-C receptacle at 3.16. It gets
a local pocket in the bottom plate, which is 2.40 thick and can give up
1.00 without argument.

**So the assembly is single-sided.** The top face carries switch pads and
nothing else. That is a real saving on a PCBA order, and it is a
consequence of the geometry rather than a goal that bent it.

### Bill of materials

- RP2040, `C2040`. Stocked at JLCPCB for both Economic and Standard
  assembly.
- QSPI flash, 8 MB, to match the QT Py RP2040 -- see "The firmware that
  is already written" below.
- 12 MHz crystal, 3.3 V LDO, decoupling per the RP2040 hardware design
  guide, BOOT button.
- USB-C 16-pin receptacle, 2 x 5.1 kΩ CC, ESD diodes.
- Six **SK6812MINI-E** reverse-mount addressable RGB, one per key,
  `C5149201` at JLCPCB. Same controller family and same mount style as
  the NeoKey's, which is the point: the status colours in `README.md`
  were tuned on reverse-mount SK6812-class pixels and stay valid.
  Adafruit's own description of the NeoKey -- "mounted on the back of
  the board to shine through to the top" -- is the arrangement this
  board copies.

  Its body is a 3528, i.e. 3.5 x 2.8, which is the same package GTMX's
  drawing calls for by its other name, 2835. That is not luck; it is
  the size keyboard switches leave room for.

  **`SK6812MINI-E` and `SK6812MINI-EA` are not interchangeable on an
  order.** One is reversed in the tape and one has to be placed
  upside-down by explicit instruction to the assembler. Getting this
  wrong lights the inside of the board six times over, and the boards
  arrive looking perfect.
- Six Kailh hot-swap sockets, MX or PG1350, **hand-soldered after the
  PCBA order**. They are the one thing the board must not have decided.

**No diodes and no matrix.** Six keys go straight to six GPIO with
internal pull-ups; a press pulls its pin low. The RP2040 has thirty
GPIO and this board needs seven, so a matrix would save no pins and
would buy a ghosting argument that direct wiring never has to make.

### The firmware that is already written

Wire the six key pins and the LED chain to the **GPIO numbers the QT Py
RP2040 uses**, and put the same 8 MB QSPI flash on the board. Then
Adafruit's released CircuitPython UF2 runs on it unmodified -- no board
definition to author, no toolchain to build, and `board.MOSI` goes on
meaning the pin it has always meant.

From `ports/raspberrypi/boards/adafruit_qtpy_rp2040/pins.c`:

| name | GPIO | | name | GPIO |
|---|---|---|---|---|
| `MOSI` | 3 | | `TX` | 20 |
| `MISO` | 4 | | `SDA` | 24 |
| `RX` | 5 | | `SCL` | 25 |
| `SCK` | 6 | | `A3`..`A0` | 26..29 |
| `NEOPIXEL` | 12 | | `NEOPIXEL_POWER` | 11 |

Eleven pins are broken out and seven are needed. The GPIO chosen for
keys and for the LED chain are a layout convenience -- every one of them
is an ordinary GPIO -- so this costs the routing nothing.

`NEOPIXEL` (GPIO12) is deliberately **not** the LED chain. On a QT Py it
is gated by `NEOPIXEL_POWER`, and a pixel line that needs a second pin
driven high before it works is a failure mode with no symptom. The chain
goes on a plain GPIO.

The firmware is still rewritten -- the point is that the *platform* is
not.

## Firmware

The two halves become one. `adafruit_neokey` goes, the seesaw goes, the
I2C bus goes, and with them `GPIO_BASE` / `SEESAW_BASE`, the per-pad
`get_keys()` guards, and the whole `ERR i2c ...` family.

What replaces it is the GPIO source that already exists, widened from
two keys to six, and one `neopixel.NeoPixel` of length six.

**What this costs, stated plainly.** Three error paths proven by fault
injection stop existing, because the faults they catch stop being
possible. `ERR i2c setup`, `ERR i2c lost at runtime` and the
cable-unplugged row of the known-good table all describe hardware that is
not on this board. That is a smaller device, not a better-tested one --
the new paths get the same treatment, by injection, before they are
believed.

What survives unchanged: the protocol and every verb, the status colours,
crossfade, pulse, phase handling, debounce, the fatal handler and its
60 s brake, `boot.py`'s drive gate (now reading six GPIO and no I2C at
all), and the dual `usb_cdc` split with tracebacks on the console port.

`NUM_KEYS` stays a constant 6. `HELLO 3 6` stays. The host cannot tell.

Known-good answers shrink to:

| State | The device says |
|---|---|
| healthy | `HELLO 3 6`, `PONG 3 6` |
| `neopixel` missing | `HELLO 3 6` + `ERR gpio pixels ...`, keys dark, presses still reported |
| died past 60 s uptime | `ERR fatal ...`, all keys red, port drops, fresh `HELLO` |
| died inside 60 s | `ERR fatal-halted ...` on every later connect, stays red |

## Case

`MPAD_LAYOUT` has done its job. It selected where the QT Py sits, and
there is no QT Py -- so `stacked` and `inline` both retire, and with them
the QT Py pocket, its rails, its lip, its STEMMA notch, the wire lane and
the cable bay.

The new axis is **`MPAD_SWITCH=mx|choc`**, and GTMX is `mx` -- the case
cannot see the difference, because every number it reads is identical
and the 3 mm GTMX saves is above the plate where the case ends.

Derived from the switch:

| | `mx` | `choc` |
|---|---|---|
| `SWITCH_HOLE` | 14.15 | 13.95 |
| `PLATE_TOP_TO_PCB` | 5.00 | 2.20 |
| `PLATE_T` | 1.60 | 1.30 |
| `SOCKET_DROP` | 1.85 | 1.90 |
| `CASE_H` | **12.25** | **9.50** |

Both hole figures are nominal plus this machine's 0.15 shrink, the
constant `SWITCH_HOLE` has always measured. 14.15 is settled on a printed
part; 13.95 is arithmetic and goes to the coupon.

`CASE_H` is derived, not chosen, and it is worth writing the sum out so
it can be argued with:

```
mx     2.40 floor + (1.85 socket + 1.40 air) + 1.60 board + 5.00  = 12.25
choc   2.40 floor + (1.90 socket + 1.40 air) + 1.60 board + 2.20  =  9.50
today  2.40 floor + (2.96 receptacle + 1.40 air) + 1.57 + 5.00    = 13.33
```

The middle term is the whole story. Today's 2.96 is the STEMMA QT
receptacle hanging under the NeoKey -- a connector this board does not
have -- and deleting it is where every millimetre of the `mx` saving
comes from. The plate gap above the board is a switch standard and
cannot be argued down, which is why `mx` saves 1.08 and `choc` saves
3.83.

Locating pegs go. A plate-mount switch clips into the top plate and its
pins go into the socket, so the switch ties plate to board -- the same
thing the first assembled six-key unit found for the breakouts. What
holds the board is its outline and the screws.

`build.py` must end in `all checks passed` for **both** switch settings
before anything is printed, and the mock has to gain the new board and
lose three old ones. Every stand-in models the mated plug, not the
connector, because that mistake has happened four times here.

## The EDA tool: EasyEDA

Both candidates were driven by an agent and measured against the
question this repository always asks: can the result be read back and
asserted, rather than looked at. **Both passed it.** The decision
therefore turned on what neither of them proved about placement, and on
one observation about this repository's own habits.

### KiCad, measured

Proven on this machine, headless, no GUI opened. A script created a
board, placed two real `SW_Cherry_MX_1.00u_Plate` footprints, saved,
**re-read the file from disk** and measured the gap:

```
SW1 x = 9.525000   SW2 x = 28.575000
measured pitch = 19.050000   wanted 19.05
all checks passed
```

The check was **watched failing first** -- placed at 19.00 it reported
`FAIL: pitch is off by -0.050000000 mm` -- so the green means something.
`kicad-cli` then exported Gerbers from the same file. The board is
s-expression text: `(at 28.575 10.795)` is literally greppable, which
makes it diffable and reviewable the way `params.py` is.

Version here is KiCad **10.0.5**, `pcbnew` importable from the app's own
Python. One trap, recorded because it cost a wrong diagnosis: a write to
`/tmp` is killed by the sandbox with **SIGKILL and no traceback**, which
reads exactly like a crash inside `pcbnew`.

### EasyEDA, measured

Six **Kailh `CPG151101S11`** hot-swap sockets -- the exact part this
board's BOM names, found in the library by its manufacturer number --
placed through the API and read back from it:

```
xs:   [1000, 1750, 2500, 3250, 4000, 4750]
gaps: [750, 750, 750, 750, 750]
pass: true
```

750 mil is 19.05 mm exactly, and that row is this pad's key field. The
check was **watched failing first**, at an injected 700, and the
injected run also reported `clearedTo: 0` so it was measuring the new
placement rather than surviving components.

`pcb_ManufactureData` then produced a real Gerber: `[object File]`,
9522 bytes. Beside it are `getBomFile`, `getPickAndPlaceFile`, and
`placePcbOrder()` -- the order itself, from the API.

Three things cost a round each and are worth carrying:
`createProject()` is beta and returns `undefined` silently (use an
existing project); enums are **not** in the execution context, so
`EPCB_LayerId.TOP` throws and the documented literal `1` is what works;
and `pcb_PrimitiveComponent.create` wants a **device**, not a footprint
-- passing a footprint item fails with a destructuring error about a
property the item plainly has.

### Getting there, and the tooling that is not it

The English-language search returns third-party MCP servers whose write
paths are beta or disabled. **They are the wrong tooling**, and one of
them was installed and removed here before the right one was found. The
real path is first-party and is a *skill*, not an MCP:

- `github.com/easyeda/easyeda-api-skill`, the `easyeda` org's own repo
- extension `run-api-gateway.eext`, publisher `oshwhub-official`
- a Node bridge on ports **49620-49629**; the agent POSTs **JavaScript**
  to `/execute`, running against the client's `eda` API

That last point matters more than it looks, because it dissolves the
argument that would otherwise decide this. A board built by executing
code is a board built from a script, and a script is text that can hold
`9.525 + n * 19.05` and live beside `case/params.py`. **The
"scripted, therefore checkable" property is not exclusive to KiCad.**

PCB coordinates there are in **1 mil**, so the pitch is exactly 750
units and rounding cannot be blamed for anything. Schematic coordinates
are 0.01 inch; mixing the two misplaces parts by 10x.

**Do not install a third-party EasyEDA MCP alongside the official
bridge** -- they squat the same 49620-49629 range and fight.

**The gateway needs a permission that its manifest does not request.**
`run-api-gateway`'s `extension.json` has no `allowExternalInteraction`,
so `eda.sys_WebSocket.register()` opens no socket at all until *Allow
interactive with external* is ticked by hand in Extension Manager →
Config. Until then the extension reports `Bridge not found` while a
perfectly healthy bridge answers, and *Show at header menu* on the same
panel is what makes its `API Gateway` → `Reconnect` menu exist. Two
symptoms, one screen, and neither is a bug.

### Why not KiCad, given it also passed

KiCad placed `SW_Cherry_MX_1.00u_Plate` at 19.050000 exactly, read it
back, was watched failing at 19.00, and exported Gerbers -- all headless
with no GUI. It keeps two properties EasyEDA gives up: it runs without
an application open, and its board is s-expression text, so `(at 28.575
10.795)` is greppable and diffable. EasyEDA's project is a single
SQLite `.eprj2`.

That second loss is smaller than it looks, because **this repository
already commits binary artefacts and keeps the source parametric.**
`case/out/` holds STLs, STEPs and PNGs; what is reviewed is
`params.py`. A `.eprj2` is that same shape of thing, and the reviewable
source is the script that builds it -- which can hold `9.525 + n *
19.05` and share it with `case/params.py`, exactly as intended.

What EasyEDA has and KiCad does not is the back half: the socket in the
BOM was in the library under its own part number, the fabrication
outputs are native rather than a plugin, and the order can be placed
from the API. The failures this board can actually suffer -- a
footprint that is not the real part, a part not in stock, a rotation
that turns six LEDs sideways -- all live there.

## Host tools and documentation

`tools/mpad.py` needs nothing. It was widened to six keys for the wired
build and the key count has not moved.

`README.md` and `AGENTS.md` both describe hardware that this board
replaces, and the claims that go wrong are specific rather than general:
the three-board hardware table, the Qwiic cable, the five wires, the
`ERR i2c ...` rows of the known-good table, the "a dead cable costs all
six" paragraph, and the two `MPAD_LAYOUT` names. `CLAUDE.md` is a symlink
to `AGENTS.md`, so that is one edit and not two.

The wired pad is not deleted from the documents. It is a built, working
device and the numbers it settled -- the 0.15 shrink, `PILOT_DIA` 2.95,
`SCREW_CLEAR_DIA` 3.70 and `CLEAR_RING_MAX` -- are inherited whole by
this case. What changes is which one the documents describe **first**.

## Verification

Ordered so that nothing expensive waits on something cheap.

1. `python3 -m py_compile firmware/*.py tools/mpad.py`
2. `MPAD_SWITCH=mx build.py` and again for `choc`, both `all checks
   passed`; then the full render sweep per switch, because `build.py`
   only rewrites the STLs and STEPs.
3. Print `coupon.stl` for `choc`. It asks two new questions: does a Choc
   seat in 13.95, and **does a 1.30 printed plate hold its clips**. The
   `mx` coupon asks nothing new.
4. Order **5 boards**, JLCPCB minimum. Continuity and shorts before
   power, on the first one, before the other four are touched.
5. Flash the stock QT Py RP2040 UF2. If it enumerates, the flash and
   crystal choices were right and no board definition is needed.
6. `tools/mpad.py --probe` reports `PONG 3 6`.
7. `--demo`: six keys light, each goes white while held.
8. Fault injection on every new error path, each one watched to fire
   before it is believed, and each with the negative control run.
9. Focus a text editor and press all six. Nothing is typed.

## Open, deliberately

- **The LED's aperture, not its package.** The part is settled and so is
  the mount style, and that turned out to move the question rather than
  answer it. A reverse-mounted pixel sits *under* the board and throws
  light up through a hole in it, so the package never has to fit inside
  a switch's window -- only the light does. What is unsettled is
  therefore **where the hole goes**, and whether each of the three
  housings is actually open above it.

  Three windows disagree on position as well as size: 3535 on full MX,
  2835 on GTMX at the offsets its drawing gives, 5.00 x 3.15 on Choc.
  One hole has to serve all three or the board favours one switch.

  Settled by looking, and it costs nothing: **turn a GTMX and a Durock
  and a Choc upside down and see where each one is open.** All three are
  on the desk. The NeoKey's own LED position, 5.08 south of switch
  centre, is the incumbent answer and the thing to check first.

- **Hot-swap socket stock at JLCPCB has not been checked**, and does not
  need to be. The sockets are hand-soldered after assembly on purpose,
  so they cannot block an order.

- **Choc's 2.20 was read off a drawing, and the drawing is a figure.**
  It is the number the community uses and it is consistent with the
  1.20 - 1.30 plate the same sheet calls for, but nothing here has
  measured a Choc switch. `CASE_H` = 9.50 rests on it entirely. The `mx`
  column does not -- its 5.00 is the number this case has been printing
  against since the beginning, and the GTMX sheet independently agrees
  with it.

- **The USB-C receptacle's 3.16 is a class figure, not a part.** No
  connector has been chosen, and the bottom-plate pocket is sized from
  it. Pick the part before drawing the pocket.

- **`PLATE_T` 1.30 for Choc may not print usefully.** The clips need to
  grab, and 1.30 is six or seven layers. The coupon is the whole test.

- **The USB-C pocket in the bottom plate is a membrane risk.** A 1.00
  pocket in a 2.40 plate leaves 1.40, and a boolean cannot see a
  membrane -- it reports 0.000 whether the material is there or not.
  This needs a thickness check, not an interference check.

## Rejected, with reasons

- **A castellated module (XIAO / QT Py) dropped into a cutout.** Zero
  firmware risk and hand-solderable, but 21 mm of width, and the USB-C
  position becomes the module's decision rather than the case's. The
  back-face band gives the same safety for less.
- **RP2350A.** This pad does not need a newer core, and choosing it
  gives up the largest single advantage on offer -- that a released UF2
  boots the board.

- **RP2354A, which stacks the flash into the package.** The real
  temptation, and the closest call here. It is an RP2350A die plus a
  Winbond `W25Q16JVWI` in one QFN-60, pin-identical to the flashless
  part, for $0.20 -- so it deletes the SOIC-8 and its six QSPI traces
  outright.

  It was declined because **the flash chip is not charging us in a
  currency we are short of.** The socket has already bought 1.85 of
  height and the part is 1.75; the free band is 114 x 11 and the part is
  5 x 6. What RP2354 saves is surplus. What it costs is not: 2 MB is the
  whole stacked device, no released CircuitPython build targets it, and
  authoring a board definition turns the firmware into an artefact this
  project owns and has to rebuild on every CircuitPython release. That
  is a standing obligation traded for a part that fits in space nothing
  else wants.

  **The condition under which it wins is worth naming**, because it may
  arrive: if a custom CircuitPython build ever becomes necessary for
  some other reason, the released-UF2 advantage is already gone, the
  flash chip becomes pure cost, and RP2354A is then the right part.

  Not a reason either way: **erratum RP2350-E9**. It latches a pin
  configured as a **pull-down**, and every key input here is a pull-up
  with the switch to ground -- the opposite arrangement. A3 and A4
  stepping address it regardless, and RP2354 is built on those.
- **A key matrix.** Six keys, eleven pins. A matrix adds diodes and a
  ghosting argument to save nothing.
- **Two board revisions, one per switch.** The combo footprint costs
  1.05 of keycap gap on Choc. Two orders cost two orders.
