# pcb/ — EasyEDA bring-up and known API traps

The board's own geometry, licensing, and what it's cloned from are in
`NOTICE.md`. This file is the operational half: how to talk to the EasyEDA
client from Python, and the specific ways the API has already bitten this
project.

**`BRINGUP.md` is the other kind of bring-up** — what to do with the
fabricated boards once they arrive from JLCPCB, in what order, and which
of those steps prove less than they appear to. Nothing here needs the
physical board; nothing there needs EasyEDA.

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

- **A pad having a hole does not make it Multi-Layer.** The USB-C
  `B4A9`/`A4B9` VBUS pads report `layer: 2` and a round `hole`; their copper
  is still Bottom-only. `route.pad_cells()` used to allow every drilled pad
  as a start on both outer layers, so both VBUS routes left on Top and never
  connected to the real pads. `connect.py` repeated the same mistake and
  called the board complete. Only `layer == 12` spans layers. With that rule,
  the router adds the two required VBUS vias and the connectivity check sees
  the same 32 connected nets EasyEDA sees.

- **Physical overlap does not always retire EasyEDA's ratline.** The grid
  router may legally enter a pad away from its centre; EasyEDA retained seven
  short airwires on six nets even though the same-net copper overlapped.
  `center_ties.py` adds seven same-net 0.15 mm stubs from the diagnosed pad
  centres to copper already touching those pads. The final Net panel must say
  `Ratlines (0)`; hiding the Ratline layer is not verification.

- **`pcb_Drc.check()` can redraw stale yellow X markers even when it finds no
  current violation.** On this board the call exceeds the bridge's fixed 30 s
  timeout, and this EasyEDA release has also rejected the asynchronous result
  with an internal `Error: undefined`. Do not scrape the editor's private tab
  state and call that a DRC result. Run **Design -> Check DRC** in the client
  and read the bottom DRC panel; the required result is `All (0)`. If an
  interactive DRC has left old Xs behind, use **Design -> Clear Errors** once.
  `removeIndicatorMarkers()` is a different marker system and does not remove
  DRC Xs, and the public `pcb_Drc` API exposes no Clear Errors method. Yellow X
  objects are UI state, not stored Multi-Layer primitives; hiding Multi-Layer
  never was the fix.

- **The stock footprint geometry and stock DRC table contradicted each
  other.** The reverse-mount LED opening left only 0.10 mm to its four pads,
  and each switch footprint contained two Multi-Layer circular fills exactly
  on top of two real plated holes. `footprint_fixes.py` moves the LED pads
  0.11 mm outward (about 0.209 mm opening clearance after EasyEDA's mil
  rounding) and deletes only those two duplicate fill records. The actual
  switch holes remain: the final NPTH drill has 6 slots plus 12 x 1.905 mm,
  12 x 2.9972 mm, and 6 x 5.0038 mm switch openings.

  `rules.py` then makes the live table match the measured geometry: 0.102 mm
  between copper objects, 0.20 mm from routed openings to copper, 0.25 mm
  from the USB-C shell holes to the outline, and 1.5 mm maximum USB pair
  skew. All values are read back after writing. The 36 switch-hole keepouts
  prohibit tracks, pours, and inner-layer copper, but not components: each
  switch necessarily overlaps the keepout around its own holes, so adding
  `NO_COMPONENTS` created 18 permanent false DRC errors. `all.sh` verifies the
  stored rule values and prints a reminder to run the client-side DRC; it does
  not claim `All (0)` on behalf of an API call that timed out.

- **Same-net clearance rules do not prevent accidental via-in-pad.** The
  router once produced 33 annulus overlaps, 27 with the drilled opening in a
  solderable pad, so the route grid treats every SMT pad as a no-via area and
  dogbones every router-created via. U3's stock 3x3 exposed-pad via array is
  removed too: `thermal_fanout.py` replaces it with four short bottom-layer
  GND spokes and 0.45/0.30 mm vias outside pad 57's paste area. This retains
  short thermal and ground paths without requiring filled-and-capped
  via-in-pad processing. `via_in_pad.py` rejects every annular SMT-pad
  overlap, without exceptions. Every board via uses the ordinary-cost
  0.45/0.30 mm geometry; the NPTH file still contains all 36 switch openings
  and the two 0.60 mm USB-C locating holes.

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

