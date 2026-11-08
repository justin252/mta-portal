import glob
import os
import sys
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from simulate_display import font, parse_bdf, render_text, SCRIPT_DIR

FIXTURES = os.path.join(os.path.dirname(__file__), 'test_fixtures')


class TestParseBdf:
    def test_tom_thumb_metrics(self):
        font = parse_bdf(os.path.join(SCRIPT_DIR, 'fonts/tom-thumb.bdf'))
        assert font['ascent'] == 5
        assert font['descent'] == 1
        assert font['bbox_h'] == 6

    def test_spleen_metrics(self):
        font = parse_bdf(os.path.join(SCRIPT_DIR, 'fonts/spleen-5x8.bdf'))
        assert font['ascent'] == 7
        assert font['descent'] == 1
        assert font['bbox_h'] == 8

    def test_tom_thumb_digit_zero(self):
        font = parse_bdf(os.path.join(SCRIPT_DIR, 'fonts/tom-thumb.bdf'))
        g = font['glyphs'][ord('0')]
        assert g['bbx'] == (3, 5, 0, 0)
        assert g['bitmap'] == [0x60, 0xA0, 0xA0, 0xA0, 0xC0]

    def test_spleen_digit_zero(self):
        font = parse_bdf(os.path.join(SCRIPT_DIR, 'fonts/spleen-5x8.bdf'))
        g = font['glyphs'][ord('0')]
        assert g['bbx'] == (5, 8, 0, -1)
        assert g['bitmap'] == [0x00, 0x60, 0x90, 0xB0, 0xD0, 0x90, 0x60, 0x00]

    def test_glyph_count(self):
        tom = parse_bdf(os.path.join(SCRIPT_DIR, 'fonts/tom-thumb.bdf'))
        spleen = parse_bdf(os.path.join(SCRIPT_DIR, 'fonts/spleen-5x8.bdf'))
        assert len(tom['glyphs']) > 90  # at least ASCII printable
        assert len(spleen['glyphs']) > 90


class TestTextPlacementFormula:
    """render_text at fixed positions: glyph top = y - bbx_h - bbx_yoff + ascent // 2.
    Expectations derived from board captures, independent of layout.py."""

    def canvas(self, role, text, x, y):
        img = Image.new('RGB', (64, 32))
        render_text(img, font(role), text, x, y, (255, 255, 255))
        return img

    def test_label_font_cap_top(self):
        # 'M' in tom-thumb (BBX 3 5 0 0, ascent 5): top = 4 - 5 - 0 + 2 = 1
        img = self.canvas('label', 'M', 18, 4)
        assert img.getpixel((18, 1)) == (255, 255, 255) and img.getpixel((18, 0)) == (0, 0, 0)
        assert img.getpixel((19, 1)) == (0, 0, 0)  # 'M' row 0 is 0xA0: gap in the middle

    def test_time_font_digit_row(self):
        # '3' in spleen (BBX 5 8 0 -1, ascent 7): top = 11 - 8 + 1 + 3 = 7, row 1 (0x60) lights x+1
        img = self.canvas('time', '3', 18, 11)
        assert img.getpixel((19, 8)) == (255, 255, 255) and img.getpixel((19, 7)) == (0, 0, 0)

    def test_clock_font_is_compact(self):
        # 1px between glyphs: '1' (2 wide) then '2' starts at x+3
        img = self.canvas('clock', '12', 0, 7)
        assert img.getpixel((3, 4)) == (255, 255, 255) and img.getpixel((2, 4)) == (0, 0, 0)


GOLDENS = sorted(glob.glob(os.path.join(FIXTURES, 'device', '*.png')))


@pytest.mark.parametrize('golden', GOLDENS, ids=os.path.basename)
def test_matches_board_capture(golden):
    """Board framebuffer captures are ground truth: the simulator must reproduce them pixel-exact.

    One per scenario, captured with `tools/portal.py goldens` (state embedded in the PNG).
    Re-capture after a layout change; a failure means the simulator no longer predicts the LEDs.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
    import portal
    state, device_px = portal.load_golden(golden)
    mismatches = portal.compare(device_px, portal.render_expected(state))
    assert not mismatches, '%d pixels differ from the board, first (x, y, board, sim): %s' % (
        len(mismatches), mismatches[0])


@pytest.mark.parametrize('golden', GOLDENS, ids=os.path.basename)
def test_board_capture_is_current(golden):
    """A capture taken before a scenario changed would still pass the test above: catch it."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
    import portal
    import scenarios
    captured, _ = portal.load_golden(golden)
    name = os.path.basename(golden)[:-len('.png')]
    assert name in scenarios.BY_NAME, 'capture for unknown scenario %r: delete it' % name
    want = scenarios.state(scenarios.BY_NAME[name])
    got = {k: captured.get(k) for k in want}
    assert got == want, 'capture for %s is out of date: make deploy, then make goldens' % name


def test_every_scenario_has_a_board_capture():
    import scenarios
    missing = [s['name'] for s in scenarios.SCENARIOS
               if os.path.join(FIXTURES, 'device', s['name'] + '.png') not in GOLDENS]
    assert not missing, 'capture with the board attached: make deploy goldens (%s)' % ', '.join(missing)
