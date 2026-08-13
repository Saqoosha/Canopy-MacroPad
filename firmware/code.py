"""Canopy MacroPad — main firmware.

The device is deliberately dumb: it reports key edges and paints the
colors it is told to paint. All meaning (which pane, which status, when
to pulse) lives in the host. That split is what lets the same wire
protocol survive the move to BLE later.

Wire protocol, line-delimited ASCII on usb_cdc.data.

  host -> device
    C <idx> <rrggbb>   set key idx to that color, e.g. `C 0 ff8000`
    S <idx> <rrggbb> [ms] [floor]
                       pulse that color, sine-eased. `ms` is the full
                       period (min 100), `floor` is the percentage the
                       dip bottoms out at, 0-100: 0 reads as an alert,
                       50 as a slow breath that says "alive" without
                       asking for attention. Defaults: 2000 ms and 0.
                       Both are clamped silently.
    B <0-100>          global brightness
    X <ms>             crossfade duration for C and S, default 500
    P                  ping
    R                  reset: all keys off, immediately

  device -> host
    HELLO <ver> <keys> sent when a host opens the data port
    PONG <ver> <keys>  reply to P
    K <idx> <0|1>      key idx pressed (1) / released (0)
    ERR <msg>          a command could not be handled

`C` and `S` drop out-of-range key indices in silence; the host may paint
before it has learned the key count.

Every change of color or floor is crossfaded (except `R` and a host
disconnect, which are immediate), so a state change reads as
a state change and not as an alarm. Solid is modelled as a pulse whose
floor is 100%, which is what lets one interpolation cover all four
transitions -- solid to solid, solid to pulsing, pulsing to solid, and
pulsing to pulsing -- with no special cases.

**A pulsing key keeps its phase when only its color or floor changes.**
Resetting it would drop the breath back to its trough, and "the heartbeat
stopped" reads louder than "the urgency changed", which is the opposite
of what happened. Phase restarts only when a solid key starts pulsing, or
when the period itself changes.

Nothing else is written to the data port, and debug output goes to the
console port (plain `print`) which the host does not read — with one
exception. If `boot.py` did not take effect there is no data port, and
this falls back to the console, where protocol lines then share a stream
with the REPL banner and any tracebacks. The host is told so explicitly:
it receives `ERR no-data-cdc-check-boot-py` right after `HELLO`.
"""

import math
import time

import board
import microcontroller
import usb_cdc

# adafruit_neokey and neopixel live in CIRCUITPY/lib, so they are the
# imports that can be missing -- a board flashed without the bundle, or
# with one for the wrong CircuitPython major. That is the same class of
# operator error as a missing Qwiic cable, which this firmware goes to
# real trouble to survive; at module scope they instead raise straight
# to the REPL and produce the silent brick everything else here is built
# to avoid. Imported inside the setup guards below instead.
#
# Two guards rather than one, because the two halves of the keypad fail
# independently now: a missing `neopixel` must not cost the NeoKey its
# LEDs, and a missing Qwiic cable must not cost the breakouts theirs.
NeoKey1x4 = None
NeoPixel = None

# 1: C / B / P / R
# 2: adds S (device-side sine pulse)
# 3: adds X, crossfades every C/S, and holds phase across a colour change
PROTOCOL_VERSION = 3

# The I2C addresses of the NeoKey boards, in physical left-to-right key
# order. This tuple is the single source of truth for how many boards
# exist -- deriving it the other way round (a count that slices a longer
# address list) silently clamps instead of failing. A second board needs
# its A0 jumper bridged on the back to answer 0x31.
PAD_ADDRESSES = (0x30,)
KEYS_PER_PAD = 4
SEESAW_KEYS = KEYS_PER_PAD * len(PAD_ADDRESSES)

# Keys 0 and 1: two Adafruit 4978 NeoKey Socket Breakouts, read straight
# off GPIO. They carry no seesaw, so there is nothing to address and
# nothing to enumerate -- which is why this is the half that cannot fail
# to come up, and why the key count below can be a constant.
#
# Each breakout puts its switch in series with a 1N4148 running SWITCHA
# to SWITCHC. SWITCHC goes to ground, so a press pulls its input low
# through the diode. The forward drop at the ~55 uA an internal pull-up
# supplies is about 0.45 V, under the RP2040's 0.8 V V_IL but not by a
# wide margin: a key that reads permanently pressed is the symptom of
# that number being wrong, and an external pull-up is the fix.
#
# Pin *names*, resolved against `board` inside the setup guard rather
# than here. `board.MISO` on a build that lacks it is an AttributeError
# at module scope, which is the silent brick again -- and a wrong-board
# flash is exactly when you want the serial half still talking.
#
# In physical left-to-right order, which here means these come *before*
# the NeoKey's four. All three pins sit on the QT Py's 3V/GND edge, so
# the harness does not have to cross the board.
#
# Empty this tuple for a board with no breakouts and the whole file
# becomes the four-key firmware: `SEESAW_BASE` falls to 0 so the NeoKey
# is 0-3 again, `NUM_KEYS` falls to 4, and the setup below is skipped
# whole. That one line is the entire difference between the two builds.
#
# There is deliberately no detection and no strap. An absent breakout is
# electrically identical to a present one nobody is pressing -- pulled
# high either way, with no readback on the pixel line and no capacitive
# sense on an RP2040 -- so any automatic answer would be a guess. A
# wrong guess renumbers every key silently, which is the one failure
# this file is built to prevent, and the flash is one file copy. The
# person doing the copy is the only honest source of truth.
GPIO_KEY_PIN_NAMES = ("MISO", "SCK")
GPIO_PIXEL_PIN_NAME = "MOSI"
GPIO_KEYS = len(GPIO_KEY_PIN_NAMES)

