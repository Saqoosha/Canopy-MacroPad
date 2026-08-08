"""Canopy MacroPad — main firmware.

The device is deliberately dumb: it reports key edges and paints the
colors it is told to paint. All meaning (which pane, which status, when
to blink) lives in the host. That split is what lets the same wire
protocol survive the move to BLE later.

Wire protocol, line-delimited ASCII on usb_cdc.data.

  host -> device
    C <idx> <rrggbb>   set key idx to that color, e.g. `C 0 ff8000`
    S <idx> <rrggbb> [ms] [floor]
                       pulse that color, sine-eased. `ms` is the full
                       period, `floor` is the percentage the dip bottoms
                       out at: 0 reads as an alert, 80 as a slow breath
                       that says "alive" without asking for attention.
    B <0-100>          global brightness
    P                  ping
    R                  reset: all keys off

  device -> host
    HELLO <ver> <keys> sent when a host opens the data port
    PONG <ver> <keys>  reply to P
    K <idx> <0|1>      key idx pressed (1) / released (0)
    ERR <msg>          a command could not be handled

Nothing else is ever written to the data port. Debug output goes to the
console port (plain `print`), which the host does not read.
"""

import math
import time

import board
import usb_cdc
from adafruit_neokey.neokey1x4 import NeoKey1x4

# 1: C / B / P / R
# 2: adds S (device-side sine pulse)
PROTOCOL_VERSION = 2

# Number of NeoKey 1x4 boards on the I2C bus. The second board needs its
# A0 jumper bridged on the back to move it off the default address.
NUM_PADS = 1
PAD_ADDRESSES = (0x30, 0x31)[:NUM_PADS]
KEYS_PER_PAD = 4

# Full brightness is genuinely painful to sit next to, but going too dim
# costs 8-bit steps: at 30% a deep pulse has only a handful of distinct
# values near its floor and visibly stalls there. 60% measured as the
# point where the fade stays smooth without being glaring. The host can
# override this at runtime with `B`.
DEFAULT_BRIGHTNESS = 0.6

# A key edge must hold this long before it is reported. Mechanical
# switches chatter for a few ms; without this the host sees phantom
# double-presses.
DEBOUNCE_S = 0.015

# ~200 Hz. Keeps press-to-report well under a single 60 Hz frame while
# leaving the I2C bus mostly idle.
POLL_INTERVAL_S = 0.005

# The pulse lives here rather than on the host. A square blink is one
# command per half period and could sit on the host happily; a sine fade
# is ~50 updates a second, which is a silly thing to push down a wire and
# would stutter on any host hiccup. Keeping it local also means the pulse
# is already where it has to be when this moves to BLE.
DEFAULT_PULSE_PERIOD_S = 2.0
# 50 Hz. Faster buys nothing: the 8-bit output repeats between steps, and
# repeats are skipped before they reach I2C.
PULSE_STEP_S = 0.02
# Perceptually a raw sine lingers at the top, and gamma 2.0 corrects
# that -- but only where there are 8-bit steps to spend. At a low global
# brightness the bottom of a deep pulse has a handful of distinct values
# in total, and squaring makes the level crawl through exactly that
# region, so the fade visibly stalls at the floor. Staying near 1.0
# trades the perceptual curve for movement that never runs out of steps.
PULSE_GAMMA = 1.0
# A pulse is timed from the moment its command arrives, so a key entering
# a state fades up from the floor and the transition itself is visible.
# Keys whose states changed at different moments then drift apart on
# their own, with no phase bookkeeping on the host.
#
# This spread is the backstop for the case that does not: several keys
# told to pulse in the same instant, which is exactly what a full re-push
# after HELLO looks like. Fraction of a period that key N is offset from
# key 0; 0 leaves simultaneous starts in lockstep, where every lit key
# dims together and the approval key's peak sinks into its neighbours'.
PULSE_PHASE_SPREAD = 1.0