- **`sch_Document.save()` persists the open schematic.** Returns `true`
  on success, `false` on upload/save failure -- do not treat false as a
  no-op. Call it after any mutation; do not ask a person to File → Save.

- **`sch_PrimitiveWire.modify({line})` echoes the request and does not
  persist.** `toAsync().setState_Line()` throws `modify failed!`. The
  shape that actually changes a wire is delete-then-create. Same-net
  stubs that touch merge into one object; that is how D+ shorted to D-
  when their stars shared a vertex at x=1025, and how the split put each
  rail back together on its own net without sharing one.

- **`getExportDocumentFile()` leaves a grey loading cover if it times out,
  and the cover locks every menu.** `showLoading()` is documented as
  阻止用户进一步操作 -- clicks and menu items go nowhere while it is up.
  The bridge's default execute timeout is 30s; the PDF export hung past
  that and the cover stayed. `sys_LoadingAndProgressBar.destroyLoading()`
  / `destroyProgressBar()` clears it. `schematic_tidy.clear_overlay()` is
  that call. Restarting EasyEDA also works, but any unsaved annotation is
  gone until you can reach File → Save.

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

- **A pad's rotation is RADIANS. A component's is DEGREES.** Same
  document, same client, same call to `getAll()`. The only sixteen
  rotated pads on this board are the USB-C receptacle's, all at
  `1.5707963`, and reading that as degrees turns a quarter turn into 1.6
  degrees — the shield tabs end up lying flat across the board edge and
  nothing complains. `geom.pad_polygon()` takes radians for that reason
  and says so.

- **A POLYGON pad's points are absolute and already rotated.** Every
  other pad shape is local to the pad and takes its translation and
  rotation; a POLYGON takes neither. Its list is also a *path*, with `L`
  and `ARC` tokens between the numbers, so pairing the raw list into
  points without skipping the keywords produces garbage.

- **A polyline's geometry is wrapped; a pad's is not.** A pad's POLYGON
  field is a bare list. A polyline's `polygon` field is an *object* with
  a `polygon` list inside it. A flattener that only descends into lists
  returns nothing for the second — which reads exactly like "this board
  has no outline", for a board whose outline is right there.
  `geom._flatten()` walks dicts because of this.

- **A polygon path must be explicitly closed.** The docs say an open
  path is closed automatically (`如果首尾不重合将会自动重合`). It is
  not: `createPolygon` refused a triangle and a square, and accepted the
  same square with its first point repeated at the end.

- **`regionName` is accepted and then not stored.** Pass one to
  `pcb_PrimitiveRegion.create()` and read the region back: there is no
  name field at all. A cleanup keyed on the name therefore matches
  nothing and every run adds another set of regions on top of the last.
  `layout.keepouts()` identifies its own by layer and rule set instead.

- **`overwriteCurrentRuleConfiguration` returns `undefined`,** not the
  documented boolean — and an undefined value disappears from the JSON
  the bridge returns, so the key is simply absent rather than false.
  Whether a rule took has to be answered by reading a number back out.

- **The class methods are not all the methods.** `PCB_PrimitivePour` has
  no rebuild function and it is easy to conclude there is no API for
  filling copper. There is: `rebuildCopperRegion()` lives on
  `IPCB_PrimitivePour`, the *instance* interface, reached by
  `pcb_PrimitivePour.get([id])`. When a class looks like it is missing
  an obvious verb, grep `references/_quick-reference.md` — it lists both
  sides.

- **The bridge has its own 30 s request timeout** and the `timeout=`
  passed to `execute()` does not raise it. `pcb_Drc.check()` and
  `sch_Netlist.getNetlist()` both outrun it on this board and come back
  as a bridge timeout while the operation completes fine inside the
  client. Neither is reachable from a script here; run them in the UI.

