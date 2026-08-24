# Custom PCB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the NeoKey 1x4, two 4978 breakouts and the QT Py RP2040 with one custom 121.60 x 21.59 PCB, assembled by JLCPCB, without changing the protocol or the macOS half.

**Architecture:** A Python package `pcb/` owns the key field's numbers and builds the board by POSTing JavaScript to the EasyEDA bridge, asserting every placement by reading it back. `case/params.py` stops deriving the key field from Adafruit board dimensions and imports it from `pcb/params.py` instead, so one pitch constant governs both the copper and the plastic. The firmware's two key sources collapse to one GPIO source.

**Tech Stack:** EasyEDA Pro V3.2 + `run-api-gateway.eext` + the official `easyeda-api` skill bridge (Node, ports 49620-49629); Python 3 stdlib for `pcb/`; build123d in `case/.venv` (Python 3.12); CircuitPython 10.x on RP2040.

**Spec:** `docs/superpowers/specs/2026-08-14-custom-pcb-design.md`

## Global Constraints

- **Switch pitch is 19.05 everywhere.** Choc v2 takes MX keycaps, so MX spacing is mandatory; Choc's own 18 x 17 would collide the caps.
- **PCB coordinates are 1 mil.** 19.05 mm = **750** units exactly. Schematic coordinates are 0.01 inch. Mixing them misplaces parts 10x.
- **Enums are not in the bridge execution context.** `EPCB_LayerId.TOP` throws; use the documented literal `1`. Look every other value up in `~/.claude/skills/easyeda-api/references/enums/` — never guess a number.
- **`pcb_PrimitiveComponent.create` takes a device, not a footprint.** Passing a footprint item fails with a destructuring error naming a property the item visibly has.
- **`dmt_Project.createProject()` is beta and returns `undefined` silently.** Open an existing project.
- **Every placement is asserted by reading it back**, and **every assertion is watched failing before it is believed.** A check nobody has seen go red is not coverage.
- **`build.py` must end in `all checks passed` before anything is printed.** There is one switch and no axis: MX and Choc hot-swap holes cannot share a position, so this board is Choc v2 only.
- **Never guess an EasyEDA API signature.** Read `~/.claude/skills/easyeda-api/references/classes/<Class>.md` first.
- Python in `pcb/` is **stdlib only**, like `tools/mpad.py`, so it runs on a fresh machine and can be imported from `case/.venv` without installing anything there.

---

## File Structure

| File | Responsibility |
|---|---|
| `pcb/params.py` | **Owner of the key field.** Pitch, switch centres, LED offsets, board outline, part numbers. Stdlib only, no imports from the repo. |
| `pcb/bridge.py` | Thin client for the EasyEDA bridge: port discovery, `execute(js)`, raises on `success: false`. |
| `pcb/probe.py` | Read-back assertions. Given expected placements, fetches actual ones and reports per-item deltas. |
| `pcb/build.py` | Entry point: opens the project, clears, places the key field, asserts, reports. |
| `pcb/README.md` | The bridge setup, the permission checkbox, the three API traps, how to re-run. |
| `case/params.py` | Modified: imports the key field from `pcb/params.py`; loses `MPAD_LAYOUT` and the QT Py block; the switch numbers become constants, not an axis. |
| `case/parts.py` | Modified: QT Py pocket, rails, lip, STEMMA notch, wire lane and cable bay deleted. |
| `case/mock.py` | Modified: one board stand-in replaces NeoKey + 2 breakouts + QT Py. |
| `firmware/code.py` | Modified: one GPIO key source; I2C, seesaw and `PAD_ADDRESSES` deleted. |
| `firmware/boot.py` | Modified: drive gate reads six GPIO, no I2C path. |

---

## Task 1: The bridge client, and proof it reports failure

**Files:**
- Create: `pcb/bridge.py`
- Create: `pcb/test_bridge.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `find_port() -> int`, `execute(js: str, timeout: float = 60.0) -> Any` (returns the `result` field, raises `BridgeError` on transport failure or `success: false`), `BridgeError(Exception)`.

- [ ] **Step 1: Write the failing test**

```python
# pcb/test_bridge.py
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
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pcb && python3 test_bridge.py
```

Expected: `ModuleNotFoundError: No module named 'bridge'`

- [ ] **Step 3: Write the implementation**

```python
# pcb/bridge.py
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
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd pcb && python3 test_bridge.py
```

Expected: three names printed, then `all checks passed`.

- [ ] **Step 5: Prove `find_port` reports a disconnected EDA**

Quit EasyEDA Pro, leaving the bridge server running, then:

```bash
cd pcb && python3 test_bridge.py
```

Expected: `BridgeError: bridge is up on 49620 but no EasyEDA window is connected...`

Reopen EasyEDA Pro and confirm the test passes again. **Both runs are required**: the error path is worthless without the run where it has to fire.

- [ ] **Step 6: Commit**

```bash
git add pcb/bridge.py pcb/test_bridge.py
git commit -m "Give the board builder a client that cannot fail quietly"
```

---

## Task 2: The key field's numbers, owned by the PCB

**Files:**
- Create: `pcb/params.py`
- Create: `pcb/test_params.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SWITCH_PITCH = 19.05`, `KEY_COUNT = 6`, `FIRST_SWITCH_X = 9.525`, `SWITCH_Y = 10.795`, `switch_centres_mm() -> list[tuple[float, float]]`, `KEY_FIELD_W`, `KEY_FIELD_D`, `BOARD_W`, `BOARD_D`, `mm_to_mil(v: float) -> int`, and the LCSC part identifiers.

- [ ] **Step 1: Write the failing test**

```python
# pcb/test_params.py
"""Run with: python3 pcb/test_params.py"""
import sys

