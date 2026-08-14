"""Run with: python3 pcb/test_bridge.py

Not pytest: this repo's host-side tooling is stdlib only so it runs on a
fresh machine, the same reason tools/mpad.py is.
"""
import sys

from bridge import BridgeError, execute, find_port


def test_port_found():
    port = find_port()
    assert isinstance(port, int), f"expected a port number, got {port!r}"
    print(f"  bridge on port {port}")


def test_execute_returns_result():
    got = execute("return 6 * 7;")
    assert got == 42, f"expected 42, got {got!r}"


def test_bad_code_raises():
    """The half that matters: a failing call must not look like a passing one."""
    try:
        execute("return notDefinedAnywhere.atAll;")
    except BridgeError as e:
        print(f"  raised as it should: {e}")
        return
    raise AssertionError("execute() swallowed an error and returned normally")


if __name__ == "__main__":
    for fn in (test_port_found, test_execute_returns_result, test_bad_code_raises):
        print(fn.__name__)
        fn()
    print("\nall checks passed")
    sys.exit(0)
