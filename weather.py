"""Pure functions for the weather screen. Works on both CircuitPython and desktop.

Open-Meteo current conditions plus today's high/low: ~560 bytes of JSON, no API key.
(The NWS forecast was 13 KB, too much to parse on a heap where a 4 KB allocation fails.)
"""

# Between Graham Av and Metropolitan Av; timezone=auto makes "today" New York's day
WEATHER_URL = ('https://api.open-meteo.com/v1/forecast?latitude=40.714&longitude=-73.948'
               '&current=temperature_2m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min'
               '&temperature_unit=fahrenheit&timezone=auto&forecast_days=1')

# WMO weather code ranges (inclusive) -> (icon bitmap, label). Codes: open-meteo.com/en/docs
CONDITIONS = (
    (0, 1, 'weather-sun.bmp', 'Clear'),
    (2, 2, 'weather-partly.bmp', 'Cloudy'),
    (3, 3, 'weather-cloud.bmp', 'Overcast'),
    (45, 48, 'weather-fog.bmp', 'Fog'),
    (51, 55, 'weather-drizzle.bmp', 'Drizzle'),
    (56, 57, 'weather-sleet.bmp', 'Sleet'),
    (61, 65, 'weather-rain.bmp', 'Rain'),
    (66, 67, 'weather-sleet.bmp', 'Sleet'),
    (71, 77, 'weather-snow.bmp', 'Snow'),
    (80, 82, 'weather-showers.bmp', 'Showers'),
    (85, 86, 'weather-snow.bmp', 'Snow'),
    (95, 99, 'weather-storm.bmp', 'Storm'),
)
DEFAULT_CONDITION = ('weather-cloud.bmp', 'Cloudy')
NIGHT = {'weather-sun.bmp': 'weather-moon.bmp', 'weather-partly.bmp': 'weather-partly-night.bmp'}

def parse_weather(data):
    """Open-Meteo response -> {'temp_f', 'code', 'hi_f', 'lo_f', 'is_day'}. Raises on unexpected shape."""
    current, daily = data['current'], data['daily']
    return {'temp_f': current['temperature_2m'], 'code': current['weather_code'],
            'hi_f': daily['temperature_2m_max'][0], 'lo_f': daily['temperature_2m_min'][0],
            'is_day': current.get('is_day', 1) == 1}


def map_condition(code, is_day=True):
    """WMO weather code -> (bitmap filename, display label). Unknown codes fall back to cloudy;
    at night the sun icons become moons."""
    for lo, hi, bitmap, label in CONDITIONS:
        if lo <= code <= hi:
            return (bitmap if is_day else NIGHT.get(bitmap, bitmap)), label
    return DEFAULT_CONDITION


def format_temperature(temp_f):
    """Format temperature for display."""
    return '%d°F' % round(temp_f)


def format_hi_lo(hi_f, lo_f):
    return 'H:%d L:%d' % (round(hi_f), round(lo_f))
