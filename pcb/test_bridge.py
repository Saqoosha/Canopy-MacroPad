"""Run with: python3 pcb/test_bridge.py

Not pytest: this repo's host-side tooling is stdlib only so it runs on a
fresh machine, the same reason tools/mpad.py is.
"""
import http.server
import json
import sys
import threading

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
    """A bridge-level failure: the live bridge-server.mjs writes a non-2xx
    status on this (see scripts/bridge-server.mjs, the /execute handler's
    catch block), so this reaches BridgeError through urllib.error.HTTPError
    -- the `except (urllib.error.URLError, OSError)` branch in execute().
    """
    try:
        execute("return notDefinedAnywhere.atAll;")
    except BridgeError as e:
        print(f"  raised as it should (transport branch): {e}")
        assert str(e).startswith("transport failed:"), (
            f"expected the transport-failure branch, got: {e!r}"
        )
        return
    raise AssertionError("execute() swallowed an error and returned normally")


def test_eda_side_error_raises():
    """The other half: an HTTP 200 whose body carries `success: false` --
    execute()'s `if not payload.get("success")` branch.

    The live bridge cannot be made to produce this. Its /execute handler
    (scripts/bridge-server.mjs:219-227) writes 200 only on success and a
    non-2xx status on every failure path -- confirmed by reading the
    source and reproduced live: `return EPCB_LayerId.TOP;` against the
    running bridge comes back as HTTP 500 with body
    {"success": false, "error": "EPCB_LayerId is not defined"}, which is
    the transport branch above, not this one.

    So this test stubs a bridge that answers the way execute()'s
    docstring says a bridge is allowed to: 200 with success: false. It
    exercises bridge.py's own handling of that shape, not the live
    server's behavior.
    """

    class _StubHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps(
                    {"service": "easyeda-bridge", "edaConnected": True}
                ).encode()
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps(
                {"success": False, "error": "EPCB_LayerId is not defined"}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    server = http.server.HTTPServer(("127.0.0.1", 0), _StubHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_range = bridge.PORT_RANGE
    bridge.PORT_RANGE = range(port, port + 1)
    try:
        try:
            execute("return EPCB_LayerId.TOP;")
        except BridgeError as e:
            print(f"  raised as it should (eda-side branch): {e}")
            assert str(e) == "EPCB_LayerId is not defined", (
                f"expected the raw eda-side error, got: {e!r}"
            )
            return
        raise AssertionError("execute() swallowed a success: false payload")
    finally:
        bridge.PORT_RANGE = original_range
        server.shutdown()
        thread.join()


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