import params


def test_six_switches_on_pitch():
    centres = params.switch_centres_mm()
    assert len(centres) == params.KEY_COUNT, f"got {len(centres)} centres"
    xs = [x for x, _ in centres]
    gaps = [round(b - a, 6) for a, b in zip(xs, xs[1:])]
    assert gaps == [params.SWITCH_PITCH] * 5, f"gaps were {gaps}"


def test_pitch_is_a_whole_number_of_mils():
    """19.05 mm is 0.75 inch, so it must be exactly 750 with no rounding.

    If this ever fails, every placement is off by a fraction of a mil and
    nothing downstream will say so.
    """
    assert params.mm_to_mil(params.SWITCH_PITCH) == 750


def test_board_is_the_field_plus_the_usb_tab():
    assert params.KEY_FIELD_W == 114.30
    assert round(params.BOARD_W - params.KEY_FIELD_W, 6) == params.USB_TAB_W


if __name__ == "__main__":
    for fn in (
        test_six_switches_on_pitch,
        test_pitch_is_a_whole_number_of_mils,
        test_board_is_the_field_plus_the_usb_tab,
    ):
        print(fn.__name__)
        fn()
    print("\nall checks passed")
    sys.exit(0)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd pcb && python3 test_params.py
```

Expected: `ModuleNotFoundError: No module named 'params'`

- [ ] **Step 3: Write the implementation**

```python
# pcb/params.py
"""The key field's numbers, and the only place they are written.

This file used to be case/params.py's job, derived from the NeoKey and the
4978 breakout. The boards are gone and the copper is ours now, so the PCB
owns the field and the case imports it. Changing the pitch here moves the
sockets, the pixels and the plate holes together, which is the whole point
of the inversion.

Stdlib only, deliberately: case/.venv must be able to import it without
installing anything, and so must a fresh machine.
"""

# --- units -----------------------------------------------------------------
# EasyEDA's PCB editor works in 1 mil. 1 mm = 1/0.0254 mil.
MIL_PER_MM = 1.0 / 0.0254


def mm_to_mil(v):
    """Millimetres to whole mils.

    Rounds, and every number this design uses is exact at 1 mil: 19.05 is
    0.75 inch (750), 9.525 is 375, 10.795 is 425.
    """
    return round(v * MIL_PER_MM)


# --- the key field ---------------------------------------------------------
# Pitch and depth are inherited from the NeoKey 1x4 the pad was built on, so
# every keycap and every printed plate hole that already works still does.
SWITCH_PITCH = 19.05
KEY_COUNT = 6
FIRST_SWITCH_X = 9.525          # half a pitch in from the field's left edge
SWITCH_Y = 10.795               # NeoKey 4980's switch centre, read off its .brd

KEY_FIELD_W = KEY_COUNT * SWITCH_PITCH      # 114.30
KEY_FIELD_D = 21.59                         # the NeoKey's depth, kept


def switch_centres_mm():
    """Board-local switch centres, left to right, key 0 first."""
    return [(FIRST_SWITCH_X + n * SWITCH_PITCH, SWITCH_Y) for n in range(KEY_COUNT)]


# --- the board -------------------------------------------------------------
# The USB-C receptacle is the one part that does not fit under the plate, so
# it gets a tab off the right end rather than growing the whole outline.
USB_TAB_W = 7.30
BOARD_W = KEY_FIELD_W + USB_TAB_W           # 121.60
BOARD_D = KEY_FIELD_D                       # 21.59
BOARD_T = 1.60
BOARD_LAYERS = 4

# --- parts -----------------------------------------------------------------
# EasyEDA library identifiers, found with lib_Device.search() and confirmed by
# placing them. The library UUID is the local system library.
LIB_UUID = "0819f05c4eef4c71ace90d822a990e87"
DEV_MX_SOCKET = "96b68765c94c47e5851d5c1124075178"   # Kailh CPG151101S11

