"""Canopy MacroPad — main firmware.

The device is deliberately dumb: it reports key edges and paints the
colors it is told to paint. All meaning (which pane, which status, when
to pulse) lives in the host. That split is what lets the same wire
protocol survive the move to BLE later.

Wire protocol, line-delimited ASCII on usb_cdc.data.

  host -> device
    C <idx> <rrggbb>   set key idx to that color, e.g. `C 0 ff8000`
    S <idx> <rrggbb> [ms] [floor]
                       pulse that color, eased by `PULSE_CURVE`. `ms` is the full
                       period (min 100), `floor` is the percentage the
                       dip bottoms out at, 0-100: 0 reads as an alert,
                       50 as a slow breath that says "alive" without
                       asking for attention. Defaults: 2500 ms and 0.
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

import array
import math
import os
import sys
import time

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
# 2: adds S (device-side eased pulse)
# 3: adds X, crossfades every C/S, and holds phase across a colour change
PROTOCOL_VERSION = 3

# Two boards run this file and they are not the same shape. The QT Py
# build is two Adafruit 4978 breakouts on GPIO plus a NeoKey on I2C; the
# custom PCB is six switches straight to GPIO and one six-pixel chain.
#
# They cannot share one pin table even though they share pin *numbers*.
# The PCB was laid out against the QT Py's broken-out GPIO on purpose, so
# the same eleven numbers are available on both -- but GPIO3 is the
# breakouts' pixel line on one board and KEY0 on the other. Every
# difference between the two devices lives in this table.
#
# Pins are GPIO **numbers**, resolved through `microcontroller.pin`, not
# names through `board`. `board` carries a per-build name table, and the
# QT Py's names are simply absent from the generic build the PCB runs --
# measured on the real board, not assumed: `[n for n in ('MOSI', 'MISO',
# 'SCK', 'TX', 'RX', 'SDA', 'SCL') if hasattr(board, n)]` returns `[]`
# there. `microcontroller.pin.GPIOn` is the chip's own numbering and is
# on every RP2040 build.
PROFILES = {
    # Adafruit QT Py RP2040. Keys 0-1 are the two breakouts, keys 2-5 the
    # NeoKey. All three GPIO sit on the QT Py's 3V/GND edge, so the
    # harness does not have to cross the board.
    "qtpy": {
        "gpio_keys": (4, 6),                # MISO, SCK
        "gpio_pixel": 3,                    # MOSI
        "pad_addresses": (0x30,),
        # 50 Hz, and no dithering at that rate -- see `PAINT_HZ`. Four of
        # this board's six pixels live behind seesaw, so a paint is I2C
        # traffic competing with the key scan for the same bus, and the
        # NeoKey's own comment upstream is about exactly that cost.
        "paint_hz": 50,
        # No dithering at 50 Hz: the table beside `DITHER` measures it as
        # worse than none.
        "dither": False,
    },
    # The custom PCB. Six switches on GPIO in the board's physical key
    # order, one chain of six pixels, and no I2C anywhere on the board --
    # so the whole I2C half below is skipped rather than failing.
    "pcb": {
        "gpio_keys": (3, 4, 6, 20, 5, 24),
        "gpio_pixel": 25,
        "pad_addresses": (),
        # 200 Hz, which is what buys the dithering below. Every pixel is
        # on one bit-banged GPIO chain: six of them is ~260 us per show,
        # so 200 Hz costs about 5% of wall time and no bus at all.
        "paint_hz": 200,
        # The loop achieves about 148 Hz of that with six keys pulsing, and
        # the flag is True on the strength of the lit board rather than of
        # the request: at that rate a 50/50 dither alternates near 74 Hz,
        # and every depth from 67% down was invisible on a static ladder.
        "dither": True,
    },
}

# Which profile, decided by which CircuitPython **binary** is running.
#
# That is not the detection this file forbids, and the difference is the
# whole reason this one is allowed to be automatic. Whether a breakout is
# *wired* is electrically unknowable -- an absent one and a present one
# nobody is pressing are both pulled high, with no readback on the pixel
# line and no capacitive sense on an RP2040 -- so that question was
# always a human's to answer. Which build you booted is a compile-time
# string, and there is no guess in reading it.
#
# `settings.toml`'s `MPAD_BOARD` overrides the table, and is the answer
# of record for a board whose build name is not in it. The PCB currently
# runs a stock `raspberry_pi_pico` build: a name it does not own, that an
# actual Pico would also answer to, and that stops matching the day the
# board gets a definition of its own.
#
# An unrecognised answer gets **no** fallback profile. A wrong guess
# renumbers every key silently, which is the one failure this file is
# built to prevent, so it comes up with no hardware at all and says so.
# Both strings were read off their own board's REPL, not taken from a
# board definition: `print(sys.implementation._build)` answers
# 'raspberry_pi_pico' on the built PCB and 'adafruit_qtpy_rp2040' on the
# QT Py. Worth re-reading after a CircuitPython upgrade, and the failure
# if one ever stops matching is the safe one -- that board comes up with
# `HELLO <ver> 0` and `ERR board ...` rather than with wrong pins, and
# `MPAD_BOARD` in settings.toml fixes it without a reflash.
BUILD_TO_PROFILE = {
    "adafruit_qtpy_rp2040": "qtpy",
    "raspberry_pi_pico": "pcb",
}
# Read through `getattr` because `_build` is a private attribute, and this
# line is at module scope where an AttributeError is the silent brick --
# CircuitPython stops `code.py`, the port goes quiet, and from the host
# that is indistinguishable from a board that never booted. A release that
# renames or drops it must land in the failure this file already has a
# path for: no profile, `ERR board`, and a device that still talks.
# `os.getenv` is not wrapped, deliberately -- it is public API, and
# guarding everything that could theoretically move is how a guard stops
# meaning anything.
_build = getattr(sys.implementation, "_build", None)
_forced = os.getenv("MPAD_BOARD")
BOARD_PROFILE = _forced or BUILD_TO_PROFILE.get(_build)
if BOARD_PROFILE in PROFILES:
    board_error = None
    _profile = PROFILES[BOARD_PROFILE]
else:
    board_error = "{} {!r} is not one of {}".format(
        "MPAD_BOARD" if _forced else "build",
        _forced or _build,
        "/".join(sorted(PROFILES)))
    _profile = {"gpio_keys": (), "gpio_pixel": None, "pad_addresses": (),
                "paint_hz": 50, "dither": False}

# The I2C addresses of the NeoKey boards, in physical left-to-right key
# order. This tuple is the single source of truth for how many boards
# exist -- deriving it the other way round (a count that slices a longer
# address list) silently clamps instead of failing. A second board needs
# its A0 jumper bridged on the back to answer 0x31. Empty on a board with
# no I2C keypad, and then nothing here is imported, addressed or reported
# on.
PAD_ADDRESSES = _profile["pad_addresses"]
KEYS_PER_PAD = 4
SEESAW_KEYS = KEYS_PER_PAD * len(PAD_ADDRESSES)

# The keys read straight off GPIO, in physical left-to-right order. They
# carry no seesaw, so there is nothing to address and nothing to
# enumerate -- which is why this is the half that cannot fail to come up.
# On the QT Py that is keys 0-1 and they come *before* the NeoKey's four;
# on the PCB it is all six and there is no other half.
#
# The switch wiring differs between the boards and only one of them has a
# margin worth watching. Each 4978 breakout puts its switch in series
# with a 1N4148 running SWITCHA to SWITCHC, and SWITCHC goes to ground,
# so a press pulls its input low *through the diode*. The forward drop at
# the ~55 uA an internal pull-up supplies is about 0.45 V, under the
# RP2040's 0.8 V V_IL but not by a wide margin: a key that reads
# permanently pressed is the symptom of that number being wrong, and an
# external pull-up is the fix. The PCB's switches go straight to ground
# with no diode in the way, so they have no such margin to lose.
#
# Resolved against `microcontroller.pin` inside the setup guard rather
# than here. A number missing from it would be an AttributeError at
# module scope, which is the silent brick again -- and a wrong-board
# flash is exactly when you want the serial half still talking.
GPIO_KEY_GPIO = _profile["gpio_keys"]
GPIO_PIXEL_GPIO = _profile["gpio_pixel"]
GPIO_KEYS = len(GPIO_KEY_GPIO)

# Index order is physical, left to right, and on the QT Py the case
# decided it rather than this file: the breakouts sit to the *left* of
# the NeoKey, for reasons of plug clearance and cable reach that
# `case/params.py` owns and states with its own numbers
# (`BREAKOUT_ORIGINS_LOCAL`). Restating one of them here is how a number
# gets carried away from what makes it true, so it is not restated.
#
# So on the QT Py the GPIO pair is 0-1 and the NeoKey is 2-5; on the PCB
# the GPIO six are 0-5 and `SEESAW_BASE` lands past the end and is never
# used. These two constants are the only place that knows which way round
# it goes.
GPIO_BASE = 0
SEESAW_BASE = GPIO_KEYS

# Derived from the profile, not from what enumerated at runtime. Key 2 is
# key 2 whether or not the NeoKey answered: the host maps index to pane,
# so letting the boards renumber when the Qwiic cable is out would
# quietly focus the wrong session.
#
# Both real profiles come to 6, by different sums -- 2 + 4 on the QT Py,
# 6 + 0 on the PCB -- so a missing NeoKey shows up as `HELLO <ver> 6`
# plus `ERR i2c ...` and the host paints keys 2-5 into a board that is
# not there. Writes to absent hardware are dropped in silence, the same
# way an out-of-range index already is.
#
# `HELLO <ver> 0` is reachable again, and means one thing only: this
# firmware does not know what board it is on. It arrives with `ERR board
# ...`, and it is the honest report -- claiming six keys that resolve to
# no pins would be a positive claim of health, which is worse than
# silence.
NUM_KEYS = SEESAW_KEYS + GPIO_KEYS

# Full brightness is genuinely painful to sit next to, but going too dim
# costs 8-bit steps: at 30% a deep pulse has only a handful of distinct
# values near its floor and visibly stalls there. 60% measured as the
# point where the fade stays smooth without being glaring. The host can
# override this at runtime with `B`.
#
# Measured on a lit board, and the number stands -- but for a reason the
# original note did not have. `DITHER` buys steps back above
# `DITHER_FLOOR`, and separately the board says a one-level step stops
# being visible around value 2 anyway. So the low end is not as bad as
# this comment once implied, and 60 is no longer a floor forced by
# quantisation. It is still what idle's white balance was measured at,
# which is the reason not to move it casually.
DEFAULT_BRIGHTNESS = 0.6

# All timing is integer nanoseconds. `time.monotonic()` returns a float
# whose precision decays with uptime -- on a single-precision build the
# step near `now` grows past both thresholds below in a day or two --
# 15 ms is the ulp somewhere past 2^17 seconds -- and this is a device
# that lives plugged into a desk. The failure
# is silent and awful: the debounce window stops measuring anything, so
# one press reports as several and the wrong pane gets focused.
DEBOUNCE_NS = 15_000_000       # 15 ms

# How often the LEDs are repainted, and it is a per-board number because
# it buys different things on the two boards. It is the pulse's sample
# rate, and -- at 200 Hz and above -- the carrier the dithering below
# rides on.
#
# **It is a request, not the achieved rate.** `POLL_INTERVAL_S` is 5 ms so
# 200 Hz is the arithmetic ceiling, but the loop measured **148 Hz** with
# six keys pulsing -- a 26% shortfall. Which is why whether to dither is a
# separate field in the profile rather than a comparison against this
# number: a comparison would be deciding on a rate the board does not
# reach. What was actually judged, on the lit board at 148 Hz, is recorded
# beside each profile's flag.
PAINT_HZ = _profile["paint_hz"]
PULSE_STEP_NS = 1_000_000_000 // PAINT_HZ
# Temporal dithering is only switched on where the paint rate can carry
# it, and 200 Hz is not a round number -- it is where the measurement
# crosses over. Error-diffusing at 50 Hz is *worse than not dithering*,
# because the dither's own alternation then lands inside the band the eye
# sees as flicker rather than above it. Simulated against the real
# quantiser, error energy in the visible 5-30 Hz band, in LSB rms, for a
# gamma-2.0 breath at floor 0.15:
#
#     brightness   today@50   dither@50   @100    @200    @400
#     0.10            0.254      0.396   0.230   0.084   0.031
#     0.15            0.237      0.378   0.237   0.075   0.029
#     0.60            0.347      0.390   0.198   0.082   0.037
#
# So 50 Hz loses, 100 Hz draws, and 200 Hz wins by 3x. A board that
# cannot afford 200 Hz must not dither at all, which is why this is a
# threshold and not a preference.
# Read from the profile rather than derived as `PAINT_HZ >= 200`, which is
# what this line used to say and was a small lie: `PAINT_HZ` is the rate
# the loop *asks* for and the PCB achieves about 148 of it, so the
# comparison passed on a board that misses its own stated bar. The
# threshold above is still the reason each flag is set the way it is; what
# changed is that the flag records a decision instead of pretending to
# derive one, and the profile carries the measurement beside it.
DITHER = _profile["dither"]

# Below this output value a channel is rounded rather than dithered, and
# it is the second half of the threshold above -- 200 Hz is necessary and
# is not sufficient. Both numbers came off the lit board, on static
# ladders where nothing but the dither could move.
#
# What the eye is judging is the dither's *depth*, one level as a share
# of the light there, against the rate its pattern happens to run at.
# Error diffusion holds one value for 1/fraction frames, so a fraction of
# 0.1 alternates at 20 Hz however fast the paint is -- the rate cannot be
# bought out of this, because the fraction can always be smaller.
#
#   depth   1 LSB on   at 100 Hz   at 20 Hz
#   100%    value 1    calm        flickers
#    50%    value 2    calm        flickers
#    33%    value 3    calm        faint, still there
#    20%    value 5    calm        calm
#    11%    value 9    calm        calm
#
# So 5 is where the worst rate stops being visible. 4 is the untested
# boundary and 5 is inside it.
#
# **That derivation assumes the LED is linear, and it is not.** Keys held at
# 0/1/2/3/4/5 side by side on the real board: 0 to 1 is a different world, 1
# to 2 is plainly visible, and 2/3/4/5 cannot be told apart at all. Only the
# first two steps are visible, so 5 is conservative rather than correct --
# and the arithmetic above, which reasons about "one level as a share of the
# light", is answering a question the part does not obey. Left at 5 because
# nothing in service goes near it (see below), not because the number was
# re-derived. What this buys back is everything above
# it; below it the levels were never recoverable by any temporal trick,
# and rounding at least fails quietly. A dither there is not a smoother
# value, it is a light switching on and off.
DITHER_FLOOR = 5.0

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
# 2.5 s, chosen on a lit board against 2/3/4/5/6/8 s shown on the six keys
# at once. 2 s is 30 breaths a minute, outside the 12-20 a resting adult
# does, and a photodiode capture of a real MacBook sleep light measured
# about 12; this lands at 24, which is slower than the 2 s it replaces and
# still quick enough that a deep pulse reads as a request rather than as
# scenery. Every state uses it and only the floor changes.
#
# The host sends its own period with every `S`, so this is what a host that
# omits one gets, not what the pad normally runs. Canopy sends 2500.
DEFAULT_PULSE_PERIOD_MS = 2500
# `PULSE_GAMMA` shapes nothing any more. It is the exponent of the cosine
# family the curve below replaced, kept because that family's runner-up is
# one line away and because the number itself was earned: 1.5, picked on a
# lit board from a sweep of 1.0/1.2/1.4/1.6/1.8/2.0 carried on the six keys
# at once.
#
# What that sweep settled, and it is worth keeping because the first
# explanation of it was half wrong. A raw sine (gamma 1.0) reads as "the
# bottom is short and the top is long" -- it lingers exactly where the eye
# is least able to see a change. Gamma 2.0 reads as a pause at the bottom,
# because level-minus-floor goes as t^4 there against t^2 at 1.0, so the
# lowest 1% of the swing lasts 410 ms of a 2 s breath instead of 128. Both
# ends are wrong and the answer was between them.
#
# The old note in this place blamed that pause on there being few 8-bit
# levels at low brightness. Both facts are real and they are not cause and
# effect: the freeze is the two **meeting**, 410 ms of dwell spanning under
# 2 LSB. Dithering is the right instrument for that half and the note was
# right to name it; what it got wrong was calling it cheap. It costs a 4x
# paint rate (`DITHER`), below 200 Hz it makes the pulse worse, and below
# `DITHER_FLOOR` no rate saves it at all.
#
# And the whole quantisation half turned out not to happen in service. The
# deepest breath Canopy sends bottoms out at 7.7 of 255 in its faintest lit
# channel, where a one-level step stopped being visible around 2 -- measured
# on the board, keys held at 0/1/2/3/4/5 side by side. Everything above was
# found at brightness 15 with a floor of 0, which is outside the envelope
# the pad is ever driven in.
PULSE_GAMMA = 1.5

# The breath, precomputed at boot. Not from `PULSE_GAMMA` -- that constant
# belongs to the cosine family this replaced; see its own note above.
#
# The shape is `exp(sin)`: `(e^sin(x) - 1/e) / (e - 1/e)`, normalised and
# phase-shifted to start at its minimum. Narrow peak, wide trough -- the
# dwell sits at the bottom of the breath where a raw sine puts it at the
# top, and the top is exactly where the eye is least able to see a change.
# Traced to a 2010 comment by Adam Shea, popularised by Sean Voisen in
# 2011; Shea's stated reason was correcting the log response of
# LED->eye->brain rather than modelling breathing, and the curve is
# exactly time-symmetric about its peak whatever the folklore says.
#
# Chosen on a lit board against five others shown side by side on the six
# keys at once -- a plain triangle, FastLED's `quadwave` and `cubicwave`,
# `sine^1.5`, and the Gaussian fitted to a real MacBook sleep light -- all
# sharing colour, floor, phase and brightness so only the curve differed.
# A gamma sweep over the cosine ran the same way first: 1.0 read as "the
# bottom is short and the top is long", 2.0 as a pause at the bottom, and
# 1.5 was the best of that family before this beat it.
#
# `PULSE_GAMMA` no longer shapes anything -- it belongs to the cosine
# family this replaced. It is kept only because `sine^1.5` is one line
# away and was the runner-up:
#
#     _raw = [((1 - math.cos(2 * math.pi * _i / _CURVE_STEPS)) / 2)
#             ** PULSE_GAMMA for _i in range(_CURVE_STEPS)]
#
# The **table** is a speed change with no effect on the shape. `math.cos`
# and `** PULSE_GAMMA` ran once per key per frame and measured as the
# largest single cost in the loop, and the index is integer arithmetic so
# the float divide goes with them.
#
# 512 is not a round number, it is the smallest power of two finer than a
# frame. A table adds a visible stair only when its steps are coarser than
# the frames sampling it, so the comparison that decides the size is
# against the loop rate rather than against the eye:
#
#     table    step     biggest jump      steps per frame
#     entries  apart    between entries   at 148 Hz (6.76 ms)
#      256     7.81 ms      3.61 LSB           0.9   <- coarser than a frame
#      512     3.91 ms      1.81 LSB           1.7
#
# The biggest change one frame to the next is 3.13 LSB at 148 Hz, so at 512
# the table's own step is already the smaller of the two and contributes no
# hold the frames did not already have. At 256 it is the larger, and would.
#
# Written out as literals this table **hard-faulted CircuitPython into
# safe mode** -- 1536 floats of source, and it was the parser rather than
# the data: measured on the board afterwards, the array costs ~2 KB of a
# free 162 KB and a lookup is 21 us. Build it, never paste it.
_CURVE_STEPS = 512
_E = math.e
_raw = [(math.exp(math.sin(2 * math.pi * _i / _CURVE_STEPS - math.pi / 2)) - 1 / _E)
        / (_E - 1 / _E) for _i in range(_CURVE_STEPS)]
_span = max(_raw) - min(_raw)
PULSE_CURVE = array.array("f", [(_v - min(_raw)) / _span for _v in _raw])
# The cosine starts at its minimum, and the whole phase rule depends on it:
# a key that begins pulsing has to fade up rather than snap to full. That
# is a property of the expression above, so it is asserted rather than
# assumed -- a curve edited to start anywhere else breaks a promise made
# in `set_pulse`, and nothing else in this file would notice.
assert PULSE_CURVE[0] < 0.02

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
i2c = None
# Skipped whole on a board with no I2C keypad, and the skip is the exact
# mirror of the GPIO one below. Running it anyway would import
# `adafruit_neokey` and call `board.STEMMA_I2C()` on a device that has
# neither, so every connect would carry an `ERR i2c setup ...` about
# hardware the board was never built with -- forever, and about a fault
# that cannot be fixed. That is precisely the noise this firmware refuses
# to emit, and a host told to expect it learns to ignore the real one.
if PAD_ADDRESSES:
    try:
        import board

        from adafruit_neokey.neokey1x4 import NeoKey1x4
        i2c = board.STEMMA_I2C()
    except Exception as err:  # noqa: BLE001 - a missing lib and a missing
        # cable arrive here identically, and both must leave the serial
        # half alive so the host is told rather than left staring at a
        # dead port.
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
            # Left at 1.0 and scaled in `paint()` instead. Not a style
            # choice: pixelbuf scales with `(v * int(b*256)) // 256`, an
            # integer floor *after* this file has already rounded to 8
            # bits, so at brightness 0.30 seventy per cent of the values
            # this file can express collapse onto a byte something else
            # already occupies. Dithering upstream of that is provably a
            # no-op -- simulated at 0.30 and below it reproduces today's
            # output frame for frame. One quantisation, owned here.
            pad.pixels.brightness = 1.0
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
# Skipped whole when the profile has no GPIO keys, and the skip is not
# cosmetic: `NeoPixel(pin, 0)` is a zero-length strip, which is either
# an exception -- and then such a board reports `ERR gpio pixels` on
# every single connect, forever, about hardware it was never built with
# -- or an empty group nothing will ever write to. Neither is worth
# carrying, and the first would teach a host to ignore that error.
gpio_switches = []
gpio_errors = []
if GPIO_KEYS:
    try:
        import digitalio

        for num in GPIO_KEY_GPIO:
            pin = getattr(microcontroller.pin, "GPIO{}".format(num))
            switch = digitalio.DigitalInOut(pin)
            switch.switch_to_input(pull=digitalio.Pull.UP)
            gpio_switches.append(switch)
    except Exception as err:  # noqa: BLE001
        gpio_errors.append("keys {}: {}".format(type(err).__name__, err))
    try:
        from neopixel import NeoPixel

        # GRB is the WS2812 family's wire order and what the NeoKey's
        # seesaw driver already assumes, so the breakouts carrying the
        # same NEO3535_REVERSE part should match, and so do the PCB's
        # SK6812MINI-E. If these keys come up with red and green swapped
        # while any NeoKey's look right, this is the line -- it is a
        # property of the LED, and neither the .brd files nor the PCB's
        # schematic states it.
        gpio_pixels = NeoPixel(
            getattr(microcontroller.pin, "GPIO{}".format(GPIO_PIXEL_GPIO)),
            GPIO_KEYS,
            # 1.0 for the reason given at the NeoKey's own brightness
            # line: the scaling happens in `paint()` so there is one
            # quantisation rather than two stacked.
            auto_write=False, brightness=1.0,
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
# The period in **milliseconds**, which is what the wire already sends, and
# the phase as a **position** inside it rather than the timestamp the breath
# started at. Both stay small integers for ever, and that is the whole
# reason for the shape.
#
# `monotonic_ns()` passes MicroPython's 30-bit small-integer boundary within
# a second of boot, so every expression touching it allocates. The curve
# index used to be
# `(now - pulse_started[i]) % period_ns[i] * _CURVE_STEPS // period_ns[i]`
# -- four big-integer operations per key per frame, and replacing just that
# expression with a small-integer counter took the loop from 142 Hz to 180
# with six keys pulsing. 236 us a key.
#
# Milliseconds counted from boot would not have fixed it: `now // 1_000_000`
# crosses the same boundary after about twelve days, and this device lives
# plugged in for weeks -- so that version works on the bench and stops
# working in service, silently, months later. A position advanced each frame
# and reduced modulo the period is bounded by the period itself and never
# grows.
period_ms = [DEFAULT_PULSE_PERIOD_MS] * NUM_KEYS
phase_ms = [0] * NUM_KEYS
# Nanoseconds the frame delta has not yet handed to `phase_ms`, and the
# timestamp it was last measured from. Carrying the remainder rather than
# dropping it is not tidiness: truncating each frame's delta would run every
# breath slow by the truncation, 0.6% at a 7 ms frame, and a rate error
# never corrects itself.
_phase_carry_ns = 0
_phase_last_ns = 0
# Last value actually pushed to each pixel. None means "nothing written
# yet", which is distinct from black, so the startup fill does not poison
# the cache. Holds the *logical* color: adafruit_pixelbuf re-renders from
# its unscaled buffer when brightness changes, so `B` still lands on
# solid keys without invalidating this.
# Holds the *hardware* byte triple -- what pixelbuf will transmit --
# because this file now applies the global brightness itself. It used to
# hold the logical colour and lean on pixelbuf re-rendering its unscaled
# buffer when `.brightness` changed; with the scaling moved here that no
# longer happens, so `B` has to invalidate instead. `set_brightness`
# does, and the settled-solid skip in the render loop tests this list so
# that the invalidation actually reaches a key that has stopped moving.
last_rgb = [None] * NUM_KEYS
# Which pixel groups have writes waiting for a show().
group_dirty = [False] * len(pixel_groups)

# The global brightness, 0.0-1.0, applied in `paint()`. The host owns it
# through `B`.
brightness = DEFAULT_BRIGHTNESS
# Per-channel dither residue, three floats per key, flat so the hot path
# indexes instead of allocating. Carrying the fraction a byte cannot hold
# into the next frame is the whole mechanism: the output alternates
# between the two bytes either side of the true value at whatever duty
# makes the time-average land on it, which is why the mean tracks the
# ideal to about 0.002 LSB. Only meaningful above `DITHER`'s threshold --
# below it the alternation is slow enough to read as flicker.
dither_err = [0.0] * (NUM_KEYS * 3)

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


def paint(idx, base, level, settled):
    """Scale one key's colour by `level` and the global brightness, to bytes.

    The single quantisation in this file. Everything upstream is float,
    everything downstream is what pixelbuf transmits, and `.brightness`
    is left at 1.0 so nothing rounds twice.

    Above `DITHER`'s threshold the fraction a byte cannot carry is kept
    and added to the next frame, so a key whose true value sits between
    two bytes alternates between them at whatever duty averages out
    right. That is what gives a low-brightness breath back the levels the
    8-bit output does not have. Longest freeze on one byte at the bottom
    of a gamma-2.0 breath, floor 0.15, worst of the three channels and
    counted only where dithering is allowed to act, measured by
    `tools/dither_check.py` running this very function with `DITHER` off at
    50 Hz against on at 200 Hz: 500 -> 50 ms at brightness 0.60, 500 -> 55
    at 0.30, 180 -> 60 at 0.15, 380 -> 70 at 0.10. The rate is not what
    does it -- the same code undithered at 200 Hz measures 185 ms where
    50 Hz measured 180.

    Those figures moved once already without being re-measured, which is
    the reason to distrust any number pasted into a comment: `DITHER_FLOOR`
    landing changed what the check counts, and only the 0.60 row survived
    it. Re-run the tool rather than trusting this paragraph.

    Under `DITHER_FLOOR` the channel is rounded instead, which is the
    whole reason that constant exists: down there one level is most of the
    light, and toggling it is a lamp switching rather than a value.

    A settled key is rounded too, and its residue cleared. Error diffusion
    on a value that never changes keeps alternating for ever, which would
    mean a solid key never stops writing and the render loop's skip never
    engages -- trading a one-LSB gain on a static colour for permanent
    traffic and a permanent shimmer.

    The floor is tested per channel, not per key. ff8000 at a low
    brightness puts red near 39, green near 19 and blue at 0, so a key is
    routinely above the floor in one channel and below it in another; a
    per-key test would either flicker the blue or freeze the red.
    """
    o = idx * 3
    r = ((base >> 16) & 0xFF) * level * brightness
    g = ((base >> 8) & 0xFF) * level * brightness
    b = (base & 0xFF) * level * brightness
    if settled or not DITHER:
        dither_err[o] = dither_err[o + 1] = dither_err[o + 2] = 0.0
        write_pixel(idx, (int(r + 0.5) << 16) | (int(g + 0.5) << 8) | int(b + 0.5))
        return
    # Written out per channel rather than through a helper: this runs
    # three times per key per frame, 3600 times a second on the PCB, and a
    # CircuitPython call costs more than the arithmetic inside it.
    #
    # Each residue is `v - int(v)` of a non-negative v, so it stays in
    # [0, 1) and the sum stays under 256. That is what keeps a channel
    # from carrying into the one above it, which would not look like a
    # rounding error -- it would look like the wrong colour.
    if r < DITHER_FLOOR:
        dither_err[o] = 0.0
        ir = int(r + 0.5)
    else:
        r += dither_err[o]
        ir = int(r)
        dither_err[o] = r - ir
    if g < DITHER_FLOOR:
        dither_err[o + 1] = 0.0
        ig = int(g + 0.5)
    else:
        g += dither_err[o + 1]
        ig = int(g)
        dither_err[o + 1] = g - ig
    if b < DITHER_FLOOR:
        dither_err[o + 2] = 0.0
        ib = int(b + 0.5)
    else:
        b += dither_err[o + 2]
        ib = int(b)
        dither_err[o + 2] = b - ib
    write_pixel(idx, (ir << 16) | (ig << 8) | ib)


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
    if to_rgb[idx] == rgb and to_floor[idx] == floor and period_ms[idx] == period:
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
    if restart_phase or period_ms[idx] != period:
        phase_ms[idx] = 0
    period_ms[idx] = period


def set_color(idx, rgb):
    if 0 <= idx < NUM_KEYS:
        # Solid is floor 1.0: the sine term drops out and the key just
        # sits at its colour.
        retarget(idx, rgb, 1.0, period_ms[idx], False)


def set_pulse(idx, rgb, period, floor):
    if not 0 <= idx < NUM_KEYS:
        return
    # Clamp before the comparison in retarget, so two commands that clamp
    # to the same effective pulse are recognised as identical.
    period = max(100, period)
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
        phase_ms[i] = 0
        period_ms[i] = DEFAULT_PULSE_PERIOD_MS
        dither_err[i * 3] = dither_err[i * 3 + 1] = dither_err[i * 3 + 2] = 0.0
        write_pixel(i, 0x000000)


def set_brightness(percent):
    """Set the global brightness. Every key is repainted, not re-sent.

    pixelbuf used to do this for free: it kept an unscaled buffer and
    re-rendered it when `.brightness` moved, so `B` landed on solid keys
    without this file touching them. The scaling lives in `paint()` now,
    so the staged bytes are simply wrong until each key is computed
    again -- and `invalidate_pixels()` is what makes the render loop stop
    skipping the settled ones long enough to do it.
    """
    global brightness
    brightness = max(0, min(100, percent)) / 100
    invalidate_pixels()


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
        period = int(parts[3]) if len(parts) > 3 else DEFAULT_PULSE_PERIOD_MS
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
# Seeded from the clock rather than left at 0, or the first paint would
# hand every phase the whole uptime and start each breath somewhere
# arbitrary instead of at its trough.
_phase_last_ns = time.monotonic_ns()
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
    print("WARNING: GPIO keys degraded ({}).".format(gpio_error))
    print("Keys {}-{} are on GPIO {} / pixels on GPIO {}."
          .format(GPIO_BASE, GPIO_BASE + GPIO_KEYS - 1,
                  "/".join(str(n) for n in GPIO_KEY_GPIO),
                  GPIO_PIXEL_GPIO))
if board_error:
    print("WARNING: unknown board ({}).".format(board_error))
    print("No keypad was claimed at all -- this is not a wiring fault.")
    print("Set MPAD_BOARD in CIRCUITPY/settings.toml to one of {}, "
          "then reset.".format("/".join(sorted(PROFILES))))


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
            if board_error:
                # First, because it is the reason the other two are
                # silent: an unresolved profile claims no pins and no
                # addresses, so neither setup guard ever runs and neither
                # has anything to report. Without this line the host gets
                # `HELLO <ver> 0` and no explanation at all.
                #
                # It passes the test the declined diagnostics failed --
                # what state would it be wrong in? None. It fires only
                # when the profile genuinely did not resolve, which is
                # never anything but a real fault, and it is the exact
                # twin of the two below: emitted once, at connect, for a
                # half of the device that otherwise cannot speak.
                write_line(
                    "ERR board {} (set MPAD_BOARD in settings.toml)".format(
                        board_error))
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
                # Advance every breath by the time since the last paint,
                # once per frame and in one place. This is the only
                # big-integer arithmetic left in the pulse: one subtract and
                # one divide a frame, where the per-key form cost four
                # operations a key. The remainder is carried rather than
                # dropped -- see `_phase_carry_ns`.
                _phase_carry_ns += now - _phase_last_ns
                _phase_last_ns = now
                _step_ms = _phase_carry_ns // 1_000_000
                _phase_carry_ns -= _step_ms * 1_000_000
                for i in range(NUM_KEYS):
                    # Inlined fast path for a fade that has finished, which
                    # is almost every frame of a steady pulse. `fade_progress`
                    # returns 1.0 for any elapsed past the crossfade, and for
                    # a crossfade of 0 as well, so the test covers both.
                    if now - fade_started[i] >= crossfade_ns:
                        t = 1.0
                    else:
                        t = fade_progress(i, now)
                    settled = False
                    if t >= 1.0:
                        # `last_rgb` joins the test, and it is load-bearing
                        # rather than defensive. This skip is now the only
                        # thing standing between a settled key and a `B`
                        # that changed what its bytes should be: pixelbuf
                        # used to re-render a brightness change for free
                        # and no longer does, so a key skipped here would
                        # hold its old brightness until the host happened
                        # to recolour it. `invalidate_pixels()` clears the
                        # entry, this lets exactly one repaint through, and
                        # the entry it writes puts the skip back.
                        if (to_floor[i] >= 1.0 and from_floor[i] >= 1.0
                                and from_rgb[i] == to_rgb[i]
                                and last_rgb[i] is not None):
                            continue  # settled, solid, and already on the wire
                        from_rgb[i] = to_rgb[i]
                        from_floor[i] = to_floor[i]
                        # `settled` answers `paint`'s question and only that
                        # one: is this key solid, so its value should be
                        # rounded rather than dithered. The skip above asks a
                        # different question -- is it solid *and already on
                        # the wire* -- and needs the colour comparison for it.
                        #
                        # One flag used to answer both, and that was the bug.
                        # Carrying `from_rgb[i] == to_rgb[i]` into `settled`
                        # made it false on the one frame a fade completes on,
                        # because the assignment two lines up had not run yet,
                        # so that frame painted through the dithering branch
                        # -- and then the skip froze whichever of the two
                        # bytes the dither happened to emit, for ever.
                        # `paint`'s rounding branch was unreachable for any
                        # key that arrived by fading, which is every key.
                        # Measured before the fix: 2 of 7 tick rates settled
                        # a channel one level off round-to-nearest and stayed
                        # there; check 9 in `tools/dither_check.py` is that
                        # frame, and was watched going red on the old code.
                        #
                        # So what fixed it was dropping the comparison, not
                        # moving the line: `to_floor[i]` is not written by
                        # either assignment above, and this reads nothing
                        # else. An earlier version of this comment claimed
                        # the ordering was the point, which would have let a
                        # later edit "restore" the comparison believing
                        # position was all that mattered.
                        settled = to_floor[i] >= 1.0
                    if t >= 1.0:
                        # `from` was just assigned `to` above, so the lerp and
                        # the floor interpolation both have closed forms here
                        # and the call is pure overhead.
                        base = to_rgb[i]
                        floor = to_floor[i]
                    else:
                        base = lerp_rgb(from_rgb[i], to_rgb[i], t)
                        floor = from_floor[i] + (to_floor[i] - from_floor[i]) * t
                    # Integer modulo *and* integer scale, so the phase stays
                    # exact however long the board has been up and no float
                    # divide happens here.
                    # Small integers throughout, bounded by the period: the
                    # phase is a position that is advanced and reduced, never
                    # a difference of two timestamps that both grow for ever.
                    _p = phase_ms[i] + _step_ms
                    # A subtract rather than `%`: `_step_ms` is one frame and
                    # `period_ms` is clamped at 100, so the wrap can fire at
                    # most once and a modulo is the more expensive way to ask.
                    if _p >= period_ms[i]:
                        _p -= period_ms[i]
                    phase_ms[i] = _p
                    level = floor + (1 - floor) * PULSE_CURVE[
                        _p * _CURVE_STEPS // period_ms[i]]
                    paint(i, base, level, settled)
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