# Index order is physical, left to right, and the case decided it rather
# than this file: the breakouts sit to the *left* of the NeoKey, because
# on the right a mated Qwiic plug lands 0.025 mm from the first
# breakout's switch body and the NeoKey's socket ends up 114 mm from a
# QT Py holding a 50 mm cable. See case/params.py, BREAKOUT_ORIGINS_LOCAL.
#
# So the GPIO pair is 0-1 and the NeoKey is 2-5 -- or, with the tuple
# above emptied, there is no pair and the NeoKey is 0-3. These two
# constants are the only place that knows which way round it goes.
GPIO_BASE = 0
SEESAW_BASE = GPIO_KEYS

# Fixed, and deliberately not derived from what enumerated. Key 2 is key
# 2 whether or not the NeoKey answered: the host maps index to pane, so
# letting the boards renumber when the Qwiic cable is out would quietly
# focus the wrong session.
#
# The cost is that `HELLO <ver> 0` -- which used to mean "device present,
# keypad absent" -- can no longer happen. A missing NeoKey now shows up
# as `HELLO <ver> 6` plus `ERR i2c ...`, and the host paints keys 2-5
# into a board that is not there. Writes to absent hardware are dropped
# in silence, the same way an out-of-range index already is.
NUM_KEYS = SEESAW_KEYS + GPIO_KEYS

# Full brightness is genuinely painful to sit next to, but going too dim
# costs 8-bit steps: at 30% a deep pulse has only a handful of distinct
# values near its floor and visibly stalls there. 60% measured as the
# point where the fade stays smooth without being glaring. The host can
# override this at runtime with `B`.
DEFAULT_BRIGHTNESS = 0.6

# All timing is integer nanoseconds. `time.monotonic()` returns a float
# whose precision decays with uptime -- on a single-precision build the
# step near `now` grows past both thresholds below in a day or two --
# 15 ms is the ulp somewhere past 2^17 seconds -- and this is a device
# that lives plugged into a desk. The failure
# is silent and awful: the debounce window stops measuring anything, so
# one press reports as several and the wrong pane gets focused.
DEBOUNCE_NS = 15_000_000       # 15 ms
PULSE_STEP_NS = 20_000_000     # 20 ms, i.e. 50 Hz

# Adds roughly 5 ms plus the scan and paint themselves on top of the
# 15 ms debounce, so a press reaches the host in ~20 ms. The debounce
# dominates; this only decides how much is added to it.
POLL_INTERVAL_S = 0.005

# The pulse lives here rather than on the host. A square blink is one
# command per half period and could sit on the host happily; a sine fade
# is ~50 updates a second, which is a silly thing to push down a wire and
# would stutter on any host hiccup. Keeping it local also means the pulse
# is already where it has to be when this moves to BLE.
#
# A pulse is timed from the moment its command arrives, so a key entering
# a state fades up from its floor and the transition itself is visible.
# An earlier revision also added a fixed per-key phase offset, to stagger
# keys told to pulse in the same instant. The two are not compatible: an
# offset that is non-zero at t=0 is exactly a key that does not start at
# its floor, and with four keys it put key 2 at full brightness on its
# very first frame. Starting at the floor won, because the key it broke
# is whichever one is holding the approval state -- nothing here maps a
# key index to a pane state, so it could be any of them. Keys whose states change at different
# moments still drift apart on their own.
#
# 2 s measured as the point where the breath reads as deliberate rather
# than nervous; every state uses it and only the floor changes.
DEFAULT_PULSE_PERIOD_NS = 2_000_000_000
# Perceptually a raw sine lingers at the top, and gamma 2.0 corrects
# that -- but only where there are 8-bit steps to spend. At a low global
# brightness the bottom of a deep pulse has a handful of distinct values
# in total, and squaring makes the level crawl through exactly that
# region, so the fade visibly stalls at the floor. Staying near 1.0
# trades the perceptual curve for movement that never runs out of steps.
# 1.0 makes the exponentiation an identity; it is kept as a retunable
# knob, not left behind by accident.
PULSE_GAMMA = 1.0

# How long a color or floor change takes to complete. An instant switch
# reads as "something just happened", but most transitions are a session
# moving from one continuous state to the next -- so an abrupt change
# makes the pad overstate the event. 500 ms is slow enough to read as a
# transition rather than a glitch, fast enough not to lag the session.
DEFAULT_CROSSFADE_NS = 500_000_000
# One fat-fingered X must not look like a hung device.
MAX_CROSSFADE_MS = 10_000

# A host that never sends a newline would otherwise grow the receive
# buffer until the heap gives out -- the only unbounded allocation in a
# loop that is otherwise allocation-free. Longest legal line is ~24 bytes.
MAX_LINE_BYTES = 256

