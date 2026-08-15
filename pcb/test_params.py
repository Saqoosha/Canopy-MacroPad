# pcb/test_params.py
"""Run with: python3 pcb/test_params.py"""
import sys

import params
import board_edge


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


def test_board_is_the_field_plus_the_mcu_bay_and_usb_tab():
    assert round(params.KEY_FIELD_W, 6) == 114.30
    assert round(params.BOARD_W - params.KEY_FIELD_W, 6) == round(
        params.MCU_BAY_W + params.USB_TAB_W, 6)
    assert 0 < params.BOARD_CORNER_RADIUS < params.BOARD_D / 2


def test_rounded_source_uses_easyeda_inverted_y_anchor():
    src = board_edge.source()
    assert src[0] == "R"
    assert round(src[1] * 0.0254, 6) == 0
    assert round(src[2] * 0.0254, 6) == round(params.BOARD_D, 6)
    assert round(src[4] * 0.0254, 6) == round(params.BOARD_D, 6)
    assert round(src[6] * 0.0254, 6) == round(params.BOARD_CORNER_RADIUS, 6)


if __name__ == "__main__":
    for fn in (
        test_six_switches_on_pitch,
        test_pitch_is_a_whole_number_of_mils,
        test_board_is_the_field_plus_the_mcu_bay_and_usb_tab,
        test_rounded_source_uses_easyeda_inverted_y_anchor,
    ):
        print(fn.__name__)
        fn()
    print("\nall checks passed")
    sys.exit(0)
