"""Apply the two measured local-footprint corrections used by this PCB.

The LED's rectangular component opening ended 0.10 mm from its four pads.
Moving each pad 0.11 mm outward leaves about 0.209 mm copper-to-opening
clearance while retaining about 0.98 mm of terminal overlap.  The switch also drew
two Multi-Layer circular fills exactly on top of two real plated holes; those
duplicate slot records made DRC count each hole twice and add yellow markers.

Both footprints are project-local.  Edit their source, save it, reopen it to
prove persistence, then reopen the PCB so its referenced instances refresh.

    python3 footprint_fixes.py            report only
    python3 footprint_fixes.py --apply    correct, persist, and reload
"""

import json
import sys

from bridge import execute

PROJECT_UUID = "78dc44acfef533ed0a8fb74feeb342c9e0374a2909a81ae129ddfffffb35a4ff"
PCB_UUID = "5d95a7752aeebe98"

LED_UUID = "211c3ce43fb82662"
SWITCH_UUID = "b58ed43d4bf7d619"

# EasyEDA footprint coordinates are mil in the source format.
LED_OLD_X = 106.295
# 2.81 mm.  An exact 2.80 mm centre leaves the asymmetric left edge of the
# rounded slot at 0.1993 mm after EasyEDA's mil rounding, just below the
# 0.2000 mm rule.  The extra 0.01 mm gives a stable ~0.209 mm result.
LED_INTERMEDIATE_X = 110.236
LED_NEW_X = 110.630
LED_PADS = {"e11": 1, "e12": 1, "e13": -1, "e14": -1}
SWITCH_DUPLICATE_FILLS = {"e38", "e39"}


def tab_id(uuid):
    return f"{uuid}@{PROJECT_UUID}"


def source(uuid):
    js = f"""
    const tab = {json.dumps(tab_id(uuid))};
    let activated = await eda.dmt_EditorControl.activateDocument(tab);
    if (!activated) {{
      const opened = await eda.lib_Footprint.openInEditor(
        {json.dumps(uuid)}, {json.dumps(PROJECT_UUID)});
      if (!opened || !await eda.dmt_EditorControl.activateDocument(opened))
        throw new Error("could not open footprint {uuid}");
    }}
    return await eda.sys_FileManager.getDocumentSource();
    """
    got = execute(js, timeout=120.0)
    if not got:
        raise SystemExit(f"empty footprint source for {uuid}")
    return got


def records(text):
    """Yield (line, header, payload), preserving unrecognised source lines."""
    for line in text.splitlines():
        if "||" not in line or not line.endswith("|"):
            yield line, None, None
            continue
        header, payload = line.split("||", 1)
        try:
            yield line, json.loads(header), json.loads(payload[:-1])
        except json.JSONDecodeError:
            yield line, None, None


def rewrite_record(header, payload):
    return (json.dumps(header, separators=(",", ":")) + "||" +
            json.dumps(payload, separators=(",", ":")) + "|")


def fix_led(text):
    out, seen, changed = [], set(), 0
    for original, header, payload in records(text):
        if header and header.get("type") == "PAD" and header.get("id") in LED_PADS:
            pad_id = header["id"]
            seen.add(pad_id)
            wanted = LED_PADS[pad_id] * LED_NEW_X
            current = payload.get("centerX")
            allowed = (LED_PADS[pad_id] * LED_OLD_X,
                       LED_PADS[pad_id] * LED_INTERMEDIATE_X, wanted)
            if not any(abs(current - value) < 1e-6 for value in allowed):
                raise SystemExit(f"{pad_id} has unexpected centerX {current}")
            if abs(current - wanted) >= 1e-6:
                payload["centerX"] = wanted
                changed += 1
                original = rewrite_record(header, payload)
        out.append(original)
    if seen != set(LED_PADS):
        raise SystemExit(f"LED footprint pads missing: {set(LED_PADS) - seen}")
    return "\n".join(out), changed


