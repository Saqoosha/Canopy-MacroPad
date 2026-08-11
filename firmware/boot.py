"""Canopy MacroPad — boot-time USB configuration.

Runs once, before code.py, on every hard reset — and only a hard reset,
which is also what re-enumerates USB and so makes a changed CDC layout
visible to the host. Saving this file is not enough: the auto-reload
that follows is a soft reset. Unplug and replug, or `microcontroller.
reset()` from the REPL, which was the path used on the bench.

The whole point of this file: the device must NOT be a keyboard.
See README.md "Why not HID".
"""

import storage
import usb_cdc
import usb_hid

import supervisor

# Do not enumerate any HID interface. Keystrokes can never leak into
# whatever app happens to be focused, and macOS never asks for the
# Input Monitoring TCC permission.
usb_hid.disable()

# Two CDC interfaces:
#   console -> the CircuitPython REPL, for humans and tracebacks
#   data    -> the Canopy <-> device protocol, machine only
usb_cdc.enable(console=True, data=True)

# The host matches on this product string (plus VID/PID) instead of a
# hardcoded /dev/cu.* path, which changes across ports and reboots.
supervisor.set_usb_identification(
    manufacturer="Saqoosha",
    product="Canopy MacroPad",
)

# CIRCUITPY stays mounted for the whole session, and unplugging the pad
# is how this device is put away -- so macOS says "Disk Not Ejected
# Properly" every single time, for a volume nobody was using. The drive
# is still wanted for deploys (README bring-up copies onto it), so gate
# it on intent rather than drop it: hold any key on the keypad while
# plugging in and CIRCUITPY appears exactly as before.
#
# Everything below sits after the serial half is already configured, and
# inside one guard whose every failure path leaves the drive *enabled* --
# a missing Qwiic cable, a missing lib, a seesaw not yet answering. This
# direction is not arbitrary: failing the other way would hide the one
# filesystem a broken board is recovered through, at exactly the moment
# the board is broken. The cost of failing this way is the macOS warning
# comes back, which is the noise this file is trying to remove and a
# perfectly survivable outcome.
#
# The key read costs a seesaw software reset (~0.5 s) before USB
# finishes enumerating, and code.py pays it again on its own init.
try:
    import board
    from adafruit_neokey.neokey1x4 import NeoKey1x4

    # 0x30 is the first entry of code.py's PAD_ADDRESSES -- duplicated
    # here because boot.py cannot import code.py without running the
    # whole program. Only the first board is probed: a second one is
    # hypothetical, and an address that does not answer costs a boot
    # delay to learn nothing.
    i2c = board.STEMMA_I2C()
    held = any(NeoKey1x4(i2c, addr=0x30).get_keys())
    i2c.deinit()
    if held:
        print("usb drive: enabled (key held at boot)")
    else:
        storage.disable_usb_drive()
        print("usb drive: disabled; hold a key while plugging in for CIRCUITPY")
except Exception as err:  # noqa: BLE001 - see above; any fault keeps the drive
    print("usb drive: enabled (gate failed: {}: {})".format(
        type(err).__name__, err))
