"""Every design the sign can show, with fixed data. Works on both CircuitPython and desktop.

Review designs on the real sign one at a time (`make review`, or `tools/portal.py show NAME`)
and verify each pixel for pixel against the simulator (`make verify`). Add a scenario for
every new design state: tests fail if a weather condition or screen kind has none.
"""

import screens

SCENARIOS = (
    {'name': 'L', 'about': 'L train, typical arrivals', 'train': ('L', [2, 6, 11], [4, 9, 14])},
    {'name': 'G', 'about': 'G train, one train southbound', 'train': ('G', [5, 15, 24], [8])},
    {'name': 'L-widest', 'about': 'L train, widest times that fit', 'train': ('L', [97, 98, 99], [97, 98, 99])},
    {'name': 'weather-clear', 'about': 'Clear, warm day',
     'weather': {'code': 0, 'temp_f': 72.4, 'hi_f': 81, 'lo_f': 65}},
    {'name': 'weather-cloudy', 'about': 'Partly cloudy',
     'weather': {'code': 2, 'temp_f': 58, 'hi_f': 63, 'lo_f': 50}},
    {'name': 'weather-overcast', 'about': 'Overcast, widest negative temperatures',
     'weather': {'code': 3, 'temp_f': -9.6, 'hi_f': -2, 'lo_f': -15}},
    {'name': 'weather-fog', 'about': 'Fog', 'weather': {'code': 45, 'temp_f': 51, 'hi_f': 55, 'lo_f': 48}},
    {'name': 'weather-drizzle', 'about': 'Drizzle', 'weather': {'code': 53, 'temp_f': 47, 'hi_f': 52, 'lo_f': 44}},
    {'name': 'weather-rain', 'about': 'Rain', 'weather': {'code': 63, 'temp_f': 63, 'hi_f': 68, 'lo_f': 57}},
    {'name': 'weather-showers', 'about': 'Rain showers',
     'weather': {'code': 81, 'temp_f': 66, 'hi_f': 74, 'lo_f': 61}},
    {'name': 'weather-sleet', 'about': 'Sleet (freezing rain)',
     'weather': {'code': 66, 'temp_f': 31, 'hi_f': 34, 'lo_f': 27}},
    {'name': 'weather-snow', 'about': 'Snow', 'weather': {'code': 73, 'temp_f': 28, 'hi_f': 31, 'lo_f': 19}},
    {'name': 'weather-storm', 'about': 'Thunderstorm, widest 3-digit temperatures',
     'weather': {'code': 95, 'temp_f': 100.2, 'hi_f': 104, 'lo_f': 88}},
    {'name': 'art-train', 'about': 'Train art (rooftop disco)', 'art': 'train.bmp'},
)
BY_NAME = {s['name']: s for s in SCENARIOS}


def state(scenario):
    """Scenario -> screen state, through the same builders live data uses."""
    if 'train' in scenario:
        return screens.train_state(*scenario['train'])
    if 'weather' in scenario:
        return screens.weather_state(scenario['weather'])
    return screens.art_state(scenario['art'])
