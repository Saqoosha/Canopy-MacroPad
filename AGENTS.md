# ClaudeMicro — working notes

Device half of the Canopy MacroPad. The macOS half is in the `Canopy`
repo under `Sources/Canopy/MacroPad/`.

`README.md` is the reference and stays that way — protocol, status
colors, bring-up steps, and the bench measurements behind every constant.
Read it before changing anything in `firmware/`. This file only carries
what the README does not.

## Layout

- `firmware/boot.py` — USB config. Runs only on a **hard** reset, which
  is also the only thing that re-enumerates USB. Saving the file is a
  soft reset and does nothing.
- `firmware/code.py` — the whole program. CircuitPython runs it top-level;
  nothing imports it, and CPython idioms (dataclasses, typing, logging,
  pytest) are unavailable or too costly on an RP2040.
- `tools/mpad.py` — host-side bring-up console. Stdlib only, deliberately,
  so it runs on a fresh machine. `--probe` first, always.
- `docs/canopy-macropad-handoff.md` — the original design brief, vendored
  verbatim. Not edited here.

## Editing the firmware

- **The device is dumb on purpose.** It reports key edges and paints what
  it is told. Which pane, which status, when to pulse — all host-side.
  Resist moving policy down here; the split is what keeps the protocol
  portable to BLE.
- **An uncaught exception is indistinguishable from a dead board.**
  CircuitPython drops to the REPL, the data port goes silent, and the
  LEDs freeze at their last value. Every I2C touch in the main loop is
  inside a guard for exactly this reason. Keep it that way.
- **Never touch `time.monotonic()`.** It is a float whose precision
  decays with uptime, and this device lives plugged in for weeks. All
  timing is integer `monotonic_ns`.
- Deploy by copying to `/Volumes/CIRCUITPY/`, then `rm` the `._*`
  AppleDouble files macOS leaves behind.

## Verifying a change

```
python3 -m py_compile firmware/*.py tools/mpad.py
cp firmware/code.py /Volumes/CIRCUITPY/ && rm -f /Volumes/CIRCUITPY/._code.py
tools/mpad.py --probe          # expect: HELLO 2 4 on the data port
tools/mpad.py --demo           # LEDs out, key edges in
```

Tracebacks land on the **console** port, never the data port. Read them
by interrupting the REPL there (`\x03`) and reloading (`\x04`).

Canopy holds the data port whenever it is running. Only one process can
usefully own it — release yours before asking Canopy to connect, and
`lsof` beats `log show` for finding out who has it.
