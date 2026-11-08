"""Screen layout shared by app.py (board) and simulate_display.py (desktop).

One source of truth so the simulator can't drift from the board. Transit screens are two
boxes: the left one holds the clock over the line logo or weather icon, the right one the
text lines, each field centered in its box (centered_x). Text uses adafruit_display_text
Label semantics: x is the left edge, and each glyph's top lands at
y - glyph_height - glyph_yoffset + font_ascent // 2. Board framebuffer captures in
test_fixtures/device/ pin this down (test_simulate_display.py).
"""

WIDTH, HEIGHT = 64, 32
BIT_DEPTH = 2  # Matrix() default: the LEDs show only the top 2 bits of each color channel

LEFT_BOX = (0, 19)    # (x, width): clock over the logo or icon, both centered on x=9
RIGHT_BOX = (22, 42)  # a 3px gap, then the text lines
CLOCK_Y = 7           # clock ink on rows 4-8 on every transit screen; logos and icons start at row 11

FONTS = {'label': 'fonts/tom-thumb.bdf', 'time': 'fonts/spleen-5x8.bdf', 'clock': 'fonts/clock.bdf'}
COLORS = {'label': 0x444444, 'time': 0xDD8000, 'clock': 0x444444}  # dim white, gold, dim white

# (field, font/color role, box, y) in display-group order, after the bitmap at index 0
TRAIN_FIELDS = (
    ('clock', 'clock', LEFT_BOX, CLOCK_Y),
    ('north', 'label', RIGHT_BOX, 4),
    ('north_times', 'time', RIGHT_BOX, 11),
    ('south', 'label', RIGHT_BOX, 20),
    ('south_times', 'time', RIGHT_BOX, 27),
    # Small status text in the times row, shown only while the times are blank. Its own
    # Label: display_text 3.3.4 keeps the old ascent when a Label's font changes (1px off)
    ('north_status', 'label', RIGHT_BOX, 11),
    ('south_status', 'label', RIGHT_BOX, 27),
)
WEATHER_FIELDS = (
    ('clock', 'clock', LEFT_BOX, CLOCK_Y),
    ('condition', 'label', RIGHT_BOX, 6),
    ('temp', 'time', RIGHT_BOX, 16),
    ('hi_lo', 'label', RIGHT_BOX, 26),
)

LINES = ('L', 'G')  # transit cycle order
STATIONS = {
    'L': {'stop_id': 'L11', 'north': 'Manhattan', 'south': 'Canarsie', 'bitmap': 'l-dashboard.bmp'},
    'G': {'stop_id': 'G29', 'north': 'Queens', 'south': 'Church Av', 'bitmap': 'g-dashboard.bmp'},
}
ART = ('art-train.bmp', 'art-skyline.bmp', 'art-bridge.bmp', 'art-rat.bmp')  # art mode, in order


def centered_x(text, glyph, box):
    """Label x that centers text's ink in box (x, width). glyph(ch) -> (advance, xoff, width)
    for the font the text is drawn in. One function so the board and simulator agree."""
    if not text:
        return box[0]
    advance = sum(glyph(ch)[0] for ch in text[:-1])
    first_xoff = glyph(text[0])[1]
    _, last_xoff, last_width = glyph(text[-1])
    width = advance + last_xoff + last_width - first_xoff
    return box[0] + (box[1] - width) // 2 - first_xoff
