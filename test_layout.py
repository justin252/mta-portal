"""Layout rules checked against the real BDF fonts and bitmaps: every string the board can
show must fit inside its box, use glyphs that draw something, and be visible on the LEDs."""
import os

import pytest
from PIL import Image

import layout
from logic import MAX_MINUTES
from simulate_display import font, glyph_metrics, ink_right
from weather import CONDITIONS, DEFAULT_CONDITION, NIGHT, format_hi_lo, format_temperature

ROOT = os.path.dirname(os.path.abspath(__file__))
FIELDS = {f[0]: f[1:] for f in layout.TRAIN_FIELDS + layout.WEATHER_FIELDS}  # field -> (role, box, y)


def worst_cases():
    """(field, text) for every shape of string the board can display."""
    cases = []
    for station in layout.STATIONS.values():
        cases += [('north', station['north']), ('south', station['south'])]
    widest = '%d,%d,%d' % ((MAX_MINUTES,) * 3)
    for times in (widest, '-,-,-', '0,0,0'):
        cases += [('north_times', times), ('south_times', times)]
    for label in sorted({c[3] for c in CONDITIONS} | {DEFAULT_CONDITION[1], '--'}):
        cases.append(('condition', label))
    for status in ('•••', 'offline'):
        cases += [('north_status', status), ('south_status', status)]
    for temp in (-40, -9, 0, 9, 99, 100, 120):
        cases.append(('temp', format_temperature(temp)))
    # NYC's coldest day on record was a high in the single digits: -5 covers it
    for hi, lo in ((104, 88), (-5, -15), (99, -9), (61, 45)):
        cases.append(('hi_lo', format_hi_lo(hi, lo)))
    for clock in ('12:52', '10:47', '11:11', '1:11', '6:05'):
        cases.append(('clock', clock))
    return cases


@pytest.mark.parametrize('field,text', worst_cases())
def test_text_fits_in_its_box_and_has_glyphs(field, text):
    role, box, _ = FIELDS[field]
    fnt = font(role)
    # A glyph can exist yet draw nothing (spleen-5x8 shipped a blank degree sign): require ink
    missing = [ch for ch in text if ch != ' ' and not any(fnt['glyphs'].get(ord(ch), {}).get('bitmap', []))]
    assert not missing, '%r: %s has no visible glyph for %r (the board would show a gap)' % (
        text, layout.FONTS[role], missing)
    x = layout.centered_x(text, glyph_metrics(role), box)
    left = x + fnt['glyphs'][ord(text[0])]['bbx'][2]
    right = ink_right(fnt, text, x)
    assert box[0] <= left and right <= box[0] + box[1], '%r spans x=%d..%d, outside its box %d..%d' % (
        text, left, right - 1, box[0], box[0] + box[1] - 1)


def test_centering_is_symmetric():
    # odd leftover pixels go to the right; never more than one
    role, box, _ = FIELDS['north']
    for text in ('Manhattan', 'Queens', 'Church Av'):
        x = layout.centered_x(text, glyph_metrics(role), box)
        left_margin = x + font(role)['glyphs'][ord(text[0])]['bbx'][2] - box[0]
        right_margin = box[0] + box[1] - ink_right(font(role), text, x)
        assert right_margin - left_margin in (0, 1), (text, left_margin, right_margin)


def rows_used(field):
    """Screen rows any glyph of this field's font can touch (Label placement formula)."""
    role, _, y = FIELDS[field]
    fnt = font(role)
    rows = set()
    for code, glyph in fnt['glyphs'].items():
        if not 32 <= code < 127 and chr(code) not in '°•':
            continue  # printable ASCII, degree sign and bullet are all the board renders
        _, h, _, yoff = glyph['bbx']
        top = y - h - yoff + fnt['ascent'] // 2
        rows.update(range(top, top + h))
    return rows


