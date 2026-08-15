# pcb/schematic_keys.py
"""Put SK1-6 and LED1-6 on the schematic so Update PCB can carry KEY/PIXEL.

The sockets and pixels were PCB-only. EasyEDA's ratsnest comes from the
schematic netlist, so those nets never arrived. This file places the same
devices the PCB already has, copies the PCB uniqueIds ($1-$12), and joins
each pin to its net with a two-point stub plus a flag or netport.

Does not call openProject (that discards unsaved edits). Does not touch
the MCU block or the existing KEY/PIXEL netports on U3.

The EasyEDA SK6812MINI-E *symbol* names its pins GND/DIN/VDD/DOUT as
numbers 1/2/3/4. The *footprint* on the PCB (and the datasheet
params.PIXEL_PAD_SIGNALS) is 1=VDD, 2=DOUT, 3=GND, 4=DIN. Update PCB
matches by pin number, so stubs here follow the footprint numbers, not
the symbol's drawn names.
"""
import json
import sys
import time

import params
from bridge import execute
from schematic_tidy import open_schematic, pin_on_any_wire, save_schematic, snapshot

# PCB uniqueIds from place_mcu / build.py. Read back and asserted, not trusted
# blind, in pcb_field_uids().
SK_UID = [f"${i}" for i in range(1, 7)]
LED_UID = [f"${i}" for i in range(7, 13)]

# Below the existing MCU block (extent ~y 896). Schematic units: 0.01 inch.
X0 = 80
PITCH = 170
SK_Y = 1020
LED_Y = 1140


def pcb_field_uids():
    js = (
        "const pcbs = await eda.dmt_Pcb.getAllPcbsInfo(); "
        "if (!pcbs || !pcbs.length) return {error: 'no PCB'}; "
        "let doc = await eda.dmt_SelectControl.getCurrentDocumentInfo(); "
        "if (!(doc && doc.documentType === 3 && doc.uuid === pcbs[0].uuid)) { "
        "await eda.dmt_EditorControl.openDocument(pcbs[0].uuid); "
        "} "
        "const all = await eda.pcb_PrimitiveComponent.getAll(); "
        "const out = {}; "
        "for (const c of all || []) { "
        "const des = c.getState_Designator() || ''; "
        "if (des.startsWith('SK') || des.startsWith('LED')) { "
        "out[des] = c.getState_UniqueId(); "
        "} "
        "} "
        "return out;"
    )
    got = execute(js, timeout=30)
    if got.get("error"):
        raise SystemExit(got["error"])
    want = {f"SK{i}": SK_UID[i - 1] for i in range(1, 7)}
    want.update({f"LED{i}": LED_UID[i - 1] for i in range(1, 7)})
    bad = [f"{d} uid={got.get(d)!r} wanted {u!r}" for d, u in want.items() if got.get(d) != u]
    if bad:
        raise AssertionError("PCB field uniqueIds: " + "; ".join(bad))
    print("  PCB uniqueIds $1-$12 on SK1-6 / LED1-6")
    return want


def delete_existing_keys(parts, wires):
    """Drop a previous run of this file: SK/LED parts plus anything we
    parked below the MCU block (flags, ports, stubs at y >= 960).
    """
    ids = []
    for p in parts:
        des = p.get("des") or ""
        if p.get("type") == "part" and des.startswith(("SK", "LED")):
            ids.append(p["id"])
        elif p.get("type") in ("netflag", "netport") and p.get("y", 0) >= 960:
            ids.append(p["id"])
    if ids:
        ok = execute("return await eda.sch_PrimitiveComponent.delete(" + json.dumps(ids) + ");")
        print(f"  deleted {len(ids)} key-field components {ok}")
    wids = []
    for w in wires:
        pts = []
        line = w.get("line")
        if line and isinstance(line[0], (int, float)):
            pts = list(zip(line[0::2], line[1::2]))
        if any(y >= 960 for _, y in pts):
            wids.append(w["id"])
    if wids:
        ok = execute("return await eda.sch_PrimitiveWire.delete(" + json.dumps(wids) + ");")
        print(f"  deleted {len(wids)} key-field wires {ok}")


def place_one(uuid, x, y, des, uid):
    js = (
        "const dev = {libraryUuid: "
        + json.dumps(params.LIB_UUID)
        + ", uuid: "
        + json.dumps(uuid)
        + "}; "
        f"const c = await eda.sch_PrimitiveComponent.create("
        f"dev, {x}, {y}, undefined, 0, false, true, true); "
        "if (!c) throw new Error('create returned nothing for ' + "
        + json.dumps(des)
        + "); "
        "const id = c.primitiveId; "
        "const back = await eda.sch_PrimitiveComponent.modify(id, {"
        f"designator: {json.dumps(des)}, "
        f"uniqueId: {json.dumps(uid)}, "
        "addIntoPcb: true, addIntoBom: true"
        "}); "
        "if (!back) throw new Error('modify returned nothing for ' + "
        + json.dumps(des)
        + "); "
        "const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(id); "
        "return {id, des: back.getState_Designator(), uid: back.getState_UniqueId(), "
        "pins: (pins || []).map(p => ({n: p.getState_PinName() || '', "
        "num: p.getState_PinNumber() || '', x: p.getState_X(), y: p.getState_Y()}))};"
    )
    got = execute(js, timeout=30)
    if got["des"] != des:
        raise AssertionError(f"designator {des!r} read back {got['des']!r}")
    if got["uid"] != uid:
        raise AssertionError(f"uniqueId {uid!r} read back {got['uid']!r}")
    return got


def pin_by_num(part, num):
    hits = [p for p in part["pins"] if str(p["num"]) == str(num)]
    if len(hits) != 1:
        raise AssertionError(f"{part['des']} pin {num}: {hits}")
    return hits[0]