# A missing Qwiic cable takes the I2C pull-ups with it, and NeoKey1x4()
# raises. That must not kill the whole device: with the serial half still
# up, a host that receives `HELLO 1 0` learns "the pad is plugged in but
# has no keypad attached", which is a diagnosable state. Dying here
# instead leaves a port that never answers, indistinguishable from a
# board that failed to boot at all.
pads = []
i2c_error = None
try:
    i2c = board.STEMMA_I2C()
    pads = [NeoKey1x4(i2c, addr=addr) for addr in PAD_ADDRESSES]
    for pad in pads:
        pad.pixels.brightness = DEFAULT_BRIGHTNESS
        pad.pixels.fill(0x000000)
except Exception as err:  # noqa: BLE001 - any I2C fault is the same story
    pads = []
    i2c_error = str(err)

# Reported to the host in HELLO/PONG, so the key count is never a
# constant on the macOS side. Zero when the keypad is missing.
NUM_KEYS = KEYS_PER_PAD * len(pads)

# Per key: (base_rgb, period_s, floor, started_at) while pulsing, None
# while solid.
pulse = [None] * NUM_KEYS
# Last value actually pushed to each pixel, so redundant writes are cheap
# to detect. None means "nothing written yet".
last_rgb = [None] * NUM_KEYS

# usb_cdc.data is None when boot.py did not run (or ran before the data
# interface was enabled). Falling back to the console port keeps the
# device testable with a plain serial monitor instead of looking dead,
# and the ERR line below says exactly what went wrong.
serial = usb_cdc.data
using_fallback_port = serial is None
if using_fallback_port:
    serial = usb_cdc.console


def write_line(text):
    """Write one protocol line, dropping it if no host is listening.

    Writing to a disconnected CDC endpoint stalls the loop, which would
    freeze key scanning for as long as the cable sits unplugged.
    """
    if serial.connected:
        serial.write(text.encode() + b"\n")