@pytest.mark.parametrize('fields', [layout.TRAIN_FIELDS, layout.WEATHER_FIELDS], ids=['train', 'weather'])
def test_rows_on_screen_and_not_overlapping(fields):
    # Fields in the same box must not share rows. X_status shares X_times's row (only one of
    # them has text at a time), so they form one slot. Different boxes may share rows.
    slots = {}
    for name, _, box, _ in fields:
        rows = rows_used(name)
        assert min(rows) >= 0 and max(rows) < layout.HEIGHT, '%s spans rows %d..%d' % (
            name, min(rows), max(rows))
        slots.setdefault((box, name.replace('_status', '_times')), set()).update(rows)
    for box in {b for b, _ in slots}:
        names = sorted((n for b, n in slots if b == box), key=lambda n: min(slots[(box, n)]))
        for a, b in zip(names, names[1:]):
            overlap = slots[(box, a)] & slots[(box, b)]
            assert not overlap, '%s and %s share rows %s' % (a, b, sorted(overlap))


@pytest.mark.parametrize('role', sorted(layout.COLORS))
def test_text_color_visible_on_leds(role):
    # Protomatter keeps only the top BIT_DEPTH bits of each channel: below 64 at depth 2 is off
    rgb = [(layout.COLORS[role] >> s) & 0xFF for s in (16, 8, 0)]
    levels = [c >> (8 - layout.BIT_DEPTH) for c in rgb]
    assert max(levels) > 0, '%s color #%06x is black on the LEDs' % (role, layout.COLORS[role])


BOX_ART = sorted({s['bitmap'] for s in layout.STATIONS.values()} | {c[2] for c in CONDITIONS} | set(NIGHT.values()))
ALL_BITMAPS = BOX_ART + list(layout.ART)


def lit(bitmap):
    img = Image.open(os.path.join(ROOT, bitmap)).convert('RGB')
    return [(x, y) for x in range(layout.WIDTH) for y in range(layout.HEIGHT) if img.getpixel((x, y)) != (0, 0, 0)]


@pytest.mark.parametrize('bitmap', ALL_BITMAPS)
def test_bitmap_fills_screen(bitmap):
    assert Image.open(os.path.join(ROOT, bitmap)).size == (layout.WIDTH, layout.HEIGHT)


@pytest.mark.parametrize('bitmap', ALL_BITMAPS)
def test_bitmap_visible_on_leds(bitmap):
    # A lit pixel with every channel below 64 is black on the matrix (bit depth 2): art drawn
    # in those colors silently loses detail on the board (the old train's windows and door did)
    img = Image.open(os.path.join(ROOT, bitmap)).convert('RGB')
    shift = 8 - layout.BIT_DEPTH
    colors = {c for _, c in img.getcolors(layout.WIDTH * layout.HEIGHT)}
    dark = sorted(p for p in colors if p != (0, 0, 0) and max(c >> shift for c in p) == 0)
    assert not dark, '%s has colors the LEDs show as black: %s' % (bitmap, dark[:5])


@pytest.mark.parametrize('bitmap', BOX_ART)
def test_logo_and_icon_stay_in_left_box_below_clock(bitmap):
    pts = lit(bitmap)
    clock_bottom = max(rows_used('clock'))
    left, width = layout.LEFT_BOX
    assert min(x for x, _ in pts) >= left and max(x for x, _ in pts) < left + width, \
        '%s spills out of the left box (columns %d..%d)' % (bitmap, left, left + width - 1)
    assert min(y for _, y in pts) >= clock_bottom + 2, \
        '%s reaches row %d: needs a clear row under the clock (ends row %d)' % (
            bitmap, min(y for _, y in pts), clock_bottom)


@pytest.mark.parametrize('bitmap', BOX_ART)
def test_logo_and_icon_centered_in_left_box(bitmap):
    xs = [x for x, _ in lit(bitmap)]
    center = layout.LEFT_BOX[0] + (layout.LEFT_BOX[1] - 1) / 2
    assert abs((min(xs) + max(xs)) / 2 - center) <= 1, '%s is off-center in the left box' % bitmap
