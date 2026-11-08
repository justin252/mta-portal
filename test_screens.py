"""screens.py builds what each screen shows; the board applies these states and the
simulator renders them, so these tests pin down the content both sides draw."""
import pytest

import layout
from screens import art_state, train_state, weather_placeholder, weather_state

GOLD, DIM = layout.COLORS['time'], layout.COLORS['label']


def test_train_state_live():
    st = train_state('L', [2, 6, 11, 15], [4], clock='6:05')
    assert st['screen'] == 'L' and st['bitmap'] == 'l-dashboard.bmp'
    assert st['texts'] == {'clock': '6:05', 'north': 'Manhattan', 'north_times': '2,6,11', 'north_status': '',
                           'south': 'Canarsie', 'south_times': '4,-,-', 'south_status': ''}
    assert st['colors'] == {'clock': DIM, 'north': DIM, 'north_times': GOLD, 'south': DIM, 'south_times': GOLD,
                            'north_status': DIM, 'south_status': DIM}


def test_clock_blank_until_known():
    assert train_state('L', [], [], 'loading')['texts']['clock'] == ''
    assert weather_placeholder()['texts']['clock'] == ''


@pytest.mark.parametrize('fresh,times,status', [
    ('stale', '2,6,11', ''),           # old numbers stay, dimmed: gold always means live
    ('loading', '', '\u2022\u2022\u2022'),  # three small dots, quieter than the direction names
    ('offline', '', 'offline'),
])
def test_train_empty_and_stale_states(fresh, times, status):
    st = train_state('G', [2, 6, 11], [5], fresh)
    assert (st['texts']['north_times'], st['texts']['north_status']) == (times, status)
    assert st['colors']['north_times'] == DIM == st['colors']['south_times']


def test_no_trains_is_dim_dashes():
    st = train_state('G', [], [5])
    assert (st['texts']['north_times'], st['colors']['north_times']) == ('-,-,-', DIM)
    assert (st['texts']['south_times'], st['colors']['south_times']) == ('5,-,-', GOLD)


def test_weather_state():
    st = weather_state({'code': 63, 'temp_f': 48.6, 'hi_f': 61.0, 'lo_f': 45.4, 'is_day': True})
    assert st['screen'] == 'weather' and st['bitmap'] == 'weather-rain.bmp'
    assert st['texts'] == {'clock': '', 'condition': 'Rain', 'temp': '49°F', 'hi_lo': 'H:61 L:45'}
    assert set(st['colors']) == {f[0] for f in layout.WEATHER_FIELDS}


def test_weather_state_at_night():
    st = weather_state({'code': 0, 'temp_f': 40, 'hi_f': 50, 'lo_f': 38, 'is_day': False})
    assert st['bitmap'] == 'weather-moon.bmp'


def test_weather_placeholder_has_every_field():
    st = weather_placeholder()
    assert set(st['texts']) == {f[0] for f in layout.WEATHER_FIELDS}


def test_art_state():
    assert art_state('art-train.bmp') == {'screen': 'art', 'bitmap': 'art-train.bmp', 'texts': {}, 'colors': {}}