# LCSC numbers for the BOM, from the spec.
LCSC_RP2040 = "C2040"
LCSC_PIXEL = "C5149201"          # SK6812MINI-E, reverse mount
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd pcb && python3 test_params.py
```

Expected: three names printed, then `all checks passed`.

- [ ] **Step 5: Watch the pitch check fail**

Temporarily set `SWITCH_PITCH = 19.00`, run `python3 test_params.py`, and confirm `test_pitch_is_a_whole_number_of_mils` fails (19.00 mm is 748 mil, not 750). Restore 19.05 with the reverse edit — **not** `git checkout`, which would discard anything else uncommitted in the file.

- [ ] **Step 6: Commit**

```bash
git add pcb/params.py pcb/test_params.py
git commit -m "Move the key field's numbers to the thing that now defines them"
```

---

## Task 3: Place the key field, and measure what was placed

**Files:**
- Create: `pcb/probe.py`
- Create: `pcb/build.py`
- Test: `pcb/build.py` is its own test — it asserts and prints `all checks passed`, the same contract `case/build.py` has.

**Interfaces:**
- Consumes: `bridge.execute`, `params.switch_centres_mm`, `params.mm_to_mil`, `params.LIB_UUID`, `params.DEV_MX_SOCKET`.
- Produces: `probe.placed_components() -> list[dict]` with keys `id`, `x`, `y` in mil; `probe.assert_pitch(placed, want_mil, label)`.

- [ ] **Step 1: Write the probe**

```python
# pcb/probe.py
"""Read placements back out of EasyEDA and measure them.

The read-back is the point. Placing is easy and EasyEDA reports success for
it either way; what this repository trusts is a number fetched from the
document afterwards.
"""
from bridge import execute


def placed_components():
    """Every component on the open PCB, in mil, sorted left to right."""
    js = (
        "const all = await eda.pcb_PrimitiveComponent.getAll(); "
        "return (all || []).map(c => ({id: c.primitiveId, x: c.x, y: c.y}));"
    )
    got = execute(js) or []
    return sorted(got, key=lambda c: c["x"])


def clear_components():
    js = (
        "const all = await eda.pcb_PrimitiveComponent.getAll(); "
        "if (all && all.length) { await eda.pcb_PrimitiveComponent.delete("
        "all.map(c => c.primitiveId)); } "
        "const left = await eda.pcb_PrimitiveComponent.getAll(); "
        "return (left || []).length;"
    )
    left = execute(js)
    if left:
        raise AssertionError(f"clear left {left} components behind")


def assert_pitch(placed, want_mil, label):
    """Every neighbouring gap must be exactly want_mil."""
    xs = [c["x"] for c in placed]
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    bad = [(i, g) for i, g in enumerate(gaps) if g != want_mil]
    if bad:
        detail = ", ".join(f"gap {i}: {g} (wanted {want_mil})" for i, g in bad)
        raise AssertionError(f"{label}: {detail}")
    print(f"  [ok ] {label}: {len(gaps)} gaps, all {want_mil} mil")
```

- [ ] **Step 2: Write the builder**

```python
# pcb/build.py
"""Build the key field and prove it landed where it was told to.

Run with: python3 pcb/build.py [--inject]

--inject places the last socket half a pitch out. It exists so the check can
be watched going red; a run that has only ever been green is not evidence.
"""
import os
import sys

import params
import probe
from bridge import execute

# The project is opened by name and never created. dmt_Project.createProject()
# returns undefined under every argument shape tried -- six of them, no
# exception raised, no project appearing -- and the sibling
# dmt_Folder.getAllFoldersUuid() throws on a missing internal `rootList`. The
# folder subsystem simply is not populated in this client's local, half-offline
# mode, and creation rides on it. So the project is made by hand in the GUI
# once, and this constant names whichever one that is.
PROJECT_NAME = os.environ.get("MPAD_EDA_PROJECT", "Canopy MacroPad")
TOP = 1          # EPCB_LayerId.TOP; the enum object is absent from the bridge
                 # execution context, so the documented literal is what works.


def open_project_pcb():
    """Open the project's first PCB and leave it active.

    dmt_Project.createProject() is beta and returns undefined without
    explaining itself, so the project is made by hand once and opened here.
    """
    js = (
        "const teams = await eda.dmt_Team.getAllTeamsInfo(); "
        "for (const t of teams || []) { "
        "const us = await eda.dmt_Project.getAllProjectsUuid(t.uuid); "
        "for (const u of us || []) { "
        "const i = await eda.dmt_Project.getProjectInfo(u); "
        "const n = (i && (i.friendlyName || i.name)) || ''; "
        f"if (n === {PROJECT_NAME!r}) {{ "
        "await eda.dmt_Project.openProject(u); "
        "const pcbs = await eda.dmt_Pcb.getAllPcbsInfo(); "
        "if (!pcbs || !pcbs.length) return {error: 'project has no PCB'}; "
        "await eda.dmt_EditorControl.openDocument(pcbs[0].uuid); "
        "const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo(); "
        "return {opened: n, pcb: pcbs[0].name, documentType: doc.documentType}; "
        "} } } "
        "return {error: 'project not found'};"
    ).replace("'", '"')
    got = execute(js)
    if got.get("error"):
        raise SystemExit(f"cannot open the board: {got['error']}")
    if got["documentType"] != 3:
        raise SystemExit(f"active document is type {got['documentType']}, not PCB")
    print(f"opened {got['opened']} / {got['pcb']}")