def stub(pin, end, net, label):
    """Two-point wire, net named explicitly. Different nets must not share
    a vertex -- EasyEDA merges touching same-net stubs and can reassign
    the combined object's net if a different net touches (pcb/README.md).
    """
    a = (pin["x"], pin["y"])
    if a[0] != end[0] and a[1] != end[1]:
        raise AssertionError(f"{label} stub is not Manhattan: {a} -> {end}")
    flat = f"[{a[0]},{a[1]},{end[0]},{end[1]}]"
    js = (
        f"const w = await eda.sch_PrimitiveWire.create({flat}, "
        + json.dumps(net)
        + ", undefined, undefined, undefined); "
        "if (!w) throw new Error('wire create returned nothing for ' + "
        + json.dumps(label)
        + "); "
        "return {id: w.primitiveId, net: w.getState_Net()};"
    )
    got = execute(js)
    if got["net"] != net:
        # same retry as schematic.py's assert_power_flags
        for _ in range(3):
            time.sleep(0.4)
            got["net"] = execute(
                f'const w = await eda.sch_PrimitiveWire.get("{got["id"]}"); '
                "return w ? w.getState_Net() : null;"
            )
            if got["net"] == net:
                break
    if got["net"] != net:
        raise AssertionError(f"{label}: stub net {got['net']!r}, wanted {net!r}")
    return got


def netport(net, x, y):
    js = (
        f'const p = await eda.sch_PrimitiveComponent.createNetPort("BI", '
        + json.dumps(net)
        + f", {x}, {y}, 0, false); "
        "return p ? p.primitiveId : null;"
    )
    pid = execute(js)
    if not pid:
        raise AssertionError(f"netport {net} create returned nothing at {(x, y)}")
    return pid


def netflag(kind, net, x, y):
    js = (
        f"const f = await eda.sch_PrimitiveComponent.createNetFlag("
        + json.dumps(kind)
        + ", "
        + json.dumps(net)
        + f", {x}, {y}, 0, false); "
        "return f ? f.primitiveId : null;"
    )
    pid = execute(js)
    if not pid:
        raise AssertionError(f"{kind} {net} flag create returned nothing at {(x, y)}")
    return pid


def join_port(pin, net, dx, dy, label):
    end = (pin["x"] + dx, pin["y"] + dy)
    netport(net, end[0], end[1])
    stub(pin, end, net, label)


def join_flag(pin, kind, net, dx, dy, label):
    end = (pin["x"] + dx, pin["y"] + dy)
    netflag(kind, net, end[0], end[1])
    stub(pin, end, net, label)


def wire_socket(part, i):
    key = f"KEY{i}"
    p1 = pin_by_num(part, "1")
    p2 = pin_by_num(part, "2")
    join_port(p1, key, -30, 0, f"{part['des']}.1-{key}")
    join_flag(p2, "Ground", "GND", 30, 0, f"{part['des']}.2-GND")


def wire_led(part, i):
    """Pin numbers follow the PCB/datasheet, not the symbol names."""
    vdd = pin_by_num(part, "1")   # symbol draws this as GND
    dout = pin_by_num(part, "2")  # symbol draws this as DIN
    gnd = pin_by_num(part, "3")   # symbol draws this as VDD
    din = pin_by_num(part, "4")   # symbol draws this as DOUT
    din_net = "PIXEL" if i == 0 else f"PIXEL{i}"
    join_flag(vdd, "Power", "3V3", -30, 0, f"{part['des']}.1-3V3")
    join_flag(gnd, "Ground", "GND", 30, 0, f"{part['des']}.3-GND")
    join_port(din, din_net, 30, 0, f"{part['des']}.4-{din_net}")
    if i < 5:
        dout_net = f"PIXEL{i + 1}"
        join_port(dout, dout_net, -30, 0, f"{part['des']}.2-{dout_net}")


def assert_wired(parts, wires):
    want = {}
    for i in range(6):
        want[("SK" + str(i + 1), "1")] = f"KEY{i}"
        want[("SK" + str(i + 1), "2")] = "GND"
        want[("LED" + str(i + 1), "1")] = "3V3"
        want[("LED" + str(i + 1), "3")] = "GND"
        want[("LED" + str(i + 1), "4")] = "PIXEL" if i == 0 else f"PIXEL{i}"
        if i < 5:
            want[("LED" + str(i + 1), "2")] = f"PIXEL{i + 1}"
    by = {p["des"]: p for p in parts if p.get("type") == "part"}
    bad = []
    for (des, num), net in want.items():
        pin = pin_by_num(by[des], num)
        hits = [h for h in pin_on_any_wire(pin, wires) if h]
        if hits != [net] and set(hits) != {net}:
            bad.append(f"{des}.{num} nets={hits} wanted {net}")
    if bad:
        raise AssertionError("key wiring: " + "; ".join(bad))
    print(f"  [ok ] {len(want)} SK/LED pins on the right nets")


def main():
    uids = pcb_field_uids()
    open_schematic()
    data = snapshot()
    delete_existing_keys(data["parts"], data["wires"])
    placed = []
    for i in range(6):
        x = X0 + i * PITCH
        sk = place_one(params.DEV_CHOC_SOCKET, x, SK_Y, f"SK{i + 1}", uids[f"SK{i + 1}"])
        led = place_one(params.DEV_PIXEL, x, LED_Y, f"LED{i + 1}", uids[f"LED{i + 1}"])
        wire_socket(sk, i)
        wire_led(led, i)
        placed.append(sk)
        placed.append(led)
        print(f"  {sk['des']}/{led['des']} uid={sk['uid']}/{led['uid']}")
    save_schematic()
    after = snapshot()
    assert_wired(after["parts"], after["wires"])


if __name__ == "__main__":
    main()
