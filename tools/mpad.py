#!/usr/bin/env python3
"""Host-side console for the Canopy MacroPad firmware.

Stdlib only, so there is nothing to install before bring-up. Serves two
jobs during Phase 1 — probe, and talk — plus three scripted variants of
talking:

    tools/mpad.py                 probe, then open a console on the data port
    tools/mpad.py --probe         probe and exit (prints a report)
    tools/mpad.py --port PATH     skip probing, talk to PATH
    tools/mpad.py --demo          light every key in turn, then mirror
                                  presses to white. Verifies the whole
                                  loop without typing anything.
    tools/mpad.py --palette       step through candidate status colors and
                                  global brightness, to re-tune values
                                  against real ambient light. Prints the
                                  post-brightness 8-bit values, which is
                                  where dark colors fall apart.
    tools/mpad.py --load          hold every key at full white, brightness
                                  100. Not for looking at — it is the
                                  worst case the pixel rail has to
                                  survive, and the state to meter it in.
"""

import argparse
import glob
import os
import select
import subprocess
import sys
import termios
import time

PROBE_TIMEOUT_S = 1.5
CANDIDATE_GLOB = "/dev/cu.usbmodem*"
ADAFRUIT_VID = "9114"  # 0x239A
# Six distinct hues, so a six-key pad has no two neighbours the same.
# Cycled if the device ever reports more keys than there are entries.
DEMO_COLORS = ["ff0000", "00ff00", "0040ff", "ff8000", "00ffa0", "ff00ff"]
# Equal RGB does not come out neutral on these LEDs — the green channel
# is the weak one, so ffffff reads visibly purple through a clear keycap.
# Trimming red and blue ~6% is enough; measured as the smallest cut that
# looks neutral, and deeper cuts were indistinguishable from it.
DEMO_HELD = "f0fff0"

# Bring-up candidates, NOT the settled palette — the shipped values live
# in the README's status-colour table and are repeated on page 1 here for
# reference. These pages exist to re-tune against a new keycap, a new
# diffuser, or a different desk lamp; they are the question, not the
# answer.
#
# A page is a list of candidates, not a picture of the pad: entry n goes
# on key n and any keys past the end of the page are turned off. Four
# entries against six keys is fine and arguably better for an A/B -- two
# dark keys between the samples and nothing else competing.
PALETTE_PAGES = [
    ("the shipped palette", [
        ("0040ff", "running"),
        ("00ffa0", "background task"),
        ("ff8000", "awaiting approval"),
        ("00ff00", "done, unread"),
    ]),
    ("idle, error, and dimmer alternatives", [
        ("273027", "idle (shipped, white-balanced)"),
        ("303030", "idle, uncorrected - reads purple"),
        ("ff0000", "error"),
        ("00c0c0", "cyan, rejected - too close to blue"),
    ]),
    ("blue vs cyan, alternating - the hard pair", [
        ("0040ff", "blue"),
        ("00ffa0", "cyan (shipped)"),
        ("0040ff", "blue"),
        ("00c0c0", "cyan, rejected"),
    ]),
]


# Returned by do_probe when several boards answered: not a port, but
# not "nothing found" either.
AMBIGUOUS = object()


class DeviceGone(Exception):
    """The port went away mid-session — unplugged, or closed under us."""


def open_raw(path):
    """Open a CDC-ACM port in raw mode, non-blocking.

    CDC ignores line speed entirely, so no baud rate is set — for a USB
    serial device that setting is decoration. Raw in the `cfmakeraw`
    sense, except `VMIN = 0` so reads never block.
    """
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        attrs = termios.tcgetattr(fd)
        attrs[0] = 0  # iflag
        attrs[1] = 0  # oflag
        attrs[2] = ((attrs[2] & ~termios.CSIZE & ~termios.PARENB)
                    | termios.CS8 | termios.CLOCAL | termios.CREAD)
        attrs[3] = 0  # lflag
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        termios.tcflush(fd, termios.TCIOFLUSH)
    except BaseException:
        # tcgetattr on a node that is not a tty — a stale device file
        # after an unplug, say — would otherwise leak the descriptor,
        # once per candidate port probed.
        os.close(fd)
        raise
    return fd


class LineReader:
    """Accumulates raw reads and returns complete, non-empty lines.

    A partial trailing line is held for the next call. Raises DeviceGone
    when the port dies, which is the one thing a bring-up tool must not
    confuse with "nothing to read yet".
    """

    def __init__(self, fd):
        self.fd = fd
        self.buf = b""

    def poll(self):
        try:
            chunk = os.read(self.fd, 4096)
        except BlockingIOError:
            return []  # the only legitimate "not yet"
        except OSError as err:
            raise DeviceGone("read failed: {}".format(err)) from err
        if not chunk:
            # With VMIN=0 an empty read is normal, so this is not EOF on
            # its own. A dead fd, though, reports permanently readable in
            # select and returns empty forever — which would spin at 100%
            # CPU looking connected. Confirm with a zero-length write.
            try:
                os.write(self.fd, b"")
            except OSError as err:
                raise DeviceGone("port closed: {}".format(err)) from err
            return []
        self.buf += chunk
        lines = []
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            text = line.decode("utf-8", "replace").strip()
            if text:
                lines.append(text)
        # A device that never sends a newline must not grow this forever.
        if len(self.buf) > 4096:
            self.buf = b""
        return lines


