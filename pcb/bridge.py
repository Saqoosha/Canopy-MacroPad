"""Client for the EasyEDA Pro bridge.

The bridge is the official easyeda-api skill's Node server; the EasyEDA
side is the run-api-gateway extension. Both scan 49620-49629 and identify
themselves with service == "easyeda-bridge".

If nothing answers, the usual cause is not the port. It is that
run-api-gateway's *Allow interactive with external* box is unticked, in
Extension Manager -> Config -- its manifest does not request the
permission, so the extension opens no socket at all and reports
"Bridge not found" while a healthy bridge answers.
"""
import json
import urllib.error
import urllib.request

PORT_RANGE = range(49620, 49630)
SERVICE = "easyeda-bridge"


class BridgeError(Exception):
    pass


def _get(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def find_port():
    for port in PORT_RANGE:
        try:
            health = _get(f"http://127.0.0.1:{port}/health", 1.0)
        except (urllib.error.URLError, OSError, ValueError):
            continue
        if health.get("service") != SERVICE:
            continue
        if not health.get("edaConnected"):
            raise BridgeError(
                f"bridge is up on {port} but no EasyEDA window is connected. "
                "Tick 'Allow interactive with external' and 'Show at header "
                "menu' in Extension Manager -> Config, then API Gateway -> "
                "Reconnect."
            )
        return port
    raise BridgeError(
        f"no bridge on ports {PORT_RANGE.start}-{PORT_RANGE.stop - 1}. Start it "
        "with: node ~/.claude/skills/easyeda-api/scripts/bridge-server.mjs &"
    )


def execute(js, timeout=60.0):
    """POST JavaScript to the running EasyEDA client and return its result.

    Raises rather than returning a falsy value, because a silent None here
    reads exactly like a successful call that placed nothing.
    """
    port = find_port()
    body = json.dumps({"code": js}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/execute",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
    except (urllib.error.URLError, OSError) as e:
        raise BridgeError(f"transport failed: {e}") from e
    if not payload.get("success"):
        raise BridgeError(payload.get("error", "no error message"))
    return payload.get("result")
