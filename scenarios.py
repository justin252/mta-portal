"""Every design the sign can show, with fixed data. Works on both CircuitPython and desktop.

Review designs on the real sign one at a time (`make review`, or `tools/portal.py show NAME`)
and verify each pixel for pixel against the simulator (`make verify`). Add a scenario for
every new design state: tests fail if a weather condition or screen kind has none.
"""

import screens

SCENARIOS = (
    # Train screens: live, then every empty state
    {'name': 'L', 'clock': '12:52', 'about': 'L train, typical arrivals', 'train': ('L', [2, 6, 11], [4, 9, 14])},
    {'name': 'G', 'clock': '6:05', 'about': 'G train, one train southbound', 'train': ('G', [5, 15, 24], [8])},
    {'name': 'L-widest', 'clock': '10:47', 'about': 'L train, widest times that fit', 'train': ('L', [97, 98, 99], [97, 98, 99])},
    {'name': 'G-no-trains', 'clock': '9:41', 'about': 'No G trains listed northbound (service change)',
     'train': ('G', [], [3, 12, 21])},
    {'name': 'L-stale', 'clock': '7:30', 'about': 'Data over 90s old: numbers dim until a fetch succeeds',
     'train': ('L', [2, 6, 11], [4, 9, 14], 'stale')},
    {'name': 'L-loading', 'about': 'Just booted, first fetch not back yet', 'train': ('L', [], [], 'loading')},
    {'name': 'L-offline', 'about': 'No data and fetches failing (outage)', 'train': ('L', [], [], 'offline')},
    # Weather: every icon and label, day and night
    {'name': 'weather-clear', 'clock': '12:52', 'about': 'Clear day',
     'weather': {'code': 0, 'temp_f': 72.4, 'hi_f': 81, 'lo_f': 65}},
    {'name': 'weather-clear-night', 'clock': '11:08', 'about': 'Clear night',
     'weather': {'code': 0, 'temp_f': 41, 'hi_f': 55, 'lo_f': 39, 'is_day': False}},
    {'name': 'weather-cloudy', 'clock': '1:15', 'about': 'Partly cloudy day',
     'weather': {'code': 2, 'temp_f': 58, 'hi_f': 63, 'lo_f': 50}},
    {'name': 'weather-cloudy-night', 'clock': '10:47', 'about': 'Partly cloudy night',
     'weather': {'code': 2, 'temp_f': 47, 'hi_f': 58, 'lo_f': 44, 'is_day': False}},
    {'name': 'weather-overcast', 'clock': '7:45', 'about': 'Overcast, widest negative temperatures',
     'weather': {'code': 3, 'temp_f': -9.6, 'hi_f': -2, 'lo_f': -15}},
    {'name': 'weather-fog', 'clock': '6:30', 'about': 'Fog', 'weather': {'code': 45, 'temp_f': 51, 'hi_f': 55, 'lo_f': 48}},
    {'name': 'weather-drizzle', 'clock': '4:20', 'about': 'Drizzle', 'weather': {'code': 53, 'temp_f': 47, 'hi_f': 52, 'lo_f': 44}},
    {'name': 'weather-rain', 'clock': '5:55', 'about': 'Rain', 'weather': {'code': 63, 'temp_f': 63, 'hi_f': 68, 'lo_f': 57}},
    {'name': 'weather-showers', 'clock': '3:10', 'about': 'Rain showers',
     'weather': {'code': 81, 'temp_f': 66, 'hi_f': 74, 'lo_f': 61}},
    {'name': 'weather-sleet', 'clock': '8:05', 'about': 'Sleet (freezing rain)',
     'weather': {'code': 66, 'temp_f': 31, 'hi_f': 34, 'lo_f': 27}},
    {'name': 'weather-snow', 'clock': '9:00', 'about': 'Snow', 'weather': {'code': 73, 'temp_f': 28, 'hi_f': 31, 'lo_f': 19}},
    {'name': 'weather-storm', 'clock': '11:11', 'about': 'Thunderstorm, widest 3-digit temperatures',
     'weather': {'code': 95, 'temp_f': 100.2, 'hi_f': 104, 'lo_f': 88}},
    # Art mode (UP button)
    {'name': 'art-train', 'about': 'Art: rooftop disco on the L', 'art': 'art-train.bmp'},
    {'name': 'art-skyline', 'about': 'Art: Manhattan skyline at night', 'art': 'art-skyline.bmp'},
    {'name': 'art-bridge', 'about': 'Art: Williamsburg Bridge at dusk', 'art': 'art-bridge.bmp'},
    {'name': 'art-rat', 'about': 'Art: pizza rat', 'art': 'art-rat.bmp'},
)
BY_NAME = {s['name']: s for s in SCENARIOS}


def state(scenario):
    """Scenario -> screen state, through the same builders live data uses. Loading and
    offline scenarios have no clock: the board only knows the time after a good fetch."""
    clock = scenario.get('clock', '')
    if 'train' in scenario:
        line, north, south = scenario['train'][:3]
        fresh = scenario['train'][3] if len(scenario['train']) > 3 else 'live'
        return screens.train_state(line, north, south, fresh, clock)
    if 'weather' in scenario:
        return screens.weather_state(scenario['weather'], clock)
    return screens.art_state(scenario['art'])
