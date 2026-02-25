#!/usr/bin/env python3
"""Simulate the MTA Portal 64x32 LED matrix display as a scaled PNG."""

import argparse
import os
import sys
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DISPLAY_W, DISPLAY_H = 64, 32
SCALE = 10

STATIONS = {
    'L': {'north': 'Manhattan', 'south': 'Canarsie', 'bitmap': 'l-dashboard.bmp'},
    'G': {'north': 'Queens', 'south': 'Church Av', 'bitmap': 'g-dashboard.bmp'},
}

COLORS = {
    'label': (0x44, 0x44, 0x44),
    'time': (0xDD, 0x80, 0x00),
}


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


def render_text(canvas, font, text, x, y, color):
    """Render text onto canvas matching CircuitPython displayio.Label positioning.

    y is the label's vertical center. _y_offset = (bbox_h - descent) // 2.
    Each glyph's bitmap row r maps to cell_row = ascent - bbx_yoff - bbx_h + r.
    """
    y_offset = (font['bbox_h'] - font['descent']) // 2
    ascent = font['ascent']
    text_top = y - y_offset
    cursor_x = x
    for ch in text:
        glyph = font['glyphs'].get(ord(ch))
        if glyph is None:
            continue
        bbx_w, bbx_h, bbx_xoff, bbx_yoff = glyph['bbx']
        for r, row_bits in enumerate(glyph['bitmap']):
            screen_y = text_top + ascent - bbx_yoff - bbx_h + r
            if not (0 <= screen_y < DISPLAY_H):
                continue
            for c in range(bbx_w):
                if row_bits & (0x80 >> c):
                    screen_x = cursor_x + bbx_xoff + c
                    if 0 <= screen_x < DISPLAY_W:
                        canvas.putpixel((screen_x, screen_y), color)
        cursor_x += glyph['dwidth']


def main():
    parser = argparse.ArgumentParser(description='Simulate MTA Portal LED matrix display')
    parser.add_argument('--line', choices=['L', 'G'], default='L')
    parser.add_argument('--north', default='3,8,14', help='Northbound arrival times')
    parser.add_argument('--south', default='1,5,12', help='Southbound arrival times')
    parser.add_argument('--train', action='store_true', help='Show full-screen train bitmap')
    parser.add_argument('-o', '--output', default='simulated_display.png')
    args = parser.parse_args()

    if args.train:
        train_path = os.path.join(SCRIPT_DIR, 'train.bmp')
        if not os.path.exists(train_path):
            print("Error: train.bmp not found", file=sys.stderr)
            sys.exit(1)
        img = Image.open(train_path).convert('RGB')
        scaled = img.resize((DISPLAY_W * SCALE, DISPLAY_H * SCALE), Image.NEAREST)
        scaled.save(args.output)
        return

    canvas = render_display(args.line, args.north, args.south)
    scaled = canvas.resize((DISPLAY_W * SCALE, DISPLAY_H * SCALE), Image.NEAREST)
    scaled.save(args.output)


def render_display(line='L', north='3,8,14', south='1,5,12'):
    """Render 64x32 canvas matching the LED matrix. Returns PIL Image (pre-scale)."""
    station = STATIONS[line]
    font_label = parse_bdf(os.path.join(SCRIPT_DIR, 'fonts/tom-thumb.bdf'))
    font_time = parse_bdf(os.path.join(SCRIPT_DIR, 'fonts/spleen-5x8.bdf'))

    canvas = Image.new('RGB', (DISPLAY_W, DISPLAY_H), (0, 0, 0))
    dashboard = Image.open(os.path.join(SCRIPT_DIR, station['bitmap'])).convert('RGB')
    canvas.paste(dashboard, (0, 0))

    # Matches code.py lines 141-147: label/time pairs at fixed positions
    render_text(canvas, font_label, station['north'], 18, 4, COLORS['label'])
    render_text(canvas, font_time, north, 18, 11, COLORS['time'])
    render_text(canvas, font_label, station['south'], 18, 20, COLORS['label'])
    render_text(canvas, font_time, south, 18, 27, COLORS['time'])
    return canvas


if __name__ == '__main__':
    main()