def send(fd, text, timeout=2.0):
    """Write one whole line, or raise DeviceGone.

    The fd is non-blocking, so a bare os.write can write fewer bytes than
    asked and truncate a command mid-line — the device would then answer
    a corrupt line with a baffling ERR.
    """
    data = (text.rstrip("\n") + "\n").encode()
    deadline = time.monotonic() + timeout
    while data:
        try:
            written = os.write(fd, data)
        except BlockingIOError:
            # A device that asserts DTR then stops reading would spin
            # here forever printing nothing -- the "looks connected,
            # isn't" state DeviceGone exists to name. The firmware's
            # halt branch is exactly such a device.
            if time.monotonic() >= deadline:
                raise DeviceGone("device stopped accepting input after "
                                 "{:.0f}s (firmware halted?)".format(timeout))
            select.select([], [fd], [], 0.25)
            continue
        except OSError as err:
            raise DeviceGone("write failed: {}".format(err)) from err
        data = data[written:]


def close_quietly(fd, farewell=True):
    """Send R and close, without letting cleanup mask the real error."""
    try:
        if farewell:
            send(fd, "R")
            print("\nclosed (sent R)")
    except DeviceGone as err:
        print("\ndevice gone, could not send R: {}".format(err),
              file=sys.stderr)
    finally:
        os.close(fd)


def probe_port(path):
    """Return the PONG/HELLO line if this port speaks the protocol.

    The console port runs the REPL: it echoes `P` back but never answers
    `PONG`, which is what makes this a reliable discriminator — far more
    so than the trailing digits of the device name.
    """
    try:
        fd = open_raw(path)
    except (OSError, termios.error) as err:
        # termios.error is not an OSError subclass, so catching only
        # OSError would let it escape and kill the whole probe run.
        return None, "open failed: {}".format(err)
    try:
        reader = LineReader(fd)
        send(fd, "P")
        deadline = time.monotonic() + PROBE_TIMEOUT_S
        seen = []
        while time.monotonic() < deadline:
            for line in reader.poll():
                seen.append(line)
                if line.startswith("PONG") or line.startswith("HELLO"):
                    return line, None
            time.sleep(0.02)
        return None, "no PONG (saw: {})".format(seen or "nothing")
    except DeviceGone as err:
        return None, str(err)
    finally:
        os.close(fd)


def usb_identity():
    """Adafruit USB devices (VID 0x239A) as ioreg reports them.

    Vendor-filtered, not a CircuitPython test: another Adafruit board on
    the bench shows up here too, and a CircuitPython board from any other
    vendor does not.
    """
    try:
        proc = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-w0", "-l"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as err:
        # Staying silent here would be worse than useless: the README
        # tells the reader that no VID 0x239A line means the board is not
        # on the bus, so a broken query would masquerade as a hardware
        # diagnosis and send them to replace innocent cables.
        print("usb: could not run ioreg ({}) — USB report unavailable. "
              "Do NOT read this as 'no board'.".format(err), file=sys.stderr)
        return []
    if proc.returncode != 0:
        print("usb: ioreg exited {}: {}".format(
            proc.returncode, proc.stderr.strip()[:200]), file=sys.stderr)
        return []

    found, others, block = [], 0, {}

    def finish(block):
        nonlocal others
        if not block.get("vid"):
            return
        if block["vid"] == ADAFRUIT_VID:
            found.append(dict(block))
        else:
            others += 1

    for line in proc.stdout.splitlines():
        # ioreg prints one node per "+-o" line. Closing the record there
        # rather than once a product/vid/pid triple happens to be
        # complete stops a hub's VID being paired with the next device's
        # product name — which would publish a wrong number at exactly
        # the moment the operator copies it into the macOS side.
        if "+-o " in line:
            finish(block)
            block = {}
        for key, label in (
            ('"USB Product Name" = ', "product"),
            ('"USB Vendor Name" = ', "vendor"),
            ('"idVendor" = ', "vid"),
            ('"idProduct" = ', "pid"),
        ):
            if key in line:
                block[label] = line.split(key, 1)[1].strip().strip('"')
    finish(block)

    if not found and others:
        print("usb: no Adafruit (0x239A) device among {} USB devices"
              .format(others), file=sys.stderr)
    return found


