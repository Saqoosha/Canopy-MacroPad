"""Run with: python3 pcb/test_bridge.py

Not pytest: this repo's host-side tooling is stdlib only so it runs on a
fresh machine, the same reason tools/mpad.py is.
"""
import socket
import sys

import bridge
from bridge import BridgeError, execute, find_port


def test_port_found():
    port = find_port()
    assert isinstance(port, int), f"expected a port number, got {port!r}"
    print(f"  bridge on port {port}")


def test_execute_returns_result():
    got = execute("return 6 * 7;")
    assert got == 42, f"expected 42, got {got!r}"


def test_transport_failure_raises():
    """The bridge not answering at all -- connection refused during the
    POST to /execute itself, not an HTTP error response. Faked by binding
    a real TCP port and releasing it immediately, so it is genuinely dead,
    then patching find_port() to hand that port straight to execute() --
    this isolates the POST /execute transport path from port *discovery*,
    which test_port_found already covers on its own.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    dead_port = s.getsockname()[1]
    s.close()  # released -- nothing listens here now

    original_find_port = bridge.find_port
    bridge.find_port = lambda: dead_port
    try:
        try:
            execute("return 1;")
        except BridgeError as e:
            print(f"  raised as it should (transport branch): {e}")
            assert str(e).startswith("transport failed:"), (
                f"expected the transport-failure branch, got: {e!r}"
            )
            return
        raise AssertionError("execute() swallowed a connection failure")
    finally:
        bridge.find_port = original_find_port


def test_eda_side_error_raises():
    """execute()'s HTTPError-body branch: JavaScript throws inside
    EasyEDA's own runtime. The bridge signals this with a non-2xx status
    (500, or 503 when no window is connected) whose body still carries
    the real message (scripts/bridge-server.mjs:219-227) -- urllib raises
    HTTPError before that body would otherwise be read, so execute() has
    to open it back up rather than report the status line alone.

    Live against the real bridge, not a stub: this needs the actual
    EasyEDA-side error text to come back, to prove the body survived --
    not merely that something raised.
    """
    try:
        execute("return EPCB_LayerId.TOP;")
    except BridgeError as e:
        print(f"  raised as it should (eda-side branch): {e}")
        assert "EPCB_LayerId is not defined" in str(e), (
            f"expected the EasyEDA-side message to survive, got: {e!r}"
        )
        return
    raise AssertionError("execute() swallowed an EasyEDA-side error")


if __name__ == "__main__":
    for fn in (
        test_port_found,
        test_execute_returns_result,
        test_transport_failure_raises,
        test_eda_side_error_raises,
    ):
        print(fn.__name__)
        fn()
    print("\nall checks passed")
    sys.exit(0)