# How many consecutive failed I2C scans before the keypad is declared
# gone on the console. One or two is bus noise; a run of them is a cable.
I2C_FAIL_LIMIT = 20


# `board.STEMMA_I2C()` is what raises when the Qwiic cable is missing:
# the I2C pull-ups live on the NeoKey board, so without it the bus check
# fails before any NeoKey1x4 is constructed. That must not kill the whole
# device. With the serial half still up, a host that receives
# `HELLO <ver> 0` learns "the pad is plugged in but has no keypad
# attached", which is a diagnosable state. Dying here instead leaves a
# port that never answers, indistinguishable from a board that failed to
# boot at all.
#
# Each board is then initialised separately so a second board with an
# unbridged A0 jumper -- the likeliest wiring mistake once there are two
# -- degrades to "one board works" instead of "no keypad at all".
# `pads` is (base index, board) so the base survives a board that did
# not answer. `pixel_groups` is (pixel object, base index, count) for
# every run of keys that shares one strip of pixels -- one per NeoKey
# board, plus one for the whole breakout chain. Both a NeoKey's
# `pad.pixels` and a `neopixel.NeoPixel` are adafruit_pixelbuf.PixelBuf
# subclasses, so they take the same `[i] = rgb`, `.show()`, `.fill()`
# and `.brightness`, and one routing table covers both kinds.
pads = []
pixel_groups = []
pad_errors = []
try:
    from adafruit_neokey.neokey1x4 import NeoKey1x4
    i2c = board.STEMMA_I2C()
except Exception as err:  # noqa: BLE001 - a missing lib and a missing
    # cable arrive here identically, and both must leave the serial half
    # alive so the host is told rather than left staring at a dead port.
    i2c = None
    pad_errors.append("setup {}: {}".format(type(err).__name__, err))
if i2c is not None:
    for slot, addr in enumerate(PAD_ADDRESSES):
        # The base index comes from the slot, not from how many boards
        # answered. Appending in arrival order means that with two
        # addresses configured and the first one silent, the second
        # board's keys take the first board's indices -- the same silent
        # renumbering the GPIO half is kept static to avoid.
        base = SEESAW_BASE + slot * KEYS_PER_PAD
        try:
            pad = NeoKey1x4(i2c, addr=addr)
            # NeoKey1x4 leaves auto_write on, which turns every single
            # pixel assignment into a full buffer transmit plus a SHOW
            # over seesaw. During a pulse that is one transaction per key
            # per step -- four times the bus traffic needed, competing
            # with the key scan for the same bus. Batch instead: write
            # the pixels, then show once per pad per tick.
            pad.pixels.auto_write = False
            pad.pixels.brightness = DEFAULT_BRIGHTNESS
            pad.pixels.fill(0x000000)
            pad.pixels.show()
            pads.append((base, pad))
            pixel_groups.append((pad.pixels, base, KEYS_PER_PAD))
        except Exception as err:  # noqa: BLE001
            pad_errors.append("0x{:02x} {}: {}".format(
                addr, type(err).__name__, err))

# The GPIO half comes up in two guards, because it fails in two ways.
# The pins are core CircuitPython and cannot go missing; `neopixel` is a
# file on the drive exactly like adafruit_neokey. Losing the library
# must not cost these two keys their presses, so the switches are built
# first and separately -- the half that needs nothing stays working when
# the half that needs something does not.
#
# Skipped whole when GPIO_KEY_PIN_NAMES is empty, and the skip is not
# cosmetic: `NeoPixel(pin, 0)` is a zero-length strip, which is either
# an exception -- and then a four-key board reports `ERR gpio pixels` on
# every single connect, forever, about hardware it was never built with
# -- or an empty group nothing will ever write to. Neither is worth
# carrying, and the first would teach a host to ignore that error.
gpio_switches = []
gpio_errors = []
if GPIO_KEYS:
    try:
        import digitalio

        for name in GPIO_KEY_PIN_NAMES:
            switch = digitalio.DigitalInOut(getattr(board, name))
            switch.switch_to_input(pull=digitalio.Pull.UP)
            gpio_switches.append(switch)
    except Exception as err:  # noqa: BLE001
        gpio_errors.append("keys {}: {}".format(type(err).__name__, err))
    try:
        from neopixel import NeoPixel

        # GRB is the WS2812 family's wire order and what the NeoKey's
        # seesaw driver already assumes, so the breakouts carrying the
        # same NEO3535_REVERSE part should match. If keys 0 and 1 come up
        # with red and green swapped while 2-5 look right, this is the
        # line -- it is a property of the LED, and nothing in the .brd
        # files states it.
        gpio_pixels = NeoPixel(
            getattr(board, GPIO_PIXEL_PIN_NAME), GPIO_KEYS,
            auto_write=False, brightness=DEFAULT_BRIGHTNESS,
            pixel_order="GRB")
        gpio_pixels.fill(0x000000)
        gpio_pixels.show()
        pixel_groups.append((gpio_pixels, GPIO_BASE, GPIO_KEYS))
    except Exception as err:  # noqa: BLE001
        gpio_errors.append("pixels {}: {}".format(type(err).__name__, err))