def fix_switch(text):
    out, present = [], set()
    for original, header, payload in records(text):
        if header and header.get("id") in SWITCH_DUPLICATE_FILLS:
            if header.get("type") != "FILL" or payload.get("layerId") != 12:
                raise SystemExit(f"{header['id']} is no longer the expected Multi-Layer fill")
            present.add(header["id"])
            continue
        out.append(original)
    if present not in (set(), SWITCH_DUPLICATE_FILLS):
        raise SystemExit(f"only one duplicate switch fill was present: {present}")
    return "\n".join(out), len(present)


def write_and_reopen(uuid, text):
    js = f"""
    const tab = {json.dumps(tab_id(uuid))};
    if (!await eda.dmt_EditorControl.activateDocument(tab))
      throw new Error("footprint tab disappeared before write");
    if (!await eda.sys_FileManager.setDocumentSource({json.dumps(text)}))
      throw new Error("setDocumentSource refused the footprint");
    if (!await eda.pcb_Document.save())
      throw new Error("footprint save failed");
    const beforeClose = await eda.sys_FileManager.getDocumentSource();
    if (!await eda.dmt_EditorControl.closeDocument(tab))
      throw new Error("footprint close failed");
    const reopened = await eda.lib_Footprint.openInEditor(
      {json.dumps(uuid)}, {json.dumps(PROJECT_UUID)});
    if (!reopened || !await eda.dmt_EditorControl.activateDocument(reopened))
      throw new Error("footprint reopen failed");
    const afterReopen = await eda.sys_FileManager.getDocumentSource();
    return {{beforeClose, afterReopen, reopened}};
    """
    got = execute(js, timeout=180.0)
    # EasyEDA reserialises some untouched primitives during save (including
    # ticket order and numeric spelling), so byte equality is not a valid
    # persistence test.  The target records are checked semantically by the
    # fresh ``inspect()`` after both reopen operations below.
    if not got["beforeClose"] or not got["afterReopen"]:
        raise SystemExit(f"footprint {uuid} came back empty after save/reopen")


def reopen_pcb():
    js = f"""
    const tab = {json.dumps(tab_id(PCB_UUID))};
    if (!await eda.dmt_EditorControl.activateDocument(tab))
      throw new Error("PCB tab not found");
    if (!await eda.pcb_Document.save()) throw new Error("PCB save failed");
    if (!await eda.dmt_EditorControl.closeDocument(tab))
      throw new Error("PCB close failed");
    const reopened = await eda.dmt_EditorControl.openDocument(
      {json.dumps(PCB_UUID)});
    if (!reopened || !await eda.dmt_EditorControl.activateDocument(reopened))
      throw new Error("PCB reopen failed");
    return reopened;
    """
    return execute(js, timeout=180.0)


def inspect():
    led = source(LED_UUID)
    switch = source(SWITCH_UUID)
    _, led_changed = fix_led(led)
    _, switch_changed = fix_switch(switch)
    print(f"LED pads still needing outward shift: {led_changed}")
    print(f"duplicate switch slot fills still present: {switch_changed}")
    return led, switch, led_changed, switch_changed


def main():
    led, switch, led_changed, switch_changed = inspect()
    if "--apply" not in sys.argv[1:]:
        print("report only; pass --apply to persist")
        return
    fixed_led, _ = fix_led(led)
    fixed_switch, _ = fix_switch(switch)
    if led_changed:
        write_and_reopen(LED_UUID, fixed_led)
    if switch_changed:
        write_and_reopen(SWITCH_UUID, fixed_switch)
    reopened = reopen_pcb()
    _, _, led_after, switch_after = inspect()
    if led_after or switch_after:
        raise SystemExit("footprint correction did not survive reopen")
    print(f"PCB reloaded as {reopened}")
    print(f"LED pads shifted: {led_changed}; duplicate switch fills removed: {switch_changed}")


if __name__ == "__main__":
    main()