- **Four lines forming a closed rectangle are not a board outline.** They
  are four lines. `zoomToBoardOutline()` returns true, the render looks
  right, DRC says nothing — and Auto Routing refuses to start with
  "Please draw a board outline first!". The edge has to be **one closed
  polyline** (`pcb_PrimitivePolyline`, layer 11). Related: widening the
  board left the old right-hand edge in place and the client split the
  new top and bottom edges against it, giving seven segments — one of
  them a full-height cut line down the middle of the board, which a fab
  would route. `layout.strip()` checks the edge is a single closed loop
  for both reasons.

- **EasyEDA's rounded-rectangle `R` path has an inverted Y anchor.** For a
  board spanning y=0..21.59 mm, `['R', 0, 0, w, h, 0, r]` produces an
  outline at y=-21.59..0. The source has to start at y=21.59 mm. The
  documented polygon `discretize()` methods return `Not implemented`, so
  `board_edge.py` verifies both the raw path and the primitive's measured
  bounding box after creation. A render that merely looks rounded is not
  enough; the old inverted outline looked plausible below the components.

- **A copper pour whose boundary no longer matches the board vanishes on
  rebuild.** The GND and 3V3 planes were drawn for the 121.60 mm board;
  after widening to 139.60 they were removed by the next copper rebuild,
  silently. The only symptom was an autorouter that did nothing. And a
  pour that reaches *nothing* is discarded the same way: 3V3 refused to
  fill at all until `stitch.py` gave its pads vias, because every 3V3 pad
  on this board is surface-mount on the bottom. `planes.py` derives both
  boundaries from `params` so they cannot outlive the board again.

## Schematic-side API traps (`schematic.py`)

Everything above was learned placing sockets and pixels on the **PCB**.
Building the RP2040 block on the **schematic** turned up a second, distinct
set of traps, all confirmed live:

- **`SCH_ManufactureData.getNetlistFile()` breaks permanently after
  `createNetFlag()` or `createNetPort()`.** Not occasionally -- every time,
  reproduced twice independently, on both calls. Before either is placed the
  netlist reads fine (the very first read after a batch of edits can be
  stale or `undefined`, but a short retry recovers it every time this was
  watched). After either is placed, every subsequent `getNetlistFile()` call
  on that document returns `undefined` forever, with no amount of retrying
  or waiting fixing it -- only a full component clear does.
  `schematic.py`'s `assert_nets()` reads the netlist once, early, for
  everything that is a physical wire (QSPI, the crystal pair, VBUS, DVDD,
  USB D+/D-, CC1/CC2), *before* placing any flag or port, and falls back to
  `assert_nets_by_graph()` (a union-find over this file's own recorded wire
  segments) for anything checked after that point.

- **`eda.sch_PrimitiveComponent.getState_Component().uuid` is not the uuid
  passed to `create()`.** EasyEDA clones the library device into the
  project's own local library on placement and hands back *that* copy's
  uuid from then on -- confirmed live: `params.DEV_RP2040` is
  `"a550c651..."`, but the placed RP2040's own reported component uuid
  reads `"a67eb1f3155fc4f9"`, 16 hex characters, unrelated-looking. The
  netlist's `props.Device` field carries the same cloned uuid, not the
  original. `params.LCSC_OF` matches on the netlist's `props.Supplier Part`
  (the LCSC number) instead, which survives the clone unchanged.

