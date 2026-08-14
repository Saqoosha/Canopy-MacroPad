"""Canopy MacroPad — boot-time USB configuration.

Runs once, before code.py, on every hard reset — and only a hard reset,
which is also what re-enumerates USB and so makes a changed CDC layout
visible to the host. Saving this file is not enough: the auto-reload
that follows is a soft reset. Unplug and replug, or `microcontroller.
reset()` from the REPL, which was the path used on the bench.

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
    manufacturer="Saqoosha",
    product="Canopy MacroPad",
)

# CircuitPython keeps CIRCUITPY mounted for the whole session, and
# unplugging the pad is how this device is put away -- so macOS says
# "Disk Not Ejected Properly" every single time, for a volume nobody was
# using. The drive is still wanted for deploys (README bring-up copies
# onto it), so gate it on intent rather than drop it: hold a key through
# a hard reset and CIRCUITPY appears exactly as before.
#
# The safety property is not "every failure is caught" -- it is that
# `disable_usb_drive()` sits on exactly one path, a completed read that
# saw no key held. Every other outcome leaves the drive enabled: an
# exception caught below, one that escapes it, or a read that never
# returns. Stating it that way survives failure modes nobody has thought
# of yet, which an enumerated list does not.
#
# The direction is not arbitrary -- failing the other way would hide the
# one filesystem a broken board is recovered through, at exactly the
# moment the board is broken. The cost of failing this way is that the
# macOS warning comes back, which is the noise this file is trying to
# remove and a perfectly survivable outcome. Proven by injection, not by
# reading: see AGENTS.md for the two faults that were watched to fire.
#
# `storage` is imported here rather than at module scope so that nothing
# this feature needs can run before usb_hid.disable() above. A module
# top raise in boot.py skips the whole file, and the default USB config
# it would fall back to has HID enabled -- the single thing this file
# exists to prevent. See AGENTS.md on why usb_midi.disable() was
# declined for the same reason.
try:
    import storage

    import board
    import digitalio

    # The pin names are duplicated from code.py's KEY_PIN_NAMES, for the
    # same reason 0x30 used to be duplicated here: boot.py cannot import
    # code.py without running the whole program. If the two lists drift
    # apart, a name that does not exist raises and the drive is simply
    # always enabled; a name that exists but is wrong reads high through
    # its pull-up, so that one key quietly stops opening the drive while
    # the rest still do. The second is the one to watch for, because it
    # looks like nothing at all.
    held = False
    switches = []
    for name in ("MOSI", "MISO", "SCK", "TX", "RX", "SDA"):
        switch = digitalio.DigitalInOut(getattr(board, name))
        switch.switch_to_input(pull=digitalio.Pull.UP)
        switches.append(switch)
    for switch in switches:
        # Pull-up plus a diode to ground: pressed reads low.
        held = held or not switch.value
    for switch in switches:
        # Tidiness, not necessity: CircuitPython unlocks and deinits the
        # board busses when the boot VM tears down, so code.py claims
        # these same pins fine a moment later either way. Measured,
        # because reading could not settle it -- a gate forced to raise
        # here still left code.py reporting HELLO 3 6.
        switch.deinit()

    if held:
        print("usb drive: enabled (key held at boot)")
    else:
        # Print before disabling. The other order has a state where the
        # only record is inverted: the drive goes away, the print then
        # fails, and the handler below writes "enabled" about a board
        # whose drive is off.
        print("usb drive: disabled; hold a key while plugging in for CIRCUITPY")
        storage.disable_usb_drive()
except Exception as err:  # noqa: BLE001 - see above; any fault keeps the drive
    print("usb drive: enabled (gate failed: {}: {})".format(
        type(err).__name__, err))
