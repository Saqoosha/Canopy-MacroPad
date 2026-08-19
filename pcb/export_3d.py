"""Export the live EasyEDA PCB's 3D model, with component models.

This is the board as EasyEDA's own 3D preview draws it -- real package
shapes, not the envelopes ``case/mock.py`` builds for its booleans. The
case viewer loads the result so a fit can be looked at as well as
measured.

    python3 export_3d.py

Two things make this different from ``export_manufacturing.py``, and both
are the reason it does not just reuse ``fetch()``:

**The bridge's request timeout is a hard 30 s** (``REQUEST_TIMEOUT_MS`` in
``bridge-server.mjs``), and a 3D export of this board takes longer. So the
export is *started* in one call that returns immediately, parked on
``globalThis``, and polled by later calls. A single blocking call fails
with a bridge timeout while EasyEDA is still working perfectly -- the same
shape of false failure ``pcb_Drc.check()`` produces.

**The payload is megabytes.** base64 of a whole board's mesh does not
belong in one JSON response, so the finished bytes are handed back in
slices and reassembled here, with the total length checked against the
size EasyEDA reported.
"""

import base64
import json
import os
import sys
import time

import build
from bridge import execute


OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "3d")

# 'Component Model' is the whole point. The other three are what make the
# result read like the EasyEDA preview rather than a bare slab.
ELEMENTS = ["Component Model", "Via", "Silkscreen", "Wire In Signal Layer"]

# 'Outfit' is the assembly -- one solid with everything in place. 'Parts'
# splits it and is the wrong shape for dropping into a viewer.
MODEL_MODE = "Outfit"

# Components with no bound 3D model get one generated from their height
# property. Without this the hot-swap sockets and several passives simply
# do not appear, which reads as a board that is missing parts.
AUTO_GENERATE = True

SLICE = 4_000_000       # base64 characters per response
POLL_SECONDS = 3
POLL_LIMIT = 200        # 10 minutes


def start(file_type):
    """Kick the export off and return at once."""
    js = f"""
    globalThis.__c3d = {{ state: "running" }};
    eda.pcb_ManufactureData.get3DFile(
        "canopy_macropad_3d",
        "{file_type}",
        {json.dumps(ELEMENTS)},
        {json.dumps(MODEL_MODE)},
        {json.dumps(AUTO_GENERATE)}
    ).then(async (f) => {{
        if (!f) {{
            globalThis.__c3d = {{ state: "error", error: "get3DFile returned undefined" }};
            return;
        }}
        const bytes = new Uint8Array(await f.arrayBuffer());
        let bin = "";
        const chunk = 0x8000;
        for (let i = 0; i < bytes.length; i += chunk)
            bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
        globalThis.__c3d = {{
            state: "done", name: f.name || "", type: f.type || "",
            size: bytes.length, b64: btoa(bin),
        }};
    }}).catch((e) => {{
        globalThis.__c3d = {{ state: "error", error: String(e && e.message || e) }};
    }});
    return {{ started: true }};
    """
    execute(js, 25)


def poll():
    """State only. The bytes are deliberately not in this response."""
    return execute("""
    const s = globalThis.__c3d;
    if (!s) return { state: "missing" };
    return { state: s.state, error: s.error || "", size: s.size || 0,
             name: s.name || "", type: s.type || "",
             chars: s.b64 ? s.b64.length : 0 };
    """, 25)


def collect(chars):
    """Pull the parked base64 back in slices and rebuild it here."""
    parts = []
    for begin in range(0, chars, SLICE):
        got = execute(
            f"return {{ s: globalThis.__c3d.b64.slice({begin}, {begin + SLICE}) }};",
            120,
        )
        parts.append(got["s"])
        print(f"  {min(begin + SLICE, chars):>10,} / {chars:,} chars")
    joined = "".join(parts)
    if len(joined) != chars:
        raise SystemExit(f"slice reassembly lost data: {len(joined)} != {chars}")
    return base64.b64decode(joined)


def release():
    execute('globalThis.__c3d = undefined; return {cleared:true};', 25)


def export(file_type):
    print(f"starting {file_type} export ({MODEL_MODE}, "
          f"autoGenerateModels={AUTO_GENERATE})")
    start(file_type)

    for attempt in range(POLL_LIMIT):
        time.sleep(POLL_SECONDS)
        state = poll()
        if state["state"] == "done":
            break
        if state["state"] in ("error", "missing"):
            raise SystemExit(f"{file_type} export failed: {state.get('error') or state['state']}")
        print(f"  waiting… {(attempt + 1) * POLL_SECONDS}s")
    else:
        raise SystemExit(f"{file_type} export still running after "
                         f"{POLL_LIMIT * POLL_SECONDS}s")

    print(f"  EasyEDA finished: name={state['name']!r} size={state['size']:,} bytes")
    data = collect(state["chars"])
    if len(data) != state["size"]:
        raise SystemExit(f"size mismatch: EasyEDA said {state['size']}, got {len(data)}")
    release()

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"canopy_macropad_3d.{file_type}")
    with open(path, "wb") as handle:
        handle.write(data)
    print(f"wrote {path} ({len(data):,} bytes)")
    return path


def main():
    build.open_project_pcb()
    types = sys.argv[1:] or ["obj"]
    for file_type in types:
        if file_type not in ("obj", "step"):
            raise SystemExit(f"unknown file type {file_type!r}; use obj and/or step")
        export(file_type)


if __name__ == "__main__":
    main()