- **A placed part's Designator is assigned by placement order within its
  own default prefix, not by anything this file controls.** The crystal
  (`Y1` in this file's own naming) landed on Designator `"U4"`, not the
  USBLC6-2SC6 -- EasyEDA numbers every `"U?"`-prefixed device (chips,
  crystals, LDOs alike) in one shared counter, in the order they were
  placed. Match components by LCSC number, not Designator.

- **A pin placed exactly coincident with another primitive is not provably
  on its net.** A `Ground`/`Power` net flag, or a net port, placed at the
  exact same coordinate as a target pin, with no wire at all, creates
  successfully and reads back at the right position -- but nothing in the
  API distinguishes that from a symbol merely occupying the same pixel.
  `getAllPinsByPrimitiveId()` on the flag itself shows it does have its own
  real connection point; the fix is a short, real, two-point wire from the
  flag's point to the target pin, not reliance on coincidence.

- **`eda.sch_PrimitiveWire.create()`'s coincidence-based net inheritance
  (rule 1 in its own doc comment: "if one endpoint lands on a primitive
  with a net, follow it") does not populate `getState_Net()` the way an
  explicit `net` argument does.** A stub wire from a net flag to a target
  pin, created with `net` left `undefined` so it should inherit the flag's
  declared net by coincidence, reads back `getState_Net() === ''` --
  every time this was tried. The same stub, created with the net name
  passed explicitly, reads back correctly. Pass `net` explicitly; do not
  rely on inference from a touched flag or port.

- **Two wires sharing any coordinate -- not just their nominal endpoints --
  get silently merged into one wire object, and the merge can reassign
  which net the combined object reports.** Confirmed via
  `ISCH_PrimitiveWire.getState_Line()`: a wire object's line array showed
  two unrelated 2-point segments concatenated together after two separate
  `create()` calls happened to touch the same point. In the densest area
  of this board (the ten 100 nF decoupling caps, all at the same y) a
  handful of GND/3V3 flag stub wires ended up merged into the *other*
  rail's wire object despite passing this file's own pin- and
  segment-crossing checks -- meaning the merge criterion is not fully
  captured by "does a registered pin or a previously-drawn segment sit on
  this new segment", the check `schematic.py`'s `elbow()` and
  `_find_clear_offset()` both use. `assert_power_flags()` samples a few
  stub wires per rail with `getState_Net()` rather than trusting placement
  alone, and reports (not silently swallows) any sample that came back on
  the wrong net -- see its own docstring for the exact count on the last
  run.

- **A single-bend Manhattan route between two pins routinely passes
  through a third, unrelated pin on the same crowded column or row, and
  the collision is a real electrical short, not a cosmetic overlap.**
  Every densely-pinned cluster on this board -- the RP2040's own 57-pin
  symbol, the crystal's 4-pad footprint, the flash's two pin columns, the
  USB-C connector's packed 12-signal column -- produced at least one
  wiring attempt where both of the two "obvious" bend points landed on an
  unrelated pin instead of empty space. `schematic.py`'s `elbow()` checks
  every candidate route against every pin on the board
  (`getAllPinsByPrimitiveId()`, read back once after placement) before
  committing to it, and searches a widening set of detour offsets before
  raising -- six pin columns needed that search before a route was found,
  one (the crystal's boxed-in first pin, and the USB-C connector's
  fully-packed 545-655 column) needed a hand-built path instead. A route
  that "looks like" the obvious 3-point elbow is not evidence it avoids
  every pin in between; only checking it against the actual pin list is.

## PCB-side MCU import traps (`place_mcu.py`)

- **`create()` never builds EasyEDA's flying wires.** UniqueIds,
  `pad.modify({net})`, `importChanges()`, and `setNetlist()` can all
  report success while the canvas still has no ratsnest. The path that
  actually creates them is PCB **Design → Import Changes from Schematic**
  (`Alt+I`) against an empty board (or schematic-tab **Design → Schematic
  to PCB** — that item is not on the PCB Design menu). After convert,
  move existing parts (`place_mcu.py --relayout`); do not delete and
  recreate, and do not run `build.py`. Convert dumps SK/LED on TOP at
  schematic-relative coords (negative Y, off the outline); `--relayout`
  puts them on BOTTOM at `params` field positions and keeps the 32 nets.
  Switch holes are not in the schematic; `footprint.place_switch_holes`
  goes back on after the move. After convert, `pcb/cluster.py` packs the
  MCU block by net (crystal on XIN/XOUT, ESD/LDO on the USB tab, flash
  in the next pixel gap). `cluster.py` records the superseded four-layer
  experiment; the finished board uses `stack.py` to require exactly two
  copper layers. `planes.py` creates Bottom GND and Top 3V3 pours, and
  `rebuildCopperRegion()` verifies that both filled copper primitives remain.
  `sch_Net.getAllNetsName()` stays `[]`
  even when `getNetlistFile("JLCEDA")` is complete — do not call
  deprecated `sch_Netlist.getNetlist()` (hangs). The SK6812 symbol's pin
  *names* (1=GND …) do not match its footprint or `PIXEL_PAD_SIGNALS`
  (1=VDD …); convert maps by pin *number*, which is why it still ran.

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

## Re-running the finished routed board

```
cd pcb
./all.sh
python3 plot.py
```

`all.sh` replaces the rounded outline, requires a two-layer stack, applies
placement and silkscreen, routes all signal and power nets, rebuilds Bottom
GND and Top 3V3 pours, requires the EasyEDA Net panel to read `Ratlines (0)`,
checks that all 32 nets are single connected islands, and runs the
review-specific checks in `polish.py`. The reverse-mount LED rectangles are physical board
openings and are obstacles to both the signal router and power-via stitcher.
KEY0 uses y=7.9 mm through the repeated opening/centre-hole passage, the
farthest legal row on the 0.10 mm router grid; KEY3 avoids the narrow
passage. PIXEL2--PIXEL5 must have no 90-degree copper corners.

There are deliberately no board mounting holes. The printed case already
locates and clamps the PCB between its shell standoffs and bottom support
columns; adding holes would consume routing area without adding retention.
The case imports `BOARD_CORNER_RADIUS` from `pcb/params.py`, so its pocket
and the R2.54 mm board corners have one source.

## Manufacturing export and JLCPCB quote

Export the exact open PCB revision, then verify the three files before an
upload:

```
cd pcb
python3 export_manufacturing.py
```

This writes `out/manufacturing/canopy_macropad-gerber.zip`,
`canopy_macropad-bom.xlsx`, and `canopy_macropad-cpl.xlsx`. The exporter checks
that the archive contains both outer copper layers and drill data, and no
inner copper layers; that the BOM contains U1 as W25Q64JVSSIQ / C179171; that the old
unavailable C2940195 XSON part is absent; and that U1 is present in the CPL.
Passing export checks prove file completeness, not DRC cleanliness, so run the
EasyEDA DRC panel immediately before upload.

**And run `./all.sh` before the export, not after.** The exporter runs
none of the design guards -- not `via_in_pad.py`, not `thermal_fanout.py`
-- so it will produce a perfectly complete Gerber from a document `all.sh`
would reject. This is not hypothetical: U3's stock 3x3 exposed-pad via
array reappeared in the live document after one export, nine GND vias
straight through pad 57, which is exactly the via-in-pad this board is
built to avoid. DRC does not catch it either, because a same-net via in a
same-net pad breaks no rule -- it is a manufacturing decision. The first
fabricated boards escaped only because the export happened before the
regression rather than after it. `pcb/BRINGUP.md` carries the two commands
that compare a fabricated drill file against the document at any time.

The board is now a dedicated two-layer redesign: Bottom carries the GND pour,
Top carries the 3V3 pour and backbone, and every signal and power net has an
explicit ordinary-copper path. Do not reuse an older four-layer Gerber archive.

For the intended cheapest partial assembly, start with 5 green FR-4 boards,
2 layers, 1.6 mm, 1 oz copper and the cheapest available HASL finish. Enable
Economic PCBA on the bottom side for 2 boards and
use customer/self-service parts selection. U3 (RP2040) and U1 (C179171 flash)
must be assembled; the reverse-mount LEDs, hot-swap sockets, and SW1 may be
marked DNP for hand soldering. The checked cheaper flash candidates were
Standard-only in Economic assembly, so retain C179171 unless the live parts
filter shows a compatible in-stock Economic option. Recheck live stock and the displayed total before
saving the quote because JLCPCB availability and fees can change after these
files were exported. Never advance from the reviewed quote to payment without
an explicit order instruction.

## Re-running the original key-cell `build.py`

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

`assert_drc()` calls DRC with `userInterface=false`; the call may still exceed
the bridge timeout or fail inside this EasyEDA release. Use the client-side DRC
panel for the manufacturing decision rather than treating this legacy helper
as final evidence.
`export_fabrication()` does not depend on DRC passing; Gerber, BOM, and
pick-and-place all export successfully even with DRC errors present, which
is realistic (a fabricator's tooling doesn't refuse a design with DRC
violations, a human has to catch that first) but also means a green
`export_fabrication()` is not evidence the board is fabrication-ready.
