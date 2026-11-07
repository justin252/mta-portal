"""Screen layout shared by app.py (board) and simulate_display.py (desktop).

One source of truth so the simulator can't drift from the board. Text uses
adafruit_display_text Label semantics: x is the left edge, and each glyph's top lands
at y - glyph_height - glyph_yoffset + font_ascent // 2. Board framebuffer captures in
test_fixtures/device/ pin this down (test_simulate_display.py).
"""

WIDTH, HEIGHT = 64, 32
BIT_DEPTH = 2  # Matrix() default: the LEDs show only the top 2 bits of each color channel
TEXT_X = 18    # all text starts here; the logo or weather icon fills columns 1-15

FONTS = {'label': 'fonts/tom-thumb.bdf', 'time': 'fonts/spleen-5x8.bdf'}
COLORS = {'label': 0x444444, 'time': 0xDD8000}  # dim white, gold

# (field, font/color role, x, y) in display-group order, after the bitmap at index 0
TRAIN_FIELDS = (
    ('north', 'label', TEXT_X, 4),
    ('north_times', 'time', TEXT_X, 11),
    ('south', 'label', TEXT_X, 20),
    ('south_times', 'time', TEXT_X, 27),
)
WEATHER_FIELDS = (
    ('condition', 'label', TEXT_X, 10),
    ('temp', 'time', TEXT_X, 22),
)

LINES = ('L', 'G')  # screen order: UP jumps to LINES[0], DOWN to LINES[1]
STATIONS = {
    'L': {'stop_id': 'L11', 'north': 'Manhattan', 'south': 'Canarsie', 'bitmap': 'l-dashboard.bmp'},
    'G': {'stop_id': 'G29', 'north': 'Queens', 'south': 'Church Av', 'bitmap': 'g-dashboard.bmp'},
}
TRAIN_ART = 'train.bmp'
