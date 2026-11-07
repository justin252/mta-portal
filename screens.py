"""What each screen shows, as data. Works on both CircuitPython and desktop.

Pure functions from live (or scenario) data to a screen state:
    {'screen': 'L' | 'G' | 'weather' | 'art', 'bitmap': file,
     'texts': {field: text}, 'colors': {field: 0xRRGGBB}}
app.py applies states to the LEDs and simulate_display.py renders the same states,
so the board and the simulator draw from one definition.
"""

import layout
from logic import times_text
from weather import DEFAULT_CONDITION, format_hi_lo, format_temperature, map_condition


def _colors(fields):
    return {field: layout.COLORS[role] for field, role, _, _ in fields}


# Arrival rows when there are no numbers to show; gold is only ever used for live numbers
EMPTY = {'loading': 'Loading', 'offline': 'Offline'}


def _row(minutes, fresh):
    """(text, color) for one direction's arrival row."""
    if fresh in EMPTY:
        return EMPTY[fresh], layout.COLORS['label']
    text = times_text(minutes)
    live = fresh == 'live' and minutes
    return text, layout.COLORS['time'] if live else layout.COLORS['label']


def train_state(line, north, south, fresh='live'):
    """Arrival minutes (soonest first) for one line -> that line's screen.
    fresh is logic.freshness(): 'live', 'stale', 'loading' or 'offline'."""
    station = layout.STATIONS[line]
    (n_text, n_color), (s_text, s_color) = _row(north, fresh), _row(south, fresh)
    colors = _colors(layout.TRAIN_FIELDS)
    colors['north_times'], colors['south_times'] = n_color, s_color
    return {'screen': line, 'bitmap': station['bitmap'],
            'texts': {'north': station['north'], 'north_times': n_text,
                      'south': station['south'], 'south_times': s_text},
            'colors': colors}


def weather_state(reading):
    """Weather reading (weather.parse_weather) -> the weather screen."""
    bitmap, condition = map_condition(reading['code'], reading.get('is_day', True))
    return {'screen': 'weather', 'bitmap': bitmap,
            'texts': {'condition': condition, 'temp': format_temperature(reading['temp_f']),
                      'hi_lo': format_hi_lo(reading['hi_f'], reading['lo_f'])},
            'colors': _colors(layout.WEATHER_FIELDS)}


def weather_placeholder():
    """Before the first reading (the weather screen stays out of the cycle until then)."""
    return {'screen': 'weather', 'bitmap': DEFAULT_CONDITION[0],
            'texts': {'condition': '--', 'temp': '--', 'hi_lo': ''},
            'colors': _colors(layout.WEATHER_FIELDS)}


def art_state(bitmap):
    return {'screen': 'art', 'bitmap': bitmap, 'texts': {}, 'colors': {}}
