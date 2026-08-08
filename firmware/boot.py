"""Canopy MacroPad — boot-time USB configuration.

Runs once, before code.py, on every hard reset. Changes here need a
physical USB unplug/replug to take effect; the RESET button alone does
not always re-enumerate.

The whole point of this file: the device must NOT be a keyboard.
See README.md "Why not HID".
"""

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
    manufacturer="Whatever",
    product="Canopy MacroPad",
)