# Two variables on purpose. `boot_i2c_error` is what setup found and
# never changes; `i2c_error` is what is true *now*, so the connect
# branch reports the current state instead of a snapshot taken before
# the cable was knocked loose. Without that split, a host reconnecting
# after a runtime bus loss is greeted with a clean HELLO and a key count
# the device can no longer honour -- worse than silence, because it is a
# positive claim of health.
#
# The key count in HELLO stays at its startup value even then. Resizing
# eight parallel per-key lists mid-loop is the one hazard this shape
# genuinely has, and it is not worth taking for a rare fault when the
# accompanying ERR already says the keypad is gone.
boot_i2c_error = "; ".join(pad_errors) or None
i2c_error = boot_i2c_error
# What the GPIO half found wrong with itself, reported next to the I2C
# faults so a missing `neopixel` is diagnosable instead of being two
# dark keys. There is no runtime twin of this one: a bus can be
# unplugged mid-session, a soldered pin cannot.
gpio_error = "; ".join(gpio_errors) or None

# Per key, one appearance model for both solid and pulsing: a colour and
# a floor, where floor 1.0 means the sine contributes nothing and the key
# is simply lit. That single representation is what lets one crossfade
# cover all four transitions -- solid->solid, solid->pulsing,
# pulsing->solid, pulsing->pulsing -- with no special cases.
#
# `from_*` is the appearance the running crossfade started from, `to_*`
# is where it is heading, and `fade_started` is when. Separate lists
# rather than tuples: nothing here is ever resized, and comparing whole
# scalars avoids the field-order coupling a packed tuple invites.
from_rgb = [0x000000] * NUM_KEYS
from_floor = [1.0] * NUM_KEYS
to_rgb = [0x000000] * NUM_KEYS
to_floor = [1.0] * NUM_KEYS
fade_started = [0] * NUM_KEYS
period_ns = [DEFAULT_PULSE_PERIOD_NS] * NUM_KEYS
pulse_started = [0] * NUM_KEYS
# Last value actually pushed to each pixel. None means "nothing written
# yet", which is distinct from black, so the startup fill does not poison
# the cache. Holds the *logical* color: adafruit_pixelbuf re-renders from
# its unscaled buffer when brightness changes, so `B` still lands on
# solid keys without invalidating this.
last_rgb = [None] * NUM_KEYS
# Which pixel groups have writes waiting for a show().
group_dirty = [False] * len(pixel_groups)

serial = usb_cdc.data
using_fallback_port = serial is None
if using_fallback_port:
    serial = usb_cdc.console

# `connected` only means the host asserted DTR -- it says nothing about
# whether the host is *reading*. A host that opens the port and then
# stops draining (suspended, at a debugger breakpoint, App Nap) fills the
# CDC endpoint, and the default write_timeout of None then blocks
# forever, freezing the one loop that scans keys and paints LEDs. A
# bounded timeout stops the stall. Note what it does *not* do:
# CircuitPython's write returns a short count rather than raising on
# timeout, so the result is a truncated line, not a dropped one. The
# fragment glues onto the next message, so the host loses two lines and
# resyncs at the newline after them.
serial.write_timeout = 0.05


def write_line(text):
    """Write one protocol line. True only if it actually left.

    Covers two cases the loop must survive: no host has the port open,
    and a host has it open but is not draining it. Callers that commit
    state on the strength of a message -- the key scan does -- must check
    the result, or the device ends up believing it said something it
    never said.
    """
    if not serial.connected:
        return False
    try:
        # A newline anywhere in the payload would split one message into
        # two and hand the host a fragment it cannot parse. This is the
        # single choke point, so sanitising here covers every caller.
        serial.write(text.replace("\n", " ").replace("\r", " ").encode() + b"\n")
        return True
    except Exception:  # noqa: BLE001 - a dropped line must not stop the loop
        return False


def write_pixel(idx, rgb):
    """Stage a color for one key, skipping unchanged writes.

    Cheap insurance rather than a hot-path win: a bright pulse really
    does change value on nearly every step. What this elides is the
    repeated identical commands a host is explicitly invited to send, and
    every step of a dark or shallow pulse, where the 8-bit output does
    repeat. Call `flush_pixels()` to push staged writes to the hardware.
    """
    if last_rgb[idx] == rgb:
        return
    for g in range(len(pixel_groups)):
        pixels, base, count = pixel_groups[g]
        if not base <= idx < base + count:
            continue
        # Hardware first, bookkeeping second. The other order looks
        # harmless until an I2C fault raises between them: the cache then
        # claims the key was painted, every later write of that value is
        # elided as redundant, and a settled solid key -- which the
        # render loop skips -- keeps the old colour until the host
        # happens to change it. Including through `all_off()`, which is
        # the frozen orange key the disconnect handler exists to prevent.
        pixels[idx - base] = rgb
        last_rgb[idx] = rgb
        group_dirty[g] = True
        return
    # No hardware behind this key -- a NeoKey that did not answer, or a
    # `neopixel` that would not import. Drop it the way an out-of-range
    # index is dropped, and leave the cache alone so that nothing is
    # remembered about a pixel that was never written.