def place_sockets(inject=False):
    xs = [params.mm_to_mil(x) for x, _ in params.switch_centres_mm()]
    y = params.mm_to_mil(params.SWITCH_Y)
    if inject:
        xs[-1] -= params.mm_to_mil(params.SWITCH_PITCH) // 2
        print(f"INJECTED: last socket moved to {xs[-1]}, the check must FAIL")
    for x in xs:
        js = (
            f'const dev = {{libraryUuid: "{params.LIB_UUID}", '
            f'uuid: "{params.DEV_MX_SOCKET}"}}; '
            f"const c = await eda.pcb_PrimitiveComponent.create("
            f"dev, {TOP}, {x}, {y}, 0, false); "
            "return c ? c.primitiveId : null;"
        )
        if not execute(js):
            raise AssertionError(f"create returned nothing for x={x}")
    return xs


def main():
    inject = "--inject" in sys.argv
    open_project_pcb()
    probe.clear_components()
    asked = place_sockets(inject)
    placed = probe.placed_components()

    if len(placed) != params.KEY_COUNT:
        raise AssertionError(f"placed {len(placed)}, wanted {params.KEY_COUNT}")
    print(f"  [ok ] count: {len(placed)}")

    got_xs = [c["x"] for c in placed]
    if got_xs != sorted(asked):
        raise AssertionError(f"read back {got_xs}, asked for {sorted(asked)}")
    print(f"  [ok ] positions: {got_xs}")

    probe.assert_pitch(placed, params.mm_to_mil(params.SWITCH_PITCH), "socket pitch")
    print("\nall checks passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the injected build first**

```bash
cd pcb && python3 build.py --inject
```

Expected: `INJECTED: ...`, then `AssertionError: socket pitch: gap 4: 375 (wanted 750)`.

**If this passes, stop.** A green injected run means the assertion is not measuring what it claims to.

- [ ] **Step 4: Run the clean build**

```bash
cd pcb && python3 build.py
```

Expected:

```
opened Canopy MacroPad / PCB1
  [ok ] count: 6
  [ok ] positions: [375, 1125, 1875, 2625, 3375, 4125]
  [ok ] socket pitch: 5 gaps, all 750 mil

all checks passed
```

- [ ] **Step 5: Look at the board**

Open the PCB tab in EasyEDA and confirm six sockets in an even row. The numbers agreeing is necessary and is not sufficient — four rendering bugs in this repository's viewer raised no error and were found by looking.

- [ ] **Step 6: Commit**

```bash
git add pcb/probe.py pcb/build.py
git commit -m "Place six sockets from one pitch, and read all five gaps back"
```

---

## Task 4: Settle the LED aperture on real switches

**Files:**
- Modify: `docs/superpowers/specs/2026-08-14-custom-pcb-design.md` (the LED bullet under "Open, deliberately")
- Modify: `pcb/params.py` (add `PIXEL_OFFSET_MM`)

**Interfaces:**
- Consumes: `params.SWITCH_Y`.
- Produces: `params.PIXEL_OFFSET_MM: tuple[float, float]` — the pixel's centre relative to its switch centre — and `params.PIXEL_HOLE_DIA`.

This task is a **measurement, not code**. It cannot be done by reading, and the three switches disagree, so it gates the board.

- [ ] **Step 1: Collect the three switches and a lit reference**

A Durock Ice King, an Outemu GTMX, and a Choc v2 if one has arrived. Power the existing six-key pad so its NeoKey pixels are lit at `B 100` white — that is the worst case and the condition the status colours were tuned under.

- [ ] **Step 2: Look up through each switch**

Turn each switch upside down and find the opening in its underside. Record, for each: whether an opening exists, roughly where it sits relative to the switch centre, and roughly how big it is. The drawings say 3535 for full MX, **2835 for GTMX**, and a placed LED position for Choc v2 — this step is checking those against the parts.

- [ ] **Step 3: Hold each switch over a lit pixel**

The question is not whether the package fits the window — a reverse-mount pixel sits under the board and only its light goes through. The question is **whether one hole position serves all three housings.** Note any switch where the light is blocked or lands off-centre.

- [ ] **Step 4: Record the answer in the spec**

Replace the "The LED's aperture, not its package" bullet with what was seen. If one position serves all three, say so and give it. If it does not, say which switch is favoured and what the others cost.

- [ ] **Step 5: Write the numbers into `pcb/params.py`**

```python
# --- the pixel -------------------------------------------------------------
# Reverse-mount pixel under the board, shining up through an opening into the
# switch's own window. Every number here is cloned from Adafruit's NeoKey 1x4
# board file rather than chosen -- see pcb/NOTICE.md -- because that board
# lights these exact switches today and Saqoosha has confirmed the fit on the
# part.
#
# The opening is a RECTANGLE, not a round hole. That was the first thing a
# guess got wrong here: Eagle layer 46 is milling, and NEO3535_REVERSE draws
# a rectangle there spanning x -1.927..1.927 and y -1.727..1.727.
PIXEL_OFFSET_MM = (0.0, -5.08)      # switch y 10.795 -> pixel y 5.715
PIXEL_OPENING_MM = (3.854, 3.454)   # milled slot, from Eagle layer 46
PIXEL_PADS = [                      # bottom side, 1.2 x 0.9 each
    ((2.65, -0.75), (1.2, 0.9)),
    ((2.65, 0.75), (1.2, 0.9)),
    ((-2.65, -0.75), (1.2, 0.9)),
    ((-2.65, 0.75), (1.2, 0.9)),
]
```

**Do not copy the x nudge.** Two of the NeoKey's four pixels sit 0.127 off
their switch's x (LED4 at 9.652 against SW1's 9.525, LED2 at 47.752 against
SW3's 47.625) while the other two are dead on. That is the chain's routing,
not a dimension, and carrying it in would import someone else's trace layout
as geometry. All six pixels here share their switch's x exactly.

- [ ] **Step 6: Commit**

```bash
git add pcb/params.py docs/superpowers/specs/2026-08-14-custom-pcb-design.md
git commit -m "Settle the pixel's hole by looking through the switches"
```

---

## Task 5: Case — one switch axis, and the field imported rather than derived

**Files:**
- Modify: `case/params.py`
- Modify: `case/parts.py`
- Modify: `case/mock.py`
- Modify: `case/build.py`

**Interfaces:**
- Consumes: `pcb/params.py`'s `SWITCH_PITCH`, `switch_centres_mm`, `KEY_FIELD_W`, `KEY_FIELD_D`, `BOARD_W`, `BOARD_D`, `BOARD_T`.
- Produces: `SWITCH_HOLE` 14.10, `PLATE_TOP_TO_PCB` 2.20, `PLATE_T` 1.30, `SOCKET_DROP` 1.90, `CASE_H` 9.50 — all constants, no switch axis.

- [ ] **Step 1: Import the field instead of deriving it**

At the top of `case/params.py`, replacing the NeoKey and breakout blocks:

```python
import os
import sys

# The PCB owns the key field now. This is a path insert rather than a package
# import because case/ runs in its own 3.12 venv and pcb/ is stdlib-only, so
# neither has to know about the other's environment.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pcb"))
import params as pcb  # noqa: E402

SWITCH_PITCH = pcb.SWITCH_PITCH
KEY_FIELD_W = pcb.KEY_FIELD_W
KEY_FIELD_D = pcb.KEY_FIELD_D
BOARD_W = pcb.BOARD_W
BOARD_D = pcb.BOARD_D
BOARD_T = pcb.BOARD_T
SWITCH_X = [x for x, _ in pcb.switch_centres_mm()]
SWITCH_Y = pcb.SWITCH_Y
```

- [ ] **Step 2: Replace the layout axis with the switch axis**

```python
# MPAD_LAYOUT selected where the QT Py sat, and there is no QT Py. It was
# briefly going to be replaced by MPAD_SWITCH, and that is gone too: MX and
# Choc hot-swap holes cannot share a position -- their alignment posts sit
# 0.42 apart and need 1.86 -- so this board is Choc v2 and nothing else.
# With one switch there is no axis, and every number below is a constant.
#
# 13.95 cutout off Kailh CPG135301D01, plus this machine's 0.15 shrink.
SWITCH_HOLE = 14.10
PLATE_TOP_TO_PCB = 2.20
PLATE_T = 1.30          # Choc's clips need 1.30; there is no fallback now
SOCKET_DROP = 1.90
```

- [ ] **Step 3: Delete the QT Py geometry**

Remove from `case/params.py`: `QTPY_*` (all of them), `CABLE_BAY`, `QWIIC_PLUG_L`, `WIRE_LANE_*`, `WIRE_CHANNEL_*`, `INLINE_*`, `STACKED`, `LAYOUT`, `NEOKEY_*`, `BREAKOUT_*`. Remove the parts in `case/parts.py` that read them, and the corresponding stand-ins in `case/mock.py`.

**Assert every substitution if you script this.** A `str.replace()` that misses returns the string unchanged, the edit silently does nothing, and the next command reports success on code that was never modified. This has bitten twice in this repository.

- [ ] **Step 4: Give the mock one board**

In `case/mock.py`, replace the NeoKey, both breakouts and the QT Py with a single stand-in built from `BOARD_W x BOARD_D x BOARD_T`, plus the USB-C plug body at the right-hand tab. **Model the mated plug, not the receptacle** — a wall can clear a socket perfectly and still seal it off, which has happened four times here.

- [ ] **Step 5: Build both switch settings**

```bash
cd case
.venv/bin/python build.py
```

Expected: `all checks passed`, and `CASE_H` 9.50 — **3.83 below the wired
pad's 13.33**, which is the entire reason this switch was worth its cost.

- [ ] **Step 6: Watch a check fail**

Set `SWITCH_HOLE` to 20.0 and rebuild. Expected: the switch-body interference check goes red with a non-zero mm³. Restore by the reverse edit. **Move geometry or push one number past its limit — do not shrink a feature to nothing**, because a zero-width `Box` makes OCCT throw and the build dies before any check runs.

- [ ] **Step 7: Run the whole figure sweep**

`build.py` only rewrites STLs and STEPs, so the PNGs and the viewer still show the old design until:

```bash
cd case
.venv/bin/python build.py
.venv/bin/python product.py
.venv/bin/python render.py
.venv/bin/python section.py
.venv/bin/python webgl.py dump
.venv/bin/python webgl.py page
open -a "Google Chrome" out/viewer.html
```

Reload the tab: regenerating the page does not refresh an open one, and the stale geometry looks entirely convincing.

- [ ] **Step 8: Add the two questions the coupon has to answer**

`case/params.py` already carries sweep tuples for the numbers a printer
settles. Add one for the switch hole:

```python
# Kailh CPG135301D01 gives 13.95; this machine pulls a hole in by 0.15, the
# constant SWITCH_HOLE has always measured, so 14.10 is the arithmetic. It
# has never been checked against a Choc v2 -- none has been on this desk --
# so the sweep brackets it rather than trusting it.
HOLE_SWEEP = (14.00, 14.10, 14.20)
```

The second question cannot be swept, only printed: **does 1.30 of printed
plate hold a Choc v2's clips?** Add a coupon fragment at `PLATE_T` 1.30
carrying one `HOLE_SWEEP` hole, in the orientation the real plate prints in.

**This coupon is blocking now, where it used to be optional.** With MX gone
there is no fallback thickness and no switch already on the desk that fits
the board, so a wrong 1.30 is discovered on the finished case rather than on
a fragment.

- [ ] **Step 9: Print the coupon before the case**

```bash
cd case && MPAD_SWITCH=choc .venv/bin/python build.py
# print out/choc/coupon.stl
```

Press each switch into each hole by hand. The one that seats without force
and does not rock is the answer. Record it in `case/README.md` beside the
`SWITCH_HOLE` entry, with which switches were tried.

- [ ] **Step 10: Commit**

```bash
git add case/params.py case/parts.py case/mock.py case/build.py case/README.md case/out
git commit -m "Let the case read the field off the board that defines it"
```

---

## Task 6: Firmware — one key source

**Files:**
- Modify: `firmware/code.py`
- Modify: `firmware/boot.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: unchanged protocol. `HELLO 3 6`, `PONG 3 6`.

- [ ] **Step 1: Collapse the sources**

In `firmware/code.py`, delete `PAD_ADDRESSES`, `SEESAW_BASE`, `GPIO_BASE`, the `adafruit_neokey` import and every `i2c` guard. Replace the two-source list with one:

```python
# One board, one source. The seesaw and its bus are gone with the NeoKey, and
# so is every ERR i2c path -- not because they were wrong but because the
# hardware they described is not on this device.
KEY_PIN_NAMES = ("MOSI", "MISO", "SCK", "TX", "RX", "SDA")
PIXEL_PIN_NAME = "SCL"
NUM_KEYS = len(KEY_PIN_NAMES)
```

Keep `NUM_KEYS` a constant, for the reason it already is: the host maps index to pane, and a silent renumbering focuses the wrong session.

- [ ] **Step 2: Compile**

```bash
python3 -m py_compile firmware/*.py tools/mpad.py
```

Expected: silence.

- [ ] **Step 3: Update the drive gate**

In `firmware/boot.py`, delete the I2C branch and read the same six pin names. `boot.py` still cannot import `code.py` — that would run the whole program — so the pin names remain a second copy. **Their failure mode is silent**: a name that exists but points at the wrong pin reads high through its pull-up, and those keys quietly stop opening the drive. Keep the two lists adjacent in review.

- [ ] **Step 4: Deploy and probe**

```bash
cp firmware/code.py /Volumes/CIRCUITPY/ && rm -f /Volumes/CIRCUITPY/._code.py
tools/mpad.py --probe
```

Expected: `PONG 3 6`. If the port answers nothing, check `lsof /dev/cu.usbmodem*` first — Canopy holds the data port and that reads exactly like a dead board.

- [ ] **Step 5: Deploy `boot.py` with a hard reset**

```bash
cp firmware/boot.py /Volumes/CIRCUITPY/ && rm -f /Volumes/CIRCUITPY/._boot.py
# replug, or from the REPL on the console port:
#   import microcontroller; microcontroller.reset()
tools/mpad.py --probe
```

Expected: `PONG 3 6`, and `CIRCUITPY` gone. Copying `code.py` triggers auto-reload, which is a **soft** reset, so an edited `boot.py` never runs and the probe reports a healthy board still on the old USB config.

- [ ] **Step 6: Injection on the surviving error paths**

Copy `code.py` aside, inject a `raise` in the pixel setup, flash, and confirm the host is told `ERR gpio pixels ...` while key presses still report. Restore **from the copy, not from git** — `git checkout --` restores the committed file and would discard anything uncommitted. Then run the negative control: with no fault, confirm the error does **not** appear. A passing error-path test that was never triggered is the default outcome here, not the exception.

- [ ] **Step 7: Commit**

```bash
git add firmware/code.py firmware/boot.py
git commit -m "Make the keypad one source, and say what that costs"
```

---

## Task 7: The combo footprint, so one board takes three switches

**Files:**
- Create: `pcb/footprint.py`
- Modify: `pcb/params.py` (add `DEV_CHOC_SOCKET`, `SWITCH_HOLES`)

**Interfaces:**
- Consumes: `bridge.execute`, `params.switch_centres_mm`.
- Produces: `footprint.assert_holes_present(centre_mil) -> None`, raising with the missing hole's nominal diameter.

The board must accept a Durock, a GTMX and a Choc v2 from the same copper.
MX and GTMX share a pattern outright; Choc v2 does not, and the two overlap
rather than conflict — MX wants Ø4.00 centre with 2 x Ø1.50, Choc v2 wants
Ø5.00 centre with 2 x Ø1.20 and a Ø1.60.

- [ ] **Step 1: Write the hole table into `pcb/params.py`**

```python
# --- switch holes ----------------------------------------------------------
# Offsets are from the switch centre, in mm, +y towards the board's back.
#
# The MX rows are MEASURED, out of Adafruit's own "NeoKey 1x4 QT I2C.brd" --
# the board this project's working pad is built on. They are not derived from
# a switch drawing, and the difference is not academic: a first pass written
# from drawings had the pin drills at 1.50 (forgetting that the hot-swap
# socket's barrel passes through, not just the switch pin) and omitted the
# two plate-mount alignment posts entirely, which would have refused every
# five-pin switch this pad uses.
#
# The Choc v2 rows are READ OFF Kailh's CPG135301D01 figure and have not been
# checked against a part or a board. They are the weaker half of this table.
#
# The centre is Choc v2's Ø5.00 rather than MX's Ø3.9, because the hole only
# has to clear a centre post -- the plate locates the switch -- so the larger
# swallows the smaller and the reverse would not.
SWITCH_HOLES = [
    ("centre", (0.00, 0.00), 5.00),        # choc v2 drawing; MX board has 3.9
    ("mx_pin_a", (-3.81, 2.54), 3.0635),   # measured
    ("mx_pin_b", (2.54, 5.08), 3.0635),    # measured
    ("mx_post_l", (-5.08, 0.00), 1.8135),  # measured, plate-mount alignment
    ("mx_post_r", (5.08, 0.00), 1.8135),   # measured, plate-mount alignment
    ("choc_a", (-5.00, 3.80), 1.20),       # drawing, unverified
    ("choc_b", (5.00, 3.80), 1.20),        # drawing, unverified
    ("choc_c", (0.00, 5.90), 1.60),        # drawing, unverified
]

# The Kailh socket's own solder pads, bottom side, measured off the same
# board. These are what the socket is hand-soldered to after assembly.
SOCKET_PADS = [
    ((6.09, 5.08), (2.55, 2.50)),
    ((-7.36, 2.50), (2.55, 2.50)),
]
```

- [ ] **Step 2: Write the probe**

```python
# pcb/footprint.py
"""Assert the combo footprint has every hole all three switches need.

A footprint that is missing a hole still builds, still passes DRC, and still
looks right -- it simply refuses the switch, once, on the assembled unit.
"""
import params
from bridge import execute


def _pads_near(x_mil, y_mil, radius_mil):
    js = (
        "const all = await eda.pcb_PrimitivePad.getAll(); "
        "return (all || []).map(p => ({x: p.x, y: p.y, d: p.holeDiameter}));"
    )
    pads = execute(js) or []
    return [
        p for p in pads
        if abs(p["x"] - x_mil) <= radius_mil and abs(p["y"] - y_mil) <= radius_mil
    ]


def assert_holes_present(centre_mm):
    """Every entry in params.SWITCH_HOLES must exist at its offset."""
    cx, cy = centre_mm
    missing = []
    for name, (dx, dy), dia in params.SWITCH_HOLES:
        want_x = params.mm_to_mil(cx + dx)
        want_y = params.mm_to_mil(cy + dy)
        near = _pads_near(want_x, want_y, 4)
        if not near:
            missing.append(f"{name} (Ø{dia:.2f}) at ({want_x}, {want_y})")
    if missing:
        raise AssertionError("combo footprint is missing: " + "; ".join(missing))
    print(f"  [ok ] combo footprint: {len(params.SWITCH_HOLES)} holes present")
```

- [ ] **Step 3: Watch it fail before trusting it**

Add a seventh entry to `SWITCH_HOLES` at an offset nothing occupies:

```python
    ("injected", (9.00, 9.00), 1.00),
```

Run the probe. Expected: `AssertionError: combo footprint is missing: injected
(Ø1.00) at (354, 354)`. Remove the entry by the reverse edit.

- [ ] **Step 4: Draw the footprint and run the probe against it**

Build the combined pad set on the first switch position, then:

```bash
cd pcb && python3 -c "
import footprint, params
footprint.assert_holes_present(params.switch_centres_mm()[0])
print('all checks passed')
"
```

- [ ] **Step 5: Confirm on parts, not on the probe**

The probe proves the holes exist where the table says. It cannot prove the
table matches the switches. Once boards arrive, press a Durock, a GTMX and a
Choc v2 into the same position and record which seat. **This is the check the
probe cannot be**, and the reason both exist.

- [ ] **Step 6: Commit**

```bash
git add pcb/footprint.py pcb/params.py
git commit -m "Give one position the holes all three switches ask for"
```

---

## Task 8: Schematic, DRC and the order

**Files:**
- Modify: `pcb/build.py` (add the RP2040 block and the manufacturing step)
- Create: `pcb/README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: Gerber, BOM and pick-and-place files.

- [ ] **Step 1: Bring in the RP2040 reference**

Raspberry Pi's Minimal Viable Board is published under CC-BY-SA with permission to copy and modify. Import it rather than inventing the block: RP2040, 8 MB QSPI flash matching the QT Py's, 12 MHz crystal, 3.3 V LDO, decoupling, BOOT button, USB-C with 2 x 5.1 kΩ CC and ESD diodes.

Wire the six key pins and the pixel line to the **QT Py RP2040's GPIO numbers** — `MOSI` 3, `MISO` 4, `RX` 5, `SCK` 6, `TX` 20, `SDA` 24, `SCL` 25 — so Adafruit's released CircuitPython UF2 boots the board with no board definition to author. `NEOPIXEL` (GPIO12) is deliberately not the chain: on a QT Py it is gated by `NEOPIXEL_POWER`, and a pixel line needing a second pin driven high is a failure mode with no symptom.

- [ ] **Step 2: Run DRC**

```python
# in pcb/build.py
def assert_drc():
    passed = execute("return await eda.pcb_Drc.check(true, true, false);")
    if not passed:
        raise AssertionError("DRC reported errors; open the PCB and read them")
    print("  [ok ] DRC")
```

- [ ] **Step 3: Export manufacturing data**

```python
def export_fabrication():
    js = (
        'const g = await eda.pcb_ManufactureData.getGerberFile("canopy_macropad"); '
        'const b = await eda.pcb_ManufactureData.getBomFile("canopy_macropad"); '
        'const p = await eda.pcb_ManufactureData.getPickAndPlaceFile("canopy_macropad"); '
        "return {gerber: g ? g.size : 0, bom: b ? b.size : 0, place: p ? p.size : 0};"
    )
    got = execute(js, timeout=120.0)
    for name, size in got.items():
        if not size:
            raise AssertionError(f"{name} came back empty")
    print(f"  [ok ] fabrication: {got}")
```

- [ ] **Step 4: Check the six pixels' rotation before ordering**

`SK6812MINI-E` and `SK6812MINI-EA` differ in tape orientation, and the wrong one lights the inside of the board six times over while the boards arrive looking perfect. Confirm the placement file's rotation for the pixels against the part's datasheet, by eye, before the order.

- [ ] **Step 5: Order five boards**

JLCPCB minimum. Assemble everything **except** the hot-swap sockets — those are hand-soldered afterwards, which is what lets one board serve MX, GTMX and Choc v2.

- [ ] **Step 6: Write `pcb/README.md`**

Cover: starting the bridge, the *Allow interactive with external* checkbox and why its absence reads as "Bridge not found", the three API traps in the Global Constraints, and how to re-run `build.py` with and without `--inject`.

- [ ] **Step 7: Commit**

```bash
git add pcb/build.py pcb/README.md
git commit -m "Take the board from placement to a fabrication package"
```

---

## Task 9: Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md` (`CLAUDE.md` is a symlink to it, so this is one edit)

- [ ] **Step 1: Fix the claims that this board makes wrong**

In `README.md`: the three-board hardware table, the Qwiic cable, the five wires, the `ERR i2c ...` rows of the known-good table, the "a dead cable costs all six" paragraph, and both `MPAD_LAYOUT` names.

- [ ] **Step 2: Keep the wired pad rather than deleting it**

It is a built, working device, and the numbers it settled — the 0.15 shrink, `PILOT_DIA` 2.95, `SCREW_CLEAR_DIA` 3.70, `CLEAR_RING_MAX` — are inherited whole. What changes is which pad the documents describe first.

- [ ] **Step 3: Review the section, not the diff**

Two commits a round apart have already contradicted each other in this repository, and neither commit's diff contained the other. Read the changed sections end to end.

- [ ] **Step 4: Commit**

```bash
git add README.md AGENTS.md
git commit -m "Describe the board that exists now, and keep the one that came before"
```
