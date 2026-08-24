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
# The I2C half of the read costs a seesaw software reset before USB
# finishes enumerating -- 0.5 s flat, from
# `adafruit_seesaw.Seesaw.sw_reset`'s `post_reset_delay` default, not a
# bench number -- and code.py pays it again on its own init.
# Boot-to-enumeration roughly doubles. Holding one of the two GPIO keys
# skips it outright, which is a side effect of reading them first and
# not the reason for it.
#
# `storage` is imported here rather than at module scope so that nothing
# this feature needs can run before usb_hid.disable() above. A module
# top raise in boot.py skips the whole file, and the default USB config
# it would fall back to has HID enabled -- the single thing this file
# exists to prevent. See AGENTS.md on why usb_midi.disable() was
# declined for the same reason.
try:
    import os
    import storage
    import sys

    import digitalio
    import microcontroller

    # Duplicated from code.py's PROFILES for the same reason 0x30 used to
    # be duplicated below: boot.py cannot import code.py without running
    # the whole program. Deliberately the smallest copy that answers this
    # file's one question -- which pins to read, and whether there is a
    # bus worth probing -- so there is less of it to drift.
    #
    # Failing to resolve a profile raises out of this block, and the
    # handler at the bottom leaves the drive enabled. That is the right
    # direction: a board this file does not recognise is exactly a board
    # someone needs to copy a new code.py to.
    PROFILES = {
        "qtpy": {"gpio_keys": (4, 6), "pad_addresses": (0x30,)},
        "pcb": {"gpio_keys": (3, 4, 6, 20, 5, 24), "pad_addresses": ()},
    }
    BUILD_TO_PROFILE = {
        "adafruit_qtpy_rp2040": "qtpy",
        "raspberry_pi_pico": "pcb",
    }
    profile = PROFILES[
        os.getenv("MPAD_BOARD")
        or BUILD_TO_PROFILE[sys.implementation._build]]

    # The GPIO keys first, because they are nearly free: a handful of pin
    # reads against the seesaw software reset below, which costs 0.5 s
    # flat. A finger on any one of them answers the question without the
    # bus being touched at all -- so a board with no Qwiic cable, or
    # without the library, can still ask for the drive deliberately
    # instead of only getting it by failing. On the PCB there is no bus
    # at all and these reads are the whole gate.
    #
    # GPIO *numbers*, not `board` names, for the reason code.py gives:
    # `board`'s name table is per build and the QT Py's names are absent
    # from the generic build the PCB runs. A number that does not exist
    # raises and the drive is simply always enabled; a number that exists
    # but is wrong reads high through its pull-up, so that key quietly
    # stops opening the drive while the others still do. The second is
    # the one to watch for, because it looks like nothing at all.
    held = False
    switches = []
    for num in profile["gpio_keys"]:
        switch = digitalio.DigitalInOut(
            getattr(microcontroller.pin, "GPIO{}".format(num)))
        switch.switch_to_input(pull=digitalio.Pull.UP)
        switches.append(switch)
    for switch in switches:
        # Pull-up to a switch on ground -- through the breakout's diode on
        # the QT Py, straight to ground on the PCB. Pressed reads low
        # either way.
        held = held or not switch.value
    for switch in switches:
        switch.deinit()

    if not held and profile["pad_addresses"]:
        # Only the first board is probed, so a second board's keys would
        # not work as the gate; an address that does not answer costs a
        # boot delay to learn nothing. If the profile's addresses ever go
        # wrong, this gate throws forever and the drive is simply always
        # enabled, which is the failure direction we want anyway.
        #
        # Reached only when the profile has an address at all, so a board
        # with no I2C keypad never pays the 0.5 s and never fails here
        # about a bus it does not have.
        #
        # Both imports sit here rather than at the top of the block so
        # that a missing library, or a `board` with no STEMMA_I2C on it,
        # costs only the four keys that need them.
        import board

        from adafruit_neokey.neokey1x4 import NeoKey1x4

        i2c = board.STEMMA_I2C()
        held = any(
            NeoKey1x4(i2c, addr=profile["pad_addresses"][0]).get_keys())
        # Tidiness, not necessity: CircuitPython unlocks and deinits the
        # board busses when the boot VM tears down, so code.py opens the
        # bus fine even when a raise above skips this line. Measured,
        # because reading could not settle it -- a gate forced to raise
        # here still left code.py reporting HELLO 3 4. The pin deinits
        # above are the same kind of tidiness, and matter a little more:
        # code.py claims those two pins itself a moment later.
        i2c.deinit()
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
