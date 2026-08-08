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
- **Patching this file with a script? Assert every substitution.** A
  bare `str.replace()` that misses returns the string unchanged, so the
  edit silently does nothing and the next command reports success on
  code that was never modified. This bit three times in one session,
  once producing a "test passed" for a fault that had never been
  injected. `assert old in s` before every replace.

## Verifying a change

```
python3 -m py_compile firmware/*.py tools/mpad.py
cp firmware/code.py /Volumes/CIRCUITPY/ && rm -f /Volumes/CIRCUITPY/._code.py
tools/mpad.py --probe          # expect: PONG 3 4 on the data port
tools/mpad.py --demo           # LEDs out, key edges in
```

Known-good answers, for telling a healthy board from a sick one:

| State | The device says |
|---|---|
| healthy | `HELLO 3 4` on connect, `PONG 3 4` to `P` |
| keypad or `lib/` missing | `HELLO 3 0` + `ERR i2c setup ...`, connection held |
| bus lost while running | `HELLO 3 4` + `ERR i2c lost at runtime: ...` |
| firmware died past 60 s uptime | `ERR fatal ...`, all keys red, port drops, fresh `HELLO` |
| firmware died inside 60 s | `ERR fatal-halted ...` on every later connect, stays red |

USB identity: VID `0x239A`, PID `0x80F8`, product `Canopy MacroPad`,
manufacturer `Saqoosha`. Two ports enumerate; **never pick by trailing
number** — only `P` → `PONG` identifies the data port, because the
console echoes `P` as REPL input and never answers.

Tracebacks land on the **console** port, never the data port. Read them
by interrupting the REPL there (`\x03`) and reloading (`\x04`).

Canopy holds the data port whenever it is running. Only one process can
usefully own it — release yours before asking Canopy to connect, and
`lsof` beats `log show` for finding out who has it. Flashing while it is
held works (the copy is mass storage, not serial), but the soft reset
that follows drops Canopy's connection.

## Error paths are only real once you have broken them

Every hardening path in this firmware was wrong the first time, and none
of the mistakes were visible by reading. The method that found them:
copy `firmware/code.py`, inject a `raise` where the fault belongs, flash
the copy, watch, restore. Three separate guards were proven this way —
the fatal handler (both sides of its 60 s brake), the setup guard (by
`mv`-ing `lib/adafruit_neokey` aside), and the runtime I2C latch.

Two of those tests failed *as tests* before they failed as code: one
patched nothing because a `replace()` missed, and one landed on the
boundary of its own fault window. **A passing error-path test that was
never actually triggered is the default outcome, not the exception.**
Make the injected fault prove itself — print from inside it, or assert
the symptom appears — before believing a clean run.

For a receive-path change, the decisive check is a burst larger than
`MAX_LINE_BYTES` ending in `P`: if the buffer bound is wrong, the `P`
is eaten with it and no `PONG` comes back. 441 and 881 bytes both work.

## Diagnostics that were deliberately not added

Reviewers keep proposing the same six, and they were declined on the
same grounds each time: each buys a rare diagnosis by making the device
say more all the time, and this pad works because it says very little —
the same reasoning that keeps exactly one status pulsing.

- `ERR i2c lost` / `ERR i2c ok` mid-session — a one-second cable wobble
  would announce the keypad as gone when it is not. (The *stale* half of
  this was a real bug and is fixed: `i2c_error` is live, so a reconnect
  after a bus loss reports the truth.)
- `ERR argc <cmd>` split from `ERR unknown <cmd>` — hosts read any
  `ERR unknown` as "verb unsupported"; a new code changes what they parse.
- `ERR line-too-long` on the receive bound — every pre-`HELLO` overrun
  would draw an error the host is told to ignore.
- A reset counter in `microcontroller.nvm` to brake a slow reset loop —
  wears NVM on every fault, and Canopy already detects `HELLO` storms.
- Placeholder pads to keep key indices aligned when one of two boards
  fails — changes what `HELLO`'s key count means, and no host implements
  the distinction.
- `usb_midi.disable()` in `boot.py` — builds without the module raise
  `AttributeError` there and break USB entirely, to defend against an
  interface the measured descriptor already lacks.

If one of these is proposed again, the question to answer first is what
state the new behaviour would be *wrong* in. Every one of them has one.