def flush_pixels():
    """Push staged writes to hardware. Returns the first error, or None.

    Guarded per group rather than inside the loop's single try. The
    groups fail independently: a bus that cannot paint the NeoKey must
    not stop the breakout chain painting, which is the whole reason keys
    0 and 1 hang off GPIO. That holds for every I2C fault with the cable
    still in it. It does not hold for the cable itself -- the built unit
    draws the breakouts' VDD off the NeoKey's header, so an unplugged
    cable takes their pixels with it whatever this function does.
    """
    first_err = None
    for g in range(len(pixel_groups)):
        if not group_dirty[g]:
            continue
        try:
            pixel_groups[g][0].show()
            group_dirty[g] = False
        except Exception as err:  # noqa: BLE001 - the caller reports it
            if first_err is None:
                first_err = err
    return first_err


def invalidate_pixels():
    """Forget what the hardware is showing, so the next tick repaints.

    Called after an I2C failure: the write cache cannot be trusted about
    anything that may have been half-applied, and a settled solid key
    would otherwise never be written again.
    """
    for i in range(NUM_KEYS):
        last_rgb[i] = None
    for i in range(len(group_dirty)):
        group_dirty[i] = True


def lerp_rgb(a, b, t):
    return ((int(((a >> 16) & 0xFF) + (((b >> 16) & 0xFF) - ((a >> 16) & 0xFF)) * t) << 16)
            | (int(((a >> 8) & 0xFF) + (((b >> 8) & 0xFF) - ((a >> 8) & 0xFF)) * t) << 8)
            | int((a & 0xFF) + ((b & 0xFF) - (a & 0xFF)) * t))


def fade_progress(idx, now):
    if crossfade_ns <= 0:
        return 1.0
    elapsed = now - fade_started[idx]
    # The lower clamp is load-bearing, not defensive. `now` is sampled
    # once at the top of the loop while `retarget` stamps a fresh
    # timestamp, so a key retargeted in the same iteration has
    # `fade_started > now` and elapsed goes negative. A negative t makes
    # lerp_rgb extrapolate past `from`, a channel underflows to -1, the
    # whole packed value goes negative, and `>> 16 & 0xFF` decodes it as
    # 255 -- a full-brightness wrong-colour frame on exactly the
    # transition this fade exists to smooth. It also pushes the floor
    # above 1.0, spilling the level past 24 bits.
    if elapsed <= 0:
        return 0.0
    return 1.0 if elapsed >= crossfade_ns else elapsed / crossfade_ns


def retarget(idx, rgb, floor, period, restart_phase):
    """Begin a crossfade towards a new appearance for one key.

    Re-issuing the appearance a key is already heading for is a no-op, so
    a host can re-push its whole state whenever convenient -- after every
    HELLO, on a timer -- without restarting either the crossfade or the
    breath. That guarantee is why the host never has to track which keys
    are already doing what.
    """
    if to_rgb[idx] == rgb and to_floor[idx] == floor and period_ns[idx] == period:
        return
    now = time.monotonic_ns()
    # Start the new fade from what is on screen *now*, not from the last
    # target -- otherwise a change arriving mid-fade jumps backwards to
    # where the previous one began.
    t = fade_progress(idx, now)
    from_rgb[idx] = lerp_rgb(from_rgb[idx], to_rgb[idx], t)
    from_floor[idx] = from_floor[idx] + (to_floor[idx] - from_floor[idx]) * t
    to_rgb[idx] = rgb
    to_floor[idx] = floor
    fade_started[idx] = now
    if restart_phase or period_ns[idx] != period:
        pulse_started[idx] = now
    period_ns[idx] = period


def set_color(idx, rgb):
    if 0 <= idx < NUM_KEYS:
        # Solid is floor 1.0: the sine term drops out and the key just
        # sits at its colour.
        retarget(idx, rgb, 1.0, period_ns[idx], False)


def set_pulse(idx, rgb, period, floor):
    if not 0 <= idx < NUM_KEYS:
        return
    # Clamp before the comparison in retarget, so two commands that clamp
    # to the same effective pulse are recognised as identical.
    period = max(100_000_000, period)
    floor = min(max(floor, 0.0), 1.0)
    # Phase restarts only when a *solid* key begins pulsing. A key already
    # breathing keeps its phase through a colour or floor change: what
    # altered is the urgency, not the heartbeat, and dropping the breath
    # back to its trough would read louder than the change itself.
    # Read the floor currently *displayed*, not the target. A key going
    # pulsing -> solid has to_floor == 1.0 from the first instant while
    # it keeps visibly breathing for the whole crossfade; testing the
    # target would restart the phase mid-breath, which is exactly what
    # this rule promises cannot happen.
    now = time.monotonic_ns()
    shown_floor = (from_floor[idx]
                   + (to_floor[idx] - from_floor[idx]) * fade_progress(idx, now))
    retarget(idx, rgb, floor, period, shown_floor >= 1.0)


def all_off():
    # No crossfade here. `R` and a host disconnect both mean "nobody owns
    # these any more", and that should be true the moment it is said.
    for i in range(NUM_KEYS):
        # Every per-key field, named in one place. Splitting them across
        # parallel lists bought an allocation-free hot path; the price is
        # that nothing structural stops a reset from forgetting one.
        from_rgb[i] = to_rgb[i] = 0x000000
        from_floor[i] = to_floor[i] = 1.0
        fade_started[i] = 0
        pulse_started[i] = 0
        period_ns[i] = DEFAULT_PULSE_PERIOD_NS
        write_pixel(i, 0x000000)