def do_probe(verbose=True):
    """Return the single data port, or None if not exactly one answered."""
    candidates = sorted(glob.glob(CANDIDATE_GLOB))
    if verbose:
        print("candidate ports: {}".format(candidates or "none"))
        for dev in usb_identity():
            try:
                hexed = " (0x{:04x} / 0x{:04x})".format(
                    int(dev["vid"]), int(dev.get("pid", "0")))
            except ValueError:
                # This function exists so a broken query cannot pose as a
                # hardware diagnosis; crashing on odd ioreg text would
                # undo that for the sake of a convenience.
                hexed = ""
            print("usb: product={!r} vid={} pid={}{}".format(
                dev.get("product", "?"), dev["vid"],
                dev.get("pid", "?"), hexed))
    data_ports = []
    for path in candidates:
        line, why = probe_port(path)
        if line:
            data_ports.append(path)
            if verbose:
                print("  {}  DATA   -> {}".format(path, line))
        elif verbose:
            print("  {}  console/silent ({})".format(path, why))
    if len(data_ports) > 1:
        print("\n{} devices answered: {}. Pick one with --port.".format(
            len(data_ports), ", ".join(data_ports)), file=sys.stderr)
        # Distinct from "nothing answered", so main does not follow a
        # correct explanation with its opposite.
        return AMBIGUOUS
    return data_ports[0] if data_ports else None