def write_pixel(idx, rgb):
    """Push a color to the hardware, skipping unchanged writes.

    The pulse recomputes every key 50 times a second; most of those land
    on the same 8-bit value as the previous step, and each redundant
    write is an I2C transaction competing with the key scan.
    """
    if last_rgb[idx] != rgb:
        last_rgb[idx] = rgb
        pads[idx // KEYS_PER_PAD].pixels[idx % KEYS_PER_PAD] = rgb


def set_color(idx, rgb):
    if 0 <= idx < NUM_KEYS:
        pulse[idx] = None
        write_pixel(idx, rgb)
    # Out-of-range indices are dropped in silence on purpose: the host
    # may paint before it has learned the key count from HELLO/PONG.


def set_pulse(idx, rgb, period_s, floor):
    if not 0 <= idx < NUM_KEYS:
        return
    spec = (rgb, max(0.1, period_s), min(max(floor, 0.0), 1.0))
    current = pulse[idx]
    # Restarting the clock only for a *different* pulse is what makes a
    # host safe to re-push from. A host that repaints its whole state
    # periodically, or after every HELLO, would otherwise reset the phase
    # each time and the breath would never get past its first moments.
    if current is not None and current[:3] == spec:
        return
    pulse[idx] = spec + (time.monotonic(),)


def all_off():
    for i in range(NUM_KEYS):
        pulse[i] = None
        write_pixel(i, 0x000000)


def set_brightness(percent):
    level = max(0, min(100, percent)) / 100
    for pad in pads:
        pad.pixels.brightness = level


def handle(line):
    parts = line.decode().strip().split()
    if not parts:
        return
    cmd = parts[0]
    if cmd == "C" and len(parts) == 3:
        set_color(int(parts[1]), int(parts[2], 16))
    elif cmd == "S" and len(parts) in (3, 4, 5):
        period = int(parts[3]) / 1000 if len(parts) > 3 else DEFAULT_PULSE_PERIOD_S
        floor = int(parts[4]) / 100 if len(parts) > 4 else 0.0
        set_pulse(int(parts[1]), int(parts[2], 16), period, floor)
    elif cmd == "B" and len(parts) == 2:
        set_brightness(int(parts[1]))
    elif cmd == "P":
        write_line("PONG {} {}".format(PROTOCOL_VERSION, NUM_KEYS))
    elif cmd == "R":
        all_off()
    else:
        write_line("ERR unknown {}".format(cmd))


# --- key state ---------------------------------------------------------
# `stable` is what the host has been told. `raw_prev` plus `changed_at`
# implement the debounce: an edge only becomes stable once the raw level
# has held its new value for DEBOUNCE_S.
stable = [False] * NUM_KEYS
raw_prev = [False] * NUM_KEYS
changed_at = [0.0] * NUM_KEYS

rx_buffer = b""
was_connected = False
last_pulse_at = 0.0

if using_fallback_port:
    print("WARNING: usb_cdc.data is None - boot.py did not take effect.")
    print("Copy boot.py to CIRCUITPY, then physically unplug and replug USB.")
if i2c_error:
    print("WARNING: no keypad on I2C ({}).".format(i2c_error))
    print("Check the Qwiic cable between the QT Py and the NeoKey.")


while True:
    now = time.monotonic()

    # --- host connect / disconnect -------------------------------------
    connected = serial.connected
    if connected and not was_connected:
        # Announce on every fresh open, not just at power-on: a banner
        # sent at boot is lost if the host was not listening yet. This is
        # also the host's cue to re-push every color after a device reset.
        write_line("HELLO {} {}".format(PROTOCOL_VERSION, NUM_KEYS))
        if using_fallback_port:
            write_line("ERR no-data-cdc-check-boot-py")
        if i2c_error:
            write_line("ERR i2c {}".format(i2c_error))
    elif was_connected and not connected:
        # Nobody owns the LEDs any more. Stale status is worse than none:
        # a frozen orange key claims a session still wants an answer.
        all_off()
    was_connected = connected

    # --- commands from the host (non-blocking) -------------------------
    if serial.in_waiting:
        rx_buffer += serial.read(serial.in_waiting)
        while b"\n" in rx_buffer:
            line, rx_buffer = rx_buffer.split(b"\n", 1)
            try:
                handle(line)
            except Exception as err:  # noqa: BLE001 - never die on bad input
                write_line("ERR {}".format(err))

    # --- pulse ---------------------------------------------------------
    if now - last_pulse_at >= PULSE_STEP_S:
        last_pulse_at = now
        for i in range(NUM_KEYS):
            spec = pulse[i]
            if spec is None:
                continue
            base, period, floor, started = spec
            # Cosine starting at its minimum, so a key that begins
            # pulsing fades up rather than snapping to full.
            phase = ((now - started) / period
                     + i * PULSE_PHASE_SPREAD / NUM_KEYS) % 1.0
            level = (1 - math.cos(2 * math.pi * phase)) / 2
            level = floor + (1 - floor) * level ** PULSE_GAMMA
            write_pixel(i, (int(((base >> 16) & 0xFF) * level) << 16)
                        | (int(((base >> 8) & 0xFF) * level) << 8)
                        | int((base & 0xFF) * level))

    # --- key scan ------------------------------------------------------
    # get_keys() reads all four keys of a board in one I2C transaction,
    # which is 4x fewer round trips than indexing each key.
    raw = []
    for pad in pads:
        raw.extend(pad.get_keys())

    for i in range(NUM_KEYS):
        level = raw[i]
        if level != raw_prev[i]:
            raw_prev[i] = level
            changed_at[i] = now
        elif level != stable[i] and (now - changed_at[i]) >= DEBOUNCE_S:
            stable[i] = level
            write_line("K {} {}".format(i, 1 if level else 0))

    time.sleep(POLL_INTERVAL_S)