def set_brightness(percent):
    level = max(0, min(100, percent)) / 100
    for g in range(len(pixel_groups)):
        pixel_groups[g][0].brightness = level
        group_dirty[g] = True


def handle(line):
    global crossfade_ns
    parts = line.decode().strip().split()
    if not parts:
        return
    cmd = parts[0]
    if cmd == "C" and len(parts) == 3:
        # Masking here rather than at each use keeps C and S agreeing on
        # what an out-of-range color means. Without it `C 0 1ffffff`
        # raises inside pixelbuf while `S 0 1ffffff` is quietly truncated
        # by the shift arithmetic, and a negative value pulses white.
        set_color(int(parts[1]), int(parts[2], 16) & 0xFFFFFF)
    elif cmd == "S" and len(parts) in (3, 4, 5):
        period = (int(parts[3]) * 1_000_000 if len(parts) > 3
                  else DEFAULT_PULSE_PERIOD_NS)
        floor = int(parts[4]) / 100 if len(parts) > 4 else 0.0
        set_pulse(int(parts[1]), int(parts[2], 16) & 0xFFFFFF, period, floor)
    elif cmd == "B" and len(parts) == 2:
        set_brightness(int(parts[1]))
    elif cmd == "X" and len(parts) == 2:
        # Clamped at both ends like S's period and floor: with no
        # ceiling, one fat-fingered value freezes every transition for
        # hours and reads as a device that stopped responding.
        now = time.monotonic_ns()
        for i in range(NUM_KEYS):
            # fade_progress divides by the live global, so changing it
            # would otherwise rescale fades already in flight -- a fade
            # 80% done snaps backwards on a longer X, or jumps to its end
            # on a shorter one. Re-anchor from what is on screen instead.
            t = fade_progress(i, now)
            from_rgb[i] = lerp_rgb(from_rgb[i], to_rgb[i], t)
            from_floor[i] = from_floor[i] + (to_floor[i] - from_floor[i]) * t
            fade_started[i] = now
        crossfade_ns = min(max(0, int(parts[1])), MAX_CROSSFADE_MS) * 1_000_000
    elif cmd == "P":
        write_line("PONG {} {}".format(PROTOCOL_VERSION, NUM_KEYS))
    elif cmd == "R":
        all_off()
    else:
        write_line("ERR unknown {}".format(cmd))


# --- key state ---------------------------------------------------------
# `stable` is what the host has been told. `raw_prev` plus `changed_at`
# implement the debounce: an edge only becomes stable once the raw level
# has held its new value for DEBOUNCE_NS. `changed_at[i]` is meaningful
# only while `raw_prev[i] != stable[i]`; when they agree it is dead data.
stable = [False] * NUM_KEYS
raw_prev = [False] * NUM_KEYS
changed_at = [0] * NUM_KEYS
# Refilled every tick rather than rebuilt, like every other per-key list
# here. The scan runs 200 times a second and the loop is otherwise
# allocation-free; every entry is written before it is read, either from
# the hardware or, when a board has stopped answering, from `stable`.
raw = [False] * NUM_KEYS

crossfade_ns = DEFAULT_CROSSFADE_NS
rx_buffer = b""
was_connected = False
last_pulse_at = 0
i2c_fail_count = 0
i2c_lost_reported = False
# Set when a host connects, so the first scan afterwards adopts whatever
# the keys are doing right now instead of reporting edges against a
# previous session's state. Without it, a key held across a reconnect
# sends the new host a release for a press it never saw.
resync_keys = False

if using_fallback_port:
    print("WARNING: usb_cdc.data is None - boot.py did not take effect.")
    print("Copy boot.py to CIRCUITPY, then reset (see README bring-up).")
if i2c_error:
    print("WARNING: no keypad on I2C ({}).".format(i2c_error))
    print("Check the Qwiic cable between the QT Py and the NeoKey.")
    print("Reconnecting it needs a reset; it is not picked up live.")
if gpio_error:
    print("WARNING: breakout keys degraded ({}).".format(gpio_error))
    print("Keys {}-{} are the two 4978 boards on GPIO {} / pixels on {}."
          .format(GPIO_BASE, GPIO_BASE + GPIO_KEYS - 1,
                  "/".join(GPIO_KEY_PIN_NAMES), GPIO_PIXEL_PIN_NAME))


# An uncaught exception is the worst thing that can happen here, and it
# is silent: CircuitPython stops code.py, the data port goes quiet and
# the LEDs freeze at whatever they last showed. From the host that is
# indistinguishable from a board that never booted, and the only way out
# is for a human to notice and unplug it.
#
# So: say so, then reboot into the recovery path that already exists --
# a fresh HELLO, which the host already treats as "re-push everything".
#
# The one thing this must never do is make the board unreachable. A fault
# that fires immediately on every boot would otherwise reset-loop, and a
# board whose USB re-enumerates every few seconds is hard to write a new
# code.py to. Below MIN_UPTIME_BEFORE_RESET_NS the device stays halted
# and red instead, which is both the louder failure signal and the state
# you can actually recover from.
MIN_UPTIME_BEFORE_RESET_NS = 60_000_000_000  # 60 s
booted_at = time.monotonic_ns()

