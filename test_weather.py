"""Tests for weather.py — pure weather logic."""
import json
import os
import pytest
from weather import parse_nws_forecast, map_condition, format_temperature

FIXTURES = os.path.join(os.path.dirname(__file__), 'test_fixtures')


class TestParseNwsForecast:
    def test_basic(self):
        data = {'properties': {'periods': [
            {'temperature': 42, 'shortForecast': 'Partly Cloudy', 'icon': 'https://api.weather.gov/icons/land/day/sct,20'}
        ]}}
        result = parse_nws_forecast(data)
        assert result == {'temp_f': 42, 'short_forecast': 'Partly Cloudy', 'icon_url': 'https://api.weather.gov/icons/land/day/sct,20'}

    def test_missing_icon(self):
        data = {'properties': {'periods': [
            {'temperature': 30, 'shortForecast': 'Snow'}
        ]}}
        result = parse_nws_forecast(data)
        assert result['icon_url'] == ''

    def test_negative_temp(self):
        data = {'properties': {'periods': [
            {'temperature': -5, 'shortForecast': 'Cold', 'icon': ''}
        ]}}
        assert parse_nws_forecast(data)['temp_f'] == -5


class TestMapCondition:
    @pytest.mark.parametrize("url,expected_bmp,expected_label", [
        ('https://api.weather.gov/icons/land/day/skc', 'weather-sun.bmp', 'Clear'),
        ('https://api.weather.gov/icons/land/day/few', 'weather-sun.bmp', 'Clear'),
        ('https://api.weather.gov/icons/land/day/sct,20', 'weather-cloud.bmp', 'Cloudy'),
        ('https://api.weather.gov/icons/land/day/bkn', 'weather-cloud.bmp', 'Cloudy'),
        ('https://api.weather.gov/icons/land/day/ovc', 'weather-cloud.bmp', 'Overcast'),
        ('https://api.weather.gov/icons/land/day/rain', 'weather-rain.bmp', 'Rain'),
        ('https://api.weather.gov/icons/land/day/rain_showers,50', 'weather-rain.bmp', 'Rain'),
        ('https://api.weather.gov/icons/land/day/snow', 'weather-snow.bmp', 'Snow'),
        ('https://api.weather.gov/icons/land/day/sleet', 'weather-snow.bmp', 'Sleet'),
        ('https://api.weather.gov/icons/land/day/tsra', 'weather-storm.bmp', 'Storm'),
        ('https://api.weather.gov/icons/land/day/fog', 'weather-fog.bmp', 'Fog'),
        ('https://api.weather.gov/icons/land/day/haze', 'weather-fog.bmp', 'Haze'),
        ('https://api.weather.gov/icons/land/night/skc', 'weather-sun.bmp', 'Clear'),
    ])
    def test_conditions(self, url, expected_bmp, expected_label):
        bmp, label = map_condition(url)
        assert bmp == expected_bmp
        assert label == expected_label

    def test_empty_url(self):
        assert map_condition('') == ('weather-cloud.bmp', 'Cloudy')

    def test_unknown_condition(self):
        assert map_condition('https://api.weather.gov/icons/land/day/xyz') == ('weather-cloud.bmp', 'Cloudy')

    def test_dual_condition_picks_impactful(self):
        """NWS URLs can have two conditions (transition). We pick the last (most impactful)."""
        bmp, label = map_condition('https://api.weather.gov/icons/land/night/sct/snow,80?size=medium')
        assert bmp == 'weather-snow.bmp'
        assert label == 'Snow'

    def test_size_param_stripped(self):
        bmp, _ = map_condition('https://api.weather.gov/icons/land/day/rain,40?size=medium')
        assert bmp == 'weather-rain.bmp'


class TestFormatTemperature:
    @pytest.mark.parametrize("temp,expected", [
        (42, '42°F'),
        (0, '0°F'),
        (-5, '-5°F'),
        (100, '100°F'),
        (72.6, '73°F'),
    ])
    def test_formatting(self, temp, expected):
        assert format_temperature(temp) == expected


class TestNwsIntegration:
    """End-to-end test using a saved real NWS API response."""

    @pytest.fixture
    def nws_data(self):
        with open(os.path.join(FIXTURES, 'nws_sample.json')) as f:
            return json.load(f)

    def test_parse_returns_valid_types(self, nws_data):
        weather = parse_nws_forecast(nws_data)
        assert isinstance(weather['temp_f'], (int, float))
        assert isinstance(weather['short_forecast'], str)
        assert isinstance(weather['icon_url'], str)

    def test_icon_url_maps_to_known_bitmap(self, nws_data):
        weather = parse_nws_forecast(nws_data)
        bmp, label = map_condition(weather['icon_url'])
        assert bmp.startswith('weather-') and bmp.endswith('.bmp')
        assert len(label) <= 10

    def test_temp_formats_cleanly(self, nws_data):
        weather = parse_nws_forecast(nws_data)
        temp_str = format_temperature(weather['temp_f'])
        assert temp_str.endswith('°F')
        # Strip suffix and verify it's a number
        num_part = temp_str.replace('°F', '')
        int(num_part)  # raises if not a valid int string

    def test_full_pipeline(self, nws_data):
        """Entire flow: parse → map → format. No step crashes, output is display-ready."""
        weather = parse_nws_forecast(nws_data)
        bmp, label = map_condition(weather['icon_url'])
        temp = format_temperature(weather['temp_f'])
        # All outputs are short enough for the 46px display area
        assert len(label) <= 10
        assert len(temp) <= 6
