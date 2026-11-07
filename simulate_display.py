#!/usr/bin/env python3
"""Simulate the MTA Portal 64x32 LED matrix display as a scaled PNG.

Renders from layout.py (the same spec app.py builds the board's display from) with the
same BDF fonts and BMP bitmaps. Pixel-exact against board captures in test_fixtures/device/.
"""

import argparse
import os
import sys
from PIL import Image

import layout
from weather import format_hi_lo, format_temperature, map_condition

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DISPLAY_W, DISPLAY_H = layout.WIDTH, layout.HEIGHT
SCALE = 10
STATIONS = layout.STATIONS
COLORS = {role: ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF) for role, c in layout.COLORS.items()}

_fonts = {}


def parse_bdf(path):
    """Parse a BDF font file. Returns dict with ascent, descent, bbox_h, glyphs."""
    glyphs = {}
    meta = {}
    with open(path) as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('FONT_ASCENT'):
            meta['ascent'] = int(line.split()[1])
        elif line.startswith('FONT_DESCENT'):
            meta['descent'] = int(line.split()[1])
        elif line.startswith('FONTBOUNDINGBOX'):
            parts = line.split()
            meta['bbox_h'] = int(parts[2])
        elif line.startswith('STARTCHAR'):
            encoding = dwidth = None
            bbx = (0, 0, 0, 0)
            bitmap = []
            i += 1
            while i < len(lines) and lines[i] != 'ENDCHAR':
                if lines[i].startswith('ENCODING'):
                    encoding = int(lines[i].split()[1])
                elif lines[i].startswith('DWIDTH'):
                    dwidth = int(lines[i].split()[1])
                elif lines[i].startswith('BBX'):
                    p = lines[i].split()
                    bbx = (int(p[1]), int(p[2]), int(p[3]), int(p[4]))
                elif lines[i] == 'BITMAP':
                    i += 1
                    while i < len(lines) and lines[i] != 'ENDCHAR':
                        bitmap.append(int(lines[i], 16))
                        i += 1
                    continue
                i += 1
            if encoding is not None:
                glyphs[encoding] = {'dwidth': dwidth, 'bbx': bbx, 'bitmap': bitmap}
        i += 1
    meta['glyphs'] = glyphs
    return meta


def font(role):
    """Parsed BDF font for a layout role ('label' or 'time'), cached."""
    if role not in _fonts:
        _fonts[role] = parse_bdf(os.path.join(SCRIPT_DIR, layout.FONTS[role]))
    return _fonts[role]


def text_width(fnt, text):
    """Pixel advance of text; missing glyphs draw nothing on the board either."""
    return sum(fnt['glyphs'][ord(ch)]['dwidth'] for ch in text if ord(ch) in fnt['glyphs'])


def render_text(canvas, font, text, x, y, color):
    """Render text onto canvas matching adafruit_display_text.label.Label positioning.

    Same formula as Label._update_text: glyph top = y - bbx_h - bbx_yoff + ascent // 2,
    then bitmap row r lands at top + r. Verified pixel-exact against board framebuffer
    captures (test_fixtures/device/).
    """
    y_offset = font['ascent'] // 2
    cursor_x = x
    for ch in text:
        glyph = font['glyphs'].get(ord(ch))
        if glyph is None:
            continue
        bbx_w, bbx_h, bbx_xoff, bbx_yoff = glyph['bbx']
        for r, row_bits in enumerate(glyph['bitmap']):
            screen_y = y - bbx_h - bbx_yoff + y_offset + r
            if not (0 <= screen_y < DISPLAY_H):
                continue
            for c in range(bbx_w):
                if row_bits & (0x80 >> c):
                    screen_x = cursor_x + bbx_xoff + c
                    if 0 <= screen_x < DISPLAY_W:
                        canvas.putpixel((screen_x, screen_y), color)
        cursor_x += glyph['dwidth']


def render_screen(state):
    """Render a screen state as app.py reports it: {'screen', 'texts', 'bitmap'}."""
    screen, texts = state['screen'], dict(state.get('texts', {}))
    if screen == 'train_art':
        return Image.open(os.path.join(SCRIPT_DIR, layout.TRAIN_ART)).convert('RGB')
    if screen in STATIONS:
        station = STATIONS[screen]
        fields, bitmap = layout.TRAIN_FIELDS, state.get('bitmap', station['bitmap'])
        texts.setdefault('north', station['north'])
        texts.setdefault('south', station['south'])
    elif screen == 'weather':
        fields, bitmap = layout.WEATHER_FIELDS, state['bitmap']
    else:
        raise ValueError('unknown screen %r' % screen)
    canvas = Image.new('RGB', (DISPLAY_W, DISPLAY_H), (0, 0, 0))
    canvas.paste(Image.open(os.path.join(SCRIPT_DIR, bitmap)).convert('RGB'), (0, 0))
    for field, role, x, y in fields:
        render_text(canvas, font(role), texts.get(field, ''), x, y, COLORS[role])
    return canvas


def render_display(line='L', north='3,8,14', south='1,5,12'):
    """Render a train screen. Returns PIL Image (pre-scale)."""
    return render_screen({'screen': line, 'texts': {'north_times': north, 'south_times': south}})


def render_weather_display(condition='cloud', temp='42°F', label='Cloudy', hi_lo='H:48 L:37'):
    """Render the weather screen; condition is an icon name ('cloud') or bitmap filename."""
    bitmap = condition if condition.endswith('.bmp') else 'weather-%s.bmp' % condition
    return render_screen({'screen': 'weather', 'bitmap': bitmap,
                          'texts': {'condition': label, 'temp': temp, 'hi_lo': hi_lo}})


def led_view(img):
    """What the LEDs show: each channel keeps only its top BIT_DEPTH bits (Protomatter driver).

    Channels below 2**(8 - BIT_DEPTH) go dark, so dim art details vanish on the board.
    """
    top = 2 ** layout.BIT_DEPTH - 1
    shift = 8 - layout.BIT_DEPTH
    return img.point(lambda c: (c >> shift) * 255 // top)


def main():
    parser = argparse.ArgumentParser(description='Simulate MTA Portal LED matrix display')
    parser.add_argument('--line', choices=sorted(STATIONS), default='L')
    parser.add_argument('--north', default='3,8,14', help='Northbound arrival times')
    parser.add_argument('--south', default='1,5,12', help='Southbound arrival times')
    parser.add_argument('--train', action='store_true', help='Show full-screen train bitmap')
    parser.add_argument('--weather', action='store_true', help='Show weather screen')
    parser.add_argument('--code', type=int, default=3, help='WMO weather code (default 3, overcast)')
    parser.add_argument('--temp', type=float, default=42, help='Temperature in F')
    parser.add_argument('--hi', type=float, default=48, help="Today's high in F")
    parser.add_argument('--lo', type=float, default=37, help="Today's low in F")
    parser.add_argument('--led', action='store_true', help='Quantize colors to what the LEDs show')
    parser.add_argument('-o', '--output', default='simulated_display.png')
    args = parser.parse_args()

    if args.train:
        canvas = render_screen({'screen': 'train_art'})
    elif args.weather:
        bitmap, label = map_condition(args.code)
        canvas = render_weather_display(bitmap, format_temperature(args.temp), label,
                                        format_hi_lo(args.hi, args.lo))
    else:
        canvas = render_display(args.line, args.north, args.south)
    if args.led:
        canvas = led_view(canvas)
    canvas.resize((DISPLAY_W * SCALE, DISPLAY_H * SCALE), Image.NEAREST).save(args.output)
    print(args.output, file=sys.stderr)


if __name__ == '__main__':
    main()