try:
    while True:
        now = time.monotonic_ns()

        # --- host connect / disconnect -------------------------------------
        connected = serial.connected
        if connected and not was_connected:
            # Announce on every fresh open, not just at power-on: a banner
            # sent at boot is lost if the host was not listening yet. This is
            # also the host's cue to re-push every color after a device reset.
            rx_buffer = b""
            resync_keys = True
            write_line("HELLO {} {}".format(PROTOCOL_VERSION, NUM_KEYS))
            if using_fallback_port:
                write_line("ERR no-data-cdc-check-boot-py")
            if i2c_error:
                # The advice differs by cause and must not be guessed at:
                # a keypad missing since boot needs a reset once it is
                # reconnected, while a bus lost at runtime comes back on
                # its own the moment it answers again.
                write_line("ERR i2c {}{}".format(
                    i2c_error,
                    " (reset required after fixing)"
                    if i2c_error is boot_i2c_error else ""))
            if gpio_error:
                # Always a setup fault, because there is no runtime twin
                # of it -- so unlike the bus above, "reset after fixing"
                # is unconditionally true here and can just be said.
                write_line(
                    "ERR gpio {} (reset required after fixing)".format(
                        gpio_error))
        elif was_connected and not connected:
            # Nobody owns the LEDs any more. Stale status is worse than none:
            # a frozen orange key claims a session still wants an answer.
            # Brightness goes back to the default for the same reason -- the
            # next host should not inherit a `B 5` the last one left behind.
            # A partial line from the departing host goes too, or it would be
            # concatenated onto the next host's first command.
            try:
                all_off()
                set_brightness(int(DEFAULT_BRIGHTNESS * 100))
            except Exception:  # noqa: BLE001 - the I2C guard below reports it
                pass
            # Host-set state, same as brightness: the next host should
            # not inherit an `X 0` the last one left behind.
            crossfade_ns = DEFAULT_CROSSFADE_NS
            rx_buffer = b""
        was_connected = connected

        # --- commands from the host (non-blocking) -------------------------
        if serial.in_waiting:
            rx_buffer += serial.read(serial.in_waiting) or b""
            while b"\n" in rx_buffer:
                line, rx_buffer = rx_buffer.split(b"\n", 1)
                try:
                    handle(line)
                except Exception as err:  # noqa: BLE001 - never die on bad input
                    # The type name matters: several CircuitPython builtins
                    # are raised with no argument, so str(err) alone can be
                    # empty and the host would receive a bare "ERR ".
                    write_line("ERR {} {}".format(type(err).__name__, err))

        # --- LEDs and keys -------------------------------------------------
        # Every I2C touch is guarded. The startup path already treats a
        # missing keypad as a survivable state; a cable knocked loose
        # *after* boot is the likelier version of the same event, and
        # unguarded it raises straight out of the loop, drops to the REPL,
        # and leaves a silent port with frozen LEDs -- which is exactly what
        # a board that never booted looks like.
        #
        # Several guards now rather than one, because half the keypad no
        # longer touches the bus. An I2C fault has to cost exactly the
        # keys behind it and no others -- otherwise putting keys 0 and 1
        # on GPIO bought nothing. The cable is the one exception and it
        # is a wiring fact rather than a firmware one: the built unit
        # draws the breakouts' VDD and GND off the NeoKey's header, so
        # unplugging it costs all six however carefully this loop is
        # split. Every arm records into `tick_err` and the accounting
        # below stays in one place.
        tick_err = None
        try:
            if now - last_pulse_at >= PULSE_STEP_NS:
                last_pulse_at = now
                for i in range(NUM_KEYS):
                    t = fade_progress(i, now)
                    if t >= 1.0:
                        if to_floor[i] >= 1.0 and from_floor[i] >= 1.0 \
                                and from_rgb[i] == to_rgb[i]:
                            continue  # settled and solid: nothing moves
                        from_rgb[i] = to_rgb[i]
                        from_floor[i] = to_floor[i]
                    base = lerp_rgb(from_rgb[i], to_rgb[i], t)
                    floor = from_floor[i] + (to_floor[i] - from_floor[i]) * t
                    # Integer modulo before the divide, so phase stays exact
                    # no matter how long the board has been up. Cosine starts
                    # at its minimum, so a key that begins pulsing fades up
                    # rather than snapping to full.
                    phase = ((now - pulse_started[i]) % period_ns[i]) / period_ns[i]
                    level = (1 - math.cos(2 * math.pi * phase)) / 2
                    level = floor + (1 - floor) * level ** PULSE_GAMMA
                    write_pixel(i, (int(((base >> 16) & 0xFF) * level) << 16)
                                | (int(((base >> 8) & 0xFF) * level) << 8)
                                | int((base & 0xFF) * level))
        except Exception as err:  # noqa: BLE001
            # Not necessarily I2C -- this arm also covers the pulse
            # arithmetic, which is why the type name is carried into the
            # report rather than sending someone to check a healthy cable.
            tick_err = err
            invalidate_pixels()
        if tick_err is None:
            # Guarded per group inside, so a bus that cannot show() the
            # NeoKey still lets the breakout chain paint.
            tick_err = flush_pixels()
            if tick_err is not None:
                # A failure may have landed between a pixel write and its
                # show, so nothing the cache claims is trustworthy.
                invalidate_pixels()

        # The GPIO keys first, and outside every guard. Reading a pin
        # cannot fail the way the bus can, and these are the two keys put
        # on GPIO precisely so that a missing cable could not reach them.
        for i in range(len(gpio_switches)):
            # Pull-up plus a diode to ground: pressed reads low.
            raw[GPIO_BASE + i] = not gpio_switches[i].value

        # get_keys() reads all four keys of a board in one I2C
        # transaction, which is 4x fewer round trips than indexing each.
        for pad_base, pad in pads:
            try:
                levels = pad.get_keys()
            except Exception as err:  # noqa: BLE001
                if tick_err is None:
                    tick_err = err
                # Freeze this board's keys at what the host has already
                # been told. Filling them with False instead would
                # manufacture a release for a finger that never lifted,
                # and a release is a thing the host acts on.
                for k in range(KEYS_PER_PAD):
                    raw[pad_base + k] = stable[pad_base + k]
                    raw_prev[pad_base + k] = stable[pad_base + k]
            else:
                for k in range(KEYS_PER_PAD):
                    raw[pad_base + k] = levels[k]

        if tick_err is not None:
            i2c_fail_count += 1
            if i2c_fail_count >= I2C_FAIL_LIMIT and not i2c_lost_reported:
                i2c_lost_reported = True
                i2c_error = "lost at runtime: {}: {}".format(
                    type(tick_err).__name__, tick_err)
                print("key/LED tick failed {} times: {}".format(
                    i2c_fail_count, i2c_error))
        else:
            if i2c_lost_reported:
                # Back on the bus. Fall back to whatever setup found, so
                # a recovered wobble stops being reported as a fault.
                i2c_error = boot_i2c_error
                print("key/LED tick recovered")
            i2c_fail_count = 0
            i2c_lost_reported = False

        if resync_keys:
            # Adopt the current levels without emitting anything, so keys
            # held across a reconnect produce neither a phantom press nor an
            # orphan release.
            resync_keys = False
            for i in range(NUM_KEYS):
                stable[i] = raw_prev[i] = raw[i]
                changed_at[i] = now
        else:
            for i in range(NUM_KEYS):
                level = raw[i]
                if level != raw_prev[i]:
                    raw_prev[i] = level
                    changed_at[i] = now
                elif level != stable[i] and (now - changed_at[i]) >= DEBOUNCE_NS:
                    # `stable` means "what the host has been told", so it
                    # may only advance once the telling succeeded.
                    # Committing regardless leaves the host holding a
                    # release for a press it never saw -- the orphan edge
                    # `resync_keys` prevents across reconnects, reachable
                    # here without one.
                    if write_line("K {} {}".format(i, 1 if level else 0)):
                        stable[i] = level

        time.sleep(POLL_INTERVAL_S)

