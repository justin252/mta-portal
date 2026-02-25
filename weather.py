"""Pure functions for weather data. Works on both CircuitPython and desktop."""

CONDITION_MAP = {
    'skc': ('weather-sun.bmp', 'Clear'),
    'few': ('weather-sun.bmp', 'Clear'),
    'sct': ('weather-cloud.bmp', 'Cloudy'),
    'bkn': ('weather-cloud.bmp', 'Cloudy'),
    'ovc': ('weather-cloud.bmp', 'Overcast'),
    'rain': ('weather-rain.bmp', 'Rain'),
    'rain_showers': ('weather-rain.bmp', 'Rain'),
    'snow': ('weather-snow.bmp', 'Snow'),
    'sleet': ('weather-snow.bmp', 'Sleet'),
    'tsra': ('weather-storm.bmp', 'Storm'),
    'fog': ('weather-fog.bmp', 'Fog'),
    'haze': ('weather-fog.bmp', 'Haze'),
}
DEFAULT_CONDITION = ('weather-cloud.bmp', 'Cloudy')


def parse_nws_forecast(data):
    """Extract temp_f, short_forecast, icon_url from NWS forecast response."""
    period = data['properties']['periods'][0]
    return {
        'temp_f': period['temperature'],
        'short_forecast': period['shortForecast'],
        'icon_url': period.get('icon', ''),
    }


def map_condition(icon_url):
    """Parse NWS icon URL to (bitmap_filename, display_label). Falls back to cloudy."""
    if not icon_url:
        return DEFAULT_CONDITION
    # URL format: https://api.weather.gov/icons/land/{day|night}/{condition},{pct}
    # May have two conditions: sct/snow,80 — pick the most impactful (last match)
    parts = icon_url.rstrip('/').split('/')
    for part in reversed(parts):
        code = part.split(',')[0].split('?')[0]
        if code in CONDITION_MAP:
            return CONDITION_MAP[code]
    return DEFAULT_CONDITION


def format_temperature(temp_f):
    """Format temperature for display."""
    return '%d\u00b0F' % round(temp_f)
