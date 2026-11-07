"""screens.py builds what each screen shows; the board applies these states and the
simulator renders them, so these tests pin down the content both sides draw."""
import layout
from screens import art_state, train_state, weather_placeholder, weather_state


def test_train_state():
    st = train_state('L', [2, 6, 11, 15], [4])
    assert st['screen'] == 'L' and st['bitmap'] == 'l-dashboard.bmp'
    assert st['texts'] == {'north': 'Manhattan', 'north_times': '2,6,11',
                           'south': 'Canarsie', 'south_times': '4,-,-'}
    assert st['colors'] == {'north': layout.COLORS['label'], 'north_times': layout.COLORS['time'],
                            'south': layout.COLORS['label'], 'south_times': layout.COLORS['time']}


def test_train_state_without_data():
    assert train_state('G', [], [])['texts']['north_times'] == '-,-,-'


def test_weather_state():
    st = weather_state({'code': 63, 'temp_f': 48.6, 'hi_f': 61.0, 'lo_f': 45.4})
    assert st['screen'] == 'weather' and st['bitmap'] == 'weather-rain.bmp'
    assert st['texts'] == {'condition': 'Rain', 'temp': '49°F', 'hi_lo': 'H:61 L:45'}
    assert set(st['colors']) == {f[0] for f in layout.WEATHER_FIELDS}


def test_weather_placeholder_has_every_field():
    st = weather_placeholder()
    assert set(st['texts']) == {f[0] for f in layout.WEATHER_FIELDS}


def test_art_state():
    assert art_state('train.bmp') == {'screen': 'art', 'bitmap': 'train.bmp', 'texts': {}, 'colors': {}}