except Exception as err:  # noqa: BLE001 - last line before a silent brick
    # Free memory before doing anything else. MemoryError is an Exception
    # and lands here like any other, and every line below allocates --
    # formatting a message, encoding it, packing a colour. Without this
    # the handler re-raises and drops to the REPL: the exact silent brick
    # it exists to prevent, in the one case it is most likely to face.
    gc.collect()
    detail = "unknown"
    try:
        detail = "{}: {}".format(type(err).__name__, err)
        print("FATAL:", detail)
        write_line("ERR fatal {}".format(detail))
    except Exception:  # noqa: BLE001
        pass
    try:
        # Whatever the last host left is not a signal any more, and `B 5`
        # would make the alert invisible.
        set_brightness(int(DEFAULT_BRIGHTNESS * 100))
    except Exception:  # noqa: BLE001
        pass
    try:
        # Best effort: if the fault *was* the I2C bus, this cannot work,
        # and that is precisely when the reset matters most.
        for i in range(NUM_KEYS):
            last_rgb[i] = None
            write_pixel(i, 0xFF0000)
        flush_pixels()
    except Exception:  # noqa: BLE001
        pass
    if time.monotonic_ns() - booted_at < MIN_UPTIME_BEFORE_RESET_NS:
        # The CIRCUITPY part is not filler. Getting here means boot.py
        # ran to completion, so the drive gate ran too and the volume is
        # gone -- this branch is reached with a healthy keypad and dead
        # firmware, which is the one shape the gate's fail-open does not
        # cover. Naming the key is the difference between a recovery and
        # a hunt for a disk that is not there.
        print("Failed within {} s of boot - halting red rather than "
              "reset-looping. Hold a key and replug to mount CIRCUITPY, "
              "fix code.py, then reset."
              .format(MIN_UPTIME_BEFORE_RESET_NS // 1_000_000_000))
        # `ERR fatal` above only reached a host that was already
        # attached. Without this the board sits on an enumerated, wholly
        # silent port -- the signature this whole guard exists to
        # eliminate -- for every host that arrives afterwards.
        halted_connected = False
        while True:
            now_connected = serial.connected
            if now_connected and not halted_connected:
                write_line("HELLO {} {}".format(PROTOCOL_VERSION, NUM_KEYS))
                write_line("ERR fatal-halted {}".format(detail))
            halted_connected = now_connected
            time.sleep(0.2)
    time.sleep(2)
    microcontroller.reset()
