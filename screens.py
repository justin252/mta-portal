"""What each screen shows, as data. Works on both CircuitPython and desktop.

Pure functions from live (or scenario) data to a screen state:
    {'screen': 'L' | 'G' | 'weather' | 'art', 'bitmap': file,
     'texts': {field: text}, 'colors': {field: 0xRRGGBB}}
app.py applies states to the LEDs and simulate_display.py renders the same states,
so the board and the simulator draw from one definition.
"""

import layout
from logic import format_arrival_triple
from weather import DEFAULT_CONDITION, format_hi_lo, format_temperature, map_condition


def _colors(fields):
    return {field: layout.COLORS[role] for field, role, _, _ in fields}


def train_state(line, north, south):
    """Arrival minutes (soonest first) for one line -> that line's screen."""
    station = layout.STATIONS[line]
    return {'screen': line, 'bitmap': station['bitmap'],
            'texts': {'north': station['north'], 'north_times': '%s,%s,%s' % format_arrival_triple(north),
                      'south': station['south'], 'south_times': '%s,%s,%s' % format_arrival_triple(south)},
            'colors': _colors(layout.TRAIN_FIELDS)}


def weather_state(reading):
    """Weather reading {'code', 'temp_f', 'hi_f', 'lo_f'} -> the weather screen."""
    bitmap, condition = map_condition(reading['code'])
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
