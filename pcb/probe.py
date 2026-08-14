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
