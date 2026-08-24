"""Export the live EasyEDA PCB's Gerber, BOM, and pick-and-place files.

Unlike ``build.export_fabrication()``, this writes the returned bytes so
the exact verified revision can be uploaded to JLCPCB.

    python3 export_manufacturing.py
"""

import base64
import io
import os
import re
import zipfile

import build
from bridge import execute


OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "out", "manufacturing")

EXPORTS = {
    "gerber": ('eda.pcb_ManufactureData.getGerberFile("canopy_macropad")',
               "canopy_macropad-gerber.zip"),
    "bom": ('eda.pcb_ManufactureData.getBomFile("canopy_macropad")',
            "canopy_macropad-bom.xlsx"),
    "cpl": ('eda.pcb_ManufactureData.getPickAndPlaceFile("canopy_macropad")',
            "canopy_macropad-cpl.xlsx"),
}


def fetch(expression):
    js = f"""
    const f=await {expression};
    if(!f) return {{error:"export returned undefined"}};
    const bytes=new Uint8Array(await f.arrayBuffer());
    let bin="";
    const chunk=0x8000;
    for(let i=0;i<bytes.length;i+=chunk)
      bin+=String.fromCharCode.apply(null,bytes.subarray(i,i+chunk));
    return {{name:f.name||"",type:f.type||"",size:bytes.length,b64:btoa(bin)}};
    """
    got = execute(js, 180)
    if got.get("error"):
        raise SystemExit(got["error"])
    data = base64.b64decode(got["b64"])
    if not data or len(data) != got["size"]:
        raise SystemExit(f"export size mismatch: {got['size']} / {len(data)}")
    return got, data


def inspect_gerber(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
    if not any("GTL" in name.upper() or "TOP" in name.upper() for name in names):
        raise SystemExit(f"Gerber archive has no top copper: {names}")
    if not any("GBL" in name.upper() or "BOTTOM" in name.upper() for name in names):
        raise SystemExit(f"Gerber archive has no bottom copper: {names}")
    if not any("DRL" in name.upper() or "DRILL" in name.upper()
               or "TXT" in name.upper() for name in names):
        raise SystemExit(f"Gerber archive has no drill file: {names}")
    inner = [name for name in names
             if "INNER" in name.upper()
             or re.search(r"\.G(?:1|2|3|4)L$", name, re.IGNORECASE)]
    if inner:
        raise SystemExit(f"two-layer Gerber unexpectedly contains inner copper: {inner}")
    return len(names)


def xlsx_text_and_rows(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = []
        rows = 0
        for name in archive.namelist():
            if not name.endswith(".xml"):
                continue
            text = archive.read(name).decode("utf-8", "replace")
            xml.append(text)
            if name.startswith("xl/worksheets/"):
                rows += len(re.findall(r"<row(?:\s|>)", text))
    return "\n".join(xml), rows


def inspect_bom(data):
    flattened, rows = xlsx_text_and_rows(data)
    for wanted in ("C179171", "W25Q64JVSSIQ", "U1"):
        if wanted not in flattened:
            raise SystemExit(f"BOM does not contain {wanted}")
    if "C2940195" in flattened or "W25Q64JVXGIQ" in flattened:
        raise SystemExit("BOM still contains the unavailable XSON flash")
    return rows


def inspect_cpl(data):
    flattened, rows = xlsx_text_and_rows(data)
    if "U1" not in flattened:
        raise SystemExit("CPL does not contain U1")
    return rows


def main():
    build.open_project_pcb()
    os.makedirs(OUT, exist_ok=True)
    results = {}
    for label, (expression, filename) in EXPORTS.items():
        meta, data = fetch(expression)
        path = os.path.join(OUT, filename)
        with open(path, "wb") as handle:
            handle.write(data)
        results[label] = (path, len(data))
        print(f"exported {label}: {path} ({len(data)} bytes; "
              f"EasyEDA name={meta['name']!r}, type={meta['type']!r})")

    with open(results["gerber"][0], "rb") as handle:
        print(f"Gerber entries: {inspect_gerber(handle.read())}")
    with open(results["bom"][0], "rb") as handle:
        print(f"BOM rows: {inspect_bom(handle.read())}")
    with open(results["cpl"][0], "rb") as handle:
        print(f"CPL rows: {inspect_cpl(handle.read())}")
    print("manufacturing export verified")


if __name__ == "__main__":
    main()
