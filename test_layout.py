"""Layout rules checked against the real BDF fonts and bitmaps: every string the board can
show must fit on the 64x32 matrix, use glyphs that draw something, and be visible on the LEDs."""
import os

import pytest
from PIL import Image

import layout
from logic import MAX_MINUTES
from simulate_display import font
from weather import CONDITION_MAP, DEFAULT_CONDITION, format_temperature

ROOT = os.path.dirname(os.path.abspath(__file__))
FIELDS = {field: (role, x, y) for field, role, x, y in layout.TRAIN_FIELDS + layout.WEATHER_FIELDS}


def worst_cases():
    """(field, text) for every shape of string the board can display."""
    cases = []
    for station in layout.STATIONS.values():
        cases += [('north', station['north']), ('south', station['south'])]
    widest = '%d,%d,%d' % ((MAX_MINUTES,) * 3)
    for times in (widest, '-,-,-', '0,0,0'):
        cases += [('north_times', times), ('south_times', times)]
    for label in sorted({v[1] for v in CONDITION_MAP.values()} | {DEFAULT_CONDITION[1], '--'}):
        cases.append(('condition', label))
    for temp in (-40, -9, 0, 9, 99, 100, 120):
        cases.append(('temp', format_temperature(temp)))
    return cases


def ink_right(fnt, text, x):
    """One past the last lit column (trailing glyph spacing draws nothing)."""
    right, cursor = x, x
    for ch in text:
        glyph = fnt['glyphs'][ord(ch)]
        w, _, xoff, _ = glyph['bbx']
        if any(glyph['bitmap']):
            right = max(right, cursor + xoff + w)
        cursor += glyph['dwidth']
    return right


@pytest.mark.parametrize('field,text', worst_cases())
def test_text_fits_and_has_glyphs(field, text):
    role, x, _ = FIELDS[field]
    fnt = font(role)
    # A glyph can exist yet draw nothing (spleen-5x8 shipped a blank degree sign): require ink
    missing = [ch for ch in text if ch != ' ' and not any(fnt['glyphs'].get(ord(ch), {}).get('bitmap', []))]
    assert not missing, '%r: %s has no visible glyph for %r (the board would show a gap)' % (
        text, layout.FONTS[role], missing)
    right = ink_right(fnt, text, x)
    assert right <= layout.WIDTH, '%r is clipped: ink ends at x=%d, display is %dpx wide' % (
        text, right - 1, layout.WIDTH)


def rows_used(field):
    """Screen rows any glyph of this field's font can touch (Label placement formula)."""
    role, _, y = FIELDS[field]
    fnt = font(role)
    rows = set()
    for code, glyph in fnt['glyphs'].items():
        if not 32 <= code < 127 and chr(code) != '°':
            continue  # printable ASCII plus the degree sign is all the board renders
        _, h, _, yoff = glyph['bbx']
        top = y - h - yoff + fnt['ascent'] // 2
        rows.update(range(top, top + h))
    return rows


@pytest.mark.parametrize('fields', [layout.TRAIN_FIELDS, layout.WEATHER_FIELDS], ids=['train', 'weather'])
def test_rows_on_screen_and_not_overlapping(fields):
    names = [f[0] for f in fields]
    for name in names:
        rows = rows_used(name)
        assert min(rows) >= 0 and max(rows) < layout.HEIGHT, '%s spans rows %d..%d' % (
            name, min(rows), max(rows))
    for a, b in zip(names, names[1:]):
        overlap = rows_used(a) & rows_used(b)
        assert not overlap, '%s and %s share rows %s' % (a, b, sorted(overlap))


@pytest.mark.parametrize('role', sorted(layout.COLORS))
def test_text_color_visible_on_leds(role):
    # Protomatter keeps only the top BIT_DEPTH bits of each channel: below 64 at depth 2 is off
    rgb = [(layout.COLORS[role] >> s) & 0xFF for s in (16, 8, 0)]
    levels = [c >> (8 - layout.BIT_DEPTH) for c in rgb]
    assert max(levels) > 0, '%s color #%06x is black on the LEDs' % (role, layout.COLORS[role])


# (bitmap, where its screen's text starts, minimum black columns between art and text)
CLEARANCE = [(s['bitmap'], layout.TEXT_X, 2) for s in layout.STATIONS.values()] + \
    [(icon, layout.TEXT_X, 2) for icon in sorted({v[0] for v in CONDITION_MAP.values()})]


@pytest.mark.parametrize('bitmap', [c[0] for c in CLEARANCE] + [layout.TRAIN_ART])
def test_bitmap_fills_screen(bitmap):
    assert Image.open(os.path.join(ROOT, bitmap)).size == (layout.WIDTH, layout.HEIGHT)


@pytest.mark.parametrize('bitmap,text_x,gap', CLEARANCE)
def test_bitmap_clear_of_text(bitmap, text_x, gap):
    img = Image.open(os.path.join(ROOT, bitmap)).convert('RGB')
    lit = [x for x in range(layout.WIDTH) for y in range(layout.HEIGHT) if img.getpixel((x, y)) != (0, 0, 0)]
    assert max(lit) + 1 + gap <= text_x, '%s ends at column %d: needs %d clear columns before text at x=%d' % (
        bitmap, max(lit), gap, text_x)
