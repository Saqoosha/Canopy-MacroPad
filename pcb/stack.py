"""Set the live PCB to the copper-layer count declared in params.

Inner pours must be deleted before reducing the stack. EasyEDA otherwise
retains primitives on layers that no longer manufacture, which makes a
two-layer quote look valid while silently discarding power copper.

    python3 stack.py --apply
"""

import sys

import build
import params
from bridge import execute


def state():
    return execute(
        "const n=await eda.pcb_Layer.getTheNumberOfCopperLayers();"
        "const ls=await eda.pcb_Layer.getAllLayers();"
        "const ps=await eda.pcb_PrimitivePour.getAll();"
        "return {copper:n,layers:(ls||[]).filter(l=>[1,2,15,16].includes(l.id))"
        ".map(l=>[l.id,l.name,l.layerStatus,l.type]),"
        "pours:(ps||[]).map(p=>[p.net,p.layer])};"
    )


def apply():
    js = f"""
    const out={{}};
    const pours=await eda.pcb_PrimitivePour.getAll();
    const ids=(pours||[]).map(p=>p.primitiveId);
    out.removed=ids.length ? await eda.pcb_PrimitivePour.delete(ids) : true;
    out.set=await eda.pcb_Layer.setTheNumberOfCopperLayers({params.BOARD_LAYERS});
    out.copper=await eda.pcb_Layer.getTheNumberOfCopperLayers();
    out.pours=(await eda.pcb_PrimitivePour.getAll()||[])
      .map(p=>[p.net,p.layer]);
    return out;
    """
    got = execute(js, timeout=180.0)
    if not got["removed"] or not got["set"]:
        raise SystemExit(f"stack conversion failed: {got}")
    if got["copper"] != params.BOARD_LAYERS or got["pours"]:
        raise SystemExit(f"stack did not settle at two clean layers: {got}")
    print(f"  copper layers: {got['copper']}; old pours removed")


def main():
    build.open_project_pcb()
    before = state()
    print(f"  before: {before['copper']} copper, pours {before['pours']}")
    if "--apply" not in sys.argv:
        print("  report only -- pass --apply")
        return
    apply()
    after = state()
    if after["copper"] != params.BOARD_LAYERS:
        raise SystemExit(f"wanted {params.BOARD_LAYERS} layers, got {after}")
    print(f"  after: {after['copper']} copper, pours {after['pours']}")


if __name__ == "__main__":
    main()
