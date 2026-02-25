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
        # 'M' in 'Manhattan', tom-thumb at x=18 y=4: first lit pixel at (18, 2)
        assert self.img.getpixel((18, 2)) == (0x44, 0x44, 0x44)

    def test_label_m_gap(self):
        # 'M' bitmap row 0 is 0xA0 (10100000) — middle pixel (19,2) is black
        assert self.img.getpixel((19, 2)) == (0, 0, 0)

    def test_time_3_top(self):
        # '3' in north times, spleen at x=18 y=11: row 1 (0x60) lights (19, 9)
        assert self.img.getpixel((19, 9)) == (0xDD, 0x80, 0x00)

    def test_black_background(self):
        # Right side of display, no text rendered here
        assert self.img.getpixel((30, 0)) == (0, 0, 0)


class TestReferenceImages:
    """Compare full renders against stored reference images."""

    def _compare(self, actual, ref_path, tmp_path):
        ref = Image.open(ref_path).convert('RGB')
        assert actual.size == ref.size, f"Size mismatch: {actual.size} vs {ref.size}"
        mismatches = []
        for y in range(actual.size[1]):
            for x in range(actual.size[0]):
                if actual.getpixel((x, y)) != ref.getpixel((x, y)):
                    mismatches.append((x, y, actual.getpixel((x, y)), ref.getpixel((x, y))))
        if mismatches:
            actual_path = tmp_path / os.path.basename(ref_path).replace('.png', '_actual.png')
            actual.save(actual_path)
            pytest.fail(
                f"{len(mismatches)} pixel mismatches (saved actual to {actual_path}). "
                f"First: ({mismatches[0][0]},{mismatches[0][1]}) "
                f"got {mismatches[0][2]} expected {mismatches[0][3]}"
            )

    def test_l_train(self, tmp_path):
        actual = render_display('L', '3,8,14', '1,5,12')
        self._compare(actual, os.path.join(FIXTURES, 'ref_L.png'), tmp_path)

    def test_g_train(self, tmp_path):
        actual = render_display('G', '2,7,15', '4,9,20')
        self._compare(actual, os.path.join(FIXTURES, 'ref_G.png'), tmp_path)

    def test_weather(self, tmp_path):
        actual = render_weather_display('cloud', format_temperature(42), 'Cloudy')
        self._compare(actual, os.path.join(FIXTURES, 'ref_weather.png'), tmp_path)


class TestWeatherPixelSpotChecks:
    """Verify weather screen rendering."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.img = render_weather_display('cloud', format_temperature(42), 'Cloudy')

    def test_condition_label_pixel(self):
        # 'C' in 'Cloudy', tom-thumb at x=18 y=10: first lit pixel at (19, 8)
        assert self.img.getpixel((19, 8)) == (0x44, 0x44, 0x44)

    def test_temp_pixel(self):
        # '4' in '42°F', spleen at x=18 y=22: first lit pixel at (18, 20)
        assert self.img.getpixel((18, 20)) == (0xDD, 0x80, 0x00)

    def test_weather_bitmap_present(self):
        # Cloud bitmap should have non-black pixels in left 18px
        has_content = any(
            self.img.getpixel((x, y)) != (0, 0, 0)
            for x in range(18) for y in range(32)
        )
        assert has_content
