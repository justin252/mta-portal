import os
import sys
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from simulate_display import parse_bdf, render_display, render_weather_display, SCRIPT_DIR
from weather import format_temperature

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


class TestPixelSpotChecks:
    """Verify rendering math by checking specific pixel colors."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.img = render_display('L', '3,8,14', '1,5,12')

    def test_label_m_top_left(self):
        # 'M' in 'Manhattan', tom-thumb at x=18 y=4: top = 4 - 5 - 0 + 5//2 = 1 (board-verified)
        assert self.img.getpixel((18, 1)) == (0x44, 0x44, 0x44)

    def test_label_m_gap(self):
        # 'M' bitmap row 0 is 0xA0 (10100000) — middle pixel (19,1) is black
        assert self.img.getpixel((19, 1)) == (0, 0, 0)

    def test_time_3_top(self):
        # '3' in north times, spleen at x=18 y=11: top = 11 - 8 + 1 + 7//2 = 7, row 1 (0x60) lights (19, 8)
        assert self.img.getpixel((19, 8)) == (0xDD, 0x80, 0x00)

    def test_black_background(self):
        # Right side of display, no text rendered here
        assert self.img.getpixel((30, 0)) == (0, 0, 0)


DEVICE_CAPTURES = os.path.join(FIXTURES, 'device')


@pytest.mark.parametrize('capture', sorted(os.listdir(DEVICE_CAPTURES)))
def test_matches_board_capture(capture):
    """Board framebuffer dumps are ground truth: the simulator must reproduce them pixel-exact.

    Captured with `tools/portal.py shot` (raw [FB] lines from diag.py). Re-capture after any
    layout change; a failure here means the simulator no longer predicts the LEDs.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
    import portal
    with open(os.path.join(DEVICE_CAPTURES, capture)) as f:
        state, rows = portal.parse_dump(f.read().splitlines())
    mismatches = portal.compare(portal.decode_rgb565(rows), portal.render_expected(state))
    assert not mismatches, '%d pixels differ from the board, first (x, y, board, sim): %s' % (
        len(mismatches), mismatches[0])


class TestWeatherPixelSpotChecks:
    """Verify weather screen rendering."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.img = render_weather_display('cloud', format_temperature(42), 'Cloudy')

    def test_condition_label_pixel(self):
        # 'C' in 'Cloudy', tom-thumb at x=21 y=6: top = 6 - 5 - 0 + 5//2 = 3, C starts 1px in
        assert self.img.getpixel((22, 3)) == (0x44, 0x44, 0x44)

    def test_temp_pixel(self):
        # '4' in '42°F', spleen at x=21 y=16: top = 16 - 8 + 1 + 7//2 = 12, row 1 is lit
        assert self.img.getpixel((21, 13)) == (0xDD, 0x80, 0x00)

    def test_weather_bitmap_present(self):
        # Cloud bitmap should have non-black pixels in left 18px
        has_content = any(
            self.img.getpixel((x, y)) != (0, 0, 0)
            for x in range(18) for y in range(32)
        )
        assert has_content
