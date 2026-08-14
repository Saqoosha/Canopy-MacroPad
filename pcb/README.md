# pcb/ — bring-up and known API traps

The board's own geometry, licensing, and what it's cloned from are in
`NOTICE.md`. This file is the operational half: how to talk to the EasyEDA
client from Python, and the specific ways the API has already bitten this
project.

## Starting the bridge

The bridge is the `easyeda-api` skill's Node server; the EasyEDA side is
the `run-api-gateway` extension. Start it with:

```
node ~/.claude/skills/easyeda-api/scripts/bridge-server.mjs &
```

It scans ports 49620-49629 and identifies itself with `service ==
"easyeda-bridge"`. Check it's actually up and actually talking to a client
before running anything against it:

```
curl -s http://127.0.0.1:49620/health
```

A healthy answer has `"edaConnected": true`. If `edaConnected` is `false`,
or if nothing answers on any port in the range at all, the fix is the same
either way and it is **not** a port problem:

**In EasyEDA, Extension Manager → Config → `run-api-gateway` → tick
*Allow interactive with external*.** The extension's manifest does not
request this permission by default, so without the box ticked the
extension opens no socket at all. What you see instead is `"Bridge not
found"` (or a `health` check that never returns `edaConnected: true`)
against a bridge process that is itself perfectly healthy — the failure
reads like the bridge is broken when the actual gap is a permission
EasyEDA never granted its own extension. Tick the box, then also tick
*Show at header menu* if you want the API Gateway status visible, then use
API Gateway → Reconnect. `bridge.py`'s `find_port()` raises a message
naming this exact fix.

## API traps this project has actually hit

- **Enums are not in the bridge execution context.** Code sent to
  `execute()` runs in an environment where `EPCB_LayerId`,
  `EPCB_PrimitivePadHoleType`, and every other enum object are simply
  absent — referencing one throws a `ReferenceError`, not a wrong value.
  Every enum used in this codebase is the documented **literal** instead,
  with a comment naming which enum it stands in for: `build.py`'s `TOP =
  1` (`EPCB_LayerId.TOP`), `footprint.py`'s `MULTI = 12`
  (`EPCB_LayerId.MULTI`). Before adding a new one, check the literal
  against the enum's reference page under
  `~/.claude/skills/easyeda-api/references/enums/` — do not guess the
  number.

- **`pcb_PrimitiveComponent.create()` takes a device, not a footprint.**
  The first argument is `{libraryUuid, uuid}` naming a *device* (symbol +
  footprint + 3D model bundled together, EasyEDA's unit of "a part"), not
  a bare footprint UUID. `params.DEV_CHOC_SOCKET` and `params.DEV_PIXEL` are
  both device UUIDs, found with `lib_Device.search()` and confirmed live
  by placing them and reading the result back — not read off a footprint
  browser.

- **A pad's hole is `[type, diameter]` (or `[SLOT, diameter, length]`),
  never a `holeDiameter` field.** `IPCB_PrimitivePad` has no such
  property, confirmed live and absent from the class reference. The real
  shape is `hole`, and it is `null` for an SMD pad with no hole at all.
  `footprint.py._pads_near()`'s comment documents this in detail because
  it is exactly the kind of property name a reasonable guess gets wrong
  silently: reading a nonexistent `holeDiameter` doesn't throw, it just
  reads `undefined` forever.

- **`eda.lib_Symbol.get()` carries no pin data.** Its return's keys are
  `name`, `libraryType`, `uuid`, `libraryUuid`, `classification`, `type`,
  `description`, `subPartNames` — confirmed live, nothing resembling a pin
  list or a pad-number-to-signal mapping anywhere in it. The instinct when
  a question is "which pad is which signal" is to reach for the symbol,
  since that's where a schematic tool would put it — it isn't here.
  `params.PIXEL_PAD_SIGNALS` (the SK6812MINI-E's pad-number-to-signal
  mapping `build.assert_pixel_signal_orientation()` checks against) comes
  from the datasheet (LCSC C5149201) instead, because the library has
  nowhere to get it from.

- **PCB coordinates are 1 mil; schematic coordinates are 0.01 inch.**
  `params.mm_to_mil()` is the PCB-side conversion the whole placement
  pipeline runs on. The schematic side is a different unit entirely: a
  live test placing `sch_PrimitiveComponent.create(dev, 100, 100, ...)`
  read back as `x: 100, y: 100`, and that's 1.00 inch each axis, not 100
  mil. The two documents are 2.54x apart on identical-looking integer
  coordinates. Mixing them — e.g. reusing a PCB-side mil value as a
  schematic-side argument — places a part at roughly 1/2.54 of the
  intended distance from origin, silently; nothing errors, the part just
  lands in the wrong place by a factor that isn't obviously wrong at a
  glance.

## The RP2040 reference: GUI-only

Raspberry Pi's Minimal Viable Board reference design needs to come in by
**hand, through EasyEDA's Start Page → Import KiCad**, not by script.
This was checked, not assumed: every plausible import entry point in the
bridge's API reference was read — `DMT_Project` (`createProject`,
`getAllProjectsUuid`, `getCurrentProjectInfo`, `getProjectInfo`,
`moveProjectToFolder`, `openProject` — no import method of any kind),
`SYS_FormatConversion` (the class whose entire job is cross-EDA format
conversion, and it supports exactly two formats, Altium Designer and
T/DISA 4001 — no KiCad), and a grep across the full 120+-class reference
tree for "kicad" (nothing). There is no scripted path in.

The schematic *primitives* the API does expose — `sch_PrimitiveComponent
.create()`, `.getAllPinsByPrimitiveId()` for pin positions,
`sch_PrimitiveWire.create()` with net names — were each proven live
(placed a test component, read its pins, wired a net-named connection,
then deleted all three). They work. What's missing isn't the ability to
place and wire parts by script; it's a source for the reference design's
actual values (LDO part, ESD diode array, crystal load caps, the exact
decoupling network) that doesn't require either clicking Import KiCad or
hand-transcribing a KiCad schematic into individual `create()` calls,
which is authoring the schematic by hand with extra steps. So: import
the reference by hand, then use the script to verify the result — count
parts, check net names, and so on — rather than trying to build the
schematic from the API end to end.

## Re-running `build.py`

```
python3 pcb/build.py                # place sockets + pixels, DRC, export
python3 pcb/build.py --inject        # last socket placed half a pitch off
python3 pcb/build.py --inject-pixel  # pixel 0's y nudged off its switch's offset
```

Every run opens the named project (`MPAD_EDA_PROJECT` env var, default
`Canopy MacroPad`), clears and re-places the sockets and pixels (never the
switch holes — those are `footprint.py`'s job and a separate call, since
`probe.clear_components()` only clears components, not the holed pads
`footprint.py` places), then checks count, position, pitch, and pixel
pairing before running DRC and exporting fabrication data. `--inject` and
`--inject-pixel` are mutually distinct faults, each proven to make its own
check fail on its own — not inferred from the other's failure. Neither
flag touches DRC or export; those are checked on whatever's actually on
the board regardless of which (if any) injection flag was passed.

`assert_drc()` calls DRC with `userInterface=true`, so a failure also
pops EasyEDA's own DRC panel open with the real error list — the raised
`AssertionError` message alone doesn't say what's wrong, the panel does.
`export_fabrication()` does not depend on DRC passing; Gerber, BOM, and
pick-and-place all export successfully even with DRC errors present, which
is realistic (a fabricator's tooling doesn't refuse a design with DRC
violations, a human has to catch that first) but also means a green
`export_fabrication()` is not evidence the board is fabrication-ready.