def read_key_count(reader, timeout=PROBE_TIMEOUT_S):
    """How many keys the device says it has, or None if it never says.

    `HELLO <ver> <keys>` arrives unprompted on connect and `PONG <ver>
    <keys>` answers `P`, so either will do and whichever lands first
    wins. Lines are echoed as they are read because this is a console:
    swallowing the handshake to parse it would hide the one exchange
    worth seeing.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for line in reader.poll():
            print("< {}".format(line))
            parts = line.split()
            if len(parts) >= 3 and parts[0] in ("PONG", "HELLO"):
                try:
                    return int(parts[2])
                except ValueError:
                    pass  # a mangled line is not a key count
        time.sleep(0.02)
    return None


def load(path):
    """Hold every key at full white, which is what a rail is measured under.

    Idle is the flattering case and it is not the case that browns out.
    The pixels on both board kinds hang off the incoming Qwiic rail rather
    than off the regulated 3.3 V behind it -- see README "Hardware" -- so
    what the LEDs see is the QT Py's rail minus whatever 50 mm of thin
    Qwiic conductor drops under load, and that drop only exists when there
    is load.

    Probe at the LED end, not at the QT Py: the two differ by exactly the
    thing being measured. Take the reading at four keys before the
    breakouts land and again at six afterwards -- one number cannot
    separate cable drop from a regulator giving up, and two can.
    """
    fd = open_raw(path)
    reader = LineReader(fd)
    keys = read_key_count(reader)
    if keys is None:
        keys = len(DEMO_COLORS)
        print("no PONG within {}s - assuming {} keys.".format(
            PROBE_TIMEOUT_S, keys))
    # No crossfade and no pulse: the point is a steady worst case, not a
    # transition. Full brightness on purpose -- the shipped 60 is not what
    # the supply has to survive.
    send(fd, "X 0")
    send(fd, "B 100")
    for idx in range(keys):
        send(fd, "C {} ffffff".format(idx))
    print("{} keys at full white, brightness 100.".format(keys))
    print("meter the pixel VDD at an LED, not at the QT Py.")
    print("[Ctrl-C] to stop and blank them")
    try:
        while True:
            for line in reader.poll():
                print("< {}".format(line))
            time.sleep(0.1)
    except KeyboardInterrupt:
        send(fd, "R")
        print("\nblanked.")
    return 0


def console(path, demo=False):
    fd = open_raw(path)
    reader = LineReader(fd)
    print("connected: {}  (Ctrl-D to quit)".format(path))

    try:
        send(fd, "P")
        if demo:
            # Ask rather than assume. The key count is the second field
            # of PONG, and carrying it is the whole reason the protocol
            # has it -- this tool used to paint exactly len(DEMO_COLORS)
            # keys, which was right only while the pad had four.
            keys = read_key_count(reader)
            if keys is None:
                keys = len(DEMO_COLORS)
                print("demo: no PONG within {}s - assuming {} keys."
                      .format(PROBE_TIMEOUT_S, keys))
            # This mode answers "does a press reach the host and light
            # the key". Crossfading a tap into a partial fade is exactly
            # the ambiguity it exists to remove.
            send(fd, "X 0")
            for idx in range(keys):
                send(fd, "C {} {}".format(
                    idx, DEMO_COLORS[idx % len(DEMO_COLORS)]))
                time.sleep(0.25)
            print("demo: {} keys lit. press them — each press turns its "
                  "key white.".format(keys))

        while True:
            ready, _, _ = select.select([fd, sys.stdin], [], [], 0.1)
            if fd in ready:
                for line in reader.poll():
                    print("< {}".format(line))
                    if demo and line.startswith("K "):
                        # A malformed line is exactly what this tool
                        # exists to show; crashing on one would take the
                        # observer down with the thing being observed.
                        # int() is the real test; `isdigit` says yes to
                        # superscripts and other numerals it rejects.
                        parts = line.split()
                        try:
                            idx, state = int(parts[1]), parts[2]
                        except (IndexError, ValueError):
                            print("! malformed: {!r}".format(line))
                            continue
                        color = (DEMO_HELD if state == "1"
                                 else DEMO_COLORS[int(idx) % len(DEMO_COLORS)])
                        send(fd, "C {} {}".format(idx, color))
            if sys.stdin in ready:
                text = sys.stdin.readline()
                if not text:
                    break
                if text.strip():
                    send(fd, text)
    except KeyboardInterrupt:
        pass
    except DeviceGone as err:
        print("\ndevice disconnected: {}".format(err), file=sys.stderr)
        os.close(fd)
        return 1
    except BaseException:
        os.close(fd)
        raise
    close_quietly(fd)
    return 0


def palette(path, brightness=60):
    """Step through candidate status colors at adjustable brightness.

    Also prints what each color becomes *after* the global brightness
    multiply. That number is the thing to watch: NeoPixel brightness
    scales the 8-bit channels, so a dark color at a low brightness lands
    in single digits, where WS2812 mixing is coarse and picks up a color
    cast. `101010` at brightness 30 is `(4,4,4)` — four steps above off.
    """
    fd = open_raw(path)
    reader = LineReader(fd)
    page = 0
    # Comparing candidate colours is this mode's whole job; fading
    # between pages muddies the A/B.
    send(fd, "X 0")

    def show():
        name, entries = PALETTE_PAGES[page % len(PALETTE_PAGES)]
        # Clear first: a shorter page would otherwise leave the previous
        # one's colours sitting on the keys past its end, which reads as
        # part of the comparison rather than as leftovers.
        send(fd, "R")
        send(fd, "B {}".format(brightness))
        print("\n--- {} --- (brightness {}%)".format(name, brightness))
        for idx, (hexcolor, label) in enumerate(entries):
            send(fd, "C {} {}".format(idx, hexcolor))
            raw = int(hexcolor, 16)
            scaled = tuple(int(((raw >> s) & 0xFF) * brightness / 100)
                           for s in (16, 8, 0))
            print("  key {}  #{}  -> {!s:<15} {}".format(
                idx, hexcolor, scaled, label))
        print("[enter] next page   [b N] brightness   [q] quit")

    try:
        show()
        while True:
            ready, _, _ = select.select([fd, sys.stdin], [], [], 0.1)
            if fd in ready:
                for line in reader.poll():
                    print("< {}".format(line))
            if sys.stdin in ready:
                text = sys.stdin.readline()
                if not text or text.strip() == "q":
                    break
                parts = text.split()
                if parts and parts[0] == "b":
                    try:
                        brightness = max(0, min(100, int(parts[1])))
                    except (IndexError, ValueError):
                        # `lstrip("-")` used to let `b --5` through.
                        print("usage: b <0-100>")
                        continue
                else:
                    page += 1
                show()
    except KeyboardInterrupt:
        pass
    except DeviceGone as err:
        print("\ndevice disconnected: {}".format(err), file=sys.stderr)
        os.close(fd)
        return 1
    except BaseException:
        os.close(fd)
        raise
    close_quietly(fd)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="skip probing, use this port")
    parser.add_argument("--probe", action="store_true", help="probe and exit")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true",
                      help="light all keys, mirror presses to white")
    mode.add_argument("--palette", action="store_true",
                      help="step through candidate status colors")
    mode.add_argument("--load", action="store_true",
                      help="every key full white at 100%% — the worst case, "
                           "for metering the pixel rail")
    args = parser.parse_args()

    if args.probe:
        # Honour --probe whether or not --port was given, rather than
        # silently dropping into a console the caller did not ask for.
        if args.port:
            line, why = probe_port(args.port)
            print("{}  {}".format(args.port, line or "no answer ({})".format(why)))
            return 0 if line else 1
        return 0 if do_probe() else 1

    port = args.port or do_probe()
    if port is AMBIGUOUS:
        return 1
    if not port:
        print("\nno data port answered. see README.md bring-up steps.",
              file=sys.stderr)
        return 1

    try:
        if args.palette:
            return palette(port)
        if args.load:
            return load(port)
        return console(port, demo=args.demo)
    except (OSError, termios.error) as err:
        print("cannot open {}: {}\ntry --probe to list ports."
              .format(port, err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
