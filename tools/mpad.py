#!/usr/bin/env python3
"""Host-side console for the Canopy MacroPad firmware.

Stdlib only, so there is nothing to install before bring-up. Serves two
jobs during Phase 1:

  probe  - work out which of the two /dev/cu.usbmodem* ports is the data
           port, and report the numbers the macOS side needs to match on
  talk   - an interactive line console: type `C 0 ff0000`, watch `K 0 1`

Usage:
    tools/mpad.py                 probe, then open a console on the data port
    tools/mpad.py --probe         probe and exit (prints a report)
    tools/mpad.py --port PATH     skip probing, talk to PATH
    tools/mpad.py --demo          light every key in turn, then mirror
                                  presses to white. Verifies the whole
                                  loop without typing anything.
    tools/mpad.py --palette       paint the candidate status colors side
                                  by side and step global brightness, to
                                  pick values that survive real ambient
                                  light. Prints the post-brightness 8-bit
                                  values, which is where dark colors fall
                                  apart.
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
DEMO_COLORS = ["ff0000", "00ff00", "0040ff", "ff8000"]

# Candidate status colors, four at a time because there are four keys.
# The point of the side-by-side pages is that colors chosen on a screen
# do not survive a WS2812 under desk lighting — cyan next to blue is the
# pair most likely to collapse into "some blue-ish key".
PALETTE_PAGES = [
    ("the four active states", [
        ("0040ff", "running / spawning"),
        ("00c0c0", "background task (cyan A)"),
        ("ff8000", "awaiting approval"),
        ("00ff40", "done, unread"),
    ]),
    ("idle, error, and the rest of the cyans", [
        ("101010", "idle"),
        ("ff0000", "error"),
        ("00a0a0", "cyan B"),
        ("00ffc0", "cyan C"),
    ]),
    ("blue vs cyan, alternating - the hard pair", [
        ("0040ff", "blue"),
        ("00c0c0", "cyan A"),
        ("0040ff", "blue"),
        ("00a0a0", "cyan B"),
    ]),
]


def open_raw(path):
    """Open a CDC-ACM port in raw mode, non-blocking.

    CDC ignores line speed entirely, so no baud rate is set — for a USB
    serial device that setting is decoration.
    """
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    # cfmakeraw equivalent: no echo, no canonical mode, no translation.
    attrs[0] = 0  # iflag
    attrs[1] = 0  # oflag
    attrs[2] = attrs[2] | termios.CS8
    attrs[3] = 0  # lflag
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


class LineReader:
    """Accumulates raw reads and yields complete lines."""

    def __init__(self, fd):
        self.fd = fd
        self.buf = b""

    def poll(self):
        try:
            chunk = os.read(self.fd, 4096)
        except (BlockingIOError, OSError):
            return []
        if not chunk:
            return []
        self.buf += chunk
        lines = []
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            text = line.decode("utf-8", "replace").strip()
            if text:
                lines.append(text)
        return lines


def send(fd, text):
    os.write(fd, (text.rstrip("\n") + "\n").encode())


def probe_port(path):
    """Return the PONG/HELLO line if this port speaks the protocol.

    The console port runs the REPL: it echoes `P` back but never answers
    `PONG`, which is what makes this a reliable discriminator.
    """
    try:
        fd = open_raw(path)
    except OSError as err:
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
    finally:
        os.close(fd)


def usb_identity():
    """VID/PID/product string of any attached CircuitPython board.

    Reported so the macOS side can match on real numbers instead of a
    guessed device path.
    """
    try:
        out = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-w0", "-l"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found, block = [], {}
    for line in out.splitlines():
        for key, label in (
            ('"USB Product Name" = ', "product"),
            ('"USB Vendor Name" = ', "vendor"),
            ('"idVendor" = ', "vid"),
            ('"idProduct" = ', "pid"),
        ):
            if key in line:
                block[label] = line.split(key, 1)[1].strip().strip('"')
        if {"product", "vid", "pid"} <= block.keys():
            if block.get("vid") == "9114":  # 0x239A, Adafruit
                found.append(dict(block))
            block = {}
    return found


def do_probe(verbose=True):
    candidates = sorted(glob.glob(CANDIDATE_GLOB))
    if verbose:
        print("candidate ports: {}".format(candidates or "none"))
        for dev in usb_identity():
            print("usb: product={!r} vid={} (0x{:04x}) pid={} (0x{:04x})".format(
                dev["product"], dev["vid"], int(dev["vid"]),
                dev["pid"], int(dev["pid"])))
    data_port = None
    for path in candidates:
        line, why = probe_port(path)
        if line:
            data_port = path
            if verbose:
                print("  {}  DATA   -> {}".format(path, line))
        elif verbose:
            print("  {}  console/silent ({})".format(path, why))
    return data_port


def console(path, demo=False):
    fd = open_raw(path)
    reader = LineReader(fd)
    print("connected: {}  (Ctrl-D to quit)".format(path))
    send(fd, "P")

    if demo:
        for idx, color in enumerate(DEMO_COLORS):
            send(fd, "C {} {}".format(idx, color))
            time.sleep(0.25)
        print("demo: keys lit. press them — each press turns its key white.")

    try:
        while True:
            ready, _, _ = select.select([fd, sys.stdin], [], [], 0.1)
            if fd in ready:
                for line in reader.poll():
                    print("< {}".format(line))
                    if demo and line.startswith("K "):
                        _, idx, state = line.split()
                        color = "ffffff" if state == "1" else DEMO_COLORS[
                            int(idx) % len(DEMO_COLORS)]
                        send(fd, "C {} {}".format(idx, color))
            if sys.stdin in ready:
                text = sys.stdin.readline()
                if not text:
                    break
                if text.strip():
                    send(fd, text)
    except KeyboardInterrupt:
        pass
    finally:
        send(fd, "R")
        os.close(fd)
        print("\nclosed (sent R)")


def palette(path, brightness=30):
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

    def show():
        name, entries = PALETTE_PAGES[page % len(PALETTE_PAGES)]
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

    show()
    try:
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
                if parts and parts[0] == "b" and len(parts) == 2:
                    brightness = max(0, min(100, int(parts[1])))
                else:
                    page += 1
                show()
    except KeyboardInterrupt:
        pass
    finally:
        send(fd, "R")
        os.close(fd)
        print("\nclosed (sent R)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="skip probing, use this port")
    parser.add_argument("--probe", action="store_true", help="probe and exit")
    parser.add_argument("--demo", action="store_true",
                        help="light all keys, mirror presses to white")
    parser.add_argument("--palette", action="store_true",
                        help="step through candidate status colors")
    args = parser.parse_args()

    port = args.port
    if not port:
        port = do_probe()
        if args.probe:
            return 0 if port else 1
        if not port:
            print("\nno data port answered. see README.md bring-up steps.")
            return 1

    if args.palette:
        palette(port)
    else:
        console(port, demo=args.demo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
