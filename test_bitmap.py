import os
from PIL import Image
import pytest

BMP_DIR = os.path.dirname(__file__)
LETTER_COLOR = (0, 0, 0)
BLACK = (0, 0, 0)
CIRCLE_X = 8
CIRCLE_Y = 16
CIRCLE_RADIUS = 7

TRAINS = {
    'L': {'path': os.path.join(BMP_DIR, 'l-dashboard.bmp'), 'color': (167, 169, 172)},
    'G': {'path': os.path.join(BMP_DIR, 'g-dashboard.bmp'), 'color': (108, 190, 69)},
}


def render_circle_ascii(img, color):
    """Render the circle region as ASCII art for readable test failures.

    Returns string like:
        ...XXX...
        ..XXXXX..
        .XXX.XXX.
        .XXXXXXX.
        ..XXXXX..
        ...XXX...

    Where X = circle color, . = letter (black), ' ' = outside (black bg).
    """
    r = CIRCLE_RADIUS
    lines = []
    for y in range(CIRCLE_Y - r, CIRCLE_Y + r + 1):
        row = ''
        for x in range(CIRCLE_X - r, CIRCLE_X + r + 1):
            px = img.getpixel((x, y))
            if px == color:
                row += 'X'
            elif px == BLACK:
                dx, dy = x - CIRCLE_X, y - CIRCLE_Y
                if dx * dx + dy * dy <= r * r:
                    row += '.'  # black pixel inside circle = letter
                else:
                    row += ' '  # outside circle
            else:
                row += '?'  # unexpected color
        lines.append(row)
    return '\n'.join(lines)


@pytest.fixture(params=['L', 'G'])
def train(request):
    cfg = TRAINS[request.param]
    return {
        'letter': request.param,
        'img': Image.open(cfg['path']),
        'color': cfg['color'],
    }


def test_dimensions(train):
    assert train['img'].size == (64, 32)


def test_circle_color(train):
    img, color = train['img'], train['color']
    assert img.getpixel((CIRCLE_X, CIRCLE_Y + 6)) == color, \
        f"Circle region:\n{render_circle_ascii(img, color)}"


def test_circle_edges(train):
    img, color = train['img'], train['color']
    viz = f"Circle region:\n{render_circle_ascii(img, color)}"
    assert img.getpixel((CIRCLE_X, CIRCLE_Y - CIRCLE_RADIUS)) == color, viz
    assert img.getpixel((CIRCLE_X, CIRCLE_Y + CIRCLE_RADIUS)) == color, viz
    assert img.getpixel((CIRCLE_X - CIRCLE_RADIUS, CIRCLE_Y)) == color, viz
    assert img.getpixel((CIRCLE_X + CIRCLE_RADIUS, CIRCLE_Y)) == color, viz


def test_no_text_overlap(train):
    assert train['img'].getpixel((17, CIRCLE_Y)) == BLACK


def test_letter_present(train):
    img, color = train['img'], train['color']
    letter_pixels = 0
    for x in range(CIRCLE_X - 4, CIRCLE_X + 4):
        for y in range(CIRCLE_Y - 4, CIRCLE_Y + 4):
            if img.getpixel((x, y)) == LETTER_COLOR:
                letter_pixels += 1
    assert letter_pixels > 5, \
        f"Only {letter_pixels} letter pixels found.\n{render_circle_ascii(img, color)}"


def test_letter_centered(train):
    img, color, letter = train['img'], train['color'], train['letter']
    viz = f"Circle region:\n{render_circle_ascii(img, color)}"

    # Find letter pixels (black inside circle, not background)
    r_sq = CIRCLE_RADIUS * CIRCLE_RADIUS
    xs, ys = [], []
    for y in range(CIRCLE_Y - 6, CIRCLE_Y + 6):
        for x in range(CIRCLE_X - 6, CIRCLE_X + 6):
            dx, dy = x - CIRCLE_X, y - CIRCLE_Y
            if dx * dx + dy * dy < r_sq and img.getpixel((x, y)) == LETTER_COLOR:
                xs.append(x)
                ys.append(y)
    assert len(xs) > 0, f"No letter pixels found.\n{viz}"
    mid_x = (min(xs) + max(xs)) / 2
    mid_y = (min(ys) + max(ys)) / 2
    assert abs(mid_x - CIRCLE_X) <= 0.5, \
        f"{letter} x center={mid_x}, expected ~{CIRCLE_X}\n{viz}"
    assert abs(mid_y - CIRCLE_Y) <= 0.5, \
        f"{letter} y center={mid_y}, expected ~{CIRCLE_Y}\n{viz}"
